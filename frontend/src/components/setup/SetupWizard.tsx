import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createDraft } from '../../api/drafts';
import type { CreateDraftRequest, DraftMode, PickTradeInput, ScoringFormat } from '../../types/draft';
import { StepConfirm } from './StepConfirm';
import { StepDraftMode } from './StepDraftMode';
import { StepLeagueConfig } from './StepLeagueConfig';
import { StepPickTrades } from './StepPickTrades';
import { StepTeamNames } from './StepTeamNames';

const DEFAULT_ROSTER_SLOTS: Record<string, number> = {
  QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, DST: 1, K: 1, BENCH: 6,
};

function generateSnakeOrder(leagueSize: number, totalRounds: number): number[][] {
  const order: number[][] = [];
  for (let rnd = 1; rnd <= totalRounds; rnd++) {
    if (rnd % 2 === 1) {
      order.push(Array.from({ length: leagueSize }, (_, i) => i));
    } else {
      order.push(Array.from({ length: leagueSize }, (_, i) => leagueSize - 1 - i));
    }
  }
  return order;
}

type Step = 1 | 2 | 3 | 4 | 5;

export function SetupWizard() {
  const navigate = useNavigate();

  const [step, setStep] = useState<Step>(1);
  const [draftMode, setDraftMode] = useState<DraftMode>('simulation');
  const [leagueSize, setLeagueSize] = useState(12);
  const [scoringFormat, setScoringFormat] = useState<ScoringFormat>('half_ppr');
  const [rosterSlots, setRosterSlots] = useState<Record<string, number>>(DEFAULT_ROSTER_SLOTS);
  const [pickClockSeconds, setPickClockSeconds] = useState<number | null>(null);
  const [teamNames, setTeamNames] = useState<string[]>(
    Array.from({ length: 12 }, (_, i) => `Team ${i + 1}`),
  );
  const [humanTeamId, setHumanTeamId] = useState(0);
  const [pickTrades, setPickTrades] = useState<PickTradeInput[]>([]);
  const [draftOrder, setDraftOrder] = useState<number[][]>(
    generateSnakeOrder(12, Object.values(DEFAULT_ROSTER_SLOTS).reduce((a, b) => a + b, 0)),
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const totalRounds = Object.values(rosterSlots).reduce((a, b) => a + b, 0);

  // Sync team names when league size changes
  const handleLeagueConfigChange = (cfg: { leagueSize: number; scoringFormat: ScoringFormat; rosterSlots: Record<string, number>; pickClockSeconds: number | null }) => {
    const newSize = cfg.leagueSize;
    setLeagueSize(newSize);
    setScoringFormat(cfg.scoringFormat);
    setRosterSlots(cfg.rosterSlots);
    setPickClockSeconds(cfg.pickClockSeconds);
    const newRounds = Object.values(cfg.rosterSlots).reduce((a, b) => a + b, 0);
    setDraftOrder(generateSnakeOrder(newSize, newRounds));
    setTeamNames((prev) =>
      Array.from({ length: newSize }, (_, i) => prev[i] ?? `Team ${i + 1}`),
    );
    if (humanTeamId >= newSize) setHumanTeamId(0);
  };

  const handleSubmit = async () => {
    setError('');
    setLoading(true);
    try {
      const names =
        teamNames.length === leagueSize
          ? teamNames
          : Array.from({ length: leagueSize }, (_, i) => teamNames[i] ?? `Team ${i + 1}`);

      const req: CreateDraftRequest = {
        draft_mode: draftMode,
        league_size: leagueSize,
        scoring_format: scoringFormat,
        roster_slots: rosterSlots,
        team_names: names,
        human_team_id: humanTeamId,
        data_year: 2025,
        pick_trades: pickTrades,
        pick_clock_seconds: draftMode === 'manual_tracker' ? null : pickClockSeconds,
      };
      const draft = await createDraft(req);
      navigate(`/draft/${draft.draft_id}`);
    } catch (e: unknown) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        String(e);
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  const stepTitles = ['Mode', 'League', 'Teams', 'Trades', 'Confirm'];

  return (
    <div style={{ maxWidth: 700, margin: '0 auto', padding: '32px 16px' }}>
      {/* Progress bar */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 32 }}>
        {stepTitles.map((title, i) => {
          const s = (i + 1) as Step;
          const active = step === s;
          const done = step > s;
          return (
            <div key={i} style={{ flex: 1, textAlign: 'center', position: 'relative' }}>
              <div
                style={{
                  width: 28, height: 28, borderRadius: '50%', margin: '0 auto 4px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: done ? 'var(--success)' : active ? 'var(--accent)' : 'var(--bg-hover)',
                  color: 'white', fontWeight: 700, fontSize: 13,
                  cursor: done ? 'pointer' : 'default',
                }}
                onClick={() => done && setStep(s)}
              >
                {done ? '✓' : i + 1}
              </div>
              <div style={{ fontSize: 11, color: active ? 'var(--text-primary)' : 'var(--text-muted)' }}>
                {title}
              </div>
              {i < stepTitles.length - 1 && (
                <div style={{
                  position: 'absolute', top: 14, left: '50%', width: '100%',
                  height: 2, background: done ? 'var(--success)' : 'var(--border)',
                  zIndex: -1,
                }} />
              )}
            </div>
          );
        })}
      </div>

      {/* Step content */}
      <div className="card" style={{ minHeight: 360 }}>
        {step === 1 && <StepDraftMode value={draftMode} onChange={setDraftMode} />}
        {step === 2 && (
          <StepLeagueConfig
            value={{ leagueSize, scoringFormat, rosterSlots, pickClockSeconds }}
            onChange={handleLeagueConfigChange}
            draftMode={draftMode}
          />
        )}
        {step === 3 && (
          <StepTeamNames
            leagueSize={leagueSize}
            humanTeamId={humanTeamId}
            value={teamNames}
            onNamesChange={setTeamNames}
            onHumanTeamChange={setHumanTeamId}
          />
        )}
        {step === 4 && (
          <StepPickTrades
            leagueSize={leagueSize}
            teamNames={teamNames.slice(0, leagueSize)}
            totalRounds={totalRounds}
            value={pickTrades}
            draftOrder={draftOrder}
            humanTeamId={humanTeamId}
            onChange={(trades, order) => { setPickTrades(trades); setDraftOrder(order); }}
          />
        )}
        {step === 5 && (
          <StepConfirm
            config={{
              draft_mode: draftMode,
              league_size: leagueSize,
              scoring_format: scoringFormat,
              roster_slots: rosterSlots,
              team_names: teamNames.slice(0, leagueSize),
              human_team_id: humanTeamId,
              data_year: 2025,
              pick_trades: pickTrades,
              pick_clock_seconds: draftMode === 'manual_tracker' ? null : pickClockSeconds,
            }}
            onSubmit={handleSubmit}
            loading={loading}
          />
        )}
        {error && <p className="error-text" style={{ marginTop: 12 }}>{error}</p>}
      </div>

      {/* Navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
        <button
          className="secondary"
          onClick={() => step === 1 ? navigate('/') : setStep((s) => (s - 1) as Step)}
        >
          {step === 1 ? '← Home' : '← Back'}
        </button>
        {step < 5 && (
          <button className="primary" onClick={() => setStep((s) => Math.min(5, s + 1) as Step)}>
            Next →
          </button>
        )}
      </div>
    </div>
  );
}
