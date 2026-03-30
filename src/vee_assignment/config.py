from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


class Settings(BaseModel):
    openai_api_key: str = Field(min_length=1)
    openai_model: str = Field(default="gpt-4.1-mini", min_length=1)
    jina_api_key: str = Field(min_length=1)
    request_timeout_seconds: float = Field(default=20.0, gt=0)
    enable_observability_stream: bool = Field(default=False)
    observability_stream_prefix: str = Field(default="[trace]", min_length=1)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        try:
            return cls(
                openai_api_key=os.getenv("OPENAI_API_KEY", ""),
                openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                jina_api_key=os.getenv("JINA_API_KEY", ""),
                request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
                enable_observability_stream=_env_bool("ENABLE_OBSERVABILITY_STREAM", default=False),
                observability_stream_prefix=os.getenv("OBSERVABILITY_STREAM_PREFIX", "[trace]"),
            )
        except ValidationError as exc:
            raise ValueError(format_settings_error(exc)) from exc
        except ValueError as exc:
            raise ValueError("Invalid environment configuration. Ensure numeric env vars are valid numbers.") from exc


def format_settings_error(exc: ValidationError) -> str:
    field_to_env = {
        "openai_api_key": "OPENAI_API_KEY",
        "openai_model": "OPENAI_MODEL",
        "jina_api_key": "JINA_API_KEY",
        "request_timeout_seconds": "REQUEST_TIMEOUT_SECONDS",
        "observability_stream_prefix": "OBSERVABILITY_STREAM_PREFIX",
    }
    missing = []
    invalid = []
    for item in exc.errors():
        field = ".".join(str(part) for part in item["loc"])
        env_name = field_to_env.get(field, field)
        msg = item["msg"]
        if "at least 1 character" in msg:
            missing.append(env_name)
        else:
            invalid.append(f"{env_name}: {msg}")
    pieces = []
    if missing:
        pieces.append(f"Missing required env vars: {', '.join(sorted(missing))}")
    if invalid:
        pieces.append(f"Invalid env vars: {'; '.join(invalid)}")
    return " | ".join(pieces)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default
