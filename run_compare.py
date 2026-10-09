"""Run one LangGraph agent from openbox-barrier-demo under one integration.

The graph, tools, documents, prompt and model are identical between modes;
only the integration changes:

    langfuse   LangGraph + Langfuse CallbackHandler, no OpenBox
    openbox    LangGraph + OpenBox graph handler, no Langfuse

    uv run --project ../openbox-barrier-demo --with langfuse --with 'langchain>=1.0' \\
        python run_compare.py --mode langfuse
    uv run --project ../openbox-barrier-demo --with langfuse --with 'langchain>=1.0' \\
        python run_compare.py --mode openbox

Each run writes runs/<mode>.json (session id, Langfuse trace id, what the
agent read and filed) and keeps its output files under runs/<mode>/.

Configuration (environment variables, all optional):

    BARRIER_DEMO_DIR      path to openbox-barrier-demo   (default: ../openbox-barrier-demo)
    MODEL_SOURCE          "ollama" or "env"              (default: ollama)
    OLLAMA_BASE_URL       Ollama OpenAI-compatible URL   (default: http://127.0.0.1:11434/v1)
    OLLAMA_MODEL          model to use with Ollama       (default: llama3.2)
    LANGFUSE_HOST         Langfuse URL                   (default: http://localhost:3100)
    LANGFUSE_PUBLIC_KEY   Langfuse project public key    (default: langfuse/.env.example value)
    LANGFUSE_SECRET_KEY   Langfuse project secret key    (default: langfuse/.env.example value)

With MODEL_SOURCE=env the OpenAI key and model from the barrier demo's .env are
used as they are.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import shutil
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEMO = Path(os.environ.get("BARRIER_DEMO_DIR", HERE.parent / "openbox-barrier-demo")).resolve()
TRACE_NAMES = {"langfuse": "LangGraph + Langfuse", "openbox": "LangGraph + OpenBox"}


def _environment(mode: str) -> None:
    from dotenv import load_dotenv

    # The barrier demo's agent identities, OpenBox URL and (optionally) OpenAI key.
    load_dotenv(DEMO / ".env")
    if os.environ.get("MODEL_SOURCE", "ollama") == "ollama":
        # The agent's tool calls are scheduled by the graph; the model only
        # writes the briefing, so a small local model is enough.
        os.environ["OPENAI_BASE_URL"] = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
        os.environ["OPENAI_API_KEY"] = "ollama"
        os.environ["OPENAI_MODEL"] = os.environ.get("OLLAMA_MODEL", "llama3.2")
    # Read the demo's documents; write everything into this repo, never into the demo.
    os.environ["DOCUMENT_LIBRARY_DIR"] = str(DEMO / "documents")
    out = HERE / "runs" / mode
    shutil.rmtree(out, ignore_errors=True)
    os.environ["REPORT_OUTPUT_DIR"] = str(out / "reports")
    os.environ["FILED_DOCUMENTS_DIR"] = str(out / "filed_documents")
    # Self-hosted Langfuse from ./langfuse.
    host = os.environ.get("LANGFUSE_HOST", "http://localhost:3100")
    os.environ["LANGFUSE_HOST"] = host
    os.environ["LANGFUSE_BASE_URL"] = host
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", "pk-lf-local-compare")
    os.environ.setdefault("LANGFUSE_SECRET_KEY", "sk-lf-local-compare")


async def main(mode: str, agent: str) -> dict:
    _environment(mode)

    from langchain_openai import ChatOpenAI
    from openbox_langgraph_client_intelligence.config import AgentSettings
    from openbox_langgraph_client_intelligence.governance import build_governed_agent
    from openbox_langgraph_client_intelligence.governance_reasons import (
        OpenBoxEvaluationRecorder,
        observe_openbox_start_results,
    )
    from openbox_langgraph_client_intelligence.profiles import get_profile
    from openbox_langgraph_client_intelligence.repository import DocumentRepository
    from openbox_langgraph_client_intelligence.tools import build_document_tools
    from openbox_langgraph_client_intelligence.workflow import (
        build_research_graph,
        initial_state,
    )

    profile = get_profile(agent)
    settings = AgentSettings.from_environment(profile)
    suffix = uuid.uuid4().hex[:8]
    session_id = f"{profile.slug}-{mode}-{suffix}"
    trace_name = f"{profile.display_name} · {TRACE_NAMES[mode]}"

    repository = DocumentRepository(
        settings.document_library_dir, settings.report_output_dir, settings.filed_documents_dir
    )
    evaluations = OpenBoxEvaluationRecorder()
    tools = build_document_tools(
        repository, agent_slug=profile.slug, governance_failure_sink=evaluations.record_exception
    )
    model = ChatOpenAI(model=settings.openai_model, temperature=0, disable_streaming=True)
    graph = build_research_graph(
        profile,
        tools,
        model,
        governance_reason_lookup=evaluations.reason_for,
        governance_evaluation_lookup=evaluations.evaluation_for,
    )

    runnable = graph
    callbacks: list = []
    langfuse = None
    if mode == "openbox":
        runnable = build_governed_agent(
            graph,
            profile,
            settings,
            session_id=session_id,
            multi_agent_session_id=f"compare-{suffix}",
        )
        observe_openbox_start_results(runnable, evaluations)
    else:
        from langfuse import get_client
        from langfuse.langchain import CallbackHandler

        langfuse = get_client()
        callbacks.append(CallbackHandler())

    outcome: dict = {"mode": mode, "agent": profile.slug, "session_id": session_id}
    with contextlib.ExitStack() as stack:
        if langfuse is not None:
            from langfuse import propagate_attributes

            stack.enter_context(
                langfuse.start_as_current_observation(
                    name=trace_name, as_type="agent", input={"assignment": profile.assignment}
                )
            )
            stack.enter_context(
                propagate_attributes(
                    trace_name=trace_name, session_id=session_id, tags=[mode, profile.slug]
                )
            )
        try:
            result = await runnable.ainvoke(
                initial_state(profile),
                config={
                    "configurable": {"thread_id": session_id},
                    "recursion_limit": 50,
                    "callbacks": callbacks,
                    "run_name": trace_name,
                },
            )
            outcome["status"] = "completed"
            outcome["read"] = [
                e.get("document_id") if isinstance(e, dict) else str(e)
                for e in result.get("evidence", [])
            ]
            outcome["unavailable"] = result.get("unavailable", [])
            outcome["filed"] = [
                {"client": f.get("client_name"), "status": f.get("status"),
                 "destination": f.get("destination_document_id")}
                for f in result.get("filing_results", [])
            ]
        except Exception as exc:
            outcome["status"] = f"stopped: {type(exc).__name__}: {exc}"
        if langfuse is not None:
            outcome["langfuse_trace_id"] = langfuse.get_current_trace_id()
    if langfuse is not None:
        langfuse.flush()

    out = HERE / "runs" / f"{mode}.json"
    out.write_text(json.dumps(outcome, indent=2, default=str))
    return outcome


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=sorted(TRACE_NAMES), required=True)
    parser.add_argument("--agent", default="amy", help="barrier-demo agent: amy, barry or colin")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(main(args.mode, args.agent)), indent=2, default=str))
