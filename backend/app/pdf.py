from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from .storage import read_bytes

pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))


def build_report_pdf(patient, session, summary, conclusion, signature_path):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm, topMargin=16 * mm)
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "STSong-Light"

    rows = [
        ["病历号", patient.medical_no, "性别", patient.gender, "年龄", str(patient.age)],
        ["会话编号", session.id, "开始时间", session.start_time.strftime("%Y-%m-%d %H:%M"), "状态", session.status],
        ["主要部位", summary.most_frequent_location if summary else "-", "总帧数", str(summary.total_frames if summary else 0), "病灶帧", str(summary.lesion_frames_count if summary else 0)],
    ]
    table = Table(rows, colWidths=[22 * mm, 40 * mm, 18 * mm, 32 * mm, 20 * mm, 30 * mm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef6ff")),
                ("FONTNAME", (0, 0), (-1, -1), "STSong-Light"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    story = [
        Paragraph("Bronchoscopy-AI 智能辅助诊断报告", styles["Title"]),
        Spacer(1, 8 * mm),
        table,
        Spacer(1, 8 * mm),
        Paragraph("AI 分析摘要", styles["Heading2"]),
        Paragraph(_summary_text(summary), styles["BodyText"]),
        Spacer(1, 6 * mm),
        Paragraph("医生诊断结论", styles["Heading2"]),
        Paragraph(conclusion.replace("\n", "<br/>"), styles["BodyText"]),
        Spacer(1, 8 * mm),
        Paragraph(f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["BodyText"]),
    ]

    try:
        signature = Image(BytesIO(read_bytes(signature_path)), width=45 * mm, height=18 * mm)
        story.extend([Spacer(1, 8 * mm), Paragraph("医生签名", styles["Heading2"]), signature])
    except Exception:
        story.extend([Spacer(1, 8 * mm), Paragraph("医生签名：已提交", styles["BodyText"])])

    doc.build(story)
    return buffer.getvalue()


def _summary_text(summary):
    if not summary:
        return "暂无 AI 摘要。"
    abnormalities = ", ".join(f"{k}: {v}" for k, v in (summary.abnormalities_json or {}).items())
    return (
        f"最常见部位：{summary.most_frequent_location or '-'}；"
        f"总帧数：{summary.total_frames}；病灶帧数：{summary.lesion_frames_count}；"
        f"异常统计：{abnormalities or '-'}。"
    )
