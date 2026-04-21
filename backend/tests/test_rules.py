import unittest

from app.models import LabReportItem, StructuredLabReport
from app.rules import evaluate_cross_report_alerts, evaluate_red_flags, evaluate_structured_lab_alerts


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

    def test_detects_high_potassium_risk_from_structured_items(self):
        alerts = evaluate_structured_lab_alerts(
            [
                LabReportItem(name="K", alias="K", value="5.8", unit="mmol/L"),
                LabReportItem(name="Cr", alias="Cr", value="128", unit="umol/L"),
            ],
            symptoms="乏力、心悸。",
            clinical_notes="",
        )

        self.assertTrue(any(alert.title == "高钾风险" for alert in alerts))
        self.assertTrue(any(alert.risk_level == "高风险" for alert in alerts))

    def test_detects_hyponatremia_with_symptoms_as_high_risk(self):
        alerts = evaluate_structured_lab_alerts(
            [LabReportItem(name="Na", alias="Na", value="128", unit="mmol/L")],
            symptoms="头晕、明显乏力。",
            clinical_notes="",
        )

        low_na_alert = next(alert for alert in alerts if alert.title == "低钠风险")
        self.assertEqual(low_na_alert.risk_level, "高风险")

    def test_detects_marked_hyperglycemia_with_symptoms_as_high_risk(self):
        alerts = evaluate_structured_lab_alerts(
            [LabReportItem(name="GLU", alias="GLU", value="14.2", unit="mmol/L")],
            symptoms="口渴、乏力。",
            clinical_notes="",
        )

        high_glu_alert = next(alert for alert in alerts if alert.title == "明显高血糖风险")
        self.assertEqual(high_glu_alert.risk_level, "高风险")

    def test_detects_high_potassium_with_renal_risk_across_reports(self):
        alerts = evaluate_cross_report_alerts(
            [
                StructuredLabReport(
                    report_type="cbc",
                    items=[
                        LabReportItem(name="HGB", alias="血红蛋白", value="108", unit="g/L"),
                    ],
                ),
                StructuredLabReport(
                    report_type="chemistry_basic",
                    items=[
                        LabReportItem(name="K", alias="钾", value="5.8", unit="mmol/L"),
                        LabReportItem(name="Cr", alias="肌酐", value="168", unit="umol/L"),
                        LabReportItem(name="eGFR", alias="eGFR", value="38", unit="mL/min/1.73m2"),
                    ],
                ),
            ],
            symptoms="乏力、心悸。",
            clinical_notes="",
        )

        alert = next(alert for alert in alerts if alert.title == "联合风险：高钾合并肾功能异常")
        self.assertEqual(alert.risk_level, "高风险")
        self.assertIn("K=5.8", alert.matched_terms)
        self.assertIn("eGFR=38", alert.matched_terms)

    def test_detects_anemia_with_renal_risk_across_reports(self):
        alerts = evaluate_cross_report_alerts(
            [
                StructuredLabReport(
                    report_type="cbc",
                    items=[
                        LabReportItem(name="HGB", alias="血红蛋白", value="82", unit="g/L"),
                    ],
                ),
                StructuredLabReport(
                    report_type="chemistry_basic",
                    items=[
                        LabReportItem(name="Cr", alias="肌酐", value="140", unit="umol/L"),
                    ],
                ),
            ],
            symptoms="头晕、乏力。",
            clinical_notes="",
        )

        alert = next(alert for alert in alerts if alert.title == "联合风险：贫血合并肾功能异常")
        self.assertEqual(alert.risk_level, "高风险")


if __name__ == "__main__":
    unittest.main()
