import os
import uuid
import logging
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Embedding mode: 'mock' for fast dev, 'real' for production
# Set EMBEDDING_MODE=real to use BAAI/bge-large-en-v1.5
os.environ.setdefault("EMBEDDING_MODE", "mock")

# Import our custom components
from backend.ingestion.pdf_extractor import extract_pdf_text
from backend.graph.langgraph_flow import run_financial_pipeline
from backend.rag.retrieval import rag_chatbot

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("backend.main")

app = FastAPI(title="AI-Powered Financial Intelligence Platform API")

# Enable CORS for frontend connection (Next.js)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In development, allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-Memory report database
REPORTS_DB = {}

class ChatRequest(BaseModel):
    report_id: str
    message: str
    session_id: Optional[str] = None

class TriggerRequest(BaseModel):
    report_id: str
    query: Optional[str] = ""

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

def run_agent_pipeline_task(report_id: str, raw_text: str, company: str, query: str):
    """
    Background worker that updates the reports DB with live LangGraph steps.
    """
    try:
        REPORTS_DB[report_id]["status"] = "processing"
        
        # Run the full LangGraph pipeline (pass report_id for scoped vector storage)
        final_state = run_financial_pipeline(raw_text, company, query, report_id=report_id)
        
        # Extract fields from the LangGraph AgentState
        original_analysis = final_state.get("original_analysis", {})
        final_comparative = final_state.get("final_comparative_analysis", {})
        sections = final_state.get("sections", {})

        # Reshape into the flat structure the frontend expects:
        # result.risks, result.sentiment, result.sections, result.final_comparative_analysis
        reshaped_result = {
            "raw_text": raw_text,
            "sections": sections,
            "risks": original_analysis.get("risks", []),
            "sentiment": original_analysis.get("sentiment", {}),
            "executive_summary": original_analysis.get("executive_summary", ""),
            "explainability": original_analysis.get("explainability", ""),
            "needs_scraping": original_analysis.get("needs_scraping", False),
            "targets": original_analysis.get("targets", []),
            "final_comparative_analysis": final_comparative,
        }

        REPORTS_DB[report_id]["status"] = "complete"
        REPORTS_DB[report_id]["current_step"] = final_state.get("current_step", "Pipeline Completed")
        REPORTS_DB[report_id]["logs"] = final_state.get("logs", [])
        REPORTS_DB[report_id]["result"] = reshaped_result
        
        logger.info(f"Background LangGraph pipeline completed for report: {report_id}")
    except Exception as e:
        logger.error(f"Error running pipeline in background: {str(e)}")
        REPORTS_DB[report_id]["status"] = "failed"
        REPORTS_DB[report_id]["current_step"] = "Execution Failed"
        REPORTS_DB[report_id]["logs"].append(f"❌ CRITICAL ERROR: {str(e)}")

@app.post("/api/upload")
async def upload_filing(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    company_name: Optional[str] = Form(None),
    user_query: Optional[str] = Form("")
):
    """
    Uploads a financial filing PDF, extracts text, and triggers
    the LangGraph Financial Agentic workflow in the background.
    """
    logger.info(f"Received upload request: {file.filename}")
    
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF filings are supported.")
        
    try:
        # Read file bytes
        file_bytes = await file.read()
        
        # Extract text from PDF
        extracted_text = extract_pdf_text(file_bytes)
        if len(extracted_text.strip()) < 100:
            raise HTTPException(status_code=400, detail="The uploaded PDF text content could not be extracted.")
            
        # Determine company name
        company = company_name if company_name else guess_company_from_filename(file.filename)
        
        # Create report ID
        report_id = str(uuid.uuid4())
        
        # Initialize DB entry
        REPORTS_DB[report_id] = {
            "id": report_id,
            "filename": file.filename,
            "company_name": company,
            "status": "queued",
            "current_step": "Ingesting PDF text...",
            "logs": ["PDF upload successful.", f"Extracted {len(extracted_text)} characters.", f"Identified company profile: '{company}'."],
            "result": None
        }
        
        # Trigger background task for LangGraph flow
        background_tasks.add_task(
            run_agent_pipeline_task,
            report_id,
            extracted_text,
            company,
            user_query
        )
        
        return {
            "success": True,
            "report_id": report_id,
            "company_name": company,
            "status": "queued"
        }
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
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
    Conversational RAG Chatbot query endpoint. Matches query against report embeddings.
    Supports multi-turn conversation via session_id.
    """
    report_id = req.report_id
    if report_id not in REPORTS_DB:
        raise HTTPException(status_code=404, detail="Report not found.")
        
    report = REPORTS_DB[report_id]
    company = report["company_name"]
    session_id = req.session_id or str(uuid.uuid4())
    
    # Ask chatbot with session and report scoping
    chatbot_res = rag_chatbot.query_chatbot(
        user_question=req.message,
        company_name=company,
        report_id=report_id,
        session_id=session_id,
    )
    chatbot_res["session_id"] = session_id
    return chatbot_res


@app.post("/api/chat/stream")
async def chatbot_query_stream(req: ChatRequest):
    """
    Streaming RAG Chatbot endpoint. Streams tokens as they are generated.
    """
    report_id = req.report_id
    if report_id not in REPORTS_DB:
        raise HTTPException(status_code=404, detail="Report not found.")

    report = REPORTS_DB[report_id]
    company = report["company_name"]
    session_id = req.session_id or str(uuid.uuid4())

    async def _stream():
        import json
        for event_type, payload in rag_chatbot.stream_chatbot(
            user_question=req.message,
            company_name=company,
            report_id=report_id,
            session_id=session_id,
        ):
            if event_type == "token":
                yield payload
            elif event_type == "metadata":
                payload["session_id"] = session_id
                yield "\n__META__" + json.dumps(payload)

    return StreamingResponse(_stream(), media_type="text/plain")


@app.get("/api/chat/{report_id}/history")
async def get_chat_history(report_id: str, session_id: str = None):
    """
    Returns conversation history for a report + session.
    """
    if report_id not in REPORTS_DB:
        raise HTTPException(status_code=404, detail="Report not found.")

    from backend.rag.conversation_memory import conversation_store
    if session_id:
        history = conversation_store.get_history(report_id, session_id)
    else:
        history = conversation_store.get_all_sessions(report_id)
    return {"report_id": report_id, "session_id": session_id, "history": history}


@app.get("/api/rag/diagnostics/{report_id}")
async def rag_diagnostics(report_id: str):
    """
    Returns RAG diagnostics for a report: chunk count, embedding status, sample queries.
    """
    if report_id not in REPORTS_DB:
        raise HTTPException(status_code=404, detail="Report not found.")

    from backend.rag.rag_diagnostics import get_diagnostics
    report = REPORTS_DB[report_id]
    company = report["company_name"]
    diagnostics = get_diagnostics(report_id, company)
    return diagnostics

if __name__ == "__main__":
    import uvicorn
    # Start server on port 8000
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
