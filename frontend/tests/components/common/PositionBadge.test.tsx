import { render, screen } from '@testing-library/react';
import { PositionBadge } from '../../../src/components/common/PositionBadge';

describe('PositionBadge', () => {
  it('renders the position text', () => {
    render(<PositionBadge position="QB" />);
    expect(screen.getByText('QB')).toBeInTheDocument();
  });

  it.each(['QB', 'RB', 'WR', 'TE', 'K', 'DST', 'FLEX'])(
    'renders %s with correct CSS class',
    (pos) => {
      render(<PositionBadge position={pos} />);
      const badge = screen.getByText(pos);
      expect(badge).toHaveClass('pos-badge');
      expect(badge).toHaveClass(pos);
    },
  );

  it('renders unknown position without crashing', () => {
    render(<PositionBadge position="UNKNOWN" />);
    expect(screen.getByText('UNKNOWN')).toBeInTheDocument();
  });
});
