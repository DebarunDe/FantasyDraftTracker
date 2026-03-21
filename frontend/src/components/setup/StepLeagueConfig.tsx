import type { DraftMode, ScoringFormat } from '../../types/draft';

interface LeagueConfigValues {
  leagueSize: number;
  scoringFormat: ScoringFormat;
  rosterSlots: Record<string, number>;
  pickClockSeconds: number | null;
}

interface Props {
  value: LeagueConfigValues;
  onChange: (v: LeagueConfigValues) => void;
  draftMode: DraftMode;
}

const VALID_SIZES = [8, 10, 12, 14];
const SCORING_OPTIONS: { value: ScoringFormat; label: string }[] = [
  { value: 'standard', label: 'Standard' },
  { value: 'half_ppr', label: 'Half PPR' },
  { value: 'full_ppr', label: 'Full PPR' },
];
const SLOT_ORDER = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'DST', 'K', 'BENCH'];

const CLOCK_OPTIONS: { label: string; value: number | null }[] = [
  { label: 'No timer', value: null },
  { label: '30s', value: 30 },
  { label: '60s', value: 60 },
  { label: '90s', value: 90 },
  { label: '2 min', value: 120 },
  { label: '3 min', value: 180 },
  { label: '5 min', value: 300 },
];

export function StepLeagueConfig({ value, onChange, draftMode }: Props) {
  const update = (key: keyof LeagueConfigValues, val: unknown) =>
    onChange({ ...value, [key]: val });

  const updateSlot = (pos: string, n: number) =>
    onChange({ ...value, rosterSlots: { ...value.rosterSlots, [pos]: n } });

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20 }}>League Settings</h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 24 }}>
        <div>
          <div className="label">League Size</div>
          <select value={value.leagueSize} onChange={(e) => update('leagueSize', Number(e.target.value))}>
            {VALID_SIZES.map((s) => (
              <option key={s} value={s}>{s} Teams</option>
            ))}
          </select>
        </div>
        <div>
          <div className="label">Scoring Format</div>
          <select value={value.scoringFormat} onChange={(e) => update('scoringFormat', e.target.value as ScoringFormat)}>
            {SCORING_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="label" style={{ marginBottom: 12 }}>Roster Slots</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 24 }}>
        {SLOT_ORDER.map((pos) => (
          <div key={pos}>
            <div style={{ color: 'var(--text-secondary)', fontSize: 12, marginBottom: 4 }}>{pos}</div>
            <input
              type="number"
              min={0}
              max={20}
              value={value.rosterSlots[pos] ?? 0}
              onChange={(e) => updateSlot(pos, Number(e.target.value))}
              style={{ width: '100%' }}
            />
          </div>
        ))}
      </div>

      {draftMode !== 'manual_tracker' && (
        <div>
          <div className="label" style={{ marginBottom: 8 }}>Pick Timer</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {CLOCK_OPTIONS.map((opt) => (
              <button
                key={String(opt.value)}
                type="button"
                aria-pressed={value.pickClockSeconds === opt.value}
                onClick={() => update('pickClockSeconds', opt.value)}
                style={{
                  padding: '6px 14px', borderRadius: 6, fontSize: 13,
                  border: '2px solid',
                  borderColor: value.pickClockSeconds === opt.value ? 'var(--accent)' : 'var(--border)',
                  background: value.pickClockSeconds === opt.value ? 'rgba(59,130,246,0.12)' : 'var(--bg-card)',
                  color: value.pickClockSeconds === opt.value ? 'var(--accent)' : 'var(--text-secondary)',
                  fontWeight: value.pickClockSeconds === opt.value ? 700 : 400,
                  cursor: 'pointer',
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
          {value.pickClockSeconds !== null && (
            <div style={{ marginTop: 6, fontSize: 12, color: 'var(--text-muted)' }}>
              When time runs out, the top recommendation is auto-drafted.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
