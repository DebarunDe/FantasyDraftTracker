import { render, screen } from '@testing-library/react';
import { DraftHeader } from '../../../src/components/draft/DraftHeader';
import { makeDraftSummary } from '../../fixtures/mockData';

// Prevent real timers from running in usePickClock
vi.mock('../../../src/hooks/usePickClock', () => ({
  usePickClock: () => 45,
}));

// Render PickClock as a simple stub
vi.mock('../../../src/components/draft/PickClock', () => ({
  PickClock: () => <div data-testid="pick-clock" />,
}));

describe('DraftHeader', () => {
  it('renders current round and total rounds', () => {
    const draft = makeDraftSummary({ current_round: 3 });
    render(<DraftHeader draft={draft} wsStatus="open" />);
    expect(screen.getByText(/3/)).toBeInTheDocument();
    // totalRounds = sum of roster slots = 15 for default config
    expect(screen.getByText(/15/)).toBeInTheDocument();
  });

  it('renders current pick number', () => {
    const draft = makeDraftSummary({ current_pick: 7 });
    render(<DraftHeader draft={draft} wsStatus="open" />);
    expect(screen.getByText('7')).toBeInTheDocument();
  });

  it('shows the team currently on the clock', () => {
    const draft = makeDraftSummary({ current_team_id: 2 });
    render(<DraftHeader draft={draft} wsStatus="open" />);
    expect(screen.getByText('Team 3')).toBeInTheDocument();
  });

  it('shows "← You" indicator on human turn', () => {
    // Team 0 is human in the default fixture
    const draft = makeDraftSummary({ current_team_id: 0 });
    render(<DraftHeader draft={draft} wsStatus="open" />);
    expect(screen.getByText('← You')).toBeInTheDocument();
  });

  it('hides "← You" on computer turn', () => {
    // Team 1 is a computer team
    const draft = makeDraftSummary({ current_team_id: 1 });
    render(<DraftHeader draft={draft} wsStatus="open" />);
    expect(screen.queryByText('← You')).not.toBeInTheDocument();
  });

  it('shows Draft Complete badge when is_complete is true', () => {
    const draft = makeDraftSummary({ is_complete: true });
    render(<DraftHeader draft={draft} wsStatus="open" />);
    expect(screen.getByText(/Draft Complete/)).toBeInTheDocument();
  });

  it('hides on-clock section when draft is complete', () => {
    const draft = makeDraftSummary({ is_complete: true, current_team_id: 0 });
    render(<DraftHeader draft={draft} wsStatus="open" />);
    expect(screen.queryByText('ON CLOCK')).not.toBeInTheDocument();
  });

  it('shows Manual badge for manual_tracker mode', () => {
    const draft = makeDraftSummary({
      league_config: {
        league_id: 'league-1',
        league_size: 12,
        scoring_format: 'half_ppr',
        draft_type: 'snake',
        draft_mode: 'manual_tracker',
        data_year: 2025,
        roster_slots: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, DST: 1, K: 1, BENCH: 6 },
      },
    });
    render(<DraftHeader draft={draft} wsStatus="open" />);
    expect(screen.getByText('Manual')).toBeInTheDocument();
  });

  it('does not show Manual badge for simulation mode', () => {
    const draft = makeDraftSummary();
    render(<DraftHeader draft={draft} wsStatus="open" />);
    expect(screen.queryByText('Manual')).not.toBeInTheDocument();
  });

  it('renders the scoring format label', () => {
    const draft = makeDraftSummary();
    render(<DraftHeader draft={draft} wsStatus="open" />);
    expect(screen.getByText(/Half PPR/)).toBeInTheDocument();
  });
});
