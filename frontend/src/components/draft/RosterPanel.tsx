import { useEffect, useState } from 'react';
import type { DraftSummary } from '../../types/draft';
import { getRoster } from '../../api/picks';
import { PositionBadge } from '../common/PositionBadge';
import { LoadingSpinner } from '../common/LoadingSpinner';

interface Props {
  draft: DraftSummary;
}

export function RosterPanel({ draft }: Props) {
  const [teamId, setTeamId] = useState(draft.current_team_id);
  const [roster, setRoster] = useState<Record<string, { name: string; position: string; projected_points: number }[]>>({});
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getRoster(draft.draft_id, teamId)
      .then((data) => setRoster(data.roster))
      .finally(() => setLoading(false));
  }, [draft.draft_id, teamId, draft.current_pick]);

  const slotOrder = Object.keys(draft.league_config.roster_slots);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '8px 12px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        <select value={teamId} onChange={(e) => setTeamId(Number(e.target.value))} style={{ width: '100%' }}>
          {draft.teams.map((t) => (
            <option key={t.team_id} value={t.team_id}>
              {t.team_name}{t.is_human ? ' (You)' : ''}
            </option>
          ))}
        </select>
      </div>
      <div style={{ overflowY: 'auto', flex: 1, padding: '8px 0' }}>
        {loading ? (
          <div style={{ padding: 16 }}><LoadingSpinner label="Loading roster…" /></div>
        ) : (
          slotOrder.map((slot) => {
            const players = roster[slot] ?? [];
            const slots = draft.league_config.roster_slots[slot] ?? 1;
            return (
              <div key={slot} style={{ padding: '4px 12px' }}>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, fontWeight: 600 }}>{slot}</div>
                {Array.from({ length: slots }).map((_, i) => {
                  const p = players[i];
                  return (
                    <div
                      key={i}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 8,
                        padding: '4px 0', borderBottom: '1px solid var(--border)',
                        minHeight: 28,
                      }}
                    >
                      {p ? (
                        <>
                          <PositionBadge position={p.position} />
                          <span style={{ fontSize: 13, fontWeight: 600 }}>{p.name}</span>
                          <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--text-muted)' }}>
                            {p.projected_points.toFixed(1)} pts
                          </span>
                        </>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>— empty —</span>
                      )}
                    </div>
                  );
                })}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
