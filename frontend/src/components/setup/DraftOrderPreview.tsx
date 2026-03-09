interface Props {
  draftOrder: number[][];
  teamNames: string[];
  highlightTeamId?: number;
}

export function DraftOrderPreview({ draftOrder, teamNames, highlightTeamId }: Props) {
  const maxRoundsToShow = Math.min(draftOrder.length, 5);

  return (
    <div>
      <div className="label" style={{ marginBottom: 8 }}>
        Pick Order Preview (first {maxRoundsToShow} rounds)
      </div>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 12 }}>
          <thead>
            <tr>
              <th style={{ padding: '4px 8px', textAlign: 'left', color: 'var(--text-muted)' }}>Rd</th>
              {draftOrder[0]?.map((_, i) => (
                <th key={i} style={{ padding: '4px 6px', color: 'var(--text-muted)', fontWeight: 500 }}>
                  #{i + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {draftOrder.slice(0, maxRoundsToShow).map((round, rIdx) => (
              <tr key={rIdx}>
                <td style={{ padding: '3px 8px', color: 'var(--text-secondary)', fontWeight: 600 }}>
                  {rIdx + 1}
                </td>
                {round.map((teamId, pIdx) => (
                  <td
                    key={pIdx}
                    style={{
                      padding: '3px 6px',
                      background: highlightTeamId === teamId ? 'rgba(59,130,246,0.2)' : 'transparent',
                      color: highlightTeamId === teamId ? 'var(--accent)' : 'var(--text-secondary)',
                      fontWeight: highlightTeamId === teamId ? 700 : 400,
                      borderRadius: 4,
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {teamNames[teamId] ?? `T${teamId + 1}`}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
