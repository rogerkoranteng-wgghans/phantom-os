# Phantom OS — DevPost Submission

> **Hackathon:** Gemini Live Agent Challenge (March 2026)
> **Categories:** Live Agents · UI Navigator
> **Live Demo:** https://phantom-backend-cxotjai2ta-uc.a.run.app/health
> **GitHub:** https://github.com/rogerkoranteng-wgghans/phantom-os

---

## Inspiration

Every year we collectively waste billions of hours on repetitive computer tasks — copying data between apps, formatting spreadsheets, sending follow-up emails, clicking through multi-step workflows. We have AI assistants that can *talk* about doing these things, but they can't actually *do* them.

The moment we saw the Gemini Live API — real-time audio streaming, native voice understanding, multimodal vision — we asked a different question: what if the AI could *see* your screen and *control* your computer the way a human would? Not through a chatbot interface, not through browser extensions limited to one tab, but as a true operating system layer that works across *every* application on your machine.

That's how Phantom OS was born. An AI that doesn't just answer — it acts.

---

## What It Does

Phantom OS is an autonomous AI desktop agent that sees your screen, hears your voice, and operates your computer across any application — no keyboard or mouse required.

**Speak a command like:**
> *"Research the top AI funding rounds from this week, put the data in a spreadsheet, then draft a Slack message to my team summarizing the findings."*

Phantom will:
1. Open your browser and search for recent AI news
2. Navigate through results, reading and extracting data
3. Open Google Sheets (or Excel), create a table, type the data in
4. Switch to Slack, find your team channel, draft and type the message
5. **Pause and ask your confirmation before hitting Send**
6. Narrate every step in real-time through your speakers

### Core Capabilities

**Multimodal Perception**
- Real-time screen capture streamed as video frames to Gemini
- Voice input via microphone with energy-based VAD (voice activity detection)
- Webcam emotion analysis — detects frustration, urgency, engagement in real-time

**Computer Control**
- Mouse: human-like bezier curve movement, click, double-click, right-click, drag, scroll
- Keyboard: realistic WPM typing, hotkeys, any special key combination
- System: open any app by name, open URLs, manage clipboard, focus windows

**AI Agent Swarm (7 Specialized Agents)**

| Agent | Role |
|---|---|
| **Orchestrator** | Decomposes complex tasks into sub-tasks, executes as a DAG |
| **Safety** | Classifies risk level, blocks dangerous actions, requests confirmation |
| **Memory** | Episodic + semantic memory across sessions (Firestore) |
| **Research** | Web search with Google Search grounding via Gemini |
| **Workflow** | Records, saves, and replays multi-step automation sequences |
| **Communication** | Drafts emails and messages in your personal writing style |
| **Prediction** | Pre-stages likely next actions to reduce execution latency |

**Safety-First Design**
- Every action is risk-classified before execution (low / medium / high / critical)
- High-risk actions (Send, Submit, Purchase, Delete) require explicit confirmation
- Certain destructive shortcuts (Shift+Delete, Ctrl+Shift+Delete) are unconditionally blocked
- Full audit log of every action in Firestore

**Real-Time Dashboard**
- Live action feed showing what the AI is doing and why
- Agent status panel with a task dependency graph
- Memory browser (episodic, semantic, workflow)
- Confirmation modal for high-risk actions
- Emotion radar showing your real-time emotional context

**Windows Desktop Installer**
- Single `.exe` installer built with PyInstaller + Inno Setup
- No Python, Node.js, or Redis installation required
- Embedded Redis (fakeredis) — zero external dependencies
- Optional: point to a cloud backend URL at install time

---

## How We Built It

### Architecture

```
┌─────────────────────────┐    WebSocket (wss://)    ┌──────────────────────────────┐
│     Desktop Agent        │◄────────────────────────►│   FastAPI Backend             │
│     (Python)             │  screen frames + audio   │   (Google Cloud Run)          │
│                          │  voice responses + cmds  │                               │
│  capture/screen.py       │                          │  services/gemini_live.py      │
│  capture/audio.py        │                          │  → Gemini 2.5 Flash Native    │
│  capture/camera.py       │                          │     Audio (Live API)          │
│  executor/mouse.py       │                          │                               │
│  executor/keyboard.py    │                          │  agents/orchestrator.py       │
│  executor/system.py      │                          │  agents/safety.py             │
│  overlay/hud.py          │                          │  agents/memory.py             │
└─────────────────────────┘                          │  agents/research.py           │
                                                      │  agents/workflow.py           │
         ▲                                            │  agents/communication.py      │
         │ REST                                       │  agents/prediction.py         │
         │                                            │                               │
┌────────┴─────────────┐                             │  services/redis_bus.py        │
│   React Dashboard     │◄────────────────────────── │  services/session.py          │
│   (Vite + Tailwind)   │   WebSocket                 └──────────────────────────────┘
│                       │
│  LiveSessionPage       │
│  MemoryPage            │
│  WorkflowPage          │
│  AuditPage             │
└───────────────────────┘
```

### Technology Choices

**Gemini 2.5 Flash Native Audio** (`gemini-2.5-flash-native-audio-latest`)
We use the newest native audio model specifically because it processes voice natively without text-to-speech conversion — the voice responses feel instant and natural. Screen frames are streamed alongside audio so Gemini has full visual context when reasoning about what to do next.

**Google Cloud Run**
The backend runs serverless on Cloud Run with session affinity enabled — critical for WebSocket connections, since each user's Gemini Live session must stay on the same instance. The entire backend can be deployed with a single shell script.

**Firestore**
Three-tier memory architecture: episodic memories (recent events), semantic memories (persistent user preferences), and workflow memories (saved automation sequences). Memory persists across sessions and is queryable by tag or content.

**Redis (embedded for local/desktop, optional Memorystore for cloud)**
All inter-agent messaging and session state flows through Redis pub/sub. For the Windows installer, we use `fakeredis` — a pure-Python in-memory implementation, so users need zero infrastructure.

**FastAPI + WebSockets**
A single WebSocket connection carries: screen frames (JPEG, base64), audio chunks (PCM 16kHz), action commands, voice audio responses, session state updates, and confirmation requests. Everything bidirectional over one persistent connection.

**PyInstaller + Inno Setup**
To eliminate the install friction of "install Python, install Redis, set environment variables", we bundle everything into a single Windows `.exe` installer built via GitHub Actions CI. The installer wizard asks for the Gemini API key and optionally a cloud backend URL — that's it.

### The Gemini Live Integration

The trickiest part was getting the streaming pipeline right. Audio is captured in 100ms chunks, encoded as PCM at 16kHz, and streamed via `send_realtime_input(audio=Blob(...))`. The native audio model uses its own built-in VAD to detect when the user finishes speaking and generates a native audio response — no text-to-speech step.

Screen frames are sent alongside via `send_realtime_input(video=Blob(...))` at adaptive FPS (1fps idle, 4fps during active task execution), giving Gemini continuous visual context of what's on screen.

The response comes back as streaming PCM audio chunks at 24kHz, which are played through a continuous `sounddevice.OutputStream` — samples are queued rather than restarted, producing smooth uninterrupted speech.

---

## Challenges We Ran Into

**1. The API changed under us**
We started with `gemini-2.0-flash-live-001` and the v1alpha API version. Midway through, the model was deprecated and the SDK was updated (v1.65.0). The new API uses completely different method signatures: `send_realtime_input(audio=Blob(...))` instead of `send_realtime_input(media=LiveClientRealtimeInput(...))`, and `Blob.data` requires raw bytes, not base64 strings. We spent hours tracking down silent failures.

**2. `send_client_content(turns=[], turn_complete=True)` kills the session**
Our original end-of-turn signal — sending `send_client_content` with empty turns — caused a 1007 "Invalid Argument" error on the native audio model, silently killing the Gemini session. This meant users got no response at all. The fix was to remove it entirely and rely on the model's built-in VAD.

**3. WebSocket keepalive on Cloud Run**
Cloud Run's load balancer doesn't forward WebSocket-level ping frames back to the client. Our agent's `ping_interval=20` setting caused connections to drop after exactly 28 seconds (20s interval + 8s timeout). Fixed by setting `ping_interval=None` and implementing application-level heartbeat messages every 15 seconds.

**4. Audio playback on Linux (Wayland)**
`sd.play(chunk, blocking=False)` restarts playback with every tiny 1920-sample chunk, making the audio inaudible. Fixed by using a persistent `sd.OutputStream` where `.write()` queues samples continuously. Also hit Wayland screen capture issues (mss doesn't support Wayland) — fixed with a grim/scrot fallback chain.

**5. API key leaked in GitHub repo**
The Gemini API key appeared in Cloud Run deployment logs (included in the `gcloud run deploy --set-env-vars` command) which were visible via `gcloud logging read`. Google automatically revoked it. Always use `--update-secrets` or Secret Manager for production.

**6. 24-second backend startup on local dev**
Without GCP credentials, Firestore initialization attempts timeout twice (once for MemoryAgent, once for WorkflowAgent), each taking ~12 seconds. Fixed with proper fallbacks to in-memory stores — the backend works fully offline.

---

## Accomplishments We're Proud Of

- **End-to-end working pipeline**: voice → screen → Gemini → action → execution. The agent actually controls the computer.
- **Fully deployed on Google Cloud**: backend running live on Cloud Run with real WebSocket connections from the desktop agent.
- **Windows installer in CI**: GitHub Actions builds a 94MB `PhantomOS-Setup.exe` on every push — bundling backend, agent, and embedded Redis with zero user-side dependencies.
- **7-agent architecture**: each agent is genuinely specialized and the orchestrator correctly routes tasks. Memory persists to Firestore. Safety agent correctly intercepts destructive actions.
- **Dual-mode deployment**: the same codebase runs entirely on the desktop (embedded Redis, local Gemini session) or with the backend on Cloud Run (agent is just mic/screen/keyboard, everything else in the cloud).
- **Emotion-adaptive behavior**: webcam-based frustration detection causes Phantom to change its tone mid-session without being prompted.

---

## What We Learned

- **Native audio models are fundamentally different** from text-based Live models. The VAD, turn detection, and response format all work differently. Read the SDK source, not just the docs.
- **WebSocket on Cloud Run requires session affinity** (`--session-affinity` flag). Without it, each request can hit a different instance, breaking stateful Gemini sessions.
- **Streaming audio playback is non-trivial**. A persistent output stream that queues samples is qualitatively different from repeatedly calling `play()` on tiny chunks.
- **Always test the full stack end-to-end early**. We had each component working in isolation before realizing the interaction between them (e.g. the end-of-turn signal killing the session) was the real problem.
- **fakeredis makes desktop distribution dramatically simpler**. Eliminating Redis as a user-side dependency removes one of the biggest friction points for non-technical users.

---

## What's Next

- **Windows UAC / process elevation**: currently requires admin for some system actions (installing software, modifying protected files)
- **Multi-monitor support**: currently captures primary display only
- **Workflow marketplace**: share and download community-built automation workflows
- **Fine-tuned action model**: train a specialized model on action-observation pairs for more reliable UI element targeting
- **Mobile companion app**: view audit log and approve/reject confirmations from your phone
- **Plugin API**: let developers register custom action types (e.g. "send Slack message" as a first-class action)

---

## Built With

`python` `fastapi` `websockets` `google-gemini` `gemini-live-api` `google-cloud-run` `google-cloud-firestore` `redis` `fakeredis` `react` `typescript` `vite` `tailwindcss` `pyinstaller` `inno-setup` `docker` `github-actions` `sounddevice` `pynput` `mss` `opencv` `pystray`

---

## Try It Yourself

**Cloud backend is live:**
```
Health check: https://phantom-backend-cxotjai2ta-uc.a.run.app/health
```

**Run locally in 3 commands:**
```bash
git clone https://github.com/rogerkoranteng-wgghans/phantom-os.git
cd phantom-os
docker compose up --build   # backend + Redis

# In a second terminal:
cd agent && pip install -r requirements.txt
GEMINI_API_KEY=your_key BACKEND_URL=ws://localhost:8000 python main.py
```

**Or download the Windows installer** from the [GitHub Actions artifacts](https://github.com/rogerkoranteng-wgghans/phantom-os/actions) — no Python or Redis needed.

---

*Team: Solo submission*
*Built over 4 days for the Gemini Live Agent Challenge, March 2026*
