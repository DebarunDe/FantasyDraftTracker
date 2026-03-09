export function LoadingSpinner({ label }: { label?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-secondary)' }}>
      <div className="spinner" />
      {label && <span>{label}</span>}
    </div>
  );
}
