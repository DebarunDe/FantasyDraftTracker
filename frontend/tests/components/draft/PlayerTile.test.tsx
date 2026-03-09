import { render, screen } from '@testing-library/react';
import { PlayerTile } from '../../../src/components/draft/PlayerTile';
import { mockPick, mockPickWithReach, mockPickWithSteal } from '../../fixtures/mockData';

describe('PlayerTile', () => {
  it('renders player name and pick number', () => {
    render(<PlayerTile pick={mockPick} isNew={false} />);
    expect(screen.getByText('Christian McCaffrey')).toBeInTheDocument();
    expect(screen.getByText('#1')).toBeInTheDocument();
  });

  it('renders the position badge', () => {
    render(<PlayerTile pick={mockPick} isNew={false} />);
    expect(screen.getByText('RB')).toBeInTheDocument();
  });

  it('renders nfl team', () => {
    render(<PlayerTile pick={mockPick} isNew={false} />);
    expect(screen.getByText(/SF/)).toBeInTheDocument();
  });

  it('applies tile-new class when isNew is true', () => {
    const { container } = render(<PlayerTile pick={mockPick} isNew={true} />);
    expect(container.firstChild).toHaveClass('tile-new');
  });

  it('does not apply tile-new class when isNew is false', () => {
    const { container } = render(<PlayerTile pick={mockPick} isNew={false} />);
    expect(container.firstChild).not.toHaveClass('tile-new');
  });

  it('renders reach label in danger color', () => {
    render(<PlayerTile pick={mockPickWithReach} isNew={false} />);
    expect(screen.getByText('Reach')).toBeInTheDocument();
  });

  it('renders STEAL label in success color', () => {
    render(<PlayerTile pick={mockPickWithSteal} isNew={false} />);
    expect(screen.getByText('STEAL')).toBeInTheDocument();
  });

  it('does not render reach label when empty string', () => {
    render(<PlayerTile pick={mockPick} isNew={false} />);
    expect(screen.queryByText('Reach')).not.toBeInTheDocument();
    expect(screen.queryByText('STEAL')).not.toBeInTheDocument();
  });

  it('renders tradedTo label when provided', () => {
    render(<PlayerTile pick={mockPick} isNew={false} tradedTo="Team 3" />);
    expect(screen.getByText('→ Team 3')).toBeInTheDocument();
  });

  it('does not render tradedTo when not provided', () => {
    render(<PlayerTile pick={mockPick} isNew={false} />);
    expect(screen.queryByText(/→/)).not.toBeInTheDocument();
  });
});
