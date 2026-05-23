"""
LangGraph orchestration — Earnings Report Risk & Sentiment Extractor.

Flow:
  discover sections (PDF-specific) → chunk/index full narrative → map-reduce analysis
  → [scrape → validate → comparative re-analysis] | finalize → END
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from backend.agents.financial_agent import financial_agent
from backend.agents.healing_loop import (
    run_analysis_with_healing,
    run_comparative_with_healing,
    run_scrape_with_healing,
)
from backend.agents.validator_agent import validator_agent
from backend.config import get_settings
from backend.extraction.section_extractor import SectionExtractionError, discover_sections
from backend.extraction.section_models import FilingSection, sections_catalog, sections_to_text_map
from backend.rag.chunking import split_text_into_chunks
from backend.tools.chroma_tool import chromadb_manager
from backend.tools.scrape_plan import companies_from_requests, resolve_request_tickers
from backend.tools.scraper import financial_scraper
from backend.reports_store import append_report_log

logger = logging.getLogger(__name__)

StepCallback = Callable[[str, Dict[str, Any], Dict[str, Any]], None]
ProgressCallback = Callable[[str, Optional[str]], None]


class AgentState(TypedDict, total=False):
    company_name: str
    raw_text: str
    user_query: str

    sections: Dict[str, str]
    section_catalog: List[Dict[str, Any]]
    chunks_indexed: int
    rag_context_snippets: List[str]

    original_analysis: Dict[str, Any]
    needs_scraping: bool
    scraping_reason: str
    targets: List[str]
    scrape_requests: List[Dict[str, Any]]
    heal_logs: List[str]

    scraped_documents: List[Dict[str, Any]]
    validated_contexts: List[Dict[str, Any]]
    final_comparative_analysis: Dict[str, Any]

    current_step: str
    logs: List[str]
    report_id: str


def _append_logs(state: AgentState, *messages: str) -> List[str]:
    logs = list(state.get("logs", []))
    logs.extend(messages)
    return logs


def _rebuild_sections(state: AgentState) -> List[FilingSection]:
    catalog = state.get("section_catalog") or []
    text_map = state.get("sections") or {}
    rebuilt: List[FilingSection] = []
    for entry in catalog:
        sid = str(entry.get("id", ""))
        if not sid:
            continue
        rebuilt.append(
            FilingSection(
                id=sid,
                title=str(entry.get("title", sid)),
                text=text_map.get(sid, ""),
                priority=int(entry.get("priority", 50)),
                source=str(entry.get("source", "")),
            )
        )
    return rebuilt


def _narrative_excerpt(sections: List[FilingSection], limit: int = 12_000) -> str:
    parts: List[str] = []
    for sec in sorted(sections, key=lambda s: -s.priority)[:6]:
        parts.append(f"=== {sec.title} ===\n{sec.text[:4000]}")
    combined = "\n\n".join(parts)
    return combined[:limit]


def node_ingest_and_chunk(state: AgentState) -> Dict[str, Any]:
    logs = _append_logs(
        state,
        "Step 1: Discovering narrative sections across full filing (MD&A, risks, outlook)...",
    )
    logger.info("LangGraph node: ingest_and_chunk")

    raw_text = state.get("raw_text", "")
    company = state.get("company_name", "Target Company")
    report_id = state.get("report_id", "")

    if report_id:
        append_report_log(
            report_id,
            "Discovering narrative sections (MD&A, risks, etc.)...",
            step="Section discovery in progress",
        )
    discovered = discover_sections(raw_text)
    sections = sections_to_text_map(discovered)
    catalog = sections_catalog(discovered)

    for entry in catalog[:8]:
        logs.append(
            f"  • {entry['title']} ({entry['char_count']:,} chars, priority {entry['priority']})"
        )

    settings = get_settings()
    filing_budget = settings.max_chunks_per_filing
    per_section_cap = settings.max_chunks_per_section
    analyzable = [s for s in discovered if s.priority >= 15]
    weight_total = sum(s.priority for s in analyzable) or 1

    total_indexed = 0
    if report_id:
        append_report_log(
            report_id,
            f"Indexing up to {filing_budget} chunks in vector store (this may take a few minutes)...",
            step="Embedding & indexing",
        )
    for sec in discovered:
        if not sec.text or sec.priority < 10:
            continue
        chunks = split_text_into_chunks(sec.text)
        if not chunks:
            continue
        share = sec.priority / weight_total if sec in analyzable else 0.15
        allowance = max(4, int(filing_budget * share)) if sec in analyzable else 4
        allowance = min(allowance, per_section_cap, len(chunks))
        if len(chunks) > allowance:
            chunks = chunks[:allowance]
        ids = [f"{company}_{sec.id}_{uuid.uuid4().hex[:6]}_{i}" for i in range(len(chunks))]
        metadata = [
            {"company": company, "section": sec.id, "section_title": sec.title, "chunk_index": i}
            for i in range(len(chunks))
        ]
        chromadb_manager.add_chunks(chunks, metadata, ids)
        total_indexed += len(chunks)
        if report_id and total_indexed % 20 == 0:
            append_report_log(
                report_id,
                f"Indexed {total_indexed} chunks so far (latest: {sec.title[:60]})...",
                step="Embedding & indexing",
            )

    logs.append(
        f"Indexed {total_indexed} chunks from {len(catalog)} filing-specific sections (budget {filing_budget})."
    )

    return {
        "sections": sections,
        "section_catalog": catalog,
        "chunks_indexed": total_indexed,
        "current_step": "Section Discovery & Indexing Complete",
        "logs": logs,
    }


def node_financial_analysis(state: AgentState) -> Dict[str, Any]:
    logs = _append_logs(
        state,
        "Step 2: Map-reduce risk & sentiment analysis (MD&A-focused, all narrative sections)...",
    )
    logger.info("LangGraph node: financial_analysis")

    filing_sections = _rebuild_sections(state)
    company = state.get("company_name", "Target Company")
    query = state.get("user_query", "")
    report_id = state.get("report_id", "")

    if report_id:
        append_report_log(
            report_id,
            "Running map-reduce analysis across narrative sections (MD&A prioritized)...",
            step="Risk & sentiment analysis",
        )

    analysis_input = _narrative_excerpt(filing_sections)
    if not analysis_input.strip():
        raise SectionExtractionError(
            "No narrative section text available for financial analysis."
        )

    def _analyze() -> dict:
        return financial_agent.analyze_filing_from_sections(
            filing_sections, company, query
        )

    analysis_result, analysis_heal_logs = run_analysis_with_healing(
        _analyze,
        company_name=company,
        user_query=query,
        filing_text=analysis_input,
        shape_fn=lambda payload: financial_agent._ensure_analysis_shape(
            payload, analysis_input, query, company
        ),
    )
    for msg in analysis_heal_logs:
        logs.append(f"[Self-heal] {msg}")

    needs_scrape = bool(analysis_result.get("needs_scraping", False))
    targets = list(analysis_result.get("targets") or [])
    scrape_requests = list(analysis_result.get("scrape_requests") or [])
    reason = str(analysis_result.get("reason") or "")

    risks = analysis_result.get("risks", [])
    sentiment_score = analysis_result.get("sentiment", {}).get("score", 0.0)
    logs.append(
        f"Initial audit complete — {len(risks)} risks detected; "
        f"sentiment score {sentiment_score}."
    )

    if needs_scrape and scrape_requests:
        for i, req in enumerate(scrape_requests, start=1):
            req_type = req.get("type", "web_search")
            if req_type == "web_search":
                logs.append(
                    f"Scrape plan {i}: web search — \"{req.get('query', '')[:100]}\""
                )
            else:
                logs.append(
                    f"Scrape plan {i}: {req_type} — {req.get('company', '')} "
                    f"({req.get('filing_type', '10-K')})"
                )
        logs.append(f"Agent decision: external enrichment required. Reason: {reason}")
    else:
        logs.append("Agent decision: local filing context is sufficient — skipping web scrape.")

    return {
        "original_analysis": analysis_result,
        "needs_scraping": needs_scrape,
        "targets": targets,
        "scrape_requests": scrape_requests,
        "scraping_reason": reason,
        "heal_logs": analysis_heal_logs,
        "current_step": "Initial Financial Analysis Complete",
        "logs": logs,
    }


def node_web_scraping(state: AgentState) -> Dict[str, Any]:
    logs = _append_logs(
        state,
        "Step 3: Web Scraping Tool — LLM-planned searches and SEC fetches...",
    )
    logger.info("LangGraph node: web_scraping")

    scrape_requests = resolve_request_tickers(
        list(state.get("scrape_requests") or []),
        financial_scraper.resolve_ticker,
    )
    company = state.get("company_name", "Target Company")
    user_query = state.get("user_query", "")
    filing_sections = _rebuild_sections(state)
    filing_excerpt = _narrative_excerpt(filing_sections, limit=3000)

    logs.append(
        f"Scrape plan: {len(scrape_requests)} request(s) — self-healing enabled (max retries from config)."
    )

    def _execute(req: Dict[str, Any]) -> Dict[str, Any]:
        return financial_scraper.execute_scrape_request(req)

    scraped_docs, failures, scrape_heal_logs = run_scrape_with_healing(
        scrape_requests,
        execute_fn=_execute,
        company_name=company,
        user_query=user_query,
        filing_excerpt=filing_excerpt,
        on_attempt=lambda attempt, msg: logs.append(f"[Self-heal] {msg}"),
    )
    for msg in scrape_heal_logs:
        if not msg.startswith("[Self-heal]"):
            logs.append(f"[Self-heal] {msg}")

    for doc in scraped_docs:
        logs.append(
            f"Retrieved {len(doc.get('text', ''))} chars from {doc.get('source', 'external')}."
        )
    for fail in failures:
        req = fail.get("request") or {}
        label = req.get("query") or req.get("company") or "unknown"
        logs.append(f"Scrape failed after healing: {label} — {fail.get('error', '')[:120]}")

    if not scraped_docs:
        logs.append("No external documents retrieved — validation will have nothing to approve.")

    return {
        "scraped_documents": scraped_docs,
        "current_step": "Web Scraping Complete",
        "logs": logs,
    }


def node_validation(state: AgentState) -> Dict[str, Any]:
    logs = _append_logs(state, "Step 4: Validator Agent — auditing scraped content...")
    logger.info("LangGraph node: validation")

    scraped_docs = state.get("scraped_documents", [])
    company = state.get("company_name", "Target Company")
    scrape_requests = list(state.get("scrape_requests") or [])
    allowed_companies = companies_from_requests(scrape_requests, company)

    validated_contexts: List[Dict[str, Any]] = []
    for doc in scraped_docs:
        audit_res = validator_agent.validate_scraped_content(
            doc, company, allowed_companies, scrape_requests
        )
        doc_company = doc.get("company", "Unknown")

        if audit_res.get("is_valid", False):
            logs.append(
                f"APPROVED: {doc_company} — relevance {audit_res.get('relevance_score')}, "
                f"freshness {audit_res.get('freshness_rating')}."
            )
            validated_contexts.append(
                {
                    "source": doc.get("source"),
                    "company": doc_company,
                    "filing_type": doc.get("filing_type"),
                    "text": audit_res.get("cleaned_content"),
                }
            )

            comp_chunks = split_text_into_chunks(audit_res.get("cleaned_content", ""))
            if comp_chunks:
                ids = [
                    f"{doc_company}_competitor_{uuid.uuid4().hex[:6]}_{i}"
                    for i in range(len(comp_chunks))
                ]
                metadata = [
                    {
                        "company": doc_company,
                        "section": "competitor_analysis",
                        "chunk_index": i,
                    }
                    for i in range(len(comp_chunks))
                ]
                chromadb_manager.add_chunks(comp_chunks, metadata, ids)
        else:
            logs.append(
                f"REJECTED: {doc_company} — {audit_res.get('rejection_reason', 'failed validation')}."
            )

    logs.append(f"Validation complete — {len(validated_contexts)} context(s) approved for re-analysis.")

    return {
        "validated_contexts": validated_contexts,
        "current_step": "Validation Complete",
        "logs": logs,
    }


def node_comparative_reanalysis(state: AgentState) -> Dict[str, Any]:
    logs = _append_logs(
        state,
        "Step 5: Financial Intelligence Agent — comparative re-analysis with validated context...",
    )
    logger.info("LangGraph node: comparative_reanalysis")

    orig_analysis = state.get("original_analysis", {})
    validated_ctxs = state.get("validated_contexts", [])
    company = state.get("company_name", "Target Company")

    if not validated_ctxs:
        logs.append("No validated external context — synthesizing finalize summary from local analysis.")
        comp_result = _build_finalize_analysis(orig_analysis, company)
    else:

        def _compare() -> dict:
            return financial_agent.analyze_comparative(
                orig_analysis, validated_ctxs, company
            )

        comp_result, comp_heal_logs = run_comparative_with_healing(
            _compare,
            on_attempt=lambda attempt, msg: logs.append(f"[Self-heal] {msg}"),
        )
        for msg in comp_heal_logs:
            if not msg.startswith("[Self-heal]"):
                logs.append(f"[Self-heal] {msg}")

    logs.append("Comparative re-analysis complete — benchmarks and tone shifts synthesized.")
    logs.append("LangGraph Financial Intelligence pipeline executed successfully.")

    return {
        "final_comparative_analysis": comp_result,
        "current_step": "Pipeline Completed",
        "logs": logs,
    }


def _build_finalize_analysis(original_analysis: Dict[str, Any], company_name: str) -> Dict[str, Any]:
    """Summary payload when scrape branch is skipped or validation yields no documents."""
    return {
        "original_summary": original_analysis.get("executive_summary", ""),
        "comparative_analysis": (
            f"No external peer or prior-period filings were required for {company_name}. "
            "Analysis is based solely on the uploaded filing narrative sections."
        ),
        "tone_shifts": [],
        "competitor_benchmarks": [],
        "explainability_synthesis": original_analysis.get("explainability", ""),
    }


def node_finalize_without_scrape(state: AgentState) -> Dict[str, Any]:
    logs = _append_logs(
        state,
        "Step 3 (skip branch): Finalizing insights from uploaded filing only...",
    )
    logger.info("LangGraph node: finalize_without_scrape")

    orig_analysis = state.get("original_analysis", {})
    company = state.get("company_name", "Target Company")
    final = _build_finalize_analysis(orig_analysis, company)

    logs.append("Pipeline completed without external web enrichment.")
    logs.append("LangGraph Financial Intelligence pipeline executed successfully.")

    return {
        "final_comparative_analysis": final,
        "current_step": "Pipeline Completed",
        "logs": logs,
    }


def router_should_scrape(state: AgentState) -> str:
    if state.get("needs_scraping") and state.get("scrape_requests"):
        return "web_scraping"
    return "finalize"


def router_after_validation(state: AgentState) -> str:
    if state.get("validated_contexts"):
        return "comparative_reanalysis"
    return "finalize_empty_scrape"


def build_financial_intelligence_graph():
    builder = StateGraph(AgentState)

    builder.add_node("ingest_and_chunk", node_ingest_and_chunk)
    builder.add_node("financial_analysis", node_financial_analysis)
    builder.add_node("web_scraping", node_web_scraping)
    builder.add_node("validation", node_validation)
    builder.add_node("comparative_reanalysis", node_comparative_reanalysis)
    builder.add_node("finalize_without_scrape", node_finalize_without_scrape)
    builder.add_node("finalize_empty_scrape", node_finalize_without_scrape)

    builder.set_entry_point("ingest_and_chunk")
    builder.add_edge("ingest_and_chunk", "financial_analysis")
    builder.add_conditional_edges(
        "financial_analysis",
        router_should_scrape,
        {
            "web_scraping": "web_scraping",
            "finalize": "finalize_without_scrape",
        },
    )
    builder.add_edge("web_scraping", "validation")
    builder.add_conditional_edges(
        "validation",
        router_after_validation,
        {
            "comparative_reanalysis": "comparative_reanalysis",
            "finalize_empty_scrape": "finalize_empty_scrape",
        },
    )
    builder.add_edge("comparative_reanalysis", END)
    builder.add_edge("finalize_without_scrape", END)
    builder.add_edge("finalize_empty_scrape", END)

    return builder.compile()


financial_graph = build_financial_intelligence_graph()


def _merge_stream_state(accumulated: Dict[str, Any], node_update: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(accumulated)
    for key, value in node_update.items():
        if key == "logs" and key in merged:
            merged["logs"] = list(merged.get("logs", [])) + list(value)
        else:
            merged[key] = value
    return merged


def run_financial_pipeline(
    raw_pdf_text: str,
    company: str,
    query: str = "",
    on_step: Optional[StepCallback] = None,
    report_id: str = "",
    on_progress: Optional[ProgressCallback] = None,
) -> dict:
    """
    Run the compiled LangGraph workflow and return the final AgentState dict.

    Optional on_step(node_name, node_update, accumulated_state) fires after each node
    for live orchestration logging in the API layer.
    """
    initial_state: AgentState = {
        "company_name": company,
        "raw_text": raw_pdf_text,
        "user_query": query,
        "sections": {},
        "section_catalog": [],
        "chunks_indexed": 0,
        "rag_context_snippets": [],
        "original_analysis": {},
        "needs_scraping": False,
        "scraping_reason": "",
        "targets": [],
        "scrape_requests": [],
        "heal_logs": [],
        "scraped_documents": [],
        "validated_contexts": [],
        "final_comparative_analysis": {},
        "current_step": "Pipeline Initialized",
        "logs": ["LangGraph agent pipeline spawned."],
        "report_id": report_id,
    }

    if report_id and on_progress:
        on_progress("LangGraph workflow initialized.", "Pipeline initialized")

    accumulated: Dict[str, Any] = dict(initial_state)

    for event in financial_graph.stream(initial_state, stream_mode="updates"):
        for node_name, node_update in event.items():
            accumulated = _merge_stream_state(accumulated, node_update)
            if on_step:
                on_step(node_name, node_update, accumulated)

    return accumulated
