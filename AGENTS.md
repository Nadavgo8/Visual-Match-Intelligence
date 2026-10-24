# Repository instructions

Read [CLAUDE.md](CLAUDE.md) for shared project context, then the documents relevant to the task. Shared setup, test commands, coverage gate, schemas and CI for every tool: [02-SETUP-AND-GIT.md](docs/implementation/02-SETUP-AND-GIT.md). Reply in the user's language; code, file names, product UI and submission materials are English.

## Active plan and scope

- The active plan is [VMI-FINAL-PLAN-F.md](docs/implementation/VMI-FINAL-PLAN-F.md). Its explicit decisions take precedence over older product summaries: 2D demo, delayed linked generator xG, and no permanent model/runtime choice before D2-00.
- Execute only the authorized task. Writing or updating the plan does not authorize implementing the entire product.
- Keep implementation, meaningful tests, fixes and review for one task in the same PR. A separate tests-only PR needs an independently useful scope, not merely a failing test. Diagnose routine failures before escalating a purported product decision.
- Each new task branch starts from updated `main`; wait for dependent PRs to merge. Commit bodies explain what changed, why, validation and remaining limits. Consult the work board and handoff for the latest authorized next step.
- Zero extra cost is mandatory. Do not start paid services, billing trials, paid fallbacks or quota overages.

## Mandatory quality and Git workflow

Follow [12-QUALITY-AND-GIT-GATES.md](docs/implementation/12-QUALITY-AND-GIT-GATES.md) for every branch and every stage transition.

- Inspect Git status, current branch, task ownership and dependencies before changes. Preserve unrelated work and the other developer's changes.
- Work on a task branch, never directly on `main`. Use separate worktrees/checkouts for concurrent editors; do not rewrite shared history or force-push.
- For each meaningful behavior change, add focused unit tests, run affected tests and review the code and tests before a dependent work step. Test requirements and observable behavior, including failure paths and boundaries.
- Run the full existing suite on every branch, including documentation branches. Do not add artificial unit tests for prose-only edits; verify links, commands and consistency as well.
- Before merge, record tested SHA, exact commands and real results, resolve all P0/P1/P2 findings, and record a technical PASS on the tested SHA. The user authorizes automatic session-driven squash merge after tests and code review pass; routine human approval is not required. Never invent a human approval or an independent reviewer.
- Rerun after fixes or synchronization. After squash merge, verify the integrated `main` before marking a task DONE. Between stages, require technical review of accumulated changes and tests on the same integrated SHA.
- Never invent a PASS, reviewer, approval, coverage percentage or CI state. A blocked or unrun test remains explicit and blocks the corresponding gate; independent work may continue.
- After a finding, record its cause, a regression test and a focused improvement to the next review. Do not weaken assertions or thresholds to obtain green checks.
- CI, coverage gates, frontend test tooling and branch protections are D2-01 implementation requirements until actual configuration and verification exist. A Markdown policy does not activate them.

- Follow policy section 7.3: fix the tested HEAD and base, run actual required tests, review the full diff and evidence, resolve blocking findings and discussions, recheck HEAD/base, merge with matching HEAD without bypasses, and test merged main. This is active-session automation, not an unattended background service. An empty CI list is not a PASS.
