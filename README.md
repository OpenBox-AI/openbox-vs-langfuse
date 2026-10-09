# OpenBox vs Langfuse: observability on the same LangGraph agent

One LangGraph agent, run twice. Run 1 is wired to Langfuse only, run 2 is wired to OpenBox only.
The graph, tools, documents, prompt and model are identical, and so is the work the agent does: 3
searches, 3 document reads, 1 briefing, 4 filings (11 tool calls). The question is what each platform records and what its dashboard shows.

**Report:** [`OpenBox-vs-Langfuse-Observability.pdf`](OpenBox-vs-Langfuse-Observability.pdf) (4 pages, A4).
The same content as a web page is in [`report/index.html`](report/index.html).

## Results (9 Oct 2026)

| | LangGraph + Langfuse | LangGraph + OpenBox |
|---|---|---|
| Records | 56 observations | 27 governance events + 14 spans + 1 signed session record |
| Graph steps (nodes and routers) | 43, plus an auto-drawn graph | Not recorded; tool and LLM activities only |
| Tool calls | 11, with input and full output | 12 tool and LLM calls with input and a verdict; no tool output |
| LLM call | Parsed: messages, model, temperature, 633 in / 288 out tokens | Raw HTTP: request and response bodies, headers (auth redacted), status |
| Files the agent touched | Not visible | 8 reads and 5 writes, with real path, mode and bytes |
| Outbound network | LLM calls only | Every HTTP request the process makes |
| Decision per call | — | Verdict on every event and every span |
| Tamper-evidence | — | Merkle root over 55 leaves (27 events + 14 spans × started/completed), 27-link hash chain, RSA-SHA256 |
| Prompt management, evals, datasets | Yes | — |

The two overlap on the agent-level trace. Langfuse goes deeper into the framework. OpenBox goes deeper into
the running process, and adds a decision, an agent identity and a verifiable record on top.

## What's in this repo

| Path | What it is |
|---|---|
| `run_compare.py` | Runs the agent in one mode: `--mode langfuse` or `--mode openbox` |
| `langfuse/` | Self-hosted Langfuse (upstream compose file, ports moved off OpenBox's) |
| `scripts/count_langfuse.sh`, `scripts/count_openbox.sh` | Read each platform's own store and print the numbers in the table above |
| `scripts/find_openbox_ids.sh` | Prints the OpenBox agent and session ids of the latest run |
| `capture/langfuse.py`, `capture/openbox.py` | Take the dashboard screenshots |
| `capture/open_chrome.sh` | Opens a Chrome window for signing in to OpenBox before `capture/openbox.py` |
| `screenshots/` | Full-size screenshots from the run in the report |
| `report/` | The report page, its images, and `render_pdf.py` |

## Setup

### 1. Prerequisites

- macOS or Linux, with Docker (Docker Desktop or Colima). Give it at least **8 GB of memory**: Langfuse
  (ClickHouse, Postgres, MinIO, Redis) and the local OpenBox stack (Keycloak, Postgres, Temporal) run together.
  With Colima: `colima start --cpu 4 --memory 8`.
- [`uv`](https://docs.astral.sh/uv/) and Python 3.12.
- [Ollama](https://ollama.com) with `llama3.2`: `ollama pull llama3.2`. (Or use an OpenAI key, see below.)
- Read access to the `OpenBox-AI` GitHub org.

### 2. Clone this repo next to the agent

The agent is the client-intelligence demo in `openbox-barrier-demo`. Clone it as a sibling of this repo:

```bash
git clone https://github.com/OpenBox-AI/openbox-barrier-demo.git
git -C openbox-barrier-demo checkout c7ca6fb   # the commit the report was run on
git clone https://github.com/OpenBox-AI/openbox-vs-langfuse.git
uv sync --project openbox-barrier-demo
```

If the demo lives somewhere else, set `BARRIER_DEMO_DIR=/path/to/openbox-barrier-demo`.

### 3. Run OpenBox

The report was run against a local OpenBox stack on `develop`. Follow `LOCAL_SETUP.md` in the OpenBox
workspace (`openbox-local.sh start`), register an org and sign in. The dashboard is then at
http://localhost:3233, core at http://localhost:8086.

A hosted environment works too: point `OPENBOX_API_URL` at its core URL, and set `OPENBOX_DASHBOARD_URL` to
its dashboard when taking screenshots. The count and id scripts read the local stack's Postgres, so on a
hosted environment take the numbers from the dashboard instead.

### 4. Create the agent and configure the demo

In the OpenBox dashboard, create an agent named `AmyClientIntelligenceAgent` and copy its API key. The
report used an agent with **no policies**, so nothing is blocked and both runs do the same work.

```bash
cd openbox-barrier-demo
cp .env.example .env
```

Fill in `OPENBOX_API_URL`, `AMY_OPENBOX_AGENT_NAME` and `AMY_OPENBOX_API_KEY` (and
`AMY_OPENBOX_WORKLOAD_PRIVATE_KEY` if your agent uses workload signing). The OpenAI values can stay empty
when you use Ollama. `run_compare.py` overrides the document and output folders itself, so the demo's own
folders are never written to.

### 5. Start Langfuse

```bash
cd openbox-vs-langfuse/langfuse
cp .env.example .env
docker compose -p langfuse-compare up -d
curl -s http://localhost:3100/api/public/health     # {"status":"OK",...}
```

The `.env` creates an org, a project (`policy-studio`), API keys and a user on first start. Sign in at
http://localhost:3100 as `demo@openbox.local` / `compare-demo-123`. These are throwaway local values;
change them in `.env` before the first start if the instance is reachable by anyone else.

## Rerun the test

From the repo root.

**Run 1, LangGraph + Langfuse:**

```bash
uv run --project ../openbox-barrier-demo --with langfuse --with 'langchain>=1.0' \
  python run_compare.py --mode langfuse
```

**Run 2, LangGraph + OpenBox:**

```bash
uv run --project ../openbox-barrier-demo --with langfuse --with 'langchain>=1.0' \
  python run_compare.py --mode openbox
```

Each run takes about a minute and prints what the agent read and filed. Both should show the same 3 reads
and 4 filings with status `committed`. The run's ids go to `runs/<mode>.json`, and its output files to
`runs/<mode>/`.

**Check the numbers:**

```bash
scripts/count_langfuse.sh     # observations by type, graph steps, LLM tokens
scripts/count_openbox.sh      # events by type, file and HTTP spans, signed record
```

Expected: Langfuse `CHAIN 43, TOOL 11, GENERATION 1, AGENT 1` and `633 / 288` tokens with llama3.2.
OpenBox `ActivityStarted 12, ActivityCompleted 12` plus 3 session events, spans `file.read 8, file.write 5,
HTTP POST 1`, and a Merkle root over 55 leaves: the 27 events plus 28 span records (each of the 14 spans
is signed when it starts and when it completes). Token counts vary with the model; the structure does not.

### Use OpenAI instead of Ollama

Put `OPENAI_API_KEY` and `OPENAI_MODEL` in the demo's `.env` and run with `MODEL_SOURCE=env`:

```bash
MODEL_SOURCE=env uv run --project ../openbox-barrier-demo --with langfuse --with 'langchain>=1.0' \
  python run_compare.py --mode langfuse
```

Only the briefing text comes from the model. The tool calls are scheduled by the graph, so the outcome and
the counts are the same with any model. With a priced model Langfuse also shows cost.

### Other options

| Variable | Default | Purpose |
|---|---|---|
| `BARRIER_DEMO_DIR` | `../openbox-barrier-demo` | Where the agent lives |
| `MODEL_SOURCE` | `ollama` | `ollama`, or `env` to use the demo's OpenAI settings |
| `OLLAMA_BASE_URL` / `OLLAMA_MODEL` | `http://127.0.0.1:11434/v1` / `llama3.2` | Local model |
| `LANGFUSE_HOST` | `http://localhost:3100` | Langfuse URL |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | values in `langfuse/.env.example` | Langfuse project keys |

`--agent barry` or `--agent colin` runs one of the demo's other agents (they need their own OpenBox agent
and keys in the demo's `.env`).

## Retake the screenshots

Install the browser once: `uv run --with playwright playwright install chromium`. To use an existing
Chromium instead, set `CHROMIUM_PATH`.

**Langfuse** (signs in by itself):

```bash
uv run --with playwright python capture/langfuse.py
```

**OpenBox.** The dashboard asks for a password on every new login, so the script attaches to a browser you
sign in to yourself:

```bash
capture/open_chrome.sh &                  # sign in, leave the window open
uv run --with playwright python capture/openbox.py $(scripts/find_openbox_ids.sh)
```

`open_chrome.sh` uses Google Chrome; set `CHROME_PATH` for another Chromium build. Screenshots are written to
`screenshots/`; set `SCREENSHOT_DIR` to write them elsewhere.

**Rebuild the PDF** after editing `report/index.html` or swapping images in `report/obs/`:

```bash
uv run --with playwright python report/render_pdf.py
```

## Where to look in each dashboard

| Data | Langfuse | OpenBox |
|---|---|---|
| Run timeline | Tracing → the trace → Tree / Timeline | Agents → agent → Sessions → session → replay |
| Graph of the agent | Tracing → the trace → Graph | — |
| LLM call | Trace tree → `ChatOpenAI` | Verify → Tree View → Expand All → `llm_call` → `http_post` span |
| Files read and written | — | Verify → Tree View → Expand All → `file_read` / `file_write` spans |
| Integrity check | — | Agents → agent → Verify (Merkle root, hash chain, signatures) |
| Usage dashboards | Home | Agents → agent → Overview |

## Notes and limits

- The OpenBox agent overview shows 7-day totals per agent, so earlier runs of the same agent are included.
  In the report run its token panel did not count the local llama3.2 call.
- OpenBox's file capture records everything the process opens, including reads the agent's code did not
  ask for (Python's `platform` module reading `SystemVersion.plist` on macOS).
- The documents are fictional demo files from `openbox-barrier-demo`. The company names in them (Coca-Cola,
  Dell, Staples) are real brands used as placeholders; nothing in them comes from those companies.

## Tear down

```bash
docker compose -p langfuse-compare down        # keeps Langfuse's data volumes
docker compose -p langfuse-compare down -v     # removes them too
```
