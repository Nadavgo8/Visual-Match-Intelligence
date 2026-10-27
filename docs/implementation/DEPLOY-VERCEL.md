# Deploying on Vercel: two known risks and their fixes

## Live deployment (27.10.2026): Azure App Service

**Judges' link: https://vmi-match.azurewebsites.net** (`/tv` on a laptop, `/app` on a phone, same room code).

We deployed on Azure, not Vercel. Container Apps (`infra/deploy.sh`) could not build: Free Trial subscriptions refuse ACR Tasks (`TasksOperationsNotAllowed`), and there is no local Docker. App Service builds from source itself, so `infra/deploy-appservice.sh` deploys there instead. It uses one always-on B1 instance, so rooms stay in one memory with no time limit (risk 2 below does not apply), and a system-assigned managed identity, so no secret (risk 1 below does not apply). It runs on the Free Trial credit; the script refuses to run unless the spending limit is On. Rerun the script to redeploy the current checkout.

Checked on the live site, 27.10: `/api/health` answers `agents: foundry`; a TV and a phone share one room (same seed and run); the phone cannot control playback; a reconnecting phone gets the current state and feed.

**Open:** the app's identity needs two roles on the Foundry resource before answers come from the model. The script's role step failed under Git Bash (it rewrote the `/subscriptions/...` scope into a file path; now fixed with `MSYS_NO_PATHCONV=1`). Run once, as the subscription owner, in PowerShell:

```powershell
foreach ($r in 'Cognitive Services User','Azure AI Developer') { az role assignment create --assignee-object-id 844bc951-6403-4286-8338-faaa31065e52 --assignee-principal-type ServicePrincipal --role $r --scope /subscriptions/3abad52b-7c6c-4f6d-b811-e19bb8d58acd/resourceGroups/vmi-rg/providers/Microsoft.CognitiveServices/accounts/vmi-foundry-nadav }
```

Then the Ask test below must show `· AI`. Before that it shows `· written by code` (checked: `source: local`). The same question against Foundry from a local server answered from the model (`source: agent`, gpt-5-mini, 17.6 s), so the code path works.

The rest of this file is the original Vercel analysis, kept for reference.

Written 26.10.2026 for the D2-06 deploy. The app was built as one long-running server (FastAPI + WebSocket rooms in memory) with keyless access to Microsoft Foundry. On Vercel, two things work differently. Each section below gives the risk, a 2-minute test, and the fix.

Azure resources already created (Free Trial, spending limit On, so nothing can bill a card):

| What | Value |
|---|---|
| Resource group | `vmi-rg` (Sweden Central) |
| Foundry resource | `vmi-foundry-nadav` |
| Project endpoint | `https://vmi-foundry-nadav.services.ai.azure.com/api/projects/vmi` |
| Model deployment | `gpt-5-mini` |
| Resource ID | `/subscriptions/3abad52b-7c6c-4f6d-b811-e19bb8d58acd/resourceGroups/vmi-rg/providers/Microsoft.CognitiveServices/accounts/vmi-foundry-nadav` |

## Risk 1: the AI silently doesn't answer

**Why.** The app logs in to Foundry with `DefaultAzureCredential`, which needs an Azure identity. Locally that's your `az login`; on Azure Container Apps it's the app's managed identity. Vercel has neither. The Foundry call then fails, the app falls back to code-written answers, and nothing visibly breaks.

**Fix: give the app its own Azure identity (a service principal).** Run once, signed in with `az login` as the subscription owner:

```bash
az ad sp create-for-rbac --name vmi-vercel \
  --role "Cognitive Services User" \
  --scopes /subscriptions/3abad52b-7c6c-4f6d-b811-e19bb8d58acd/resourceGroups/vmi-rg/providers/Microsoft.CognitiveServices/accounts/vmi-foundry-nadav
```

It prints `appId`, `password` and `tenant`. In Vercel → Project → Settings → Environment Variables, add:

| Variable | Value |
|---|---|
| `AZURE_CLIENT_ID` | `appId` from the output |
| `AZURE_CLIENT_SECRET` | `password` from the output |
| `AZURE_TENANT_ID` | `tenant` from the output |
| `FOUNDRY_PROJECT_ENDPOINT` | the project endpoint above |
| `FOUNDRY_MODEL` | `gpt-5-mini` |
| `VMI_WARM_DEMO` | `0` (no batch of model calls at every cold start) |

Then redeploy. No code changes: `DefaultAzureCredential` picks these variables up by itself.

- The secret is a password. Keep it only in Vercel's settings, never in the repo (it will be public) or in chat.
- Role changes can take a few minutes to apply.
- If the secret ever leaks: `az ad sp credential reset --id <appId>`, then update Vercel.

**Test (2 minutes).** On the deployed URL, open `/app?room=test`, go to Ask, and ask "What's the score?".

- **Working:** the answer is model-written and arrives in a few seconds. With the technical line shown (or in the browser console), the source is the agent on `gpt-5-mini`.
- **Not working:** the answer arrives instantly and reads like the template ("Harbour City 1–0 Northvale Rovers, 24:59 on the clock…"), with a fallback reason such as `agent error`. Check the five variables and the role assignment.

`/api/health` saying `"agents": "foundry"` only means the variables are set. It does not prove the login works; the Ask test does.

## Risk 2: the TV and the phone don't see the same match

**Why.** A room (one TV and its phones) lives in the server's memory, and a 20 Hz loop moves the match forward. Vercel runs functions, possibly several copies, and pins each WebSocket to one copy until that function's time limit ends. So:

- the TV and the phone can land on **different copies**, and the phone sees an empty room or a different match;
- a long session can be **cut off** at the time limit; the client reconnects, maybe onto a fresh copy with no match in it.

**Test (10 minutes).** On the deployed URL:

1. Laptop: open `/tv?room=judge1` and press Play.
2. Phone: open `/app?room=judge1`.
3. Check for at least 10 minutes:
   - the phone's score and clock follow the TV;
   - goals and other big moments appear in the phone's feed;
   - "What did I miss?" answers;
   - the TV doesn't show "disconnected" over and over.

Repeat once with a second laptop or browser opening the same room, to check two connections share one room.

**Fixes, simplest first:**

1. **Raise the function time limit** in the Vercel project settings (Functions → Max Duration), as high as the free plan allows. This helps with dropped sessions, but not with different copies.
2. **If the phone still doesn't follow the TV, don't patch it on Vercel.** Making rooms work across copies means moving them to an external store, which is a rebuild. Use the ready alternative instead.

**Ready alternative: Azure Container Apps.** One always-on copy (so one shared memory) and a managed identity (so no secret at all). Run once:

```bash
az provider register -n Microsoft.OperationalInsights --wait
az provider register -n Microsoft.App --wait
az provider register -n Microsoft.ContainerRegistry --wait

export FOUNDRY_PROJECT_ENDPOINT="https://vmi-foundry-nadav.services.ai.azure.com/api/projects/vmi"
export FOUNDRY_MODEL="gpt-5-mini"
export FOUNDRY_RESOURCE_ID="/subscriptions/3abad52b-7c6c-4f6d-b811-e19bb8d58acd/resourceGroups/vmi-rg/providers/Microsoft.CognitiveServices/accounts/vmi-foundry-nadav"
bash infra/deploy.sh
```

The script refuses to run unless the subscription's spending limit is On. It prints the live URL at the end. Run the same two tests on it.

## Before submitting

- [ ] Ask test: answers come from the model, not the template.
- [ ] Two-screen test: 10+ minutes, the phone follows the TV.
- [ ] No secret in the repo: `git grep -n "AZURE_CLIENT_SECRET="` finds nothing.
- [ ] The link opens in a private window (judges aren't signed in).
- [ ] The deployment stays up until Nov 10, 23:59 PT. The Azure credit lasts 30 days from sign-up, past that date.
