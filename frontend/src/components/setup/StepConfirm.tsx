import type { CreateDraftRequest } from '../../types/draft';

const SCORING_LABELS: Record<string, string> = {
  standard: 'Standard',
  half_ppr: 'Half PPR',
  full_ppr: 'Full PPR',
};

interface Props {
  config: CreateDraftRequest;
  onSubmit: () => void;
  loading: boolean;
}

export function StepConfirm({ config, onSubmit, loading }: Props) {
  const totalRounds = Object.values(config.roster_slots).reduce((a, b) => a + b, 0);

  return (
    <div>
      <h2 style={{ marginBottom: 20, fontSize: 20 }}>Confirm Draft Settings</h2>
      <div className="card" style={{ marginBottom: 16 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <tbody>
            {[
              ['Mode', config.draft_mode === 'simulation' ? 'Simulation' : 'Manual Tracker'],
              ['League Size', `${config.league_size} teams`],
              ['Scoring', SCORING_LABELS[config.scoring_format]],
              ['Total Rounds', totalRounds],
              ['Your Team', config.team_names[config.human_team_id]],
              ['Pick Trades', config.pick_trades.length === 0 ? 'None' : `${config.pick_trades.length} trade(s)`],
            ].map(([label, val]) => (
              <tr key={String(label)} style={{ borderBottom: '1px solid var(--border)' }}>
                <td style={{ padding: '8px 0', color: 'var(--text-muted)', width: '40%' }}>{label}</td>
                <td style={{ padding: '8px 0', fontWeight: 600 }}>{val}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ marginBottom: 16 }}>
        <div className="label" style={{ marginBottom: 8 }}>Teams</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {config.team_names.map((name, i) => (
            <span
              key={i}
              style={{
                padding: '4px 10px',
                borderRadius: 20,
                background: i === config.human_team_id ? 'var(--accent)' : 'var(--bg-hover)',
                fontSize: 13,
              }}
            >
              {name}
            </span>
          ))}
        </div>
      </div>

      <button className="primary" onClick={onSubmit} disabled={loading} style={{ width: '100%', padding: '12px' }}>
        {loading ? 'Creating Draft…' : '🏈 Start Draft'}
      </button>
    </div>
  );
}
