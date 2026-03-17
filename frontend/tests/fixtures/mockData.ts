import type {
  DraftSummary,
  PickResponse,
  PlayerResponse,
  RecommendationResponse,
} from '../../src/types/draft';

export const mockPlayer: PlayerResponse = {
  player_id: 'player-1',
  name: 'Patrick Mahomes',
  position: 'QB',
  nfl_team: 'KC',
  bye_week: 10,
  projected_points: 380.5,
  baseline_vor: 45.2,
  overall_rank: 5,
};

export const mockPlayerNoBye: PlayerResponse = {
  player_id: 'player-2',
  name: 'Justin Jefferson',
  position: 'WR',
  nfl_team: 'MIN',
  bye_week: null,
  projected_points: 290.0,
  baseline_vor: 38.1,
  overall_rank: 8,
};

export const mockPick: PickResponse = {
  pick_number: 1,
  round: 1,
  team_id: 0,
  player_id: 'player-3',
  player_name: 'Christian McCaffrey',
  position: 'RB',
  nfl_team: 'SF',
  slot: 'RB1',
  timestamp: '2025-01-01T00:01:00Z',
  reach_delta: null,
  reach_label: '',
};

export const mockPickWithReach: PickResponse = {
  ...mockPick,
  pick_number: 5,
  player_name: 'Reach Pick',
  reach_delta: -12,
  reach_label: 'Reach',
};

export const mockPickWithSteal: PickResponse = {
  ...mockPick,
  pick_number: 6,
  player_name: 'Steal Pick',
  reach_delta: 18,
  reach_label: 'STEAL',
};

export const mockRec: RecommendationResponse = {
  player_id: 'player-4',
  player_name: 'Saquon Barkley',
  position: 'RB',
  nfl_team: 'PHI',
  projected_points: 310.5,
  dynamic_vor: 88.0,
  base_vor: 80.0,
  rank: 1,
  reasoning: 'Elite RB1 with massive VOR advantage over RB2',
  tier: 1,
  is_tier_boundary: false,
  mc_expected_score: 330.0,
  mc_delta: 12.5,
};

export const mockRecTierBoundary: RecommendationResponse = {
  ...mockRec,
  player_id: 'player-5',
  player_name: 'Chase Brown',
  rank: 2,
  mc_delta: 0,
  is_tier_boundary: true,
};

const DEFAULT_ROSTER_SLOTS: Record<string, number> = {
  QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, DST: 1, K: 1, BENCH: 6,
};

export function makeDraftSummary(overrides: Partial<DraftSummary> = {}): DraftSummary {
  const leagueSize = 12;
  const totalRounds = Object.values(DEFAULT_ROSTER_SLOTS).reduce((a, b) => a + b, 0);
  return {
    draft_id: 'draft-test-123',
    league_config: {
      league_id: 'league-1',
      league_size: leagueSize,
      scoring_format: 'half_ppr',
      draft_type: 'snake',
      draft_mode: 'simulation',
      data_year: 2025,
      roster_slots: DEFAULT_ROSTER_SLOTS,
      pick_clock_seconds: null,
    },
    draft_start_time: '2025-01-01T00:00:00Z',
    current_pick: 1,
    current_round: 1,
    current_team_id: 0,
    is_complete: false,
    completed_at: null,
    draft_order: Array.from({ length: totalRounds }, (_, round) =>
      round % 2 === 0
        ? Array.from({ length: leagueSize }, (_, i) => i)
        : Array.from({ length: leagueSize }, (_, i) => leagueSize - 1 - i),
    ),
    pick_trades: [],
    teams: Array.from({ length: leagueSize }, (_, i) => ({
      team_id: i,
      team_name: `Team ${i + 1}`,
      is_human: i === 0,
      roster: {},
      picks: [],
    })),
    all_picks: [],
    ...overrides,
  };
}
