import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { exportDraft } from '../../api/drafts';
import { getRoster } from '../../api/picks';
import type { DraftSummary, PickResponse, RosterPlayer, TeamRosterData } from '../../types/draft';
import { PositionBadge } from '../common/PositionBadge';
import { DraftGrid } from './DraftGrid';

type Tab = 'board' | 'rosters' | 'compare' | 'picks';

interface Props {
  draft: DraftSummary;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SLOT_ORDER = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'K', 'DST', 'BENCH'];

function starterPoints(roster: Record<string, RosterPlayer[]>): number {
  return Object.entries(roster)
    .filter(([slot]) => slot !== 'BENCH')
    .flatMap(([, players]) => players)
    .reduce((sum, p) => sum + p.projected_points, 0);
}

function totalPoints(roster: Record<string, RosterPlayer[]>): number {
  return Object.values(roster).flatMap((p) => p).reduce((sum, p) => sum + p.projected_points, 0);
}

function slotPoints(roster: Record<string, RosterPlayer[]>, slot: string): number {
  return (roster[slot] ?? []).reduce((s, p) => s + p.projected_points, 0);
}

// ---------------------------------------------------------------------------
// Root screen
// ---------------------------------------------------------------------------

export function PostDraftScreen({ draft }: Props) {
  const navigate = useNavigate();
  const [tab, setTab] = useState<Tab>('board');
  const [allRosters, setAllRosters] = useState<TeamRosterData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchAll() {
      const results: TeamRosterData[] = await Promise.all(
        draft.teams.map((t) => getRoster(draft.draft_id, t.team_id)),
      );
      setAllRosters(results);
      setLoading(false);
    }
    fetchAll();
  }, [draft.draft_id, draft.teams]);

  const humanTeamId = draft.teams.find((t) => t.is_human)?.team_id ?? -1;

  const tabs: { key: Tab; label: string }[] = [
    { key: 'board', label: 'Draft Board' },
    { key: 'rosters', label: 'Rosters' },
    { key: 'compare', label: 'League Compare' },
    { key: 'picks', label: 'Pick Quality' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden', background: 'var(--bg-primary)' }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 0,
        borderBottom: '1px solid var(--border)', background: 'var(--bg-secondary)',
        padding: '0 12px', flexShrink: 0,
      }}>
        {/* Draft complete badge */}
        <span style={{
          fontSize: 11, fontWeight: 700, color: 'var(--success)',
          marginRight: 16, padding: '4px 8px',
          background: 'rgba(34,197,94,0.1)', borderRadius: 4,
          border: '1px solid rgba(34,197,94,0.3)',
          whiteSpace: 'nowrap',
        }}>
          DRAFT COMPLETE
        </span>

        {/* Tabs */}
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            style={{
              padding: '12px 14px',
              fontSize: 13,
              fontWeight: tab === key ? 700 : 400,
              background: 'transparent',
              border: 'none',
              borderBottom: tab === key ? '2px solid var(--accent)' : '2px solid transparent',
              color: tab === key ? 'var(--accent)' : 'var(--text-secondary)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {label}
          </button>
        ))}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Actions */}
        <button
          className="secondary"
          onClick={() => exportDraft(draft.draft_id)}
          style={{ fontSize: 12, padding: '4px 12px', marginRight: 8 }}
        >
          Export CSV
        </button>
        <button
          className="secondary"
          onClick={() => navigate('/')}
          style={{ fontSize: 12, padding: '4px 12px' }}
        >
          ← Home
        </button>
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {tab === 'board' && <BoardTab draft={draft} />}
        {tab === 'rosters' && <RostersTab allRosters={allRosters} loading={loading} humanTeamId={humanTeamId} />}
        {tab === 'compare' && <CompareTab allRosters={allRosters} loading={loading} humanTeamId={humanTeamId} />}
        {tab === 'picks' && <PickQualityTab draft={draft} humanTeamId={humanTeamId} />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Board tab — existing draft grid, full width
// ---------------------------------------------------------------------------

function BoardTab({ draft }: { draft: DraftSummary }) {
  return (
    <div style={{ height: '100%', overflow: 'auto', padding: 12 }}>
      <DraftGrid draft={draft} newlyAddedPickNumber={null} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Rosters tab
// ---------------------------------------------------------------------------

function RostersTab({
  allRosters,
  loading,
  humanTeamId,
}: {
  allRosters: TeamRosterData[];
  loading: boolean;
  humanTeamId: number;
}) {
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // Default to human team once loaded
  useEffect(() => {
    if (!loading && selectedId === null) {
      setSelectedId(humanTeamId >= 0 ? humanTeamId : allRosters[0]?.team_id ?? 0);
    }
  }, [loading, humanTeamId, allRosters, selectedId]);

  if (loading) return <Spinner />;

  const teamData = allRosters.find((r) => r.team_id === selectedId);

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Team list sidebar */}
      <div style={{
        width: 180, borderRight: '1px solid var(--border)',
        overflowY: 'auto', padding: '8px 0', flexShrink: 0,
      }}>
        {allRosters.map((r) => {
          const sPts = starterPoints(r.roster);
          const isSelected = r.team_id === selectedId;
          return (
            <div
              key={r.team_id}
              onClick={() => setSelectedId(r.team_id)}
              style={{
                padding: '7px 12px', cursor: 'pointer',
                background: isSelected ? 'var(--bg-secondary)' : 'transparent',
                borderLeft: isSelected ? '3px solid var(--accent)' : '3px solid transparent',
              }}
            >
              <div style={{
                fontSize: 12, fontWeight: isSelected ? 700 : 400,
                color: r.team_id === humanTeamId ? 'var(--accent)' : 'var(--text-primary)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {r.team_name}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 1 }}>
                {sPts.toFixed(1)} starter pts
              </div>
            </div>
          );
        })}
      </div>

      {/* Roster detail */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {teamData && <RosterDetail teamData={teamData} />}
      </div>
    </div>
  );
}

function RosterDetail({ teamData }: { teamData: TeamRosterData }) {
  const { roster, team_name, is_human } = teamData;
  const sPts = starterPoints(roster);
  const tPts = totalPoints(roster);

  const orderedSlots = [
    ...SLOT_ORDER.filter((s) => s in roster),
    ...Object.keys(roster).filter((s) => !SLOT_ORDER.includes(s)),
  ];

  return (
    <div style={{ maxWidth: 640 }}>
      {/* Team header */}
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: is_human ? 'var(--accent)' : 'var(--text-primary)' }}>
          {team_name}
          {is_human && <span style={{ fontSize: 11, marginLeft: 8, color: 'var(--text-muted)', fontWeight: 400 }}>Your team</span>}
        </h2>
        <div style={{ display: 'flex', gap: 24, marginTop: 8 }}>
          <Stat label="Projected Starters" value={`${sPts.toFixed(1)} pts`} highlight />
          <Stat label="Full Roster" value={`${tPts.toFixed(1)} pts`} />
        </div>
      </div>

      {/* Slot sections */}
      {orderedSlots.map((slot) => {
        const players = roster[slot] ?? [];
        if (players.length === 0) return null;
        const isBench = slot === 'BENCH';
        return (
          <div key={slot} style={{ marginBottom: 12 }}>
            <div style={{
              fontSize: 10, fontWeight: 700, color: 'var(--text-muted)',
              textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4,
              display: 'flex', justifyContent: 'space-between',
            }}>
              <span>{slot}</span>
              {!isBench && (
                <span style={{ color: 'var(--text-secondary)' }}>
                  {slotPoints(roster, slot).toFixed(1)} pts
                </span>
              )}
            </div>
            {players.map((p) => (
              <div key={p.player_id} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '6px 10px', marginBottom: 3,
                background: 'var(--bg-secondary)', borderRadius: 6,
                opacity: isBench ? 0.65 : 1,
              }}>
                <PositionBadge position={p.position} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.name}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                    {p.nfl_team}{p.bye_week != null ? ` · Bye ${p.bye_week}` : ''}
                  </div>
                </div>
                <div style={{ fontSize: 13, fontWeight: 700, color: isBench ? 'var(--text-muted)' : 'var(--text-primary)', flexShrink: 0 }}>
                  {p.projected_points.toFixed(1)}
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Compare tab — horizontal stacked position bars (Power Rankings style)
// ---------------------------------------------------------------------------

const BAR_SLOTS = ['QB', 'RB', 'WR', 'TE', 'FLEX', 'K', 'DST'] as const;
type BarSlot = typeof BAR_SLOTS[number];

const POS_COLOR: Record<BarSlot, string> = {
  QB:   '#ef4444',
  RB:   '#22c55e',
  WR:   '#3b82f6',
  TE:   '#f59e0b',
  FLEX: '#0ea5e9',
  K:    '#6b7280',
  DST:  '#a855f7',
};

const RANK_BG = ['#f59e0b', '#94a3b8', '#b45309'];  // gold, silver, bronze

function CompareTab({
  allRosters,
  loading,
  humanTeamId,
}: {
  allRosters: TeamRosterData[];
  loading: boolean;
  humanTeamId: number;
}) {
  if (loading) return <Spinner />;

  const ranked = [...allRosters]
    .map((r) => ({
      ...r,
      starterPts: starterPoints(r.roster),
      totalPts: totalPoints(r.roster),
      posPts: Object.fromEntries(BAR_SLOTS.map((s) => [s, slotPoints(r.roster, s)])) as Record<BarSlot, number>,
    }))
    .sort((a, b) => b.starterPts - a.starterPts);

  const maxStarter = ranked[0]?.starterPts ?? 1;

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '20px 24px' }}>
      {/* Header + legend */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>Power Rankings — Projected Points</h2>
        <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}>
          {BAR_SLOTS.map((pos) => (
            <div key={pos} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div style={{ width: 10, height: 10, borderRadius: 2, background: POS_COLOR[pos], flexShrink: 0 }} />
              <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontWeight: 600 }}>{pos}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Team rows */}
      {ranked.map((r, i) => {
        const isHuman = r.team_id === humanTeamId;
        const barFillPct = maxStarter > 0 ? (r.starterPts / maxStarter) * 100 : 0;

        return (
          <div
            key={r.team_id}
            style={{
              marginBottom: 18,
              padding: '12px 14px',
              background: isHuman ? 'rgba(59,130,246,0.06)' : 'var(--bg-secondary)',
              borderRadius: 8,
              border: isHuman ? '1px solid rgba(59,130,246,0.25)' : '1px solid var(--border)',
            }}
          >
            {/* Row header: rank + name + total pts */}
            <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8, gap: 10 }}>
              {/* Rank badge */}
              <div style={{
                width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: i < 3 ? RANK_BG[i] : 'var(--bg-hover)',
                fontSize: 11, fontWeight: 800,
                color: i < 3 ? '#0f172a' : 'var(--text-muted)',
              }}>
                {i + 1}
              </div>

              {/* Team name */}
              <span style={{
                flex: 1, fontSize: 14, fontWeight: isHuman ? 700 : 500,
                color: isHuman ? 'var(--accent)' : 'var(--text-primary)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {r.team_name}
                {isHuman && <span style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 400, marginLeft: 6 }}>You</span>}
              </span>

              {/* Total pts */}
              <span style={{ fontSize: 16, fontWeight: 800, color: i === 0 ? 'var(--success)' : 'var(--text-primary)', flexShrink: 0 }}>
                {r.starterPts.toFixed(1)}
                <span style={{ fontSize: 10, fontWeight: 400, color: 'var(--text-muted)', marginLeft: 3 }}>pts</span>
              </span>
            </div>

            {/* Stacked bar */}
            <div style={{ position: 'relative', height: 28, background: 'var(--bg-hover)', borderRadius: 5, overflow: 'hidden' }}>
              {/* Filled portion, scales to maxStarter */}
              <div style={{ display: 'flex', height: '100%', width: `${barFillPct}%`, minWidth: 4 }}>
                {BAR_SLOTS.map((pos) => {
                  const pts = r.posPts[pos];
                  const segPct = r.starterPts > 0 ? (pts / r.starterPts) * 100 : 0;
                  if (segPct < 0.5) return null;
                  const showLabel = segPct > 7;
                  return (
                    <div
                      key={pos}
                      style={{
                        width: `${segPct}%`,
                        background: POS_COLOR[pos],
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        overflow: 'hidden', flexShrink: 0,
                        borderRight: '1px solid rgba(0,0,0,0.15)',
                      }}
                      title={`${pos}: ${pts.toFixed(1)} pts`}
                    >
                      {showLabel && (
                        <span style={{ fontSize: 9, fontWeight: 800, color: 'rgba(255,255,255,0.95)', whiteSpace: 'nowrap' }}>
                          {pts.toFixed(0)}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Positional breakdown labels */}
            <div style={{ display: 'flex', gap: 14, marginTop: 6, flexWrap: 'wrap' }}>
              {BAR_SLOTS.map((pos) => {
                const pts = r.posPts[pos];
                if (pts <= 0) return null;
                return (
                  <div key={pos} style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                    <div style={{ width: 7, height: 7, borderRadius: 1, background: POS_COLOR[pos], flexShrink: 0 }} />
                    <span style={{ fontSize: 10, color: 'var(--text-secondary)' }}>
                      <span style={{ fontWeight: 700, color: POS_COLOR[pos] }}>{pos}</span>
                      {' '}{pts.toFixed(1)}
                    </span>
                  </div>
                );
              })}
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 3 }}>
                <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>Total roster</span>
                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-secondary)' }}>{r.totalPts.toFixed(1)}</span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pick Quality tab — reach/steal analysis per team
// ---------------------------------------------------------------------------

const LABEL_COLORS: Record<string, string> = {
  STEAL: 'var(--success)',
  Value: 'var(--success)',
  REACH: 'var(--danger)',
};

function PickQualityTab({ draft, humanTeamId }: { draft: DraftSummary; humanTeamId: number }) {
  const [selectedId, setSelectedId] = useState<number>(humanTeamId >= 0 ? humanTeamId : 0);

  // Team summary stats
  const teamStats = draft.teams.map((t) => {
    const teamPicks = draft.all_picks.filter((p) => p.team_id === t.team_id);
    const labelled = teamPicks.filter((p) => p.reach_label !== '');
    const steals = teamPicks.filter((p) => p.reach_label === 'STEAL' || p.reach_label === 'Value');
    const reaches = teamPicks.filter((p) => p.reach_label === 'REACH');
    const deltas = teamPicks.filter((p) => p.reach_delta != null).map((p) => p.reach_delta as number);
    const avgDelta = deltas.length > 0 ? deltas.reduce((s, d) => s + d, 0) / deltas.length : 0;
    return { team: t, teamPicks, labelled, steals, reaches, avgDelta };
  });

  const selectedStats = teamStats.find((s) => s.team.team_id === selectedId);
  const selectedPicks = selectedStats?.teamPicks ?? [];

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Team list sidebar */}
      <div style={{
        width: 200, borderRight: '1px solid var(--border)',
        overflowY: 'auto', padding: '8px 0', flexShrink: 0,
      }}>
        {teamStats.map(({ team, steals, reaches, avgDelta }) => {
          const isSelected = team.team_id === selectedId;
          return (
            <div
              key={team.team_id}
              onClick={() => setSelectedId(team.team_id)}
              style={{
                padding: '7px 12px', cursor: 'pointer',
                background: isSelected ? 'var(--bg-secondary)' : 'transparent',
                borderLeft: isSelected ? '3px solid var(--accent)' : '3px solid transparent',
              }}
            >
              <div style={{
                fontSize: 12, fontWeight: isSelected ? 700 : 400,
                color: team.team_id === humanTeamId ? 'var(--accent)' : 'var(--text-primary)',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {team.team_name}
              </div>
              <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
                <span style={{ fontSize: 10, color: 'var(--success)' }}>{steals.length} value</span>
                <span style={{ fontSize: 10, color: 'var(--danger)' }}>{reaches.length} reach</span>
                <span style={{ fontSize: 10, color: avgDelta > 5 ? 'var(--danger)' : avgDelta < -5 ? 'var(--success)' : 'var(--text-muted)' }}>
                  avg {avgDelta > 0 ? '+' : ''}{avgDelta.toFixed(1)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Pick detail */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
        {selectedStats && (
          <div style={{ maxWidth: 720 }}>
            <div style={{ display: 'flex', gap: 20, marginBottom: 20, flexWrap: 'wrap' }}>
              <Stat label="Total Picks" value={String(selectedPicks.length)} />
              <Stat label="Value / Steals" value={String(selectedStats.steals.length)} color="var(--success)" />
              <Stat label="Reaches" value={String(selectedStats.reaches.length)} color="var(--danger)" />
              <Stat
                label="Avg Pick Delta"
                value={`${selectedStats.avgDelta > 0 ? '+' : ''}${selectedStats.avgDelta.toFixed(1)}`}
                color={selectedStats.avgDelta > 5 ? 'var(--danger)' : selectedStats.avgDelta < -5 ? 'var(--success)' : undefined}
                note="picks ahead of rank (+) or behind (-)"
              />
            </div>

            <div style={{ marginBottom: 8, fontSize: 11, color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              All Picks
            </div>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  <th style={thStyle({ align: 'center', w: 40 })}>Pick</th>
                  <th style={thStyle({ align: 'left' })}>Player</th>
                  <th style={thStyle({ align: 'center', w: 50 })}>Pos</th>
                  <th style={thStyle({ align: 'center', w: 60 })}>Rank</th>
                  <th style={thStyle({ align: 'center', w: 70 })}>Delta</th>
                  <th style={thStyle({ align: 'center', w: 60 })}>Label</th>
                </tr>
              </thead>
              <tbody>
                {selectedPicks.map((pick) => (
                  <PickRow key={pick.pick_number} pick={pick} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function PickRow({ pick }: { pick: PickResponse }) {
  const labelColor = LABEL_COLORS[pick.reach_label] ?? 'var(--text-muted)';
  return (
    <tr style={{ borderBottom: '1px solid var(--border)' }}>
      <td style={tdStyle({ align: 'center' })}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>#{pick.pick_number}</span>
      </td>
      <td style={tdStyle({ align: 'left' })}>
        <div style={{ fontWeight: 600 }}>{pick.player_name}</div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{pick.nfl_team}</div>
      </td>
      <td style={tdStyle({ align: 'center' })}>
        <PositionBadge position={pick.position} />
      </td>
      <td style={tdStyle({ align: 'center' })}>
        {pick.reach_delta != null
          ? <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>#{pick.pick_number - pick.reach_delta}</span>
          : <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>—</span>}
      </td>
      <td style={tdStyle({ align: 'center' })}>
        {pick.reach_delta != null ? (
          <span style={{ fontSize: 11, fontWeight: 600, color: pick.reach_delta > 0 ? 'var(--danger)' : pick.reach_delta < 0 ? 'var(--success)' : 'var(--text-muted)' }}>
            {pick.reach_delta > 0 ? '+' : ''}{pick.reach_delta}
          </span>
        ) : (
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>—</span>
        )}
      </td>
      <td style={tdStyle({ align: 'center' })}>
        {pick.reach_label ? (
          <span style={{ fontSize: 10, fontWeight: 700, color: labelColor }}>{pick.reach_label}</span>
        ) : (
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>—</span>
        )}
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function Spinner() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', fontSize: 13 }}>
      Loading…
    </div>
  );
}

function Stat({ label, value, highlight, color, note }: { label: string; value: string; highlight?: boolean; color?: string; note?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
      <span style={{ fontSize: 20, fontWeight: 700, color: color ?? (highlight ? 'var(--success)' : 'var(--text-primary)') }}>{value}</span>
      {note && <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{note}</span>}
    </div>
  );
}

function thStyle({ align, w }: { align: 'left' | 'right' | 'center'; w?: number }): React.CSSProperties {
  return {
    textAlign: align,
    padding: '6px 8px',
    fontSize: 11,
    fontWeight: 600,
    color: 'var(--text-muted)',
    whiteSpace: 'nowrap',
    ...(w ? { width: w } : {}),
  };
}

function tdStyle({ align }: { align: 'left' | 'right' | 'center' }): React.CSSProperties {
  return {
    textAlign: align,
    padding: '7px 8px',
    verticalAlign: 'middle',
  };
}
