from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx

from .config import settings
from .models import AnalysisResponse, RuleAlert, StructuredCBCReport
from .prompting import build_system_prompt, build_user_prompt


class OllamaClientError(RuntimeError):
    pass


class OllamaClient:
    async def analyze(
        self,
        *,
        image_base64: Optional[str],
        image_filename: Optional[str],
        patient_age: Optional[int],
        patient_sex: Optional[str],
        symptoms: Optional[str],
        clinical_notes: Optional[str],
        current_medications: Optional[str],
        alerts: list[RuleAlert],
        structured_report: Optional[StructuredCBCReport] = None,
    ) -> AnalysisResponse:
        user_message: dict[str, Any] = {
            "role": "user",
            "content": build_user_prompt(
                patient_age=patient_age,
                patient_sex=patient_sex,
                symptoms=symptoms,
                clinical_notes=clinical_notes,
                current_medications=current_medications,
                alerts=alerts,
                image_filename=image_filename,
                structured_report=structured_report,
            ),
        }
        if image_base64:
            user_message["images"] = [image_base64]

        payload: dict[str, Any] = {
            "model": settings.ollama_model,
            "stream": False,
            "format": "json",
            "options": {"temperature": settings.ollama_temperature},
            "messages": [
                {"role": "system", "content": build_system_prompt()},
                user_message,
            ],
        }

        async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
            try:
                response = await client.post(
                    f"{settings.ollama_base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise OllamaClientError(
                    "无法连接 Ollama，请确认 `ollama serve` 已启动且模型已拉取。"
                ) from exc

        content = response.json().get("message", {}).get("content", "")
        if not content:
            raise OllamaClientError("Ollama 未返回有效内容。")

        return AnalysisResponse.model_validate(_parse_json_content(content))


def _parse_json_content(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise OllamaClientError(
            "模型返回内容不是合法 JSON，请调整模型或提示词。"
        ) from exc
