"""
LLM-driven chat agent — THINK → Action → Observe loop.

The SLM decides whether to retrieve filing chunks, fetch external data, run
comparative analysis, or answer directly. No rule-based routing.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from backend.agents.financial_agent import financial_agent
from backend.agents.llm_client import llm_client
from backend.agents.slm_system_prompts import SlmRole, compose_slm_prompt, user_query_reminder
from backend.agents.validator_agent import validator_agent
from backend.config import get_settings
from backend.guardrails import guardrails
from backend.rag.citation_sources import (
    citation_from_chroma_chunk,
    citation_from_scraped_context,
    summarize_source_types,
)
from backend.rag.chat_comparison import _format_comparison_answer
from backend.rag.chunking import split_text_into_chunks
from backend.tools.chroma_tool import chromadb_manager
from backend.tools.scrape_plan import is_plausible_peer_name
from backend.tools.scraper import financial_scraper

logger = logging.getLogger(__name__)

# Tool catalog surfaced to the SLM each step
AGENT_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "rag_retrieve",
        "description": (
            "Semantic search over the uploaded filing stored in ChromaDB. "
            "Use first for questions answerable from the PDF (risks, competitors "
            "named in the filing, MD&A, performance narrative)."
        ),
        "parameters": {
            "query": "Search query (defaults to user question)",
            "n_results": "Number of chunks (1-8, default 4)",
        },
    },
    {
        "name": "get_report_summary",
        "description": (
            "Structured pipeline output for the uploaded company: executive summary, "
            "risk list, sentiment score, MD&A highlights — no external fetch."
        ),
        "parameters": {},
    },
    {
        "name": "sec_filing_fetch",
        "description": (
            "Download latest SEC filing (10-K/10-Q) for a named US public company. "
            "Use when the user names a peer ticker/company or comparison needs external filing text."
        ),
        "parameters": {
            "company": "Company name or ticker (required)",
            "filing_type": "10-K or 10-Q (default 10-K)",
        },
    },
    {
        "name": "prior_filing_fetch",
        "description": (
            "Download prior-year SEC filing for trend / YoY comparison."
        ),
        "parameters": {
            "company": "Company name or ticker (required)",
            "filing_type": "10-K or 10-Q (default 10-K)",
        },
    },
    {
        "name": "web_search",
        "description": (
            "DuckDuckGo web scrape for discovery when SEC ticker unknown or user asks "
            "about entities not in the uploaded filing."
        ),
        "parameters": {
            "query": "Search query (required)",
            "company": "Optional label for the result",
        },
    },
    {
        "name": "comparative_analyze",
        "description": (
            "Run comparative SLM synthesis using uploaded pipeline analysis plus any "
            "validated external contexts fetched earlier in this turn. "
            "Call only after you have enough peer/prior evidence."
        ),
        "parameters": {},
    },
    {
        "name": "finish",
        "description": (
            "Emit the final user-facing answer. Include inline bracket citations "
            "referencing evidence from prior tool observations."
        ),
        "parameters": {
            "answer": "Complete markdown answer for the user (required)",
        },
    },
]

ALLOWED_ACTIONS = frozenset(t["name"] for t in AGENT_TOOLS)

# Tool priority: RAG → report summary → external fetch → comparative → finish
TOOL_PRIORITY_ORDER = (
    "rag_retrieve",
    "get_report_summary",
    "sec_filing_fetch",
    "prior_filing_fetch",
    "web_search",
    "comparative_analyze",
    "finish",
)

MAX_WEB_SEARCH_PER_TURN = 2

_QUERY_STOPWORDS = frozenset(
    {
        "what", "who", "are", "the", "is", "apple", "google", "company",
        "top", "main", "their", "about", "from", "that", "this", "with",
        "have", "does", "how", "when", "where", "which", "your", "for",
    }
)


@dataclass
class AgentSession:
    company_name: str
    user_message: str
    report: dict
    step: int = 0
    observations: List[Dict[str, Any]] = field(default_factory=list)
    rag_chunks: List[dict] = field(default_factory=list)
    validated_scrapes: List[dict] = field(default_factory=list)
    citations: List[dict] = field(default_factory=list)
    status_steps: List[str] = field(default_factory=list)
    comparative_result: Optional[dict] = None
    seen_citation_keys: set = field(default_factory=set)
    rag_bootstrap_done: bool = False
    summary_bootstrap_done: bool = False
    web_search_attempts: int = 0
    rag_covers_query: bool = False

    def add_citation(self, citation: dict) -> None:
        key = (
            citation.get("citation_id"),
            citation.get("company"),
            citation.get("chunk_index"),
        )
        if key in self.seen_citation_keys:
            return
        self.seen_citation_keys.add(key)
        self.citations.append(citation)


def _query_terms(text: str) -> List[str]:
    terms = [
        re.sub(r"[^a-z0-9]", "", w.lower())
        for w in re.split(r"\W+", text or "")
        if len(w) > 3 and re.sub(r"[^a-z0-9]", "", w.lower()) not in _QUERY_STOPWORDS
    ]
    return [t for t in terms if t]


def _rag_covers_query(session: AgentSession) -> bool:
    """Heuristic: filing chunks already mention query topic terms."""
    terms = _query_terms(session.user_message)
    if not terms or not session.rag_chunks:
        return False

    corpus = " ".join(
        str(c.get("document") or "").lower() for c in session.rag_chunks
    )
    if not corpus.strip():
        return False

    hits = sum(1 for t in terms if t in corpus)
    if hits >= max(1, len(terms) // 2):
        return True

    # Competitor-style questions often match competition language in 10-K
    q_lower = session.user_message.lower()
    if any(w in q_lower for w in ("competitor", "rival", "competition", "peer")):
        if any(
            w in corpus
            for w in ("compet", "rival", "market share", "smartphone", "compete")
        ):
            return True
    return False


def _bootstrap_rag_phase(session: AgentSession) -> None:
    """Mandatory first step: retrieve filing evidence before LLM chooses external tools."""
    if session.rag_bootstrap_done:
        return

    rag_obs = _tool_rag_retrieve(session, {"query": session.user_message, "n_results": 6})
    session.rag_bootstrap_done = True
    session.rag_covers_query = _rag_covers_query(session)
    session.status_steps.append("Bootstrap ACTION: rag_retrieve (automatic — tool priority)")
    session.status_steps.append(
        f"Bootstrap OBSERVE: {rag_obs.get('message') or rag_obs.get('error')}"
    )
    session.observations.append(
        {
            "step": 0,
            "think": "Tool priority: search uploaded filing in vector DB before any web scrape.",
            "action": "rag_retrieve",
            "action_input": {"query": session.user_message},
            "observe": rag_obs,
        }
    )

    summary_obs = _tool_get_report_summary(session, {})
    session.summary_bootstrap_done = True
    session.status_steps.append("Bootstrap ACTION: get_report_summary (automatic)")
    session.status_steps.append(f"Bootstrap OBSERVE: {summary_obs.get('message')}")
    session.observations.append(
        {
            "step": 0,
            "think": "Load pipeline analysis summary from uploaded report.",
            "action": "get_report_summary",
            "action_input": {},
            "observe": summary_obs,
        }
    )


def _allowed_actions(session: AgentSession) -> List[str]:
    """Filter tools based on priority state for this turn."""
    allowed = list(TOOL_PRIORITY_ORDER)

    if session.rag_covers_query:
        # Filing evidence likely sufficient — block web search unless user names external entity
        q = session.user_message.lower()
        names_external = bool(
            re.search(r"\b(compare|versus|vs\.?|against|benchmark)\b", q)
            or re.search(r"\b(msft|googl|samsung|huawei|amd|nvda|meta)\b", q)
        )
        if not names_external:
            allowed = [a for a in allowed if a not in ("web_search",)]

    if session.web_search_attempts >= MAX_WEB_SEARCH_PER_TURN:
        allowed = [a for a in allowed if a != "web_search"]

    if not session.rag_bootstrap_done:
        allowed = [a for a in allowed if a in ("rag_retrieve", "get_report_summary", "finish")]

    return allowed


def _enforce_action(session: AgentSession, action: str) -> tuple[str, Optional[str]]:
    """
    Redirect disallowed actions per tool priority.
    Returns (action, optional_override_message).
    """
    allowed = _allowed_actions(session)
    if action in allowed:
        return action, None

    if action == "web_search":
        if not session.rag_bootstrap_done:
            return "rag_retrieve", "web_search blocked — rag_retrieve must run first (automatic bootstrap may have failed)."
        if session.rag_covers_query:
            return "finish", (
                "web_search blocked — uploaded filing chunks already cover this topic. "
                "Answer from RAG evidence or state gaps honestly."
            )
        if session.web_search_attempts >= MAX_WEB_SEARCH_PER_TURN:
            return "finish", f"web_search blocked — max {MAX_WEB_SEARCH_PER_TURN} attempts reached."

    if action not in allowed and action != "finish":
        # Fall back to finish if LLM keeps picking blocked tools
        return "finish", f"Action '{action}' blocked by tool priority; synthesize from existing evidence."

    return action, None


def _report_analysis(report: dict) -> dict:
    result = report.get("result") or {}
    if not isinstance(result, dict):
        return {}
    return {
        "executive_summary": result.get("executive_summary"),
        "mda_summary": result.get("mda_summary"),
        "sentiment": result.get("sentiment"),
        "risks": (result.get("risks") or [])[:12],
        "explainability": result.get("explainability"),
        "section_titles": list((result.get("sections") or {}).keys())[:20],
    }


def _truncate(text: str, limit: int = 2400) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _tool_rag_retrieve(session: AgentSession, params: dict) -> dict:
    query = str(params.get("query") or session.user_message).strip()
    n_results = max(1, min(int(params.get("n_results") or 4), 8))
    where = {"company": session.company_name} if session.company_name else None
    chunks = chromadb_manager.query_similar_chunks(query, n_results=n_results, where=where)
    if not chunks and session.company_name:
        chunks = chromadb_manager.query_similar_chunks(query, n_results=n_results)

    session.rag_chunks = chunks
    for i, item in enumerate(chunks):
        session.add_citation(citation_from_chroma_chunk(item, i))

    previews = []
    for i, item in enumerate(chunks[:n_results]):
        meta = item.get("metadata") or {}
        sec = str(meta.get("section", "section")).replace("_", " ")
        previews.append(
            {
                "index": i,
                "section": sec,
                "company": meta.get("company"),
                "excerpt": _truncate(str(item.get("document") or ""), 600),
            }
        )

    return {
        "success": bool(chunks),
        "chunks_found": len(chunks),
        "previews": previews,
        "message": (
            f"Retrieved {len(chunks)} filing chunk(s) from vector DB."
            if chunks
            else "No matching filing chunks in vector DB."
        ),
    }


def _tool_get_report_summary(session: AgentSession, params: dict) -> dict:
    analysis = _report_analysis(session.report)
    return {
        "success": bool(analysis),
        "analysis": analysis,
        "message": (
            "Pipeline analysis summary loaded."
            if analysis
            else "Report analysis not ready — pipeline may still be running."
        ),
    }


def _validate_and_store_scrape(session: AgentSession, doc: dict) -> dict:
    company = session.company_name
    allowed = {session.company_name}
    for ctx in session.validated_scrapes:
        label = str(ctx.get("company") or "").strip()
        if label:
            allowed.add(label)

    peer_label = str(doc.get("company") or "").strip()
    if peer_label and is_plausible_peer_name(peer_label, company):
        allowed.add(peer_label)

    audit = validator_agent.validate_scraped_content(
        doc, company, list(allowed), scrape_requests=[{"company": peer_label}]
    )
    if not audit.get("is_valid"):
        return {
            "success": False,
            "validated": False,
            "reason": audit.get("rejection_reason", "validation failed"),
        }

    cleaned = audit.get("cleaned_content") or doc.get("text") or ""
    ctx = {
        "source": doc.get("source"),
        "company": peer_label or doc.get("company"),
        "filing_type": doc.get("filing_type"),
        "text": cleaned,
        "urls": doc.get("urls") or [],
    }
    session.validated_scrapes.append(ctx)
    session.add_citation(
        citation_from_scraped_context(ctx, len(session.validated_scrapes) - 1)
    )

    chunks = split_text_into_chunks(cleaned)
    if chunks and peer_label:
        ids = [f"{peer_label}_agent_{uuid.uuid4().hex[:6]}_{i}" for i in range(len(chunks))]
        metadata = [
            {"company": peer_label, "section": "agent_scrape", "chunk_index": i}
            for i in range(len(chunks))
        ]
        chromadb_manager.add_chunks(chunks, metadata, ids)

    return {
        "success": True,
        "validated": True,
        "company": peer_label,
        "source": doc.get("source"),
        "excerpt": _truncate(cleaned, 800),
        "chars": len(cleaned),
    }


def _tool_sec_filing(session: AgentSession, params: dict, prior: bool = False) -> dict:
    company = str(params.get("company") or "").strip()
    if not company:
        return {"success": False, "error": "company is required"}
    if not is_plausible_peer_name(company, session.company_name):
        return {"success": False, "error": f"'{company}' is not a plausible company name"}

    filing_type = str(params.get("filing_type") or "10-K").strip()
    req = {
        "type": "prior_filing" if prior else "sec_filing",
        "company": company,
        "filing_type": filing_type.replace("-PRIOR", ""),
    }
    doc = financial_scraper.execute_scrape_request(req)
    if not doc.get("success") or not str(doc.get("text") or "").strip():
        return {
            "success": False,
            "error": doc.get("error") or "SEC fetch returned no text",
            "resolved_ticker": doc.get("resolved_ticker") or financial_scraper.resolve_ticker(company),
        }

    validation = _validate_and_store_scrape(session, doc)
    return {
        "success": validation.get("validated", False),
        "fetch": {
            "company": company,
            "source": doc.get("source"),
            "filing_type": doc.get("filing_type"),
        },
        **validation,
    }


def _tool_web_search(session: AgentSession, params: dict) -> dict:
    query = str(params.get("query") or "").strip()
    if not query:
        return {"success": False, "error": "query is required"}
    session.web_search_attempts += 1
    company = str(params.get("company") or "EXTERNAL").strip()
    doc = financial_scraper.execute_scrape_request(
        {"type": "web_search", "query": query, "company": company}
    )
    if not str(doc.get("text") or "").strip():
        return {
            "success": False,
            "error": doc.get("error") or "Web search returned no text",
        }
    validation = _validate_and_store_scrape(session, doc)
    return {
        "success": validation.get("validated", False),
        "query": query,
        **validation,
    }


def _tool_comparative_analyze(session: AgentSession, params: dict) -> dict:
    if not session.validated_scrapes:
        return {
            "success": False,
            "error": (
                "No validated external contexts yet. Fetch sec_filing, prior_filing, "
                "or web_search first."
            ),
        }

    original = _report_analysis(session.report)
    if not original:
        original = {"note": "Minimal analysis — pipeline may be incomplete"}

    comp = financial_agent.analyze_comparative(
        original,
        session.validated_scrapes,
        session.company_name,
        user_query=session.user_message,
    )
    session.comparative_result = comp
    narrative = _truncate(str(comp.get("comparative_analysis") or ""), 1200)
    benchmarks = comp.get("competitor_benchmarks") or []
    return {
        "success": True,
        "comparative_analysis_excerpt": narrative,
        "benchmark_count": len(benchmarks),
        "tone_shift_count": len(comp.get("tone_shifts") or []),
        "message": "Comparative SLM synthesis complete.",
    }


def execute_agent_tool(session: AgentSession, action: str, params: dict) -> dict:
    """Run one tool and return an observation dict for the SLM."""
    params = params if isinstance(params, dict) else {}
    dispatch: Dict[str, Callable[..., dict]] = {
        "rag_retrieve": lambda: _tool_rag_retrieve(session, params),
        "get_report_summary": lambda: _tool_get_report_summary(session, params),
        "sec_filing_fetch": lambda: _tool_sec_filing(session, params, prior=False),
        "prior_filing_fetch": lambda: _tool_sec_filing(session, params, prior=True),
        "web_search": lambda: _tool_web_search(session, params),
        "comparative_analyze": lambda: _tool_comparative_analyze(session, params),
    }
    fn = dispatch.get(action)
    if not fn:
        return {"success": False, "error": f"Unknown tool: {action}"}
    try:
        return fn()
    except Exception as exc:
        logger.exception("Agent tool %s failed", action)
        return {"success": False, "error": str(exc)}


def _build_step_prompt(session: AgentSession, max_steps: int) -> str:
    allowed = _allowed_actions(session)
    allowed_tools = [t for t in AGENT_TOOLS if t["name"] in allowed]
    tools_json = json.dumps(allowed_tools, indent=2)
    history = json.dumps(session.observations[-8:], indent=2) if session.observations else "[]"
    analysis_hint = _report_analysis(session.report)
    has_analysis = bool(analysis_hint)
    rag_hint = (
        "yes — filing chunks likely contain the answer; prefer finish over web_search"
        if session.rag_covers_query
        else "no — consider external fetch only if filing evidence is insufficient"
    )

    task_body = f"""
{user_query_reminder(session.user_message)}

[Uploaded company] {session.company_name}
[Pipeline analysis ready] {has_analysis}
[Step] {session.step + 1} of {max_steps}
[RAG bootstrap complete] {session.rag_bootstrap_done}
[RAG chunks retrieved] {len(session.rag_chunks)}
[RAG likely sufficient] {rag_hint}
[Web searches used] {session.web_search_attempts} / {MAX_WEB_SEARCH_PER_TURN}
[Validated external contexts] {len(session.validated_scrapes)}

[Tool priority — enforced by the platform]
1. rag_retrieve + get_report_summary (already run automatically at turn start)
2. finish when filing evidence answers the question
3. sec_filing_fetch / prior_filing_fetch only for named peers or explicit comparisons
4. web_search ONLY if RAG did not surface relevant evidence (max {MAX_WEB_SEARCH_PER_TURN} per turn)
5. comparative_analyze after validated external contexts exist

[Allowed tools this step — pick exactly ONE]
{tools_json}

[Prior steps — THINK / Action / Observe]
{history}

[Loop protocol]
1. THINK: Review bootstrap RAG previews first before requesting web_search.
2. ACTION: One allowed tool, or finish with action_input.answer.
3. If filing chunks mention competitors/risks/metrics for this question → finish now.

[Output JSON schema — ONLY this object]
{{
  "think": "Your reasoning (2-4 sentences)",
  "action": "<one allowed tool name>",
  "action_input": {{ }},
  "answer": null
}}

When action is finish, set action_input.answer to the complete user-facing markdown answer.
"""
    return compose_slm_prompt(SlmRole.CHAT_AGENT, task_body)


def _parse_agent_step(raw: Optional[dict]) -> Optional[dict]:
    if not raw or not isinstance(raw, dict):
        return None
    action = str(raw.get("action") or "").strip().lower()
    if action not in ALLOWED_ACTIONS:
        return None
    think = str(raw.get("think") or "").strip()
    action_input = raw.get("action_input")
    if not isinstance(action_input, dict):
        action_input = {}
    answer = raw.get("answer") or action_input.get("answer")
    return {
        "think": think,
        "action": action,
        "action_input": action_input,
        "answer": str(answer).strip() if answer else None,
    }


def _synthesize_answer_from_rag(session: AgentSession) -> str:
    """Generate a citation-backed answer from accumulated evidence."""
    context_parts: List[str] = []
    for i, item in enumerate(session.rag_chunks[:6]):
        meta = item.get("metadata") or {}
        sec = str(meta.get("section", "section")).replace("_", " ")
        comp = meta.get("company", session.company_name)
        context_parts.append(
            f"[{comp} {sec} chunk {meta.get('chunk_index', i)}]:\n"
            f"{str(item.get('document') or '')[:900]}"
        )
    for i, ctx in enumerate(session.validated_scrapes[:3]):
        context_parts.append(
            f"[External {ctx.get('company')} — {ctx.get('source')}]:\n"
            f"{str(ctx.get('text') or '')[:900]}"
        )

    analysis = _report_analysis(session.report)
    if analysis.get("executive_summary"):
        context_parts.append(f"[Pipeline executive summary]: {analysis['executive_summary']}")

    if not context_parts:
        return (
            f"I could not find sufficient evidence in the uploaded filing for "
            f"{session.company_name} to answer: {session.user_message}"
        )

    task_body = f"""
{user_query_reminder(session.user_message)}

[Retrieved evidence — uploaded filing + any validated external fetches]
{chr(10).join(context_parts)}

[Task]
Write a direct, query-specific answer using ONLY the evidence above.
Include inline bracket citations for factual claims.
If evidence is partial, answer what is supported and state what is missing.
"""
    text = llm_client.generate(
        compose_slm_prompt(SlmRole.RAG_CHAT, task_body),
        temperature=0.1,
        timeout=60,
    )
    return (text or "").strip()


def _fallback_finish(session: AgentSession) -> str:
    """Last-resort answer when the agent exhausts steps without finish."""
    synthesized = _synthesize_answer_from_rag(session)
    if synthesized and len(synthesized) > 80:
        return synthesized

    parts = [
        f"I researched your question about {session.company_name} but could not "
        "complete the agent loop in time."
    ]
    if session.rag_chunks:
        excerpt = _truncate(str(session.rag_chunks[0].get("document") or ""), 400)
        parts.append(f"From the uploaded filing: \"{excerpt}\"")
    if session.comparative_result:
        parts.append(
            _truncate(str(session.comparative_result.get("comparative_analysis") or ""), 600)
        )
    parts.append(
        "Try rephrasing with a specific section, metric, or peer company name."
    )
    return " ".join(parts)


def run_chat_agent(
    report: dict,
    user_message: str,
    *,
    max_steps: Optional[int] = None,
) -> dict:
    """
    THINK → Action → Observe loop until the SLM calls finish or max_steps is hit.
    """
    settings = get_settings()
    limit = max_steps if max_steps is not None else settings.chat_max_agent_steps
    company = str(report.get("company_name") or "Target Company")

    session = AgentSession(
        company_name=company,
        user_message=user_message,
        report=report,
    )

    _bootstrap_rag_phase(session)

    final_answer: Optional[str] = None
    mode = "agent"

    for step in range(limit):
        session.step = step
        prompt = _build_step_prompt(session, limit)
        raw = llm_client.generate_json(
            prompt,
            temperature=0.15,
            timeout=75,
            validator=lambda p: isinstance(p.get("action"), str),
        )
        parsed = _parse_agent_step(raw)

        if not parsed:
            session.status_steps.append(
                f"Step {step + 1}: SLM returned invalid step JSON — retrying."
            )
            session.observations.append(
                {
                    "step": step + 1,
                    "think": "(parse failure)",
                    "action": "error",
                    "observe": {"success": False, "error": "Invalid agent JSON"},
                }
            )
            continue

        think = parsed["think"]
        action = parsed["action"]
        action_input = parsed["action_input"]
        action, priority_msg = _enforce_action(session, action)
        if priority_msg:
            session.status_steps.append(f"Step {step + 1} PRIORITY: {priority_msg}")

        session.status_steps.append(f"Step {step + 1} THINK: {think}")
        session.status_steps.append(f"Step {step + 1} ACTION: {action}")

        if action == "finish":
            final_answer = parsed["answer"] or str(action_input.get("answer") or "").strip()
            if not final_answer or priority_msg:
                final_answer = _synthesize_answer_from_rag(session)
            if session.comparative_result and final_answer:
                formatted = _format_comparison_answer(session.comparative_result, company)
                if len(final_answer) < 120 and formatted:
                    final_answer = formatted
            elif session.comparative_result and not final_answer:
                final_answer = _format_comparison_answer(session.comparative_result, company)
            if not final_answer:
                final_answer = _fallback_finish(session)
            session.observations.append(
                {
                    "step": step + 1,
                    "think": think,
                    "action": "finish",
                    "observe": {"success": True, "message": "Final answer emitted."},
                }
            )
            break

        observation = execute_agent_tool(session, action, action_input)
        if action == "rag_retrieve":
            session.rag_covers_query = _rag_covers_query(session)
        session.status_steps.append(
            f"Step {step + 1} OBSERVE: {observation.get('message') or observation.get('error') or json.dumps(observation)[:200]}"
        )
        session.observations.append(
            {
                "step": step + 1,
                "think": think,
                "action": action,
                "action_input": action_input,
                "observe": observation,
            }
        )

    if not final_answer:
        final_answer = _fallback_finish(session)
        session.status_steps.append("Max steps reached — emitting fallback answer.")

    out_guard = guardrails.check_llm_text_output(final_answer)
    if not out_guard.allowed:
        payload = out_guard.to_api_payload()
        payload["mode"] = mode
        payload["status_steps"] = session.status_steps
        return payload

    final_answer = out_guard.sanitized_text or final_answer

    return {
        "success": True,
        "mode": mode,
        "answer": final_answer,
        "citations": session.citations,
        "source_summary": summarize_source_types(session.citations),
        "status_steps": session.status_steps,
        "agent_steps": len(session.observations),
        "comparison": session.comparative_result,
    }
