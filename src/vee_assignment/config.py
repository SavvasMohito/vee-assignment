from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


class Settings(BaseModel):
    openai_api_key: str = Field(min_length=1)
    openai_model: str = Field(default="gpt-4.1-mini", min_length=1)
    jina_api_key: str = Field(min_length=1)
    jina_gl: str = Field(default="GB", min_length=2)
    jina_hl: str = Field(default="en", min_length=2)
    max_research_pages: int = Field(default=3, ge=1, le=5)
    request_timeout_seconds: float = Field(default=20.0, gt=0)

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        try:
            return cls(
                openai_api_key=os.getenv("OPENAI_API_KEY", ""),
                openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
                jina_api_key=os.getenv("JINA_API_KEY", ""),
                jina_gl=os.getenv("JINA_GL", "GB"),
                jina_hl=os.getenv("JINA_HL", "en"),
                max_research_pages=int(os.getenv("MAX_RESEARCH_PAGES", "3")),
                request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
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
        "jina_gl": "JINA_GL",
        "jina_hl": "JINA_HL",
        "max_research_pages": "MAX_RESEARCH_PAGES",
        "request_timeout_seconds": "REQUEST_TIMEOUT_SECONDS",
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
