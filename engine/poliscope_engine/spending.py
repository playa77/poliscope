"""WP-048-reservation: exact, durable, atomic multi-scope exposure ledger.

This private database is outside civilization history. Completion/cancel/crash
never releases exposure. Full actual-cost reconciliation belongs to WP-048.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
from fractions import Fraction
from poliscope_engine.numeric import parse, canonical, exact
from poliscope_engine.contracts.spending import SpendReserve, SpendReply


def units(value: str) -> int:
    amount = Fraction(parse(value)) * 1000000
    if amount.denominator != 1 or amount < 0:
        raise ValueError('invalid_exposure')
    return amount.numerator


def money(value: int) -> str:
    return canonical(exact(Fraction(value, 1000000)))


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
        if self.db.execute('SELECT version FROM spending_version').fetchall() != [(1,)]:
            self.db.close()
            raise ValueError('unsupported_spending_version')
        path.chmod(0o600)

    def close(self):
        self.db.close()

    def request(self, query):
        b = query.binding
        binding = hashlib.sha256(b.model_dump_json().encode()).hexdigest()
        def reply(status, exposure=0):
            return SpendReply(dispatch_id=b.dispatch_id, status=status, exposure=money(exposure))
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT binding,exposure,state FROM grants WHERE dispatch=?', (b.dispatch_id,)).fetchone()
            if row and row[0] != binding:
                result = reply('conflict')
            elif query.action == 'status':
                result = reply(row[2], row[1]) if row else reply('missing')
            elif isinstance(query, SpendReserve):
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
                    for kind, identity, allowance in scopes:
                        scope = kind + ':' + identity
                        existing = self.db.execute('SELECT allowance FROM limits WHERE scope=?', (scope,)).fetchone()
                        # A dispatch cannot silently increase previously configured limits.
                        if existing and allowance != existing[0]:
                            accepted = False
                        total = self.db.execute(f"SELECT COALESCE(SUM(exposure),0) FROM grants WHERE {kind}_id=? AND state!='no-send' AND dispatch!=?", (identity, b.dispatch_id)).fetchone()[0]
                        if total + amount > allowance:
                            accepted = False
                    if not accepted:
                        result = reply('denied')
                    else:
                        for kind, identity, allowance in scopes:
                            self.db.execute('INSERT OR IGNORE INTO limits VALUES(?,?)', (kind + ':' + identity, allowance))
                        self.db.execute('INSERT INTO grants VALUES(?,?,?,?,?,?,?) ON CONFLICT(dispatch) DO UPDATE SET exposure=excluded.exposure',
                                        (b.dispatch_id, binding, b.turn_id, b.session_id, b.profile_id, amount, 'reserved'))
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
