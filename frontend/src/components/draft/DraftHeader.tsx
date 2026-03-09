import type { DraftSummary } from '../../types/draft';
import { usePickClock } from '../../hooks/usePickClock';
import { PickClock } from './PickClock';

const SCORING_LABELS: Record<string, string> = {
  standard: 'Standard', half_ppr: 'Half PPR', full_ppr: 'Full PPR',
};

interface Props {
  draft: DraftSummary;
  wsStatus: string;
}

export function DraftHeader({ draft, wsStatus }: Props) {
  const { current_round, current_pick, current_team_id, is_complete, league_config, teams } = draft;
  const currentTeam = teams[current_team_id];
  const isHumanTurn = currentTeam?.is_human ?? false;
  const totalRounds = Object.values(league_config.roster_slots).reduce((a, b) => a + b, 0);

  const clockSeconds = usePickClock(90, isHumanTurn && !is_complete);

  return (
    <div
      style={{
        padding: '10px 16px',
        background: 'var(--bg-secondary)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16,
        flexWrap: 'wrap',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <div>
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>ROUND</span>
          <div style={{ fontWeight: 700, fontSize: 18 }}>{current_round}<span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: 14 }}>/{totalRounds}</span></div>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>PICK</span>
          <div style={{ fontWeight: 700, fontSize: 18 }}>{current_pick}</div>
        </div>
        {!is_complete && (
          <div>
            <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>ON CLOCK</span>
            <div
              style={{
                fontWeight: 700, fontSize: 15,
                color: isHumanTurn ? 'var(--accent)' : 'var(--text-primary)',
              }}
            >
              {currentTeam?.team_name ?? '—'}
              {isHumanTurn && (
                <span style={{ marginLeft: 8, fontSize: 12, color: 'var(--success)' }}>← You</span>
              )}
            </div>
          </div>
        )}
        {is_complete && (
          <span style={{ color: 'var(--success)', fontWeight: 700, fontSize: 15 }}>
            ✓ Draft Complete
          </span>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <PickClock seconds={clockSeconds} total={90} active={isHumanTurn && !is_complete} />
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          {league_config.league_size}-team · {SCORING_LABELS[league_config.scoring_format] ?? league_config.scoring_format}
          {league_config.draft_mode === 'manual_tracker' && (
            <span style={{ marginLeft: 8, color: 'var(--warning)', fontWeight: 600 }}>Manual</span>
          )}
        </div>
        <div
          style={{
            width: 8, height: 8, borderRadius: '50%',
            background: wsStatus === 'open' ? 'var(--success)' : wsStatus === 'connecting' ? 'var(--warning)' : 'var(--danger)',
          }}
          title={`WebSocket: ${wsStatus}`}
        />
      </div>
    </div>
  );
}
