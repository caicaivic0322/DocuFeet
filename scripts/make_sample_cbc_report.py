from __future__ import annotations

from pathlib import Path


def _load_dependencies():
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception as exc:  # pragma: no cover - script helper
        raise SystemExit(
            "需要 Pillow 才能生成血常规样例图。可使用 backend/.venv/bin/python 运行本脚本。"
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


def make_sample_cbc_report(path: Path) -> None:
    Image, ImageDraw, ImageFont = _load_dependencies()
    width, height = 1480, 1080
    image = Image.new("RGB", (width, height), "#f4f6f8")
    draw = ImageDraw.Draw(image)

    title_font = _load_font(ImageFont, 48)
    subtitle_font = _load_font(ImageFont, 24)
    header_font = _load_font(ImageFont, 28)
    cell_font = _load_font(ImageFont, 26)
    small_font = _load_font(ImageFont, 22)

    draw.rounded_rectangle((44, 36, width - 44, height - 36), radius=28, fill="white", outline="#d6dce2")
    draw.text((88, 78), "乡镇医院检验报告单", fill="#1e2933", font=title_font)
    draw.text((90, 142), "项目：血常规（CBC）    样本：静脉血    状态：已审核", fill="#55626d", font=subtitle_font)
    draw.text((90, 182), "姓名：张某某    性别：女    年龄：63 岁    科室：内科门诊", fill="#55626d", font=subtitle_font)
    draw.text((90, 222), "报告时间：2026-04-21 09:45    申请医师：李医生", fill="#55626d", font=subtitle_font)

    table_left = 90
    table_top = 300
    table_width = width - 180
    row_height = 92
    columns = [0, 200, 640, 880, 1120, table_width]
    headers = ["项目", "中文名", "结果", "单位", "参考范围", "标记"]

    draw.rounded_rectangle(
        (table_left, table_top, table_left + table_width, table_top + row_height),
        radius=18,
        fill="#edf3ef",
        outline="#d6dce2",
    )
    for index, header in enumerate(headers):
        draw.text((table_left + columns[index] + 18, table_top + 28), header, fill="#244638", font=header_font)

    rows = [
        ("WBC", "白细胞", "12.4", "10^9/L", "3.5-9.5", "H"),
        ("RBC", "红细胞", "4.12", "10^12/L", "3.8-5.1", ""),
        ("HGB", "血红蛋白", "88", "g/L", "115-150", "L"),
        ("PLT", "血小板", "268", "10^9/L", "125-350", ""),
        ("NEUT%", "中性粒细胞%", "81.5", "%", "40-75", "H"),
        ("CRP", "C 反应蛋白", "38.6", "mg/L", "0-8", "H"),
    ]

    for row_index, row in enumerate(rows, start=1):
        y1 = table_top + row_height * row_index
        y2 = y1 + row_height
        fill = "#fff4f2" if row[5] == "H" else "#fff8ee" if row[5] == "L" else "white"
        draw.rectangle((table_left, y1, table_left + table_width, y2), fill=fill, outline="#d6dce2")

        for column in columns[1:-1]:
            draw.line((table_left + column, y1, table_left + column, y2), fill="#d6dce2", width=2)

        draw.text((table_left + 18, y1 + 30), row[0], fill="#1e2933", font=cell_font)
        draw.text((table_left + columns[1] + 18, y1 + 30), row[1], fill="#43505a", font=cell_font)
        draw.text((table_left + columns[2] + 18, y1 + 30), row[2], fill="#1e2933", font=cell_font)
        draw.text((table_left + columns[3] + 18, y1 + 30), row[3], fill="#1e2933", font=cell_font)
        draw.text((table_left + columns[4] + 18, y1 + 30), row[4], fill="#1e2933", font=cell_font)
        draw.text((table_left + columns[5] + 28, y1 + 30), row[5] or "-", fill="#9a3b35", font=cell_font)

    footer_top = table_top + row_height * (len(rows) + 1) + 36
    draw.rounded_rectangle((90, footer_top, width - 90, footer_top + 180), radius=20, fill="#f7faf8", outline="#d6dce2")
    draw.text((118, footer_top + 26), "备注：", fill="#244638", font=header_font)
    draw.text(
        (118, footer_top + 78),
        "患者主诉乏力、头晕 3 天。建议结合症状与血红蛋白下降情况进一步评估。",
        fill="#55626d",
        font=small_font,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "docs" / "sample-cbc-report.png"
    make_sample_cbc_report(out)
    print(out)
