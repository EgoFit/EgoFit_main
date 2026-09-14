from __future__ import annotations

import html
from io import BytesIO
import math
from pathlib import Path
import re
from urllib.parse import urljoin, urlparse
import zipfile

from django.conf import settings


def build_program_pdf(program, request=None) -> bytes:
    """Render a program as a Persian-capable PDF when ReportLab is available."""
    link_base_url = _pdf_link_base_url(request)
    try:
        return _build_reportlab_pdf(program, link_base_url=link_base_url)
    except ImportError:
        return _build_fallback_pdf(program, link_base_url=link_base_url)


def _pdf_link_base_url(request=None) -> str:
    if request is not None:
        try:
            return request.build_absolute_uri("/")
        except Exception:
            pass

    configured_base_url = (
        getattr(settings, "EGOFIT_PUBLIC_BASE_URL", "")
        or getattr(settings, "PUBLIC_BASE_URL", "")
    )
    return str(configured_base_url or "").rstrip("/") + "/" if configured_base_url else ""


def _pdf_movement_media_url(movement, link_base_url="") -> str:
    media = next(iter(_movement_video_files(movement)), None)
    if media is None:
        media = getattr(movement, "media", None)
    media_name = getattr(media, "name", "") if media else ""
    if not media_name:
        return ""
    if str(media_name).startswith(("http://", "https://")):
        return str(media_name)

    media_url = ""
    try:
        storage = getattr(media, "storage", None)
        if storage is not None:
            media_url = storage.url(media_name)
    except Exception:
        pass
    if not media_url:
        try:
            media_url = media.url
        except Exception:
            return ""

    media_url = str(media_url or "")
    parsed_url = urlparse(media_url)
    if parsed_url.scheme:
        return media_url if parsed_url.scheme in {"http", "https"} else ""
    if media_url.startswith("//"):
        return urljoin(link_base_url, media_url) if link_base_url else ""
    return urljoin(link_base_url, media_url.lstrip("/")) if link_base_url else media_url


def _movement_video_files(movement):
    try:
        video_files = list(movement.video_files)
    except Exception:
        video_files = []
    if video_files:
        return video_files
    return [
        video
        for field_name in ("video_1", "video_2", "video_3")
        if (video := getattr(movement, field_name, None))
    ]


def _build_reportlab_pdf(program, *, link_base_url="") -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Paragraph, Table, TableStyle

    font_name = _register_farsi_font()
    reshape_text = _get_rtl_text_transformer()

    output = BytesIO()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "SarbargProgramTitle",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=10.5,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.black,
    )
    header_style = ParagraphStyle(
        "SarbargTableHeader",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=8.2,
        leading=9.5,
        alignment=TA_CENTER,
        textColor=colors.black,
    )
    body_style = ParagraphStyle(
        "SarbargTableBody",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=7.4,
        leading=8.6,
        alignment=TA_CENTER,
        textColor=colors.black,
    )
    note_heading_style = ParagraphStyle(
        "SarbargNoteHeading",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=9.5,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.red,
    )
    info_style = ParagraphStyle(
        "SarbargInfo",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=8.5,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.black,
    )

    def paragraph(value, style=body_style, *, href=""):
        transformed = reshape_text(str(value or ""))
        content = html.escape(transformed).replace("\n", "<br/>")
        if href:
            escaped_href = html.escape(href, quote=True)
            content = (
                f'<link href="{escaped_href}">'
                f'<u><font color="#0563C1">{content}</font></u>'
                "</link>"
            )
        return Paragraph(content, style)

    def movement_paragraph(movement, style=body_style):
        return paragraph(
            movement.name,
            style,
            href=_pdf_movement_media_url(movement, link_base_url),
        )

    page_width, page_height = letter
    content_x = 0.5 * inch
    content_width = 7.48 * inch
    table_widths = [2.754 * inch, 0.986 * inch, 0.589 * inch, 0.986 * inch, 2.165 * inch]
    background = _pdf_background_reader(ImageReader)
    document = canvas.Canvas(output, pagesize=letter)
    document.setTitle(str(program.title))
    document.setAuthor("EgoFit")

    days = list(program.days.all())
    # Sarbarg has six workbook slots, with two slots on each schedule page.
    schedule_page_count = max(3, math.ceil(max(1, len(days)) / 2))
    day_slots = days + [None] * (schedule_page_count * 2 - len(days))

    for page_index in range(schedule_page_count):
        _draw_pdf_background(document, background, page_width, page_height)
        top = page_height - 2.18 * inch
        for slot_index in range(2):
            day_index = page_index * 2 + slot_index
            table = _build_sarbarg_day_table(
                day_slots[day_index],
                day_index + 1,
                paragraph,
                title_style,
                header_style,
                table_widths,
                colors,
                movement_paragraph=movement_paragraph,
            )
            _, table_height = table.wrapOn(document, content_width, page_height)
            table.drawOn(document, content_x, top - table_height)
            top -= table_height + 0.16 * inch
        document.showPage()

    _draw_pdf_background(document, background, page_width, page_height)
    _draw_sarbarg_summary_page(
        document=document,
        program=program,
        paragraph=paragraph,
        info_style=info_style,
        note_heading_style=note_heading_style,
        content_x=content_x,
        content_width=content_width,
        page_height=page_height,
        colors=colors,
        link_base_url=link_base_url,
    )
    document.showPage()
    document.save()
    return output.getvalue()


def _build_sarbarg_day_table(
    day,
    number,
    paragraph,
    title_style,
    header_style,
    table_widths,
    colors,
    movement_paragraph=None,
):
    from reportlab.platypus import Table, TableStyle

    movement_paragraph = movement_paragraph or (lambda movement: paragraph(movement.name))
    title = f"برنامه {_persian_number(number)}"
    if day is not None and day.name:
        title = f"{title} — {day.name}"

    rows = [[paragraph(title, title_style), "", "", "", ""], [
        paragraph("توضیحات", header_style),
        paragraph("استراحت (ثانیه)", header_style),
        paragraph("ست", header_style),
        paragraph("تکرار", header_style),
        paragraph("نام حرکت", header_style),
    ]]

    movement_rows = []
    if day is not None:
        for item in day.items.all():
            movement_rows.append((item.exercise, item.sets, item.reps, item.rest, item.note))
            if item.superset_exercise_id:
                movement_rows.append(
                    (
                        item.superset_exercise,
                        item.superset_sets or item.sets,
                        item.superset_reps or item.reps,
                        item.superset_rest or item.rest,
                        item.note,
                    )
                )
            if item.third_exercise_id:
                movement_rows.append(
                    (
                        item.third_exercise,
                        item.third_sets or item.sets,
                        item.third_reps or item.reps,
                        item.third_rest or item.rest,
                        item.note,
                    )
                )

    for movement, sets, reps, rest, note in movement_rows:
        rows.append(
            [
                paragraph(note or "\u00a0"),
                paragraph(rest or "—"),
                paragraph(sets or "—"),
                paragraph(reps or "—"),
                movement_paragraph(movement),
            ]
        )

    # Keep the characteristic writing space from the reference document.
    for _ in range(max(0, 10 - len(movement_rows))):
        rows.append([paragraph("\u00a0")] * 5)

    table = Table(
        rows,
        colWidths=table_widths,
        rowHeights=[19, 23] + [17] * (len(rows) - 2),
    )
    table.setStyle(
        TableStyle(
            [
                ("SPAN", (0, 0), (-1, 0)),
                ("GRID", (0, 0), (-1, -1), 0.55, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]
        )
    )
    return table


def _draw_sarbarg_summary_page(
    *,
    document,
    program,
    paragraph,
    info_style,
    note_heading_style,
    content_x,
    content_width,
    page_height,
    colors,
    link_base_url="",
):
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, Table, TableStyle

    corrective_by_phase = {"warmup": [], "cooldown": []}
    for item in program.corrective_items.all():
        corrective_by_phase.setdefault(item.phase, []).append(item)

    def corrective_paragraph(phase):
        items = corrective_by_phase.get(phase, [])
        if not items:
            return paragraph("—", info_style)

        lines = []
        reshape_text = _get_rtl_text_transformer()
        for item in items:
            name = html.escape(reshape_text(item.corrective_exercise.name))
            href = _pdf_movement_media_url(item.corrective_exercise, link_base_url)
            if href:
                name = (
                    f'<link href="{html.escape(href, quote=True)}">'
                    f'<u><font color="#0563C1">{name}</font></u>'
                    "</link>"
                )
            line = f"• {name}"
            if item.sets:
                line += f" — ست: {html.escape(reshape_text(item.sets))}"
            if item.reps:
                line += f" — تکرار/مدت: {html.escape(reshape_text(item.reps))}"
            if item.note:
                line += f" — {html.escape(reshape_text(item.note))}"
            lines.append(line)
        return Paragraph("<br/>".join(lines), info_style)

    athlete = getattr(getattr(program, "user", None), "fullname", "") or "—"
    coach = getattr(getattr(program, "prescribed_by", None), "display_name", "") or getattr(
        getattr(program, "prescribed_by", None), "fullname", ""
    ) or "—"
    info_lines = [
        f"عنوان برنامه: {program.title}",
        f"نام ورزشکار: {athlete}",
        f"نام مربی: {coach}",
        f"تاریخ شروع: {_format_pdf_date(program.start_date)}",
        f"تاریخ اتمام: {_format_pdf_date(program.end_date) if program.end_date else '—'}",
    ]
    note_lines = [
        program.notes,
        f"مکمل و نکات تغذیه‌ای:\n{program.supplements_note}" if program.supplements_note else "",
        f"توضیحات گرم کردن:\n{program.warmup_notes}" if program.warmup_notes else "",
        f"توضیحات سرد کردن:\n{program.cooldown_notes}" if program.cooldown_notes else "",
    ]
    note_body = "\n\n".join(item for item in note_lines if item).strip() or "—"

    summary = Table(
        [
            [
                paragraph("حرکات اصلاحی حین گرم کردن", info_style),
                paragraph("حرکات اصلاحی حین سرد کردن", info_style),
            ],
            [
                corrective_paragraph("warmup"),
                corrective_paragraph("cooldown"),
            ],
            [
                [
                    Paragraph(
                        html.escape(_get_rtl_text_transformer()("نکات، مکمل پیشنهادی و مصرف:")),
                        note_heading_style,
                    ),
                    paragraph(note_body, info_style),
                ],
                paragraph("\n".join(info_lines), info_style),
            ],
        ],
        colWidths=[content_width / 2, content_width / 2],
        rowHeights=[0.35 * inch, 1.15 * inch, 2.45 * inch],
    )
    summary.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.55, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    _, summary_height = summary.wrapOn(document, content_width, page_height)
    summary.drawOn(document, content_x, page_height - 2.58 * inch - summary_height)


def _draw_pdf_background(document, background, page_width, page_height):
    if background is not None:
        document.drawImage(
            background,
            0,
            0,
            width=page_width,
            height=page_height,
            preserveAspectRatio=False,
            mask="auto",
        )


def _pdf_background_reader(image_reader_class):
    background_data = _pdf_background_data()
    if background_data:
        try:
            return image_reader_class(BytesIO(background_data))
        except Exception:
            pass
    return None


def _pdf_background_data():
    try:
        base_dir = Path(settings.BASE_DIR)
    except Exception:
        base_dir = Path(__file__).resolve().parents[2]

    configured_path = getattr(settings, "EGOFIT_PDF_BACKGROUND_PATH", "")
    candidates = [Path(configured_path)] if configured_path else []
    candidates.extend(
        [
            base_dir / "assets" / "images" / "sarbarg-background.jpg",
            base_dir / "assets" / "images" / "sarbarg.jpg",
        ]
    )
    for path in candidates:
        if path and path.exists():
            try:
                return path.read_bytes()
            except Exception:
                continue

    # Keep the reference document useful even if its extracted image asset was
    # not deployed separately.
    docx_path = base_dir / "Sarbarg.docx"
    if docx_path.exists():
        try:
            with zipfile.ZipFile(docx_path) as archive:
                return archive.read("word/media/image1.jpg")
        except (KeyError, OSError, zipfile.BadZipFile):
            pass
    return b""


def _persian_number(number):
    digits = "۰۱۲۳۴۵۶۷۸۹"
    return "".join(digits[int(char)] for char in str(number))


def _format_pdf_date(value):
    if not value:
        return "—"
    try:
        import jdatetime

        return jdatetime.date.fromgregorian(date=value).strftime("%d/%m/%Y")
    except (ImportError, TypeError, ValueError):
        return value.strftime("%d/%m/%Y")


def _register_farsi_font() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for path in _pdf_font_candidates():
        if path.exists():
            try:
                pdfmetrics.registerFont(TTFont("EgoFitFarsi", str(path)))
                return "EgoFitFarsi"
            except Exception:
                continue
    raise ImportError(
        "No Persian-capable TrueType font is available for program PDF generation."
    )


def _get_rtl_text_transformer():
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
    except ImportError:
        raise ImportError(
            "arabic-reshaper and python-bidi are required for Persian program PDFs."
        )

    def transform(value):
        return get_display(arabic_reshaper.reshape(value))

    return transform


def _build_fallback_pdf(program, *, link_base_url="") -> bytes:
    """Create an image-based Persian PDF when optional PDF packages are absent.

    The fallback intentionally follows the same Sarbarg layout as the
    ReportLab renderer so development installations without ReportLab still
    produce the branded, Persian-capable worksheet.
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return _minimal_pdf(
            [
                "EgoFit workout program",
                "Install reportlab, arabic-reshaper, and python-bidi for Persian PDF output.",
            ]
        )

    font_path = next((path for path in _pdf_font_candidates() if path.exists()), None)
    if font_path is None:
        return _minimal_pdf(
            [
                "EgoFit workout program",
                "No Persian font is available for PDF output.",
            ]
        )

    page_width, page_height = 864, 1232
    background_data = _pdf_background_data()
    days = list(program.days.all())
    schedule_page_count = max(3, math.ceil(max(1, len(days)) / 2))
    day_slots = days + [None] * (schedule_page_count * 2 - len(days))
    pages = []
    page_links = []
    for page_index in range(schedule_page_count):
        page = _fallback_background_page(Image, background_data, page_width, page_height)
        draw = ImageDraw.Draw(page)
        top = 270
        current_page_links = []
        for slot_index in range(2):
            day_index = page_index * 2 + slot_index
            table_height = _draw_fallback_day_table(
                draw,
                day_slots[day_index],
                day_index + 1,
                font_path,
                x=51,
                top=top,
                width=762,
                link_base_url=link_base_url,
                link_specs=current_page_links,
            )
            top += table_height + 14
        pages.append(page)
        page_links.append(current_page_links)

    summary_page = _fallback_background_page(Image, background_data, page_width, page_height)
    summary_page_links = []
    _draw_fallback_summary_page(
        ImageDraw.Draw(summary_page),
        program,
        font_path,
        x=51,
        top=290,
        width=762,
        link_base_url=link_base_url,
        link_specs=summary_page_links,
    )
    pages.append(summary_page)
    page_links.append(summary_page_links)

    return _build_image_pdf_with_links(
        pages,
        page_links,
        page_width=page_width,
        page_height=page_height,
    )


def _fallback_background_page(image_module, background_data, page_width, page_height):
    if background_data:
        try:
            return image_module.open(BytesIO(background_data)).convert("RGB").resize(
                (page_width, page_height)
            )
        except Exception:
            pass
    return image_module.new("RGB", (page_width, page_height), "white")


def _fallback_movement_rows(day):
    rows = []
    if day is None:
        return rows
    for item in day.items.all():
        rows.append((item.exercise.name, item.sets, item.reps, item.rest, item.note, item.exercise))
        if item.superset_exercise_id:
            rows.append(
                (
                    item.superset_exercise.name,
                    item.superset_sets or item.sets,
                    item.superset_reps or item.reps,
                    item.superset_rest or item.rest,
                    item.note,
                    item.superset_exercise,
                )
            )
        if item.third_exercise_id:
            rows.append(
                (
                    item.third_exercise.name,
                    item.third_sets or item.sets,
                    item.third_reps or item.reps,
                    item.third_rest or item.rest,
                    item.note,
                    item.third_exercise,
                )
            )
    return rows


def _draw_fallback_day_table(
    draw,
    day,
    number,
    font_path,
    *,
    x,
    top,
    width,
    link_base_url="",
    link_specs=None,
):
    from PIL import ImageFont

    title_font = ImageFont.truetype(str(font_path), 18)
    header_font = ImageFont.truetype(str(font_path), 13)
    body_font = ImageFont.truetype(str(font_path), 13)
    widths = [280, 100, 60, 100, 222]
    title_height, header_height, row_height = 30, 42, 27
    movement_rows = _fallback_movement_rows(day)
    row_count = max(10, len(movement_rows))
    height = title_height + header_height + row_count * row_height
    right = x + width
    bottom = top + height
    ink = "#111111"

    title = f"برنامه {_persian_number(number)}"
    if day is not None and day.name:
        title = f"{title} — {day.name}"
    _fallback_cell_text(draw, title, (x, top, right, top + title_height), title_font, max_lines=1)
    draw.rectangle((x, top, right, top + title_height), outline=ink, width=1)
    draw.line((x, top + title_height, right, top + title_height), fill=ink, width=1)

    headers = ["توضیحات", "استراحت/دقیقه", "ست", "تکرار", "نام حرکت"]
    current_x = x
    for column_width, label in zip(widths, headers):
        next_x = current_x + column_width
        _fallback_cell_text(
            draw,
            label,
            (current_x, top + title_height, next_x, top + title_height + header_height),
            header_font,
            max_lines=2,
        )
        draw.rectangle(
            (current_x, top + title_height, next_x, top + title_height + header_height),
            outline=ink,
            width=1,
        )
        current_x = next_x

    values = [
        (row[4] or "—", row[3] or "—", row[1] or "—", row[2] or "—", row[0])
        for row in movement_rows
    ]
    values.extend([(" ", " ", " ", " ", " ")] * (row_count - len(values)))
    for row_index, row in enumerate(values):
        row_top = top + title_height + header_height + row_index * row_height
        current_x = x
        for column_width, value in zip(widths, row):
            next_x = current_x + column_width
            _fallback_cell_text(
                draw,
                value,
                (current_x, row_top, next_x, row_top + row_height),
                body_font,
                max_lines=2,
            )
            draw.rectangle(
                (current_x, row_top, next_x, row_top + row_height),
                outline=ink,
                width=1,
            )
            current_x = next_x
        if link_specs is not None and row_index < len(movement_rows):
            movement = movement_rows[row_index][5]
            href = _pdf_movement_media_url(movement, link_base_url)
            if href:
                movement_cell_x = x + sum(widths[:4])
                link_specs.append(
                    (
                        movement_cell_x,
                        row_top,
                        widths[4],
                        row_height,
                        href,
                    )
                )
    return height


def _build_image_pdf_with_links(pages, page_links, *, page_width, page_height):
    """Build an image PDF and retain URI annotations for the fallback renderer."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        None,
    ]
    page_object_ids = []

    for page, links in zip(pages, page_links):
        page_object_id = len(objects) + 1
        objects.append(None)
        page_object_ids.append(page_object_id)

        image_output = BytesIO()
        page.convert("RGB").save(image_output, format="JPEG", quality=90, optimize=True)
        image_data = image_output.getvalue()
        image_object_id = len(objects) + 1
        objects.append(
            b"<< /Type /XObject /Subtype /Image "
            + f"/Width {page_width} /Height {page_height} ".encode("ascii")
            + b"/ColorSpace /DeviceRGB /BitsPerComponent 8 "
            + b"/Filter /DCTDecode /Length "
            + str(len(image_data)).encode("ascii")
            + b" >>\nstream\n"
            + image_data
            + b"\nendstream"
        )

        content = (
            f"q\n{page_width} 0 0 {page_height} 0 0 cm\n"
            "/Im0 Do\nQ\n"
        ).encode("ascii")
        content_object_id = len(objects) + 1
        objects.append(
            b"<< /Length "
            + str(len(content)).encode("ascii")
            + b" >>\nstream\n"
            + content
            + b"endstream"
        )

        annotation_ids = []
        for left, top, width, height, href in links:
            annotation_object_id = len(objects) + 1
            annotation_ids.append(annotation_object_id)
            bottom = page_height - top - height
            uri = _pdf_literal_string(href)
            objects.append(
                b"<< /Type /Annot /Subtype /Link "
                + f"/Rect [{left:g} {bottom:g} {left + width:g} {bottom + height:g}] ".encode("ascii")
                + b"/Border [0 0 0] /A << /S /URI /URI "
                + uri
                + b" >> >>"
            )

        page_object = (
            b"<< /Type /Page /Parent 2 0 R "
            + f"/MediaBox [0 0 {page_width} {page_height}] ".encode("ascii")
            + b"/Resources << /XObject << /Im0 "
            + f"{image_object_id} 0 R".encode("ascii")
            + b" >> >> /Contents "
            + f"{content_object_id} 0 R".encode("ascii")
        )
        if annotation_ids:
            page_object += b" /Annots [" + b" ".join(
                f"{annotation_id} 0 R".encode("ascii")
                for annotation_id in annotation_ids
            ) + b"]"
        page_object += b" >>"
        objects[page_object_id - 1] = page_object

    objects[1] = (
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{page_id} 0 R".encode("ascii") for page_id in page_object_ids)
        + f"] /Count {len(page_object_ids)} >>".encode("ascii")
    )
    return _serialize_pdf_objects(objects)


def _pdf_literal_string(value):
    escaped = str(value).encode("utf-8").replace(b"\\", b"\\\\")
    escaped = escaped.replace(b"(", b"\\(").replace(b")", b"\\)")
    return b"(" + escaped + b")"


def _serialize_pdf_objects(objects):
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF".encode("ascii")
    )
    return bytes(pdf)


def _draw_fallback_summary_page(
    draw,
    program,
    font_path,
    *,
    x,
    top,
    width,
    link_base_url="",
    link_specs=None,
):
    from PIL import ImageFont

    heading_font = ImageFont.truetype(str(font_path), 15)
    body_font = ImageFont.truetype(str(font_path), 13)
    note_font = ImageFont.truetype(str(font_path), 16)
    column_width = width // 2
    heading_height, corrective_height, details_height = 34, 130, 270
    ink = "#111111"
    right = x + width

    corrective_by_phase = {"warmup": [], "cooldown": []}
    for item in program.corrective_items.all():
        corrective_by_phase.setdefault(item.phase, []).append(item)

    def corrective_text(phase):
        items = corrective_by_phase.get(phase, [])
        if not items:
            return "—"
        return "\n".join(
            f"• {item.corrective_exercise.name}"
            + (f" — ست: {item.sets}" if item.sets else "")
            + (f" — تکرار/مدت: {item.reps}" if item.reps else "")
            + (f" — {item.note}" if item.note else "")
            for item in items
        )

    athlete = getattr(getattr(program, "user", None), "fullname", "") or "—"
    coach_user = getattr(program, "prescribed_by", None)
    coach = getattr(coach_user, "display_name", "") or getattr(coach_user, "fullname", "") or "—"
    info = "\n".join(
        [
            f"عنوان برنامه: {program.title}",
            f"نام ورزشکار: {athlete}",
            f"نام مربی: {coach}",
            f"تاریخ شروع: {_format_pdf_date(program.start_date)}",
            f"تاریخ اتمام: {_format_pdf_date(program.end_date) if program.end_date else '—'}",
        ]
    )
    note_body = "\n\n".join(
        item
        for item in (
            program.notes,
            f"مکمل و نکات غذایی:\n{program.supplements_note}" if program.supplements_note else "",
            f"توضیحات گرم کردن:\n{program.warmup_notes}" if program.warmup_notes else "",
            f"توضیحات سرد کردن:\n{program.cooldown_notes}" if program.cooldown_notes else "",
        )
        if item
    ) or "—"

    draw.rectangle(
        (x, top, right, top + heading_height + corrective_height + details_height),
        outline=ink,
        width=1,
    )
    draw.line((x + column_width, top, x + column_width, top + heading_height + corrective_height), fill=ink, width=1)
    draw.line((x, top + heading_height, right, top + heading_height), fill=ink, width=1)
    draw.line((x, top + heading_height + corrective_height, right, top + heading_height + corrective_height), fill=ink, width=1)
    draw.line((x + column_width, top + heading_height + corrective_height, x + column_width, top + heading_height + corrective_height + details_height), fill=ink, width=1)

    _fallback_cell_text(draw, "حرکات اصلاحی حین گرم کردن", (x, top, x + column_width, top + heading_height), heading_font, max_lines=2)
    _fallback_cell_text(draw, "حرکات اصلاحی حین سرد کردن", (x + column_width, top, right, top + heading_height), heading_font, max_lines=2)
    _fallback_cell_text(
        draw,
        corrective_text("warmup"),
        (x, top + heading_height, x + column_width, top + heading_height + corrective_height),
        body_font,
        max_lines=6,
    )
    _fallback_cell_text(
        draw,
        corrective_text("cooldown"),
        (x + column_width, top + heading_height, right, top + heading_height + corrective_height),
        body_font,
        max_lines=6,
    )
    if link_specs is not None:
        for phase, cell_x in (("warmup", x), ("cooldown", x + column_width)):
            items = corrective_by_phase.get(phase, [])
            if not items:
                continue
            cell_top = top + heading_height
            row_height = corrective_height / len(items)
            for index, item in enumerate(items):
                href = _pdf_movement_media_url(item.corrective_exercise, link_base_url)
                if href:
                    link_specs.append(
                        (
                            cell_x,
                            cell_top + index * row_height,
                            column_width,
                            row_height,
                            href,
                        )
                    )
    _fallback_cell_text(
        draw,
        "نکات، مکمل پیشنهادی و مصرف:",
        (x, top + heading_height + corrective_height, x + column_width, top + heading_height + corrective_height + 38),
        note_font,
        fill="#d00000",
        max_lines=2,
    )
    _fallback_cell_text(
        draw,
        note_body,
        (x, top + heading_height + corrective_height + 34, x + column_width, top + heading_height + corrective_height + details_height),
        body_font,
        max_lines=11,
    )
    _fallback_cell_text(
        draw,
        info,
        (x + column_width, top + heading_height + corrective_height, right, top + heading_height + corrective_height + details_height),
        body_font,
        max_lines=8,
    )


def _fallback_cell_text(
    draw,
    value,
    box,
    font,
    *,
    fill="#111111",
    max_lines=2,
):
    left, top, right, bottom = box
    max_width = max(1, right - left - 8)
    lines = []
    for raw_line in str(value or " ").splitlines() or [" "]:
        lines.extend(_wrap_fallback_line(raw_line, font, max_width, draw))
    if not lines:
        lines = [" "]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        logical = lines[-1]
        while len(logical) > 1 and draw.textlength(
            _fallback_rtl_visual(logical + "…"), font=font
        ) > max_width:
            logical = logical[:-1]
        lines[-1] = logical + "…" if logical.strip() else "…"

    line_height = max(13, int(font.size * 1.25))
    total_height = line_height * len(lines)
    current_y = top + max(0, (bottom - top - total_height) // 2)
    for line in lines:
        visual = _fallback_rtl_visual(line)
        text_width = draw.textlength(visual, font=font)
        draw.text(
            (left + (right - left - text_width) / 2, current_y),
            visual,
            font=font,
            fill=fill,
        )
        current_y += line_height


def _pdf_font_candidates() -> list[Path]:
    candidates = []
    try:
        configured_path = getattr(settings, "EGOFIT_PDF_FONT_PATH", "")
        base_dir = Path(settings.BASE_DIR)
    except Exception:
        configured_path = ""
        base_dir = Path(__file__).resolve().parents[2]
    if configured_path:
        candidates.append(Path(configured_path))

    try:
        import admin_persian

        package_fonts = (
            Path(admin_persian.__file__).resolve().parent
            / "static"
            / "admin_persian"
            / "fonts"
        )
        candidates.extend(
            [
                package_fonts / "sahel" / "Sahel.ttf",
                package_fonts / "vazir" / "Vazir.ttf",
                package_fonts / "samim" / "Samim.ttf",
                package_fonts / "yekan" / "Yekan.ttf",
                package_fonts / "tanha" / "Tanha.ttf",
            ]
        )
    except (ImportError, AttributeError, OSError):
        pass

    candidates.extend(
        [
            base_dir / "assets" / "fonts" / "Vazirmatn-Regular.ttf",
            base_dir / "assets" / "fonts" / "BNazanin.ttf",
            Path("C:/Windows/Fonts/tahoma.ttf"),
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
    )
    return candidates


_ARABIC_FORMS = {
    "ا": ("\ufe8d", "\ufe8e", None, None),
    "آ": ("\ufe81", "\ufe82", None, None),
    "ب": ("\ufe8f", "\ufe90", "\ufe91", "\ufe92"),
    "پ": ("\ufb56", "\ufb57", "\ufb58", "\ufb59"),
    "ت": ("\ufe95", "\ufe96", "\ufe97", "\ufe98"),
    "ث": ("\ufe99", "\ufe9a", "\ufe9b", "\ufe9c"),
    "ج": ("\ufe9d", "\ufe9e", "\ufe9f", "\ufea0"),
    "چ": ("\ufb7a", "\ufb7b", "\ufb7c", "\ufb7d"),
    "ح": ("\ufea1", "\ufea2", "\ufea3", "\ufea4"),
    "خ": ("\ufea5", "\ufea6", "\ufea7", "\ufea8"),
    "د": ("\ufea9", "\ufeaa", None, None),
    "ذ": ("\ufeab", "\ufeac", None, None),
    "ر": ("\ufead", "\ufeae", None, None),
    "ز": ("\ufeaf", "\ufeb0", None, None),
    "ژ": ("\xfb8a", "\ufb8b", None, None),
    "س": ("\ufeb1", "\ufeb2", "\ufeb3", "\ufeb4"),
    "ش": ("\ufeb5", "\ufeb6", "\ufeb7", "\ufeb8"),
    "ص": ("\ufeb9", "\ufeba", "\ufebb", "\ufebc"),
    "ض": ("\ufebd", "\ufebe", "\ufebf", "\ufec0"),
    "ط": ("\ufec1", "\ufec2", "\ufec3", "\ufec4"),
    "ظ": ("\ufec5", "\ufec6", "\ufec7", "\ufec8"),
    "ع": ("\ufec9", "\ufeca", "\ufecb", "\ufecc"),
    "غ": ("\ufecd", "\ufece", "\ufecf", "\ufed0"),
    "ف": ("\ufed1", "\ufed2", "\ufed3", "\ufed4"),
    "ق": ("\ufed5", "\ufed6", "\ufed7", "\ufed8"),
    "ک": ("\ufb8e", "\ufb8f", "\ufb90", "\ufb91"),
    "گ": ("\ufb92", "\ufb93", "\ufb94", "\ufb95"),
    "ل": ("\ufedd", "\ufede", "\ufedf", "\ufee0"),
    "م": ("\ufee1", "\ufee2", "\ufee3", "\ufee4"),
    "ن": ("\ufee5", "\ufee6", "\ufee7", "\ufee8"),
    "ه": ("\ufee9", "\ufeea", "\ufeeb", "\ufeec"),
    "و": ("\ufeed", "\ufeee", None, None),
    "ی": ("\ufeef", "\ufef0", "\ufef1", "\ufef2"),
    "\u06CC": ("\ufef1", "\ufef2", "\ufef3", "\ufef4"),
}


def _fallback_rtl_visual(value: str) -> str:
    tokens = re.findall(r"[\u0600-\u06ff\u200c]+|[A-Za-z]+|[0-9]+|\s+|.", str(value))
    visual_tokens = []
    for token in reversed(tokens):
        if re.fullmatch(r"[\u0600-\u06ff]+", token):
            visual_tokens.append(_reshape_arabic_run(token)[::-1])
        else:
            visual_tokens.append(token)
    return "".join(visual_tokens)


def _reshape_arabic_run(value: str) -> str:
    chars = [char for char in value if char != "\u200c"]
    shaped = []
    for index, char in enumerate(chars):
        forms = _ARABIC_FORMS.get(char)
        if not forms:
            shaped.append(char)
            continue
        previous = chars[index - 1] if index else ""
        following = chars[index + 1] if index + 1 < len(chars) else ""
        previous_forms = _ARABIC_FORMS.get(previous)
        following_forms = _ARABIC_FORMS.get(following)
        joins_previous = bool(previous_forms and previous_forms[2] and forms[1])
        joins_following = bool(following_forms and forms[2] and following_forms[1])
        if joins_previous and joins_following and forms[3]:
            shaped.append(forms[3])
        elif joins_previous:
            shaped.append(forms[1])
        elif joins_following and forms[2]:
            shaped.append(forms[2])
        else:
            shaped.append(forms[0])
    return "".join(shaped)


def _wrap_fallback_line(value, font, max_width, draw):
    words = str(value).split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        visual = _fallback_rtl_visual(candidate)
        if font.getlength(visual) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _minimal_pdf(lines: list[str]) -> bytes:
    """Create a valid, readable ASCII PDF when ReportLab is not installed."""
    escaped_lines = []
    for line in lines[:45]:
        safe = str(line).encode("ascii", "replace").decode("ascii")
        safe = safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        escaped_lines.append(f"({safe}) Tj")
    content = "BT /F1 10 Tf 40 800 Td 0 -16 Td ".encode("ascii")
    content += b" ".join(
        [f"{line} 0 -16 Td".encode("ascii") for line in escaped_lines]
    )
    content += b" ET"

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{number} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF".encode("ascii")
    )
    return bytes(pdf)
