import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StepLeagueConfig } from '../../../src/components/setup/StepLeagueConfig';

const DEFAULT_SLOTS: Record<string, number> = {
  QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, DST: 1, K: 1, BENCH: 6,
};

const defaultValue = {
  leagueSize: 12,
  scoringFormat: 'half_ppr' as const,
  rosterSlots: DEFAULT_SLOTS,
  pickClockSeconds: null as number | null,
};

describe('StepLeagueConfig', () => {
  it('renders all valid league size options', () => {
    render(<StepLeagueConfig value={defaultValue} onChange={() => {}} draftMode="simulation" />);
    expect(screen.getByRole('option', { name: '8 Teams' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '10 Teams' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '12 Teams' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '14 Teams' })).toBeInTheDocument();
  });

  it('renders all scoring format options', () => {
    render(<StepLeagueConfig value={defaultValue} onChange={() => {}} draftMode="simulation" />);
    expect(screen.getByRole('option', { name: 'Standard' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Half PPR' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Full PPR' })).toBeInTheDocument();
  });

  it('shows current roster slot values', () => {
    render(<StepLeagueConfig value={defaultValue} onChange={() => {}} draftMode="simulation" />);
    // SLOT_ORDER: QB=1, RB=2, WR=2, TE=1, FLEX=1, DST=1, K=1, BENCH=6
    // Multiple inputs share value "1"; use getAllBy and verify count
    expect(screen.getAllByDisplayValue('1')).toHaveLength(5); // QB, TE, FLEX, DST, K
    expect(screen.getAllByDisplayValue('2')).toHaveLength(2); // RB, WR
    expect(screen.getByDisplayValue('6')).toBeInTheDocument(); // BENCH
  });

  it('calls onChange with updated league size when select changes', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<StepLeagueConfig value={defaultValue} onChange={onChange} draftMode="simulation" />);
    await user.selectOptions(screen.getByDisplayValue('12 Teams'), '10');
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ leagueSize: 10 }),
    );
  });

  it('calls onChange with updated scoring format', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<StepLeagueConfig value={defaultValue} onChange={onChange} draftMode="simulation" />);
    await user.selectOptions(screen.getByDisplayValue('Half PPR'), 'full_ppr');
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ scoringFormat: 'full_ppr' }),
    );
  });

  it('calls onChange with updated roster slots when QB input changes', () => {
    const onChange = vi.fn();
    render(<StepLeagueConfig value={defaultValue} onChange={onChange} draftMode="simulation" />);
    // SLOT_ORDER: QB, RB, WR, TE, FLEX, DST, K, BENCH — QB is the first input with value "1"
    // Use fireEvent.change to directly fire the change event on the controlled input.
    const qbInput = screen.getAllByDisplayValue('1')[0];
    fireEvent.change(qbInput, { target: { value: '2' } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        rosterSlots: expect.objectContaining({ QB: 2 }),
      }),
    );
  });

  it('allows setting a slot to 0 (e.g. disabling K)', () => {
    const onChange = vi.fn();
    render(<StepLeagueConfig value={defaultValue} onChange={onChange} draftMode="simulation" />);
    // SLOT_ORDER: QB[0], TE[1], FLEX[2], DST[3], K[4] — K is the last input with value "1"
    const allOnes = screen.getAllByDisplayValue('1');
    const kField = allOnes[allOnes.length - 1];
    fireEvent.change(kField, { target: { value: '0' } });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        rosterSlots: expect.objectContaining({ K: 0 }),
      }),
    );
  });
});
