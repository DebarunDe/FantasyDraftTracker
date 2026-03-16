import { useMemo } from 'react';
import type { DraftSummary, PickResponse } from '../../types/draft';
import { EmptyTile } from './EmptyTile';
import { PlayerTile } from './PlayerTile';

interface Props {
  draft: DraftSummary;
  newlyAddedPickNumber: number | null;
}

export function DraftGrid({ draft, newlyAddedPickNumber }: Props) {
  const { draft_order, all_picks, teams, current_pick } = draft;

  // pick_number → Pick lookup
  const pickMap = useMemo(() => {
    const map = new Map<number, PickResponse>();
    all_picks.forEach((p) => map.set(p.pick_number, p));
    return map;
  }, [all_picks]);

  const teamNames = teams.map((t) => t.team_name);
  const leagueSize = draft_order[0]?.length ?? 0;

  // Stable column order: team_id 0…N-1. Each column always represents the same
  // team regardless of snake direction.
  const columnTeamIds = useMemo(
    () => Array.from({ length: leagueSize }, (_, i) => i),
    [leagueSize],
  );

  return (
    <div className="draft-grid-scroll" style={{ overflowY: 'auto', overflowX: 'auto', flex: 1 }}>
      <table className="draft-grid-table" style={{ borderCollapse: 'collapse', width: '100%', tableLayout: 'fixed' }}>
        <thead>
          <tr>
            <th style={{ width: 36, padding: '6px 4px', color: 'var(--text-muted)', fontSize: 11, textAlign: 'center' }}>
              RD
            </th>
            {columnTeamIds.map((teamId) => (
              <th
                key={teamId}
                style={{
                  padding: '6px 4px', fontSize: 11, fontWeight: 600,
                  color: teams[teamId]?.is_human ? 'var(--accent)' : 'var(--text-secondary)',
                  textAlign: 'center', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}
                title={teamNames[teamId]}
              >
                {teamNames[teamId] ?? `T${teamId + 1}`}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {draft_order.map((round, roundIdx) => {
            // Each team's "natural" pick position is what their slot would be in a
            // standard snake draft (ignoring trades). For even rounds (0-indexed) the
            // order is left→right (pos = teamId); for odd rounds it's right→left
            // (pos = leagueSize - 1 - teamId).
            // We then look at draft_order[round][naturalPos] to find who ACTUALLY
            // picks there after any trade. If that differs from the column's teamId,
            // the slot was traded away and the tile shows a "→ Recipient" indicator.
            const isReversed = roundIdx % 2 === 1;

            return (
              <tr key={roundIdx}>
                <td style={{ padding: '3px 4px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 11, fontWeight: 600 }}>
                  {roundIdx + 1}
                </td>
                {columnTeamIds.map((teamId) => {
                  const naturalPos = isReversed ? leagueSize - 1 - teamId : teamId;
                  const actualPickerId = round[naturalPos];
                  const pickNumber = roundIdx * leagueSize + naturalPos + 1;
                  const pick = pickMap.get(pickNumber);
                  const isOnClock = pickNumber === current_pick && !draft.is_complete;
                  // Slot was traded to another team
                  const tradedTo = actualPickerId !== teamId
                    ? (teamNames[actualPickerId] ?? `Team ${actualPickerId + 1}`)
                    : undefined;

                  return (
                    <td key={teamId} style={{ padding: '3px 4px' }}>
                      {pick ? (
                        <PlayerTile
                          pick={pick}
                          isNew={pick.pick_number === newlyAddedPickNumber}
                          tradedTo={tradedTo}
                        />
                      ) : (
                        <EmptyTile
                          isOnClock={isOnClock}
                          teamName={teamNames[teamId] ?? ''}
                        />
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
