import { it,expect } from 'vitest';
import { assistantQuestion } from '../../desktop/renderer/assistant-question';
import type { InterviewQuestion } from '../../contracts/interview';
const question={query:{context:{data_store_id:'store',civilization_id:'civilization',branch_id:'original',revision_id:'original-revision'},scope_id:'scope'},definition:{id:'question',original_text:'How should the declared service be organized?',source_refs:['source'],assumption_refs:['assumption']},clarification:'Clarify responsibility',dependencies:['Unresolved capacity'],current_commitment:'COMMITMENT-CANARY',options:[{rationale:'PRIVATE-DRAFT-CANARY'}],private_rationale:'PRIVATE-RATIONALE-CANARY'} as unknown as InterviewQuestion;
it('explicit interview draft includes original public context and unresolved evidence but no private or draft copies',()=>{
 const text=assistantQuestion(question)!;
 expect(text).toContain('original-revision');expect(text).toContain('How should the declared service be organized?');expect(text).toContain('Unresolved capacity');expect(text).toContain('source');
 expect(text).not.toContain('COMMITMENT-CANARY');expect(text).not.toContain('PRIVATE-DRAFT-CANARY');expect(text).not.toContain('PRIVATE-RATIONALE-CANARY');
});
it('oversized public questions cannot silently truncate context or replace the editable draft',()=>{
 expect(assistantQuestion({...question,clarification:'x'.repeat(8192)})).toBeUndefined();
});
