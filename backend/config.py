from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    deepgram_api_key: str = os.getenv("DEEPGRAM_API_KEY", "")
    google_api_key: str = os.getenv("GOOGLE_API_KEY", "")
    hf_token: str = os.getenv("HF_TOKEN", "")

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
    default_org_id: str = os.getenv("DEFAULT_ORG_ID", "00000000-0000-0000-0000-000000000001")

    rubric_version: str = os.getenv("RUBRIC_VERSION", "1.0")
    company_facts_version: str = os.getenv("COMPANY_FACTS_VERSION", "1.0")
    analysis_version: str = os.getenv("ANALYSIS_VERSION", "1.0")

    def __init__(self) -> None:
        if not self.deepgram_api_key:
            raise RuntimeError("DEEPGRAM_API_KEY is not set")
        if not self.google_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
