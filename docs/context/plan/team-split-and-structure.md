# Team split and project structure (2 people)

## The idea in one line
Split the work along the pipeline. **Person A** owns the data side: generate, ingest and interpret. **Person B** owns the AI and screen side: explain, render and personalize. The two halves meet at **two JSON schemas you agree on first**. After that, each person can work without waiting for the other.

| | Person A: data and platform | Person B: agents and experience |
|---|---|---|
| Pipeline stages | Ingest, Interpret | Explain, Render, Personalize |
| Builds | Synthetic match generator, live event stream, stats engine (pass difficulty, speeds, possession, momentum), Azure infra | Multi-agent system (narrator, explainer, personalizer, translator), overlay UI, analyst and fan modes |
| Microsoft tech | Event Hubs or Container Apps, Cosmos DB or Fabric, `azd`/Bicep | Foundry, Agent Framework, MCP (stats exposed as tools), Static Web Apps |
| Works against | The schemas | Recorded sample matches in `data/samples/`, so it doesn't wait for A's live stream |
| Also owns | README, architecture diagram, deploy link | Demo video and pitch |

Why this split works: each person demos something on their own by mid-week, and the judging criteria divide the same way. A covers tech implementation and synthetic data. B covers agentic design and UX/video.

## The contract (agree on this together first)
1. **`event.schema.json`**: one match event, modelled on StatsBomb (id, t, period, team, player, type, location, end_location, outcome, related ids), plus an optional tracking frame (player x/y/speed, DFL-style).
2. **`insight.schema.json`**: what the stats engine emits for the agents. Running stats, detected "moments" (a big chance, a pressure spike, a momentum swing) with numbers attached, and match state.
3. **`overlay.schema.json`**: what the agents emit for the screen. A timed card (`t_start`, `t_end`, slot, text, language, audience mode, data points).

Commit sample files for all three on day 1, even if they're hand-written.

## Repo structure
```
<project-name>/
├── schemas/                 # the contract: event / insight / overlay JSON schemas + examples
├── data/
│   ├── generator/           # A: synthetic match simulator (teams, players, events, tracking)
│   ├── calibration/         # A: notebooks tuning the generator on open data (raw data git-ignored)
│   └── samples/             # generated matches (.jsonl) that everyone develops against
├── services/
│   ├── stream/              # A: replays a match "live" at 1x–10x speed → Event Hubs / SSE
│   ├── stats/               # A: interpret stage — metrics, moment detection, match state
│   ├── agents/              # B: Agent Framework / Foundry agents + MCP server over stats
│   │   ├── orchestrator/
│   │   ├── narrator/        #   live commentary lines
│   │   ├── explainer/       #   "why this matters" (control vs chaos, pressure, rhythm)
│   │   ├── personalizer/    #   analyst vs casual fan, favourite club/player, player-focus
│   │   └── translator/      #   multi-language output
│   └── api/                 # B (A helps): FastAPI gateway, websocket to the UI
├── web/                     # B: React overlay on a pitch view + mode switcher + recap page
├── infra/                   # A: azd + Bicep (Container Apps, Event Hubs, Cosmos, Foundry)
├── tests/
├── docs/                    # architecture diagram, demo script, judging checklist
├── .github/workflows/       # CI: lint, tests, deploy
└── README.md
```
Suggested stack: Python for the generator, stats and agents (Agent Framework has a Python SDK), and React with TypeScript for the UI. Python works for the API too.

## Timeline (submission closes Oct 27, 11:59 pm PT)
- **Oct 9–11: Together.** Pick the angle and name, write the three schemas, set up the repo skeleton and CI, and both register (registration closes **Oct 20, 12 pm PT**). Choose the team Representative, who is the one person that submits.
- **Oct 12–18: Apart.** A builds the generator, stream and stats engine. B builds the agents and UI against the sample files.
- **Oct 19–22: Together.** Connect the live stream to the agents and the UI, deploy to Azure, and fix whatever breaks.
- **Oct 23–27: Polish.** Tune the personalization modes, add multi-language, write the README and architecture doc, record the video (under 2 minutes) and submit a day early.

## Working rules
- `main` always runs. Work on short branches with PRs, and the other person gives a quick review.
- Each person keeps their own folders. Changes to `schemas/` need both people to agree.
- Do a 10-minute sync each day: what's done, what's blocked, and whether the schemas changed.
