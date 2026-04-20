import unittest

from app.rules import evaluate_red_flags


class RuleMatchingTest(unittest.TestCase):
    def test_does_not_match_negated_red_flag_symptoms(self):
        alerts = evaluate_red_flags("低热一天，轻微咳嗽，无气促，无胸痛。")

        matched_terms = [term for alert in alerts for term in alert.matched_terms]

        self.assertNotIn("胸痛", matched_terms)
        self.assertNotIn("气促", matched_terms)
        self.assertFalse(any(alert.risk_level == "高风险" for alert in alerts))

    def test_still_matches_affirmed_red_flag_symptoms(self):
        alerts = evaluate_red_flags("走路后胸闷气短，伴呼吸困难。")

        matched_terms = [term for alert in alerts for term in alert.matched_terms]

        self.assertIn("胸闷", matched_terms)
        self.assertIn("呼吸困难", matched_terms)
        self.assertTrue(any(alert.risk_level == "高风险" for alert in alerts))


if __name__ == "__main__":
    unittest.main()
