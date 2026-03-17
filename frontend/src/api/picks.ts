import client from './client';
import type {
  PickResponse,
  PlayerResponse,
  RecommendationResponse,
} from '../types/draft';

export const makePick = (
  draftId: string,
  teamId: number,
  playerId: string,
): Promise<PickResponse> =>
  client
    .post<PickResponse>(`/drafts/${draftId}/picks`, {
      team_id: teamId,
      player_id: playerId,
    })
    .then((r) => r.data);

export const getPlayers = (
  draftId: string,
  position?: string,
  limit = 50,
  offset = 0,
  name?: string,
): Promise<PlayerResponse[]> =>
  client
    .get<PlayerResponse[]>(`/drafts/${draftId}/players`, {
      params: { position, limit, offset, name },
    })
    .then((r) => r.data);

export const getRecommendations = (
  draftId: string,
): Promise<RecommendationResponse[]> =>
  client
    .get<RecommendationResponse[]>(`/drafts/${draftId}/recommendations`)
    .then((r) => r.data);

export const getRoster = (draftId: string, teamId: number) =>
  client.get(`/drafts/${draftId}/roster/${teamId}`).then((r) => r.data);
