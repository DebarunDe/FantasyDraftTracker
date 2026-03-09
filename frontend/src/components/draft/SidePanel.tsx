import { useState } from 'react';
import type { DraftSummary, PlayerResponse, RecommendationResponse } from '../../types/draft';
import { AvailablePlayers } from './AvailablePlayers';
import { RecommendationsPanel } from './RecommendationsPanel';
import { RosterPanel } from './RosterPanel';

type Tab = 'recs' | 'available' | 'roster';

interface Props {
  draft: DraftSummary;
  players: PlayerResponse[];
  recommendations: RecommendationResponse[];
  onPickPlayer: (playerId: string) => void;
  onFilterChange: (position: string | undefined) => void;
  recsLoading: boolean;
}

export function SidePanel({ draft, players, recommendations, onPickPlayer, onFilterChange, recsLoading }: Props) {
  const [tab, setTab] = useState<Tab>('recs');

  const tabs: { id: Tab; label: string }[] = [
    { id: 'recs', label: '🤖 Recs' },
    { id: 'available', label: '📋 Available' },
    { id: 'roster', label: '🏈 Roster' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', borderLeft: '1px solid var(--border)' }}>
      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              flex: 1, padding: '10px 4px', borderRadius: 0,
              background: tab === t.id ? 'var(--bg-hover)' : 'transparent',
              color: tab === t.id ? 'var(--text-primary)' : 'var(--text-muted)',
              fontSize: 13, fontWeight: tab === t.id ? 700 : 500,
              borderBottom: tab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {tab === 'recs' && (
          <RecommendationsPanel
            draft={draft}
            recommendations={recommendations}
            onPickPlayer={onPickPlayer}
            refreshing={recsLoading}
          />
        )}
        {tab === 'available' && (
          <AvailablePlayers
            players={players}
            onPickPlayer={onPickPlayer}
            onFilterChange={onFilterChange}
            rosterSlots={draft.league_config.roster_slots}
          />
        )}
        {tab === 'roster' && <RosterPanel draft={draft} />}
      </div>
    </div>
  );
}
