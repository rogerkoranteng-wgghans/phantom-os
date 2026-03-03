# Phantom OS

> Stop typing. Start commanding. Your computer, operated by voice and vision.

**Phantom OS** is an autonomous AI desktop agent powered by the Gemini Live API and Google ADK. It sees your screen in real-time, hears your voice, and operates your computer across any application — no keyboard required.

Built for the **Gemini Live Agent Challenge** (March 2026).
Qualifies for: **Live Agents** category + **UI Navigator** category.

---

## Architecture

```
┌─────────────────────┐     WebSocket      ┌──────────────────────────┐
│   Desktop Agent     │◄──────────────────►│   FastAPI Backend        │
│   (Python)          │  frames + audio    │   (Google Cloud Run)     │
│                     │  actions + voice   │                          │
│  • Screen capture   │                    │  • Gemini Live API       │
│  • Mic stream       │                    │  • ADK Multi-Agent       │
│  • Webcam emotion   │                    │  • Redis session bus     │
│  • Mouse/keyboard   │                    │  • Firestore memory      │
│  • HUD overlay      │                    │                          │
└─────────────────────┘                    └──────────────────────────┘
         │                                            │
         │                                ┌───────────▼──────────────┐
         │                                │   React Dashboard        │
         │                                │   (Vite + Tailwind)      │
         └────── REST/WS ─────────────────►                          │
                                          │  • Live action feed      │
                                          │  • Agent task graph      │
                                          │  • Memory browser        │
                                          │  • Workflow library      │
                                          └──────────────────────────┘
```

### Data Flow

```
User voice → Desktop Agent (mic capture)
           → WebSocket (audio chunks)
           → Backend (Gemini Live session)
           → Gemini 2.0 Flash Live (multimodal reasoning)
           → Action JSON → Safety Agent → Redis queue
           → WebSocket → Desktop Agent executes action
           → Screen capture → Backend → Gemini (visual feedback loop)
```

---

## Agent Swarm

| Agent | Role |
|---|---|
| **Phantom Core** | Gemini Live session, action parsing |
| **Orchestrator** | Task decomposition, DAG execution |
| **Safety** | Risk classification, confirmation flow |
| **Memory** | Episodic + semantic memory (Firestore) |
| **Research** | Web search with Google grounding |
| **Prediction** | Pre-stages next actions for low latency |
| **Workflow** | Records, stores, replays automation workflows |
| **Communication** | Drafts emails/messages in user's voice |

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11+ |
| Node.js | 18+ |
| Redis | 7+ (or Docker) |
| Docker + Compose | 24+ (optional, for one-command start) |
| Google Cloud SDK | latest (for deployment) |

Required accounts / keys:
- Gemini API key (from [Google AI Studio](https://aistudio.google.com))
- Google Cloud project with Firestore enabled (for memory persistence)

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Gemini API key from Google AI Studio |
| `GOOGLE_CLOUD_PROJECT` | Yes | GCP project ID for Firestore |
| `REDIS_URL` | Yes | Redis connection URL (default: `redis://localhost:6379`) |
| `FIRESTORE_EMULATOR_HOST` | No | Set to use local Firestore emulator (e.g. `localhost:8080`) |
| `VITE_BACKEND_URL` | No | Dashboard WebSocket base URL (default: `ws://localhost:8000`) |

Create a `.env` file in `backend/`:

```bash
GEMINI_API_KEY=your_key_here
GOOGLE_CLOUD_PROJECT=your_project_id
REDIS_URL=redis://localhost:6379
```

---

## Quick Start

### Option A — Docker Compose (recommended)

```bash
# Clone and enter the project
git clone https://github.com/your-org/phantom-os.git
cd phantom-os

# Create backend env file
cp backend/.env.example backend/.env
# Edit backend/.env and fill in GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT

# Start backend + Redis
docker compose up --build

# Backend is now at http://localhost:8000
# Redis is at localhost:6379
```

### Option B — Manual Setup

#### 1. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT, REDIS_URL
uvicorn main:app --reload --port 8000
```

#### 2. Desktop Agent

```bash
cd agent
python -m venv venv && source venv/bin/activate

# Linux: tkinter is stdlib but may need the system package
# sudo apt-get install python3-tk

pip install -r requirements.txt
python main.py
```

The agent opens a transparent HUD overlay, starts screen capture, and connects to the backend WebSocket.

#### 3. Dashboard

```bash
cd dashboard
npm install
npm run dev
# Open http://localhost:5173
```

---

## GCP Deployment

See [`deploy/cloud-run.sh`](deploy/cloud-run.sh) for a ready-to-run script.

Manual steps:

```bash
export PROJECT_ID=your-gcp-project
export GEMINI_API_KEY=your_key
export REDIS_URL=redis://your-redis-host:6379

# Build and push image
gcloud builds submit ./backend --tag gcr.io/$PROJECT_ID/phantom-backend

# Deploy to Cloud Run
gcloud run deploy phantom-backend \
  --image gcr.io/$PROJECT_ID/phantom-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "GEMINI_API_KEY=$GEMINI_API_KEY,REDIS_URL=$REDIS_URL,GOOGLE_CLOUD_PROJECT=$PROJECT_ID"
```

After deployment, update the agent's `BACKEND_URL` env var to the Cloud Run service URL:

```bash
export BACKEND_URL=wss://phantom-backend-xxxx-uc.a.run.app
python agent/main.py
```

---

## How It Works

1. **Start all components** (docker compose up + agent + dashboard)
2. **Open the dashboard** at `http://localhost:5173`
3. **Connect** with a session ID — the dashboard shows live agent status
4. **Speak a command** into your microphone:
   > *"Research the top 5 AI startups that raised funding this week, create a spreadsheet, and draft a Slack message to my team"*
5. **Phantom executes**: navigates browser, copies data, opens spreadsheet, types content — all narrated in real-time via the HUD
6. **High-risk actions** (form submits, purchases, deletions) pause for your confirmation in the dashboard modal

### Safety System

Every action Gemini proposes is:
1. Re-classified by the Safety Agent (overrides self-reported risk if needed)
2. Blocked if it matches critical risk patterns with no prior consent
3. Queued for confirmation if `risk_level` is `high` or `critical`
4. Logged to the audit trail in Firestore

### Memory

Phantom remembers your workflows, preferences, and past tasks using Firestore. Episodic memories expire; semantic preferences persist across sessions.

---

## Demo Scenarios

- **Multi-app research task**: Research → Spreadsheet → Email in one command
- **Workflow learning**: *"Remember this as my morning routine"*
- **Safety confirmation**: High-risk actions pause and require explicit approval
- **Emotional context**: Phantom detects frustration via webcam and adapts tone

---

## Tech Stack

- **Gemini 2.0 Flash Live** (`gemini-2.0-flash-live-001`) — real-time audio + video streaming
- **Google ADK** — multi-agent orchestration
- **Google Cloud Run** — backend deployment
- **Firestore** — long-term memory
- **Redis** — session state + inter-agent message bus
- **FastAPI** — async WebSocket server
- **React + Vite + Tailwind** — monitoring dashboard
