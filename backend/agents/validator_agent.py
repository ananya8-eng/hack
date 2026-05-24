import re
import logging

from backend.agents.llm_client import llm_client

logger = logging.getLogger(__name__)

class ValidatorAgent:

    def validate_scraped_content(
        self,
        scraped_data: dict,
        target_company: str,
        target_competitors: list,
        scrape_requests: list | None = None,
    ) -> dict:
        """
        Validates scraped data before integration into the context window.
        Uses the configured LLM chain (NVIDIA first), otherwise executes deterministic validation rules.
        """
        text = scraped_data.get("text", "")
        source = scraped_data.get("source", "Unknown")
        scraped_company = scraped_data.get("company", "Unknown").upper().strip()
        filing_type = scraped_data.get("filing_type", "10-K").upper().strip()
        search_query = scraped_data.get("search_query", "")
        is_web = filing_type == "WEB" or bool(search_query)

        logger.info(f"Validator Agent auditing source: {source} ({scraped_company})...")

        plan_summary = ""
        if scrape_requests:
            plan_lines = []
            for req in scrape_requests:
                plan_lines.append(
                    f"- {req.get('type')}: company={req.get('company')}, "
                    f"query={req.get('query', '')[:120]}, purpose={req.get('purpose', '')}"
                )
            plan_summary = "\n".join(plan_lines)

        prompt = f"""
        [System] You are an elite AI Financial Compliance and Validator Agent.
        Audit this scraped document to verify it is authentic, recent, and highly relevant.
        
        [Target Profile]
        Target Company: {target_company}
        Allowed Competitors/Peers: {", ".join(target_competitors)}
        Agent Scrape Plan:
        {plan_summary or "N/A"}
        Web Search Query (if any): {search_query or "N/A"}
        
        [Scraped Document Metadata]
        Source: {source}
        Declared Company: {scraped_company}
        Filing Type: {filing_type}
        
        [Content Snippet]
        {text[:2000]}
        
        [Task]
        Return a strict JSON document validating this content. Ensure the keys match exactly:
        {{
            "is_valid": true/false,
            "relevance_score": 0.0 to 1.0 (relevance to target company or its allowed competitors),
            "freshness_rating": "High / Medium / Low",
            "trust_source": true/false (true if official filing, regulatory website, or trusted SEC EDGAR archive),
            "rejection_reason": "Reason if is_valid is false, otherwise null",
            "cleaned_content": "A high-quality extracted text summary, excluding any HTML tags, duplicate headers, or boilerplate legalese."
        }}
        """

        parsed = llm_client.generate_json(prompt, temperature=0.0)
        if parsed:
            return parsed

        # ==========================================
        # DETERMINISTIC VALIDATION FALLBACK
        # ==========================================
        logger.info("Executing Deterministic Validation Fallback...")

        is_valid = True
        rejection_reason = None
        relevance_score = 1.0
        freshness_rating = "High"
        trust_source = True
        
        text_lower = text.lower()
        company_clean = target_company.upper().strip()
        allowed_comps_upper = [c.upper().strip() for c in target_competitors]

        # Rule 1: Reject if the document content is empty or extremely short
        if len(text.strip()) < 200:
            is_valid = False
            rejection_reason = "Scraped content is too short or empty, indicating a failed download or empty document."
            relevance_score = 0.0

        # Rule 2: Company relevance (relaxed for web_search enrichment)
        elif is_web:
            query_tokens = [
                w for w in re.split(r"\W+", (search_query or "").lower()) if len(w) > 3
            ]
            token_hits = sum(1 for w in query_tokens if w in text_lower)
            target_hits = len(re.findall(rf"\b{re.escape(company_clean)}\b", text.upper()))
            if token_hits >= 1 or target_hits >= 1 or len(text.strip()) >= 500:
                relevance_score = max(relevance_score, 0.75)
            else:
                relevance_score = 0.45

        elif (
            scraped_company != "UNKNOWN"
            and scraped_company != company_clean
            and scraped_company not in allowed_comps_upper
            and scraped_company != "EXTERNAL"
        ):
            mentions_target = len(re.findall(rf"\b{re.escape(company_clean)}\b", text.upper()))
            mentions_comps = sum(
                len(re.findall(rf"\b{re.escape(c)}\b", text.upper()))
                for c in allowed_comps_upper
            )

            if mentions_target == 0 and mentions_comps == 0:
                is_valid = False
                rejection_reason = (
                    f"Company alignment mismatch. Document is about {scraped_company}, "
                    f"not target '{company_clean}' or planned peers {allowed_comps_upper}."
                )
                relevance_score = 0.1
            else:
                relevance_score = 0.6
        
        # Rule 3: Detect standard SPAM pages / generic login panels / error pages
        spam_keywords = ["404 not found", "access denied", "robot check", "captcha", "cookie policy", "sign in to your account", "paywall", "subscribe to read"]
        if is_valid:
            for kw in spam_keywords:
                if kw in text_lower:
                    is_valid = False
                    rejection_reason = f"Security gate or error page detected. Found keyword: '{kw}'."
                    relevance_score = 0.0
                    trust_source = False
                    break

        # Rule 4: Source Trust Audit
        if is_valid:
            if "EDGAR" in source.upper() or "FILING" in source.upper() or "SEC" in source.upper() or "GOV" in source.upper():
                trust_source = True
                relevance_score = max(relevance_score, 0.9)
            elif (
                not is_web
                and (
                    "BLOG" in source.upper()
                    or "FORUM" in source.upper()
                )
            ):
                trust_source = False
                relevance_score = min(relevance_score, 0.5)
                rejection_reason = "Rejected due to untrusted/unofficial source (e.g. blog or forum post)."
                is_valid = False

        # Rule 5: Freshness audit based on year markers (e.g. rejecting things from > 5 years ago if they declare high freshness)
        years_found = [int(y) for y in re.findall(r"\b(20\d{2})\b", text_lower)]
        if years_found:
            max_year = max(years_found)
            # Suppose current mock year is 2026
            if max_year < 2020:
                freshness_rating = "Low"
                # We can still accept it if it's explicitly a historical trend scrape, otherwise flag
            elif max_year >= 2024:
                freshness_rating = "High"
            else:
                freshness_rating = "Medium"

        # Content cleaning: Extract high quality text snippets, removing extra spaces
        cleaned = text.strip()
        # Regex to strip excessive linebreaks
        cleaned = re.sub(r'\n\s*\n', '\n', cleaned)
        cleaned_summary = cleaned[:3000] # Keep a rich snippet of the validated content

        return {
            "is_valid": is_valid,
            "relevance_score": round(relevance_score, 2),
            "freshness_rating": freshness_rating,
            "trust_source": trust_source,
            "rejection_reason": rejection_reason,
            "cleaned_content": cleaned_summary
        }

# Singleton helper
validator_agent = ValidatorAgent()
