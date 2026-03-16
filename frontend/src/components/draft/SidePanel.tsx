import { useEffect, useState } from 'react';
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
  activeTabOverride?: Tab;
  onTabChange?: (tab: Tab) => void;
}

export function SidePanel({ draft, players, recommendations, onPickPlayer, onFilterChange, recsLoading, activeTabOverride, onTabChange }: Props) {
  const [tab, setTab] = useState<Tab>('recs');
  const displayedTab = activeTabOverride ?? tab;

  useEffect(() => {
    if (import.meta.env.DEV && activeTabOverride !== undefined && !onTabChange) {
      console.warn('SidePanel: activeTabOverride is set without onTabChange. Tab clicks will have no effect.');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTabClick = (id: Tab) => {
    if (activeTabOverride !== undefined && onTabChange) {
      onTabChange(id);
    } else {
      setTab(id);
    }
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'recs', label: '🤖 Recs' },
    { id: 'available', label: '📋 Available' },
    { id: 'roster', label: '🏈 Roster' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', borderLeft: '1px solid var(--border)' }}>
      {/* Tab bar — hidden on mobile (bottom nav replaces it) */}
      <div className="sidepanel-tab-bar" style={{ display: 'flex', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => handleTabClick(t.id)}
            style={{
              flex: 1, padding: '10px 4px', borderRadius: 0,
              background: displayedTab === t.id ? 'var(--bg-hover)' : 'transparent',
              color: displayedTab === t.id ? 'var(--text-primary)' : 'var(--text-muted)',
              fontSize: 13, fontWeight: displayedTab === t.id ? 700 : 500,
              borderBottom: displayedTab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {displayedTab === 'recs' && (
          <RecommendationsPanel
            draft={draft}
            recommendations={recommendations}
            onPickPlayer={onPickPlayer}
            refreshing={recsLoading}
          />
        )}
        {displayedTab === 'available' && (
          <AvailablePlayers
            players={players}
            onPickPlayer={onPickPlayer}
            onFilterChange={onFilterChange}
            rosterSlots={draft.league_config.roster_slots}
          />
        )}
        {displayedTab === 'roster' && <RosterPanel draft={draft} />}
      </div>
    </div>
  );
}
