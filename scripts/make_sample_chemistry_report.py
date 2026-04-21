from __future__ import annotations

from pathlib import Path


def _load_dependencies():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # pragma: no cover
        raise SystemExit(
            "需要 Pillow 才能生成生化样例图。可使用 backend/.venv/bin/python 运行本脚本。"
        ) from exc
    return Image, ImageDraw, ImageFont


def _load_font(ImageFont, size: int):
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def make_sample_chemistry_report(path: Path) -> None:
    Image, ImageDraw, ImageFont = _load_dependencies()
    width, height = 1500, 1120
    image = Image.new("RGB", (width, height), "#f4f6f8")
    draw = ImageDraw.Draw(image)

    title_font = _load_font(ImageFont, 48)
    subtitle_font = _load_font(ImageFont, 24)
    header_font = _load_font(ImageFont, 28)
    cell_font = _load_font(ImageFont, 26)
    small_font = _load_font(ImageFont, 22)

    draw.rounded_rectangle((44, 36, width - 44, height - 36), radius=28, fill="white", outline="#d6dce2")
    draw.text((88, 78), "乡镇医院生化检验报告单", fill="#1e2933", font=title_font)
    draw.text((90, 142), "项目：生化基础项    样本：静脉血    状态：已审核", fill="#55626d", font=subtitle_font)
    draw.text((90, 182), "姓名：王某某    性别：男    年龄：58 岁    科室：全科门诊", fill="#55626d", font=subtitle_font)
    draw.text((90, 222), "报告时间：2026-04-21 10:20    申请医师：周医生", fill="#55626d", font=subtitle_font)

    table_left = 90
    table_top = 300
    table_width = width - 180
    row_height = 88
    columns = [0, 200, 700, 930, 1160, table_width]
    headers = ["项目", "中文名", "结果", "单位", "参考范围", "标记"]

    draw.rounded_rectangle((table_left, table_top, table_left + table_width, table_top + row_height), radius=18, fill="#edf0f8", outline="#d6dce2")
    for index, header in enumerate(headers):
        draw.text((table_left + columns[index] + 18, table_top + 28), header, fill="#31446d", font=header_font)

    rows = [
        ("Cr", "肌酐", "128", "umol/L", "57-111", "H"),
        ("BUN", "尿素氮", "8.4", "mmol/L", "3.1-8.0", "H"),
        ("eGFR", "估算肾小球滤过率", "62", "mL/min/1.73m2", "90-120", "L"),
        ("K", "钾", "5.8", "mmol/L", "3.5-5.3", "H"),
        ("Na", "钠", "134", "mmol/L", "137-147", "L"),
        ("Cl", "氯", "97", "mmol/L", "99-110", "L"),
        ("GLU", "葡萄糖", "13.6", "mmol/L", "3.9-6.1", "H"),
        ("ALT", "谷丙转氨酶", "48", "U/L", "9-50", ""),
        ("AST", "谷草转氨酶", "42", "U/L", "15-40", "H"),
        ("ALB", "白蛋白", "34", "g/L", "35-52", "L"),
    ]

    for row_index, row in enumerate(rows, start=1):
        y1 = table_top + row_height * row_index
        y2 = y1 + row_height
        fill = "#fff4f2" if row[5] == "H" else "#fff8ee" if row[5] == "L" else "white"
        draw.rectangle((table_left, y1, table_left + table_width, y2), fill=fill, outline="#d6dce2")
        for column in columns[1:-1]:
            draw.line((table_left + column, y1, table_left + column, y2), fill="#d6dce2", width=2)

        draw.text((table_left + 18, y1 + 28), row[0], fill="#1e2933", font=cell_font)
        draw.text((table_left + columns[1] + 18, y1 + 28), row[1], fill="#43505a", font=cell_font)
        draw.text((table_left + columns[2] + 18, y1 + 28), row[2], fill="#1e2933", font=cell_font)
        draw.text((table_left + columns[3] + 18, y1 + 28), row[3], fill="#1e2933", font=cell_font)
        draw.text((table_left + columns[4] + 18, y1 + 28), row[4], fill="#1e2933", font=cell_font)
        draw.text((table_left + columns[5] + 28, y1 + 28), row[5] or "-", fill="#9a3b35", font=cell_font)

    footer_top = table_top + row_height * (len(rows) + 1) + 32
    draw.rounded_rectangle((90, footer_top, width - 90, footer_top + 172), radius=20, fill="#f7faf8", outline="#d6dce2")
    draw.text((118, footer_top + 24), "备注：", fill="#31446d", font=header_font)
    draw.text(
        (118, footer_top + 76),
        "患者口渴、乏力，近期饮水不足。建议结合血糖升高与电解质异常进一步评估。",
        fill="#55626d",
        font=small_font,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "docs" / "sample-chemistry-report.png"
    make_sample_chemistry_report(out)
    print(out)
