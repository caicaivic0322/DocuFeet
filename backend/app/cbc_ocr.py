from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from .models import ItemFlag, LabExtractionResponse, LabReportItem, LabReportType


class CBCOCRExtractionError(RuntimeError):
    pass


_ROW_CLUSTER_TOLERANCE = 0.028
_TEXT_NORMALIZATIONS = {
    "W8C": "WBC",
    "R8C": "RBC",
    "H6B": "HGB",
    "PIT": "PLT",
    "PL1": "PLT",
    "TB1L": "TBIL",
    "A1T": "ALT",
    "A5T": "AST",
    "C1": "Cl",
}

_REPORT_DEFS: dict[LabReportType, dict[str, object]] = {
    "cbc": {
        "title": "血常规",
        "required_items": ("WBC", "RBC", "HGB", "PLT"),
        "patterns": {
            "WBC": ("WBC", "白细胞"),
            "RBC": ("RBC", "红细胞"),
            "HGB": ("HGB", "HB", "Hb", "血红蛋白", "血色素"),
            "PLT": ("PLT", "PIT", "PL1", "血小板"),
        },
        "name_cleanup": r"^(白细胞|红细胞|血红蛋白|血色素|血小板)\s*",
        "supported_units": (
            r"10\^\d+/L",
            r"10\^\d+/UL",
            r"10\^\d+/uL",
            r"G/L",
            r"g/L",
            r"PG",
            r"pg",
            r"fL",
            r"FL",
            r"%",
            r"/L",
        ),
    },
    "chemistry_basic": {
        "title": "生化基础项",
        "required_items": ("Cr", "K", "Na", "GLU"),
        "patterns": {
            "Cr": ("CR", "CREA", "CREATININE", "肌酐", "Cr"),
            "BUN": ("BUN", "UREA", "尿素氮"),
            "eGFR": ("EGFR", "E-GFR", "估算肾小球滤过率", "eGFR"),
            "K": ("K", "钾"),
            "Na": ("NA", "钠", "Na"),
            "Cl": ("CL", "氯", "Cl"),
            "GLU": ("GLU", "葡萄糖", "血糖"),
            "ALT": ("ALT", "谷丙转氨酶"),
            "AST": ("AST", "谷草转氨酶"),
            "TBIL": ("TBIL", "总胆红素"),
            "ALB": ("ALB", "白蛋白"),
        },
        "name_cleanup": r"^(肌酐|尿素氮|估算肾小球滤过率|钾|钠|氯|葡萄糖|血糖|谷丙转氨酶|谷草转氨酶|总胆红素|白蛋白)\s*",
        "supported_units": (
            r"UMOL/L",
            r"MMOL/L",
            r"MG/DL",
            r"U/L",
            r"G/L",
            r"ML/MIN/1\.73M2",
            r"MG/L",
            r"%",
        ),
    },
}

_VISION_SWIFT = r"""
import Foundation
import Vision
import ImageIO
import CoreGraphics

struct OCRLine: Codable {
    let text: String
    let confidence: Double
    let x: Double
    let y: Double
    let width: Double
    let height: Double
}

enum OCRFailure: Error {
    case invalidArguments
    case imageLoadFailed
}

func loadImage(_ path: String) throws -> CGImage {
    let url = URL(fileURLWithPath: path)
    guard
        let source = CGImageSourceCreateWithURL(url as CFURL, nil),
        let image = CGImageSourceCreateImageAtIndex(source, 0, nil)
    else {
        throw OCRFailure.imageLoadFailed
    }
    return image
}

func runOCR(path: String) throws -> [OCRLine] {
    let image = try loadImage(path)
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = false
    request.recognitionLanguages = ["zh-Hans", "en-US"]

    let handler = VNImageRequestHandler(cgImage: image, options: [:])
    try handler.perform([request])

    let observations = request.results ?? []
    return observations.compactMap { observation in
        guard let candidate = observation.topCandidates(1).first else { return nil }
        let box = observation.boundingBox
        return OCRLine(
            text: candidate.string,
            confidence: Double(candidate.confidence),
            x: Double(box.minX),
            y: Double(box.minY),
            width: Double(box.width),
            height: Double(box.height)
        )
    }
}

do {
    guard CommandLine.arguments.count >= 2 else {
        throw OCRFailure.invalidArguments
    }
    let lines = try runOCR(path: CommandLine.arguments[1])
    let encoder = JSONEncoder()
    let data = try encoder.encode(lines)
    FileHandle.standardOutput.write(data)
} catch {
    fputs(String(describing: error), stderr)
    exit(1)
}
"""


def extract_cbc_from_image(*, filename: str | None, raw_bytes: bytes) -> LabExtractionResponse:
    observations = _run_macos_vision_ocr(raw_bytes)
    rows = _group_rows(observations)
    report_type = _detect_report_type(rows)
    items = _extract_items(rows, report_type)
    required_items = _required_items(report_type)
    missing = [item for item in required_items if item not in {entry.name for entry in items}]
    can_analyze = not missing
    notice = (
        f"已按固定版式提取{_report_title(report_type)}候选字段，请逐项确认后再分析。"
        if can_analyze
        else f"缺少关键字段：{', '.join(missing)}，请重新拍照或手动补全后再分析。"
    )

    return LabExtractionResponse(
        report_type=report_type,
        source_image_name=filename,
        raw_text="\n".join(row["text"] for row in rows),
        items=items,
        missing_required_items=missing,
        can_analyze=can_analyze,
        notice=notice,
    )


def _required_items(report_type: LabReportType) -> tuple[str, ...]:
    return _REPORT_DEFS[report_type]["required_items"]  # type: ignore[return-value]


def _report_title(report_type: LabReportType) -> str:
    return _REPORT_DEFS[report_type]["title"]  # type: ignore[return-value]


def _patterns(report_type: LabReportType) -> dict[str, tuple[str, ...]]:
    return _REPORT_DEFS[report_type]["patterns"]  # type: ignore[return-value]


def _run_macos_vision_ocr(raw_bytes: bytes) -> list[dict[str, str | float]]:
    if not raw_bytes:
        raise CBCOCRExtractionError("未读取到图片内容，请重新上传检验单。")

    if not Path("/usr/bin/xcrun").exists():
        raise CBCOCRExtractionError("当前系统缺少 macOS OCR 运行环境，无法识别检验单。")

    with tempfile.TemporaryDirectory(prefix="cbc-ocr-") as temp_dir:
        temp_path = Path(temp_dir)
        image_path = temp_path / "report-image.png"
        image_path.write_bytes(raw_bytes)
        script_path = temp_path / "vision_ocr.swift"
        script_path.write_text(_VISION_SWIFT, encoding="utf-8")

        try:
            result = subprocess.run(
                ["/usr/bin/xcrun", "swift", str(script_path), str(image_path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=20,
            )
        except subprocess.TimeoutExpired as exc:
            raise CBCOCRExtractionError("检验单识别超时，请更换更清晰的图片后重试。") from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.strip() or "未知错误"
            raise CBCOCRExtractionError(f"检验单识别失败：{stderr}") from exc

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise CBCOCRExtractionError("OCR 服务返回内容异常，请稍后重试。") from exc

    normalized: list[dict[str, str | float]] = []
    for line in payload if isinstance(payload, list) else []:
        if not isinstance(line, dict):
            continue
        text = str(line.get("text", "")).strip()
        confidence = float(line.get("confidence", 0.0) or 0.0)
        if text:
            normalized.append(
                {
                    "text": _normalize_text(text),
                    "confidence": confidence,
                    "x": float(line.get("x", 0.0) or 0.0),
                    "y": float(line.get("y", 0.0) or 0.0),
                    "width": float(line.get("width", 0.0) or 0.0),
                    "height": float(line.get("height", 0.0) or 0.0),
                }
            )
    if not normalized:
        raise CBCOCRExtractionError("未识别到有效文字，请重新拍照并确保检验单清晰完整。")
    return normalized


def _normalize_text(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.replace("：", ":")).strip()
    for source, target in _TEXT_NORMALIZATIONS.items():
        normalized = normalized.replace(source, target)
    return normalized


def _group_rows(observations: list[dict[str, str | float]]) -> list[dict[str, str | float]]:
    if not observations:
        return []

    ordered = sorted(
        observations,
        key=lambda line: (-_row_center_y(line), float(line.get("x", 0.0) or 0.0)),
    )
    groups: list[list[dict[str, str | float]]] = []
    for line in ordered:
        if not groups:
            groups.append([line])
            continue
        if abs(_row_center_y(line) - _average_center_y(groups[-1])) <= _ROW_CLUSTER_TOLERANCE:
            groups[-1].append(line)
        else:
            groups.append([line])

    rows: list[dict[str, str | float]] = []
    for group in groups:
        by_x = sorted(group, key=lambda line: float(line.get("x", 0.0) or 0.0))
        rows.append(
            {
                "text": " ".join(str(line["text"]).strip() for line in by_x if str(line["text"]).strip()),
                "confidence": sum(float(line.get("confidence", 0.0) or 0.0) for line in by_x) / len(by_x),
            }
        )
    return rows


def _row_center_y(line: dict[str, str | float]) -> float:
    return float(line.get("y", 0.0) or 0.0) + float(line.get("height", 0.0) or 0.0) / 2


def _average_center_y(group: list[dict[str, str | float]]) -> float:
    return sum(_row_center_y(line) for line in group) / len(group)


def _detect_report_type(rows: list[dict[str, str | float]]) -> LabReportType:
    joined = "\n".join(str(row["text"]) for row in rows).upper()
    chemistry_markers = ("肌酐", "CREA", "EGFR", "GLU", "ALT", "AST", "TBIL", "ALB", "生化")
    cbc_markers = ("WBC", "RBC", "HGB", "PLT", "白细胞", "血红蛋白", "血常规")
    chemistry_score = sum(1 for marker in chemistry_markers if marker.upper() in joined)
    cbc_score = sum(1 for marker in cbc_markers if marker.upper() in joined)
    return "chemistry_basic" if chemistry_score > cbc_score else "cbc"


def _extract_items(rows: list[dict[str, str | float]], report_type: LabReportType) -> list[LabReportItem]:
    items: list[LabReportItem] = []
    for canonical_name, aliases in _patterns(report_type).items():
        candidate = _match_row(canonical_name, aliases, rows, report_type)
        if candidate:
            items.append(candidate)
    return items


def _match_row(
    canonical_name: str,
    aliases: tuple[str, ...],
    rows: list[dict[str, str | float]],
    report_type: LabReportType,
) -> LabReportItem | None:
    best_match: LabReportItem | None = None
    for row in rows:
        raw_text = str(row["text"]).strip()
        matched_alias = _find_alias(raw_text, aliases)
        if not matched_alias:
            continue
        parsed = _parse_fixed_layout_row(raw_text, matched_alias, report_type)
        candidate = LabReportItem(
            name=canonical_name,
            alias=matched_alias,
            value=parsed["value"],
            unit=parsed["unit"],
            reference_range=parsed["reference_range"],
            flag=parsed["flag"],
            confidence=float(row.get("confidence", 0.0) or 0.0),
            confirmed=False,
            edited_by_user=False,
        )
        if not best_match or _item_score(candidate) > _item_score(best_match):
            best_match = candidate
    return best_match


def _find_alias(text: str, aliases: tuple[str, ...]) -> str | None:
    upper = text.upper()
    for alias in aliases:
        if alias.upper() in upper:
            return alias
    return None


def _parse_fixed_layout_row(text: str, alias: str, report_type: LabReportType) -> dict[str, str | ItemFlag]:
    normalized = re.sub(r"\s+", " ", text).strip()
    working = normalized.split(alias, 1)[1].strip() if alias in normalized else normalized
    working = re.sub(_REPORT_DEFS[report_type]["name_cleanup"], "", working, flags=re.IGNORECASE)  # type: ignore[arg-type]
    reference_range = _extract_reference_range(working)
    flag = _extract_flag(working)

    range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)", working)
    prefix = working[: range_match.start()].strip() if range_match else working
    suffix = working[range_match.end() :].strip() if range_match else ""

    value = _extract_primary_value(prefix)
    unit = _extract_unit(prefix, value=value, report_type=report_type)
    if not unit:
        unit = _extract_unit(working.replace(reference_range, "", 1), value=value, report_type=report_type)
    if flag == "unknown" and suffix:
        flag = _extract_flag(suffix)
    if flag == "unknown":
        flag = _infer_flag_from_value(value, reference_range)

    return {"value": value, "unit": unit, "reference_range": reference_range, "flag": flag}


def _item_score(item: LabReportItem) -> float:
    score = item.confidence
    if item.value:
        score += 1.0
    if item.reference_range:
        score += 0.4
    if item.unit:
        score += 0.3
    if item.flag != "unknown":
        score += 0.2
    return score


def _extract_primary_value(text: str) -> str:
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    return numbers[0] if numbers else ""


def _extract_reference_range(text: str) -> str:
    match = re.search(r"(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)", text)
    if not match:
        return ""
    return f"{match.group(1)}-{match.group(2)}"


def _extract_unit(text: str, *, value: str, report_type: LabReportType) -> str:
    working = text
    if value:
        working = working.replace(value, "", 1)
    working = re.sub(r"(^|\s)(H|L)(?=\s|$)", " ", working)
    working = working.replace("↑", "").replace("↓", "")
    pattern = "|".join(_REPORT_DEFS[report_type]["supported_units"])  # type: ignore[arg-type]
    match = re.search(f"({pattern})", working, flags=re.IGNORECASE)
    return match.group(1) if match else ""


def _extract_flag(text: str) -> ItemFlag:
    if re.search(r"(^|\s)H($|\s)", text) or "↑" in text:
        return "high"
    if re.search(r"(^|\s)L($|\s)", text) or "↓" in text:
        return "low"
    return "unknown"


def _infer_flag_from_value(value: str, reference_range: str) -> ItemFlag:
    if value and reference_range:
        try:
            low_text, high_text = reference_range.split("-", 1)
            numeric_value = float(value)
            low = float(low_text)
            high = float(high_text)
        except ValueError:
            return "unknown"
        if numeric_value < low:
            return "low"
        if numeric_value > high:
            return "high"
        return "normal"
    return "unknown"
