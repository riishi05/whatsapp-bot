import { useEffect, useState } from "react";
import { getSessions, getThread } from "../api";
import api from "../api";

const STATUS_COLORS = {
  WAITING_FOR_BOT: "bg-gray-300 text-gray-700",
  AGENT_RESPONDING: "bg-yellow-200 text-yellow-800",
  RESOLVED: "bg-green-200 text-green-800",
  NEEDS_HUMAN: "bg-red-200 text-red-800",
};

function Bubble({ msg }) {
  const isBot = msg.sender === "bot";
  return (
    <div className={`flex ${isBot ? "justify-start" : "justify-end"} mb-2`}>
      <div
        className={`max-w-[70%] rounded-lg px-3 py-2 shadow text-sm ${
          isBot ? "bg-white" : "bg-wa-bubble"
        }`}
      >
        {msg.media && msg.media.mime_type?.startsWith("image/") && (
          <div className="mb-1 text-xs italic text-gray-500">🖼️ Image sent: {msg.media.url}</div>
        )}
        {msg.media && msg.media.mime_type === "application/pdf" && (
          <div className="mb-1 inline-block px-2 py-1 rounded bg-red-100 text-red-700 text-xs font-semibold">
            📄 PDF: {msg.media.filename || "document"}
          </div>
        )}
        {msg.text_content && <div>{msg.text_content}</div>}
        <div className="text-[10px] text-gray-400 mt-1 text-right">
          {new Date(msg.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}

export default function ChatMonitor({ tenantId }) {
  const [sessions, setSessions] = useState([]);
  const [activeNumber, setActiveNumber] = useState(null);
  const [thread, setThread] = useState([]);
  const [testInput, setTestInput] = useState("");
  const [testPhone, setTestPhone] = useState("test-user-1");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    setActiveNumber(null);
    setThread([]);
    const load = () => getSessions(tenantId).then(setSessions);
    load();
    const interval = setInterval(load, 4000); // simple polling for live updates
    return () => clearInterval(interval);
  }, [tenantId]);

  useEffect(() => {
    if (!activeNumber) return;
    const load = () => getThread(tenantId, activeNumber).then(setThread);
    load();
    const interval = setInterval(load, 3000);
    return () => clearInterval(interval);
  }, [tenantId, activeNumber]);

  const activeSession = sessions.find((s) => s.phone_number === activeNumber);

  // Chat is considered closed once the bot has resolved it — no more
  // messages should be sendable from the dashboard for that thread.
  const isChatClosed = activeSession?.status === "RESOLVED";

  const sendTestMessage = async () => {
    if (!testInput.trim() || sending) return;
    setSending(true);
    // switch view to this test phone number so the reply is visible immediately
    setActiveNumber(testPhone);
    const messageText = testInput;
    setTestInput("");
    try {
      await api.post("/dev/simulate-message", {
        tenant_id: tenantId,
        phone_number: testPhone,
        text: messageText,
      });
      // refresh session list + thread right away
      getSessions(tenantId).then(setSessions);
      getThread(tenantId, testPhone).then(setThread);
    } finally {
      setSending(false);
    }
  };

  const [threadInput, setThreadInput] = useState("");
  const [threadSending, setThreadSending] = useState(false);

  const sendToActiveThread = async () => {
    if (!threadInput.trim() || threadSending || !activeNumber || isChatClosed) return;
    setThreadSending(true);
    const messageText = threadInput;
    setThreadInput("");
    try {
      await api.post("/dev/simulate-message", {
        tenant_id: tenantId,
        phone_number: activeNumber,
        text: messageText,
      });
      getSessions(tenantId).then(setSessions);
      getThread(tenantId, activeNumber).then(setThread);
    } finally {
      setThreadSending(false);
    }
  };

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* Session list */}
      <div className="w-80 border-r bg-white overflow-y-auto flex flex-col">
        {/* Test Chat box — bypasses WhatsApp entirely, runs the LangGraph agent directly */}
        <div className="p-3 border-b bg-yellow-50">
          <div className="text-xs font-semibold text-yellow-800 mb-2">🧪 Test Chat (no WhatsApp needed)</div>
          <input
            value={testPhone}
            onChange={(e) => setTestPhone(e.target.value)}
            placeholder="test phone / id"
            className="w-full border rounded px-2 py-1 text-xs mb-2"
          />
          <div className="flex gap-1">
            <input
              value={testInput}
              onChange={(e) => setTestInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendTestMessage()}
              placeholder="Type a message…"
              className="flex-1 border rounded px-2 py-1 text-xs"
            />
            <button
              onClick={sendTestMessage}
              disabled={sending}
              className="bg-wa-green text-white px-3 rounded text-xs font-medium disabled:opacity-50"
            >
              {sending ? "…" : "Send"}
            </button>
          </div>
        </div>

        {sessions.length === 0 && (
          <div className="p-4 text-sm text-gray-400">No active conversations yet.</div>
        )}
        {sessions.map((s) => (
          <button
            key={s.phone_number}
            onClick={() => setActiveNumber(s.phone_number)}
            className={`w-full text-left p-3 border-b hover:bg-gray-50 ${
              s.phone_number === activeNumber ? "bg-gray-100" : ""
            }`}
          >
            <div className="flex justify-between items-center">
              <span className="font-medium text-sm">{s.phone_number}</span>
              {s.is_typing && <span className="text-xs text-wa-green animate-pulse">typing…</span>}
            </div>
            <span
              className={`inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full ${
                STATUS_COLORS[s.status] || "bg-gray-200"
              }`}
            >
              {s.status}
            </span>
          </button>
        ))}
      </div>

      {/* Thread view */}
      <div className="flex-1 flex flex-col bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] bg-gray-50">
        {activeNumber ? (
          <>
            <div className="p-3 bg-wa-teal text-white flex justify-between items-center">
              <span className="font-medium">{activeNumber}</span>
              {(activeSession?.is_typing || sending) && (
                <span className="text-xs italic animate-pulse">bot is typing…</span>
              )}
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {thread.map((m, i) => (
                <Bubble key={i} msg={m} />
              ))}
            </div>

            {isChatClosed ? (
              <div className="p-3 bg-gray-100 border-t text-center text-xs text-gray-500 font-medium">
                🔒 This chat has been closed — no further messages can be sent.
              </div>
            ) : (
              <div className="p-3 bg-white border-t flex gap-2">
                <input
                  value={threadInput}
                  onChange={(e) => setThreadInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendToActiveThread()}
                  placeholder={`Message ${activeNumber}…`}
                  className="flex-1 border rounded-full px-4 py-2 text-sm"
                />
                <button
                  onClick={sendToActiveThread}
                  disabled={threadSending}
                  className="bg-wa-green text-white px-5 rounded-full text-sm font-medium disabled:opacity-50"
                >
                  {threadSending ? "…" : "Send"}
                </button>
              </div>
            )}
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
            Select a conversation, or use Test Chat on the left to try the bot instantly
          </div>
        )}
      </div>
    </div>
  );
}