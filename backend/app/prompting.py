from __future__ import annotations

from typing import Optional

from .knowledge import CURATED_GUIDANCE
from .models import RuleAlert


def build_system_prompt() -> str:
    return """你是“乡镇医生的副手”，不是独立执业医生。

请严格遵守以下规则：
1. 不输出确定诊断，不使用“确诊”“就是”“肯定”等措辞。
2. 必须输出风险等级：低风险 / 中风险 / 高风险。
3. 必须输出下一步行动，优先写需要补充的检查、观察或转诊建议。
4. 必须说明依据，依据只能来自：
   - 用户提供的症状、既往史、用药、报告图片
   - 提供给你的规则命中结果
   - 提供给你的本地知识片段
5. 对高风险情况优先提醒转诊，不要被单一检验指标误导。
6. 输出 JSON，不要输出 Markdown。

JSON 字段要求：
{
  "risk_level": "低风险|中风险|高风险",
  "doctor_summary": "一句到三句的临床摘要",
  "abnormal_findings": ["异常点1", "异常点2"],
  "possible_causes": ["可能原因1", "可能原因2"],
  "next_steps": ["下一步1", "下一步2"],
  "urgent_transfer_reasons": ["需要立即转诊的原因"],
  "medication_watchouts": ["用药注意事项"],
  "citations": [{"source": "来源", "excerpt": "引用内容"}]
}
"""


def build_user_prompt(
    *,
    patient_age: Optional[int],
    patient_sex: Optional[str],
    symptoms: Optional[str],
    clinical_notes: Optional[str],
    current_medications: Optional[str],
    alerts: list[RuleAlert],
    image_filename: Optional[str],
) -> str:
    rule_lines = "\n".join(
        f'- {alert.title} | 风险={alert.risk_level} | 命中={", ".join(alert.matched_terms)} | 原因={alert.rationale} | 建议={alert.recommended_action}'
        for alert in alerts
    ) or "- 未命中明确红旗规则"

    knowledge_lines = "\n".join(
        f'- {item["source"]}: {item["excerpt"]}' for item in CURATED_GUIDANCE
    )

    return f"""请结合上传的检查单图片与以下信息生成基层医生版结果。

[患者基础信息]
- 年龄: {patient_age or "未提供"}
- 性别: {patient_sex or "未提供"}

[主诉/症状]
{symptoms or "未提供"}

[补充病情]
{clinical_notes or "未提供"}

[当前用药]
{current_medications or "未提供"}

[图片文件名]
{image_filename or "未上传图片"}

[规则命中]
{rule_lines}

[本地知识片段]
{knowledge_lines}

请优先识别：
1. 检查单里的异常指标
2. 是否存在需要立即转诊的高危线索
3. 在基层条件下最实际的下一步动作

再次强调：不要给出确定诊断。"""
