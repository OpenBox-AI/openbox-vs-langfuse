#!/usr/bin/env bash
# Count what OpenBox stored for the `openbox` run: governance events, spans and
# the signed session record. Reads the local stack's Postgres.
set -euo pipefail
cd "$(dirname "$0")/.."
PG="${OPENBOX_PG_CONTAINER:-openbox-local-postgres-1}"
RUN=$(python3 -c "import json;print(json.load(open('runs/openbox.json'))['session_id'])")
q() { docker exec "$PG" psql -U postgres -d openbox -At -F' | ' -c "$1"; }
S=$(q "select id from sessions where workflow_id like '${RUN}-%' order by created_at desc limit 1")
echo "== governance events by type (session $S)"
q "select event_type, count(*) from governance_events where session_id='$S' group by 1 order by 2 desc"
echo "== completed spans by name"
q "select name, count(*) from spans where session_id='$S' and stage='completed' group by 1 order by 2 desc"
echo "== file and HTTP spans"
q "select name, coalesce(attributes->>'file.path', attributes->>'url.full') from spans where session_id='$S' and stage='completed' order by start_time"
echo "== signed session record"
q "select 'merkle root ' || encode(merkle_root,'hex') || ', leaves ' || event_count || ', signature bytes ' || length(signature) from session_attestations where session_id='$S'"
