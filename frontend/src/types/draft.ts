// TypeScript interfaces mirroring the Pydantic schemas from src/web/schemas.py

export type ScoringFormat = 'standard' | 'half_ppr' | 'full_ppr';
export type DraftMode = 'simulation' | 'manual_tracker';
export type Position = 'QB' | 'RB' | 'WR' | 'TE' | 'K' | 'DST' | 'FLEX' | 'BENCH';

export interface PickTradeInput {
  from_team_id: number;
  round: number;
  to_team_id: number;
}

export interface CreateDraftRequest {
  draft_mode: DraftMode;
  league_size: number;
  scoring_format: ScoringFormat;
  roster_slots: Record<string, number>;
  team_names: string[];
  human_team_id: number;
  data_year: number;
  pick_trades: PickTradeInput[];
}

export interface LeagueConfig {
  league_id: string;
  league_size: number;
  scoring_format: ScoringFormat;
  draft_type: string;
  draft_mode: DraftMode;
  data_year: number;
  roster_slots: Record<string, number>;
}

export interface PickResponse {
  pick_number: number;
  round: number;
  team_id: number;
  player_id: string;
  player_name: string;
  position: string;
  nfl_team: string;
  slot: string | null;
  timestamp: string;
  reach_delta: number | null;
  reach_label: string;
}

export interface TeamResponse {
  team_id: number;
  team_name: string;
  is_human: boolean;
  roster: Record<string, string[]>;
  picks: string[];
}

export interface DraftSummary {
  draft_id: string;
  league_config: LeagueConfig;
  draft_start_time: string;
  current_pick: number;
  current_round: number;
  current_team_id: number;
  is_complete: boolean;
  completed_at: string | null;
  draft_order: number[][];
  pick_trades: PickTradeInput[];
  teams: TeamResponse[];
  all_picks: PickResponse[];
}

export interface PlayerResponse {
  player_id: string;
  name: string;
  position: string;
  nfl_team: string;
  bye_week: number | null;
  projected_points: number;
  baseline_vor: number;
  overall_rank: number | null;
}

export interface RecommendationResponse {
  player_id: string;
  player_name: string;
  position: string;
  nfl_team: string;
  projected_points: number;
  dynamic_vor: number;
  base_vor: number;
  rank: number;
  reasoning: string;
  tier: number;
  is_tier_boundary: boolean;
  mc_expected_score: number;
  mc_delta: number;
}

export interface RosterPlayer {
  player_id: string;
  name: string;
  position: string;
  nfl_team: string;
  bye_week: number | null;
  projected_points: number;
  baseline_vor: number;
  overall_rank: number | null;
}

export interface TeamRosterData {
  team_id: number;
  team_name: string;
  is_human: boolean;
  roster: Record<string, RosterPlayer[]>;
}

export interface SavedDraftMeta {
  draft_id: string;
  start_time: string;
  is_complete: boolean;
  current_round: number;
  current_pick: number;
  league_size: number;
  scoring_format: ScoringFormat;
}

// WebSocket event types
export interface WsPickMadeEvent {
  type: 'pick_made';
  pick: PickResponse;
  draft_state: {
    current_pick: number;
    current_round: number;
    current_team_id: number;
    is_complete: boolean;
    completed_at: string | null;
    all_picks: PickResponse[];
  };
}

export interface WsComputerThinkingEvent {
  type: 'computer_thinking';
  team_id: number;
  team_name: string;
  pick_number: number;
}

export interface WsDraftCompleteEvent {
  type: 'draft_complete';
  summary: DraftSummary;
}

export interface WsErrorEvent {
  type: 'error';
  message: string;
}

export interface WsPingEvent {
  type: 'ping';
}

export type WsEvent =
  | WsPickMadeEvent
  | WsComputerThinkingEvent
  | WsDraftCompleteEvent
  | WsErrorEvent
  | WsPingEvent;
