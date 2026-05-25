"""Tests for LLM-driven chat agent loop."""
from unittest.mock import MagicMock, patch

from backend.rag.chat_agent import (
    AGENT_TOOLS,
    AgentSession,
    _bootstrap_rag_phase,
    _enforce_action,
    _rag_covers_query,
    execute_agent_tool,
    run_chat_agent,
)


def test_agent_tools_catalog_includes_core_tools():
    names = {t["name"] for t in AGENT_TOOLS}
    assert "rag_retrieve" in names or any("rag" in n for n in names)
    assert "web_search" in names
    assert "finish" in names


@patch("backend.rag.chat_agent.chromadb_manager")
def test_rag_retrieve_tool(mock_chroma):
    mock_chroma.query_similar_chunks.return_value = [
        {
            "document": "Apple competes with Samsung in smartphones.",
            "metadata": {"company": "Apple", "section": "risk", "chunk_index": 0},
        }
    ]
    session = AgentSession(
        company_name="Apple",
        user_message="Who are the competitors?",
        report={"company_name": "Apple", "result": {}},
    )
    obs = execute_agent_tool(session, "rag_retrieve", {"query": "competitors"})
    assert obs["success"] is True
    assert obs["chunks_found"] == 1
    assert len(session.citations) == 1


def test_rag_covers_competitor_query():
    session = AgentSession(
        company_name="Apple",
        user_message="Who are Apple's top smartphone competitors?",
        report={},
    )
    session.rag_chunks = [
        {
            "document": "The Company competes with Samsung, Google and other smartphone vendors.",
            "metadata": {"section": "risk"},
        }
    ]
    assert _rag_covers_query(session) is True


def test_web_search_blocked_when_rag_covers_query():
    session = AgentSession(
        company_name="Apple",
        user_message="Who are Apple's top smartphone competitors?",
        report={},
    )
    session.rag_bootstrap_done = True
    session.rag_covers_query = True
    action, msg = _enforce_action(session, "web_search")
    assert action == "finish"
    assert msg is not None


@patch("backend.rag.chat_agent._synthesize_answer_from_rag")
@patch("backend.rag.chat_agent._bootstrap_rag_phase")
@patch("backend.rag.chat_agent.llm_client")
@patch("backend.rag.chat_agent.execute_agent_tool")
def test_agent_loop_finishes_after_rag(mock_exec, mock_llm, mock_bootstrap, mock_synth):
    mock_synth.return_value = "Samsung and Google are named smartphone competitors in the filing."
    mock_llm.generate_json.side_effect = [
        {
            "think": "Bootstrap RAG already has competitor names.",
            "action": "finish",
            "action_input": {},
        },
    ]

    report = {
        "company_name": "Apple",
        "result": {
            "executive_summary": "Strong iPhone sales.",
            "risks": [],
            "sections": {"risk": "Competition from Samsung."},
        },
    }
    out = run_chat_agent(report, "What are Apple's main smartphone competitors?", max_steps=4)
    assert out["success"] is True
    assert out["mode"] == "agent"
    mock_bootstrap.assert_called_once()
    mock_exec.assert_not_called()


@patch("backend.rag.chat_agent._synthesize_answer_from_rag")
@patch("backend.rag.chat_agent.chromadb_manager")
@patch("backend.rag.chat_agent.llm_client")
@patch("backend.rag.chat_agent.execute_agent_tool")
def test_agent_loop_can_invoke_scrape_after_rag_insufficient(
    mock_exec, mock_llm, mock_chroma, mock_synth
):
    mock_chroma.query_similar_chunks.return_value = []
    mock_synth.return_value = "AMD margin comparison from SEC filing."
    mock_exec.return_value = {
        "success": True,
        "validated": True,
        "message": "Validated scrape",
        "excerpt": "AMD margin data",
    }
    mock_llm.generate_json.side_effect = [
        {
            "think": "RAG insufficient — fetch AMD SEC filing.",
            "action": "sec_filing_fetch",
            "action_input": {"company": "AMD", "filing_type": "10-K"},
        },
        {
            "think": "Answer with what we have.",
            "action": "finish",
            "action_input": {"answer": "Comparison pending more evidence."},
        },
    ]

    report = {
        "company_name": "NVIDIA",
        "result": {"executive_summary": "AI leadership.", "risks": []},
    }
    out = run_chat_agent(report, "Compare NVIDIA against AMD on margins", max_steps=4)
    assert out["mode"] == "agent"
    mock_exec.assert_called_once()
    assert mock_exec.call_args[0][1] == "sec_filing_fetch"
