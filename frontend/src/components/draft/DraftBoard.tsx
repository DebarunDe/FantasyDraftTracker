import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { exportDraft, simulateDraft } from '../../api/drafts';
import { useDraft } from '../../hooks/useDraft';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ComputerPickOverlay } from './ComputerPickOverlay';
import { DraftGrid } from './DraftGrid';
import { DraftHeader } from './DraftHeader';
import { PickInput } from './PickInput';
import { PostDraftScreen } from './PostDraftScreen';
import { SidePanel } from './SidePanel';

export function DraftBoard() {
  const { draftId } = useParams<{ draftId: string }>();
  const navigate = useNavigate();
  const [simming, setSimming] = useState(false);
  const {
    draft,
    players,
    recommendations,
    computerThinking,
    newlyAddedPickNumber,
    wsStatus,
    error,
    clearError,
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
      <DraftHeader draft={draft} wsStatus={wsStatus} />

      {/* Main content: grid + sidebar */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Draft grid — scrollable */}
        <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
          <DraftGrid draft={draft} newlyAddedPickNumber={newlyAddedPickNumber} />
        </div>

        {/* Side panel — fixed width */}
        <div style={{ width: 340, display: 'flex', flexDirection: 'column', overflow: 'hidden', borderLeft: '1px solid var(--border)' }}>
          <div style={{ flex: 1, overflow: 'hidden' }}>
            <SidePanel
              draft={draft}
              players={players}
              recommendations={recommendations}
              onPickPlayer={handlePickPlayer}
              onFilterChange={refreshPlayers}
              recsLoading={recsLoading}
            />
          </div>
          <PickInput draft={draft} players={players} onPickPlayer={handlePickPlayer} />
        </div>
      </div>

      {/* Footer toolbar */}
      <div style={{
        padding: '6px 12px', borderTop: '1px solid var(--border)',
        background: 'var(--bg-secondary)', display: 'flex', gap: 8, alignItems: 'center',
      }}>
        <button
          className="secondary"
          onClick={() => navigate('/')}
          style={{ fontSize: 12, padding: '4px 12px' }}
        >
          ← Home
        </button>

        {draft.league_config.draft_mode === 'simulation' && !draft.is_complete && (
          <button
            className="secondary"
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

        <button className="secondary" onClick={() => exportDraft(draftId!)} style={{ fontSize: 12, padding: '4px 12px' }}>
          Export CSV
        </button>
      </div>
    </div>
  );
}
