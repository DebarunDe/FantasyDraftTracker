import type { DraftSummary, RecommendationResponse } from '../../types/draft';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { RecCard } from './PlayerCard';

interface Props {
  draft: DraftSummary;
  recommendations: RecommendationResponse[];
  onPickPlayer: (playerId: string) => void;
  refreshing: boolean;
}

export function RecommendationsPanel({ draft, recommendations, onPickPlayer, refreshing }: Props) {
  const currentTeam = draft.teams[draft.current_team_id];
  const isHumanTurn = currentTeam?.is_human ?? false;

  if (draft.is_complete) {
    return <p style={{ padding: 16, color: 'var(--text-muted)' }}>Draft is complete.</p>;
  }

  if (!isHumanTurn && draft.league_config.draft_mode === 'simulation') {
    return (
      <p style={{ padding: 16, color: 'var(--text-muted)', fontSize: 13 }}>
        Recommendations shown on your turn.
      </p>
    );
  }

  return (
    <div>
      <div style={{ padding: '10px 12px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>🤖 Co-Pilot Picks</span>
        {refreshing && <LoadingSpinner />}
      </div>
      {recommendations.length === 0 && !refreshing ? (
        <p style={{ padding: 16, color: 'var(--text-muted)', fontSize: 13 }}>Loading recommendations…</p>
      ) : (
        recommendations.map((rec) => (
          <RecCard key={rec.player_id} rec={rec} onPick={onPickPlayer} />
        ))
      )}
    </div>
  );
}
