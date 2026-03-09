import client from './client';
import type {
  CreateDraftRequest,
  DraftSummary,
  SavedDraftMeta,
} from '../types/draft';

export const createDraft = (body: CreateDraftRequest): Promise<DraftSummary> =>
  client.post<DraftSummary>('/drafts', body).then((r) => r.data);

export const listDrafts = (): Promise<SavedDraftMeta[]> =>
  client.get<SavedDraftMeta[]>('/drafts').then((r) => r.data);

export const getDraft = (draftId: string): Promise<DraftSummary> =>
  client.get<DraftSummary>(`/drafts/${draftId}`).then((r) => r.data);

export const deleteDraft = (draftId: string): Promise<void> =>
  client.delete(`/drafts/${draftId}`).then(() => undefined);

export const advanceDraft = (draftId: string): Promise<void> =>
  client.post(`/drafts/${draftId}/advance`).then(() => undefined);

export const simulateDraft = (draftId: string): Promise<void> =>
  client.post(`/drafts/${draftId}/sim`).then(() => undefined);

export const exportDraft = (draftId: string): void => {
  window.open(`/api/drafts/${draftId}/export`, '_blank');
};
