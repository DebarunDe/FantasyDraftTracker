import type { PlayerResponse, RecommendationResponse } from '../../types/draft';
import { PositionBadge } from '../common/PositionBadge';

interface PlayerCardProps {
  player: PlayerResponse;
  rank?: number;
  onPick?: (playerId: string) => void;
}

export function PlayerCard({ player, rank, onPick }: PlayerCardProps) {
  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px',
        borderBottom: '1px solid var(--border)', cursor: onPick ? 'pointer' : 'default',
        transition: 'background 0.1s',
      }}
      onMouseEnter={(e) => { if (onPick) (e.currentTarget as HTMLDivElement).style.background = 'var(--bg-hover)'; }}
      onMouseLeave={(e) => { if (onPick) (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
      onClick={() => onPick?.(player.player_id)}
    >
      {rank !== undefined && (
        <span style={{ width: 24, color: 'var(--text-muted)', fontSize: 12, flexShrink: 0 }}>{rank}</span>
      )}
      <PositionBadge position={player.position} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {player.name}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
          {player.nfl_team}{player.bye_week != null ? ` · Bye ${player.bye_week}` : ''}
        </div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 13 }}>{player.projected_points.toFixed(1)}</div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>pts</div>
      </div>
    </div>
  );
}

interface RecCardProps {
  rec: RecommendationResponse;
  onPick?: (playerId: string) => void;
}

export function RecCard({ rec, onPick }: RecCardProps) {
  return (
    <div
      style={{
        display: 'flex', flexDirection: 'column', gap: 4, padding: '10px 12px',
        borderBottom: '1px solid var(--border)', cursor: onPick ? 'pointer' : 'default',
        transition: 'background 0.1s',
      }}
      onMouseEnter={(e) => { if (onPick) (e.currentTarget as HTMLDivElement).style.background = 'var(--bg-hover)'; }}
      onMouseLeave={(e) => { if (onPick) (e.currentTarget as HTMLDivElement).style.background = 'transparent'; }}
      onClick={() => onPick?.(rec.player_id)}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ width: 20, color: 'var(--text-muted)', fontSize: 12 }}>{rec.rank}</span>
        <PositionBadge position={rec.position} />
        <span style={{ fontWeight: 700, fontSize: 13 }}>{rec.player_name}</span>
        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{rec.nfl_team}</span>
        {rec.is_tier_boundary && (
          <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--warning)', fontWeight: 600 }}>TIER EDGE</span>
        )}
        {rec.mc_delta > 0 && (
          <span style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--success)', fontWeight: 600 }}>
            MC +{rec.mc_delta.toFixed(1)}
          </span>
        )}
      </div>
      <div style={{ paddingLeft: 28, fontSize: 12, color: 'var(--text-secondary)' }}>{rec.reasoning}</div>
    </div>
  );
}
