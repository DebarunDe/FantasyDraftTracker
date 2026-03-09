import type { PickResponse } from '../../types/draft';
import { PositionBadge } from '../common/PositionBadge';

interface Props {
  pick: PickResponse;
  isNew: boolean;
  /** Set when this pick slot was traded to another team (show recipient label). */
  tradedTo?: string;
}

const POS_BG: Record<string, string> = {
  QB: 'var(--bg-qb)', RB: 'var(--bg-rb)', WR: 'var(--bg-wr)',
  TE: 'var(--bg-te)', K: 'var(--bg-k)', DST: 'var(--bg-dst)',
};

export function PlayerTile({ pick, isNew, tradedTo }: Props) {
  const bg = POS_BG[pick.position] ?? 'var(--bg-secondary)';

  return (
    <div
      className={isNew ? 'tile-new' : undefined}
      style={{
        background: bg,
        border: '1px solid var(--border)',
        borderRadius: 6,
        padding: '6px 8px',
        height: 66,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <PositionBadge position={pick.position} />
        <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>#{pick.pick_number}</span>
      </div>
      <div>
        <div style={{ fontSize: 12, fontWeight: 700, lineHeight: 1.2, marginTop: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {pick.player_name}
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
          {pick.nfl_team}
          {pick.reach_label && (
            <span
              style={{
                marginLeft: 4,
                color: pick.reach_label === 'STEAL' || pick.reach_label === 'Value' ? 'var(--success)' : 'var(--danger)',
                fontWeight: 600,
              }}
            >
              {pick.reach_label}
            </span>
          )}
        </div>
        {tradedTo && (
          <div style={{ fontSize: 9, color: 'var(--warning)', marginTop: 2, fontWeight: 600 }}>
            → {tradedTo}
          </div>
        )}
      </div>
    </div>
  );
}
