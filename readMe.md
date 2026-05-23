# AI-Powered Financial Intelligence Platform — Final Architecture Guide

## Project Overview

Build an AI-powered financial filing intelligence platform that:

- Accepts uploaded financial filing PDFs
- Extracts important narrative sections
- Detects operational/business risks
- Performs sentiment analysis
- Uses AI agents with LangGraph
- Dynamically decides when external web scraping is needed
- Fetches competitor and previous filings
- Validates scraped data
- Generates comparative insights
- Provides a RAG chatbot with citations
- Displays insights in an interactive dashboard

---

# Final Architecture

```text
User Uploads Filing PDF
          ↓

PDF Processing Pipeline
(extract → sections → chunk → embeddings)
          ↓

Financial Intelligence Agent (Qwen)
          ↓

Agent decides:
- Is more context needed?
- Need previous filings?
- Need competitor comparison?
          ↓

Web Scraping Tool
          ↓

Validator Agent
          ↓

Validated External Context
          ↓

Financial Intelligence Agent (Re-analysis)
          ↓

Dashboard + Chatbot
```

---

# Final Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js |
| Styling | Tailwind CSS |
| Backend | FastAPI |
| Agent Framework | LangGraph |
| Main AI Model | Qwen2.5 3B Instruct |
| LLM Runtime | Ollam(locally running) -> nvdia->grok->huggingface->gemini (one serves as fallback when preceeding privider fails) |
| Embeddings | BAAI/bge-large-en-v1.5 |
| Vector Database | ChromaDB |
| PDF Parsing | PyMuPDF |
| Section Extraction | Regex + NLP |
| Chunking | LangChain |
| Sentiment Model | FinBERT |
| Web Scraping | BeautifulSoup + sec-edgar-downloader |
| Charts | Recharts |
| Optional DB | PostgreSQL |

---

# Final Agent Architecture

## Agent 1 — Financial Intelligence Agent

### Purpose
Main reasoning agent.

### Responsibilities

- Risk analysis
- Sentiment analysis
- Severity scoring
- Executive summaries
- Comparative analysis
- Deciding when scraping is required
- Detecting missing context
- Competitor identification
- Historical trend analysis
- Explainability generation

### Uses

- Qwen2.5 via Ollama
- ChromaDB retrieval tool
- Web scraping tool

---

## Agent 2 — Validator Agent

### Purpose
Validate scraped data before using it.

### Responsibilities

- Validate company relevance
- Validate filing type
- Validate filing freshness
- Reject irrelevant webpages
- Reject outdated filings
- Prevent noisy enrichment
- Validate competitor relevance
- Validate scraped context quality

### Example Validation Rules

Reject if:

- source is not an official filing
- filing is too old
- unrelated company detected
- duplicate content
- suspicious webpage

---

# What Is NOT An Agent

These are deterministic backend modules.

| Component | Type |
|---|---|
| PDF Extraction | Backend Module |
| Section Extraction | Backend Module |
| Chunking | Backend Module |
| Embedding Generation | Backend Module |
| ChromaDB Storage | Backend Module |
| Web Scraping Execution | Tool |

---

# Complete System Flow

## STEP 1 — Upload Filing

User uploads:

```text
10-K / 10-Q PDF
```

---

## STEP 2 — PDF Extraction

### Tool
PyMuPDF

### Purpose
Extract raw text from PDF.

### Example

```python
import fitz

pdf = fitz.open("report.pdf")
text = ""

for page in pdf:
    text += page.get_text()
```

---

# STEP 3 — Narrative Section Extraction

### Purpose
Extract only important narrative sections.

### Important Sections

- Risk Factors
- MD&A
- Forward Looking Statements

### Why?

Avoid:

- tables
- balance sheets
- irrelevant financial statements
- repeated headers

### Approach

Use regex-based heading detection.

### Example

```python
import re

pattern = r"ITEM 1A\.(.*?)ITEM 2\."

match = re.search(pattern, text, re.DOTALL)

risk_section = match.group(1)
```

---

# STEP 4 — Chunking

### Purpose
Split large sections into smaller semantic chunks.

### Recommended

- Chunk size: 700
- Overlap: 100

### Tool
LangChain RecursiveCharacterTextSplitter

### Example

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=700,
    chunk_overlap=100
)

chunks = splitter.split_text(risk_section)
```

---

# STEP 5 — Embeddings

### Purpose
Convert chunks into semantic vectors.

### Embedding Model
BAAI/bge-large-en-v1.5

### Example

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer(
    "BAAI/bge-large-en-v1.5"
)

embedding = model.encode(chunks[0])
```

---

# STEP 6 — Store In ChromaDB

### Purpose
Store semantic vectors for RAG retrieval.

### Example

```python
import chromadb

client = chromadb.PersistentClient(path="./db")

collection = client.get_or_create_collection("filings")
```

---

# STEP 7 — Financial Intelligence Agent Analysis

## Main Reasoning Phase

Agent analyzes:

- operational risks
- sentiment
- uncertainty
- management tone
- business concerns

### Example Prompt

```text
Analyze this filing section.

Return:
- risks
- severity
- supporting evidence
- sentiment
- executive summary
```

---

# STEP 8 — Agent Decides Whether Scraping Is Needed

## Core Agentic Behavior

Agent determines:

```text
Do I already have enough context?
```

---

# Conditions That Trigger Scraping

| Condition | Example |
|---|---|
| Missing context | vague risk description |
| Historical comparison needed | previous year trend |
| Competitor comparison needed | industry-wide issue |
| Low confidence | insufficient evidence |
| User asks comparison | compare with AMD |

---

# Structured Decision Output

```json
{
  "needs_scraping": true,
  "reason": "Need competitor comparison",
  "targets": [
    "AMD latest filing",
    "Intel latest filing"
  ]
}
```

---

# STEP 9 — Web Scraping Tool

## Purpose
Fetch contextual financial data.

### Fetch:

- previous filings
- competitor filings
- earnings reports
- industry reports

---

# Recommended Tools

## SEC Filing Fetching

```bash
pip install sec-edgar-downloader
```

### Example

```python
from sec_edgar_downloader import Downloader

loader = Downloader("filings")

loader.get("10-K", "NVDA")
```

---

# HTML Scraping

### Tool
BeautifulSoup

### Example

```python
import requests
from bs4 import BeautifulSoup

html = requests.get(url).text
soup = BeautifulSoup(html, "html.parser")
```

---

# STEP 10 — Validator Agent

## Purpose
Validate scraped content.

### Validator Checks

- correct company
- correct filing type
- recent filing
- trusted source
- useful comparison

### Example

Reject:

```text
Random blog article
```

Accept:

```text
Official SEC 10-K filing
```

---

# STEP 11 — Financial Agent Re-analysis

Agent now compares:

- uploaded filing
- previous filing
- competitor filings

### Example Insights

```text
NVIDIA mentions supply chain risks 18 times.
AMD mentions them only 6 times.
```

```text
Management tone became more cautious compared to previous year.
```

---

# STEP 12 — Dashboard

## Dashboard Components

### 1. Filing Viewer

- highlighted risk words
- clickable evidence
- page navigation

---

### 2. Risk Panel

Display:

- detected risks
- severity levels
- evidence

---

### 3. Sentiment Panel

Display:

- sentiment score
- positive/negative classification
- tone trends

---

### 4. Comparison Panel

Display:

- competitor comparisons
- previous filing trends
- risk evolution

---

### 5. Chatbot Panel

Display:

- citation-backed answers
- conversational querying

---

# Chatbot Architecture

## Flow

```text
User Question
      ↓
Embedding Generation
      ↓
ChromaDB Retrieval
      ↓
Relevant Chunks
      ↓
Qwen Response
```

---

# RAG Prompting Rules

Always:

- answer ONLY from retrieved context
- provide citations
- avoid hallucinations

---

# Suggested Folder Structure

```text
backend/
 ├── agents/
 │    ├── financial_agent.py
 │    ├── validator_agent.py
 │
 ├── tools/
 │    ├── scraper.py
 │    ├── chroma_tool.py
 │    ├── embedding_tool.py
 │
 ├── ingestion/
 │    ├── pdf_extractor.py
 │
 ├── extraction/
 │    ├── section_extractor.py
 │
 ├── rag/
 │    ├── chunking.py
 │    ├── retrieval.py
 │
 ├── graph/
 │    ├── langgraph_flow.py
 │
 ├── api/
 │    ├── routes.py
 │
frontend/
 ├── dashboard/
 ├── chatbot/
 ├── filing-viewer/
 ├── charts/
 └── components/
```

---

# Recommended Python Packages

```bash
pip install fastapi uvicorn
pip install pymupdf
pip install chromadb
pip install sentence-transformers
pip install langchain
pip install langgraph
pip install requests beautifulsoup4
pip install sec-edgar-downloader
pip install transformers
pip install ollama
```

---

# Ollama Setup

## Install

https://ollama.com

---

# Pull Qwen Model

```bash
ollama pull qwen2.5:7b-instruct
```

---

# Run Model

```bash
ollama run qwen2.5:7b-instruct
```

---

# Example Ollama API Call

```python
import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen2.5:7b-instruct",
        "prompt": "Analyze financial risks",
        "stream": False
    }
)
```

---

# Final Architecture Summary

## Agents

| Agent | Purpose |
|---|---|
| Financial Intelligence Agent | reasoning + orchestration |
| Validator Agent | trust + validation |

---

## Tools

| Tool | Purpose |
|---|---|
| PDF Extraction Tool | extract text |
| Chunking Tool | split text |
| Embedding Tool | generate embeddings |
| ChromaDB Tool | semantic retrieval |
| Web Scraping Tool | fetch external filings |

---

# Final Key Insight

The system is NOT:

```text
simple PDF summarization
```

It becomes:

```text
Adaptive AI Financial Intelligence Platform
```

because:

- AI analyzes uploaded filings
- AI decides when external enrichment is needed
- AI fetches contextual filings dynamically
- AI validates scraped data
- AI performs comparative financial reasoning
- AI generates explainable insights

