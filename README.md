# Multi-Tenant Agentic WhatsApp Orchestrator

An end-to-end multi-tenant WhatsApp AI Support & Sales Agent SaaS. Built with
**FastAPI + LangGraph + MongoDB (Motor)** on the backend and a **React +
Tailwind** monitoring dashboard on the frontend, containerized as a single
image for **GCP Cloud Run**.

---

## 1. Quick-Start: Environment Variables

Copy the example env file and fill in your own values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `MONGO_URI` | Mongo connection string (Atlas M0 or local) |
| `MONGO_DB_NAME` | Database name, defaults to `wa_agent` |
| `META_ACCESS_TOKEN` | Token from your Meta Developer App (temporary or permanent System User token) |
| `META_PHONE_NUMBER_ID` | The Phone Number ID of your WhatsApp Sandbox number |
| `META_APP_SECRET` | App Secret, used to validate `X-Hub-Signature-256` on inbound webhooks |
| `META_VERIFY_TOKEN` | Any string you choose — must match what you type into Meta's webhook verification form |
| `LLM_PROVIDER` | `anthropic` (default) or `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Your LLM provider key |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins for the dashboard |

---

## 2. Running the Stack Locally

### Option A — Docker Compose (closest to production)

```bash
docker compose up --build
```

This builds the React dashboard, bundles it into the FastAPI container, and
starts Mongo alongside it. The whole app (API + dashboard) is served at
`http://localhost:8080`.

Seed the two demo tenants once the container is up:

```bash
docker compose exec backend python -m app.seed
```

### Option B — Split dev mode (hot reload for frontend)

```bash
# Terminal 1 — Mongo
docker run -d -p 27017:27017 --name wa_mongo mongo:7

# Terminal 2 — Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed          # seed Tenant A / Tenant B
uvicorn app.main:app --reload --port 8000

# Terminal 3 — Frontend
cd frontend
npm install
npm run dev                 # http://localhost:5173, proxies /api -> :8000
```

### Exposing your local server to Meta (sandbox testing)

Meta needs a public HTTPS URL to deliver webhooks. Use `ngrok` (or `cloudflared`)
during local development:

```bash
ngrok http 8000     # (or 8080 if using docker compose)
```

Then in your Meta App dashboard → WhatsApp → Configuration:
- **Callback URL**: `https://<ngrok-id>.ngrok-free.app/api/webhooks/whatsapp`
- **Verify Token**: same value as `META_VERIFY_TOKEN` in your `.env`
- Subscribe to the `messages` webhook field.

---

## 3. LangGraph Architecture Breakdown

### State (`app/graph/state.py`)

A single `TypedDict` (`AgentState`) threads through every node. It carries:
- **Inbound context**: `tenant_id`, `phone_number`, `whatsapp_message_id`, `inbound_text`
- **Retrieved context** (filled by node 2): `tenant_prompt`, `media_library`, `history`, `whatsapp_phone_number_id`
- **Reasoning output** (filled by node 3): `response_type`, `response_text`, `media_url`, `media_filename`, `media_mime_type`, `sentiment_needs_human`

### Nodes (`app/graph/nodes.py`)

| Node | Responsibility |
|---|---|
| **Acknowledge** | Sends WhatsApp read receipt + typing indicator immediately; persists the inbound message; upserts the `ChatSession` to `AGENT_RESPONDING` |
| **Context Retriever** | Loads the tenant's system prompt + media library from Mongo; pulls the last 5 messages for that phone number as short-term memory |
| **LLM Reasoning** | Calls the configured LLM (Claude or GPT-4o) with a forced tool call (`reply`) so the model must return structured `response_type` / `response_text` / `media_keyword` / `needs_human` — no free-form parsing needed |
| **Dispatcher** | Sends the text/image/document via the WhatsApp client, logs the outbound message, and updates session status to `RESOLVED` or `NEEDS_HUMAN` (bonus: sentiment-based handover) |

### Edges

Linear pipeline, no branching required for the core flow:

```
Acknowledge → Context Retriever → LLM Reasoning → Dispatcher → END
```

`run_agent()` in `app/graph/graph.py` compiles this once at import time and
is invoked per-message as a FastAPI `BackgroundTask` (see Task 4 below), so
Meta's webhook always gets a fast `200 OK` while the graph runs asynchronously.

### Why a forced tool call instead of prompting for JSON?

Using the LLM's native tool-calling (Anthropic `tool_choice`, OpenAI
`function_call`) guarantees a parseable, schema-valid decision every time —
no regex/JSON-repair needed, and the "attach media only if it matches a real
keyword" guardrail is enforced in code (`llm_reasoning_node`) rather than
trusted blindly from the model.

---

## 4. Async Webhook Handling (Task 4)

`POST /api/webhooks/whatsapp`:
1. Validates `X-Hub-Signature-256` against `META_APP_SECRET` (bonus requirement).
2. Parses the inbound Meta payload.
3. Schedules `run_agent(...)` via FastAPI's `BackgroundTasks` — the request
   returns `200 OK` immediately, well under Meta's 3-second retry window, while
   the LangGraph pipeline (read receipt → typing → LLM → dispatch) runs after
   the response has already been sent.

`GET /api/webhooks/whatsapp` implements Meta's `hub.challenge` verification
handshake.

---

## 5. Frontend Dashboard (Task 5)

- **Tenant Switcher** — pill buttons in the header, toggles between Tenant A / B.
- **Live Chat Monitor** — left pane lists active phone numbers (polled every 4s)
  with a status pill (`WAITING_FOR_BOT` / `AGENT_RESPONDING` / `RESOLVED` /
  `NEEDS_HUMAN`) and a live "typing…" indicator; right pane renders a
  WhatsApp-style bubble thread, with 🖼️ image markers and 📄 PDF badges for
  media messages.
- **Broadcast Campaign Drawer** — pick a template + cohort (explicit numbers or
  all active sessions for the tenant) and fire a broadcast via
  `POST /api/broadcast`.

---

## 6. Deployment (Task 6 — GCP Cloud Run)

The root `Dockerfile` is a two-stage build: it compiles the React dashboard
first, then copies the static build into the FastAPI image so **one
container** serves both the API and the dashboard.

```bash
# Build & push
gcloud builds submit --tag gcr.io/<PROJECT_ID>/wa-agent

# Deploy
gcloud run deploy wa-agent \
  --image gcr.io/<PROJECT_ID>/wa-agent \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars MONGO_DB_NAME=wa_agent \
  --set-secrets MONGO_URI=mongo-uri:latest,META_ACCESS_TOKEN=meta-token:latest,META_APP_SECRET=meta-app-secret:latest,META_VERIFY_TOKEN=meta-verify-token:latest,ANTHROPIC_API_KEY=anthropic-key:latest
```

Store `MONGO_URI`, `META_ACCESS_TOKEN`, `META_APP_SECRET`, `META_VERIFY_TOKEN`,
and `ANTHROPIC_API_KEY` in **Secret Manager** (as referenced above) rather than
plain env vars in production.

After deploy, point Meta's webhook Callback URL to:
```
https://<your-cloud-run-url>/api/webhooks/whatsapp
```

The dashboard is served at the same root URL (`/`), so a single Cloud Run
service satisfies both the "admin dashboard" and "public backend webhook
handler" deliverables.

---

## 7. Project Structure

```
wa-agent/
├── Dockerfile                  # single-image build (frontend + backend)
├── docker-compose.yml          # local dev: mongo + backend
├── .env.example
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py             # FastAPI app, CORS, static mount
│       ├── config.py           # env-based settings
│       ├── database.py         # Motor client + collections + indexes
│       ├── models.py           # Tenant / ChatSession / MessageLog schemas
│       ├── whatsapp_client.py  # Meta Graph API helpers (Task 2)
│       ├── llm.py              # Anthropic/OpenAI tool-calling wrapper
│       ├── tenant_resolver.py  # phone_number_id -> tenant_id cache
│       ├── seed.py             # seeds Tenant A (furniture) & B (automotive)
│       ├── graph/
│       │   ├── state.py        # AgentState TypedDict
│       │   ├── nodes.py        # 4 LangGraph nodes (Task 3)
│       │   └── graph.py        # graph wiring + run_agent()
│       └── routers/
│           ├── webhook.py      # Task 4 - GET verify / POST async handler
│           ├── dashboard.py    # tenants/sessions/messages REST API
│           └── broadcast.py    # Task 5 - broadcast campaign endpoint
└── frontend/
    ├── index.html, vite.config.js, tailwind.config.js
    └── src/
        ├── App.jsx
        ├── api.js
        └── components/
            ├── TenantSwitcher.jsx
            ├── ChatMonitor.jsx
            └── BroadcastDrawer.jsx
```

---

## 8. Bonus Points Implemented

- ✅ **Webhook Security** — `X-Hub-Signature-256` HMAC validation (`webhook.py::_verify_signature`)
- ✅ **Fallback Handover** — LLM's `needs_human` flag flips session status to `NEEDS_HUMAN`, surfaced in red on the dashboard
- ⏳ **Inbound Media Parsing** — not implemented in this scaffold; the `MessageLog.media` field and `MessageDirection.INBOUND` model already support extending `context_retriever_node`/`llm_reasoning_node` with a multimodal describe-image step

---

## 9. Deliverables Checklist

1. **Source Code** — this repository.
2. **Deployed URLs** — add your live Cloud Run dashboard + webhook URL here after deploying.
3. **Documentation** — this README (env setup, local run, LangGraph breakdown, deployment).
4. **Demo Video** — record a 3–5 min Loom/YouTube walkthrough: Tenant A dashboard → send a WhatsApp message → typing indicator live on phone → bot replies with catalog/image → switch to Tenant B → show state/history changes on dashboard. Link it here.
