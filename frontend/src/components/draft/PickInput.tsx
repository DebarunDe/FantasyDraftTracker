import { useState } from 'react';
import type { DraftSummary, PlayerResponse } from '../../types/draft';

interface Props {
  draft: DraftSummary;
  players: PlayerResponse[];
  onPickPlayer: (playerId: string) => void;
}

export function PickInput({ draft, players, onPickPlayer }: Props) {
  const [query, setQuery] = useState('');
  const [confirming, setConfirming] = useState<PlayerResponse | null>(null);

  const currentTeam = draft.teams[draft.current_team_id];
  const isHumanTurn = currentTeam?.is_human ?? false;
  const isManual = draft.league_config.draft_mode === 'manual_tracker';

  if (!isHumanTurn && !isManual) return null;
  if (draft.is_complete) return null;

  const results = query.trim().length >= 2
    ? players.filter((p) => p.name.toLowerCase().includes(query.toLowerCase())).slice(0, 8)
    : [];

  const handleConfirm = () => {
    if (!confirming) return;
    onPickPlayer(confirming.player_id);
    setConfirming(null);
    setQuery('');
  };

  return (
    <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border)', background: 'var(--bg-secondary)', flexShrink: 0 }}>
      <div style={{ marginBottom: 4, fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>
        {isManual ? `Enter pick for ${currentTeam?.team_name}` : `Your pick — ${currentTeam?.team_name}`}
      </div>

      {confirming ? (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ flex: 1, fontSize: 14 }}>
            Draft <strong>{confirming.name}</strong> ({confirming.position} - {confirming.nfl_team})?
          </span>
          <button className="primary" onClick={handleConfirm}>✓ Confirm</button>
          <button className="secondary" onClick={() => setConfirming(null)}>✕</button>
        </div>
      ) : (
        <div style={{ position: 'relative' }}>
          <input
            type="text"
            placeholder="Search player name…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus={isHumanTurn}
          />
          {results.length > 0 && (
            <div
              style={{
                position: 'absolute', bottom: '100%', left: 0, right: 0,
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 6, overflow: 'hidden', zIndex: 50,
                maxHeight: 240, overflowY: 'auto',
              }}
            >
              {results.map((p) => (
                <div
                  key={p.player_id}
                  style={{
                    padding: '8px 12px', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 8,
                    borderBottom: '1px solid var(--border)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-hover)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  onClick={() => { setConfirming(p); setQuery(''); }}
                >
                  <span className={`pos-badge ${p.position}`}>{p.position}</span>
                  <span style={{ fontWeight: 600 }}>{p.name}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>{p.nfl_team}</span>
                  <span style={{ marginLeft: 'auto', fontSize: 12 }}>{p.projected_points.toFixed(1)} pts</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
