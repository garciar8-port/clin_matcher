/** TypeScript types mirroring the Python data models in src/graph/state.py */

export interface PatientProfile {
  age: number;
  sex: string;
  diagnosis: string;
  stage: string | null;
  prior_therapies: string[];
  biomarkers: string[];
  performance_status: string | null;
  comorbidities: string[];
  location: string | null;
}

export interface Trial {
  nct_id: string;
  title: string;
  phase: string;
  status: string;
  sponsor: string;
  conditions: string[];
  inclusion_criteria: string;
  exclusion_criteria: string;
  locations: { facility: string; city: string; state: string; country: string }[];
  last_updated: string;
}

export interface CriterionResult {
  criterion_text: string;
  met: boolean | null;
  reasoning: string;
}

export interface TrialEvaluation {
  nct_id: string;
  criteria_met: CriterionResult[];
  criteria_failed: CriterionResult[];
  criteria_uncertain: CriterionResult[];
  eligible: "yes" | "no" | "maybe";
  reasoning: string;
}

export interface RankedTrial {
  nct_id: string;
  title: string;
  rank: number;
  score: number;
  match_summary: string;
  evaluation: TrialEvaluation;
}

export interface Clarification {
  source_node: string;
  question: string;
  context: string;
}

export interface ClarificationResponse {
  question_id: string;
  answer: string;
}

export type AppState =
  | { status: "idle" }
  | { status: "running"; currentNode: string; progress: string[] }
  | { status: "clarification"; clarifications: Clarification[]; threadId: string }
  | { status: "complete"; rankings: RankedTrial[]; profile: PatientProfile | null }
  | { status: "error"; message: string };

export interface NodeUpdate {
  patient_profile?: PatientProfile;
  candidate_trials?: Trial[];
  evaluations?: TrialEvaluation[];
  rankings?: RankedTrial[];
  clarifications_needed?: Clarification[];
  error_log?: string[];
  current_node?: string;
}
