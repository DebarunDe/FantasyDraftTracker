import type { SavedDraftMeta } from '../../types/draft';

interface Props {
  meta: SavedDraftMeta;
  onResume: (id: string) => void;
  onDelete: (id: string) => void;
}

const SCORING_LABELS: Record<string, string> = {
  standard: 'Standard',
  half_ppr: 'Half PPR',
  full_ppr: 'Full PPR',
};

export function DraftCard({ meta, onResume, onDelete }: Props) {
  const date = new Date(meta.start_time).toLocaleDateString(undefined, {
    month: 'short', day: 'numeric', year: 'numeric',
  });

  return (
    <div
      className="card"
      style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16 }}
    >
      <div>
        <div style={{ fontWeight: 600, marginBottom: 4 }}>
          {meta.league_size}-Team · {SCORING_LABELS[meta.scoring_format] ?? meta.scoring_format}
          {meta.is_complete && (
            <span style={{ marginLeft: 8, color: 'var(--success)', fontSize: 12 }}>✓ Complete</span>
          )}
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>
          {date} · Round {meta.current_round} · Pick {meta.current_pick}
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: 11, marginTop: 2 }}>
          {meta.draft_id.slice(0, 8)}…
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button className="primary" onClick={() => onResume(meta.draft_id)}>
          {meta.is_complete ? 'View' : 'Resume'}
        </button>
        <button className="danger" onClick={() => onDelete(meta.draft_id)}>Delete</button>
      </div>
    </div>
  );
}
