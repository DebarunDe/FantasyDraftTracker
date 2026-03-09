interface Props {
  position: string;
}

export function PositionBadge({ position }: Props) {
  return <span className={`pos-badge ${position}`}>{position}</span>;
}
