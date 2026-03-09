import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PlayerCard, RecCard } from '../../../src/components/draft/PlayerCard';
import { mockPlayer, mockPlayerNoBye, mockRec, mockRecTierBoundary } from '../../fixtures/mockData';

describe('PlayerCard', () => {
  it('renders player name, position badge, nfl team, and projected points', () => {
    render(<PlayerCard player={mockPlayer} />);
    expect(screen.getByText('Patrick Mahomes')).toBeInTheDocument();
    expect(screen.getByText('QB')).toBeInTheDocument();
    expect(screen.getByText(/KC/)).toBeInTheDocument();
    expect(screen.getByText('380.5')).toBeInTheDocument();
  });

  it('renders bye week when present', () => {
    render(<PlayerCard player={mockPlayer} />);
    expect(screen.getByText(/Bye 10/)).toBeInTheDocument();
  });

  it('omits bye week when null', () => {
    render(<PlayerCard player={mockPlayerNoBye} />);
    expect(screen.queryByText(/Bye/)).not.toBeInTheDocument();
  });

  it('renders rank badge when provided', () => {
    render(<PlayerCard player={mockPlayer} rank={3} />);
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('omits rank when not provided', () => {
    render(<PlayerCard player={mockPlayer} />);
    // Only the pts label should be a short number-like text; no rank number rendered
    expect(screen.queryByText('1')).not.toBeInTheDocument();
  });

  it('calls onPick with player_id when clicked', async () => {
    const user = userEvent.setup();
    const onPick = vi.fn();
    render(<PlayerCard player={mockPlayer} onPick={onPick} />);
    await user.click(screen.getByText('Patrick Mahomes'));
    expect(onPick).toHaveBeenCalledWith('player-1');
  });

  it('does not crash when clicked without onPick', async () => {
    const user = userEvent.setup();
    render(<PlayerCard player={mockPlayer} />);
    await user.click(screen.getByText('Patrick Mahomes'));
    // No error thrown
  });
});

describe('RecCard', () => {
  it('renders player name and reasoning text', () => {
    render(<RecCard rec={mockRec} />);
    expect(screen.getByText('Saquon Barkley')).toBeInTheDocument();
    expect(screen.getByText('Elite RB1 with massive VOR advantage over RB2')).toBeInTheDocument();
  });

  it('shows MC delta when mc_delta > 0', () => {
    render(<RecCard rec={mockRec} />);
    expect(screen.getByText('MC +12.5')).toBeInTheDocument();
  });

  it('hides MC delta when mc_delta is 0', () => {
    render(<RecCard rec={mockRecTierBoundary} />);
    expect(screen.queryByText(/MC \+/)).not.toBeInTheDocument();
  });

  it('shows TIER EDGE label when is_tier_boundary is true', () => {
    render(<RecCard rec={mockRecTierBoundary} />);
    expect(screen.getByText('TIER EDGE')).toBeInTheDocument();
  });

  it('hides TIER EDGE when is_tier_boundary is false', () => {
    render(<RecCard rec={mockRec} />);
    expect(screen.queryByText('TIER EDGE')).not.toBeInTheDocument();
  });

  it('calls onPick with player_id when clicked', async () => {
    const user = userEvent.setup();
    const onPick = vi.fn();
    render(<RecCard rec={mockRec} onPick={onPick} />);
    await user.click(screen.getByText('Saquon Barkley'));
    expect(onPick).toHaveBeenCalledWith('player-4');
  });
});
