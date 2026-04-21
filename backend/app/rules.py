from __future__ import annotations

from typing import Optional

from .models import LabReportItem, RiskLevel, RuleAlert, StructuredLabReport

_RED_FLAG_RULES = [
    {
        "title": "疑似心血管高危",
        "keywords": ["胸痛", "胸闷", "大汗", "出汗", "呼吸困难", "放射痛", "濒死感"],
        "rationale": "胸部不适合并出汗或呼吸困难时，需要优先排除急性心血管事件。",
        "recommended_action": "立即评估生命体征，完善心电图/肌钙蛋白，并考虑转上级医院。",
        "risk_level": "高风险",
    },
    {
        "title": "疑似脑卒中或急性神经系统事件",
        "keywords": ["口角歪斜", "言语不清", "肢体无力", "偏瘫", "抽搐", "意识障碍"],
        "rationale": "急性局灶神经功能缺失或抽搐提示需要紧急评估。",
        "recommended_action": "立即启动卒中/神经急症流程并紧急转诊。",
        "risk_level": "高风险",
    },
    {
        "title": "疑似严重感染或脓毒症",
        "keywords": ["高热", "寒战", "神志改变", "低血压", "呼吸急促", "少尿"],
        "rationale": "感染伴循环或意识异常时，需要尽快排除脓毒症。",
        "recommended_action": "尽快复测生命体征，完善感染评估，必要时立即转诊。",
        "risk_level": "高风险",
    },
    {
        "title": "消化道/失血风险",
        "keywords": ["黑便", "呕血", "便血", "头晕乏力", "晕厥"],
        "rationale": "出血相关症状需要结合血红蛋白和血流动力学状态快速判断。",
        "recommended_action": "尽快复查血常规并评估失血风险，必要时转诊。",
        "risk_level": "高风险",
    },
    {
        "title": "非特异但需要尽快评估",
        "keywords": ["持续发热", "反复呕吐", "明显乏力", "食欲差", "体重下降"],
        "rationale": "持续或进行性症状提示存在需要进一步检查的风险。",
        "recommended_action": "优先完成基础检查并结合检验结果决定是否升级转诊。",
        "risk_level": "中风险",
    },
]

_RISK_ORDER: dict[RiskLevel, int] = {"低风险": 0, "中风险": 1, "高风险": 2}
_NEGATION_MARKERS = ("无", "没有", "未见", "否认", "不伴", "未")


def _keyword_is_negated(haystack: str, keyword: str) -> bool:
    index = haystack.find(keyword)
    while index != -1:
        prefix = haystack[max(0, index - 4) : index]
        if any(marker in prefix for marker in _NEGATION_MARKERS):
            index = haystack.find(keyword, index + len(keyword))
            continue
        return False
    return True


def evaluate_red_flags(*parts: Optional[str]) -> list[RuleAlert]:
    haystack = " ".join(part for part in parts if part).lower()
    alerts: list[RuleAlert] = []

    for rule in _RED_FLAG_RULES:
        matched = [
            keyword
            for keyword in rule["keywords"]
            if keyword.lower() in haystack
            and not _keyword_is_negated(haystack, keyword.lower())
        ]
        if matched:
            alerts.append(
                RuleAlert(
                    title=rule["title"],
                    matched_terms=matched,
                    rationale=rule["rationale"],
                    recommended_action=rule["recommended_action"],
                    risk_level=rule["risk_level"],
                )
            )

    alerts.sort(key=lambda item: _RISK_ORDER[item.risk_level], reverse=True)
    return alerts


def evaluate_structured_lab_alerts(
    items: list[LabReportItem],
    *,
    symptoms: Optional[str],
    clinical_notes: Optional[str],
) -> list[RuleAlert]:
    lookup = {item.name: item for item in items if item.value.strip()}
    source_text = " ".join(part for part in (symptoms, clinical_notes) if part)
    alerts: list[RuleAlert] = []

    potassium = _as_float(lookup.get("K"))
    creatinine = _as_float(lookup.get("Cr"))
    egfr = _as_float(lookup.get("eGFR"))
    glucose = _as_float(lookup.get("GLU"))
    sodium = _as_float(lookup.get("Na"))
    chloride = _as_float(lookup.get("Cl"))

    if potassium is not None and potassium >= 5.5:
        alerts.append(
            RuleAlert(
                title="高钾风险",
                matched_terms=[f"K={potassium:g}"],
                rationale="血钾明显升高时需要警惕心律失常风险，基层场景应尽快复核心电图和重复电解质。",
                recommended_action="尽快复查电解质并完善心电图；若伴乏力、心悸或病情不稳，应立即转诊。",
                risk_level="高风险",
            )
        )

    if creatinine is not None and (creatinine >= 120 or (egfr is not None and egfr < 60)):
        matched = []
        if creatinine is not None and creatinine >= 120:
            matched.append(f"Cr={creatinine:g}")
        if egfr is not None and egfr < 60:
            matched.append(f"eGFR={egfr:g}")
        alerts.append(
            RuleAlert(
                title="肾功能异常风险",
                matched_terms=matched,
                rationale="肌酐升高或 eGFR 下降提示存在肾功能受损风险，需要结合脱水、感染、用药和基础肾病情况尽快评估。",
                recommended_action="尽快复查肾功能与尿量，评估脱水和用药影响；若进行性加重或伴少尿，应考虑转诊。",
                risk_level="中风险" if egfr is None or egfr >= 45 else "高风险",
            )
        )

    if glucose is not None and glucose >= 13.9:
        alerts.append(
            RuleAlert(
                title="明显高血糖风险",
                matched_terms=[f"GLU={glucose:g}"],
                rationale="血糖明显升高时需警惕酮症或高渗状态，尤其在口渴、乏力、呕吐等症状存在时更需提高警觉。",
                recommended_action="尽快复测血糖，评估尿酮体或血酮及脱水情况；若症状明显或血糖继续升高，应尽快转诊。",
                risk_level="高风险" if _contains_any(source_text, ("口渴", "呕吐", "意识差", "乏力")) else "中风险",
            )
        )

    if sodium is not None and sodium < 135:
        risk_level: RiskLevel = "中风险"
        if sodium < 130 and _contains_any(source_text, ("头晕", "呕吐", "意识差", "抽搐", "明显乏力", "乏力")):
            risk_level = "高风险"
        alerts.append(
            RuleAlert(
                title="低钠风险",
                matched_terms=[f"Na={sodium:g}"],
                rationale="低钠时需结合乏力、头晕、呕吐或意识异常判断是否存在需要尽快纠正的电解质紊乱。",
                recommended_action="尽快复查电解质并评估容量状态；若低钠明显或伴神经系统症状，应考虑转诊。",
                risk_level=risk_level,
            )
        )

    if chloride is not None and chloride < 98 and _contains_any(source_text, ("呕吐", "乏力", "头晕")):
        alerts.append(
            RuleAlert(
                title="低氯伴症状风险",
                matched_terms=[f"Cl={chloride:g}"],
                rationale="低氯合并呕吐、乏力或头晕时，提示可能存在容量不足或酸碱失衡，需要尽快复核。",
                recommended_action="尽快复查电解质和容量状态，必要时上级医院进一步评估。",
                risk_level="中风险",
            )
        )

    alerts.sort(key=lambda item: _RISK_ORDER[item.risk_level], reverse=True)
    return alerts


def evaluate_cross_report_alerts(
    reports: list[StructuredLabReport],
    *,
    symptoms: Optional[str],
    clinical_notes: Optional[str],
) -> list[RuleAlert]:
    items = [
        item
        for report in reports
        for item in report.items
        if item.confirmed and item.value.strip()
    ]
    lookup = {item.name: item for item in items}
    source_text = " ".join(part for part in (symptoms, clinical_notes) if part)
    alerts: list[RuleAlert] = []

    potassium = _as_float(lookup.get("K"))
    creatinine = _as_float(lookup.get("Cr"))
    egfr = _as_float(lookup.get("eGFR"))
    glucose = _as_float(lookup.get("GLU"))
    hemoglobin = _as_float(lookup.get("HGB"))

    renal_terms = _renal_matched_terms(creatinine=creatinine, egfr=egfr)
    has_renal_risk = bool(renal_terms)

    if potassium is not None and potassium >= 5.5 and has_renal_risk:
        alerts.append(
            RuleAlert(
                title="联合风险：高钾合并肾功能异常",
                matched_terms=[f"K={potassium:g}", *renal_terms],
                rationale="血钾升高同时存在肌酐升高或 eGFR 下降时，高钾持续或加重的风险更高，需要按电解质急症优先处理。",
                recommended_action="立即复查电解质和心电图，核对影响血钾的用药；若心电图异常、少尿或症状明显，应立即转诊。",
                risk_level="高风险",
            )
        )

    if hemoglobin is not None and hemoglobin < 90 and has_renal_risk:
        risk_level: RiskLevel = "高风险" if _contains_any(
            source_text, ("头晕", "心悸", "气短", "乏力", "胸闷")
        ) else "中风险"
        alerts.append(
            RuleAlert(
                title="联合风险：贫血合并肾功能异常",
                matched_terms=[f"HGB={hemoglobin:g}", *renal_terms],
                rationale="明显贫血叠加肾功能异常时，需要警惕慢性肾病相关贫血、失血或急性病情加重，单看一张报告容易低估风险。",
                recommended_action="复核血常规、肾功能和尿常规，询问黑便/出血及慢性肾病史；若伴胸闷、心悸、气短或进行性乏力，应尽快转诊。",
                risk_level=risk_level,
            )
        )

    if glucose is not None and glucose >= 13.9 and (
        has_renal_risk or _contains_any(source_text, ("口渴", "呕吐", "少尿", "尿量减少", "明显乏力"))
    ):
        matched = [f"GLU={glucose:g}", *renal_terms]
        alerts.append(
            RuleAlert(
                title="联合风险：高血糖伴脱水或肾功能风险",
                matched_terms=matched,
                rationale="明显高血糖合并口渴、少尿或肾功能异常时，需要警惕脱水、酮症或高渗状态对肾功能的进一步影响。",
                recommended_action="尽快复测血糖，评估尿酮/血酮、容量状态和肾功能；若呕吐、意识改变、少尿或血糖持续升高，应立即转诊。",
                risk_level="高风险",
            )
        )

    alerts.sort(key=lambda item: _RISK_ORDER[item.risk_level], reverse=True)
    return alerts


def _as_float(item: LabReportItem | None) -> float | None:
    if item is None or not item.value.strip():
        return None
    try:
        return float(item.value)
    except ValueError:
        return None


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _renal_matched_terms(*, creatinine: float | None, egfr: float | None) -> list[str]:
    matched = []
    if creatinine is not None and creatinine >= 120:
        matched.append(f"Cr={creatinine:g}")
    if egfr is not None and egfr < 60:
        matched.append(f"eGFR={egfr:g}")
    return matched


def highest_risk(alerts: list[RuleAlert]) -> RiskLevel:
    if not alerts:
        return "低风险"
    return alerts[0].risk_level
