from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    app_env: str = os.getenv("APP_ENV", os.getenv("ENV", "development")).strip().lower()
    deepgram_api_key: str = os.getenv("DEEPGRAM_API_KEY", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    hf_token: str = os.getenv("HF_TOKEN", "")
    deepgram_model: str = os.getenv("DEEPGRAM_MODEL", "nova-3")
    deepgram_diarize_model: str = os.getenv("DEEPGRAM_DIARIZE_MODEL", "latest")
    deepgram_detect_language: bool = _env_bool("DEEPGRAM_DETECT_LANGUAGE", True)
    speaker_repair_primary_model: str = os.getenv("SPEAKER_REPAIR_PRIMARY_MODEL", "gpt-4o-mini")
    speaker_repair_model: str = os.getenv("SPEAKER_REPAIR_MODEL", "gemini-2.5-flash")
    analysis_model: str = os.getenv("ANALYSIS_MODEL", "gemini-2.5-flash")

    # WhisperX settings
    whisperx_model: str = os.getenv("WHISPERX_MODEL", "small")  # tiny/base/small
    whisperx_batch_size: int = int(os.getenv("WHISPERX_BATCH_SIZE", "1"))
    whisperx_compute_type: str = os.getenv("WHISPERX_COMPUTE_TYPE", "int8")

    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    base_dir: Path = Path(__file__).parent
    rubric_path: Path = base_dir / "config" / "rubric.yaml"
    company_facts_path: Path = base_dir / "config" / "company_facts.yaml"
    transcripts_dir: Path = Path("/tmp/transcripts")
    upload_dir: Path = Path("/tmp/uploads")

    database_url: str = os.getenv("DATABASE_URL", "postgresql://fitnova:fitnova_dev@localhost:5432/fitnova")

    allowed_extensions: frozenset[str] = frozenset({"wav", "mp3", "m4a"})
    min_duration_sec: float = float(os.getenv("MIN_DURATION_SEC", "10"))
    quote_match_threshold: float = float(os.getenv("QUOTE_MATCH_THRESHOLD", "0.6"))
    default_org_id: str = os.getenv("DEFAULT_ORG_ID", "11111111-1111-1111-1111-111111111111")

    rubric_version: str = os.getenv("RUBRIC_VERSION", "1.0")
    company_facts_version: str = os.getenv("COMPANY_FACTS_VERSION", "1.0")
    analysis_version: str = os.getenv("ANALYSIS_VERSION", "1.0")

    # Retry settings (vendor retries and recovery)
    deepgram_max_retries: int = int(os.getenv("DEEPGRAM_MAX_RETRIES", "3"))
    gemini_max_retries: int = int(os.getenv("GEMINI_MAX_RETRIES", "2"))
    retry_base_delay_ms: int = int(os.getenv("RETRY_BASE_DELAY_MS", "1000"))

    @property
    def is_dev(self) -> bool:
        return self.app_env in {"dev", "development", "local", "test"}

    @property
    def log_sensitive_details(self) -> bool:
        return self.is_dev and _env_bool("LOG_SENSITIVE_DETAILS", True)

    @property
    def log_tracebacks(self) -> bool:
        return self.is_dev and _env_bool("LOG_TRACEBACKS", True)

    @property
    def log_validation_payloads(self) -> bool:
        return self.is_dev and _env_bool("LOG_VALIDATION_PAYLOADS", True)

    @property
    def log_file_metadata(self) -> bool:
        return self.is_dev and _env_bool("LOG_FILE_METADATA", True)

    def __init__(self) -> None:
        if not self.deepgram_api_key:
            raise RuntimeError("DEEPGRAM_API_KEY is not set")
        if not self.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
