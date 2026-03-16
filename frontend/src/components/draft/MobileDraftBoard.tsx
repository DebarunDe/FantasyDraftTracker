import { useEffect, useRef } from 'react';
import type { DraftSummary } from '../../types/draft';
import { PositionBadge } from '../common/PositionBadge';

interface Props {
  draft: DraftSummary;
  newlyAddedPickNumber: number | null;
}

export function MobileDraftBoard({ draft, newlyAddedPickNumber }: Props) {
  const { draft_order, all_picks, teams, current_pick, is_complete } = draft;
  const leagueSize = draft_order[0]?.length ?? 0;

  const pickMap = new Map(all_picks.map((p) => [p.pick_number, p]));
  const onClockRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to current pick whenever it changes
  useEffect(() => {
    onClockRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [current_pick]);

  return (
    <div style={{ padding: '8px 0' }}>
      {draft_order.map((round, roundIdx) => (
        <div key={roundIdx}>
          {/* Round header */}
          <div style={{
            fontSize: 11, fontWeight: 700, color: 'var(--text-muted)',
            textTransform: 'uppercase', letterSpacing: '0.08em',
            padding: '10px 14px 4px',
            borderBottom: '1px solid var(--border)',
          }}>
            Round {roundIdx + 1}
          </div>

          {round.map((teamId, slotIdx) => {
            const pickNumber = roundIdx * leagueSize + slotIdx + 1;
            const pick = pickMap.get(pickNumber);
            const team = teams[teamId];
            const isOnClock = pickNumber === current_pick && !is_complete;
            const isHuman = team?.is_human ?? false;
            const isNew = pickNumber === newlyAddedPickNumber;

            if (isOnClock) {
              return (
                <div
                  key={pickNumber}
                  ref={onClockRef}
                  className="on-clock-pulse"
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '10px 14px',
                    background: 'rgba(251,191,36,0.1)',
                    borderLeft: '3px solid #fbbf24',
                    borderBottom: '1px solid var(--border)',
                    minHeight: 52,
                  }}
                >
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, minWidth: 28 }}>
                    #{pickNumber}
                  </span>
                  <span style={{ fontSize: 11, fontWeight: 800, color: '#fbbf24', letterSpacing: '0.05em' }}>
                    ON CLOCK
                  </span>
                  <span style={{ fontSize: 13, fontWeight: 600, color: isHuman ? 'var(--accent)' : 'var(--text-primary)' }}>
                    {team?.team_name ?? `Team ${teamId + 1}`}
                    {isHuman && <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 5 }}>← You</span>}
                  </span>
                </div>
              );
            }

            if (pick) {
              const labelColor = (pick.reach_label === 'STEAL' || pick.reach_label === 'Value')
                ? 'var(--success)'
                : pick.reach_label === 'REACH'
                  ? 'var(--danger)'
                  : undefined;

              return (
                <div
                  key={pickNumber}
                  className={isNew ? 'tile-new' : undefined}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 14px',
                    borderBottom: '1px solid var(--border)',
                    borderLeft: isHuman ? '3px solid var(--accent)' : '3px solid transparent',
                    background: isHuman ? 'rgba(59,130,246,0.04)' : 'transparent',
                    minHeight: 52,
                  }}
                >
                  {/* Pick number */}
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, minWidth: 28, flexShrink: 0 }}>
                    #{pickNumber}
                  </span>

                  {/* Position badge */}
                  <PositionBadge position={pick.position} />

                  {/* Player + team info */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: 13, fontWeight: 700,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {pick.player_name}
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 1 }}>
                      {pick.nfl_team}
                      <span style={{ margin: '0 4px', opacity: 0.4 }}>·</span>
                      <span style={{ color: isHuman ? 'var(--accent)' : 'var(--text-secondary)' }}>
                        {team?.team_name ?? `Team ${teamId + 1}`}
                      </span>
                    </div>
                  </div>

                  {/* Reach/steal label */}
                  {pick.reach_label && labelColor && (
                    <span style={{ fontSize: 10, fontWeight: 700, color: labelColor, flexShrink: 0 }}>
                      {pick.reach_label}
                    </span>
                  )}
                </div>
              );
            }

            // Future empty pick
            return (
              <div
                key={pickNumber}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '8px 14px',
                  borderBottom: '1px solid var(--border)',
                  opacity: 0.35,
                  minHeight: 52,
                }}
              >
                <span style={{ fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, minWidth: 28 }}>
                  #{pickNumber}
                </span>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {team?.team_name ?? `Team ${teamId + 1}`}
                </span>
              </div>
            );
          })}
        </div>
      ))}

      {is_complete && (
        <div style={{
          padding: '16px 14px', textAlign: 'center',
          fontSize: 12, color: 'var(--success)', fontWeight: 700,
        }}>
          ✓ Draft Complete
        </div>
      )}
    </div>
  );
}
