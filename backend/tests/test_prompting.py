import unittest

from app.prompting import build_system_prompt


class PromptingTest(unittest.TestCase):
    def test_system_prompt_does_not_use_placeholder_values_in_json_schema(self):
        prompt = build_system_prompt()

        self.assertNotIn("低风险|中风险|高风险", prompt)
        self.assertNotIn("异常点1", prompt)
        self.assertIn('"risk_level": "中风险"', prompt)
        self.assertIn("不要照抄示例值", prompt)


if __name__ == "__main__":
    unittest.main()
