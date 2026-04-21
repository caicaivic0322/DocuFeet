import unittest

from app.models import CBCReportItem, StructuredCBCReport
from app.prompting import build_system_prompt, build_user_prompt


class PromptingTest(unittest.TestCase):
    def test_system_prompt_does_not_use_placeholder_values_in_json_schema(self):
        prompt = build_system_prompt()

        self.assertNotIn("低风险|中风险|高风险", prompt)
        self.assertNotIn("异常点1", prompt)
        self.assertIn('"risk_level": "中风险"', prompt)
        self.assertIn("不要照抄示例值", prompt)

    def test_user_prompt_embeds_confirmed_cbc_fields(self):
        prompt = build_user_prompt(
            patient_age=68,
            patient_sex="女",
            symptoms="乏力",
            clinical_notes="面色苍白",
            current_medications="无",
            alerts=[],
            image_filename="cbc.png",
            structured_report=StructuredCBCReport(
                source_image_name="cbc.png",
                items=[
                    CBCReportItem(
                        name="HGB",
                        alias="HGB",
                        value="82",
                        unit="g/L",
                        reference_range="115-150",
                        flag="low",
                    )
                ],
            ),
        )

        self.assertIn("[确认后的结构化检验字段]", prompt)
        self.assertIn("HGB: 数值=82", prompt)


if __name__ == "__main__":
    unittest.main()
