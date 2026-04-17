from __future__ import annotations

from typing import Optional

from .models import RiskLevel, RuleAlert

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


def evaluate_red_flags(*parts: Optional[str]) -> list[RuleAlert]:
    haystack = " ".join(part for part in parts if part).lower()
    alerts: list[RuleAlert] = []

    for rule in _RED_FLAG_RULES:
        matched = [
            keyword for keyword in rule["keywords"] if keyword.lower() in haystack
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


def highest_risk(alerts: list[RuleAlert]) -> RiskLevel:
    if not alerts:
        return "低风险"
    return alerts[0].risk_level
