import unittest

from app.medgemma_client import (
    MedGemmaRuntime,
    _build_medgemma_messages,
    _coerce_medgemma_payload,
    _choose_torch_device,
    _extract_first_json_object,
    _generation_kwargs,
    _slice_generated_token_ids,
    _prepare_medgemma_prompt,
    _restore_json_prefill,
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

    def test_auto_device_prefers_mps_when_available(self):
        self.assertEqual(
            _choose_torch_device("auto", mps_available=True, cuda_available=False),
            "mps",
        )

    def test_auto_device_uses_cpu_when_no_accelerator_is_available(self):
        self.assertEqual(
            _choose_torch_device("auto", mps_available=False, cuda_available=False),
            "cpu",
        )

    def test_explicit_device_overrides_auto_selection(self):
        self.assertEqual(
            _choose_torch_device("cpu", mps_available=True, cuda_available=True),
            "cpu",
        )

    def test_mps_generation_uses_greedy_decoding_to_avoid_sampling_nans(self):
        kwargs = _generation_kwargs(device="mps", max_new_tokens=256, temperature=0.2)

        self.assertEqual(kwargs["max_new_tokens"], 256)
        self.assertFalse(kwargs["do_sample"])
        self.assertNotIn("temperature", kwargs)

    def test_cpu_generation_keeps_sampling_when_temperature_is_enabled(self):
        kwargs = _generation_kwargs(device="cpu", max_new_tokens=256, temperature=0.2)

        self.assertTrue(kwargs["do_sample"])
        self.assertEqual(kwargs["temperature"], 0.2)

    def test_slices_prompt_tokens_before_decoding_generation(self):
        output_ids = [[101, 102, 201, 202]]

        self.assertEqual(_slice_generated_token_ids(output_ids, prompt_token_count=2), [[201, 202]])

    def test_builds_chat_messages_with_image_content_first(self):
        messages = _build_medgemma_messages(
            system_prompt="系统规则",
            user_prompt="病例信息",
            image=object(),
        )

        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"][0]["type"], "image")
        self.assertEqual(messages[1]["content"][1]["text"], "病例信息")

    def test_restores_prefilled_json_opening_brace(self):
        self.assertEqual(_restore_json_prefill('"risk_level": "中风险"}'), '{"risk_level": "中风险"}')
        self.assertEqual(_restore_json_prefill('{"risk_level": "中风险"}'), '{"risk_level": "中风险"}')

    def test_unload_resets_loaded_runtime_state(self):
        runtime = MedGemmaRuntime(
            _loaded=True,
            _processor=object(),
            _model=object(),
            _actual_device="cpu",
        )

        runtime.unload()

        self.assertFalse(runtime.is_loaded())
        self.assertEqual(runtime.actual_device(), "not_loaded")


if __name__ == "__main__":
    unittest.main()
