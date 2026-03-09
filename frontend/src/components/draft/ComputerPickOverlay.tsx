import type { WsComputerThinkingEvent } from '../../types/draft';

interface Props {
  event: WsComputerThinkingEvent | null;
}

export function ComputerPickOverlay({ event }: Props) {
  if (!event) return null;

  return (
    <div
      className="fade-in"
      style={{
        position: 'fixed', top: 0, left: 0, right: 0,
        padding: '12px 16px',
        background: 'rgba(30, 41, 59, 0.95)',
        borderBottom: '2px solid var(--accent)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12,
        zIndex: 100,
        backdropFilter: 'blur(4px)',
      }}
    >
      <div className="spinner" />
      <span style={{ fontWeight: 600, fontSize: 15 }}>
        {event.team_name} is on the clock…
      </span>
      <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
        Pick #{event.pick_number}
      </span>
    </div>
  );
}
