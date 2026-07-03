import { useEffect, useState } from "react";
import TenantSwitcher from "./components/TenantSwitcher.jsx";
import ChatMonitor from "./components/ChatMonitor.jsx";
import BroadcastDrawer from "./components/BroadcastDrawer.jsx";
import { getTenants } from "./api";

export default function App() {
  const [tenants, setTenants] = useState([]);
  const [activeTenantId, setActiveTenantId] = useState(null);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    getTenants().then((data) => {
      setTenants(data);
      if (data.length) setActiveTenantId(data[0].tenant_id);
    });
  }, []);

  return (
    <div className="h-screen flex flex-col">
      <header className="flex items-center justify-between bg-wa-dark px-4 h-16">
        <div className="flex items-center gap-4">
          <h1 className="text-white font-bold text-lg">WA Agent Dashboard</h1>
          <TenantSwitcher tenants={tenants} activeTenantId={activeTenantId} onSwitch={setActiveTenantId} />
        </div>
        <button
          onClick={() => setDrawerOpen(true)}
          className="bg-wa-green text-white px-4 py-2 rounded-full text-sm font-medium"
        >
          📣 Broadcast
        </button>
      </header>

      {activeTenantId && <ChatMonitor tenantId={activeTenantId} />}

      <BroadcastDrawer tenantId={activeTenantId} open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </div>
  );
}
