import unittest

from app.cbc_ocr import _detect_report_type, _extract_items, _group_rows


class CBCOCRParsingTest(unittest.TestCase):
    def test_extracts_required_items_from_fixed_layout_lines(self):
        lines = [
            {"text": "WBC 12.4 10^9/L 3.5-9.5 H", "confidence": 0.98},
            {"text": "RBC 4.35 10^12/L 3.8-5.1", "confidence": 0.96},
            {"text": "HGB 98 g/L 115-150 L", "confidence": 0.95},
            {"text": "PLT 210 10^9/L 125-350", "confidence": 0.97},
        ]

        items = _extract_items(lines, "cbc")

        self.assertEqual([item.name for item in items], ["WBC", "RBC", "HGB", "PLT"])
        self.assertEqual(items[0].flag, "high")
        self.assertEqual(items[2].flag, "low")
        self.assertEqual(items[1].reference_range, "3.8-5.1")

    def test_groups_fragmented_ocr_boxes_back_into_rows(self):
        rows = _group_rows(
            [
                {"text": "WBC", "confidence": 0.99, "x": 0.08, "y": 0.80, "width": 0.05, "height": 0.02},
                {"text": "白细胞", "confidence": 0.97, "x": 0.22, "y": 0.80, "width": 0.08, "height": 0.02},
                {"text": "12.4", "confidence": 0.98, "x": 0.48, "y": 0.80, "width": 0.06, "height": 0.02},
                {"text": "10^9/L", "confidence": 0.97, "x": 0.63, "y": 0.80, "width": 0.08, "height": 0.02},
                {"text": "3.5-9.5", "confidence": 0.95, "x": 0.78, "y": 0.80, "width": 0.08, "height": 0.02},
                {"text": "H", "confidence": 0.96, "x": 0.92, "y": 0.80, "width": 0.02, "height": 0.02},
                {"text": "RBC", "confidence": 0.99, "x": 0.08, "y": 0.72, "width": 0.05, "height": 0.02},
                {"text": "4.12", "confidence": 0.98, "x": 0.48, "y": 0.72, "width": 0.06, "height": 0.02},
            ]
        )

        self.assertEqual(rows[0]["text"], "WBC 白细胞 12.4 10^9/L 3.5-9.5 H")
        self.assertEqual(rows[1]["text"], "RBC 4.12")

    def test_extracts_items_from_grouped_fixed_layout_rows(self):
        rows = [
            {"text": "WBC 白细胞 12.4 10^9/L 3.5-9.5 H", "confidence": 0.97},
            {"text": "RBC 红细胞 4.12 10^12/L 3.8-5.1", "confidence": 0.97},
            {"text": "HGB 血红蛋白 88 g/L 115-150 L", "confidence": 0.97},
            {"text": "PLT 血小板 268 10^9/L 125-350", "confidence": 0.97},
        ]

        items = _extract_items(rows, "cbc")

        self.assertEqual(items[0].unit, "10^9/L")
        self.assertEqual(items[2].flag, "low")
        self.assertEqual(items[3].value, "268")

    def test_detects_chemistry_report_type(self):
        rows = [
            {"text": "Cr 肌酐 128 umol/L 57-111 H", "confidence": 0.97},
            {"text": "K 钾 5.8 mmol/L 3.5-5.3 H", "confidence": 0.97},
        ]

        self.assertEqual(_detect_report_type(rows), "chemistry_basic")

    def test_extracts_basic_chemistry_items(self):
        rows = [
            {"text": "Cr 肌酐 128 umol/L 57-111 H", "confidence": 0.97},
            {"text": "K 钾 5.8 mmol/L 3.5-5.3 H", "confidence": 0.97},
            {"text": "Na 钠 134 mmol/L 137-147 L", "confidence": 0.97},
            {"text": "GLU 葡萄糖 13.6 mmol/L 3.9-6.1 H", "confidence": 0.97},
        ]

        items = _extract_items(rows, "chemistry_basic")

        self.assertEqual([item.name for item in items], ["Cr", "K", "Na", "GLU"])
        self.assertEqual(items[0].unit.lower(), "umol/l")
        self.assertEqual(items[2].flag, "low")


if __name__ == "__main__":
    unittest.main()
