"""
PDF Generator Service using ReportLab with full Vietnamese Unicode support (S7-05).
Generates branded, professional PDF documents for quotes and contracts.
"""

import os
import io
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm, mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.utils.number_to_words import number_to_vietnamese_words


# Đăng ký font tiếng Việt TrueType
FONT_NAME = "Arial"
FONT_NAME_BOLD = "Arial-Bold"
_font_registered = False


def _ensure_vietnamese_fonts():
    global _font_registered, FONT_NAME, FONT_NAME_BOLD
    if _font_registered:
        return

    # Thử đăng ký Arial tiếng Việt trên Windows
    windows_fonts_dir = r"C:\Windows\Fonts"
    arial_path = os.path.join(windows_fonts_dir, "arial.ttf")
    arial_bd_path = os.path.join(windows_fonts_dir, "arialbd.ttf")

    if os.path.exists(arial_path):
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, arial_path))
            if os.path.exists(arial_bd_path):
                pdfmetrics.registerFont(TTFont(FONT_NAME_BOLD, arial_bd_path))
            else:
                pdfmetrics.registerFont(TTFont(FONT_NAME_BOLD, arial_path))
            _font_registered = True
            return
        except Exception:
            pass

    # Fallback mặc định
    FONT_NAME = "Helvetica"
    FONT_NAME_BOLD = "Helvetica-Bold"
    _font_registered = True


def _parse_color(hex_str: Optional[str], default_color=colors.HexColor("#1E40AF")):
    """Chuyển đổi mã màu hex thành ReportLab color."""
    if not hex_str:
        return default_color
    try:
        clean_hex = hex_str.strip()
        if not clean_hex.startswith("#"):
            clean_hex = "#" + clean_hex
        return colors.HexColor(clean_hex)
    except Exception:
        return default_color


def generate_quote_pdf(quote: Dict[str, Any], template: Dict[str, Any]) -> bytes:
    """
    Xuất báo giá ra file PDF theo mẫu công ty (S7-05 AC 1 & AC 2):
    - Logo và thông tin công ty từ cấu hình template
    - Bảng sản phẩm đầy đủ số lượng, đơn giá, chiết khấu, VAT, thành tiền
    - Tổng tiền bằng số và tự động chuyển sang bằng chữ tiếng Việt
    - Điều khoản thanh toán, giao hàng và ô chữ ký đại diện
    """
    _ensure_vietnamese_fonts()
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    primary_color = _parse_color(template.get("primary_color"), colors.HexColor("#1E40AF"))
    secondary_color = _parse_color(template.get("secondary_color"), colors.HexColor("#F3F4F6"))

    styles = getSampleStyleSheet()

    company_title_style = ParagraphStyle(
        "CompanyTitle",
        fontName=FONT_NAME_BOLD,
        fontSize=12,
        leading=16,
        textColor=primary_color,
    )
    company_info_style = ParagraphStyle(
        "CompanyInfo",
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#374151"),
    )
    doc_title_style = ParagraphStyle(
        "DocTitle",
        fontName=FONT_NAME_BOLD,
        fontSize=16,
        leading=22,
        alignment=1,  # Center
        textColor=primary_color,
    )
    doc_sub_style = ParagraphStyle(
        "DocSub",
        fontName=FONT_NAME,
        fontSize=9.5,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#4B5563"),
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        fontName=FONT_NAME_BOLD,
        fontSize=10,
        leading=14,
        textColor=primary_color,
    )
    normal_style = ParagraphStyle(
        "NormalText",
        fontName=FONT_NAME,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1F2937"),
    )
    bold_style = ParagraphStyle(
        "BoldText",
        fontName=FONT_NAME_BOLD,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1F2937"),
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        fontName=FONT_NAME_BOLD,
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=colors.white,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1F2937"),
    )
    table_cell_right = ParagraphStyle(
        "TableCellRight",
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=11,
        alignment=2,  # Right
        textColor=colors.HexColor("#1F2937"),
    )
    words_style = ParagraphStyle(
        "WordsText",
        fontName=FONT_NAME_BOLD,
        fontSize=9.5,
        leading=14,
        textColor=primary_color,
    )

    story = []

    # 1. Header: Thông tin công ty & Logo (AC 1 & AC 2)
    c_name = template.get("company_name") or "CÔNG TY CỔ PHẦN CÔNG NGHỆ CRM VIỆT NAM"
    c_mst = template.get("company_tax_code") or "0109888999"
    c_addr = template.get("company_address") or "Hà Nội"
    c_phone = template.get("company_phone") or "1900 6868"
    c_email = template.get("company_email") or "sales@crmvietnam.vn"
    c_web = template.get("company_website") or "https://crmvietnam.vn"

    header_text = f"""<b>{c_name}</b><br/>
Địa chỉ: {c_addr}<br/>
Mã số thuế: {c_mst} | Điện thoại: {c_phone}<br/>
Email: {c_email} | Website: {c_web}"""

    # Logo placeholder nếu không có ảnh
    logo_text = f"<b>{c_name[:15].upper()}</b><br/><font size=7 color='#6B7280'>Enterprise CRM</font>"

    header_table_data = [
        [
            Paragraph(logo_text, company_title_style),
            Paragraph(header_text, company_info_style),
        ]
    ]
    header_table = Table(header_table_data, colWidths=[4.5 * cm, 13.5 * cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(header_table)

    # Đường kẻ phân cách
    divider = Table([['']], colWidths=[18 * cm], rowHeights=[2])
    divider.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), primary_color),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(divider)
    story.append(Spacer(1, 12))

    # 2. Tiêu đề văn bản & Số hiệu
    header_title = template.get("header_title") or "BÁO GIÁ THƯƠNG MẠI"
    story.append(Paragraph(header_title, doc_title_style))
    story.append(Spacer(1, 4))
    
    quote_num = quote.get("quote_number") or f"BG-{quote.get('id', 1)}"
    created_date = quote.get("created_at", "")[:10] or datetime.now().strftime("%Y-%m-%d")
    story.append(Paragraph(f"Số báo giá: <b>{quote_num}</b>  |  Ngày lập: {created_date}", doc_sub_style))
    story.append(Spacer(1, 14))

    # 3. Thông tin Khách hàng & Cơ hội
    cust_name = quote.get("customer_name") or f"Khách hàng #{quote.get('customer_id', '')}"
    valid_until = quote.get("valid_until", "")[:10] if quote.get("valid_until") else "30 ngày kể từ ngày lập"
    opp_title = quote.get("opportunity_title") or "Hợp đồng dịch vụ doanh nghiệp"

    customer_box_data = [
        [
            Paragraph(f"<b>Kính gửi:</b> {cust_name}", normal_style),
            Paragraph(f"<b>Hạn hiệu lực:</b> {valid_until}", normal_style),
        ],
        [
            Paragraph(f"<b>Dự án / Cơ hội:</b> {opp_title}", normal_style),
            Paragraph(f"<b>Trạng thái:</b> {quote.get('status', 'DRAFT')}", normal_style),
        ]
    ]
    customer_table = Table(customer_box_data, colWidths=[11 * cm, 7 * cm])
    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(customer_table)
    story.append(Spacer(1, 12))

    # 4. Bảng dòng sản phẩm (AC 1)
    items = quote.get("items", [])
    table_data = [
        [
            Paragraph("STT", table_header_style),
            Paragraph("Mã SP", table_header_style),
            Paragraph("Tên hàng hóa / Dịch vụ", table_header_style),
            Paragraph("ĐVT", table_header_style),
            Paragraph("SL", table_header_style),
            Paragraph("Đơn giá (VNĐ)", table_header_style),
            Paragraph("CK (%)", table_header_style),
            Paragraph("Thành tiền (VNĐ)", table_header_style),
        ]
    ]

    for idx, it in enumerate(items):
        stt = str(idx + 1)
        p_code = it.get("product_code") or f"SP-{it.get('product_id', idx+1)}"
        p_name = it.get("product_name", "Sản phẩm")
        unit = it.get("unit") or "Gói"
        qty = str(it.get("quantity") or 1)
        price = f"{float(it.get('unit_price') or 0.0):,.0f}"
        disc = f"{float(it.get('discount_value') or 0.0):.1f}%" if str(it.get("discount_type", "")).upper() == "PERCENT" else f"{float(it.get('discount_value') or 0.0):,.0f}"
        total = f"{float(it.get('line_total') or 0.0):,.0f}"

        table_data.append([
            Paragraph(stt, table_cell_style),
            Paragraph(p_code, table_cell_style),
            Paragraph(p_name, table_cell_style),
            Paragraph(unit, table_cell_style),
            Paragraph(qty, table_cell_right),
            Paragraph(price, table_cell_right),
            Paragraph(disc, table_cell_right),
            Paragraph(total, table_cell_right),
        ])

    # Thêm fallback nếu items rỗng (trường hợp quote đơn lẻ cũ)
    if not items:
        price = f"{float(quote.get('amount') or 0.0):,.0f}"
        table_data.append([
            Paragraph("1", table_cell_style),
            Paragraph("DV-01", table_cell_style),
            Paragraph(quote.get("title", "Gói giải pháp phần mềm"), table_cell_style),
            Paragraph("Gói", table_cell_style),
            Paragraph("1", table_cell_right),
            Paragraph(price, table_cell_right),
            Paragraph("0%", table_cell_right),
            Paragraph(price, table_cell_right),
        ])

    items_table = Table(
        table_data,
        colWidths=[1.0 * cm, 2.2 * cm, 5.5 * cm, 1.3 * cm, 1.2 * cm, 2.6 * cm, 1.6 * cm, 2.6 * cm]
    )
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 8))

    # 5. Tổng kết tài chính (AC 1)
    subtotal = float(quote.get("subtotal") or quote.get("amount") or 0.0)
    disc_total = float(quote.get("total_discount_amount") or 0.0)
    vat_amt = float(quote.get("vat_amount") or 0.0)
    grand_total = float(quote.get("grand_total") or quote.get("amount") or 0.0)

    summary_data = [
        [Paragraph("<b>Cộng tiền hàng (Tạm tính):</b>", table_cell_right), Paragraph(f"<b>{subtotal:,.0f} VNĐ</b>", table_cell_right)],
        [Paragraph("Chiết khấu thương mại:", table_cell_right), Paragraph(f"- {disc_total:,.0f} VNĐ", table_cell_right)],
        [Paragraph("Tiền thuế GTGT (VAT):", table_cell_right), Paragraph(f"{vat_amt:,.0f} VNĐ", table_cell_right)],
        [Paragraph("<font size=10 color='#1E40AF'><b>TỔNG CỘNG THANH TOÁN:</b></font>", table_cell_right), Paragraph(f"<font size=10 color='#1E40AF'><b>{grand_total:,.0f} VNĐ</b></font>", table_cell_right)],
    ]
    summary_table = Table(summary_data, colWidths=[12.8 * cm, 5.2 * cm])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, -1), (-1, -1), 1.0, primary_color),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 6))

    # 6. Tổng tiền bằng chữ tiếng Việt (AC 1)
    amount_in_words = number_to_vietnamese_words(grand_total)
    story.append(Paragraph(f"<b>Số tiền viết bằng chữ:</b> <i>{amount_in_words}.</i>", words_style))
    story.append(Spacer(1, 10))

    # 7. Điều khoản thanh toán & Thông tin tài khoản ngân hàng (AC 1 & AC 2)
    bank_info = template.get("company_bank_info")
    pay_terms = quote.get("payment_terms") or template.get("terms_and_conditions") or "Thanh toán theo tiến độ thỏa thuận."
    del_terms = quote.get("delivery_terms") or ""

    terms_box_data = [
        [Paragraph(f"<b>1. Điều khoản thanh toán:</b> {pay_terms}", normal_style)],
    ]
    if del_terms:
        terms_box_data.append([Paragraph(f"<b>2. Điều khoản giao hàng / triển khai:</b> {del_terms}", normal_style)])
    if bank_info:
        terms_box_data.append([Paragraph(f"<b>3. Thông tin thanh toán:</b> {bank_info}", normal_style)])

    terms_table = Table(terms_box_data, colWidths=[18 * cm])
    terms_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(terms_table)
    story.append(Spacer(1, 16))

    # 8. Nhãn chữ ký hai bên (AC 1 & AC 2)
    sig_cust = template.get("signature_customer_label") or "ĐẠI DIỆN KHÁCH HÀNG"
    sig_comp = template.get("signature_company_label") or "ĐẠI DIỆN CÔNG TY BÁO GIÁ"

    sig_data = [
        [
            Paragraph(f"<b>{sig_cust}</b><br/><font size=7.5 color='#6B7280'>(Ký, ghi rõ họ tên và đóng dấu)</font>", ParagraphStyle('Sig1', fontName=FONT_NAME, fontSize=9, alignment=1)),
            Paragraph(f"<b>{sig_comp}</b><br/><font size=7.5 color='#6B7280'>(Ký, ghi rõ họ tên và đóng dấu)</font>", ParagraphStyle('Sig2', fontName=FONT_NAME, fontSize=9, alignment=1)),
        ],
        [
            Spacer(1, 35),
            Spacer(1, 35),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[9 * cm, 9 * cm])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(KeepTogether(sig_table))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def generate_contract_pdf(contract: Dict[str, Any], template: Dict[str, Any]) -> bytes:
    """
    Xuất hợp đồng ra file PDF theo mẫu công ty (S7-05 AC 1 & AC 2):
    - Đầy đủ thông tin pháp lý, các bên A và B, dòng sản phẩm, tổng tiền bằng số và bằng chữ
    """
    _ensure_vietnamese_fonts()
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    primary_color = _parse_color(template.get("primary_color"), colors.HexColor("#1E3A8A"))
    styles = getSampleStyleSheet()

    c_name = template.get("company_name") or "CÔNG TY CỔ PHẦN CÔNG NGHỆ CRM VIỆT NAM"
    c_mst = template.get("company_tax_code") or "0109888999"
    c_addr = template.get("company_address") or "Hà Nội"
    c_phone = template.get("company_phone") or "1900 6868"
    c_email = template.get("company_email") or "legal@crmvietnam.vn"
    c_bank = template.get("company_bank_info") or ""

    company_info_style = ParagraphStyle(
        "CompanyInfo",
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#374151"),
    )
    doc_title_style = ParagraphStyle(
        "DocTitle",
        fontName=FONT_NAME_BOLD,
        fontSize=15,
        leading=20,
        alignment=1,
        textColor=primary_color,
    )
    doc_sub_style = ParagraphStyle(
        "DocSub",
        fontName=FONT_NAME,
        fontSize=9.5,
        leading=14,
        alignment=1,
        textColor=colors.HexColor("#4B5563"),
    )
    normal_style = ParagraphStyle(
        "NormalText",
        fontName=FONT_NAME,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1F2937"),
    )
    bold_style = ParagraphStyle(
        "BoldText",
        fontName=FONT_NAME_BOLD,
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1F2937"),
    )
    table_header_style = ParagraphStyle(
        "TableHeader",
        fontName=FONT_NAME_BOLD,
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=colors.white,
    )
    table_cell_style = ParagraphStyle(
        "TableCell",
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1F2937"),
    )
    table_cell_right = ParagraphStyle(
        "TableCellRight",
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=11,
        alignment=2,
        textColor=colors.HexColor("#1F2937"),
    )
    words_style = ParagraphStyle(
        "WordsText",
        fontName=FONT_NAME_BOLD,
        fontSize=9.5,
        leading=14,
        textColor=primary_color,
    )

    story = []

    # 1. Quốc hiệu / Header
    story.append(Paragraph("<b>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</b>", ParagraphStyle('QH1', fontName=FONT_NAME_BOLD, fontSize=10, alignment=1)))
    story.append(Paragraph("Độc lập - Tự do - Hạnh phúc", ParagraphStyle('QH2', fontName=FONT_NAME, fontSize=9, alignment=1)))
    story.append(Spacer(1, 10))

    # 2. Tiêu đề Hợp đồng
    header_title = template.get("header_title") or contract.get("title") or "HỢP ĐỒNG KINH TẾ DỊCH VỤ"
    story.append(Paragraph(header_title.upper(), doc_title_style))
    story.append(Spacer(1, 3))
    
    c_num = contract.get("contract_number") or f"HD-{contract.get('id', 1)}"
    s_date = contract.get("signed_date", "")[:10] or datetime.now().strftime("%Y-%m-%d")
    story.append(Paragraph(f"Số: <b>{c_num}</b>  |  Ngày ký: {s_date}", doc_sub_style))
    story.append(Spacer(1, 12))

    # 3. Thông tin 2 bên A và B
    cust_name = contract.get("customer_name") or f"Khách hàng ID {contract.get('customer_id', '')}"
    parties_data = [
        [
            Paragraph(f"<b>BÊN A (BÊN MUA):</b> {cust_name}<br/>"
                      f"Đại diện: Giám đốc / Người đại diện pháp luật<br/>"
                      f"Địa chỉ: Theo thông tin đăng ký doanh nghiệp<br/>"
                      f"Hiệu lực HĐ: {contract.get('effective_date', '')[:10]} đến {contract.get('expiration_date', '')[:10]}", normal_style),
            Paragraph(f"<b>BÊN B (BÊN BÁN):</b> {c_name}<br/>"
                      f"Mã số thuế: {c_mst}<br/>"
                      f"Địa chỉ: {c_addr}<br/>"
                      f"Điện thoại: {c_phone}", normal_style)
        ]
    ]
    parties_table = Table(parties_data, colWidths=[9 * cm, 9 * cm])
    parties_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F9FAFB")),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 12))

    # 4. Bảng sản phẩm / phạm vi cung cấp (AC 1)
    story.append(Paragraph("<b>ĐIỀU 1: PHẠM VI HÀNG HÓA VÀ DỊCH VỤ CUNG CẤP</b>", ParagraphStyle('D1', fontName=FONT_NAME_BOLD, fontSize=9.5, textColor=primary_color)))
    story.append(Spacer(1, 4))

    items = contract.get("items", [])
    table_data = [
        [
            Paragraph("STT", table_header_style),
            Paragraph("Mã SP", table_header_style),
            Paragraph("Tên hàng hóa / Dịch vụ", table_header_style),
            Paragraph("ĐVT", table_header_style),
            Paragraph("SL", table_header_style),
            Paragraph("Đơn giá (VNĐ)", table_header_style),
            Paragraph("CK (%)", table_header_style),
            Paragraph("Thành tiền (VNĐ)", table_header_style),
        ]
    ]

    for idx, it in enumerate(items):
        stt = str(idx + 1)
        p_code = it.get("product_code") or f"SP-{it.get('product_id', idx+1)}"
        p_name = it.get("product_name", "Dịch vụ")
        unit = it.get("unit") or "Gói"
        qty = str(it.get("quantity") or 1)
        price = f"{float(it.get('unit_price') or 0.0):,.0f}"
        disc = f"{float(it.get('discount_value') or 0.0):.1f}%" if str(it.get("discount_type", "")).upper() == "PERCENT" else f"{float(it.get('discount_value') or 0.0):,.0f}"
        total = f"{float(it.get('line_total') or 0.0):,.0f}"

        table_data.append([
            Paragraph(stt, table_cell_style),
            Paragraph(p_code, table_cell_style),
            Paragraph(p_name, table_cell_style),
            Paragraph(unit, table_cell_style),
            Paragraph(qty, table_cell_right),
            Paragraph(price, table_cell_right),
            Paragraph(disc, table_cell_right),
            Paragraph(total, table_cell_right),
        ])

    items_table = Table(
        table_data,
        colWidths=[1.0 * cm, 2.2 * cm, 5.5 * cm, 1.3 * cm, 1.2 * cm, 2.6 * cm, 1.6 * cm, 2.6 * cm]
    )
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), primary_color),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 8))

    # 5. Giá trị hợp đồng & Chữ viết (AC 1)
    subtotal = float(contract.get("subtotal") or 0.0)
    disc_total = float(contract.get("total_discount_amount") or 0.0)
    vat_amt = float(contract.get("vat_amount") or 0.0)
    grand_total = float(contract.get("grand_total") or 0.0)

    summary_data = [
        [Paragraph("<b>Tổng giá trị trước thuế:</b>", table_cell_right), Paragraph(f"<b>{subtotal:,.0f} VNĐ</b>", table_cell_right)],
        [Paragraph("Chiết khấu thỏa thuận:", table_cell_right), Paragraph(f"- {disc_total:,.0f} VNĐ", table_cell_right)],
        [Paragraph("Tiền thuế GTGT (VAT):", table_cell_right), Paragraph(f"{vat_amt:,.0f} VNĐ", table_cell_right)],
        [Paragraph("<font size=10 color='#1E3A8A'><b>TỔNG GIÁ TRỊ HỢP ĐỒNG:</b></font>", table_cell_right), Paragraph(f"<font size=10 color='#1E3A8A'><b>{grand_total:,.0f} VNĐ</b></font>", table_cell_right)],
    ]
    summary_table = Table(summary_data, colWidths=[12.8 * cm, 5.2 * cm])
    summary_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, -1), (-1, -1), 1.0, primary_color),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 6))

    # Số tiền bằng chữ
    amount_in_words = number_to_vietnamese_words(grand_total)
    story.append(Paragraph(f"<b>Giá trị bằng chữ:</b> <i>{amount_in_words}.</i>", words_style))
    story.append(Spacer(1, 10))

    # 6. Điều khoản thanh toán
    pay_terms = contract.get("payment_terms") or "Theo tiến độ ký kết và bàn giao."
    del_terms = contract.get("delivery_terms") or "Trong vòng 15 ngày kể từ ngày ký."
    story.append(Paragraph(f"<b>ĐIỀU 2: ĐIỀU KHOẢN THANH TOÁN VÀ THỰC HIỆN</b><br/>"
                           f"1. Điều khoản thanh toán: {pay_terms}<br/>"
                           f"2. Bàn giao và nghiệm thu: {del_terms}<br/>"
                           f"3. Tài khoản thụ hưởng: {c_bank}", normal_style))
    story.append(Spacer(1, 16))

    # 7. Ô chữ ký 2 bên (AC 1 & AC 2)
    sig_cust = template.get("signature_customer_label") or "ĐẠI DIỆN BÊN A (KHÁCH HÀNG)"
    sig_comp = template.get("signature_company_label") or "ĐẠI DIỆN BÊN B (NHÀ CUNG CẤP)"

    sig_data = [
        [
            Paragraph(f"<b>{sig_cust}</b><br/><font size=7.5 color='#6B7280'>(Ký, ghi rõ họ tên và đóng dấu)</font>", ParagraphStyle('Sig1', fontName=FONT_NAME, fontSize=9, alignment=1)),
            Paragraph(f"<b>{sig_comp}</b><br/><font size=7.5 color='#6B7280'>(Ký, ghi rõ họ tên và đóng dấu)</font>", ParagraphStyle('Sig2', fontName=FONT_NAME, fontSize=9, alignment=1)),
        ],
        [
            Spacer(1, 40),
            Spacer(1, 40),
        ]
    ]
    sig_table = Table(sig_data, colWidths=[9 * cm, 9 * cm])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(KeepTogether(sig_table))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
