import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.main import (
    _build_referral_card,
    _choose_backend,
    _fallback_reason,
    _postprocess_analysis_response,
    _validate_confirmed_lab_items,
)
from app.models import (
    AnalysisResponse,
    CBCReportItem,
    InferenceMeta,
    RuleAlert,
    StructuredCBCReport,
)
from app.medgemma_client import MedGemmaRuntimeError


class InferenceFlowTest(unittest.TestCase):
    def test_uses_medgemma_when_ready(self):
        self.assertEqual(_choose_backend("ready", True), "medgemma")

    def test_falls_back_to_ollama_when_medgemma_not_ready(self):
        self.assertEqual(_choose_backend("loading", True), "ollama")

    def test_falls_back_to_ollama_when_medgemma_is_disabled(self):
        self.assertEqual(_choose_backend("disabled", True), "ollama")

    def test_reports_no_backend_when_both_are_unavailable(self):
        self.assertIsNone(_choose_backend("failed", False))

    def test_inference_meta_marks_fallback(self):
        meta = InferenceMeta(
            backend="ollama",
            used_fallback=True,
            primary_backend="medgemma",
            fallback_reason=_fallback_reason("loading"),
        )

        self.assertTrue(meta.used_fallback)
        self.assertEqual(meta.backend, "ollama")
        self.assertIn("MedGemma", meta.fallback_reason)

    def test_postprocess_removes_urgent_reason_that_contradicts_negated_symptom(self):
        response = AnalysisResponse(
            risk_level="高风险",
            doctor_summary="患者无意识改变。",
            abnormal_findings=["胸片提示肺部感染可能"],
            possible_causes=["肺炎"],
            next_steps=[],
            urgent_transfer_reasons=["患者伴有胸闷气短，且有意识改变，符合转诊高风险线索"],
        )

        _postprocess_analysis_response(
            response,
            alerts=[],
            symptoms="咳嗽咳痰，胸闷气短，无意识改变。",
            clinical_notes="指脉氧93%，无意识改变。",
        )

        self.assertNotIn("有意识改变", " ".join(response.urgent_transfer_reasons))

    def test_postprocess_downgrades_model_high_risk_without_actionable_transfer_reason(self):
        response = AnalysisResponse(
            risk_level="高风险",
            doctor_summary="低热、轻微咳嗽，无气促或胸痛。",
            abnormal_findings=["胸部透光性正常，心影大小、形状、位置符合正常范围。"],
            possible_causes=["上呼吸道感染"],
            next_steps=["观察体温和咳嗽变化。"],
            urgent_transfer_reasons=["无明确转诊理由。"],
        )

        _postprocess_analysis_response(
            response,
            alerts=[],
            symptoms="低热一天，轻微咳嗽，无气促，无胸痛。",
            clinical_notes="精神尚可，指脉氧98%。",
        )

        self.assertEqual(response.risk_level, "中风险")
        self.assertEqual(response.urgent_transfer_reasons, [])

    def test_postprocess_preserves_rule_backed_high_risk(self):
        response = AnalysisResponse(
            risk_level="中风险",
            doctor_summary="胸闷伴气短。",
            abnormal_findings=[],
            possible_causes=[],
            next_steps=[],
            urgent_transfer_reasons=[],
        )
        alerts = [
            RuleAlert(
                title="疑似心血管高危",
                matched_terms=["胸闷"],
                rationale="胸部不适合并呼吸困难时，需要优先排除急性心血管事件。",
                recommended_action="立即评估生命体征并考虑转诊。",
                risk_level="高风险",
            )
        ]

        _postprocess_analysis_response(
            response,
            alerts=alerts,
            symptoms="胸闷，呼吸困难。",
            clinical_notes="",
        )

        self.assertEqual(response.risk_level, "高风险")
        self.assertEqual(response.urgent_transfer_reasons, [alerts[0].rationale])

    def test_postprocess_structured_high_risk_rule_overrides_model_medium_risk(self):
        response = AnalysisResponse(
            risk_level="中风险",
            doctor_summary="存在电解质异常。",
            abnormal_findings=["K 升高"],
            possible_causes=["电解质紊乱"],
            next_steps=[],
            urgent_transfer_reasons=[],
        )
        alerts = [
            RuleAlert(
                title="高钾风险",
                matched_terms=["K=5.8"],
                rationale="血钾明显升高时需要警惕心律失常风险，基层场景应尽快复核心电图和重复电解质。",
                recommended_action="尽快复查电解质并完善心电图；若伴乏力、心悸或病情不稳，应立即转诊。",
                risk_level="高风险",
            )
        ]

        _postprocess_analysis_response(
            response,
            alerts=alerts,
            symptoms="乏力、心悸。",
            clinical_notes="",
        )

        self.assertEqual(response.risk_level, "高风险")
        self.assertEqual(response.urgent_transfer_reasons, [alerts[0].rationale])
        self.assertEqual(response.next_steps, [alerts[0].recommended_action])

    def test_postprocess_high_risk_rules_replace_model_generated_transfer_reasons(self):
        response = AnalysisResponse(
            risk_level="高风险",
            doctor_summary="存在电解质异常。",
            abnormal_findings=["K 升高"],
            possible_causes=["电解质紊乱"],
            next_steps=["复查心电图"],
            urgent_transfer_reasons=["模型生成的不可靠急转理由"],
        )
        alerts = [
            RuleAlert(
                title="高钾风险",
                matched_terms=["K=5.8"],
                rationale="血钾明显升高时需要警惕心律失常风险，基层场景应尽快复核心电图和重复电解质。",
                recommended_action="尽快复查电解质并完善心电图；若伴乏力、心悸或病情不稳，应立即转诊。",
                risk_level="高风险",
            )
        ]

        _postprocess_analysis_response(
            response,
            alerts=alerts,
            symptoms="乏力、心悸。",
            clinical_notes="",
        )

        self.assertEqual(response.urgent_transfer_reasons, [alerts[0].rationale])

    def test_validate_confirmed_cbc_items_requires_core_fields(self):
        items = [
            CBCReportItem(name="WBC", alias="WBC", value="6.1", confirmed=True),
            CBCReportItem(name="RBC", alias="RBC", value="4.2", confirmed=True),
            CBCReportItem(name="HGB", alias="HGB", value="120", confirmed=True),
        ]

        with self.assertRaises(HTTPException):
            _validate_confirmed_lab_items("cbc", items)

    def test_validate_confirmed_chemistry_items_requires_core_fields(self):
        items = [
            CBCReportItem(name="Cr", alias="Cr", value="128", confirmed=True),
            CBCReportItem(name="K", alias="K", value="5.8", confirmed=True),
            CBCReportItem(name="Na", alias="Na", value="134", confirmed=True),
        ]

        with self.assertRaises(HTTPException):
            _validate_confirmed_lab_items("chemistry_basic", items)

    def test_referral_card_prefers_immediate_transfer_for_high_risk_output(self):
        response = AnalysisResponse(
            risk_level="高风险",
            doctor_summary="患者贫血明显，伴头晕乏力。",
            abnormal_findings=["HGB 降低"],
            possible_causes=["失血或其他原因所致贫血"],
            next_steps=["完善网织红细胞和复查血常规", "必要时急诊转诊"],
            urgent_transfer_reasons=["血红蛋白明显下降，需尽快上级医院评估。"],
        )

        card = _build_referral_card(
            response=response,
            structured_report=StructuredCBCReport(
                items=[
                    CBCReportItem(
                        name="HGB",
                        alias="HGB",
                        value="68",
                        unit="g/L",
                        reference_range="115-150",
                        flag="low",
                    )
                ]
            ),
            alerts=[],
        )

        self.assertEqual(card.decision, "立即转诊")
        self.assertIn("血红蛋白明显下降", " ".join(card.reasons))
        self.assertTrue(card.handoff_notes)

    def test_referral_card_uses_structured_lab_abnormalities_when_no_explicit_reason_exists(self):
        response = AnalysisResponse(
            risk_level="中风险",
            doctor_summary="存在高钾和肌酐升高，建议尽快复核。",
            abnormal_findings=["K 升高", "Cr 升高"],
            possible_causes=["电解质紊乱或肾功能异常"],
            next_steps=["复查电解质并完善心电图"],
            urgent_transfer_reasons=[],
        )

        card = _build_referral_card(
            response=response,
            structured_report=StructuredCBCReport(
                report_type="chemistry_basic",
                items=[
                    CBCReportItem(name="K", alias="K", value="5.8", unit="mmol/L", reference_range="3.5-5.3", flag="high"),
                    CBCReportItem(name="Cr", alias="Cr", value="128", unit="umol/L", reference_range="57-111", flag="high"),
                ],
            ),
            alerts=[],
        )

        self.assertEqual(card.decision, "尽快复诊")
        self.assertIn("K=5.8", " ".join(card.reasons))

    def test_analyze_falls_back_to_ollama_when_medgemma_runtime_fails(self):
        medgemma_response = MedGemmaRuntimeError("主模型输出未包含 JSON 对象。")
        ollama_response = AnalysisResponse(
            risk_level="中风险",
            doctor_summary="已使用备用模型完成分析。",
            abnormal_findings=[],
            possible_causes=[],
            next_steps=["复查电解质"],
            urgent_transfer_reasons=[],
        )

        async def run():
            from app.main import _analyze_with_selected_backend

            with patch("app.main._refresh_ollama_runtime_state", new=AsyncMock(return_value={"reachable": True, "has_model": True})), patch(
                "app.main._is_active", side_effect=lambda backend: True
            ), patch("app.main.model_runtime_state", {"medgemma": {"status": "ready"}, "ollama": {"status": "ready"}}), patch(
                "app.main.medgemma_runtime.is_loaded", return_value=True
            ), patch("app.main._call_backend", new=AsyncMock(side_effect=[medgemma_response, ollama_response])):
                return await _analyze_with_selected_backend(
                    image_base64=None,
                    image_filename="sample.png",
                    patient_age=58,
                    patient_sex="男",
                    symptoms="口渴、乏力。",
                    clinical_notes="",
                    current_medications="二甲双胍",
                    alerts=[],
                    structured_report=None,
                )

        result = __import__("asyncio").run(run())
        self.assertTrue(result.inference.used_fallback)
        self.assertEqual(result.inference.backend, "ollama")
