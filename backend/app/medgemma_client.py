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

        processor = AutoProcessor.from_pretrained(settings.medgemma_model_id, token=True)
        model = AutoModelForImageTextToText.from_pretrained(
            settings.medgemma_model_id,
            torch_dtype=getattr(torch, "bfloat16", None) or getattr(torch, "float16", None),
            device_map=None if settings.medgemma_device == "auto" else settings.medgemma_device,
            token=True,
        )

        self._processor = processor
        self._model = model
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

        inputs = processor(
            text=prompt,
            images=image,
            return_tensors="pt",
        )

        # Best effort: move tensors to model device if needed
        try:
            device = next(model.parameters()).device
            inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}
        except Exception:
            pass

        with torch.no_grad():
            output_ids = model.generate(
                **inputs,
                max_new_tokens=settings.medgemma_max_new_tokens,
                do_sample=settings.ollama_temperature > 0,
                temperature=settings.ollama_temperature,
            )

        decoded = processor.batch_decode(output_ids, skip_special_tokens=True)
        if not decoded:
            raise MedGemmaRuntimeError("MedGemma 未返回可解码输出。")

        # We still require JSON output; try to parse the first JSON object found.
        text = decoded[0].strip()
        import json
        import re

        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise MedGemmaRuntimeError("MedGemma 输出未包含 JSON 对象，请调整提示词或 max_new_tokens。")

        return AnalysisResponse.model_validate(json.loads(match.group(0)))


medgemma_runtime = MedGemmaRuntime()
