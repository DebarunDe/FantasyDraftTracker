import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { exportDraft, simulateDraft } from '../../api/drafts';
import { useDraft } from '../../hooks/useDraft';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ComputerPickOverlay } from './ComputerPickOverlay';
import { DraftGrid } from './DraftGrid';
import { DraftHeader } from './DraftHeader';
import { MobileDraftBoard } from './MobileDraftBoard';
import { PickInput } from './PickInput';
import { PostDraftScreen } from './PostDraftScreen';
import { SidePanel } from './SidePanel';

type MobileTab = 'board' | 'recs' | 'available' | 'roster';

export function DraftBoard() {
  const { draftId } = useParams<{ draftId: string }>();
  const navigate = useNavigate();
  const [simming, setSimming] = useState(false);
  const [mobilePanelTab, setMobilePanelTab] = useState<MobileTab>('recs');
  const [mobileBoardView, setMobileBoardView] = useState<'list' | 'grid'>('list');
  const {
    draft,
    players,
    recommendations,
    computerThinking,
    newlyAddedPickNumber,
    wsStatus,
    error,
    clearError,
    reportError,
    pickPlayer,
    refreshPlayers,
  } = useDraft(draftId ?? null);

  const [recsLoading, setRecsLoading] = useState(false);

  const handlePickPlayer = async (playerId: string) => {
    setRecsLoading(true);
    await pickPlayer(playerId);
    setRecsLoading(false);
  };

  if (!draft) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <LoadingSpinner label="Loading draft…" />
      </div>
    );
  }

  if (draft.is_complete) {
    return <PostDraftScreen draft={draft} />;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
      {/* Dismissable error banner */}
      {error && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '8px 14px', background: 'rgba(239,68,68,0.12)',
          borderBottom: '1px solid rgba(239,68,68,0.4)', flexShrink: 0,
        }}>
          <span style={{ fontSize: 12, color: 'var(--danger)', flex: 1 }}>
            {error}
          </span>
          <button
            onClick={clearError}
            style={{
              fontSize: 11, padding: '2px 10px',
              background: 'rgba(239,68,68,0.2)', border: '1px solid rgba(239,68,68,0.4)',
              borderRadius: 4, color: 'var(--danger)', cursor: 'pointer',
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Computer pick notification banner */}
      <ComputerPickOverlay event={computerThinking} />

      {/* Header */}
      <DraftHeader
        draft={draft}
        wsStatus={wsStatus}
        onClockExpire={() => {
          const top = recommendations[0];
          if (top) {
            handlePickPlayer(top.player_id);
          } else {
            reportError('Time expired — no recommendations available. Please make a pick manually.');
          }
        }}
      />

      {/* Main content: grid + sidebar */}
      <div
        className="draft-main-content"
        data-mobile-split={mobilePanelTab === 'recs' ? 'true' : 'false'}
        style={{ display: 'flex', flex: 1, overflow: 'hidden' }}
      >
        {/* Draft grid — visible on board tab, and in split view alongside recs */}
        <div
          className="draft-grid-pane"
          data-hidden={mobilePanelTab !== 'board' && mobilePanelTab !== 'recs' ? 'true' : 'false'}
          style={{ flex: 1, overflow: 'auto', padding: '8px', display: 'flex', flexDirection: 'column' }}
        >
          {/* Mobile-only view toggle (hidden on desktop via CSS) */}
          <div className="mobile-board-toggle">
            <button
              className={mobileBoardView === 'list' ? 'active' : ''}
              onClick={() => setMobileBoardView('list')}
            >
              ≡ List
            </button>
            <button
              className={mobileBoardView === 'grid' ? 'active' : ''}
              onClick={() => setMobileBoardView('grid')}
            >
              ⊞ Grid
            </button>
          </div>

          {/* Desktop: always show 2D grid. Mobile: show based on toggle */}
          <div className="desktop-draft-grid" data-mobile-show={mobileBoardView === 'grid' ? 'true' : 'false'} style={{ flex: 1 }}>
            <DraftGrid draft={draft} newlyAddedPickNumber={newlyAddedPickNumber} />
          </div>
          {/* Mobile vertical pick list */}
          <div className="mobile-draft-board" data-mobile-show={mobileBoardView === 'list' ? 'true' : 'false'}>
            <MobileDraftBoard draft={draft} newlyAddedPickNumber={newlyAddedPickNumber} />
          </div>
        </div>

        {/* Side panel — fixed width on desktop, full width on mobile */}
        <div
          className="draft-side-pane"
          data-hidden={mobilePanelTab === 'board' ? 'true' : 'false'}
          style={{ width: 340, display: 'flex', flexDirection: 'column', overflow: 'hidden', borderLeft: '1px solid var(--border)' }}
        >
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <SidePanel
              draft={draft}
              players={players}
              recommendations={recommendations}
              onPickPlayer={handlePickPlayer}
              onFilterChange={refreshPlayers}
              recsLoading={recsLoading}
              activeTabOverride={mobilePanelTab === 'board' ? undefined : mobilePanelTab}
              onTabChange={(tab) => setMobilePanelTab(tab)}
            />
          </div>
          <PickInput draft={draft} onPickPlayer={handlePickPlayer} />
        </div>
      </div>

      {/* Footer toolbar */}
      <div className="draft-footer" style={{
        padding: '6px 12px', borderTop: '1px solid var(--border)',
        background: 'var(--bg-secondary)', display: 'flex', gap: 8, alignItems: 'center',
      }}>
        <button
          className="secondary draft-footer-btn"
          onClick={() => navigate('/')}
          style={{ fontSize: 12, padding: '4px 12px' }}
        >
          ← Home
        </button>

        {draft.league_config.draft_mode === 'simulation' && !draft.is_complete && (
          <button
            className="secondary draft-footer-btn"
            disabled={simming}
            onClick={async () => {
              setSimming(true);
              await simulateDraft(draftId!).catch(() => {});
              setSimming(false);
            }}
            style={{ fontSize: 12, padding: '4px 12px' }}
          >
            {simming ? 'Simulating…' : 'Sim Rest'}
          </button>
        )}

        <button className="secondary draft-footer-btn" onClick={() => exportDraft(draftId!)} style={{ fontSize: 12, padding: '4px 12px' }}>
          Export CSV
        </button>
      </div>

      {/* Mobile bottom navigation bar (hidden on desktop via CSS) */}
      <nav className="mobile-bottom-nav">
        {(['board', 'recs', 'available', 'roster'] as const).map((tab) => {
          const icons: Record<MobileTab, string> = { board: '📋', recs: '🤖', available: '🏈', roster: '👤' };
          const labels: Record<MobileTab, string> = { board: 'Board', recs: 'Recs', available: 'Available', roster: 'Roster' };
          return (
            <button
              key={tab}
              className={`mobile-nav-btn${mobilePanelTab === tab ? ' active' : ''}`}
              onClick={() => setMobilePanelTab(tab)}
            >
              <span style={{ fontSize: 16 }}>{icons[tab]}</span>
              <span>{labels[tab]}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
}
