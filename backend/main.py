import logging
import uuid
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import get_settings
from backend.graph.langgraph_flow import run_financial_pipeline
from backend.ingestion.pdf_extractor import extract_pdf_text
from backend.tools.embedding_tool import embedding_manager
from backend.logging_config import configure_logging
from backend.guardrails import guardrails
from backend.rag.chat_comparison import run_chat_peer_comparison
from backend.rag.retrieval import rag_chatbot
from backend.tools.scrape_plan import is_comparison_query
from backend.reports_store import REPORTS_DB, append_report_log

configure_logging()
logger = logging.getLogger("backend.main")
settings = get_settings()

app = FastAPI(title="AI-Powered Financial Intelligence Platform API")


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "aegis-financial-api",
        "guardrails_enabled": settings.guardrails_enabled,
    }


@app.on_event("startup")
def _configure_runtime_logging() -> None:
    """Re-apply filters after uvicorn attaches access log handlers."""
    configure_logging()
    if settings.preload_embeddings_on_startup:
        logger.info("Preloading embedding model at startup...")
        embedding_manager.initialize()


# Enable CORS for frontend connection (Next.js)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    report_id: str
    message: str

class TriggerRequest(BaseModel):
    report_id: str
    query: Optional[str] = ""


def _guard_or_http(result, status_code: int = 400):
    if result.allowed:
        return None
    raise HTTPException(
        status_code=status_code,
        detail={
            "guardrail_blocked": True,
            "violations": [
                {"code": v.code, "message": v.message, "severity": v.severity}
                for v in result.violations
            ],
            "message": result.user_message(),
        },
    )

# Utility to guess company ticker/name from filename
def guess_company_from_filename(filename: str) -> str:
    fn_upper = filename.upper()
    if "NVDA" in fn_upper or "NVIDIA" in fn_upper:
        return "NVIDIA"
    elif "AMD" in fn_upper:
        return "AMD"
    elif "INTC" in fn_upper or "INTEL" in fn_upper:
        return "Intel"
    elif "AAPL" in fn_upper or "APPLE" in fn_upper:
        return "Apple"
    elif "MSFT" in fn_upper or "MICROSOFT" in fn_upper:
        return "Microsoft"
    elif "GOOG" in fn_upper or "ALPHABET" in fn_upper or "GOOGLE" in fn_upper:
        return "Google"
    elif "META" in fn_upper:
        return "Meta"
    elif "AMZN" in fn_upper or "AMAZON" in fn_upper:
        return "Amazon"
    elif "TSLA" in fn_upper or "TESLA" in fn_upper:
        return "Tesla"
        
    # Default fallback
    name_parts = filename.split(".")[0].split("_")
    return name_parts[0].capitalize()

def _apply_langgraph_step(report_id: str, node_name: str, node_update: dict, accumulated: dict) -> None:
    """Push incremental LangGraph node output into the in-memory report for polling UI."""
    report = REPORTS_DB.get(report_id)
    if not report:
        return
    if report.get("status") == "queued":
        report["status"] = "processing"
    if node_update.get("logs"):
        report["logs"] = list(accumulated.get("logs", []))
    if node_update.get("current_step"):
        report["current_step"] = node_update["current_step"]
    report["current_node"] = node_name


def run_agent_pipeline_task(
    report_id: str,
    raw_text: str,
    company: str,
    query: str,
):
    """
    Background worker that updates the reports DB with live LangGraph steps.
    """
    try:
        append_report_log(
            report_id,
            "LangGraph pipeline started.",
            step="Running agent workflow...",
            status="processing",
        )

        def on_step(node_name: str, node_update: dict, accumulated: dict) -> None:
            _apply_langgraph_step(report_id, node_name, node_update, accumulated)

        def on_progress(message: str, step: str | None = None) -> None:
            append_report_log(report_id, message, step=step)

        final_state = run_financial_pipeline(
            raw_text,
            company,
            query,
            on_step=on_step,
            report_id=report_id,
            on_progress=on_progress,
        )
        
        # Extract fields from the LangGraph AgentState
        original_analysis = final_state.get("original_analysis", {})
        final_comparative = final_state.get("final_comparative_analysis", {})
        sections = final_state.get("sections", {})

        # Reshape into the flat structure the frontend expects:
        # result.risks, result.sentiment, result.sections, result.final_comparative_analysis
        reshaped_result = {
            "raw_text": raw_text,
            "sections": sections,
            "section_catalog": final_state.get("section_catalog", []),
            "risks": original_analysis.get("risks", []),
            "sentiment": original_analysis.get("sentiment", {}),
            "executive_summary": original_analysis.get("executive_summary", ""),
            "mda_summary": original_analysis.get("mda_summary", ""),
            "future_challenges": original_analysis.get("future_challenges", []),
            "sentiment_shift_notes": original_analysis.get("sentiment_shift_notes", ""),
            "explainability": original_analysis.get("explainability", ""),
            "needs_scraping": original_analysis.get("needs_scraping", False),
            "targets": original_analysis.get("targets", []),
            "scrape_requests": original_analysis.get("scrape_requests", []),
            "scraping_reason": final_state.get("scraping_reason", ""),
            "final_comparative_analysis": final_comparative,
        }

        REPORTS_DB[report_id]["status"] = "complete"
        REPORTS_DB[report_id]["current_step"] = final_state.get("current_step", "Pipeline Completed")
        REPORTS_DB[report_id]["logs"] = final_state.get("logs", [])
        REPORTS_DB[report_id]["result"] = reshaped_result
        
        logger.info(f"Background LangGraph pipeline completed for report: {report_id}")
    except Exception as e:
        logger.error("Pipeline failed for report %s: %s", report_id, e)
        REPORTS_DB[report_id]["status"] = "failed"
        REPORTS_DB[report_id]["current_step"] = "Execution Failed"
        REPORTS_DB[report_id]["logs"].append(f"CRITICAL ERROR: {str(e)}")

def run_upload_pipeline_task(
    report_id: str,
    file_bytes: bytes,
    filename: str,
    company: str,
    user_query: str,
) -> None:
    """Extract PDF in background, then run LangGraph (keeps /api/upload fast)."""
    try:
        append_report_log(
            report_id,
            f"Extracting text from {filename} ({len(file_bytes):,} bytes)...",
            step="Extracting PDF text...",
            status="processing",
        )
        extracted_text = extract_pdf_text(file_bytes)
        char_count = len(extracted_text.strip())
        if char_count < 100:
            raise ValueError(
                "Could not extract enough text from this PDF. "
                "Try a digital 10-Q/10-K PDF (not a scanned image-only file)."
            )
        append_report_log(
            report_id,
            f"Extracted {char_count:,} characters from filing.",
            step="PDF extraction complete",
        )
        run_agent_pipeline_task(report_id, extracted_text, company, user_query)
    except Exception as exc:
        logger.error("Upload pipeline failed for %s: %s", report_id, exc)
        report = REPORTS_DB.get(report_id)
        if report:
            report["status"] = "failed"
            report["current_step"] = "Upload / extraction failed"
            report["logs"] = list(report.get("logs", [])) + [f"CRITICAL ERROR: {exc}"]


@app.post("/api/upload")
async def upload_filing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    company_name: Optional[str] = Form(None),
    user_query: Optional[str] = Form("")
):
    """
    Accepts PDF immediately; extraction + LangGraph run in the background.
    """
    filename = file.filename or "filing.pdf"
    logger.info("Received upload request: %s", filename)

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF filings are supported.")

    try:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")

        company = company_name if company_name else guess_company_from_filename(filename)
        query_guard = guardrails.check_upload_query(user_query or "")
        _guard_or_http(query_guard)

        report_id = str(uuid.uuid4())

        REPORTS_DB[report_id] = {
            "id": report_id,
            "filename": filename,
            "company_name": company,
            "status": "queued",
            "current_step": "Upload received — queued for extraction",
            "logs": [
                f"PDF upload received: {filename} ({len(file_bytes):,} bytes).",
                f"Company profile: '{company}'.",
                "Pipeline will start shortly (poll this report for live logs).",
            ],
            "result": None,
        }

        background_tasks.add_task(
            run_upload_pipeline_task,
            report_id,
            file_bytes,
            filename,
            company,
            user_query or "",
        )

        logger.info("Queued background pipeline for report %s", report_id)
        return {
            "success": True,
            "report_id": report_id,
            "company_name": company,
            "status": "queued",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload error: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to process upload: {str(e)}")

@app.get("/api/reports")
async def get_all_reports():
    """
    Returns list of all analyzed reports.
    """
    return [
        {
            "id": item["id"],
            "filename": item["filename"],
            "company_name": item["company_name"],
            "status": item["status"],
            "current_step": item["current_step"],
            "logs_count": len(item["logs"])
        }
        for item in REPORTS_DB.values()
    ]

@app.get("/api/reports/{report_id}")
async def get_report(report_id: str):
    """
    Returns the full details and result of a report.
    """
    if report_id not in REPORTS_DB:
        raise HTTPException(status_code=404, detail="Report not found.")
    return REPORTS_DB[report_id]

@app.get("/api/reports/{report_id}/status")
async def get_report_status(report_id: str):
    """
    Returns just the execution logs and current step. Ideal for polling.
    """
    if report_id not in REPORTS_DB:
        raise HTTPException(status_code=404, detail="Report not found.")
    report = REPORTS_DB[report_id]
    return {
        "id": report["id"],
        "status": report["status"],
        "current_step": report["current_step"],
        "logs": report["logs"]
    }

@app.post("/api/reports/trigger")
async def trigger_analysis(req: TriggerRequest, background_tasks: BackgroundTasks):
    """
    Re-runs the LangGraph agent for a report with a new specific query.
    """
    report_id = req.report_id
    if report_id not in REPORTS_DB:
        raise HTTPException(status_code=404, detail="Report not found.")
        
    report = REPORTS_DB[report_id]
    result = report.get("result")
    if not result:
        raise HTTPException(status_code=400, detail="Report has not finished processing yet.")

    query_guard = guardrails.check_upload_query(req.query or "")
    _guard_or_http(query_guard)

    raw_text = result.get("raw_text", "")
    company = report["company_name"]

    # Reset status
    report["status"] = "queued"
    report["current_step"] = "Re-triggering pipeline..."
    report["logs"] = ["Re-triggering LangGraph agent pipeline with new query.", f"Query: '{req.query}'"]
    report["result"] = None
    
    # Spawn background task
    background_tasks.add_task(
        run_agent_pipeline_task,
        report_id,
        raw_text,
        company,
        req.query
    )
    
    return {
        "success": True,
        "report_id": report_id,
        "status": "queued"
    }

@app.post("/api/chat")
async def chatbot_query(req: ChatRequest):
    """
    RAG chat: standard citation Q&A, or on-demand peer comparison (scrape → validate → SLM)
    when the user asks to compare against a competitor in natural language.
    """
    report_id = req.report_id
    if report_id not in REPORTS_DB:
        raise HTTPException(status_code=404, detail="Report not found.")

    chat_guard = guardrails.check_chat_message(req.message)
    if not chat_guard.allowed:
        payload = chat_guard.to_api_payload()
        payload["mode"] = "blocked"
        return payload

    safe_message = chat_guard.sanitized_text or req.message

    report = REPORTS_DB[report_id]
    company = report["company_name"]
    result = report.get("result") or {}
    filing_excerpt = ""
    sections = result.get("sections") or {}
    if isinstance(sections, dict) and sections:
        filing_excerpt = "\n".join(str(v) for v in sections.values() if v)[:8000]
    else:
        filing_excerpt = str(result.get("raw_text") or "")[:8000]

    if is_comparison_query(safe_message, filing_excerpt):
        if not result:
            raise HTTPException(
                status_code=400,
                detail="Report analysis is not ready yet. Wait for the pipeline to finish.",
            )
        comparison_res = run_chat_peer_comparison(report, safe_message)
        if comparison_res.get("handled"):
            if comparison_res.get("answer"):
                out_guard = guardrails.check_llm_text_output(comparison_res["answer"])
                if not out_guard.allowed:
                    blocked = out_guard.to_api_payload()
                    blocked["mode"] = "comparison"
                    return blocked
                comparison_res = {
                    **comparison_res,
                    "answer": out_guard.sanitized_text or comparison_res["answer"],
                }
            return comparison_res

    chatbot_res = rag_chatbot.query_chatbot(safe_message, company)
    chatbot_res["mode"] = "rag"
    return chatbot_res

if __name__ == "__main__":
    import uvicorn

    configure_logging()
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info",
        access_log=True,
    )
