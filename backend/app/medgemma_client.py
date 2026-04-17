from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Optional

from .config import settings
from .models import AnalysisResponse, RuleAlert
from .prompting import build_system_prompt, build_user_prompt


class MedGemmaNotConfiguredError(RuntimeError):
    pass


class MedGemmaRuntimeError(RuntimeError):
    pass


def _coerce_medgemma_payload(payload: dict) -> dict:
    """Normalize common single-shot model formatting slips before validation."""
    if payload.get("risk_level") == "低风险|中风险|高风险":
        payload["risk_level"] = "中风险"

    if _looks_like_schema_instruction(payload.get("doctor_summary")):
        payload["doctor_summary"] = "MedGemma 未返回具体摘要，请结合规则命中和原始资料人工复核。"

    for key in (
        "abnormal_findings",
        "possible_causes",
        "next_steps",
        "urgent_transfer_reasons",
        "medication_watchouts",
    ):
        if isinstance(payload.get(key), list):
            payload[key] = [
                item for item in payload[key] if not _looks_like_schema_instruction(item)
            ]

    if isinstance(payload.get("citations"), list):
        payload["citations"] = [
            item
            for item in payload["citations"]
            if not (
                isinstance(item, dict)
                and (
                    _looks_like_schema_instruction(item.get("source"))
                    or _looks_like_schema_instruction(item.get("excerpt"))
                )
            )
        ]
    return payload


def _looks_like_schema_instruction(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return value.startswith(("写出", "结合", "如需", "规则命中或本地知识片段名称", "引用的具体依据"))


def _extract_first_json_object(text: str) -> str | None:
    depth = 0
    start: int | None = None
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                return text[start : index + 1]

    return None


def _prepare_medgemma_prompt(prompt: str, *, has_image: bool, boi_token: str | None) -> str:
    if not has_image:
        return prompt
    if not boi_token:
        return prompt
    if boi_token in prompt:
        return prompt
    return f"{boi_token}\n{prompt}"


def _choose_torch_device(
    requested_device: str,
    *,
    mps_available: bool,
    cuda_available: bool,
) -> str:
    normalized = requested_device.strip().lower()
    if normalized != "auto":
        return normalized
    if mps_available:
        return "mps"
    if cuda_available:
        return "cuda"
    return "cpu"


def _generation_kwargs(*, device: str, max_new_tokens: int, temperature: float) -> dict:
    kwargs = {"max_new_tokens": max_new_tokens}
    if device == "mps":
        kwargs["do_sample"] = False
        return kwargs
    kwargs["do_sample"] = temperature > 0
    if kwargs["do_sample"]:
        kwargs["temperature"] = temperature
    return kwargs


@dataclass
class MedGemmaRuntime:
    """Lazy-loaded runtime for MedGemma.

    Notes:
    - This project targets local deployment first. For MedGemma, you typically need
      to accept model terms and provide a Hugging Face token (gated model).
    - We keep it optional: if not configured, API responds with a clear error and
      guides users to use Ollama backend instead.
    """

    _loaded: bool = False
    _processor: object | None = None
    _model: object | None = None
    _actual_device: str = "not_loaded"

    def is_loaded(self) -> bool:
        return self._loaded

    def actual_device(self) -> str:
        return self._actual_device

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return

        if not settings.medgemma_hf_token:
            raise MedGemmaNotConfiguredError(
                "MedGemma 未配置：请先设置 `MEDGEMMA_HF_TOKEN`（并在 Hugging Face 同意条款后获取访问权限）。"
            )

        try:
            import torch  # type: ignore
            from transformers import AutoProcessor, AutoModelForImageTextToText  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise MedGemmaNotConfiguredError(
                "MedGemma 依赖未安装：请在后端环境安装 `torch` 与 `transformers>=4.50.0`。"
            ) from exc

        # Make token available to HF client without hardcoding in code paths.
        # This avoids writing tokens to disk.
        import os

        os.environ.setdefault("HF_TOKEN", settings.medgemma_hf_token)
        os.environ.setdefault("HUGGINGFACE_HUB_TOKEN", settings.medgemma_hf_token)

        actual_device = _choose_torch_device(
            settings.medgemma_device,
            mps_available=hasattr(torch.backends, "mps") and torch.backends.mps.is_available(),
            cuda_available=torch.cuda.is_available(),
        )
        dtype = (
            getattr(torch, "float16", None)
            if actual_device in {"mps", "cuda"}
            else getattr(torch, "float32", None)
        )

        processor = AutoProcessor.from_pretrained(settings.medgemma_model_id, token=True)
        model = AutoModelForImageTextToText.from_pretrained(
            settings.medgemma_model_id,
            torch_dtype=dtype,
            device_map=None,
            token=True,
        )
        if actual_device != "cpu":
            try:
                model = model.to(actual_device)
            except Exception as exc:
                raise MedGemmaRuntimeError(
                    f"MedGemma 无法移动到 {actual_device}，请将 MEDGEMMA_DEVICE=cpu 后重试：{exc}"
                ) from exc

        self._processor = processor
        self._model = model
        self._actual_device = actual_device
        self._loaded = True

    def analyze(
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
    ) -> AnalysisResponse:
        self._ensure_loaded()
        assert self._processor is not None and self._model is not None

        # Build a single-shot prompt (MedGemma is not optimized for multi-turn).
        prompt = (
            build_system_prompt()
            + "\n\n"
            + build_user_prompt(
                patient_age=patient_age,
                patient_sex=patient_sex,
                symptoms=symptoms,
                clinical_notes=clinical_notes,
                current_medications=current_medications,
                alerts=alerts,
                image_filename=image_filename,
            )
        )

        try:
            from PIL import Image  # type: ignore
            import io
        except Exception as exc:  # pragma: no cover
            raise MedGemmaNotConfiguredError(
                "MedGemma 依赖未安装：请安装 `Pillow`。"
            ) from exc

        image = None
        if image_base64:
            raw = base64.b64decode(image_base64.encode("utf-8"))
            image = Image.open(io.BytesIO(raw)).convert("RGB")

        # Transformers multimodal generation
        try:
            import torch  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise MedGemmaNotConfiguredError(
                "MedGemma 依赖未安装：请安装 `torch`。"
            ) from exc

        processor = self._processor
        model = self._model
        prompt = _prepare_medgemma_prompt(
            prompt,
            has_image=image is not None,
            boi_token=getattr(processor, "boi_token", None),
        )

        try:
            inputs = processor(
                text=prompt,
                images=image,
                return_tensors="pt",
            )
        except ValueError as exc:
            raise MedGemmaRuntimeError(f"MedGemma 输入处理失败：{exc}") from exc

        # Best effort: move tensors to model device if needed
        try:
            device = next(model.parameters()).device
            inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}
        except Exception:
            pass

        try:
            with torch.no_grad():
                output_ids = model.generate(
                    **inputs,
                    **_generation_kwargs(
                        device=self._actual_device,
                        max_new_tokens=settings.medgemma_max_new_tokens,
                        temperature=settings.ollama_temperature,
                    ),
                )
        except RuntimeError as exc:
            raise MedGemmaRuntimeError(f"MedGemma 生成失败：{exc}") from exc

        decoded = processor.batch_decode(output_ids, skip_special_tokens=True)
        if not decoded:
            raise MedGemmaRuntimeError("MedGemma 未返回可解码输出。")

        # We still require JSON output; try to parse the first JSON object found.
        text = decoded[0].strip()
        import json

        json_text = _extract_first_json_object(text)
        if not json_text:
            raise MedGemmaRuntimeError("MedGemma 输出未包含 JSON 对象，请调整提示词或 max_new_tokens。")

        return AnalysisResponse.model_validate(_coerce_medgemma_payload(json.loads(json_text)))


medgemma_runtime = MedGemmaRuntime()
