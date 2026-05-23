from typing import TypedDict, List, Dict, Any, Optional
import uuid
import logging
from langgraph.graph import StateGraph, END

# Import backend modules
from backend.ingestion.pdf_extractor import extract_pdf_text
from backend.extraction.section_extractor import extract_sections
from backend.rag.chunking import split_text_into_chunks
from backend.tools.chroma_tool import chromadb_manager
from backend.agents.financial_agent import financial_agent
from backend.agents.validator_agent import validator_agent
from backend.tools.scraper import financial_scraper

logger = logging.getLogger(__name__)

# Define our robust LangGraph State
class AgentState(TypedDict):
    report_id: str
    company_name: str
    raw_text: str
    user_query: str
    
    # Extracted filing data
    sections: Dict[str, str]
    chunks_indexed: int
    
    # First reasoning phase
    original_analysis: Dict[str, Any]
    
    # Orchestration signals
    needs_scraping: bool
    scraping_reason: str
    targets: List[str]
    
    # Web scraping results
    scraped_documents: List[Dict[str, Any]]
    validated_contexts: List[Dict[str, Any]]
    
    # Final re-analysis phase
    final_comparative_analysis: Dict[str, Any]
    
    # Live execution steps for dashboard visualizer
    current_step: str
    logs: List[str]

# ==========================================
# GRAPH NODE FUNCTIONS
# ==========================================

def node_ingest_and_chunk(state: AgentState) -> Dict[str, Any]:
    logs = list(state.get("logs", []))
    logs.append("Step 1: Extracting narrative sections (Risk Factors, MD&A, FLS) from filing...")
    logger.info("LangGraph Node: Ingest & Chunk starting.")
    
    raw_text = state.get("raw_text", "")
    company = state.get("company_name", "Target Company")
    report_id = state.get("report_id", "")
    
    # Extract Narrative Sections
    sections = extract_sections(raw_text)
    logs.append(f"Successfully isolated: Risk Factors ({len(sections['risk_factors'])} chars), MD&A ({len(sections['mda'])} chars).")
    
    # Chunk and Index each section in Vector Database for RAG
    total_indexed = 0
    for section_name, text in sections.items():
        if not text:
            continue
        chunks = split_text_into_chunks(text)
        if chunks:
            ids = [f"{report_id}_{company}_{section_name}_{uuid.uuid4().hex[:6]}_{i}" for i in range(len(chunks))]
            metadata = [
                {
                    "report_id": report_id,
                    "company": company,
                    "section": section_name,
                    "chunk_index": i,
                    "filing_type": "uploaded_filing"
                }
                for i in range(len(chunks))
            ]
            chromadb_manager.add_chunks(chunks, metadata, ids)
            total_indexed += len(chunks)
            
    logs.append(f"ChromaDB Manager successfully indexed {total_indexed} semantic chunks for RAG Retrieval.")
    
    return {
        "sections": sections,
        "chunks_indexed": total_indexed,
        "current_step": "Ingestion & Chunking Complete",
        "logs": logs
    }

def node_financial_analysis(state: AgentState) -> Dict[str, Any]:
    logs = list(state.get("logs", []))
    logs.append("Step 2: Spawning Financial Intelligence Agent (Qwen2.5) for initial audit...")
    logger.info("LangGraph Node: Financial Analysis starting.")
    
    sections = state.get("sections", {})
    company = state.get("company_name", "Target Company")
    query = state.get("user_query", "")
    
    # We analyze the main Risk Factors text
    analysis_input = sections.get("risk_factors", "") + "\n" + sections.get("mda", "")
    analysis_result = financial_agent.analyze_filing(analysis_input, company, query)
    
    needs_scrape = analysis_result.get("needs_scraping", False)
    targets = analysis_result.get("targets", [])
    reason = analysis_result.get("reason", "")
    
    logs.append(f"Financial Agent audit finished. Detected {len(analysis_result.get('risks', []))} operational risks. Sentiment Score: {analysis_result.get('sentiment', {}).get('score', 0.0)}.")
    
    if needs_scrape:
        logs.append(f"💡 Agent decision: External context is required! Reason: '{reason}'. Scrape targets: {targets}.")
    else:
        logs.append("✅ Agent decision: Existing local context is sufficient. Skipping web enrichment.")
        
    return {
        "original_analysis": analysis_result,
        "needs_scraping": needs_scrape,
        "targets": targets,
        "scraping_reason": reason,
        "current_step": "Initial Financial Analysis Complete",
        "logs": logs
    }

def node_web_scraping(state: AgentState) -> Dict[str, Any]:
    logs = list(state.get("logs", []))
    targets = state.get("targets", [])
    reason = state.get("scraping_reason", "")
    
    logs.append(f"Step 3: Activating Web Scraping Tool to fetch targets: {targets}...")
    logger.info("LangGraph Node: Web Scraping starting.")
    
    scraped_docs = []
    for target in targets:
        logs.append(f"Scraper fetching latest 10-K SEC Edgar data for peer: '{target.upper()}'...")
        # Fetch filing
        res = financial_scraper.fetch_sec_filing(target, "10-K")
        if res.get("success"):
            scraped_docs.append(res)
            logs.append(f"Retrieved {len(res.get('text', ''))} characters of raw filing text from {res.get('source')}.")
        else:
            logs.append(f"⚠️ Failed to scrape data for {target}.")
            
    return {
        "scraped_documents": scraped_docs,
        "current_step": "Web Scraping Complete",
        "logs": logs
    }

def node_validation(state: AgentState) -> Dict[str, Any]:
    logs = list(state.get("logs", []))
    scraped_docs = state.get("scraped_documents", [])
    company = state.get("company_name", "Target Company")
    targets = state.get("targets", [])
    report_id = state.get("report_id", "")
    
    logs.append("Step 4: Spawning Validator Agent to audit external scraped content...")
    logger.info("LangGraph Node: Validation starting.")
    
    validated_contexts = []
    for doc in scraped_docs:
        audit_res = validator_agent.validate_scraped_content(doc, company, targets)
        
        if audit_res.get("is_valid", False):
            logs.append(
                f"✅ APPROVED: '{doc.get('company')}' content validated. "
                f"Relevance Score: {audit_res.get('relevance_score')}, "
                f"Freshness: {audit_res.get('freshness_rating')}, Source: Trusted."
            )
            # Store validated cleaned context
            validated_contexts.append({
                "source": doc.get("source"),
                "company": doc.get("company"),
                "text": audit_res.get("cleaned_content")
            })
            
            # Smart bonus: Index competitor chunks in ChromaDB too! This allows comparative chat citations!
            comp_chunks = split_text_into_chunks(audit_res.get("cleaned_content", ""))
            if comp_chunks:
                ids = [f"{report_id}_{doc.get('company')}_competitor_{uuid.uuid4().hex[:6]}_{i}" for i in range(len(comp_chunks))]
                metadata = [
                    {
                        "report_id": report_id,
                        "company": doc.get("company"),
                        "section": "competitor_analysis",
                        "chunk_index": i,
                        "filing_type": doc.get("filing_type", "10-K")
                    }
                    for i in range(len(comp_chunks))
                ]
                chromadb_manager.add_chunks(comp_chunks, metadata, ids)
        else:
            logs.append(f"❌ REJECTED: Content from '{doc.get('company')}' failed audit. Reason: {audit_res.get('rejection_reason')}")
            
    return {
        "validated_contexts": validated_contexts,
        "current_step": "Validation Complete",
        "logs": logs
    }

def node_comparative_reanalysis(state: AgentState) -> Dict[str, Any]:
    logs = list(state.get("logs", []))
    logs.append("Step 5: Initiating Comparative Re-Analysis (uploaded vs validated external contexts)...")
    logger.info("LangGraph Node: Comparative Re-Analysis starting.")
    
    orig_analysis = state.get("original_analysis", {})
    validated_ctxs = state.get("validated_contexts", [])
    company = state.get("company_name", "Target Company")
    
    comp_result = financial_agent.analyze_comparative(orig_analysis, validated_ctxs, company)
    
    logs.append("✅ Re-Analysis complete. Synthesized cross-company benchmarks, management tone shifts, and explainability factors.")
    logs.append("🎉 LangGraph Financial Intelligence pipeline executed successfully!")
    
    return {
        "final_comparative_analysis": comp_result,
        "current_step": "Pipeline Completed",
        "logs": logs
    }

# ==========================================
# GRAPH ROUTING
# ==========================================

def router_should_scrape(state: AgentState) -> str:
    """
    Conditional router that determines if we branch to web scraping
    or skip straight to completion.
    """
    if state.get("needs_scraping", False) and state.get("targets"):
        return "web_scraping"
    return "end"

# ==========================================
# COMPILE LANGGRAPH
# ==========================================

def build_financial_intelligence_graph() -> StateGraph:
    # 1. Initialize StateGraph with our State Schema
    builder = StateGraph(AgentState)
    
    # 2. Add Nodes
    builder.add_node("ingest_and_chunk", node_ingest_and_chunk)
    builder.add_node("financial_analysis", node_financial_analysis)
    builder.add_node("web_scraping", node_web_scraping)
    builder.add_node("validation", node_validation)
    builder.add_node("comparative_reanalysis", node_comparative_reanalysis)
    
    # 3. Define Edges (Workflows)
    builder.set_entry_point("ingest_and_chunk")
    
    builder.add_edge("ingest_and_chunk", "financial_analysis")
    
    # Conditional edge from financial_analysis
    builder.add_conditional_edges(
        "financial_analysis",
        router_should_scrape,
        {
            "web_scraping": "web_scraping",
            "end": END
        }
    )
    
    # Linear edges for the scraping/validation branch
    builder.add_edge("web_scraping", "validation")
    builder.add_edge("validation", "comparative_reanalysis")
    builder.add_edge("comparative_reanalysis", END)
    
    # Compile
    graph = builder.compile()
    return graph

# Instantiated graph runner helper
financial_graph = build_financial_intelligence_graph()

def run_financial_pipeline(raw_pdf_text: str, company: str, query: str = "", report_id: str = "") -> dict:
    """
    Synchronous helper to run the compiled LangGraph and return the complete State.
    """
    initial_state = {
        "report_id": report_id or uuid.uuid4().hex,
        "company_name": company,
        "raw_text": raw_pdf_text,
        "user_query": query,
        "sections": {},
        "chunks_indexed": 0,
        "original_analysis": {},
        "needs_scraping": False,
        "scraping_reason": "",
        "targets": [],
        "scraped_documents": [],
        "validated_contexts": [],
        "final_comparative_analysis": {},
        "current_step": "Pipeline Initialized",
        "logs": ["LangGraph agent pipeline spawned."]
    }
    
    final_state = financial_graph.invoke(initial_state)
    return final_state
