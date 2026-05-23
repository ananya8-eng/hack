"""
Load `.env` from the project root and expose typed settings for the whole backend.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Load once at import; does not override variables already set in the shell.
load_dotenv(ENV_FILE, override=False)


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # API server
    api_host: str
    api_port: int
    cors_origins: str

    # NVIDIA NIM / integrate API (primary LLM)
    nvidia_api_key: str
    nvidia_api_base_url: str
    nvidia_model: str

    # xAI Grok
    grok_api_key: str
    grok_api_base_url: str
    grok_model: str

    # Hugging Face inference
    huggingface_api_key: str
    huggingface_model: str
    huggingface_inference_url: str

    # Google Gemini
    gemini_api_key: str
    gemini_model: str

    # LLM defaults
    llm_default_timeout: int

    # Embeddings & vector store
    use_mock_embeddings: bool
    embedding_model: str
    chroma_db_path: str
    preload_embeddings_on_startup: bool
    max_chunks_per_section: int
    max_chunks_per_filing: int
    map_analysis_chunk_chars: int
    max_map_passes: int
    max_heal_attempts: int

    # SEC EDGAR & scraping
    sec_edgar_company_name: str
    sec_edgar_email: str
    scraped_filings_dir: str
    scraper_user_agent: str

    @property
    def cors_origins_list(self) -> list[str]:
        if not self.cors_origins or self.cors_origins == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    hf_model = _env("HUGGINGFACE_MODEL", "Qwen/Qwen2.5-3B-Instruct")
    hf_key = _env("HUGGINGFACE_API_KEY") or _env("HF_TOKEN")
    gemini_key = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
    grok_key = _env("GROK_API_KEY") or _env("XAI_API_KEY")

    return Settings(
        api_host=_env("API_HOST", "127.0.0.1"),
        api_port=_env_int("API_PORT", 8000),
        cors_origins=_env("CORS_ORIGINS", "*"),
        nvidia_api_key=_env("NVIDIA_API_KEY"),
        nvidia_api_base_url=_env(
            "NVIDIA_API_BASE_URL",
            "https://integrate.api.nvidia.com/v1/chat/completions",
        ),
        nvidia_model=_env("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct"),
        grok_api_key=grok_key,
        grok_api_base_url=_env(
            "GROK_API_BASE_URL", "https://api.x.ai/v1/chat/completions"
        ),
        grok_model=_env("GROK_MODEL", "grok-2-latest"),
        huggingface_api_key=hf_key,
        huggingface_model=hf_model,
        huggingface_inference_url=_env(
            "HUGGINGFACE_INFERENCE_URL",
            f"https://api-inference.huggingface.co/models/{hf_model}",
        ),
        gemini_api_key=gemini_key,
        gemini_model=_env("GEMINI_MODEL", "gemini-2.0-flash"),
        llm_default_timeout=_env_int("LLM_DEFAULT_TIMEOUT", 90),
        use_mock_embeddings=_env_bool("USE_MOCK_EMBEDDINGS", False),
        embedding_model=_env("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5"),
        chroma_db_path=_env("CHROMA_DB_PATH", "./chroma_db"),
        preload_embeddings_on_startup=_env_bool("PRELOAD_EMBEDDINGS_ON_STARTUP", True),
        max_chunks_per_section=_env_int("MAX_CHUNKS_PER_SECTION", 80),
        max_chunks_per_filing=_env_int("MAX_CHUNKS_PER_FILING", 250),
        map_analysis_chunk_chars=_env_int("MAP_ANALYSIS_CHUNK_CHARS", 3500),
        max_map_passes=_env_int("MAX_MAP_PASSES", 24),
        max_heal_attempts=_env_int("MAX_HEAL_ATTEMPTS", 3),
        sec_edgar_company_name=_env("SEC_EDGAR_COMPANY_NAME", "AegisFinancialAgent"),
        sec_edgar_email=_env("SEC_EDGAR_EMAIL", "aegis@financialintel.ai"),
        scraped_filings_dir=_env("SCRAPED_FILINGS_DIR", "./scraped_filings"),
        scraper_user_agent=_env(
            "SCRAPER_USER_AGENT", "Mozilla/5.0 AegisFinancialAgent/1.0"
        ),
    )


def reload_settings() -> Settings:
    """Clear cache after .env changes (tests / hot reload)."""
    get_settings.cache_clear()
    load_dotenv(ENV_FILE, override=True)
    return get_settings()
