#!/usr/bin/env bash
# Count what Langfuse stored for the `langfuse` run, by observation type, plus
# the LLM generation's model and token usage. Reads Langfuse's ClickHouse.
set -euo pipefail
cd "$(dirname "$0")/.."
CH="${LANGFUSE_CH_CONTAINER:-langfuse-compare-clickhouse-1}"
TRACE=$(python3 -c "import json;print(json.load(open('runs/langfuse.json'))['langfuse_trace_id'])")
q() { docker exec "$CH" clickhouse-client --user clickhouse --password clickhouse -q "$1"; }
echo "== observations by type (trace $TRACE)"
q "select type, count() from events_core where trace_id='$TRACE' group by type order by 2 desc"
echo "== graph steps by name"
q "select name, count() from events_core where trace_id='$TRACE' and type='CHAIN' group by name order by 2 desc"
echo "== LLM generation"
q "select provided_model_name, usage_details, model_parameters from events_core where trace_id='$TRACE' and type='GENERATION'"
