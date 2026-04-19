#!/usr/bin/env bash
set -euo pipefail

api_base_url="${OPSLENS_API_BASE_URL:-https://api.app-sync.com}"
quiet_hours="${OPSLENS_AUTO_RESOLVE_QUIET_HOURS:-24}"
max_records="${OPSLENS_AUTO_RESOLVE_MAX_RECORDS:-200}"

api_base_url="${api_base_url%/}"

curl --fail --show-error --silent \
  --retry 3 \
  --retry-all-errors \
  --connect-timeout 10 \
  --max-time 120 \
  -X POST \
  -H "X-OpsLens-Maintenance-Key: ${OPSLENS_MAINTENANCE_KEY}" \
  "${api_base_url}/api/v1/tickets/auto-resolve?quiet_hours=${quiet_hours}&max_records=${max_records}"
