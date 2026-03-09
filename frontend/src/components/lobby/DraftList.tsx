import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { deleteDraft, listDrafts } from '../../api/drafts';
import type { SavedDraftMeta } from '../../types/draft';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { DraftCard } from './DraftCard';

export function DraftList() {
  const [drafts, setDrafts] = useState<SavedDraftMeta[]>([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const load = () => {
    setLoading(true);
    listDrafts()
      .then(setDrafts)
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this draft?')) return;
    await deleteDraft(id);
    load();
  };

  if (loading) return <LoadingSpinner label="Loading saved drafts…" />;

  if (drafts.length === 0) {
    return <p style={{ color: 'var(--text-muted)' }}>No saved drafts found.</p>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {drafts.map((d) => (
        <DraftCard
          key={d.draft_id}
          meta={d}
          onResume={(id) => navigate(`/draft/${id}`)}
          onDelete={handleDelete}
        />
      ))}
    </div>
  );
}
