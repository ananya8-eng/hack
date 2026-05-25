"""On-demand peer comparison inside the RAG chat flow (scrape → validate → SLM)."""
from __future__ import annotations

import logging
import uuid
from typing import Any, Callable, Dict, List, Optional

from backend.agents.financial_agent import financial_agent
from backend.guardrails import guardrails
from backend.agents.healing_loop import run_comparative_with_healing, run_scrape_with_healing
from backend.agents.validator_agent import validator_agent
from backend.rag.chunking import split_text_into_chunks
from backend.rag.citation_sources import (
    build_evidence_corpus,
    citation_from_chroma_chunk,
    citation_from_scraped_context,
    companies_match,
    sanitize_competitor_benchmarks,
    summarize_source_types,
)
from backend.tools.chroma_tool import chromadb_manager
from backend.extraction.margin_trends import compute_margin_trends
from backend.tools.scrape_plan import (
    companies_from_requests,
    extract_peer_companies,
    is_chat_comparison_query,
    is_plausible_peer_name,
    plan_comparison_scrapes,
    resolve_request_tickers,
)
from backend.tools.scraper import financial_scraper

logger = logging.getLogger(__name__)


def _report_original_analysis(report: dict) -> dict:
    result = report.get("result") or {}
    return {
        "risks": result.get("risks", []),
        "sentiment": result.get("sentiment", {}),
        "executive_summary": (
            result.get("executive_summary")
            or result.get("explainability")
            or ""
        ),
        "explainability": result.get("explainability", ""),
    }


def _filing_excerpt(report: dict, limit: int = 3000) -> str:
    result = report.get("result") or {}
    sections = result.get("sections") or {}
    if isinstance(sections, dict) and sections:
        combined = "\n\n".join(str(v) for v in sections.values() if v)
        return combined[:limit]
    return str(result.get("raw_text") or "")[:limit]


def _filter_peer_contexts(
    contexts: List[dict],
    target_company: str,
) -> List[dict]:
    """Drop SEC pulls for the same issuer (common cause of 'Apple vs Apple' benchmarks)."""
    target_ticker = financial_scraper.resolve_ticker(target_company)
    kept: List[dict] = []
    for ctx in contexts:
        filing_type = str(ctx.get("filing_type") or "").upper()
        if "PRIOR" in filing_type:
            kept.append(ctx)
            continue
        peer = str(ctx.get("company") or "")
        if not is_plausible_peer_name(peer, target_company):
            logger.info("Skipping non-peer scrape context label: %s", peer)
            continue
        peer_ticker = financial_scraper.resolve_ticker(peer)
        if peer_ticker and target_ticker and peer_ticker == target_ticker:
            logger.info(
                "Skipping duplicate target-company scrape context: %s", peer
            )
            continue
        if companies_match(peer, target_company):
            continue
        kept.append(ctx)
    return kept


def _filing_vector_citations(user_message: str, company_name: str, limit: int = 4) -> List[dict]:
    where_filter = {"company": company_name} if company_name else None
    chunks = chromadb_manager.query_similar_chunks(
        user_message, n_results=limit, where=where_filter
    )
    if not chunks and company_name:
        chunks = chromadb_manager.query_similar_chunks(user_message, n_results=limit)
    return [citation_from_chroma_chunk(item, i) for i, item in enumerate(chunks)]


def _format_comparison_answer(comp: dict, company_name: str) -> str:
    parts: List[str] = []
    narrative = str(comp.get("comparative_analysis") or "").strip()
    if narrative:
        parts.append(narrative)

    benchmarks = comp.get("competitor_benchmarks") or []
    if benchmarks:
        parts.append("\n\n**Metric benchmarks** *(from retrieved filing + scrape evidence only)*")
        for bm in benchmarks[:6]:
            metric = bm.get("metric_name", "Metric")
            peer = bm.get("competitor_company") or bm.get("comparison_target") or "Peer"
            value = str(bm.get("comparison_value") or "").strip()
            if companies_match(str(peer), company_name):
                continue
            if value:
                parts.append(f"- **{metric}** ({company_name} vs {peer}): {value}")
            else:
                parts.append(f"- **{metric}** ({company_name} vs {peer})")

    tone_shifts = comp.get("tone_shifts") or []
    if tone_shifts:
        parts.append("\n\n**Management tone shifts**")
        for ts in tone_shifts[:4]:
            target = ts.get("comparison_target", "Peer")
            direction = ts.get("shift_direction", "")
            details = ts.get("details", "")
            parts.append(f"- {target} — {direction}: {details}")

    synthesis = str(comp.get("explainability_synthesis") or "").strip()
    if synthesis:
        parts.append(f"\n\n**Risk synthesis:** {synthesis}")

    if benchmarks:
        parts.append(
            "\n\n*Benchmark rows without supporting numbers in the retrieved "
            "filing or scrape text are omitted automatically.*"
        )

    return "\n".join(parts).strip() or (
        f"Comparison for {company_name} completed, but the model returned no narrative text."
    )


def _comparison_citations(
    validated_contexts: List[dict],
    filing_citations: List[dict],
) -> List[dict]:
    citations: List[dict] = list(filing_citations)
    for i, ctx in enumerate(validated_contexts):
        citations.append(citation_from_scraped_context(ctx, i))
    return citations


def run_chat_peer_comparison(
    report: dict,
    user_message: str,
    on_progress: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Scrape peer/competitor data for a chat comparison question, validate it,
    and synthesize benchmarks via the financial agent (SLM).
    """
    company = report.get("company_name", "Target Company")
    filing_text = _filing_excerpt(report, limit=8000)

    if not is_chat_comparison_query(user_message):
        return {"handled": False}

    input_guard = guardrails.check_chat_message(user_message)
    if not input_guard.allowed:
        payload = input_guard.to_api_payload()
        payload["handled"] = True
        payload["mode"] = "comparison"
        return payload

    user_message = input_guard.sanitized_text or user_message

    def progress(msg: str) -> None:
        logger.info(msg)
        if on_progress:
            on_progress(msg)

    filing_citations = _filing_vector_citations(user_message, company)

    progress("Comparison intent detected — planning live scrape targets from your question...")
    scrape_decision = plan_comparison_scrapes(user_message, company, filing_text)
    scrape_requests = list(scrape_decision.get("scrape_requests") or [])
    if not scrape_requests:
        return {
            "handled": True,
            "success": False,
            "mode": "comparison",
            "answer": (
                "I understood this as a peer comparison request, but need a clearer target. "
                f"Name the company or period to benchmark against {company} "
                '(for example: "Compare against MSFT on supply chain and gross margins").'
            ),
            "citations": filing_citations,
            "source_summary": summarize_source_types(filing_citations),
            "comparison": None,
            "status_steps": [
                scrape_decision.get("reason")
                or "No scrape targets derived from the question."
            ],
        }

    scrape_requests = resolve_request_tickers(
        scrape_requests, financial_scraper.resolve_ticker
    )
    progress(
        f"Fetching {len(scrape_requests)} external source(s) for peer comparison..."
    )

    def _execute(req: Dict[str, Any]) -> Dict[str, Any]:
        return financial_scraper.execute_scrape_request(req)

    scraped_docs, failures, _ = run_scrape_with_healing(
        scrape_requests,
        execute_fn=_execute,
        company_name=company,
        user_query=user_message,
        filing_excerpt=filing_text[:3000],
    )

    allowed = companies_from_requests(scrape_requests, company)
    validated_contexts: List[dict] = []
    status_steps: List[str] = [
        f"Scrape plan: {len(scrape_requests)} request(s).",
        f"Retrieved {len(scraped_docs)} document(s) before validation.",
        f"Uploaded filing chunks in vector DB: {len(filing_citations)} citation(s).",
    ]

    for doc in scraped_docs:
        audit = validator_agent.validate_scraped_content(
            doc, company, allowed, scrape_requests
        )
        doc_company = doc.get("company", "Unknown")
        if audit.get("is_valid", False):
            status_steps.append(f"Validated: {doc_company} ({doc.get('source', 'SEC')}).")
            validated_contexts.append(
                {
                    "source": doc.get("source"),
                    "company": doc_company,
                    "filing_type": doc.get("filing_type"),
                    "text": audit.get("cleaned_content") or doc.get("text", ""),
                    "urls": doc.get("urls") or [],
                }
            )
            chunks = split_text_into_chunks(
                audit.get("cleaned_content") or doc.get("text", "")
            )
            if chunks:
                ids = [
                    f"{doc_company}_chat_peer_{uuid.uuid4().hex[:6]}_{i}"
                    for i in range(len(chunks))
                ]
                metadata = [
                    {
                        "company": doc_company,
                        "section": "competitor_analysis",
                        "chunk_index": i,
                    }
                    for i in range(len(chunks))
                ]
                chromadb_manager.add_chunks(chunks, metadata, ids)
        else:
            status_steps.append(
                f"Rejected: {doc_company} — {audit.get('rejection_reason', 'validation failed')}."
            )

    for fail in failures:
        req = fail.get("request") or {}
        label = req.get("query") or req.get("company") or "unknown"
        status_steps.append(f"Scrape failure: {label}")

    validated_contexts = _filter_peer_contexts(validated_contexts, company)

    if not validated_contexts:
        return {
            "handled": True,
            "success": False,
            "mode": "comparison",
            "answer": (
                f"I could not retrieve validated peer filing or web data for your comparison "
                f"against {company}. Name a specific US public company and metric "
                f'(e.g. "Compare {company} vs MSFT on gross margins and supply chain risks"), '
                "or check that SEC/network access is available."
            ),
            "citations": filing_citations,
            "source_summary": summarize_source_types(filing_citations),
            "comparison": None,
            "status_steps": status_steps,
        }

    progress("Running comparative analysis with the financial SLM...")
    original_analysis = _report_original_analysis(report)

    def _compare() -> dict:
        return financial_agent.analyze_comparative(
            original_analysis,
            validated_contexts,
            company,
            user_query=user_message,
        )

    comp_result, heal_logs = run_comparative_with_healing(_compare)
    status_steps.extend(heal_logs)

    corpus = build_evidence_corpus(original_analysis, validated_contexts, filing_text)
    comp_result = {
        **comp_result,
        "competitor_benchmarks": sanitize_competitor_benchmarks(
            comp_result.get("competitor_benchmarks") or [],
            company,
            corpus,
        ),
    }
    status_steps.append("Comparative analysis complete.")

    peer: Optional[str] = None
    for ctx in validated_contexts:
        label = str(ctx.get("company") or "").strip()
        if label and not companies_match(label, company):
            peer = label
            break
    if not peer:
        peers = [
            p
            for p in extract_peer_companies(user_message, company)
            if is_plausible_peer_name(p, company)
        ]
        peer = peers[0] if peers else None

    margin_trends = compute_margin_trends(
        company,
        peer_company=peer,
        uploaded_text=filing_text,
    )
    if margin_trends.get("points"):
        status_steps.append(
            f"Margin trend series updated ({len(margin_trends['points'])} year(s) from SEC)."
        )

    stored = report.get("result")
    if isinstance(stored, dict):
        report["result"] = {
            **stored,
            "final_comparative_analysis": comp_result,
            "margin_trends": margin_trends,
        }

    all_citations = _comparison_citations(validated_contexts, filing_citations)
    answer = _format_comparison_answer(comp_result, company)
    return {
        "handled": True,
        "success": True,
        "mode": "comparison",
        "answer": answer,
        "citations": all_citations,
        "source_summary": summarize_source_types(all_citations),
        "comparison": comp_result,
        "status_steps": status_steps,
    }
