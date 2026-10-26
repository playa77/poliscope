import tool from '../../contracts/grounding-tools.json';
/** Main-retained Python grant; tools cannot supply context, paths or operations. */
import type { GroundingManifest, GroundingSelection, GroundingResult } from '../../contracts/grounding';
import type { GenerationTool } from '../../contracts/generation';
export interface GroundedSession {
  manifest: GroundingManifest;
  execute: (argumentsJSON:string, requestId:string)=>Promise<GroundingResult>;
}
export type Ground = (selection:GroundingSelection)=>Promise<GroundedSession>;
export const contextTool:GenerationTool={name:tool.name,description:tool.description,parameters_json:JSON.stringify(tool.parameters)};
