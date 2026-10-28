# Inside the Game hackathon: reference sheet

One place for the rules, the official videos, the tools, and **our project plan** (§10). All dates are shown in Israel time, with the official Pacific Time next to them. Compiled 2026-10-18.

**Sources**
- Official repo [microsoft/insidethegamehackathon](https://github.com/microsoft/insidethegamehackathon), re-read 2026-10-18: `OFFICIAL RULES.md` (§ numbers below refer to it), `RESOURCE PLAYLISTS.md`, licence, code of conduct, security notes. The repo has no starter code, no data and no video links.
- The Reactor series page [Inside the Game: Developer Hackathon (S-1709)](https://developer.microsoft.com/en-us/reactor/series/S-1709/), checked 2026-10-18. It lists **one** session so far.
- Project notes this builds on: [hackathon-brief.md](hackathon-brief.md), [reactor-aks-aca-session.md](../research/reactor-aks-aca-session.md), and the rules Q&A in the thread "Hackathon rules and plan" (Oct 18).

---

## 1. Key dates (Israel time first)

Watch the clock change: Israel leaves daylight saving on **Sun Oct 25**, but the US doesn't until Nov 1. So Israel is 10 hours ahead of PT until Oct 24, and **9 hours ahead from Oct 25 to Oct 31**.

| What | 🇮🇱 Israel time | Official (PT) |
|---|---|---|
| Registration closes, at https://aka.ms/insidethegame (every team member registers) | **Tue Oct 20, 22:00** | Tue Oct 20, 12:00 pm |
| Submission closes | **Wed Oct 28, 08:59** (in practice, aim for Tue night Oct 27) | Tue Oct 27, 11:59 pm |
| Judging. **The live link must keep working, free and open, until the end.** | Tue Oct 27, 18:00 to **Wed Nov 11, 09:59** | Oct 27, 9:00 am to Nov 10, 11:59 pm |
| Winners announced | By Sat Nov 21, 09:59 | By Fri Nov 20, 11:59 pm |

## 2. The challenge (§4.1)

Build an AI app or agent system that turns **synthetic** football events into explainable match intelligence. It is one pipeline with five stages:

1. **Ingest** synthetic events as they happen (passes, shots, tackles, possession changes, pressure, metadata).
2. **Interpret** them into stats, patterns and context.
3. **Explain** why a moment matters, not just that it happened.
4. **Render** the insight as something that can sit on screen next to the match (timed, machine-readable, overlay-ready).
5. **Personalize** it so an analyst and a casual fan get genuinely different experiences: favourite club or player, player-focus mode, language, one metric they care about.

The rules say *"a Project that only generates metrics has no audience, and a solution that only personalizes has nothing to personalize."*

Suggested features (optional): player tagging with speed and distance, pass distance, accuracy and difficulty, ball and shot speed, auto-eventing from video, narratives, milestones and recaps, explaining "control vs chaos", pressure shifts and rhythm, new synthetic datasets, and multi-language output.

## 3. Hard rules

- **Synthetic data only (§4.7).** No footage or data is provided. Any footage you use must be self-sourced and licensed. Our decision (Oct 13): no video analysis; everything is synthetic JSON events, and the demo "match" is a rendered 2D pitch with synthetic audio, labelled as synthetic.
- **New project** built after Sept 29, 2026 (§4.3).
- **Must fit at least one category** (§4) and run as shown in the video (§4.3).
- **Third-party SDKs, APIs, data and open source** are allowed if you follow their licences and build on top of them (§4.3, §4.11).
- **No Premier League or other trademarks, logos or copyrighted music** in the video or app without permission (§4.4, §11.8).
- **English** for everything submitted, or provide translations (§4.9).
- **Teams of up to 4.** Name one Representative to submit (§3, §4.10).
- **Eligibility:** no Microsoft or Premier League employees or their families/households; no residents of Brazil, Quebec, Russia, Crimea, Cuba, Iran, North Korea, Sudan, Syria or other OFAC-sanctioned places (§3).
- **No funding or contract work from Microsoft** behind the project (§4.12).
- **Multiple entries** are fine if each is substantially different (§4.5).

## 4. What to submit (§4.4, §4.8)

- [ ] **Pitch:** what you built, which Microsoft and Azure tech, what it does, what problem it solves.
- [ ] **Demo video under 2 minutes** (judges may stop at 2:00), public on YouTube, Vimeo, Facebook Video or Youku, showing the project running on its real platform. No unlicensed music or trademarks.
- [ ] **Public GitHub repo.** It must be public to count. Add a licence you choose.
- [ ] **Working test link** (site, demo or build), free and unrestricted until Nov 10. Include login details if it needs them. Judges may judge on the video and text alone, so the video has to stand on its own.

## 5. Judging (§6)

**Stage 1, pass/fail:** does it reasonably fit the theme and *"reasonably apply the required technologies featured in the Hackathon"*?

**Stage 2:** five criteria at 20% each. Ties are broken in this order, so technological implementation counts most.

| Criterion | What judges look for |
|---|---|
| Technological implementation | Creative, optimized synthetic data. Quality engineering (MS Learn cloud best practices). Effective use of the hero tech. Well-structured, documented, maintainable code. |
| Agentic design and innovation | Creative agentic patterns. Orchestration, MCP, multi-agent collaboration. A novel approach or a real improvement on existing ones. |
| Real-world impact | Size of the problem. Could it run in production? Impact on users or businesses. |
| UX and presentation | Intuitive UX. A video that sells the value. A balance of frontend and backend. |
| Category adherence | Does it match the description of the category it enters? |

## 6. Prizes and categories (§4.2, §8)

Each entrant can win one Grand Prize and one Category Prize. Prizes are paid as USD e-gift cards, and winners handle their own taxes (W-8BEN for non-US).

| Prize | Per team member | What wins it |
|---|---|---|
| Grand 1st | PL match ticket, $50 PL store voucher, $4,000 | Most complete, compelling solution with innovative use of the Microsoft AI stack, real impact, and *"accessible and personalized experiences for fans, analysts and broadcasters"* |
| Grand 2nd | Ticket, voucher, $2,500 | Runner-up on the same terms |
| Best Use of Microsoft Foundry | Voucher, $1,500 | Foundry used to build, orchestrate and manage the AI, in ways that would be hard otherwise |
| Best Enterprise Solution | Voucher, $1,500 | Production readiness: reliability, transparency, controls |
| Best Multi-Agent System | Voucher, $1,500 | Agents with distinct roles, shared state, handoffs and failure recovery, delivering something one agent couldn't. Built with GitHub Copilot, Agent Framework, A2A or similar |
| Best Azure Cloud Native Integration | Voucher, $1,500 | AKS, Container Apps, Functions, Logic Apps, AI data platforms; event-driven, automated, operationally solid |

Note that the Grand Prize text names **accessibility** explicitly, which suits our deaf and hard-of-hearing angle.

## 7. Rights and licence (§7, §11.8)

- The project stays **yours**. Microsoft and the Premier League get a free, perpetual, **non-exclusive** licence to use it for any purpose, including commercial ones, with no payment or credit.
- They may build something similar, and you waive claims over similarity.
- They can use team members' names and images in hackathon publicity for 3 years.
- The repo must be public, so pick a licence deliberately. A commercial product can't use PL names or logos. (This is not legal advice.)

---

## 8. Tools: what you must, should and can use

**Must:** at least **one Microsoft AI service** (for example Microsoft Foundry or Agent Framework) **plus Azure hosting** for the live link. This is how we read Stage 1's *"required technologies"*. The rules never require every tool, and judges reward depth over breadth (§6.2 asks *"how effectively"*, not how many). Our stack is **not decided yet**.

**Oct 22 update:** the team set a zero-extra-cost rule, so Azure hosting is no longer assumed. Task D2-00 decides the model, the hosting and how judges reach the demo (`docs/implementation/VMI-FINAL-PLAN.md` §7). §4.8 accepts a website, a working demo or a test build.

**Hero technologies named in the judging criteria (§6.2):**

| Tool | What it is | Where it would fit |
|---|---|---|
| **Microsoft Foundry** | Model hosting, agents, evaluation, content safety | The core AI service. It also unlocks the Foundry category. |
| **Microsoft Agent Framework** | Open-source SDK (.NET and Python) for agents and multi-agent workflows | Orchestrating several agents. It strengthens the agentic score and the Multi-Agent category. |
| **Azure MCP** | MCP server exposing Azure resources to agents | Agents calling tools. MCP is named in the agentic criterion. |
| **GitHub Copilot Agent Mode** | AI coding agent in the IDE | Building the app. Keep prompts in the repo to show it, as the Reactor demo did. |
| **GitHub SDK / GitHub CLI** | Automation around the repo | CI, releases, scripting. |
| **Microsoft Fabric** | Data and analytics platform | Large-scale event data and analytics. Probably overkill for a demo. |
| **Azure Apps and AI Services** | e.g. Container Apps, App Service, Functions, Speech, Translator | Hosting, TTS for synthetic commentary, translation. |
| **Azure databases** | e.g. Cosmos DB, Azure SQL, PostgreSQL | Storing matches and state, if needed. |

**Also named in the category descriptions:** A2A (agent-to-agent protocol), AKS, Azure Container Apps (ACA), Azure Functions, Logic Apps, and "AI-optimized data platforms".

**Shown in the official Reactor session** (see §9): Foundry with one model deployment and keyless (Entra ID) access, ACA (preferred for this) or AKS, Blob Storage, DuckDB in memory, Application Insights with OpenTelemetry, managed identities, Bicep plus a deploy script, Docker Compose locally, and GitHub Copilot.

**Can:** any open-source or third-party library, API or data, if its licence allows and your work builds on it (§4.3, §4.11). Non-Microsoft models or tools aren't banned, but they don't score as hero tech.

**Learning playlists** from the official repo (`RESOURCE PLAYLISTS.md`, Microsoft AI Skills Navigator):

| Playlist | What you learn |
|---|---|
| [GitHub Copilot](https://aka.ms/asn/ghcopilot) | Using Copilot to code, debug and build faster |
| [Azure AI Foundry](https://aka.ms/asn/foundry) | Building, evaluating and managing AI apps in Foundry |
| [Foundry Agents](https://aka.ms/asn/foundryagents) | Agents that reason, use tools and complete tasks |
| [Agentic Workflows](https://aka.ms/asn/agenticworkflows) | Multi-step workflows combining models, data and automation |
| [Data](https://aka.ms/asn/data) | Data as the foundation for AI experiences |

*Only the repo's one-line descriptions are summarised here. The playlist pages block automated access, so their individual videos and modules couldn't be listed. They are general Microsoft Learn content, not hackathon-specific sessions.*

---

## 9. Official videos

As of 2026-10-18, the Reactor series lists **one** session. No other official hackathon videos turned up in the repo or in searches. (The Reactor "Agents League" series is a different hackathon.)

### "Build AI-powered soccer insights apps with AKS and ACA"
- **Who and when:** Brian Benz (Principal Cloud Advocate, Microsoft), live Oct 14, 2026 at 19:00 Israel time (16:00 UTC), about 1 hour. [YouTube](https://www.youtube.com/watch?v=EQ187ohgCbo) · [Reactor event](https://developer.microsoft.com/en-us/reactor/events/27536/)
- **Based on:** the full transcript Nadav pasted in the thread "YouTube video analysis", plus his architecture slide. Full notes are in [reactor-aks-aca-session.md](../research/reactor-aks-aca-session.md).
- **What he showed:** his sample app "football results dashboard" (aka.ms/football-results-dashboard), a Q&A dashboard over 150 years of international results. It uses real Kaggle data, and when asked he couldn't say whether that is allowed. He presented it as inspiration only, with no insight into judging.
- **Architecture:** 3 services from one set of images. **web** is public; **insights** is internal and holds 9 read-only analytics tools plus the agent; **ingest** is an ACA job. Data lives in Blob (Parquet plus a manifest), queried with DuckDB in memory. Foundry is called keylessly, App Insights and OpenTelemetry trace everything, and the same images run on ACA or AKS.
- **Key lessons:**
  1. **Deterministic numbers, AI for words.** Code computes every number. The model only chooses tools and writes the narrative. Facts carry **evidence IDs**, and answers are sanity-checked before display.
  2. **"Every answer carries its receipts":** a badge showing grounding, numbers checked, model, latency, tokens, cost, and caveats.
  3. **Guardrails:** at most 6 tool calls, 1,200 tokens and 45 s per answer; it refuses off-topic questions and has a content filter.
  4. **ACA over AKS for a hackathon:** less setup, ingress by toggle, scale to zero, comparable performance.
  5. **Managed identity per service,** with Entra tokens and no keys.
  6. **Copilot prompt-driven build:** a ~500-line generation prompt in `prompts/`, run phase by phase, built the app in about a day. Architecture docs live in `docs/`.
  7. **No Azure credits are provided.** Build locally (Docker Compose), deploy late, and scale to zero to keep the link cheap until Nov 10.
  8. **Credit your data sources** on the front page.

---

## 10. Our project plan: ViSense

This merges the rules above with our current concept (v2, Oct 13) and the earlier plan files. Where a choice isn't made yet, it says so.

### 10.1 What we're building
A second-screen web app for **deaf and hard-of-hearing fans**. It turns what a hearing fan gets from sound (whistles, the crowd, the commentator, announcements) into **visual and vibration cues**, plus an **AI Q&A chat** for deeper analysis. We aren't replacing captions or sign language; we're giving another way to follow the match without looking away from it.

Two parts:
1. **Cue layer ("deaf icons"):** small icons and signals that are mostly quiet. Ambient edge glow for crowd mood, a corner icon for events (whistle reason, foul, offside, VAR, card, sub), vibration on big moments (Android only; iPhone Safari doesn't support it), and a richer insight card only during stoppages.
2. **Q&A chat agent:** "why did the crowd boo?", "what did I miss?", "why was that a foul?" It answers from the stats engine through tools, with evidence event IDs ("receipts").

**The differentiator is the Attention Engine.** For every moment it decides what matters, when to show it, how (screen, vibration, ambient, save for later) and when to show nothing. It works to an attention budget: at most one signal on screen during live play.

The demo "match" is a 2D pitch replay rendered from our synthetic data, with synthetic whistle, crowd and TTS audio, all labelled synthetic (§3).

### 10.2 How it covers the five stages (§2)

| Stage | Our piece |
|---|---|
| Ingest | Replay clock streams a generated match (events, tracking, atmosphere, match state) at 1x–10x. Format: [synthetic-event-data.md](synthetic-event-data.md) |
| Interpret | Deterministic stats engine: whistle reason, momentum, pressure, crowd mood, key moments, each with evidence IDs |
| Explain | Explainer agent writes the short "why it matters" lines at stoppages. The Q&A agent answers on demand. |
| Render | Cue layer over the 2D pitch, and phone vibration. Each cue is timed JSON (`cue` stream) |
| Personalize | Accessibility profile (cue density, vibration on/off, plain language or analyst depth), favourite team, language |

### 10.3 How it scores (§5)

| Criterion | What we show |
|---|---|
| Technological implementation | A synthetic generator with sound-as-data (whistle, atmosphere) and a realism check on every field; Foundry; clean repo, tests, CI |
| Agentic design | Attention Engine plus agents (explainer, Q&A, personaliser) calling engine stats as tools or MCP; receipts on every answer |
| Real-world impact | An under-served audience; the Grand Prize text names accessibility; every input field exists in real stadium feeds |
| UX and presentation | Video shows the same clip three ways: nothing, "everything on screen", and Attention Engine |
| Category | Not chosen yet. **Best Multi-Agent System** fits if the agents really hand off; otherwise **Best Use of Foundry**. |

### 10.4 Tools (proposal, not decided)

| Layer | Must-have | Nice-to-have |
|---|---|---|
| AI service (required) | **Microsoft Foundry**: one fast model for live phrasing and Q&A, with a content filter | Agent Framework for the multi-agent orchestration; an MCP server over the stats engine |
| Hosting (required) | **Azure Container Apps**: web, engine and agents, plus a generate job, scaling to zero | Bicep or `azd` deployment |
| Data | Blob Storage for generated matches; DuckDB for Q&A queries | (We suggest dropping Event Hubs and Cosmos from the old plan: they're more than a demo needs) |
| Ops | Application Insights with OpenTelemetry: one trace per cue doubles as its "why" | |
| Build | GitHub Copilot agent mode, with the prompts kept in `prompts/` | Azure Speech for TTS commentary in the demo audio |

### 10.5 Who does what (2 people)

| | Person A: data and engine | Person B: agents and experience |
|---|---|---|
| Builds | Match generator (events, tracking, atmosphere), replay clock, stats engine, **Attention Engine rules**, Azure deploy | Foundry agents (explainer, Q&A, personaliser), cue icons and pitch UI, vibration, chat |
| Also owns | README, architecture diagram | Demo video and pitch |
| Shared contract | `event`, `insight`, `cue` schemas, with sample files committed first | |

Full rationale: [team-split-and-structure.md](team-split-and-structure.md). That file's timeline is out of date; use the one below.

### 10.6 Timeline from today (Israel time)

| When | What |
|---|---|
| **Mon Oct 19** | Both register (closes **Tue Oct 20, 22:00**). Pick the name, licence and Representative. Lock the stack. Commit the schemas and a hand-written sample match. Get a "hello world" Foundry agent running on ACA. |
| Tue Oct 20 – Thu Oct 22 | A: generator, stats and Attention Engine. B: cue UI and chat against the sample files. |
| Fri Oct 23 – Sat Oct 24 | Connect everything, deploy to Azure, fix what breaks. |
| Sun Oct 25 – Mon Oct 26 | Polish, record the video (under 2:00), write the pitch and README. (Clocks change Oct 25.) |
| **Tue Oct 27** | Submit during the day. The hard deadline is Wed Oct 28, 08:59. |
| Until **Wed Nov 11, 09:59** | Keep the live link up. |

If we fall behind, cut in this order: vibration, extra languages, the live generator (use a pre-generated match), the stoppage insight cards.

### 10.7 Still open
- Stack and category (above).
- Visual language for the icons: a small fixed set of "channels" so each is learned once.
- How much information is too much (the attention budget).
- How to show it works: a short comprehension check in the video, plus cues per minute.

### 10.8 Pre-submission checklist
- [ ] Both registered by Tue Oct 20, 22:00
- [ ] Repo public, with a licence and data credited as "synthetic, generated by our match generator"
- [ ] No PL logos or club marks, no copyrighted music
- [ ] Video under 2:00, public on YouTube or Vimeo
- [ ] Pitch names the Microsoft and Azure tech used
- [ ] Live link open and free (rate-limit the AI endpoints instead of locking access) until Wed Nov 11, 09:59
