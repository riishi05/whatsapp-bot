import { useState } from "react";
import { sendBroadcast } from "../api";

export default function BroadcastDrawer({ tenantId, open, onClose }) {
  const [templateName, setTemplateName] = useState("new_catalog_promo");
  const [numbersRaw, setNumbersRaw] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const handleSend = async () => {
    setLoading(true);
    setResult(null);
    const phone_numbers = numbersRaw
      .split(",")
      .map((n) => n.trim())
      .filter(Boolean);
    try {
      const res = await sendBroadcast({
        tenant_id: tenantId,
        template_name: templateName,
        phone_numbers: phone_numbers.length ? phone_numbers : undefined,
      });
      setResult(res);
    } catch (e) {
      setResult({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex justify-end z-50">
      <div className="w-96 bg-white h-full p-5 shadow-xl overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="font-semibold text-lg">Broadcast Campaign</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            ✕
          </button>
        </div>

        <label className="block text-sm font-medium mb-1">Template</label>
        <select
          value={templateName}
          onChange={(e) => setTemplateName(e.target.value)}
          className="w-full border rounded p-2 mb-4 text-sm"
        >
          <option value="new_catalog_promo">Send New Catalog Promo</option>
          <option value="service_reminder">Service Reminder</option>
          <option value="seasonal_discount">Seasonal Discount</option>
        </select>

        <label className="block text-sm font-medium mb-1">
          Cohort — phone numbers (comma separated, blank = all active sessions)
        </label>
        <textarea
          value={numbersRaw}
          onChange={(e) => setNumbersRaw(e.target.value)}
          rows={3}
          placeholder="+919999999999, +918888888888"
          className="w-full border rounded p-2 mb-4 text-sm"
        />

        <button
          onClick={handleSend}
          disabled={loading}
          className="w-full bg-wa-green text-white py-2 rounded font-medium disabled:opacity-50"
        >
          {loading ? "Sending…" : "Send Broadcast"}
        </button>

        {result && (
          <div className="mt-4 text-sm">
            {result.error ? (
              <p className="text-red-600">{result.error}</p>
            ) : (
              <>
                <p className="text-green-700 mb-1">Sent: {result.sent}</p>
                <ul className="text-xs text-gray-600 space-y-1 max-h-48 overflow-y-auto">
                  {result.results.map((r, i) => (
                    <li key={i}>
                      {r.phone_number} — {r.status}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
