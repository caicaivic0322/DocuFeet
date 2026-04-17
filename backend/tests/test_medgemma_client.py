import unittest

from app.medgemma_client import (
    _coerce_medgemma_payload,
    _extract_first_json_object,
    _prepare_medgemma_prompt,
)


class MedGemmaPayloadTest(unittest.TestCase):
    def test_coerces_placeholder_risk_level_to_medium_risk(self):
        payload = {
            "risk_level": "低风险|中风险|高风险",
            "doctor_summary": "测试输出",
            "abnormal_findings": [],
            "possible_causes": [],
            "next_steps": [],
            "urgent_transfer_reasons": [],
            "medication_watchouts": [],
            "citations": [],
            "applied_rules": [],
        }

        normalized = _coerce_medgemma_payload(payload)

        self.assertEqual(normalized["risk_level"], "中风险")

    def test_extracts_first_complete_json_object_when_model_returns_extra_data(self):
        text = '{"risk_level": "高风险"}\n{"extra": true}'

        extracted = _extract_first_json_object(text)

        self.assertEqual(extracted, '{"risk_level": "高风险"}')

    def test_removes_schema_instruction_values_from_model_payload(self):
        payload = {
            "risk_level": "高风险",
            "doctor_summary": "结合症状、病史和检查结果写一到三句基层医生版摘要",
            "abnormal_findings": ["写出具体异常指标或症状线索"],
            "possible_causes": ["写出可能原因，避免确定诊断"],
            "next_steps": ["写出基层场景下可执行的下一步检查、观察或转诊动作"],
            "urgent_transfer_reasons": ["如需转诊，写出具体理由；如无则返回空数组"],
            "medication_watchouts": ["结合当前用药写注意事项；如无则返回空数组"],
            "citations": [{"source": "规则命中或本地知识片段名称", "excerpt": "引用的具体依据"}],
            "applied_rules": [],
        }

        normalized = _coerce_medgemma_payload(payload)

        self.assertEqual(normalized["doctor_summary"], "MedGemma 未返回具体摘要，请结合规则命中和原始资料人工复核。")
        self.assertEqual(normalized["abnormal_findings"], [])
        self.assertEqual(normalized["next_steps"], [])
        self.assertEqual(normalized["urgent_transfer_reasons"], [])
        self.assertEqual(normalized["citations"], [])

    def test_adds_gemma_image_token_when_image_is_present(self):
        prompt = _prepare_medgemma_prompt("请分析这张胸片。", has_image=True, boi_token="<start_of_image>")

        self.assertTrue(prompt.startswith("<start_of_image>\n"))
        self.assertIn("请分析这张胸片。", prompt)

    def test_does_not_add_image_token_without_image(self):
        prompt = _prepare_medgemma_prompt("仅分析文字病情。", has_image=False, boi_token="<start_of_image>")

        self.assertEqual(prompt, "仅分析文字病情。")


if __name__ == "__main__":
    unittest.main()
