import { useCallback, useEffect, useRef, useState } from 'react';
import { advanceDraft, getDraft } from '../api/drafts';
import { getPlayers, getRecommendations, makePick } from '../api/picks';
import type {
  DraftSummary,
  PlayerResponse,
  RecommendationResponse,
  WsComputerThinkingEvent,
  WsEvent,
} from '../types/draft';
import { useWebSocket } from './useWebSocket';

interface UseDraftResult {
  draft: DraftSummary | null;
  players: PlayerResponse[];
  recommendations: RecommendationResponse[];
  computerThinking: WsComputerThinkingEvent | null;
  newlyAddedPickNumber: number | null;
  wsStatus: string;
  error: string | null;
  clearError: () => void;
  pickPlayer: (playerId: string) => Promise<void>;
  refreshPlayers: (position?: string) => void;
  refreshRecommendations: () => void;
}

export function useDraft(draftId: string | null): UseDraftResult {
  const [draft, setDraft] = useState<DraftSummary | null>(null);
  const [players, setPlayers] = useState<PlayerResponse[]>([]);
  const [recommendations, setRecommendations] = useState<RecommendationResponse[]>([]);
  const [computerThinking, setComputerThinking] = useState<WsComputerThinkingEvent | null>(null);
  const [newlyAddedPickNumber, setNewlyAddedPickNumber] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const currentPositionFilter = useRef<string | undefined>(undefined);

  const { status: wsStatus, eventQueue, eventTick } = useWebSocket(draftId);

  // Initial load (fast path — don't call advanceDraft yet; WS may not be open)
  useEffect(() => {
    if (!draftId) return;
    getDraft(draftId).then(setDraft).catch((e) => setError(String(e)));
  }, [draftId]);

  // On WS (re)connect: refresh full draft state (catches any missed picks) then
  // fire the computer chain if it's a computer's turn.
  useEffect(() => {
    if (!draftId || wsStatus !== 'open') return;
    getDraft(draftId)
      .then((d) => {
        // Functional merge: prefer whichever state has more picks to avoid
        // overwriting picks that arrived via WS between the getDraft call and now.
        setDraft((prev) => {
          if (prev && prev.all_picks.length > d.all_picks.length) {
            return { ...d, all_picks: prev.all_picks };
          }
          return d;
        });
        if (
          !d.is_complete &&
          d.league_config.draft_mode === 'simulation' &&
          !d.teams[d.current_team_id]?.is_human
        ) {
          advanceDraft(draftId).catch(() => {});
        }
      })
      .catch(() => {});
  }, [wsStatus, draftId]);

  // Fetch players whenever draft changes
  useEffect(() => {
    if (!draft) return;
    refreshPlayers(currentPositionFilter.current);
  }, [draft?.current_pick]);

  // Fetch recommendations: always in manual_tracker (every pick slot matters),
  // otherwise only on human turns.
  useEffect(() => {
    if (!draft || draft.is_complete) return;
    const isManual = draft.league_config.draft_mode === 'manual_tracker';
    const currentTeam = draft.teams[draft.current_team_id];
    if (isManual || currentTeam?.is_human) {
      refreshRecommendations();
    }
  }, [draft?.current_pick]);

  // Handle WebSocket events — drain the entire queue so no events are dropped
  // even when React batches multiple setEventTick calls into one render.
  useEffect(() => {
    const events: WsEvent[] = eventQueue.current.splice(0);
    for (const event of events) {
      if (event.type === 'pick_made') {
        setComputerThinking(null);
        setNewlyAddedPickNumber(event.pick.pick_number);
        // Use the authoritative all_picks from the event — no manual accumulation.
        setDraft((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            all_picks: event.draft_state.all_picks,
            current_pick: event.draft_state.current_pick,
            current_round: event.draft_state.current_round,
            current_team_id: event.draft_state.current_team_id,
            is_complete: event.draft_state.is_complete,
            completed_at: event.draft_state.completed_at,
          };
        });
        setTimeout(() => setNewlyAddedPickNumber(null), 500);
      } else if (event.type === 'computer_thinking') {
        setComputerThinking(event);
      } else if (event.type === 'draft_complete') {
        setComputerThinking(null);
        setDraft(event.summary);
      }
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [eventTick]);

  const refreshPlayers = useCallback(
    (position?: string) => {
      if (!draftId) return;
      currentPositionFilter.current = position;
      getPlayers(draftId, position).then(setPlayers).catch(() => {});
    },
    [draftId],
  );

  const refreshRecommendations = useCallback(() => {
    if (!draftId) return;
    getRecommendations(draftId).then(setRecommendations).catch(() => {});
  }, [draftId]);

  const pickPlayer = useCallback(
    async (playerId: string) => {
      if (!draftId || !draft) return;
      try {
        await makePick(draftId, draft.current_team_id, playerId);
      } catch (e: unknown) {
        const msg =
          (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
          String(e);
        setError(msg);
      }
    },
    [draftId, draft],
  );

  return {
    draft,
    players,
    recommendations,
    computerThinking,
    newlyAddedPickNumber,
    wsStatus,
    error,
    clearError: () => setError(null),
    pickPlayer,
    refreshPlayers,
    refreshRecommendations,
  };
}
