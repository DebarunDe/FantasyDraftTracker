import type { ScoringFormat } from '../../types/draft';

interface LeagueConfigValues {
  leagueSize: number;
  scoringFormat: ScoringFormat;
  rosterSlots: Record<string, number>;
}

interface Props {
  value: LeagueConfigValues;
  onChange: (v: LeagueConfigValues) => void;
}

const VALID_SIZES = [8, 10, 12, 14];
const SCORING_OPTIONS: { value: ScoringFormat; label: string }[] = [
  { value: 'standard', label: 'Standard' },
  { value: 'half_ppr', label: 'Half PPR' },
  { value: 'full_ppr', label: 'Full PPR' },
];
const SLOT_ORDER = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'DST', 'K', 'BENCH'];

export function StepLeagueConfig({ value, onChange }: Props) {
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
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
    </div>
  );
}
