#!/usr/bin/env bash
set -euo pipefail

curl -X POST \
  -H "X-OpsLens-Maintenance-Key: ${OPSLENS_MAINTENANCE_KEY}" \
  "https://api.app-sync.com/api/v1/tickets/auto-resolve?quiet_hours=24&max_records=200"