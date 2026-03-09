import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { StepDraftMode } from '../../../src/components/setup/StepDraftMode';

describe('StepDraftMode', () => {
  it('renders both mode options', () => {
    render(<StepDraftMode value="simulation" onChange={() => {}} />);
    expect(screen.getByText(/Simulation/)).toBeInTheDocument();
    expect(screen.getByText(/Manual Tracker/)).toBeInTheDocument();
  });

  it('renders the description text for each mode', () => {
    render(<StepDraftMode value="simulation" onChange={() => {}} />);
    expect(screen.getByText(/Computer teams auto-pick/)).toBeInTheDocument();
    expect(screen.getByText(/Track a real draft/)).toBeInTheDocument();
  });

  it('has simulation radio checked when value is simulation', () => {
    render(<StepDraftMode value="simulation" onChange={() => {}} />);
    const simulationRadio = screen.getByDisplayValue('simulation');
    expect(simulationRadio).toBeChecked();
  });

  it('has manual_tracker radio checked when value is manual_tracker', () => {
    render(<StepDraftMode value="manual_tracker" onChange={() => {}} />);
    const manualRadio = screen.getByDisplayValue('manual_tracker');
    expect(manualRadio).toBeChecked();
  });

  it('calls onChange with manual_tracker when that option is clicked', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<StepDraftMode value="simulation" onChange={onChange} />);
    await user.click(screen.getByText(/Manual Tracker/));
    expect(onChange).toHaveBeenCalledWith('manual_tracker');
  });

  it('calls onChange with simulation when simulation option is clicked', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<StepDraftMode value="manual_tracker" onChange={onChange} />);
    await user.click(screen.getByText(/Simulation/));
    expect(onChange).toHaveBeenCalledWith('simulation');
  });
});
