interface Props {
  isOnClock: boolean;
  teamName: string;
}

export function EmptyTile({ isOnClock, teamName }: Props) {
  if (isOnClock) {
    return (
      <div
        className="on-clock-pulse"
        style={{
          background: 'rgba(251, 191, 36, 0.1)',
          border: '2px solid #fbbf24',
          borderRadius: 6,
          padding: '6px 8px',
          height: 66,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <span style={{ fontSize: 11, fontWeight: 700, color: '#fbbf24' }}>ON CLOCK</span>
      </div>
    );
  }

  return (
    <div
      style={{
        background: 'transparent',
        border: '1px solid var(--border)',
        borderRadius: 6,
        padding: '6px 8px',
        height: 66,
        opacity: 0.3,
      }}
      title={teamName}
    />
  );
}
