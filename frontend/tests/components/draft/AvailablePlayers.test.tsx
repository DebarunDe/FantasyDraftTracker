import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AvailablePlayers } from '../../../src/components/draft/AvailablePlayers';
import { mockPlayer, mockPlayerNoBye } from '../../fixtures/mockData';

const DEFAULT_SLOTS: Record<string, number> = {
  QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, DST: 1, K: 1, BENCH: 6,
};

const NO_K_DST_SLOTS: Record<string, number> = {
  QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, DST: 0, K: 0, BENCH: 6,
};

const NO_QB_SLOTS: Record<string, number> = {
  QB: 0, RB: 2, WR: 2, TE: 1, FLEX: 1, DST: 1, K: 1, BENCH: 6,
};

const NO_RB_SLOTS: Record<string, number> = {
  QB: 1, RB: 0, WR: 2, TE: 1, FLEX: 1, DST: 1, K: 1, BENCH: 6,
};

const players = [mockPlayer, mockPlayerNoBye];
const noop = () => {};

describe('AvailablePlayers — tab visibility', () => {
  it('shows All tab and all standard position tabs with default slots', () => {
    render(
      <AvailablePlayers
        players={players}
        onPickPlayer={noop}
        onFilterChange={noop}
        rosterSlots={DEFAULT_SLOTS}
      />,
    );
    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument();
    for (const pos of ['QB', 'RB', 'WR', 'TE', 'K', 'DST']) {
      expect(screen.getByRole('button', { name: pos })).toBeInTheDocument();
    }
  });

  it('hides K and DST tabs when their slots are 0', () => {
    render(
      <AvailablePlayers
        players={players}
        onPickPlayer={noop}
        onFilterChange={noop}
        rosterSlots={NO_K_DST_SLOTS}
      />,
    );
    expect(screen.queryByRole('button', { name: 'K' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'DST' })).not.toBeInTheDocument();
  });

  it('hides QB tab when QB slots are 0 (not FLEX-eligible)', () => {
    render(
      <AvailablePlayers
        players={players}
        onPickPlayer={noop}
        onFilterChange={noop}
        rosterSlots={NO_QB_SLOTS}
      />,
    );
    expect(screen.queryByRole('button', { name: 'QB' })).not.toBeInTheDocument();
  });

  it('keeps RB tab when RB slots are 0 because RB is FLEX-eligible', () => {
    render(
      <AvailablePlayers
        players={players}
        onPickPlayer={noop}
        onFilterChange={noop}
        rosterSlots={NO_RB_SLOTS}
      />,
    );
    expect(screen.getByRole('button', { name: 'RB' })).toBeInTheDocument();
  });
});

describe('AvailablePlayers — player list and interactions', () => {
  it('renders all players by default', () => {
    render(
      <AvailablePlayers
        players={players}
        onPickPlayer={noop}
        onFilterChange={noop}
        rosterSlots={DEFAULT_SLOTS}
      />,
    );
    expect(screen.getByText('Patrick Mahomes')).toBeInTheDocument();
    expect(screen.getByText('Justin Jefferson')).toBeInTheDocument();
  });

  it('shows no players found when list is empty', () => {
    render(
      <AvailablePlayers
        players={[]}
        onPickPlayer={noop}
        onFilterChange={noop}
        rosterSlots={DEFAULT_SLOTS}
      />,
    );
    expect(screen.getByText('No players found.')).toBeInTheDocument();
  });

  it('filters displayed players by search input', async () => {
    const user = userEvent.setup();
    render(
      <AvailablePlayers
        players={players}
        onPickPlayer={noop}
        onFilterChange={noop}
        rosterSlots={DEFAULT_SLOTS}
      />,
    );
    await user.type(screen.getByPlaceholderText('Search player…'), 'Mahomes');
    expect(screen.getByText('Patrick Mahomes')).toBeInTheDocument();
    expect(screen.queryByText('Justin Jefferson')).not.toBeInTheDocument();
  });

  it('search is case-insensitive', async () => {
    const user = userEvent.setup();
    render(
      <AvailablePlayers
        players={players}
        onPickPlayer={noop}
        onFilterChange={noop}
        rosterSlots={DEFAULT_SLOTS}
      />,
    );
    await user.type(screen.getByPlaceholderText('Search player…'), 'mahomes');
    expect(screen.getByText('Patrick Mahomes')).toBeInTheDocument();
  });

  it('calls onFilterChange with position string when position tab clicked', async () => {
    const user = userEvent.setup();
    const onFilterChange = vi.fn();
    render(
      <AvailablePlayers
        players={players}
        onPickPlayer={noop}
        onFilterChange={onFilterChange}
        rosterSlots={DEFAULT_SLOTS}
      />,
    );
    await user.click(screen.getByRole('button', { name: 'WR' }));
    expect(onFilterChange).toHaveBeenCalledWith('WR');
  });

  it('calls onFilterChange with undefined when All tab clicked', async () => {
    const user = userEvent.setup();
    const onFilterChange = vi.fn();
    render(
      <AvailablePlayers
        players={players}
        onPickPlayer={noop}
        onFilterChange={onFilterChange}
        rosterSlots={DEFAULT_SLOTS}
      />,
    );
    // Click QB first, then switch back to All
    await user.click(screen.getByRole('button', { name: 'QB' }));
    await user.click(screen.getByRole('button', { name: 'All' }));
    expect(onFilterChange).toHaveBeenLastCalledWith(undefined);
  });

  it('calls onPickPlayer with player_id when a player card is clicked', async () => {
    const user = userEvent.setup();
    const onPickPlayer = vi.fn();
    render(
      <AvailablePlayers
        players={[mockPlayer]}
        onPickPlayer={onPickPlayer}
        onFilterChange={noop}
        rosterSlots={DEFAULT_SLOTS}
      />,
    );
    await user.click(screen.getByText('Patrick Mahomes'));
    expect(onPickPlayer).toHaveBeenCalledWith('player-1');
  });
});
