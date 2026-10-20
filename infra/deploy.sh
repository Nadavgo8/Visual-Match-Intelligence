#!/usr/bin/env bash
# Deploy Visual Match Intelligence to Azure Container Apps with Application Insights
# and keyless (managed identity) access to Microsoft Foundry.
#
# Prereqs: az CLI logged in (`az login`), the containerapp and application-insights
# extensions, and a Foundry project with a model deployment.
#
#   export FOUNDRY_PROJECT_ENDPOINT="https://<resource>.services.ai.azure.com/api/projects/<project>"
#   export FOUNDRY_MODEL="gpt-5-mini"                      # a deployment that won't retire before judging ends
#   export FOUNDRY_RESOURCE_ID="/subscriptions/.../resourceGroups/.../providers/Microsoft.CognitiveServices/accounts/<resource>"
#   ./infra/deploy.sh
set -euo pipefail

RG=${RG:-vmi-rg}
LOC=${LOC:-swedencentral}
APP=${APP:-vmi}
ENVNAME=${ENVNAME:-vmi-env}
: "${FOUNDRY_PROJECT_ENDPOINT:?set FOUNDRY_PROJECT_ENDPOINT}"
: "${FOUNDRY_MODEL:?set FOUNDRY_MODEL}"
: "${FOUNDRY_RESOURCE_ID:?set FOUNDRY_RESOURCE_ID}"

az extension add --name containerapp --upgrade -y >/dev/null
az extension add --name application-insights --upgrade -y >/dev/null

az group create -n "$RG" -l "$LOC" -o none

echo "== Application Insights"
az monitor app-insights component create -a "$APP-ai" -g "$RG" -l "$LOC" --kind web -o none
AI_CONN=$(az monitor app-insights component show -a "$APP-ai" -g "$RG" --query connectionString -o tsv)

echo "== Build and deploy the container (Container Apps builds the Dockerfile)"
az containerapp up -n "$APP" -g "$RG" -l "$LOC" --environment "$ENVNAME" \
  --source . --ingress external --target-port 8000

echo "== Managed identity -> Foundry (no keys)"
PRINCIPAL=$(az containerapp identity assign -n "$APP" -g "$RG" --system-assigned --query principalId -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role "Azure AI User" --scope "$FOUNDRY_RESOURCE_ID" -o none || \
  echo "!! role assignment failed: grant 'Azure AI User' on the Foundry resource to $PRINCIPAL by hand"

echo "== Settings"
# One replica: rooms (a TV and its phones) live in memory, and min 1 avoids a 15-25 s cold start for judges.
az containerapp update -n "$APP" -g "$RG" --min-replicas 1 --max-replicas 1 --cpu 0.5 --memory 1Gi \
  --set-env-vars FOUNDRY_PROJECT_ENDPOINT="$FOUNDRY_PROJECT_ENDPOINT" FOUNDRY_MODEL="$FOUNDRY_MODEL" \
                 APPLICATIONINSIGHTS_CONNECTION_STRING="$AI_CONN" VMI_DEMO_SEED=12 -o none

URL=$(az containerapp show -n "$APP" -g "$RG" --query properties.configuration.ingress.fqdn -o tsv)
echo "Live at https://$URL  (health: https://$URL/api/health should say agents: foundry)"
