import { useState } from 'react';
import { DraftList } from './DraftList';

type View = 'home' | 'new' | 'resume';

interface Props {
  onNewDraft: () => void;
}

export function LandingPage({ onNewDraft }: Props) {
  const [view, setView] = useState<View>('home');

  if (view === 'resume') {
    return (
      <div style={{ maxWidth: 700, margin: '0 auto', padding: '32px 16px' }}>
        <button className="secondary" onClick={() => setView('home')} style={{ marginBottom: 24, fontSize: 13 }}>
          ← Back
        </button>
        <h2 style={{ marginBottom: 16, fontSize: 20 }}>Saved Drafts</h2>
        <DraftList />
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', height: '100vh', gap: 24,
      }}
    >
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <div style={{ fontSize: 48, marginBottom: 8 }}>🏈</div>
        <h1 style={{ fontSize: 28, fontWeight: 800, marginBottom: 4 }}>Fantasy Draft Tracker</h1>
        <p style={{ color: 'var(--text-muted)' }}>AI-powered draft assistant with Monte Carlo simulations</p>
      </div>

      <div style={{ display: 'flex', gap: 16 }}>
        <button
          className="primary"
          onClick={onNewDraft}
          style={{ padding: '14px 32px', fontSize: 16 }}
        >
          + New Draft
        </button>
        <button
          className="secondary"
          onClick={() => setView('resume')}
          style={{ padding: '14px 32px', fontSize: 16 }}
        >
          Resume Draft
        </button>
      </div>
    </div>
  );
}
