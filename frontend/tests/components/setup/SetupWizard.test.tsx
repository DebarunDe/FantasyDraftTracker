import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SetupWizard } from '../../../src/components/setup/SetupWizard';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

vi.mock('../../../src/api/drafts', () => ({
  createDraft: vi.fn().mockResolvedValue({ draft_id: 'new-draft-123' }),
}));

// Stub complex child steps so wizard navigation tests stay focused
vi.mock('../../../src/components/setup/StepPickTrades', () => ({
  StepPickTrades: () => <div>Pick Trades Step</div>,
}));

vi.mock('../../../src/components/setup/StepConfirm', () => ({
  StepConfirm: ({ onSubmit }: { onSubmit: () => void }) => (
    <div>
      <div>Confirm Draft Settings</div>
      <button onClick={onSubmit}>Start Draft</button>
    </div>
  ),
}));

describe('SetupWizard — navigation', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it('starts at step 1 showing draft mode selection', () => {
    render(<SetupWizard />);
    expect(screen.getByText('Select Draft Mode')).toBeInTheDocument();
  });

  it('shows step numbers 1-5 in progress bar', () => {
    render(<SetupWizard />);
    // Steps 2-5 are not yet done, so they show their number
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('advances to step 2 (League Settings) when Next is clicked', async () => {
    const user = userEvent.setup();
    render(<SetupWizard />);
    await user.click(screen.getByText('Next →'));
    expect(screen.getByText('League Settings')).toBeInTheDocument();
  });

  it('advances to step 3 (Team Names) from step 2', async () => {
    const user = userEvent.setup();
    render(<SetupWizard />);
    await user.click(screen.getByText('Next →'));
    await user.click(screen.getByText('Next →'));
    expect(screen.getByText('Team Names')).toBeInTheDocument();
  });
});

describe('SetupWizard — back navigation', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it('shows "← Home" label on step 1', () => {
    render(<SetupWizard />);
    expect(screen.getByRole('button', { name: '← Home' })).toBeInTheDocument();
  });

  it('navigates to / when ← Home is clicked on step 1', async () => {
    const user = userEvent.setup();
    render(<SetupWizard />);
    await user.click(screen.getByRole('button', { name: '← Home' }));
    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  it('shows "← Back" label on step 2', async () => {
    const user = userEvent.setup();
    render(<SetupWizard />);
    await user.click(screen.getByText('Next →'));
    expect(screen.getByRole('button', { name: '← Back' })).toBeInTheDocument();
  });

  it('returns to step 1 when ← Back is clicked on step 2', async () => {
    const user = userEvent.setup();
    render(<SetupWizard />);
    await user.click(screen.getByText('Next →'));
    await user.click(screen.getByRole('button', { name: '← Back' }));
    expect(screen.getByText('Select Draft Mode')).toBeInTheDocument();
  });

  it('does not call navigate when going back from step 2 to step 1', async () => {
    const user = userEvent.setup();
    render(<SetupWizard />);
    await user.click(screen.getByText('Next →'));
    await user.click(screen.getByRole('button', { name: '← Back' }));
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});

describe('SetupWizard — progress bar', () => {
  it('shows checkmark for step 1 when on step 2', async () => {
    const user = userEvent.setup();
    render(<SetupWizard />);
    await user.click(screen.getByText('Next →'));
    expect(screen.getAllByText('✓')).toHaveLength(1);
  });

  it('shows two checkmarks when on step 3', async () => {
    const user = userEvent.setup();
    render(<SetupWizard />);
    await user.click(screen.getByText('Next →'));
    await user.click(screen.getByText('Next →'));
    expect(screen.getAllByText('✓')).toHaveLength(2);
  });

  it('allows clicking a completed step circle to jump back', async () => {
    const user = userEvent.setup();
    render(<SetupWizard />);
    await user.click(screen.getByText('Next →'));
    await user.click(screen.getByText('Next →'));
    // Now on step 3; step 1 circle shows ✓ and is clickable
    const checkmarks = screen.getAllByText('✓');
    await user.click(checkmarks[0]);
    expect(screen.getByText('Select Draft Mode')).toBeInTheDocument();
  });

  it('does not show Next button on step 5', async () => {
    const user = userEvent.setup();
    render(<SetupWizard />);
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByText('Next →'));
    }
    expect(screen.queryByText('Next →')).not.toBeInTheDocument();
  });
});
