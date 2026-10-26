import type { InterviewQuestion } from '../../contracts/interview';
/** Only authored public wording/references. No current commitment, draft or rationale. */
export function assistantQuestion(question:InterviewQuestion):string|undefined {
  const text='Clarify this authored interview question, adapt your follow-up to its unresolved dependencies, and explain alternatives without choosing for me. Preserve source/coverage limits. This question was read at the context below; review the current request context separately.\n'+JSON.stringify({context:question.query.context,scope_id:question.query.scope_id,question_id:question.definition.id,wording:question.definition.original_text,clarification:question.clarification,dependencies:question.dependencies,source_refs:question.definition.source_refs,assumption_refs:question.definition.assumption_refs});
  return text.length<=8192?text:undefined;
}
