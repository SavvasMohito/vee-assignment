from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx

URL_PATTERN = re.compile(r"https?://[^\s\])\"'>]+")


@dataclass(frozen=True)
class ResearchDocument:
    url: str
    content: str


class JinaClient:
    def __init__(
        self,
        api_key: str,
        timeout_seconds: float = 20.0,
        gl: str = "GB",
        hl: str = "en",
    ) -> None:
        self.api_key = api_key
        self.search_url = "https://s.jina.ai/"
        self.timeout_seconds = timeout_seconds
        self.gl = gl
        self.hl = hl

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Engine": "direct",
            "X-Retain-Images": "none",
            "X-Return-Format": "text",
            "X-Timeout": str(int(self.timeout_seconds)),
        }

    def search(self, query: str) -> str:
        payload = {
            "q": query.strip(),
            "gl": self.gl,
            "hl": self.hl,
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(self.search_url, headers=self._headers(), json=payload)
            response.raise_for_status()
        return self._extract_search_body(response)

    def collect_research(self, query: str, max_pages: int = 3) -> list[ResearchDocument]:
        search_text = self.search(query)
        urls = self.extract_urls(search_text)[:max_pages]
        source_block = "\n".join(urls) if urls else "No direct URLs extracted from SERP."
        merged = "SERP full-context output from s.jina.ai\n\n" f"Extracted URLs:\n{source_block}\n\n" f"{search_text}"
        return [ResearchDocument(url="search-results", content=merged[:12000])]

    @staticmethod
    def _extract_search_body(response: httpx.Response) -> str:
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response.text

        parsed = response.json()
        if isinstance(parsed, dict):
            # Common shape from Jina examples: {"code": ..., "data": "...", ...}
            data = parsed.get("data")
            if isinstance(data, str) and data.strip():
                return data
        return json.dumps(parsed, ensure_ascii=True)

    @staticmethod
    def extract_urls(raw_text: str) -> list[str]:
        seen: set[str] = set()
        urls: list[str] = []
        for found in URL_PATTERN.findall(raw_text):
            cleaned = found.rstrip(".,;")
            if cleaned not in seen:
                seen.add(cleaned)
                urls.append(cleaned)
        return urls
