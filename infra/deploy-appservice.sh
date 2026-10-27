#!/usr/bin/env bash
# Deploy Visual Match Intelligence to Azure App Service (Linux, Python 3.12) with
# keyless (managed identity) access to Microsoft Foundry.
#
# Why not deploy.sh (Container Apps)? Free Trial subscriptions refuse ACR Tasks, so
# `az containerapp up --source` cannot build the image. App Service builds from source
# itself. One always-on B1 instance keeps rooms (a TV and its phones) in one memory.
#
#   export FOUNDRY_PROJECT_ENDPOINT="https://<resource>.services.ai.azure.com/api/projects/<project>"
#   export FOUNDRY_MODEL="gpt-5-mini"
#   export FOUNDRY_RESOURCE_ID="/subscriptions/.../providers/Microsoft.CognitiveServices/accounts/<resource>"
#   bash infra/deploy-appservice.sh            # rerun to redeploy the current checkout
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash on Windows would rewrite /subscriptions/... scopes into file paths
AZ=${AZ:-az}

RG=${RG:-vmi-rg}
LOC=${LOC:-swedencentral}
PLAN=${PLAN:-vmi-plan}
APP=${APP:-vmi-match}
: "${FOUNDRY_PROJECT_ENDPOINT:?set FOUNDRY_PROJECT_ENDPOINT}"
: "${FOUNDRY_MODEL:?set FOUNDRY_MODEL}"
: "${FOUNDRY_RESOURCE_ID:?set FOUNDRY_RESOURCE_ID}"

# Zero cost: only deploy to a subscription whose spending limit is On (Free Trial).
LIMIT=$($AZ rest --method get --url "https://management.azure.com/subscriptions/{subscriptionId}?api-version=2022-12-01" \
  --query subscriptionPolicies.spendingLimit -o tsv)
if [ "$LIMIT" != "On" ]; then
  echo "!! spending limit is '$LIMIT', not On: this subscription could bill a card. Stopping."
  exit 1
fi

ROOT=$(cd "$(dirname "$0")/.." && pwd)
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
# Ship what the Dockerfile ships; the exact tested versions become requirements.txt.
cp -r "$ROOT/vmi" "$ROOT/web" "$ROOT/prompts" "$STAGE/"
cp "$ROOT/requirements-lock.txt" "$STAGE/requirements.txt"
find "$STAGE" -name __pycache__ -type d -prune -exec rm -rf {} +
(cd "$STAGE" && python -c "import shutil; shutil.make_archive('../vmi-site', 'zip', '.')")
ZIP="$(dirname "$STAGE")/vmi-site.zip"

if ! $AZ webapp show -g "$RG" -n "$APP" -o none 2>/dev/null; then
  echo "== Create plan and app"
  $AZ appservice plan create -g "$RG" -n "$PLAN" -l "$LOC" --is-linux --sku B1 -o none
  $AZ webapp create -g "$RG" -p "$PLAN" -n "$APP" --runtime "PYTHON:3.12" -o none

  echo "== Managed identity -> Foundry (no keys)"
  PRINCIPAL=$($AZ webapp identity assign -g "$RG" -n "$APP" --query principalId -o tsv)
  for ROLE in "Cognitive Services User" "Azure AI Developer"; do
    $AZ role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
      --role "$ROLE" --scope "$FOUNDRY_RESOURCE_ID" -o none || \
      echo "!! role assignment failed: grant '$ROLE' on the Foundry resource to $PRINCIPAL by hand"
  done
fi

echo "== Settings"
AI_CONN=$($AZ monitor app-insights component show -a vmi-ai -g "$RG" --query connectionString -o tsv 2>/dev/null || true)
$AZ webapp config set -g "$RG" -n "$APP" --web-sockets-enabled true --always-on true --http20-enabled false \
  --startup-file "python -m uvicorn vmi.api.server:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*" -o none
$AZ webapp config appsettings set -g "$RG" -n "$APP" -o none --settings \
  WEBSITES_PORT=8000 SCM_DO_BUILD_DURING_DEPLOYMENT=true \
  FOUNDRY_PROJECT_ENDPOINT="$FOUNDRY_PROJECT_ENDPOINT" FOUNDRY_MODEL="$FOUNDRY_MODEL" \
  VMI_DEMO_SEED=2 ${AI_CONN:+APPLICATIONINSIGHTS_CONNECTION_STRING="$AI_CONN"}

echo "== Deploy code (App Service installs requirements.txt)"
$AZ webapp deploy -g "$RG" -n "$APP" --src-path "$ZIP" --type zip -o none
rm -f "$ZIP"

URL=$($AZ webapp show -g "$RG" -n "$APP" --query defaultHostName -o tsv)
echo "Live at https://$URL  (health: https://$URL/api/health should say agents: foundry)"
