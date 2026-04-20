import unittest

from app.main import _choose_backend, _fallback_reason, _postprocess_analysis_response
from app.models import AnalysisResponse, InferenceMeta, RuleAlert


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
