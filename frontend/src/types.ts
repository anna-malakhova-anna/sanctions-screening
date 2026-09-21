export type RowStatus = "auto_clear" | "review" | "auto_escalate" | "cleared" | "escalated";
export type Matcher = "exact" | "jaro_winkler";
export type AliasStrength = "strong" | "weak";

export interface MatchCandidate {
  query_name: string;
  source_id: string;
  entity_canonical_name: string;
  matched_name: string;
  is_alias_match: boolean;
  alias_strength: AliasStrength | null;
  matcher: Matcher;
  score: number;
}

export interface RowOut {
  row_id: string;
  query_name: string;
  best_score: number;
  status: RowStatus;
  top_candidate: MatchCandidate | null;
  candidates: MatchCandidate[];
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
}

export interface BatchSummary {
  batch_source: string;
  list_name: string;
  list_version: string;
  watchlist_size: number;
  total_rows: number;
  clear_threshold: number;
  escalate_threshold: number;
}

export interface VolumeBreakdown {
  auto_clear: number;
  review: number;
  auto_escalate: number;
  cleared: number;
  escalated: number;
  total: number;
}

export interface GroundTruthMetrics {
  labelled_set_size: number;
  recall_not_missed: number;
  auto_escalate_precision: number | null;
  negative_auto_escalate_rate: number;
  negative_review_rate: number;
}

export interface MetricsOut {
  clear_threshold: number;
  escalate_threshold: number;
  ground_truth: GroundTruthMetrics;
  batch_volume: VolumeBreakdown;
}

export interface StateOut {
  summary: BatchSummary;
  rows: RowOut[];
  metrics: MetricsOut;
}
