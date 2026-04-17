from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


# Always let backend/.env override any existing shell env vars (including empty values).
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)


@dataclass(frozen=True)
class Settings:
    inference_backend: str = os.getenv("INFERENCE_BACKEND", "ollama")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "gemma3:4b")
    ollama_timeout_seconds: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    ollama_temperature: float = float(os.getenv("OLLAMA_TEMPERATURE", "0.2"))
    medgemma_model_id: str = os.getenv("MEDGEMMA_MODEL_ID", "google/medgemma-1.5-4b-it")
    medgemma_hf_token: str = os.getenv("MEDGEMMA_HF_TOKEN", "")
    medgemma_device: str = os.getenv("MEDGEMMA_DEVICE", "auto")
    medgemma_max_new_tokens: int = int(os.getenv("MEDGEMMA_MAX_NEW_TOKENS", "700"))


settings = Settings()
