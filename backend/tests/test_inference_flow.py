import unittest

from app.main import _choose_backend, _fallback_reason
from app.models import InferenceMeta


class InferenceFlowTest(unittest.TestCase):
    def test_uses_medgemma_when_ready(self):
        self.assertEqual(_choose_backend("ready", True), "medgemma")

    def test_falls_back_to_ollama_when_medgemma_not_ready(self):
        self.assertEqual(_choose_backend("loading", True), "ollama")

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
