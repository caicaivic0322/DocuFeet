from __future__ import annotations

import base64
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import httpx

from .config import settings
from .models import AnalysisResponse, HealthResponse
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
    return {
        "default_backend": settings.inference_backend,
        "ollama": await ollama_status(),
        "medgemma": {
            "model_id": settings.medgemma_model_id,
            "configured": bool(settings.medgemma_hf_token),
            "device": settings.medgemma_device,
            "message": (
                "MedGemma 已配置，可尝试请求。"
                if settings.medgemma_hf_token
                else "MedGemma 未配置 HF token，当前只完成后端接线。"
            ),
        },
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
        selected = (backend or settings.inference_backend or "ollama").strip().lower()
        if selected == "medgemma":
            response = medgemma_runtime.analyze(
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
    return response
