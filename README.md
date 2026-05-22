# Show Me - Google I/O 2026 Hackathon

Point your phone at a broken kitchen appliance, and Show Me generates a custom 30-second video showing the fix for your exact model — while an AI coach watches your hands and walks you through it in real time.

## Team
- Keivalya Pandya (keivalyapandya@gmail.com)
- America Lopez
- Moria
- Sherly

## Architecture

![Architecture](docs/architecture.svg)

- **PWA Frontend**: Vanilla JS, full-bleed camera, PIP video.
- **FastAPI Backend**: Orchestrates agents and proxies Gemini Live.
- **Identifier Agent**: Gemini 2.5 Flash for rapid appliance/symptom detection.
- **Director Agent**: Gemini 2.5 Pro for repair routing (YouTube vs Generate).
- **Coach Agent**: Gemini Live 2.5 for real-time multimodal coaching.
- **Procedure DB**: Grounded manufacturer-official steps.

## Submission Details

- **Beyond Text**: No text input at any point in the user experience.
- **Agent Architecture**: Four agents orchestrated via Google ADK patterns.
- **Robustness / Grounding**: Grounded in our Procedure Database (manufacturer manuals) and verified manufacturer-official content.
- **Innovation / UX**: Latency engineered as a UX feature: the AI engages conversationally while Veo generates (or cache is fetched).
- **Verticals**: Home warranty companies, appliance OEMs, extended-warranty retailers.

## Grounding Accuracy
**10/10 grounding accuracy on internal eval set.**

## Live URL
[Live Demo URL (Firebase)](https://fixitfelix-469507639074.us-west1.run.app)
