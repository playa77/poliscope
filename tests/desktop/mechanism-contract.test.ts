import { describe, expect, it } from 'vitest';
import { mechanismFixtures } from '../../contracts/mechanism-fixtures';
import fixtureData from '../../contracts/mechanism-fixtures.json';
import type { MechanismDefinition, QuantityType } from '../../contracts/mechanism';

// Compiled along with the production consumers by root typecheck.
const declarations: MechanismDefinition[] = mechanismFixtures;

describe('mechanism contract version 1', () => {
  it('preserves shared Python fixture data in generated TypeScript', () => {
    expect(declarations).toEqual(fixtureData);
    expect(declarations.map(d => d.domain)).toEqual(['provisioning', 'economy']);
    expect(declarations[0].outputs[0].value_type).toEqual(declarations[1].inputs[0].value_type);
    expect(declarations.every(d => d.write_state_refs.length === 0)).toBe(true);
  });

  it('keeps typed allocation and independent evidence metadata', () => {
    const consumer = declarations[1];
    const claim = consumer.claims[0];
    const output = consumer.outputs.find(p => p.id === claim.dependent_output_refs[0])!;
    expect(output.input_refs).toContain(claim.allocation_input_ref);
    expect(consumer.evidence).toBe('hypothetical');
    expect(consumer.support.static?.implementation.version).toBe('v1');
  });
});

// Invalid declarations must remain compile errors in generated consumer types.
// @ts-expect-error numeric quantities cannot omit unit/time/denominator identity
const incompleteQuantity: QuantityType = { kind: 'quantity' };
// @ts-expect-error Python source is never an implementation reference
const executionPayload: NonNullable<MechanismDefinition['support']['static']> = { kind: 'trusted_python', code: 'print(1)' };
void incompleteQuantity;
void executionPayload;
