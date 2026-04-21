from __future__ import annotations

import asyncio
import base64
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import httpx
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from .cbc_ocr import CBCOCRExtractionError, extract_cbc_from_image
from .config import settings
from .models import (
    AnalysisResponse,
    HealthResponse,
    InferenceMeta,
    LabAnalysisInput,
    LabExtractionResponse,
    LabReportItem,
    LabReportType,
    MultiReportAnalysisInput,
    ReferralCard,
    RuleAlert,
    StructuredLabReport,
)
from .ollama_client import OllamaClient, OllamaClientError
from .medgemma_client import (
    medgemma_runtime,
    MedGemmaNotConfiguredError,
    MedGemmaRuntimeError,
)
from .rules import evaluate_cross_report_alerts, evaluate_red_flags, evaluate_structured_lab_alerts

app = FastAPI(title="乡镇医疗 AI 助手 API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "null"],
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
        "active": True,
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
        "active": True,
        "model_id": settings.ollama_model,
        "base_url": settings.ollama_base_url,
        "message": "等待检查 Ollama 服务。",
        "updated_at": None,
    },
}
last_analysis: dict | None = None
REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CBC_PATH = REPO_ROOT / "docs" / "sample-cbc-report.png"
SAMPLE_CHEM_PATH = REPO_ROOT / "docs" / "sample-chemistry-report.png"
WEB_DIST_DIR = Path(os.getenv("DOCUFEET_WEB_DIST", REPO_ROOT / "frontend" / "dist"))


def _safe_frontend_path(asset_path: str) -> Path | None:
    candidate = (WEB_DIST_DIR / asset_path).resolve()
    try:
        candidate.relative_to(WEB_DIST_DIR.resolve())
    except ValueError:
        return None
    return candidate


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
        "disabled": "MedGemma 已停用，已自动使用备用模型。",
    }
    return reasons.get(medgemma_status, "MedGemma 当前不可用，已自动使用备用模型。")


def _is_active(backend: str) -> bool:
    return bool(model_runtime_state[backend].get("active", True))


def _contains_negated_concept(text: str, concept: str) -> bool:
    negation_markers = ("无", "没有", "未见", "否认", "不伴", "未")
    return any(f"{marker}{concept}" in text for marker in negation_markers)


def _is_non_actionable_transfer_reason(reason: str) -> bool:
    text = reason.strip()
    if not text:
        return True
    non_reason_markers = ("无明确转诊理由", "无需转诊", "无转诊", "无急诊", "无明确急转")
    return any(marker in text for marker in non_reason_markers)


def _contradicts_negated_symptoms(reason: str, source_text: str) -> bool:
    guarded_concepts = ("意识改变", "气促", "胸痛", "呼吸困难")
    return any(
        concept in reason and _contains_negated_concept(source_text, concept)
        for concept in guarded_concepts
    )


def _postprocess_analysis_response(
    response: AnalysisResponse,
    *,
    alerts: list[RuleAlert],
    symptoms: Optional[str],
    clinical_notes: Optional[str],
) -> None:
    source_text = " ".join(part for part in (symptoms, clinical_notes) if part)
    response.urgent_transfer_reasons = [
        reason
        for reason in response.urgent_transfer_reasons
        if not _is_non_actionable_transfer_reason(reason)
        and not _contradicts_negated_symptoms(reason, source_text)
    ]

    high_risk_alerts = [alert for alert in alerts if alert.risk_level == "高风险"]
    if high_risk_alerts:
        response.risk_level = "高风险"
        response.urgent_transfer_reasons = [alert.rationale for alert in high_risk_alerts]
        if not response.next_steps:
            response.next_steps = [alert.recommended_action for alert in high_risk_alerts]
        return

    if response.risk_level == "高风险" and not response.urgent_transfer_reasons:
        response.risk_level = "中风险"


def _merge_alerts(*alert_groups: list[RuleAlert]) -> list[RuleAlert]:
    merged: list[RuleAlert] = []
    seen: set[tuple[str, str]] = set()
    for group in alert_groups:
        for alert in group:
            key = (alert.title, alert.rationale)
            if key in seen:
                continue
            seen.add(key)
            merged.append(alert)
    merged.sort(key=lambda item: {"低风险": 0, "中风险": 1, "高风险": 2}[item.risk_level], reverse=True)
    return merged


_REQUIRED_REPORT_ITEMS: dict[LabReportType, set[str]] = {
    "cbc": {"WBC", "RBC", "HGB", "PLT"},
    "chemistry_basic": {"Cr", "K", "Na", "GLU"},
}


def _build_structured_report(
    *,
    items: list[LabReportItem],
    source_image_name: Optional[str],
    report_type: LabReportType,
) -> StructuredLabReport | None:
    if not items:
        return None
    return StructuredLabReport(
        report_type=report_type,
        source_image_name=source_image_name,
        items=items,
    )


def _validate_confirmed_lab_items(report_type: LabReportType, items: list[LabReportItem]) -> None:
    required = _REQUIRED_REPORT_ITEMS[report_type]
    confirmed_names = {item.name for item in items if item.confirmed and item.value.strip()}
    missing = sorted(required - confirmed_names)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"关键检验字段缺失：{', '.join(missing)}。请确认识别结果后再分析。",
        )


def _validate_confirmed_reports(reports: list[StructuredLabReport]) -> None:
    if not reports:
        raise HTTPException(status_code=400, detail="请至少确认一份检验报告后再分析。")
    for report in reports:
        _validate_confirmed_lab_items(report.report_type, report.items)


def _combine_reports_for_prompt(reports: list[StructuredLabReport]) -> StructuredLabReport | None:
    if not reports:
        return None
    combined_items: list[LabReportItem] = []
    source_names = []
    for report in reports:
        combined_items.extend(report.items)
        if report.source_image_name:
            source_names.append(report.source_image_name)
    return StructuredLabReport(
        report_type=reports[0].report_type,
        source_image_name=" + ".join(source_names) if source_names else None,
        items=combined_items,
    )


def _build_referral_card(
    *,
    response: AnalysisResponse,
    structured_report: StructuredLabReport | None,
    alerts: list[RuleAlert],
) -> ReferralCard:
    if response.risk_level == "高风险" or response.urgent_transfer_reasons:
        decision = "立即转诊"
    elif response.risk_level == "中风险":
        decision = "尽快复诊"
    else:
        decision = "观察"

    reasons = list(response.urgent_transfer_reasons)
    if not reasons:
        reasons.extend(alert.rationale for alert in alerts[:2])
    if not reasons and structured_report:
        for item in structured_report.items:
            if item.flag in {"high", "low"}:
                reasons.append(
                    f"{item.name}={item.value or '未提供'} {item.unit or ''}".strip()
                    + f"，参考范围 {item.reference_range or '未提供'}。"
                )
    if not reasons:
        reasons.append("当前未见明确转诊红旗，建议结合病情动态观察。")

    suggested_checks = response.next_steps[:3]
    handoff_notes = []
    if response.doctor_summary:
        handoff_notes.append(response.doctor_summary)
    if structured_report:
        abnormal_items = [
            item for item in structured_report.items if item.flag in {"high", "low"}
        ]
        if abnormal_items:
            item_text = "；".join(
                f"{item.name} {item.value or '未提供'} {item.unit or ''}".strip()
                for item in abnormal_items[:3]
            )
            handoff_notes.append(f"已确认的异常检验字段：{item_text}")

    if decision == "观察" and suggested_checks:
        decision = "尽快复诊"

    return ReferralCard(
        decision=decision,
        reasons=reasons[:3],
        suggested_checks=suggested_checks,
        handoff_notes=handoff_notes[:3],
    )


async def _call_backend(
    *,
    backend: str,
    image_base64: Optional[str],
    image_filename: Optional[str],
    patient_age: Optional[int],
    patient_sex: Optional[str],
    symptoms: Optional[str],
    clinical_notes: Optional[str],
    current_medications: Optional[str],
    alerts: list[RuleAlert],
    structured_report: StructuredLabReport | None,
) -> AnalysisResponse:
    if backend == "medgemma":
        return await run_in_threadpool(
            medgemma_runtime.analyze,
            image_base64=image_base64,
            image_filename=image_filename,
            patient_age=patient_age,
            patient_sex=patient_sex,
            symptoms=symptoms,
            clinical_notes=clinical_notes,
            current_medications=current_medications,
            alerts=alerts,
            structured_report=structured_report,
        )

    return await ollama_client.analyze(
        image_base64=image_base64,
        image_filename=image_filename,
        patient_age=patient_age,
        patient_sex=patient_sex,
        symptoms=symptoms,
        clinical_notes=clinical_notes,
        current_medications=current_medications,
        alerts=alerts,
        structured_report=structured_report,
    )


async def _analyze_with_selected_backend(
    *,
    image_base64: Optional[str],
    image_filename: Optional[str],
    patient_age: Optional[int],
    patient_sex: Optional[str],
    symptoms: Optional[str],
    clinical_notes: Optional[str],
    current_medications: Optional[str],
    alerts: list[RuleAlert],
    structured_report: StructuredLabReport | None = None,
    structured_reports: list[StructuredLabReport] | None = None,
) -> AnalysisResponse:
    global last_analysis

    ollama_runtime = await _refresh_ollama_runtime_state()
    if not _is_active("medgemma"):
        model_runtime_state["medgemma"].update(
            status="disabled",
            message="MedGemma 已停用，不参与医生工作台分析。",
            device=medgemma_runtime.actual_device(),
            updated_at=_now_iso(),
        )
    elif medgemma_runtime.is_loaded():
        model_runtime_state["medgemma"].update(
            status="ready",
            message="MedGemma 已加载，默认用于医生工作台分析。",
            device=medgemma_runtime.actual_device(),
            updated_at=_now_iso(),
        )

    medgemma_status = (
        model_runtime_state["medgemma"]["status"]
        if _is_active("medgemma")
        else "disabled"
    )
    selected = _choose_backend(
        medgemma_status,
        bool(
            _is_active("ollama")
            and ollama_runtime.get("reachable")
            and ollama_runtime.get("has_model")
        ),
    )
    if selected is None:
        raise HTTPException(status_code=502, detail="本地分析服务当前不可用，请联系管理员检查模型服务。")

    used_fallback = selected == FALLBACK_BACKEND and medgemma_status != "ready"
    fallback_reason = _fallback_reason(medgemma_status) if used_fallback else None

    try:
        response = await _call_backend(
            backend=selected,
            image_base64=image_base64,
            image_filename=image_filename,
            patient_age=patient_age,
            patient_sex=patient_sex,
            symptoms=symptoms,
            clinical_notes=clinical_notes,
            current_medications=current_medications,
            alerts=alerts,
            structured_report=structured_report,
        )
    except (MedGemmaNotConfiguredError, MedGemmaRuntimeError) as exc:
        can_fallback_now = (
            selected == PRIMARY_BACKEND
            and _is_active("ollama")
            and ollama_runtime.get("reachable")
            and ollama_runtime.get("has_model")
        )
        if not can_fallback_now:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        selected = FALLBACK_BACKEND
        used_fallback = True
        fallback_reason = f"{_fallback_reason(medgemma_status)} 主模型运行失败：{exc}"
        try:
            response = await _call_backend(
                backend=selected,
                image_base64=image_base64,
                image_filename=image_filename,
                patient_age=patient_age,
                patient_sex=patient_sex,
                symptoms=symptoms,
                clinical_notes=clinical_notes,
                current_medications=current_medications,
                alerts=alerts,
                structured_report=structured_report,
            )
        except OllamaClientError as fallback_exc:
            raise HTTPException(status_code=502, detail=str(fallback_exc)) from fallback_exc
    except OllamaClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    response.inference = InferenceMeta(
        backend=selected,
        used_fallback=used_fallback,
        primary_backend=PRIMARY_BACKEND,
        fallback_reason=fallback_reason,
    )

    _postprocess_analysis_response(
        response,
        alerts=alerts,
        symptoms=symptoms,
        clinical_notes=clinical_notes,
    )
    response.applied_rules = alerts
    response.structured_report = structured_report
    response.structured_reports = structured_reports or ([structured_report] if structured_report else [])
    response.referral_card = _build_referral_card(
        response=response,
        structured_report=structured_report,
        alerts=alerts,
    )
    last_analysis = {
        "backend": response.inference.backend,
        "used_fallback": response.inference.used_fallback,
        "risk_level": response.risk_level,
        "created_at": _now_iso(),
    }
    return response


async def _warm_medgemma() -> None:
    model_runtime_state["medgemma"].update(
        active=True,
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
        if _is_active("medgemma"):
            model_runtime_state["medgemma"].update(
                status="ready",
                message="MedGemma 已加载，默认用于医生工作台分析。",
                device=medgemma_runtime.actual_device(),
                updated_at=_now_iso(),
            )
        else:
            medgemma_runtime.unload()
            model_runtime_state["medgemma"].update(
                status="disabled",
                message="MedGemma 已停用，不参与医生工作台分析。",
                device=medgemma_runtime.actual_device(),
                updated_at=_now_iso(),
            )


async def _refresh_ollama_runtime_state() -> dict:
    status = await ollama_status()
    ready = bool(status.get("reachable") and status.get("has_model"))
    active = _is_active("ollama")
    model_runtime_state["ollama"].update(
        status="ready" if ready and active else "disabled" if not active else "failed",
        message=status["message"] if active else "Ollama 已停用，不参与备用兜底。",
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


@app.get("/app")
@app.get("/app/")
@app.get("/app/{asset_path:path}")
def serve_frontend_app(asset_path: str = "") -> FileResponse:
    requested = _safe_frontend_path(asset_path) if asset_path else None
    if requested and requested.is_file():
        return FileResponse(requested)

    index_path = WEB_DIST_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="前端静态资源尚未构建，请先运行 Mac app 打包脚本。")
    return FileResponse(index_path)


@app.get("/api/demo/cbc-sample")
def demo_cbc_sample() -> dict:
    if not SAMPLE_CBC_PATH.exists():
        raise HTTPException(status_code=404, detail="未找到血常规演示样例，请先生成 sample-cbc-report.png。")
    return {
        "report_type": "cbc",
        "patient_age": 63,
        "patient_sex": "女",
        "symptoms": "乏力、头晕 3 天。",
        "clinical_notes": "血常规样例提示血红蛋白偏低，需结合症状进一步评估是否存在贫血相关风险。",
        "current_medications": "未提供",
        "image_url": "/api/demo/cbc-sample-image",
        "image_name": SAMPLE_CBC_PATH.name,
    }


@app.get("/api/demo/chemistry-sample")
def demo_chemistry_sample() -> dict:
    if not SAMPLE_CHEM_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="未找到生化演示样例，请先生成 sample-chemistry-report.png。",
        )
    return {
        "report_type": "chemistry_basic",
        "patient_age": 58,
        "patient_sex": "男",
        "symptoms": "乏力、口渴 2 天。",
        "clinical_notes": "生化样例提示血糖升高、肌酐轻度异常，需结合脱水与肾功能风险判断。",
        "current_medications": "二甲双胍",
        "image_url": "/api/demo/chemistry-sample-image",
        "image_name": SAMPLE_CHEM_PATH.name,
    }


@app.get("/api/demo/cbc-sample-image")
def demo_cbc_sample_image() -> FileResponse:
    if not SAMPLE_CBC_PATH.exists():
        raise HTTPException(status_code=404, detail="未找到血常规演示样例，请先生成 sample-cbc-report.png。")
    return FileResponse(SAMPLE_CBC_PATH, media_type="image/png", filename=SAMPLE_CBC_PATH.name)


@app.get("/api/demo/chemistry-sample-image")
def demo_chemistry_sample_image() -> FileResponse:
    if not SAMPLE_CHEM_PATH.exists():
        raise HTTPException(status_code=404, detail="未找到生化演示样例，请先生成 sample-chemistry-report.png。")
    return FileResponse(SAMPLE_CHEM_PATH, media_type="image/png", filename=SAMPLE_CHEM_PATH.name)


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
    if not _is_active("medgemma"):
        model_runtime_state["medgemma"].update(
            status="disabled",
            message="MedGemma 已停用，不参与医生工作台分析。",
            device=medgemma_runtime.actual_device(),
            updated_at=_now_iso(),
        )
    elif medgemma_runtime.is_loaded():
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


@app.post("/api/inference/models/{backend}/load")
async def load_inference_model(backend: str) -> dict:
    if backend == "medgemma":
        if medgemma_runtime.is_loaded():
            model_runtime_state["medgemma"].update(
                active=True,
                status="ready",
                message="MedGemma 已加载，默认用于医生工作台分析。",
                device=medgemma_runtime.actual_device(),
                updated_at=_now_iso(),
            )
        else:
            model_runtime_state["medgemma"].update(
                active=True,
                status="loading",
                message="MedGemma 正在后台加载。",
                updated_at=_now_iso(),
            )
            asyncio.create_task(_warm_medgemma())
        return await inference_status()

    if backend == "ollama":
        model_runtime_state["ollama"].update(active=True, updated_at=_now_iso())
        await _refresh_ollama_runtime_state()
        return await inference_status()

    raise HTTPException(status_code=404, detail="未找到该模型后端。")


@app.post("/api/inference/models/{backend}/stop")
async def stop_inference_model(backend: str) -> dict:
    if backend == "medgemma":
        model_runtime_state["medgemma"].update(active=False, updated_at=_now_iso())
        await run_in_threadpool(medgemma_runtime.unload)
        model_runtime_state["medgemma"].update(
            status="disabled",
            message="MedGemma 已停用，不参与医生工作台分析。",
            device=medgemma_runtime.actual_device(),
            updated_at=_now_iso(),
        )
        return await inference_status()

    if backend == "ollama":
        model_runtime_state["ollama"].update(
            active=False,
            status="disabled",
            message="Ollama 已停用，不参与备用兜底。",
            updated_at=_now_iso(),
        )
        return await inference_status()

    raise HTTPException(status_code=404, detail="未找到该模型后端。")


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

    return await _analyze_with_selected_backend(
        image_base64=image_base64,
        image_filename=image_filename,
        patient_age=patient_age,
        patient_sex=patient_sex,
        alerts=alerts,
        symptoms=symptoms,
        clinical_notes=clinical_notes,
        current_medications=current_medications,
    )


@app.post("/api/report/extract-cbc", response_model=LabExtractionResponse)
async def extract_cbc(
    report_image: UploadFile = File(...),
) -> LabExtractionResponse:
    raw = await report_image.read()
    try:
        return await run_in_threadpool(
            extract_cbc_from_image,
            filename=report_image.filename,
            raw_bytes=raw,
        )
    except CBCOCRExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/report/analyze-cbc", response_model=AnalysisResponse)
async def analyze_cbc(
    payload: LabAnalysisInput = Body(...),
) -> AnalysisResponse:
    _validate_confirmed_lab_items(payload.report_type, payload.items)
    structured_report = _build_structured_report(
        items=payload.items,
        source_image_name=payload.source_image_name,
        report_type=payload.report_type,
    )
    text_alerts = evaluate_red_flags(payload.symptoms, payload.clinical_notes)
    structured_alerts = evaluate_structured_lab_alerts(
        payload.items,
        symptoms=payload.symptoms,
        clinical_notes=payload.clinical_notes,
    )
    alerts = _merge_alerts(text_alerts, structured_alerts)

    return await _analyze_with_selected_backend(
        image_base64=None,
        image_filename=payload.source_image_name,
        patient_age=payload.patient_age,
        patient_sex=payload.patient_sex,
        symptoms=payload.symptoms,
        clinical_notes=payload.clinical_notes,
        current_medications=payload.current_medications,
        alerts=alerts,
        structured_report=structured_report,
        structured_reports=[structured_report] if structured_report else [],
    )


@app.post("/api/report/analyze-labs", response_model=AnalysisResponse)
async def analyze_labs(
    payload: MultiReportAnalysisInput = Body(...),
) -> AnalysisResponse:
    _validate_confirmed_reports(payload.reports)
    text_alerts = evaluate_red_flags(payload.symptoms, payload.clinical_notes)
    structured_alert_groups = [
        evaluate_structured_lab_alerts(
            report.items,
            symptoms=payload.symptoms,
            clinical_notes=payload.clinical_notes,
        )
        for report in payload.reports
    ]
    cross_report_alerts = evaluate_cross_report_alerts(
        payload.reports,
        symptoms=payload.symptoms,
        clinical_notes=payload.clinical_notes,
    )
    alerts = _merge_alerts(text_alerts, *structured_alert_groups, cross_report_alerts)
    structured_report = _combine_reports_for_prompt(payload.reports)

    return await _analyze_with_selected_backend(
        image_base64=None,
        image_filename=structured_report.source_image_name if structured_report else None,
        patient_age=payload.patient_age,
        patient_sex=payload.patient_sex,
        symptoms=payload.symptoms,
        clinical_notes=payload.clinical_notes,
        current_medications=payload.current_medications,
        alerts=alerts,
        structured_report=structured_report,
        structured_reports=payload.reports,
    )
