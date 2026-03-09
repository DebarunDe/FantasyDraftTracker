interface Props {
  leagueSize: number;
  humanTeamId: number;
  value: string[];
  onNamesChange: (names: string[]) => void;
  onHumanTeamChange: (id: number) => void;
}

export function StepTeamNames({ leagueSize, humanTeamId, value, onNamesChange, onHumanTeamChange }: Props) {
  const names = value.length === leagueSize
    ? value
    : Array.from({ length: leagueSize }, (_, i) => value[i] ?? `Team ${i + 1}`);

  const updateName = (i: number, v: string) => {
    const next = [...names];
    next[i] = v;
    onNamesChange(next);
  };

  return (
    <div>
      <h2 style={{ marginBottom: 8, fontSize: 20 }}>Team Names</h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20, fontSize: 13 }}>
        Mark your team with the ⭐ button.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
        {names.map((name, i) => (
          <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              style={{
                padding: '8px 10px', flexShrink: 0,
                background: humanTeamId === i ? 'var(--warning)' : 'var(--bg-hover)',
                color: humanTeamId === i ? 'black' : 'var(--text-secondary)',
                borderRadius: 6, fontSize: 16,
              }}
              onClick={() => onHumanTeamChange(i)}
              title="Set as your team"
              type="button"
            >
              ⭐
            </button>
            <input
              type="text"
              placeholder={`Team ${i + 1}`}
              value={name}
              onChange={(e) => updateName(i, e.target.value)}
            />
          </div>
        ))}
      </div>
      <p style={{ marginTop: 12, color: 'var(--text-secondary)', fontSize: 12 }}>
        Your team: <strong>{names[humanTeamId]}</strong> (Team {humanTeamId + 1})
      </p>
    </div>
  );
}
