"""WP-048-reservation: exact, durable, atomic multi-scope exposure ledger.

This private database is outside civilization history. Completion/cancel/crash
never releases exposure. A known reported actual replaces its estimate.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
from fractions import Fraction
from poliscope_engine.numeric import parse, canonical, exact, calculate
from poliscope_engine.contracts.spending import SpendReserve, SpendReply, SpendObserve, SpendConfigure, UsageObservation, SpendHistory, SpendRecord, SpendBinding, SpendOrigin


def units(value: str) -> int:
    amount = Fraction(parse(value)) * 1000000
    if amount.denominator != 1 or amount < 0:
        raise ValueError('invalid_exposure')
    return amount.numerator


def money(value: int) -> str:
    return canonical(exact(Fraction(value, 1000000)))


def catalog_cost(c) -> Fraction:
    prompt = calculate(parse(c.prompt_rate), parse(str(c.input_bound)), 'multiply')
    completion = calculate(parse(c.completion_rate), parse(str(c.output_bound)), 'multiply')
    estimate = calculate(calculate(prompt, completion, 'add'), parse(c.request_rate), 'add')
    oracle = Fraction(c.prompt_rate)*c.input_bound + Fraction(c.completion_rate)*c.output_bound + Fraction(c.request_rate)
    if Fraction(estimate) != oracle:
        raise ValueError('inexact_catalog_estimate')
    return Fraction(estimate)


class Spending:
    def __init__(self, path: Path):
        if not path.is_absolute():
            raise ValueError('invalid_spending_path')
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS spending_version(version INTEGER NOT NULL);
        INSERT INTO spending_version SELECT 1 WHERE NOT EXISTS(SELECT 1 FROM spending_version);
        CREATE TABLE IF NOT EXISTS grants(
          dispatch TEXT PRIMARY KEY, binding TEXT NOT NULL, turn_id TEXT NOT NULL,
          session_id TEXT NOT NULL, profile_id TEXT NOT NULL, exposure INTEGER NOT NULL,
          state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS limits(scope TEXT PRIMARY KEY, allowance INTEGER NOT NULL);
        ''')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS dispatch_records(dispatch TEXT PRIMARY KEY, binding TEXT NOT NULL, origin TEXT);
        CREATE TABLE IF NOT EXISTS observations(dispatch TEXT PRIMARY KEY, usage TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS observation_events(dispatch TEXT NOT NULL, fingerprint TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(dispatch,fingerprint));
        CREATE TABLE IF NOT EXISTS discrepancies(dispatch TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS estimates(dispatch TEXT PRIMARY KEY, catalog TEXT NOT NULL, amount TEXT NOT NULL);
        ''')
        if self.db.execute('SELECT version FROM spending_version').fetchall() != [(1,)]:
            self.db.close()
            raise ValueError('unsupported_spending_version')
        path.chmod(0o600)

    def close(self):
        self.db.close()

    def request(self, query):
        b = query.binding
        binding = hashlib.sha256(b.model_dump_json().encode()).hexdigest()
        def charge(dispatch, exposure):
            observed = self.db.execute('SELECT usage FROM observations WHERE dispatch=?', (dispatch,)).fetchone()
            actual = json.loads(observed[0]).get('actual_cost') if observed else None
            return Fraction(actual) if actual is not None else Fraction(exposure, 1000000)
        def total(kind, identity, exclude=None):
            rows = self.db.execute(f"SELECT dispatch,exposure FROM grants WHERE {kind}_id=? AND state!='no-send'", (identity,)).fetchall()
            values = [charge(d, e) for d, e in rows if d != exclude]
            amount = parse('0')
            for value in values:
                amount = calculate(amount, exact(value), 'add')
            # Decimal28 aggregation is checked against an independent exact sum.
            if Fraction(amount) != sum(values, Fraction(0)):
                raise ValueError('inexact_spending_total')
            return Fraction(amount)
        def reply(status, exposure=0):
            observed = self.db.execute('SELECT usage FROM observations WHERE dispatch=?', (b.dispatch_id,)).fetchone()
            usage = UsageObservation.model_validate_json(observed[0]) if observed else None
            estimate = self.db.execute('SELECT amount FROM estimates WHERE dispatch=?', (b.dispatch_id,)).fetchone()
            rows = self.db.execute("SELECT dispatch FROM grants WHERE profile_id=? AND state NOT IN ('reserved','no-send')", (b.profile_id,)).fetchall()
            unresolved = sum(1 for (d,) in rows if not (r := self.db.execute('SELECT usage FROM observations WHERE dispatch=?', (d,)).fetchone()) or json.loads(r[0]).get('actual_cost') is None)
            return SpendReply(dispatch_id=b.dispatch_id, status=status, exposure=money(exposure),
                reconciliation_conflict=self.db.execute('SELECT 1 FROM discrepancies WHERE dispatch=?', (b.dispatch_id,)).fetchone() is not None, usage=usage, actual_cost=usage.actual_cost if usage else None,
                catalog_estimate=estimate[0] if estimate else None,
                legacy_requests=self.db.execute('SELECT COUNT(*) FROM grants g LEFT JOIN dispatch_records r ON r.dispatch=g.dispatch WHERE g.profile_id=? AND r.dispatch IS NULL', (b.profile_id,)).fetchone()[0],
                turn_total=canonical(exact(total('turn', b.turn_id))),
                session_total=canonical(exact(total('session', b.session_id))),
                profile_total=canonical(exact(total('profile', b.profile_id))), unresolved_requests=unresolved)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT binding,exposure,state FROM grants WHERE dispatch=?', (b.dispatch_id,)).fetchone()
            if row and row[0] != binding:
                result = reply('conflict')
            elif isinstance(query, SpendHistory):
                params = [b.profile_id]
                where = ''
                if query.lookup_dispatch:
                    where += ' AND g.dispatch=?'
                    params.append(query.lookup_dispatch)
                if query.before_dispatch:
                    cursor = self.db.execute('SELECT rowid FROM grants WHERE dispatch=? AND profile_id=?', (query.before_dispatch,b.profile_id)).fetchone()
                    if not cursor:
                        raise ValueError('invalid_history_cursor')
                    where += ' AND g.rowid<?'
                    params.append(cursor[0])
                rows = self.db.execute('SELECT g.dispatch,g.state,g.exposure,r.binding,r.origin,o.usage FROM grants g JOIN dispatch_records r ON r.dispatch=g.dispatch LEFT JOIN observations o ON o.dispatch=g.dispatch WHERE g.profile_id=?'+where+' ORDER BY g.rowid DESC LIMIT 65', params).fetchall()
                records = [SpendRecord(binding=SpendBinding.model_validate_json(binding_json),state=state,exposure=money(exposure),origin=SpendOrigin.model_validate_json(origin) if origin else None,usage=UsageObservation.model_validate_json(usage) if usage else None) for dispatch,state,exposure,binding_json,origin,usage in rows[:64]]
                result = reply(row[2],row[1]) if row else reply('missing')
                result = result.model_copy(update={'records':records,'history_before':records[-1].binding.dispatch_id if len(rows)>64 else None})
            elif query.action == 'status':
                result = reply(row[2], row[1]) if row else reply('missing')
            elif isinstance(query, SpendObserve):
                if not row:
                    result = reply('missing')
                elif row[2] not in ('uncertain', 'complete'):
                    result = reply('conflict', row[1])
                else:
                    old = self.db.execute('SELECT usage FROM observations WHERE dispatch=?', (b.dispatch_id,)).fetchone()
                    previous = json.loads(old[0]) if old else {}
                    incoming = query.observation.model_dump(exclude_none=True)
                    payload = query.observation.model_dump_json()
                    self.db.execute('INSERT OR IGNORE INTO observation_events VALUES(?,?,?)', (b.dispatch_id, hashlib.sha256(payload.encode()).hexdigest(), payload))
                    # Monotonic facts: missing fields never erase previous observations.
                    # Metadata may fill gaps, but conflicting costs/identities never release funds.
                    if previous.get('actual_cost') is not None and incoming.get('actual_cost') is not None and Fraction(previous['actual_cost']) == Fraction(incoming['actual_cost']):
                        incoming['actual_cost'] = previous['actual_cost']
                    conflict = any(k in previous and previous[k] != v for k, v in incoming.items() if k not in ('source', 'outcome'))
                    if conflict:
                        self.db.execute('INSERT OR IGNORE INTO discrepancies VALUES(?)', (b.dispatch_id,))
                        # A conflicting lower charge cannot free allowance. Retain
                        # higher reported exposure for the same generation and
                        # keep both observations for an explicit later inspection.
                        same_generation = not previous.get('generation_id') or not incoming.get('generation_id') or previous['generation_id'] == incoming['generation_id']
                        cost = incoming.get('actual_cost')
                        if same_generation and cost is not None and (previous.get('actual_cost') is None or Fraction(cost) > Fraction(previous['actual_cost'])):
                            previous['actual_cost'] = cost
                            self.db.execute('UPDATE observations SET usage=? WHERE dispatch=?', (json.dumps(previous), b.dispatch_id))
                        result = reply('conflict', row[1])
                    else:
                        previous.update(incoming)
                        self.db.execute('INSERT INTO observations VALUES(?,?) ON CONFLICT(dispatch) DO UPDATE SET usage=excluded.usage', (b.dispatch_id, json.dumps(previous)))
                        result = reply(row[2], row[1])
            elif isinstance(query, SpendConfigure):
                scopes = [('turn', b.turn_id, units(query.turn_limit)), ('session', b.session_id, units(query.session_limit)), ('profile', b.profile_id, units(query.profile_limit))]
                for kind, identity, allowance in scopes:
                    self.db.execute('INSERT INTO limits VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET allowance=excluded.allowance', (kind+':'+identity, allowance))
                result = reply('configured', row[1] if row else 0)
            elif isinstance(query, SpendReserve):
                if row:
                    origin = self.db.execute('SELECT origin FROM dispatch_records WHERE dispatch=?', (b.dispatch_id,)).fetchone()
                    if (origin[0] if origin else None) != (query.origin.model_dump_json() if query.origin else None):
                        result = reply('conflict', row[1])
                        self.db.execute('COMMIT')
                        return result
                    previous = self.db.execute('SELECT catalog FROM estimates WHERE dispatch=?', (b.dispatch_id,)).fetchone()
                    catalog = query.catalog.model_dump_json() if query.catalog else None
                    if (previous[0] if previous else None) != catalog:
                        result = reply('conflict', row[1])
                        self.db.execute('COMMIT')
                        return result
                amount = units(query.exposure)
                if amount == 0:
                    result = reply('denied')
                elif row and (query.action == 'reserve' or row[2] != 'reserved'):
                    # Exact replay only; a conflicting reservation cannot send again.
                    result = reply(row[2], row[1]) if amount == row[1] else reply('conflict')
                elif query.action == 'amend' and not row:
                    result = reply('missing')
                else:
                    scopes = [('turn', b.turn_id, units(query.turn_limit)),
                              ('session', b.session_id, units(query.session_limit)),
                              ('profile', b.profile_id, units(query.profile_limit))]
                    accepted = True
                    if query.catalog is not None:
                        c = query.catalog
                        estimate = catalog_cost(c)
                        if estimate > Fraction(amount, 1000000):
                            accepted = False
                    for kind, identity, allowance in scopes:
                        scope = kind + ':' + identity
                        existing = self.db.execute('SELECT allowance FROM limits WHERE scope=?', (scope,)).fetchone()
                        # A dispatch cannot silently increase previously configured limits.
                        if existing and allowance != existing[0]:
                            accepted = False
                        if total(kind, identity, b.dispatch_id) + Fraction(amount, 1000000) > Fraction(allowance, 1000000):
                            accepted = False
                    if not accepted:
                        result = reply('denied')
                    else:
                        for kind, identity, allowance in scopes:
                            self.db.execute('INSERT OR IGNORE INTO limits VALUES(?,?)', (kind + ':' + identity, allowance))
                        self.db.execute('INSERT INTO grants VALUES(?,?,?,?,?,?,?) ON CONFLICT(dispatch) DO UPDATE SET exposure=excluded.exposure',
                                        (b.dispatch_id, binding, b.turn_id, b.session_id, b.profile_id, amount, 'reserved'))
                        self.db.execute('INSERT OR IGNORE INTO dispatch_records VALUES(?,?,?)', (b.dispatch_id,b.model_dump_json(),query.origin.model_dump_json() if query.origin else None))
                        if query.catalog is not None:
                            c = query.catalog
                            estimate = catalog_cost(c)
                            catalog = c.model_dump_json()
                            previous = self.db.execute('SELECT catalog FROM estimates WHERE dispatch=?', (b.dispatch_id,)).fetchone()
                            if previous and previous[0] != catalog:
                                raise ValueError('conflicting_catalog_estimate')
                            self.db.execute('INSERT OR IGNORE INTO estimates VALUES(?,?,?)', (b.dispatch_id, catalog, canonical(exact(estimate))))
                        result = reply('reserved', amount)
            elif not row:
                result = reply('missing')
            else:
                state = row[2]
                if query.action == 'uncertain' and state == 'reserved':
                    state = 'uncertain'
                elif query.action == 'complete' and state == 'uncertain':
                    state = 'complete'
                elif query.action == 'no-send' and state == 'reserved':
                    state = 'no-send'
                elif query.action != state:
                    result = reply('conflict', row[1])
                    self.db.execute('COMMIT')
                    return result
                self.db.execute('UPDATE grants SET state=? WHERE dispatch=?', (state, b.dispatch_id))
                result = reply(state, row[1])
            self.db.execute('COMMIT')
            return result
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
