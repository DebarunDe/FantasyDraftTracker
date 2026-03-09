import { useState } from 'react';
import type { PickTradeInput } from '../../types/draft';
import { DraftOrderPreview } from './DraftOrderPreview';

interface Props {
  leagueSize: number;
  teamNames: string[];
  totalRounds: number;
  value: PickTradeInput[];
  draftOrder: number[][];
  humanTeamId: number;
  onChange: (trades: PickTradeInput[], newOrder: number[][]) => void;
}

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

/** Apply a single one-directional pick transfer to a deep copy of the order. */
function applyOneSidedTrade(order: number[][], trade: PickTradeInput): number[][] | null {
  const round = order[trade.round - 1];
  if (!round) return null;
  const idx = round.indexOf(trade.from_team_id);
  if (idx === -1) return null;
  const newOrder = order.map((r) => [...r]);
  newOrder[trade.round - 1][idx] = trade.to_team_id;
  return newOrder;
}

export function StepPickTrades({ leagueSize, teamNames, totalRounds, value, draftOrder, humanTeamId, onChange }: Props) {
  // Bidirectional: Team A gives round aRound, Team B gives round bRound back.
  const [teamA, setTeamA] = useState(0);
  const [roundA, setRoundA] = useState(1);
  const [teamB, setTeamB] = useState(1);
  const [roundB, setRoundB] = useState(2);
  const [error, setError] = useState('');

  const addTrade = () => {
    setError('');

    if (teamA === teamB) {
      setError('Teams must be different.');
      return;
    }

    // Validate Team A owns their pick in round A
    const slotA = draftOrder[roundA - 1];
    if (!slotA || !slotA.includes(teamA)) {
      setError(`${teamNames[teamA] ?? `Team ${teamA + 1}`} does not own a pick in Round ${roundA}.`);
      return;
    }

    // Validate Team B owns their pick in round B
    const slotB = draftOrder[roundB - 1];
    if (!slotB || !slotB.includes(teamB)) {
      setError(`${teamNames[teamB] ?? `Team ${teamB + 1}`} does not own a pick in Round ${roundB}.`);
      return;
    }

    // Apply both halves atomically (same order as CLI: A→B first, then B→A)
    const tradeAtoB: PickTradeInput = { from_team_id: teamA, round: roundA, to_team_id: teamB };
    const tradeBtoA: PickTradeInput = { from_team_id: teamB, round: roundB, to_team_id: teamA };

    let newOrder = applyOneSidedTrade(draftOrder, tradeAtoB);
    if (!newOrder) { setError('Unexpected error applying trade.'); return; }
    newOrder = applyOneSidedTrade(newOrder, tradeBtoA);
    if (!newOrder) { setError('Unexpected error applying trade.'); return; }

    onChange([...value, tradeAtoB, tradeBtoA], newOrder);
  };

  /** Remove a swap pair by the index of its first half (always even). */
  const removeSwap = (pairStartIdx: number) => {
    // Trades are stored in pairs; remove both halves.
    const newTrades = value.filter((_, idx) => idx !== pairStartIdx && idx !== pairStartIdx + 1);
    // Rebuild order from scratch with remaining trades.
    let order = generateSnakeOrder(leagueSize, totalRounds);
    for (const t of newTrades) {
      const result = applyOneSidedTrade(order, t);
      if (result) order = result;
    }
    onChange(newTrades, order);
  };

  const teams = Array.from({ length: leagueSize }, (_, i) => i);
  const rounds = Array.from({ length: totalRounds }, (_, i) => i + 1);

  // Build display pairs from the flat list (every 2 entries = 1 swap)
  const swapPairs: { aToB: PickTradeInput; bToA: PickTradeInput; pairIdx: number }[] = [];
  for (let i = 0; i + 1 < value.length; i += 2) {
    swapPairs.push({ aToB: value[i], bToA: value[i + 1], pairIdx: i });
  }

  const teamLabel = (id: number) => teamNames[id] ?? `Team ${id + 1}`;

  return (
    <div>
      <h2 style={{ marginBottom: 8, fontSize: 20 }}>Pre-Draft Pick Trades</h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: 4, fontSize: 13 }}>
        Optional. Each trade is a two-way swap — both teams exchange picks to keep totals equal.
      </p>
      <p style={{ color: 'var(--text-muted)', marginBottom: 20, fontSize: 12 }}>
        Example: Team A gives Rd 1 → Team B gives Rd 3 back. Each team still drafts the same number of players.
      </p>

      {/* Two-sided input row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr auto 1fr auto',
          gap: 8,
          alignItems: 'end',
          marginBottom: 12,
        }}
      >
        {/* Left side: Team A + Round A */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div>
            <div className="label">Team A gives…</div>
            <select value={teamA} onChange={(e) => setTeamA(Number(e.target.value))}>
              {teams.map((i) => <option key={i} value={i}>{teamLabel(i)}</option>)}
            </select>
          </div>
          <div>
            <div className="label">Round A</div>
            <select value={roundA} onChange={(e) => setRoundA(Number(e.target.value))}>
              {rounds.map((r) => <option key={r} value={r}>Round {r}</option>)}
            </select>
          </div>
        </div>

        {/* Swap symbol */}
        <div style={{ textAlign: 'center', fontSize: 22, paddingBottom: 4, color: 'var(--accent)' }}>
          ↔
        </div>

        {/* Right side: Team B + Round B */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div>
            <div className="label">Team B gives…</div>
            <select value={teamB} onChange={(e) => setTeamB(Number(e.target.value))}>
              {teams.map((i) => <option key={i} value={i}>{teamLabel(i)}</option>)}
            </select>
          </div>
          <div>
            <div className="label">Round B</div>
            <select value={roundB} onChange={(e) => setRoundB(Number(e.target.value))}>
              {rounds.map((r) => <option key={r} value={r}>Round {r}</option>)}
            </select>
          </div>
        </div>

        <button className="primary" onClick={addTrade} type="button" style={{ alignSelf: 'end' }}>
          + Add
        </button>
      </div>

      {error && <p className="error-text" style={{ marginBottom: 8 }}>{error}</p>}

      {/* Display applied swaps as pairs */}
      {swapPairs.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          <div className="label" style={{ marginBottom: 6 }}>Applied Trades</div>
          {swapPairs.map(({ aToB, bToA, pairIdx }) => (
            <div
              key={pairIdx}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '8px 10px', marginBottom: 6,
                background: 'var(--bg-hover)', borderRadius: 6,
              }}
            >
              <span style={{ flex: 1, fontSize: 13 }}>
                <strong>{teamLabel(aToB.from_team_id)}</strong> Rd {aToB.round}
                <span style={{ color: 'var(--accent)', margin: '0 8px' }}>↔</span>
                <strong>{teamLabel(bToA.from_team_id)}</strong> Rd {bToA.round}
              </span>
              <button
                className="danger"
                onClick={() => removeSwap(pairIdx)}
                type="button"
                style={{ padding: '2px 8px', fontSize: 12 }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      <DraftOrderPreview draftOrder={draftOrder} teamNames={teamNames} highlightTeamId={humanTeamId} />
    </div>
  );
}
