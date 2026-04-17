from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import httpx
from starlette.concurrency import run_in_threadpool

from .config import settings
from .models import AnalysisResponse, HealthResponse, InferenceMeta
from .ollama_client import OllamaClient, OllamaClientError
from .medgemma_client import (
    medgemma_runtime,
    MedGemmaNotConfiguredError,
    MedGemmaRuntimeError,
)
from .rules import evaluate_red_flags, highest_risk

app = FastAPI(title="乡镇医疗 AI 助手 API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ollama_client = OllamaClient()

PRIMARY_BACKEND = "medgemma"
FALLBACK_BACKEND = "ollama"

model_runtime_state: dict[str, dict] = {
    "medgemma": {
        "name": "MedGemma",
        "backend": "medgemma",
        "status": "ready" if medgemma_runtime.is_loaded() else "not_loaded",
        "model_id": settings.medgemma_model_id,
        "configured": bool(settings.medgemma_hf_token),
        "device": medgemma_runtime.actual_device(),
        "configured_device": settings.medgemma_device,
        "message": "等待后台加载 MedGemma。" if settings.medgemma_hf_token else "MedGemma 未配置 HF token。",
        "updated_at": None,
    },
    "ollama": {
        "name": "Ollama",
        "backend": "ollama",
        "status": "not_loaded",
        "model_id": settings.ollama_model,
        "base_url": settings.ollama_base_url,
        "message": "等待检查 Ollama 服务。",
        "updated_at": None,
    },
}
last_analysis: dict | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _choose_backend(medgemma_status: str, ollama_ready: bool) -> str | None:
    if medgemma_status == "ready":
        return "medgemma"
    if ollama_ready:
        return "ollama"
    return None


def _fallback_reason(medgemma_status: str) -> str:
    reasons = {
        "not_loaded": "MedGemma 尚未加载，已自动使用备用模型。",
        "loading": "MedGemma 正在加载，已自动使用备用模型。",
        "failed": "MedGemma 加载失败，已自动使用备用模型。",
    }
    return reasons.get(medgemma_status, "MedGemma 当前不可用，已自动使用备用模型。")


async def _warm_medgemma() -> None:
    model_runtime_state["medgemma"].update(
        status="loading",
        message="MedGemma 正在后台加载。",
        updated_at=_now_iso(),
    )
    try:
        await run_in_threadpool(medgemma_runtime._ensure_loaded)
    except (MedGemmaNotConfiguredError, MedGemmaRuntimeError) as exc:
        model_runtime_state["medgemma"].update(
            status="failed",
            message=str(exc),
            updated_at=_now_iso(),
        )
    except Exception as exc:  # pragma: no cover - depends on local model/runtime stack.
        model_runtime_state["medgemma"].update(
            status="failed",
            message=f"MedGemma 加载失败：{exc}",
            updated_at=_now_iso(),
        )
    else:
        model_runtime_state["medgemma"].update(
            status="ready",
            message="MedGemma 已加载，默认用于医生工作台分析。",
            device=medgemma_runtime.actual_device(),
            updated_at=_now_iso(),
        )


async def _refresh_ollama_runtime_state() -> dict:
    status = await ollama_status()
    ready = bool(status.get("reachable") and status.get("has_model"))
    model_runtime_state["ollama"].update(
        status="ready" if ready else "failed",
        message=status["message"],
        base_url=status["base_url"],
        model_id=status["model"],
        available_models=status.get("available_models", []),
        updated_at=_now_iso(),
    )
    return status


@app.on_event("startup")
async def startup_models() -> None:
    if settings.medgemma_hf_token and not medgemma_runtime.is_loaded():
        asyncio.create_task(_warm_medgemma())
    else:
        model_runtime_state["medgemma"].update(
            status="ready" if medgemma_runtime.is_loaded() else "failed",
            message="MedGemma 已加载。" if medgemma_runtime.is_loaded() else "MedGemma 未配置 HF token。",
            device=medgemma_runtime.actual_device(),
            updated_at=_now_iso(),
        )
    asyncio.create_task(_refresh_ollama_runtime_state())


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        inference_backend=settings.inference_backend,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
    )


@app.get("/api/ollama/status")
async def ollama_status() -> dict:
    """Lightweight health check for Ollama connectivity and model availability."""
    base = settings.ollama_base_url.rstrip("/")
    tags_url = f"{base}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(tags_url)
            resp.raise_for_status()
            payload = resp.json()
    except Exception:
        return {
            "reachable": False,
            "base_url": settings.ollama_base_url,
            "model": settings.ollama_model,
            "message": "Ollama 未连接：请确认已安装并运行 `ollama serve`。",
        }

    models = [m.get("name") for m in payload.get("models", []) if isinstance(m, dict)]
    has_model = settings.ollama_model in models
    return {
        "reachable": True,
        "base_url": settings.ollama_base_url,
        "model": settings.ollama_model,
        "has_model": has_model,
        "available_models": models,
        "message": "Ollama 可用" if has_model else "Ollama 可用，但未找到配置的模型，请执行 `ollama pull <model>`。",
    }


@app.get("/api/inference/status")
async def inference_status() -> dict:
    await _refresh_ollama_runtime_state()
    if medgemma_runtime.is_loaded():
        model_runtime_state["medgemma"].update(
            status="ready",
            message="MedGemma 已加载，默认用于医生工作台分析。",
            device=medgemma_runtime.actual_device(),
            updated_at=_now_iso(),
        )

    return {
        "strategy": {
            "primary": PRIMARY_BACKEND,
            "fallback": FALLBACK_BACKEND,
            "auto_fallback": True,
        },
        "models": [model_runtime_state["medgemma"], model_runtime_state["ollama"]],
        "last_analysis": last_analysis,
    }


@app.post("/api/report/analyze", response_model=AnalysisResponse)
async def analyze_report(
    report_image: Optional[UploadFile] = File(default=None),
    patient_age: Optional[int] = Form(default=None),
    patient_sex: Optional[str] = Form(default=None),
    symptoms: Optional[str] = Form(default=None),
    clinical_notes: Optional[str] = Form(default=None),
    current_medications: Optional[str] = Form(default=None),
    backend: Optional[str] = Form(default=None),
) -> AnalysisResponse:
    global last_analysis

    if not report_image and not symptoms and not clinical_notes:
        raise HTTPException(
            status_code=400,
            detail="请至少上传检查单图片，或填写症状/补充病情。",
        )

    image_base64: Optional[str] = None
    image_filename: Optional[str] = None

    if report_image:
        raw = await report_image.read()
        image_base64 = base64.b64encode(raw).decode("utf-8")
        image_filename = report_image.filename

    alerts = evaluate_red_flags(symptoms, clinical_notes)

    try:
        ollama_runtime = await _refresh_ollama_runtime_state()
        if medgemma_runtime.is_loaded():
            model_runtime_state["medgemma"].update(
                status="ready",
                message="MedGemma 已加载，默认用于医生工作台分析。",
                device=medgemma_runtime.actual_device(),
                updated_at=_now_iso(),
            )

        medgemma_status = model_runtime_state["medgemma"]["status"]
        selected = _choose_backend(
            medgemma_status,
            bool(ollama_runtime.get("reachable") and ollama_runtime.get("has_model")),
        )
        if selected is None:
            raise HTTPException(status_code=502, detail="本地分析服务当前不可用，请联系管理员检查模型服务。")

        if selected == "medgemma":
            response = await run_in_threadpool(
                medgemma_runtime.analyze,
                image_base64=image_base64,
                image_filename=image_filename,
                patient_age=patient_age,
                patient_sex=patient_sex,
                symptoms=symptoms,
                clinical_notes=clinical_notes,
                current_medications=current_medications,
                alerts=alerts,
            )
        else:
            response = await ollama_client.analyze(
                image_base64=image_base64,
                image_filename=image_filename,
                patient_age=patient_age,
                patient_sex=patient_sex,
                symptoms=symptoms,
                clinical_notes=clinical_notes,
                current_medications=current_medications,
                alerts=alerts,
            )
    except (OllamaClientError, MedGemmaNotConfiguredError, MedGemmaRuntimeError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    used_fallback = selected == FALLBACK_BACKEND and medgemma_status != "ready"
    response.inference = InferenceMeta(
        backend=selected,
        used_fallback=used_fallback,
        primary_backend=PRIMARY_BACKEND,
        fallback_reason=_fallback_reason(medgemma_status) if used_fallback else None,
    )

    if alerts and highest_risk(alerts) == "高风险" and response.risk_level != "高风险":
        response.risk_level = "高风险"
        if not response.urgent_transfer_reasons:
            response.urgent_transfer_reasons = [
                alert.rationale for alert in alerts if alert.risk_level == "高风险"
            ]
        if not response.next_steps:
            response.next_steps = [
                alert.recommended_action
                for alert in alerts
                if alert.risk_level == "高风险"
            ]

    response.applied_rules = alerts
    last_analysis = {
        "backend": response.inference.backend,
        "used_fallback": response.inference.used_fallback,
        "risk_level": response.risk_level,
        "created_at": _now_iso(),
    }
    return response
