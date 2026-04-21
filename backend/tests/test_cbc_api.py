import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    AnalysisResponse,
    CBCExtractionResponse,
    CBCReportItem,
    ReferralCard,
    StructuredCBCReport,
)


class CBCAPITest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_extract_cbc_endpoint_returns_candidate_fields(self):
        extraction = CBCExtractionResponse(
            source_image_name="cbc.png",
            raw_text="WBC 6.1",
            items=[
                CBCReportItem(
                    name="WBC",
                    alias="WBC",
                    value="6.1",
                    unit="10^9/L",
                    reference_range="3.5-9.5",
                    flag="normal",
                    confidence=0.98,
                    confirmed=False,
                )
            ],
            can_analyze=False,
            missing_required_items=["RBC", "HGB", "PLT"],
        )

        with patch("app.main.extract_cbc_from_image", return_value=extraction):
            response = self.client.post(
                "/api/report/extract-cbc",
                files={"report_image": ("cbc.png", b"fake", "image/png")},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["items"][0]["name"], "WBC")

    def test_analyze_cbc_rejects_missing_required_fields(self):
        response = self.client.post(
            "/api/report/analyze-cbc",
            json={
                "report_type": "cbc",
                "patient_age": 63,
                "items": [
                    {
                        "name": "WBC",
                        "alias": "WBC",
                        "value": "6.1",
                        "confirmed": True,
                    }
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("关键检验字段缺失", response.json()["detail"])

    def test_analyze_cbc_returns_referral_card(self):
        result = AnalysisResponse(
            risk_level="中风险",
            doctor_summary="血红蛋白偏低，建议复查。",
            abnormal_findings=["HGB 偏低"],
            possible_causes=["贫血可能"],
            next_steps=["复查血常规", "必要时转上级医院"],
            urgent_transfer_reasons=[],
            medication_watchouts=[],
            citations=[],
            structured_report=StructuredCBCReport(
                items=[CBCReportItem(name="HGB", alias="HGB", value="88", confirmed=True)]
            ),
            referral_card=ReferralCard(
                decision="尽快复诊",
                reasons=["血红蛋白偏低"],
                suggested_checks=["复查血常规"],
                handoff_notes=["结合贫血风险复核"],
            ),
        )

        with patch("app.main._analyze_with_selected_backend", new=AsyncMock(return_value=result)):
            response = self.client.post(
                "/api/report/analyze-cbc",
                json={
                    "report_type": "cbc",
                    "patient_age": 63,
                    "source_image_name": "cbc.png",
                    "items": [
                        {"name": "WBC", "alias": "WBC", "value": "6.1", "confirmed": True},
                        {"name": "RBC", "alias": "RBC", "value": "4.2", "confirmed": True},
                        {"name": "HGB", "alias": "HGB", "value": "88", "confirmed": True},
                        {"name": "PLT", "alias": "PLT", "value": "210", "confirmed": True},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("referral_card", response.json())

    def test_analyze_chemistry_rejects_missing_required_fields(self):
        response = self.client.post(
            "/api/report/analyze-cbc",
            json={
                "report_type": "chemistry_basic",
                "patient_age": 58,
                "items": [
                    {"name": "Cr", "alias": "Cr", "value": "128", "confirmed": True},
                    {"name": "K", "alias": "K", "value": "5.8", "confirmed": True},
                ],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("关键检验字段缺失", response.json()["detail"])

    def test_analyze_labs_accepts_multiple_confirmed_reports(self):
        result = AnalysisResponse(
            risk_level="高风险",
            doctor_summary="多报告综合分析完成。",
            abnormal_findings=["HGB 偏低", "K 偏高"],
            possible_causes=["贫血和电解质紊乱"],
            next_steps=["复查血常规和电解质"],
            urgent_transfer_reasons=["高钾风险"],
            medication_watchouts=[],
            citations=[],
            structured_reports=[
                StructuredCBCReport(
                    report_type="cbc",
                    source_image_name="cbc.png",
                    items=[
                        CBCReportItem(name="WBC", alias="WBC", value="6.1", confirmed=True),
                        CBCReportItem(name="RBC", alias="RBC", value="4.2", confirmed=True),
                        CBCReportItem(name="HGB", alias="HGB", value="88", confirmed=True),
                        CBCReportItem(name="PLT", alias="PLT", value="210", confirmed=True),
                    ],
                ),
                StructuredCBCReport(
                    report_type="chemistry_basic",
                    source_image_name="chem.png",
                    items=[
                        CBCReportItem(name="Cr", alias="Cr", value="128", confirmed=True),
                        CBCReportItem(name="K", alias="K", value="5.8", confirmed=True),
                        CBCReportItem(name="Na", alias="Na", value="134", confirmed=True),
                        CBCReportItem(name="GLU", alias="GLU", value="13.6", confirmed=True),
                    ],
                ),
            ],
            referral_card=ReferralCard(
                decision="立即转诊",
                reasons=["高钾风险"],
                suggested_checks=["心电图"],
                handoff_notes=["多报告综合"],
            ),
        )

        analyze_mock = AsyncMock(return_value=result)
        with patch("app.main._analyze_with_selected_backend", new=analyze_mock):
            response = self.client.post(
                "/api/report/analyze-labs",
                json={
                    "patient_age": 63,
                    "symptoms": "乏力、心悸。",
                    "reports": [
                        {
                            "report_type": "cbc",
                            "source_image_name": "cbc.png",
                            "items": [
                                {"name": "WBC", "alias": "WBC", "value": "6.1", "confirmed": True},
                                {"name": "RBC", "alias": "RBC", "value": "4.2", "confirmed": True},
                                {"name": "HGB", "alias": "HGB", "value": "88", "confirmed": True},
                                {"name": "PLT", "alias": "PLT", "value": "210", "confirmed": True},
                            ],
                        },
                        {
                            "report_type": "chemistry_basic",
                            "source_image_name": "chem.png",
                            "items": [
                                {"name": "Cr", "alias": "Cr", "value": "128", "confirmed": True},
                                {"name": "K", "alias": "K", "value": "5.8", "confirmed": True},
                                {"name": "Na", "alias": "Na", "value": "134", "confirmed": True},
                                {"name": "GLU", "alias": "GLU", "value": "13.6", "confirmed": True},
                            ],
                        },
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["structured_reports"]), 2)
        passed_alerts = analyze_mock.call_args.kwargs["alerts"]
        self.assertTrue(
            any(alert.title == "联合风险：高钾合并肾功能异常" for alert in passed_alerts)
        )


if __name__ == "__main__":
    unittest.main()
