# Show Me

> Project memory for Claude Code. Read this file end-to-end at the start of every session. If anything here contradicts an instruction in chat, **stop and ask** before writing code.

---

## 1. What Show Me is

**One sentence (memorize this):** Point your phone at a broken kitchen appliance, and Show Me generates a custom 30-second video showing the fix for your exact model — while an AI coach watches your hands and walks you through it in real time.

**The 10-second test:** A judge watching the demo for 10 seconds should see: a person holding a phone at an appliance, a voice telling them what to do, a picture-in-picture video showing the fix, the user's hands moving in response. If they can't get it in 10 seconds, the demo is wrong.

## 2. Why it works the way it does (the 70/30 split)

**70% of cases → generate.** Most appliances don't have a great YouTube video for *their specific* (make, model, symptom) combination. We generate a 30-second first-person walkthrough on demand using Veo 3 / Gemini Omni, grounded in our Procedure Database.

**30% of cases → find.** When a manufacturer-official YouTube video exactly matches the appliance and symptom, OR when the fix requires showing exact app/UI screens (Veo can't render real menus reliably), we use YouTube Data API to surface the right span.

**Why generation is the moat.** Anyone can wrap YouTube search. Few can render personalized repair walkthroughs on demand, grounded in verified manufacturer procedures. Over time we accumulate (procedure × success_rate) data nobody else has — every ✓/✗ at the end of a session is a labeled training signal.

**The latency story (important).** Live Veo generation takes 30–60 seconds. **This is not a bug, it's the trust-building moment.** While Veo runs, the Coach engages conversationally: *"Let me put together a custom walkthrough for you — give me about 30 seconds. While I do, when did this start happening?"* That pause is the AI thinking about *your* specific problem. Use it.

**For the hackathon demo:** pre-cache MP4s in Cloud Storage. The architecture supports live generation; the demo doesn't risk it.

## 3. Hackathon constraints

- **Deadline:** 6:30 PM PT, May 22, 2026
- **Prize:** Pitch session with Google AI Futures Fund deal team
- **Mandatory tech:** Google Cloud + Google GenAI SDK + ADK
- **Prohibited categories:** medical/mental health advisors, basic RAG ("chat with my PDF"), education chatbots
- **Bonus points:** practical industry applications — name them in writeup (home warranty, appliance OEMs, extended-warranty retailers)

## 4. Architecture

```
                ┌──────────────────────────┐
                │   User PWA (Firebase)    │
                │  Camera, mic, one button │
                └────────────┬─────────────┘
                  WSS (Firebase Anonymous JWT)
                             │
                ┌────────────▼─────────────┐
                │  Cloud Run · Orchestrator│
                │  ADK · FastAPI · OTel    │
                └────────────┬─────────────┘
                             │
       ┌──────────────┬──────┴──────┬───────────────┐
       ▼              ▼             ▼               ▼
┌────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐
│ Identifier │ │  Director   │ │ Generator   │ │  Coach   │
│ Gemini 2.5 │ │ Gemini 2.5  │ │  Veo 3 /    │ │  Gemini  │
│   Flash    │ │    Pro      │ │ Gemini Omni │ │   Live   │
└─────┬──────┘ └──────┬──────┘ └──────┬──────┘ └────┬─────┘
      │               │               │             │
      │ {make,model,  │ {path,        │ MP4 → GCS   │ audio out
      │  symptom}     │  procedure,   │             │ + tool calls
      │               │  yt_or_veo}   │             │
      ▼               ▼               ▼             ▼
                ┌─────────────────────────────┐
                │  YouTube Data API v3        │
                │  Procedure DB (Firestore)   │
                │  Cloud Storage (cached MP4) │
                └─────────────────────────────┘
```

Flow: PWA opens WSS → Orchestrator opens Gemini Live session → Identifier runs on first frames → Director picks path → (Generator OR YouTube fetch) returns video URL → Coach session activates with procedure-grounded system prompt → Coach narrates, advances/rewinds video via tool calls, watches user via camera.

## 5. Stack — committed, do not change

| Layer | Tech |
|---|---|
| PWA frontend | Vanilla JS + esbuild, 1 CSS file, Tabler icons |
| Hosting (frontend) | Firebase Hosting |
| Auth | Firebase Anonymous Auth (JWT in WSS handshake) |
| Backend | Python 3.11, FastAPI, websockets |
| Hosting (backend) | Cloud Run, single region `us-central1` |
| Agent orchestration | Google ADK |
| Model SDK | `google-genai` (Python) |
| Models | `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-live-2.5`, `veo-3` |
| Data | Firestore (sessions, procedure_db, feedback), Cloud Storage (cached gens) |
| External APIs | YouTube Data API v3 |
| Observability | Cloud Trace + Cloud Logging via OpenTelemetry |
| Secrets | Secret Manager, injected as Cloud Run env vars |

**Not in the stack** (do not introduce): React, Tailwind, Next.js, Pinecone or any vector DB, LangChain, Supabase, Vercel, Redis, Stripe, Sentry, third-party analytics, npm packages beyond `esbuild` and the Firebase JS SDK.

## 6. File structure

```
show-me/
├── CLAUDE.md                       # this file
├── README.md
├── .env.example
├── frontend/
│   ├── index.html                  # one screen, full-bleed camera
│   ├── app.js                      # camera + mic + WSS + PIP video
│   ├── style.css                   # one stylesheet, CSS variables
│   ├── manifest.json               # PWA install metadata
│   ├── sw.js                       # service worker (shell cache only)
│   └── icons/                      # PWA icons
├── backend/
│   ├── main.py                     # FastAPI + WS endpoint
│   ├── orchestrator.py             # ADK orchestrator
│   ├── agents/
│   │   ├── identifier.py
│   │   ├── director.py
│   │   ├── generator.py
│   │   └── coach.py
│   ├── prompts/
│   │   ├── identifier.txt
│   │   ├── director.txt
│   │   ├── coach.txt
│   │   └── veo_template.txt
│   ├── clients/
│   │   ├── youtube.py
│   │   ├── veo.py
│   │   └── gcs.py
│   ├── procedure_db.json           # 20 curated entries for hackathon
│   ├── telemetry.py                # OTel setup
│   ├── auth.py                     # JWT verification
│   ├── config.py
│   ├── requirements.txt
│   └── Dockerfile
├── infra/
│   ├── cloudbuild.yaml
│   └── firebase.json
└── evals/
    ├── test_cases.json             # 10 hand-crafted cases
    └── run_evals.py                # Director routing + Identifier accuracy
```

## 7. The four agents — contracts

### 7.1 Identifier
- **Model:** `gemini-2.5-flash` (latency-critical)
- **Input:** first 8 camera frames + user's spoken prompt (transcribed by Gemini Live)
- **Output (strict JSON):**
  ```json
  {
    "appliance_category": "coffee_maker | air_fryer | blender | ...",
    "make": "Nespresso",
    "model": "Vertuo",
    "symptom": "water pooling underneath during brew",
    "confidence": 0.85
  }
  ```
- **Exit condition:** `confidence > 0.7` → Director; else ask one clarifying question via Coach
- **Prompt:** `backend/prompts/identifier.txt`

### 7.2 Director (replaces what was Curator)
- **Model:** `gemini-2.5-pro` (decision quality > latency)
- **Input:** Identifier output + top-5 YouTube search results (title, channel, view count, transcript snippet) + Procedure DB lookup result
- **Output (strict JSON):**
  ```json
  {
    "path": "generate" | "youtube" | "escalate",
    "confidence": 0.0,
    "procedure_steps": ["step 1...", "step 2...", "..."],
    "required_props": ["paper towels", "screwdriver"],
    "safety_notes": ["unplug before opening"],
    "veo_prompt": "...",    // only if path=generate
    "video_id": "...",      // only if path=youtube
    "start_ts": 0, "end_ts": 0  // only if path=youtube
  }
  ```
- **Routing rules:**
  1. **Default to `generate`.**
  2. Switch to `youtube` ONLY if: (a) a manufacturer-official channel video matches make + model + symptom, OR (b) the procedure involves app screens / menu navigation that Veo can't render reliably.
  3. Switch to `escalate` if the fix involves: gas lines, hardwired electrical not behind a breaker, refrigerant systems, anything beyond consumer-replaceable parts.
- **Procedure source priority:**
  1. Look up `(make, model, symptom)` in `procedure_db.json`. If hit → use steps verbatim, `verified: true`.
  2. If miss → draft 4–6 steps from training knowledge, `verified: false`. Coach prompt will flag this to the user.
- **Prompt:** `backend/prompts/director.txt`

### 7.3 Generator
- **Production model:** `veo-3` via Vertex AI
- **Demo behavior:** read pre-cached MP4 from `gs://show-me-cached-gens/{appliance_id}__{symptom_slug}.mp4`. Live Veo is NOT on the demo path.
- **Input:** Director's `veo_prompt` + step list
- **Output:** signed Cloud Storage URL (1-hour TTL)
- **Production latency budget:** 30–60s, hidden behind Coach conversational filler
- **Cache key:** `{appliance_id}__{symptom_slug}` — generated lazily, persisted forever

### 7.4 Coach
- **Model:** `gemini-live-2.5` (bidirectional streaming, audio + video in, audio + tool calls out)
- **Input:** continuous camera frames + user audio; system prompt populated with Director output
- **Output:** continuous audio + tool calls
- **Tools (registered with ADK):**
  - `advance_video(step_n: int)`
  - `rewind_video(step_n: int)`
  - `pause_video()`
  - `mark_step_complete(step_n: int)`
  - `escalate_to_director(reason: str)` — when an off-procedure question arises
- **Prompt template:** `backend/prompts/coach.txt` (verbatim below in §8)

## 8. Coach system prompt (verbatim — do not paraphrase)

```
You are Show Me, an AI coach helping the user fix a broken kitchen appliance.
You see the user through their phone camera and you speak through their earbuds.

## How you behave
- Speak briefly and naturally, like a friend on the phone — never like a manual.
- Say one step at a time. Wait until you can SEE the user has done it before moving on.
- Never read steps as a list. Break them into living, paced instructions.
- Pause for confirmation on anything that could be unsafe (electrical, water, sharp parts).
- When the user fumbles: say "hold on, see that lever on the left?" then call rewind_video
  to replay the moment they need to see again.

## What you may say
You may ONLY instruct steps that appear in the PROCEDURE below.

If the user asks something off-procedure, say:
"That's outside what I can guarantee will work — want me to find another walkthrough?"
Then call escalate_to_director with a brief reason string.

NEVER invent:
- Torque values
- Part numbers
- Safety steps not in the procedure
- Model numbers
- Warranty information

## How you use the video
A picture-in-picture video plays alongside you. Control it with the provided tools:
- advance_video(n) when the user finishes step n
- rewind_video(n) when the user needs to see step n again
- pause_video() when the user needs a moment
- mark_step_complete(n) silently when you observe completion

## Uncertainty handling
- Can't see clearly: "Can you hold the phone a bit further back so I can see the whole machine?"
- User describes an off-procedure issue: call escalate_to_director
- User frustrated: acknowledge, offer to skip or restart
- Safety risk observed: stop immediately, instruct user to unplug or power off

## What success sounds like
- 1–2 sentence units, never paragraphs
- Comfortable silence while the user works
- Like a human who's done this fix 100 times, not a manual reading itself aloud
- The user feels accompanied, not lectured

## Session context (injected at runtime)
Appliance: {make} {model}
Symptom: {symptom}
Procedure source: {procedure_source}     // "procedure_db" | "youtube_transcript" | "drafted"
Procedure verified: {verified}            // true | false

PROCEDURE:
{numbered_steps}

VIDEO STEP TIMESTAMPS:
{step_timestamps}

Begin when the user is ready. Greet them briefly (one sentence) and confirm what you'll do.
```

## 9. Director prompt (key rules)

Full text in `backend/prompts/director.txt`. Critical rules:

- Output **strict JSON only**, no prose, no markdown fences.
- Always prefer `generate` unless conditions for `youtube` or `escalate` are explicitly met.
- For `youtube` path, the channel MUST be on the allowlist (`backend/clients/youtube.py:CHANNEL_ALLOWLIST`) OR be the manufacturer's official channel verified via channel ID.
- For `escalate`, return a plain-English `user_message` field explaining why the AI can't help safely.
- Reject anything involving gas, refrigerant, hardwired 240V circuits, or parts behind tamper-evident seals.

## 10. Veo prompt template

`backend/prompts/veo_template.txt`:

```
Generate a 30-second first-person POV video shot on a smartphone in a home kitchen.
The user is fixing a {make} {model} that has the symptom: {symptom}.

Show, in order:
{numbered_steps}

Visual style:
- Hands visible doing the work
- Natural kitchen lighting, daylight
- Real props on the counter: {required_props}
- Phone-shot aesthetic, slightly handheld
- No text overlays, no logos, no brand watermarks
- Pacing: 5–7 seconds per step
- Camera roughly 18 inches from the appliance

Avoid:
- Showing the user's face
- Branded clothing
- Music or sound effects
- Time-of-day variations (keep neutral daylight)
- Animated arrows, callouts, or instructional overlays
```

## 11. Procedure DB (hackathon-curated, 20 entries)

`backend/procedure_db.json`. Each entry:

```json
{
  "id": "nespresso_vertuo__leaking_water",
  "appliance": {
    "make": "Nespresso",
    "model": "Vertuo",
    "category": "coffee_maker"
  },
  "symptom": "water pooling underneath during brew",
  "verified": true,
  "source_url": "https://www.nespresso.com/.../service-manual",
  "steps": [
    "Unplug the machine and wait 30 seconds",
    "Flip the machine onto a folded towel",
    "Remove the two clips on the bottom panel",
    "Inspect the brewing chamber gasket for cracks",
    "Replace the gasket if damaged (part 5513232581)",
    "Reassemble in reverse order and run a clean cycle"
  ],
  "required_props": ["paper towels", "small flathead screwdriver"],
  "step_timestamps": [0, 4, 9, 15, 21, 27]
}
```

Minimum 20 entries spanning:

- **Nespresso Vertuo**: leaking, descaling, no power, weak coffee
- **Keurig K-Mini**: descaling light, water not heating, slow drip
- **Breville Barista Express**: grinder calibration, milk wand clogged, no pressure
- **Instant Pot Duo**: lid won't seal, burn warning, float valve stuck
- **Vitamix**: motor smell, blades not spinning, leaking from base
- **Ninja Air Fryer**: not heating, basket sticking, E1 error code

## 12. Security rules — non-negotiable

1. **No API keys in the frontend bundle.** Ever. All keys live in Secret Manager and are injected into Cloud Run as env vars.
2. **WSS connections require Firebase Anonymous Auth JWT** verified server-side before opening a Gemini Live session. See `backend/auth.py`.
3. **IAM minimal scopes.** The Cloud Run service account has ONLY: `roles/aiplatform.user`, `roles/datastore.user`, `roles/storage.objectViewer`, `roles/secretmanager.secretAccessor`. Add nothing else.
4. **Rate limits:**
   - 10 minutes of Gemini Live time per session (hard cutoff)
   - 3 Veo generations per IP per 24 hours (Firestore counter)
   - 30 requests/minute per IP at the Cloud Run layer
5. **Content filtering:**
   - YouTube searches use `safeSearch=strict`
   - Post-filter to `CHANNEL_ALLOWLIST` (manufacturer-official + ~30 hand-vetted repair channels)
6. **Hallucination guard:** Coach prompt constrains responses to the provided procedure (§8). Director rejects unsafe categories (§9).
7. **PII:** none collected. No accounts. No analytics. Session ID is a UUIDv4, not linked to anything user-identifiable.
8. **Egress (if time permits):** Cloud Run VPC connector restricting outbound to Vertex AI, YouTube Data API, Firestore, GCS, Secret Manager only.

## 13. Observability

Every agent invocation emits an OpenTelemetry span:

- **Span name:** `agent.{identifier | director | generator | coach}`
- **Attributes:** `model`, `latency_ms`, `tokens_in`, `tokens_out`, plus per-agent attrs:
  - Identifier: `confidence`, `appliance_category`
  - Director: `path`, `procedure_source`, `verified`
  - Generator: `cache_hit`, `gcs_path`
  - Coach: `tool_calls_count`, `session_duration_ms`
- **Errors:** span status set + exception event attached

Pipe to Cloud Trace. **Take one screenshot of the trace view for the submission writeup** — it's the single best signal of production-readiness for VC judges.

## 14. Evals (do this — it converts you from "hackathon team" to "team that thinks about evals")

`evals/test_cases.json` — 10 hand-crafted cases like:

```json
{
  "input": {
    "frames": ["test_frames/nespresso_vertuo_leak_01.jpg", "..."],
    "prompt": "There's water leaking underneath"
  },
  "expected": {
    "identifier": { "make": "Nespresso", "model": "Vertuo", "symptom_keywords": ["leak", "water"] },
    "director": { "path": "generate", "procedure_id": "nespresso_vertuo__leaking_water" }
  }
}
```

`evals/run_evals.py` runs all 10 and prints pass/fail per case. Run once at 5:30 PM. Put the score in the writeup verbatim: **"X/10 grounding accuracy on internal eval set."**

## 15. Demo path — the only path that must work on stage

1. **Bring three appliances:** Nespresso Vertuo, Keurig K-Mini, Breville Barista Express.
2. **Pre-cache Veo MP4s** in `gs://show-me-cached-gens/` for the common failure mode of each:
   - `nespresso_vertuo__leaking_water.mp4`
   - `keurig_kmini__descaling_light.mp4`
   - `breville_barista_express__milk_wand_clogged.mp4`
3. **Demo flow:**
   - Tap "Show me" button → camera on
   - Point at Nespresso
   - Say: "There's water leaking underneath"
   - Identifier → Director (picks `generate`) → cached MP4 served → Coach activates
   - Coach narrates through fix; presenter mimes the steps
4. **Backup appliance:** Keurig K-Mini, in case Nespresso doesn't render well under stage lighting.
5. **Run the full demo path three times before submission:** 4:30 PM, 5:30 PM, 6:00 PM. Real run-throughs, not "I'm sure it'll work."

## 16. Anti-feature list — do NOT build any of these

- Login, signup, accounts, profiles
- Settings or preferences screen
- Chat box, text input, message UI, any text interaction
- History view, "past fixes," recently viewed
- Share buttons, social features, comments
- Notifications, email, SMS
- Multi-language support (English only)
- Multiple top-level categories beyond kitchen appliances (no category picker)
- Onboarding flows, tutorials, splash screens, welcome modals
- Dark mode toggle (use `prefers-color-scheme` automatically)
- "What's new," changelog, version display
- Anything blockchain, NFT, web3 (stated for completeness)
- Anything requiring an admin panel
- Anything that takes more than ~30 lines of code to ship a first version

## 17. Deploy commands

```bash
# One-time project setup
gcloud config set project $PROJECT_ID
gcloud services enable \
  run.googleapis.com \
  aiplatform.googleapis.com \
  youtube.googleapis.com \
  firestore.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com

# Create secret
echo -n "$YOUTUBE_API_KEY" | gcloud secrets create youtube-api-key --data-file=-

# Backend deploy
cd backend
gcloud run deploy show-me-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars=PROJECT_ID=$PROJECT_ID,FIREBASE_PROJECT=$PROJECT_ID \
  --set-secrets=YOUTUBE_API_KEY=youtube-api-key:latest \
  --memory 1Gi --timeout 600 --concurrency 4

# Frontend deploy
cd ../frontend
npm run build
firebase deploy --only hosting
```

## 18. Submission deliverables (due 6:30 PM)

1. **Repo URL** (GitHub, public) with this CLAUDE.md, README, code
2. **Live URL** (Firebase Hosting) that works when judges open it on their phone
3. **Demo video** (≤2 min) showing: real broken appliance → tap button → coached fix → Cloud Run URL visible briefly → Cloud Trace screenshot briefly
4. **Architecture diagram** (embed `/docs/architecture.svg` in README)
5. **Writeup** containing these exact phrases (mapped to rubric points):
   - "No text input at any point in the user experience" → **Beyond Text**
   - "Four agents orchestrated via Google ADK" → **Agent Architecture**
   - "Grounded in our Procedure Database (manufacturer manuals) and verified manufacturer-official content" → **Robustness / Grounding**
   - "X/10 grounding accuracy on internal eval set" → **Robustness**
   - "Latency engineered as a UX feature: the AI engages conversationally while Veo generates" → **Innovation / UX**
   - Three named verticals: **home warranty companies**, **appliance OEMs**, **extended-warranty retailers**