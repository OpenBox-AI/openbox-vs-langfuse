#!/usr/bin/env bash
# Print the OpenBox agent id and session id of the latest `openbox` run,
# read from the local stack's Postgres. Usage: scripts/find_openbox_ids.sh
set -euo pipefail
cd "$(dirname "$0")/.."
PG="${OPENBOX_PG_CONTAINER:-openbox-local-postgres-1}"
RUN=$(python3 -c "import json;print(json.load(open('runs/openbox.json'))['session_id'])")
docker exec "$PG" psql -U postgres -d openbox -At -F' ' -c \
  "select '--agent-id ' || agent_id || ' --session-id ' || id from sessions
   where workflow_id like '${RUN}-%' order by created_at desc limit 1"
