import { useState } from 'react';
import type { PlayerResponse } from '../../types/draft';
import { PlayerCard } from './PlayerCard';

const ALL_POSITIONS = ['QB', 'RB', 'WR', 'TE', 'K', 'DST'] as const;
const FLEX_ELIGIBLE = new Set(['RB', 'WR', 'TE']);

interface Props {
  players: PlayerResponse[];
  onPickPlayer: (playerId: string) => void;
  onFilterChange: (position: string | undefined) => void;
  rosterSlots: Record<string, number>;
}

export function AvailablePlayers({ players, onPickPlayer, onFilterChange, rosterSlots }: Props) {
  const [activePos, setActivePos] = useState('All');
  const [search, setSearch] = useState('');

  // Only show tabs for positions this league actually supports
  const validPositions = ALL_POSITIONS.filter(
    (pos) => (rosterSlots[pos] ?? 0) > 0 || FLEX_ELIGIBLE.has(pos),
  );
  const tabs = ['All', ...validPositions];

  const filtered = players.filter((p) =>
    p.name.toLowerCase().includes(search.toLowerCase()),
  );

  const handlePosChange = (pos: string) => {
    setActivePos(pos);
    onFilterChange(pos === 'All' ? undefined : pos);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Position tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        {tabs.map((pos) => (
          <button
            key={pos}
            onClick={() => handlePosChange(pos)}
            style={{
              flex: 1, padding: '8px 4px', borderRadius: 0, fontSize: 12, fontWeight: 600,
              background: activePos === pos ? 'var(--accent)' : 'transparent',
              color: activePos === pos ? 'white' : 'var(--text-secondary)',
              borderRight: '1px solid var(--border)',
            }}
          >
            {pos}
          </button>
        ))}
      </div>

      {/* Search */}
      <div style={{ padding: '8px 12px', flexShrink: 0 }}>
        <input
          type="text"
          placeholder="Search player…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: '100%' }}
        />
      </div>

      {/* Player list */}
      <div style={{ overflowY: 'auto', flex: 1 }}>
        {filtered.length === 0 ? (
          <p style={{ padding: 16, color: 'var(--text-muted)', fontSize: 13 }}>No players found.</p>
        ) : (
          filtered.map((p, i) => (
            <PlayerCard key={p.player_id} player={p} rank={i + 1} onPick={onPickPlayer} />
          ))
        )}
      </div>
    </div>
  );
}
