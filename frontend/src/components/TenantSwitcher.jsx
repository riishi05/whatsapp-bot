export default function TenantSwitcher({ tenants, activeTenantId, onSwitch }) {
  return (
    <div className="flex gap-2 p-3 bg-wa-dark">
      {tenants.map((t) => (
        <button
          key={t.tenant_id}
          onClick={() => onSwitch(t.tenant_id)}
          className={`px-4 py-2 rounded-full text-sm font-medium transition ${
            t.tenant_id === activeTenantId
              ? "bg-wa-green text-white"
              : "bg-white/10 text-white hover:bg-white/20"
          }`}
        >
          {t.name}
        </button>
      ))}
    </div>
  );
}
