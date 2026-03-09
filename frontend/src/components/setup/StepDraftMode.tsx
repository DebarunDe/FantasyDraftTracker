import type { DraftMode } from '../../types/draft';

interface Props {
  value: DraftMode;
  onChange: (v: DraftMode) => void;
}

export function StepDraftMode({ value, onChange }: Props) {
  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20 }}>Select Draft Mode</h2>
      <div style={{ display: 'flex', gap: 16 }}>
        {(['simulation', 'manual_tracker'] as DraftMode[]).map((mode) => (
          <label
            key={mode}
            style={{
              flex: 1, padding: 20, borderRadius: 8, border: '2px solid',
              borderColor: value === mode ? 'var(--accent)' : 'var(--border)',
              background: value === mode ? 'rgba(59,130,246,0.1)' : 'var(--bg-card)',
              cursor: 'pointer', display: 'block',
            }}
          >
            <input
              type="radio"
              name="draft_mode"
              value={mode}
              checked={value === mode}
              onChange={() => onChange(mode)}
              style={{ display: 'none' }}
            />
            <div style={{ fontWeight: 700, marginBottom: 8, textTransform: 'capitalize' }}>
              {mode === 'simulation' ? '🤖 Simulation' : '📋 Manual Tracker'}
            </div>
            <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
              {mode === 'simulation'
                ? 'Computer teams auto-pick with AI. You make picks for your team with recommendations.'
                : 'You enter all picks manually. Track a real draft in progress.'}
            </div>
          </label>
        ))}
      </div>
    </div>
  );
}
