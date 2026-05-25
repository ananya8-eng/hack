import json
import logging
from typing import List

from backend.agents.analysis_heuristics import (
    analyze_risk_heuristics,
    comparative_analysis_from_contexts,
    compute_sentiment_heuristics,
)
from backend.rag.citation_sources import (
    build_evidence_corpus,
    sanitize_competitor_benchmarks,
)
from backend.agents.llm_client import llm_client
from backend.agents.slm_system_prompts import (
    SlmRole,
    compose_slm_prompt,
    user_query_reminder,
)
from backend.extraction.section_models import FilingSection
from backend.tools.vector_store import vector_store as chromadb_manager
from backend.tools.scrape_plan import (
    build_heuristic_scrape_requests,
    normalize_scraping_decision,
)

logger = logging.getLogger(__name__)


class FinancialAgent:
    def _retrieve_rag_context(
        self,
        query: str,
        company_name: str,
        n_results: int = 4,
    ) -> str:
        """Qdrant retrieval tool for agent reasoning (RAG-augmented analysis)."""
        where_filter = {"company": company_name} if company_name else None
        chunks = chromadb_manager.query_similar_chunks(
            query, n_results=n_results, where=where_filter
        )
        if not chunks and company_name:
            chunks = chromadb_manager.query_similar_chunks(query, n_results=n_results)

        if not chunks:
            return ""

        parts: List[str] = []
        for item in chunks:
            meta = item.get("metadata", {})
            sec = str(meta.get("section", "section")).replace("_", " ").title()
            comp = meta.get("company", company_name)
            idx = meta.get("chunk_index", 0)
            parts.append(f"[{comp} {sec} - Chunk {idx}]\n{item.get('document', '')}")
        return "\n\n".join(parts)

    def _normalize_scraping_decision(self, payload: dict, text: str, user_query: str, company_name: str) -> dict:
        return normalize_scraping_decision(payload, text, user_query, company_name)

    def _ensure_analysis_shape(
        self,
        payload: dict,
        text: str,
        user_query: str,
        company_name: str,
    ) -> dict:
        """Fill missing or invalid LLM fields so downstream nodes never see ambiguous partial JSON."""
        from backend.agents.map_reduce_analysis import _normalize_risk_list

        merged = dict(payload)

        risks = merged.get("risks")
        normalized_risks = _normalize_risk_list(risks)
        if not normalized_risks:
            merged["risks"] = analyze_risk_heuristics(text)
        else:
            merged["risks"] = normalized_risks

        sentiment = merged.get("sentiment")
        if not isinstance(sentiment, dict) or "score" not in sentiment:
            merged["sentiment"] = compute_sentiment_heuristics(text)

        if not str(merged.get("executive_summary") or "").strip():
            merged["executive_summary"] = (
                f"Narrative review completed for {company_name} based on uploaded filing sections."
            )

        if not str(merged.get("explainability") or "").strip():
            merged["explainability"] = (
                "Analysis combines filing narrative signals with retrieved vector context and, "
                "when required, externally validated enrichment."
            )

        return self._normalize_scraping_decision(merged, text, user_query, company_name)

    def analyze_filing_from_sections(
        self,
        sections: List[FilingSection],
        company_name: str = "Target Company",
        user_query: str = "",
    ) -> dict:
        """
        Map-reduce analysis across all PDF-specific narrative sections (MD&A prioritized).
        """
        from backend.agents.map_reduce_analysis import run_map_reduce_analysis

        logger.info(
            "Map-reduce analysis for %s across %s sections",
            company_name,
            len(sections),
        )
        result = run_map_reduce_analysis(sections, company_name, user_query)
        combined = "\n\n".join(s.text[:5000] for s in sections[:4])
        return self._ensure_analysis_shape(result, combined, user_query, company_name)

    def analyze_filing(self, text: str, company_name: str = "Target Company", user_query: str = "") -> dict:
        """
        Analyzes the narrative filing text for risks, sentiment, and scraping requirements.
        Uses the configured LLM chain (NVIDIA first), otherwise activates the heuristic reasoning engine.
        """
        logger.info(f"Financial Agent starting analysis for {company_name}...")

        rag_query = user_query if user_query else "operational risks supply chain competition regulatory"
        rag_context = self._retrieve_rag_context(rag_query, company_name)

        task_body = f"""
        {user_query_reminder(user_query, "Conduct a full comprehensive risk and sentiment audit.")}

        [Uploaded company] {company_name}

        [Retrieved RAG Context from vector_db / Qdrant]
        {rag_context if rag_context else "No additional vector-retrieved chunks yet (first-pass ingestion)."}

        [Filing Text]
        {text[:4000]}

        [Task]
        Return a strict JSON document representing your financial analysis. Ensure the keys match exactly:
        {{
            "risks": [
                {{
                    "risk_name": "Short, clear risk title",
                    "category": "Supply Chain / Competitive / Regulatory / Financial / Geopolitical",
                    "severity": "High / Medium / Low",
                    "evidence": "Exact quote from text supporting this risk",
                    "implication": "Potential impact on business operations and revenues"
                }}
            ],
            "sentiment": {{
                "classification": "Positive / Negative / Neutral",
                "score": -1.0 to 1.0,
                "metrics": {{
                    "optimism": 0.0 to 1.0,
                    "pessimism": 0.0 to 1.0,
                    "cautiousness": 0.0 to 1.0,
                    "uncertainty": 0.0 to 1.0
                }}
            }},
            "executive_summary": "High-level summary of the narrative and takeaways.",
            "explainability": "Deep analytical reasoning connecting the risks to company performance.",
            "needs_scraping": true/false (true when external peer, competitor, industry, or prior-period context is needed),
            "reason": "Why external enrichment is required",
            "scrape_requests": [
                {{
                    "type": "web_search | sec_filing | prior_filing",
                    "query": "Natural-language search query for web_search only, e.g. what are Google's top 5 competitors in cloud advertising?",
                    "company": "Company name or ticker this request supports (any public company, not a fixed list)",
                    "filing_type": "10-K or 10-Q for SEC requests; WEB for web_search",
                    "purpose": "Why this specific fetch helps answer the user request"
                }}
            ],
            "targets": ["Optional legacy tickers only if you also want SEC pulls, e.g. META"]
        }}

        Rules for scrape_requests:
        - Prefer web_search with a concrete natural-language query when the user asks about competitors, peers, or industry context.
        - Use sec_filing when you need official SEC filing text; set "company" to the official stock ticker only (e.g. AAPL for Apple, MSFT for Microsoft, GOOGL for Alphabet/Google, META for Meta).
        - Never use brand names as tickers (wrong: APPLE, GOOGLE; correct: AAPL, GOOGL).
        - Use prior_filing for year-over-year comparison on the same company as the uploaded filing (resolve to its ticker first).
        - You may include multiple requests (web discovery first, then sec_filing for named peers).
        - Do not limit companies to a predefined set; choose companies and queries that match the user request and filing.
        """
        prompt = compose_slm_prompt(SlmRole.FILING_ANALYST, task_body)

        parsed = llm_client.generate_json(prompt, temperature=0.1, timeout=90)

        if parsed:
            logger.info("Model returned parseable JSON for financial analysis")
            return self._ensure_analysis_shape(parsed, text, user_query, company_name)

        logger.warning(
            "LLM did not return valid JSON after retries; using heuristic analysis fallback"
        )

        # ==========================================
        # HEURISTIC ENGINE FALLBACK
        # ==========================================
        logger.info("Executing Heuristic Intelligence Fallback...")
        
        # Analyze Sentiment
        sentiment_data = compute_sentiment_heuristics(text)
        
        # Analyze Risks
        risks_data = analyze_risk_heuristics(text)
        
        scrape_decision = build_heuristic_scrape_requests(text, user_query, company_name)
        needs_scraping = scrape_decision["needs_scraping"]
        reason = scrape_decision["reason"]
        scrape_requests = scrape_decision.get("scrape_requests", [])
        targets = scrape_decision.get("targets", [])

        # Executive Summary synthesis
        company_cleaned = company_name.upper().strip()
        num_high_risks = sum(1 for r in risks_data if r["severity"] == "High")
        exec_summary = (
            f"Financial narrative assessment for {company_cleaned} reveals a {sentiment_data['classification'].lower()} "
            f"underlying bias with a net sentiment index of {sentiment_data['score']}. We detected {len(risks_data)} principal risks, "
            f"of which {num_high_risks} represent high severity. "
            f"Key operational headwind revolves around {risks_data[0]['risk_name'] if risks_data else 'macroeconomic volatility'}. "
            f"Management shows increased {sentiment_data['metrics']['cautiousness']*100:.0f}% cautiousness index and "
            f"{sentiment_data['metrics']['uncertainty']*100:.0f}% uncertainty level regarding forward-looking production targets."
        )

        explainability = (
            f"The computed sentiment score ({sentiment_data['score']}) is highly correlated with "
            f"the frequency of cautionary statements and supply dependencies. In particular, {company_cleaned}'s exposure to "
            f"{risks_data[0]['category'] if risks_data else 'Operational'} vulnerabilities acts as a severe drag on margin ratings. "
            f"Supply-chain or foundry constraints discussed in the filing may compress gross margins if capacity tightens."
        )

        return {
            "risks": risks_data,
            "sentiment": sentiment_data,
            "executive_summary": exec_summary,
            "explainability": explainability,
            "needs_scraping": needs_scraping,
            "reason": reason,
            "scrape_requests": scrape_requests,
            "targets": targets,
        }

    def analyze_comparative(
        self,
        original_analysis: dict,
        scraped_contexts: list,
        company_name: str,
        user_query: str = "",
    ) -> dict:
        """
        Combines original filing analysis with scraped contexts (competitors/previous years)
        to perform advanced multi-document financial benchmarking and shift detection.
        """
        logger.info("Financial Agent performing comparative re-analysis...")
        question = (user_query or "").strip()

        scraped_summaries = []
        for i, ctx in enumerate(scraped_contexts):
            scraped_summaries.append(
                f"Source {i+1}: {ctx.get('source')} ({ctx.get('company', 'external')})\n"
                f"Content: {ctx.get('text', '')[:2000]}\n"
            )

        scraped_text_block = "\n".join(scraped_summaries)

        task_body = f"""
        {user_query_reminder(question, "General peer benchmark requested.")}

        [Uploaded company] {company_name}

        [Original Analysis — from uploaded filing pipeline]
        {json.dumps(original_analysis, indent=2)}

        [Validated External Contexts — sec_edgar / web_search / prior_filing tools only]
        {scraped_text_block}

        [Task]
        Perform a cross-comparison that directly answers the user query only.
        Open comparative_analysis with a direct answer to the user's question in the first 1-2 sentences.
        Use competitor names ONLY as they appear in the contexts or the user query.
        NEVER set competitor_company to the same entity as {company_name} (no self-comparisons).
        Do NOT invent revenue, net income, gross margin, or quarterly figures unless the exact numbers appear above.
        Prefer qualitative, excerpt-backed benchmarks over fabricated financial tables.
        Return strict JSON with these keys:
        {{
            "original_summary": "Brief summary of original analysis",
            "comparative_analysis": "Detailed comparison grounded in the supplied texts",
            "tone_shifts": [
                {{
                    "comparison_target": "Named peer or prior period from the contexts",
                    "shift_direction": "Cautious / Optimistic / Neutral shift label",
                    "details": "Evidence-backed explanation"
                }}
            ],
            "competitor_benchmarks": [
                {{
                    "metric_name": "Metric you can support from the texts",
                    "target_company": "{company_name}",
                    "competitor_company": "Peer name from retrieved context",
                    "comparison_value": "Qualitative or counted comparison from the texts only"
                }}
            ],
            "explainability_synthesis": "How these factors affect operational risk per the evidence"
        }}
        """
        prompt = compose_slm_prompt(SlmRole.COMPARATIVE, task_body)

        def _valid_comparative(payload: dict) -> bool:
            return isinstance(payload.get("comparative_analysis"), str)

        parsed = llm_client.generate_json(
            prompt,
            temperature=0.1,
            timeout=90,
            validator=_valid_comparative,
        )
        if parsed:
            logger.info("Model returned parseable JSON for comparative analysis")
            corpus = build_evidence_corpus(
                original_analysis,
                scraped_contexts,
            )
            benchmarks = sanitize_competitor_benchmarks(
                parsed.get("competitor_benchmarks") or [],
                company_name,
                corpus,
            )
            return {**parsed, "competitor_benchmarks": benchmarks}

        logger.warning(
            "Comparative LLM did not return valid JSON after retries; using evidence-only fallback"
        )
        return comparative_analysis_from_contexts(
            original_analysis,
            scraped_contexts,
            company_name,
            user_query=question,
        )

# Singleton helper
financial_agent = FinancialAgent()
