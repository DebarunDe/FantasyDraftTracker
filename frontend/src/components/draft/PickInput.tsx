import { useEffect, useRef, useState } from 'react';
import { getPlayers } from '../../api/picks';
import type { DraftSummary, PlayerResponse } from '../../types/draft';

interface Props {
  draft: DraftSummary;
  onPickPlayer: (playerId: string) => void;
}

export function PickInput({ draft, onPickPlayer }: Props) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<PlayerResponse[]>([]);
  const [confirming, setConfirming] = useState<PlayerResponse | null>(null);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentTeam = draft.teams[draft.current_team_id];
  const isHumanTurn = currentTeam?.is_human ?? false;
  const isManual = draft.league_config.draft_mode === 'manual_tracker';

  // Debounced search: call the API with a name filter
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);

    if (query.trim().length < 2) {
      setResults([]);
      setHighlightedIndex(-1);
      return;
    }

    debounceRef.current = setTimeout(() => {
      getPlayers(draft.draft_id, undefined, 8, 0, query.trim())
        .then((r) => { setResults(r); setHighlightedIndex(-1); })
        .catch(() => {});
    }, 200);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query, draft.draft_id]);

  // Reset search state when the pick slot changes
  useEffect(() => {
    setQuery('');
    setResults([]);
    setConfirming(null);
    setHighlightedIndex(-1);
  }, [draft.current_pick]);

  // Scroll highlighted item into view
  useEffect(() => {
    if (highlightedIndex < 0 || !dropdownRef.current) return;
    const item = dropdownRef.current.children[highlightedIndex] as HTMLElement | undefined;
    item?.scrollIntoView({ block: 'nearest' });
  }, [highlightedIndex]);

  if (!isHumanTurn && !isManual) return null;
  if (draft.is_complete) return null;

  const selectPlayer = (p: PlayerResponse) => {
    setConfirming(p);
    setQuery('');
    setResults([]);
    setHighlightedIndex(-1);
  };

  const handleConfirm = () => {
    if (!confirming) return;
    onPickPlayer(confirming.player_id);
    setConfirming(null);
    setQuery('');
    setResults([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (results.length === 0) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightedIndex((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const target = highlightedIndex >= 0 ? results[highlightedIndex] : results[0];
      if (target) selectPlayer(target);
    } else if (e.key === 'Escape') {
      setResults([]);
      setHighlightedIndex(-1);
    }
  };

  return (
    <div className="pick-input-bar" style={{ padding: '10px 12px', borderTop: '1px solid var(--border)', background: 'var(--bg-secondary)', flexShrink: 0 }}>
      <div style={{ marginBottom: 4, fontSize: 12, color: 'var(--text-muted)', fontWeight: 600 }}>
        {isManual ? `Enter pick for ${currentTeam?.team_name}` : `Your pick — ${currentTeam?.team_name}`}
      </div>

      {confirming ? (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ flex: 1, fontSize: 14 }}>
            Draft <strong>{confirming.name}</strong> ({confirming.position} - {confirming.nfl_team})?
          </span>
          <button className="primary" onClick={handleConfirm} autoFocus>✓ Confirm</button>
          <button className="secondary" onClick={() => setConfirming(null)}>✕</button>
        </div>
      ) : (
        <div style={{ position: 'relative' }}>
          <input
            type="text"
            placeholder="Search player name…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            autoFocus={isHumanTurn}
          />
          {results.length > 0 && (
            <div
              ref={dropdownRef}
              className="pick-input-dropdown"
              style={{
                position: 'absolute', bottom: '100%', left: 0, right: 0,
                background: 'var(--bg-card)', border: '1px solid var(--border)',
                borderRadius: 6, overflow: 'hidden', zIndex: 50,
                maxHeight: 240, overflowY: 'auto',
              }}
            >
              {results.map((p, idx) => (
                <div
                  key={p.player_id}
                  style={{
                    padding: '8px 12px', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: 8,
                    borderBottom: '1px solid var(--border)',
                    background: idx === highlightedIndex ? 'var(--bg-hover)' : 'transparent',
                  }}
                  onMouseEnter={() => setHighlightedIndex(idx)}
                  onMouseLeave={() => setHighlightedIndex(-1)}
                  onClick={() => selectPlayer(p)}
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
