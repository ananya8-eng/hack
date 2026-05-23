from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


OUTPUT = "docs/feature_rag_summary.pdf"


def bullet(text):
    return Paragraph(f"- {text}", styles["Body"])


styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="TitleCustom",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#111827"),
        spaceAfter=12,
    )
)
styles.add(
    ParagraphStyle(
        name="HeadingCustom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#1f2937"),
        spaceBefore=10,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#374151"),
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        name="Small",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#4b5563"),
    )
)


story = []
story.append(Paragraph("Feature/RAG Branch Summary", styles["TitleCustom"]))
story.append(
    Paragraph(
        "This document summarizes the practical RAG work implemented in the feature/rag branch. "
        "It is intended as a quick understanding guide, not a full technical specification.",
        styles["Body"],
    )
)

story.append(Paragraph("Current Status", styles["HeadingCustom"]))
status_data = [
    ["Area", "Status"],
    ["Backend RAG flow", "Working with report-scoped retrieval and structured responses"],
    ["Frontend", "Build and lint pass; chat still uses non-streaming endpoint"],
    ["Streaming endpoint", "Implemented; fallback path validated"],
    ["Real embeddings", "Supported in code, not fully validated end-to-end"],
]
table = Table(status_data, colWidths=[1.8 * inch, 4.8 * inch])
table.setStyle(
    TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]
    )
)
story.append(table)
story.append(Spacer(1, 8))

story.append(Paragraph("What Was Implemented", styles["HeadingCustom"]))
for item in [
    "Report-scoped RAG retrieval using report_id metadata and report-specific Chroma collections.",
    "Hybrid retrieval combining semantic search with BM25 keyword reranking when available.",
    "Query routing for factual, analytical, and comparative questions.",
    "Reranking and MMR-style filtering to improve relevance and reduce duplicate context.",
    "Conversation memory using report_id + session_id, including simple follow-up query contextualization.",
    "Structured financial prompt templates that enforce citations and insufficient-evidence behavior.",
    "Citation verification, hallucination checks, confidence scores, and structured RAG response metadata.",
    "RAG diagnostics endpoint for collection stats, embedding mode, reranker status, and sample retrieval.",
    "Streaming chat endpoint that uses Ollama streaming when available and falls back safely when unavailable.",
    "Section-scoped parent-child chunking with char ranges, parent chunk IDs, section names, and duplicate sentence counts.",
    "Frontend fixes for TypeScript build, lint cleanup, and chat session_id persistence.",
    "Backend dependency manifest through requirements.txt.",
]:
    story.append(bullet(item))

story.append(Paragraph("Main Files Added or Changed", styles["HeadingCustom"]))
for item in [
    "backend/rag/hybrid_search.py, reranker.py, query_router.py",
    "backend/rag/conversation_memory.py, prompt_templates.py",
    "backend/rag/citation_verifier.py, hallucination_guard.py, answer_formatter.py",
    "backend/rag/rag_diagnostics.py and retrieval.py",
    "backend/tools/chroma_tool.py and embedding_tool.py",
    "backend/graph/langgraph_flow.py and backend/main.py",
    "backend/rag/chunking.py",
    "frontend/app/page.tsx",
    "requirements.txt",
]:
    story.append(bullet(item))

story.append(Paragraph("Validation Completed", styles["HeadingCustom"]))
for item in [
    "Backend compile check passed: python -m compileall backend.",
    "Frontend lint passed: npm run lint.",
    "Frontend production build passed: npm run build.",
    "Smoke tested upload pipeline with synthetic filing text.",
    "Smoke tested /api/chat with cited, structured RAG response.",
    "Smoke tested /api/chat/stream and verified final metadata packet.",
    "Smoke tested /api/rag/diagnostics/{report_id} and verified chunk stats.",
]:
    story.append(bullet(item))

story.append(Paragraph("Remaining Gaps", styles["HeadingCustom"]))
for item in [
    "Real BAAI embeddings are supported but were not validated end-to-end because the model is large.",
    "Ollama live token streaming code exists, but local Ollama timed out during validation; fallback streaming was validated.",
    "Frontend does not yet consume /api/chat/stream; it still uses /api/chat.",
    "Citation and hallucination checks are heuristic, not full NLI/entailment systems.",
    "No formal automated pytest or frontend test suite was added yet.",
    "Chunk metadata does not yet include reliable PDF page numbers or filing dates.",
]:
    story.append(bullet(item))

story.append(Paragraph("Commits Created", styles["HeadingCustom"]))
for item in [
    "14931cf - fix: stabilize scoped rag pipeline",
    "19abf76 - feat: complete rag streaming and chunk scoping",
]:
    story.append(bullet(item))

story.append(Spacer(1, 8))
story.append(
    Paragraph(
        "Bottom line: the branch now has a working backend RAG implementation with scoped retrieval, citations, "
        "memory, diagnostics, and streaming support. It is usable, but the final production-grade polish requires "
        "real model validation, frontend streaming integration, and automated tests.",
        styles["Small"],
    )
)

doc = SimpleDocTemplate(
    OUTPUT,
    pagesize=letter,
    rightMargin=0.65 * inch,
    leftMargin=0.65 * inch,
    topMargin=0.55 * inch,
    bottomMargin=0.55 * inch,
)
doc.build(story)
print(OUTPUT)
