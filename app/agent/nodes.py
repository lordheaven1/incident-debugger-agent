import os
import re
from typing import TypedDict
from dotenv import load_dotenv

from app.agent.schemas import DiagnosisReport, TriageResult
from app.agent.tools import get_recent_git_commits, read_file_snippet, search_codebase

load_dotenv()


class AgentState(TypedDict):
    fingerprint: str
    service_name: str
    environment: str
    raw_log: str
    triage: dict
    retrieved_chunks: list[dict]
    file_context: str
    git_history: str
    report: dict


def _get_candidate_models() -> list[str]:
    primary = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    extra = os.getenv(
        "GEMINI_FALLBACK_MODELS",
        "gemini-3.7-flash,gemini-3.6-flash,gemini-3.8-flash",
    )
    models = [primary] + [m.strip() for m in extra.split(",") if m.strip()]
    seen = set()
    return [m for m in models if not (m in seen or seen.add(m))]


def _build_llm(model_name: str, api_key: str):
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.0,
        timeout=25,
        max_retries=0,
    )


def _fallback_triage(service_name: str, raw_log: str) -> TriageResult:
    exc_match = re.search(r"\b([A-Za-z]+(?:Error|Exception))\b", raw_log)
    exception_type = exc_match.group(1) if exc_match else "RuntimeError"

    file_match = re.search(r"([\w./\\-]+\.py)", raw_log)
    suspected_file = file_match.group(1).replace("\\", "/") if file_match else None

    func_match = re.search(r"\bin\s+([a-zA-Z_][a-zA-Z0-9_]*)", raw_log)
    suspected_function = func_match.group(1) if func_match else None

    severity = "P1" if exception_type in {"ZeroDivisionError", "ConnectionError", "DatabaseError"} else "P2"
    search_query = f"{service_name} {exception_type} {suspected_function or ''} {raw_log[:160]}".strip()

    return TriageResult(
        severity=severity,
        exception_type=exception_type,
        suspected_file=suspected_file,
        suspected_function=suspected_function,
        search_query=search_query,
    )


async def triage_node(state: AgentState) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        result = _fallback_triage(state["service_name"], state["raw_log"])
        return {"triage": result.model_dump()}

    prompt = (
        "You are an SRE incident triage specialist. Extract the severity (P1-P4), "
        "exception type, suspected file path, suspected function name, and a concise "
        "semantic search query from this production log.\n\n"
        "Severity Rubric:\n"
        "- P1: Critical outages or systemic failures in core paths (e.g., ZeroDivisionError, "
        "ConnectionError, DatabaseError, or CRITICAL logs impacting all users).\n"
        "- P2: High-severity application errors affecting specific requests or edge cases "
        "(e.g., KeyError, ValueError, TypeError).\n"
        "- P3: Degraded performance or recoverable warnings.\n"
        "- P4: Minor or informational issues.\n\n"
        f"Service: {state['service_name']}\n"
        f"Environment: {state['environment']}\n"
        f"Raw Log:\n{state['raw_log']}"
    )

    for model_name in _get_candidate_models():
        try:
            structured_llm = _build_llm(model_name, api_key).with_structured_output(TriageResult)
            result = await structured_llm.ainvoke(prompt)
            print(f"[triage] Live LLM response from {model_name}")
            return {"triage": result.model_dump()}
        except Exception as exc:
            print(f"[triage] {model_name} unavailable ({exc})")

    print("[triage] All LLM models unavailable, falling back to deterministic parser.")
    result = _fallback_triage(state["service_name"], state["raw_log"])
    return {"triage": result.model_dump()}


async def retrieve_node(state: AgentState) -> dict:
    query = state["triage"]["search_query"]
    chunks = await search_codebase(query=query, limit=3)
    return {"retrieved_chunks": chunks}


async def inspect_node(state: AgentState) -> dict:
    triage = state["triage"]
    chunks = state["retrieved_chunks"]

    target_file = triage.get("suspected_file")
    start_line = 1
    end_line = 60

    if not target_file:
        for chunk in chunks:
            if chunk["file_path"].endswith(".py"):
                target_file = chunk["file_path"]
                start_line = max(1, chunk["start_line"] - 5)
                end_line = chunk["end_line"] + 10
                break

    if not target_file and chunks:
        target_file = chunks[0]["file_path"]

    if target_file:
        file_context = read_file_snippet(target_file, start_line=start_line, end_line=end_line)
        git_history = get_recent_git_commits(target_file, limit=3)
    else:
        file_context = "No matching source file found in repository."
        git_history = "No git history available."

    return {
        "file_context": file_context,
        "git_history": git_history,
    }


def _fallback_synthesis(state: AgentState) -> DiagnosisReport:
    triage = state["triage"]
    chunks = state["retrieved_chunks"]

    code_chunk = next((c for c in chunks if c["file_path"].endswith(".py")), None)
    runbook_chunk = next((c for c in chunks if c["file_path"].endswith(".md")), None)

    affected_file = (
        triage.get("suspected_file")
        or (code_chunk["file_path"] if code_chunk else "unknown")
    )
    affected_lines = (
        f"{code_chunk['start_line']}-{code_chunk['end_line']}"
        if code_chunk
        else "unknown"
    )

    if runbook_chunk:
        root_cause = f"{triage['exception_type']} matched runbook guidance in {runbook_chunk['file_path']}."
        suggested_fix = runbook_chunk["content"]
        confidence = 0.88
    else:
        root_cause = f"{triage['exception_type']} detected in {affected_file}."
        suggested_fix = "Add defensive input validation and guard edge-case values before execution."
        confidence = 0.65

    return DiagnosisReport(
        severity=triage["severity"],
        exception_type=triage["exception_type"],
        root_cause=root_cause,
        affected_file=affected_file,
        affected_lines=affected_lines,
        recent_commit=state["git_history"],
        suggested_fix=suggested_fix,
        confidence=confidence,
    )


async def synthesize_node(state: AgentState) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        report = _fallback_synthesis(state)
        return {"report": report.model_dump()}

    formatted_chunks = "\n\n".join(
        f"[{c['file_path']}:{c['start_line']}-{c['end_line']}]\n{c['content']}"
        for c in state["retrieved_chunks"]
    )
    prompt = (
        "You are a senior Site Reliability Engineer. Produce a precise root-cause "
        "diagnosis report grounded strictly in the retrieved code, runbooks, and git history.\n\n"
        f"Service: {state['service_name']} ({state['environment']})\n"
        f"Raw Log:\n{state['raw_log']}\n\n"
        f"Triage Classification: {state['triage']}\n\n"
        f"Retrieved Code & Runbooks:\n{formatted_chunks}\n\n"
        f"Inspected File Snippet:\n{state['file_context']}\n\n"
        f"Recent Git Commits:\n{state['git_history']}"
    )

    for model_name in _get_candidate_models():
        try:
            structured_llm = _build_llm(model_name, api_key).with_structured_output(DiagnosisReport)
            report = await structured_llm.ainvoke(prompt)
            print(f"[synthesize] Live LLM response from {model_name}")
            return {"report": report.model_dump()}
        except Exception as exc:
            print(f"[synthesize] {model_name} unavailable ({exc})")

    print("[synthesize] All LLM models unavailable, falling back to deterministic report.")
    report = _fallback_synthesis(state)
    return {"report": report.model_dump()}