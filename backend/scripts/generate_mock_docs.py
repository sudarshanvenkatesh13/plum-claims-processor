"""
Generates realistic Indian medical document images for testing the claims system.
Output: frontend/public/sample-documents/
Run: cd backend && python -m scripts.generate_mock_docs
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── Constants ─────────────────────────────────────────────────────────────────

W, H = 800, 1100
BG       = (252, 252, 250)   # Slight off-white paper
DARK     = (25, 25, 25)
GRAY     = (110, 110, 110)
LGRAY    = (190, 190, 190)
TEAL     = (0, 110, 100)
BLUE     = (30, 60, 130)
RED_DARK = (140, 20, 20)
TABLE_BG = (245, 245, 245)
L_MARGIN = 40
R_MARGIN = W - 40
INNER_W  = R_MARGIN - L_MARGIN

OUT_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "public" / "sample-documents"

# ── Font loading ──────────────────────────────────────────────────────────────

_FONT_PATHS_REGULAR = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]
_FONT_PATHS_BOLD = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
_cache: dict = {}


def _load(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    key = (size, bold)
    if key in _cache:
        return _cache[key]
    paths = _FONT_PATHS_BOLD if bold else _FONT_PATHS_REGULAR
    for p in paths:
        if Path(p).exists():
            try:
                f = ImageFont.truetype(p, size)
                _cache[key] = f
                return f
            except Exception:
                pass
    # Pillow 10+ supports size parameter on default font
    try:
        f = ImageFont.load_default(size=size)
    except TypeError:
        f = ImageFont.load_default()
    _cache[key] = f
    return f


# ── Drawing helpers ───────────────────────────────────────────────────────────

def _new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle([6, 6, W - 7, H - 7], outline=LGRAY, width=1)
    return img, draw


def _text(draw: ImageDraw.ImageDraw, x: int, y: int, txt: str,
          size: int = 14, bold: bool = False, color: tuple = DARK,
          anchor: str = "la") -> int:
    """Draw text and return its pixel height."""
    font = _load(size, bold)
    draw.text((x, y), txt, font=font, fill=color, anchor=anchor)
    bb = draw.textbbox((x, y), txt, font=font, anchor=anchor)
    return bb[3] - bb[1]


def _line(draw: ImageDraw.ImageDraw, y: int, margin: int = L_MARGIN) -> int:
    draw.line([(margin, y), (R_MARGIN, y)], fill=LGRAY, width=1)
    return y + 14


def _hbar(draw: ImageDraw.ImageDraw, y: int, color: tuple = TEAL, height: int = 3) -> int:
    draw.rectangle([L_MARGIN, y, R_MARGIN, y + height], fill=color)
    return y + height + 10


def _watermark(img: Image.Image, text: str = "ORIGINAL", angle: int = 30,
               opacity: int = 22, size: int = 72) -> Image.Image:
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    font = _load(size, bold=True)
    bb = d.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    cx, cy = (W - tw) // 2, (H - th) // 2
    d.text((cx, cy), text, font=font, fill=(180, 180, 180, opacity))
    rotated = overlay.rotate(angle, expand=False)
    base = img.convert("RGBA")
    base.alpha_composite(rotated)
    return base.convert("RGB")


def _stamp_circle(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int = 42,
                  line1: str = "PAID", line2: str = "ORIGINAL", color: tuple = RED_DARK) -> None:
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=2)
    draw.ellipse([cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4], outline=color, width=1)
    _text(draw, cx, cy - 10, line1, size=13, bold=True, color=color, anchor="mm")
    _text(draw, cx, cy + 8,  line2, size=10, bold=False, color=color, anchor="mm")


def _signature(draw: ImageDraw.ImageDraw, x: int, y: int, width: int = 130) -> None:
    """Draw a squiggly signature line."""
    pts: list[tuple[int, int]] = []
    for i in range(width):
        xi = x + i
        yi = y + int(7 * math.sin(i * 0.25)) + int(4 * math.sin(i * 0.6)) + random.randint(-1, 1)
        pts.append((xi, yi))
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=DARK, width=2)
    # Tail flourish
    draw.line([(x + width, y + 2), (x + width + 20, y - 8)], fill=DARK, width=2)


def _table_header(draw: ImageDraw.ImageDraw, y: int,
                  cols: list[str], widths: list[int], start_x: int = L_MARGIN) -> int:
    total = sum(widths)
    draw.rectangle([start_x, y, start_x + total, y + 28], fill=(220, 235, 235))
    draw.rectangle([start_x, y, start_x + total, y + 28], outline=LGRAY, width=1)
    x = start_x
    for col, w in zip(cols, widths):
        _text(draw, x + 6, y + 7, col, size=12, bold=True, color=TEAL)
        if x + w < start_x + total:
            draw.line([(x + w, y), (x + w, y + 28)], fill=LGRAY, width=1)
        x += w
    return y + 28


def _table_row(draw: ImageDraw.ImageDraw, y: int,
               vals: list[str], widths: list[int], start_x: int = L_MARGIN,
               shaded: bool = False) -> int:
    total = sum(widths)
    if shaded:
        draw.rectangle([start_x, y, start_x + total, y + 26], fill=(248, 250, 250))
    draw.rectangle([start_x, y, start_x + total, y + 26], outline=LGRAY, width=1)
    x = start_x
    for i, (val, w) in enumerate(zip(vals, widths)):
        align_right = i > 0 and val and val[0].isdigit()
        if align_right:
            _text(draw, x + w - 8, y + 6, val, size=12, color=DARK, anchor="ra")
        else:
            _text(draw, x + 6, y + 6, val, size=12, color=DARK)
        if x + w < start_x + total:
            draw.line([(x + w, y), (x + w, y + 26)], fill=LGRAY, width=1)
        x += w
    return y + 26


def _total_row(draw: ImageDraw.ImageDraw, y: int,
               label: str, amount: str, widths: list[int], start_x: int = L_MARGIN) -> int:
    total = sum(widths)
    draw.rectangle([start_x, y, start_x + total, y + 30], fill=(225, 240, 235))
    draw.rectangle([start_x, y, start_x + total, y + 30], outline=LGRAY, width=1)
    label_end = start_x + sum(widths[:-1])
    _text(draw, label_end - 8, y + 8, label, size=13, bold=True, color=TEAL, anchor="ra")
    _text(draw, start_x + total - 8, y + 8, amount, size=13, bold=True, color=TEAL, anchor="ra")
    return y + 30


# ── Document 1: Prescription — Rajesh Kumar (TC004) ──────────────────────────

def gen_prescription_rajesh() -> None:
    img, draw = _new_canvas()

    # Header
    _text(draw, W // 2, 28, "Dr. Arun Sharma", size=26, bold=True, color=TEAL, anchor="mt")
    _text(draw, W // 2, 60, "MBBS, MD (Internal Medicine)", size=14, color=GRAY, anchor="mt")
    _text(draw, W // 2, 80, "Reg. No: KA/45678/2015", size=12, color=GRAY, anchor="mt")
    _text(draw, W // 2, 98, "City Medical Centre, 12 MG Road, Bengaluru – 560 001", size=12, color=GRAY, anchor="mt")
    _text(draw, W // 2, 116, "Ph: +91-80-4123 4567  |  Timing: 9 AM – 1 PM, 4 PM – 8 PM", size=11, color=GRAY, anchor="mt")

    y = _hbar(draw, 134, color=TEAL, height=2)

    # Patient info row
    draw.rectangle([L_MARGIN, y, R_MARGIN, y + 34], fill=(240, 250, 248), outline=LGRAY, width=1)
    _text(draw, L_MARGIN + 10, y + 9, "Patient:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 68, y + 9, "Rajesh Kumar", size=13, bold=True, color=DARK)
    _text(draw, 310, y + 9, "Age:", size=12, bold=True, color=GRAY)
    _text(draw, 345, y + 9, "39 yrs", size=12, color=DARK)
    _text(draw, 420, y + 9, "Sex:", size=12, bold=True, color=GRAY)
    _text(draw, 453, y + 9, "M", size=12, color=DARK)
    _text(draw, R_MARGIN - 10, y + 9, "Date: 01-Nov-2024", size=12, color=DARK, anchor="ra")
    y += 34 + 10

    # Diagnosis
    _text(draw, L_MARGIN, y, "Diagnosis:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 90, y, "Viral Fever (Acute Febrile Illness)", size=13, color=DARK)
    y += 22
    y = _line(draw, y)

    # Rx
    _text(draw, L_MARGIN, y, "℞", size=28, bold=True, color=TEAL)
    y += 36

    meds = [
        ("1.", "Tab Paracetamol 650 mg",       "— 1-1-1 × 5 days    (After food)"),
        ("2.", "Tab Vitamin C 500 mg",           "— 0-0-1 × 7 days    (After food)"),
        ("3.", "Tab Azithromycin 500 mg",        "— 1-0-0 × 3 days    (Before food)"),
    ]
    for num, drug, dosage in meds:
        _text(draw, L_MARGIN + 4,  y, num,    size=13, color=GRAY)
        _text(draw, L_MARGIN + 22, y, drug,   size=13, bold=True, color=DARK)
        _text(draw, L_MARGIN + 22, y + 18, dosage, size=12, color=GRAY)
        y += 44

    y = _line(draw, y + 4)

    # Investigations
    _text(draw, L_MARGIN, y, "Investigations:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 110, y, "CBC (Complete Blood Count), Dengue NS1 Antigen", size=13, color=DARK)
    y += 28

    # Follow-up
    _text(draw, L_MARGIN, y, "Follow-up:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 80, y, "After 5 days or immediately if symptoms worsen", size=13, color=DARK)
    y += 28
    y = _line(draw, y)

    # Advice
    _text(draw, L_MARGIN, y, "Advice:", size=13, bold=True, color=GRAY)
    advice = ["• Rest and adequate hydration (3–4 litres/day)",
              "• Avoid spicy/oily food for 5 days",
              "• Paracetamol only for fever — avoid NSAIDs"]
    y += 22
    for a in advice:
        _text(draw, L_MARGIN + 12, y, a, size=12, color=GRAY)
        y += 20

    # Signature area
    y = 900
    _line(draw, y)
    y += 8
    _signature(draw, L_MARGIN + 20, y + 20)
    draw.line([(L_MARGIN, y + 48), (L_MARGIN + 200, y + 48)], fill=LGRAY, width=1)
    _text(draw, L_MARGIN, y + 52, "Dr. Arun Sharma", size=13, bold=True, color=DARK)
    _text(draw, L_MARGIN, y + 70, "MBBS, MD (Internal Medicine)", size=11, color=GRAY)
    _text(draw, L_MARGIN, y + 86, "Reg. No: KA/45678/2015", size=11, color=GRAY)

    # Stamp
    _stamp_circle(draw, R_MARGIN - 70, y + 40, r=48, line1="CLINIC", line2="STAMP", color=BLUE)

    # Footer
    _text(draw, W // 2, H - 22, "— This prescription is valid for 30 days —", size=10, color=LGRAY, anchor="mt")

    img = _watermark(img, "PRESCRIPTION", angle=28, opacity=18, size=68)
    _save(img, "prescription_rajesh_consultation.jpg")


# ── Document 2: Hospital Bill — Rajesh Kumar (TC004) ─────────────────────────

def gen_bill_rajesh() -> None:
    img, draw = _new_canvas()

    # Header band
    draw.rectangle([6, 6, W - 7, 90], fill=(0, 110, 100))
    _text(draw, W // 2, 18, "CITY MEDICAL CENTRE", size=28, bold=True, color=(255, 255, 255), anchor="mt")
    _text(draw, W // 2, 54, "12 MG Road, Bengaluru – 560 001", size=13, color=(210, 235, 232), anchor="mt")
    _text(draw, W // 2, 72, "GSTIN: 29AXXXX1234X1ZX  |  Ph: +91-80-4123 4567", size=11, color=(185, 220, 215), anchor="mt")

    y = 105
    # Bill meta
    draw.rectangle([L_MARGIN, y, R_MARGIN, y + 56], fill=(245, 250, 249), outline=LGRAY, width=1)
    _text(draw, L_MARGIN + 10, y + 8,  "Bill No:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 70, y + 8,  "CMC/2024/08321", size=12, color=DARK)
    _text(draw, L_MARGIN + 10, y + 28, "Date:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 55, y + 28, "01-Nov-2024", size=12, color=DARK)
    _text(draw, 420, y + 8,  "Patient:", size=12, bold=True, color=GRAY)
    _text(draw, 480, y + 8,  "Rajesh Kumar", size=12, color=DARK)
    _text(draw, 420, y + 28, "Age/Sex:", size=12, bold=True, color=GRAY)
    _text(draw, 490, y + 28, "39 / Male", size=12, color=DARK)
    _text(draw, L_MARGIN + 10, y + 44, "Ref. Doctor:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 95, y + 44, "Dr. Arun Sharma", size=12, color=DARK)
    y += 56 + 18

    # Table
    cols   = ["DESCRIPTION",             "QTY", "RATE (₹)",  "AMOUNT (₹)"]
    widths = [INNER_W - 240,              60,    90,          90]
    rows = [
        ("Consultation Fee (OPD)",         "1", "1,000.00", "1,000.00"),
        ("CBC – Complete Blood Count",     "1",   "200.00",   "200.00"),
        ("Dengue NS1 Antigen Test",        "1",   "300.00",   "300.00"),
    ]

    y = _table_header(draw, y, cols, widths)
    for i, row in enumerate(rows):
        y = _table_row(draw, y, list(row), widths, shaded=(i % 2 == 1))

    y += 10
    draw.line([(L_MARGIN, y), (R_MARGIN, y)], fill=LGRAY, width=1)
    y += 8
    _total_row(draw, y, "Sub-Total:", "₹ 1,500.00", widths)
    y += 30
    _table_row(draw, y, ["GST (0%)", "", "", "₹ 0.00"], widths)
    y += 26 + 4
    _total_row(draw, y, "TOTAL PAYABLE:", "₹ 1,500.00", widths)
    y += 30 + 20

    # Payment
    _text(draw, L_MARGIN, y, "Payment Mode:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 110, y, "UPI  (Ref: UPI24110108321)", size=13, color=DARK)
    y += 24
    _text(draw, L_MARGIN, y, "Amount in words:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 130, y, "Rupees One Thousand Five Hundred Only", size=12, color=DARK)
    y += 36

    _line(draw, y)
    y += 14
    # Signature
    _text(draw, R_MARGIN, y, "Authorised Signatory", size=12, bold=True, color=GRAY, anchor="ra")
    _signature(draw, R_MARGIN - 170, y + 28)
    draw.line([(R_MARGIN - 180, y + 60), (R_MARGIN, y + 60)], fill=LGRAY, width=1)
    _text(draw, R_MARGIN, y + 64, "City Medical Centre", size=11, color=GRAY, anchor="ra")

    _stamp_circle(draw, L_MARGIN + 80, y + 40, r=50, line1="AMOUNT", line2="RECEIVED", color=RED_DARK)

    # Footer
    _text(draw, W // 2, H - 30, "This is a computer-generated bill.", size=10, color=LGRAY, anchor="mt")
    _text(draw, W // 2, H - 16, "Retain this for insurance / tax purposes.", size=10, color=LGRAY, anchor="mt")

    img = _watermark(img, "ORIGINAL", angle=32, opacity=20)
    _save(img, "hospital_bill_rajesh_consultation.jpg")


# ── Document 3: Prescription — Priya Singh / Apollo (TC010) ──────────────────

def gen_prescription_priya() -> None:
    img, draw = _new_canvas()

    # Apollo-style header
    draw.rectangle([6, 6, W - 7, 95], fill=(0, 65, 130))
    _text(draw, W // 2, 16, "APOLLO HOSPITALS", size=26, bold=True, color=(255, 255, 255), anchor="mt")
    _text(draw, W // 2, 50, "Bannerghatta Road, Bengaluru – 560 076", size=13, color=(180, 210, 240), anchor="mt")
    _text(draw, W // 2, 68, "NABH Accredited  |  Ph: +91-80-2630 4050", size=11, color=(150, 190, 225), anchor="mt")

    y = 108
    _text(draw, W // 2, y, "Dr. Meena Reddy", size=22, bold=True, color=BLUE, anchor="mt")
    y += 30
    _text(draw, W // 2, y, "MBBS, MD (General Medicine)  |  Reg. No: KA/56789/2018", size=12, color=GRAY, anchor="mt")
    y += 20
    _text(draw, W // 2, y, "OPD Consultation — Outpatient Department", size=11, color=GRAY, anchor="mt")
    y += 8
    y = _line(draw, y + 8)

    # Patient row
    draw.rectangle([L_MARGIN, y, R_MARGIN, y + 34], fill=(235, 243, 255), outline=LGRAY, width=1)
    _text(draw, L_MARGIN + 8, y + 9, "Patient:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 68, y + 9, "Priya Singh", size=13, bold=True, color=DARK)
    _text(draw, 300, y + 9, "Age:", size=12, bold=True, color=GRAY)
    _text(draw, 335, y + 9, "34 yrs", size=12, color=DARK)
    _text(draw, 410, y + 9, "Sex:", size=12, bold=True, color=GRAY)
    _text(draw, 443, y + 9, "F", size=12, color=DARK)
    _text(draw, R_MARGIN - 8, y + 9, "Date: 15-Oct-2024", size=12, color=DARK, anchor="ra")
    y += 34 + 12

    _text(draw, L_MARGIN, y, "Diagnosis:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 90, y, "Acute Upper Respiratory Tract Infection (URTI)", size=13, color=DARK)
    y += 22
    _text(draw, L_MARGIN, y, "Complaints:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 90, y, "Sore throat, dry cough, mild fever (3 days)", size=12, color=GRAY)
    y += 28
    y = _line(draw, y)

    # Rx
    _text(draw, L_MARGIN, y, "℞", size=28, bold=True, color=BLUE)
    y += 36

    meds = [
        ("1.", "Tab Azithromycin 500 mg",        "— 1-0-0 × 3 days    (Empty stomach)"),
        ("2.", "Syp Cough Expectorant",           "— 5 ml TDS × 5 days (After food)"),
        ("3.", "Tab Cetirizine 10 mg",            "— 0-0-1 × 5 days    (At night)"),
        ("4.", "Throat Lozenges (Strepsils)",     "— Every 2–3 hrs as required"),
    ]
    for num, drug, dosage in meds:
        _text(draw, L_MARGIN + 4, y, num, size=13, color=GRAY)
        _text(draw, L_MARGIN + 22, y, drug, size=13, bold=True, color=DARK)
        _text(draw, L_MARGIN + 22, y + 18, dosage, size=12, color=GRAY)
        y += 44

    y = _line(draw, y + 4)

    _text(draw, L_MARGIN, y, "Investigations:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 110, y, "Throat Swab Culture, Chest X-Ray (PA view)", size=13, color=DARK)
    y += 26
    _text(draw, L_MARGIN, y, "Follow-up:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 80, y, "After 3 days. Return immediately if breathlessness.", size=13, color=DARK)
    y += 28
    y = _line(draw, y)

    _text(draw, L_MARGIN, y, "Advice:", size=13, bold=True, color=GRAY)
    y += 20
    for a in ["• Steam inhalation twice daily", "• Adequate rest and warm fluids", "• Avoid cold beverages and A/C"]:
        _text(draw, L_MARGIN + 12, y, a, size=12, color=GRAY)
        y += 20

    y = 895
    _line(draw, y)
    y += 10
    _signature(draw, L_MARGIN + 30, y + 20, width=140)
    draw.line([(L_MARGIN, y + 52), (L_MARGIN + 220, y + 52)], fill=LGRAY, width=1)
    _text(draw, L_MARGIN, y + 56, "Dr. Meena Reddy, MBBS MD", size=12, bold=True, color=DARK)
    _text(draw, L_MARGIN, y + 74, "Apollo Hospitals, Bengaluru", size=11, color=GRAY)

    draw.ellipse([R_MARGIN - 100, y + 5, R_MARGIN - 5, y + 100], outline=BLUE, width=2)
    _text(draw, R_MARGIN - 52, y + 38, "APOLLO", size=11, bold=True, color=BLUE, anchor="mm")
    _text(draw, R_MARGIN - 52, y + 56, "HOSPITALS", size=10, color=BLUE, anchor="mm")
    _text(draw, R_MARGIN - 52, y + 74, "BENGALURU", size=9, color=GRAY, anchor="mm")

    _text(draw, W // 2, H - 20, "— Apollo Hospitals — Prescription valid for 30 days —", size=10, color=LGRAY, anchor="mt")

    img = _watermark(img, "PRESCRIPTION", angle=28, opacity=18, size=64)
    _save(img, "prescription_priya_consultation.jpg")


# ── Document 4: Hospital Bill — Priya Singh / Apollo (TC010) ─────────────────

def gen_bill_priya_apollo() -> None:
    img, draw = _new_canvas()

    draw.rectangle([6, 6, W - 7, 100], fill=(0, 65, 130))
    _text(draw, W // 2, 14, "APOLLO HOSPITALS", size=30, bold=True, color=(255, 255, 255), anchor="mt")
    _text(draw, W // 2, 52, "Bannerghatta Road, Bengaluru – 560 076", size=13, color=(175, 208, 238), anchor="mt")
    _text(draw, W // 2, 70, "GSTIN: 29AXXXX5678X2ZX  |  NABH Accredited", size=11, color=(150, 190, 225), anchor="mt")
    _text(draw, W // 2, 86, "Ph: +91-80-2630 4050  |  billing@apollo.blr", size=10, color=(130, 175, 215), anchor="mt")

    y = 116
    draw.rectangle([L_MARGIN, y, R_MARGIN, y + 60], fill=(235, 243, 255), outline=LGRAY, width=1)
    _text(draw, L_MARGIN + 10, y + 8,  "Bill No:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 70, y + 8,  "APL/2024/45678", size=12, color=DARK)
    _text(draw, L_MARGIN + 10, y + 28, "Date:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 55, y + 28, "15-Oct-2024", size=12, color=DARK)
    _text(draw, L_MARGIN + 10, y + 48, "Dept:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 55, y + 48, "General Medicine OPD", size=12, color=DARK)
    _text(draw, 430, y + 8,  "Patient:", size=12, bold=True, color=GRAY)
    _text(draw, 490, y + 8,  "Priya Singh", size=12, color=DARK)
    _text(draw, 430, y + 28, "Age/Sex:", size=12, bold=True, color=GRAY)
    _text(draw, 494, y + 28, "34 / Female", size=12, color=DARK)
    _text(draw, 430, y + 48, "Doctor:", size=12, bold=True, color=GRAY)
    _text(draw, 484, y + 48, "Dr. Meena Reddy", size=12, color=DARK)
    y += 60 + 18

    cols   = ["DESCRIPTION",             "QTY",  "RATE (₹)", "AMOUNT (₹)"]
    widths = [INNER_W - 240,              60,     90,         90]
    rows = [
        ("Consultation Fee (OPD)",        "1", "2,000.00", "2,000.00"),
        ("Throat Swab Culture",           "1",   "800.00",   "800.00"),
        ("Chest X-Ray (PA view)",         "1", "1,200.00", "1,200.00"),
        ("Medications dispensed",         "1",   "500.00",   "500.00"),
    ]

    y = _table_header(draw, y, cols, widths)
    for i, row in enumerate(rows):
        y = _table_row(draw, y, list(row), widths, shaded=(i % 2 == 1))

    y += 10
    draw.line([(L_MARGIN, y), (R_MARGIN, y)], fill=LGRAY, width=1)
    y += 8
    _total_row(draw, y, "Sub-Total:", "₹ 4,500.00", widths)
    y += 30
    _table_row(draw, y, ["CGST (0%)", "", "", "₹ 0.00"], widths)
    y += 26
    _table_row(draw, y, ["SGST (0%)", "", "", "₹ 0.00"], widths)
    y += 26 + 4
    _total_row(draw, y, "TOTAL PAYABLE:", "₹ 4,500.00", widths)
    y += 30 + 20

    _text(draw, L_MARGIN, y, "Payment Mode:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 120, y, "Credit Card  (Last 4 digits: XXXX)", size=13, color=DARK)
    y += 24
    _text(draw, L_MARGIN, y, "Amount in words:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 135, y, "Rupees Four Thousand Five Hundred Only", size=12, color=DARK)
    y += 36

    _line(draw, y)
    y += 14
    _text(draw, R_MARGIN, y, "Authorised Signatory", size=12, bold=True, color=GRAY, anchor="ra")
    _signature(draw, R_MARGIN - 175, y + 28, width=150)
    draw.line([(R_MARGIN - 195, y + 62), (R_MARGIN, y + 62)], fill=LGRAY, width=1)
    _text(draw, R_MARGIN, y + 66, "Apollo Hospitals, Bengaluru", size=11, color=GRAY, anchor="ra")

    _stamp_circle(draw, L_MARGIN + 82, y + 44, r=52, line1="PAYMENT", line2="RECEIVED", color=RED_DARK)

    _text(draw, W // 2, H - 30, "Computer Generated Bill — No signature required.", size=10, color=LGRAY, anchor="mt")
    _text(draw, W // 2, H - 16, "For queries: billing-blr@apollohospitals.com", size=10, color=LGRAY, anchor="mt")

    img = _watermark(img, "ORIGINAL", angle=32, opacity=18)
    _save(img, "hospital_bill_priya_apollo.jpg")


# ── Document 5: Dental Bill — Amit Verma (TC006) ─────────────────────────────

def gen_dental_bill_amit() -> None:
    img, draw = _new_canvas()

    draw.rectangle([6, 6, W - 7, 92], fill=(30, 80, 160))
    _text(draw, W // 2, 14, "SMILE DENTAL CLINIC", size=26, bold=True, color=(255, 255, 255), anchor="mt")
    _text(draw, W // 2, 50, "34 Koramangala 5th Block, Bengaluru – 560 034", size=13, color=(185, 210, 245), anchor="mt")
    _text(draw, W // 2, 68, "BDS / MDS Specialists  |  Ph: +91-80-4056 7890", size=11, color=(160, 195, 235), anchor="mt")

    y = 108
    draw.rectangle([L_MARGIN, y, R_MARGIN, y + 56], fill=(235, 240, 255), outline=LGRAY, width=1)
    _text(draw, L_MARGIN + 10, y + 8,  "Bill No:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 70, y + 8,  "SDC/2024/1234", size=12, color=DARK)
    _text(draw, L_MARGIN + 10, y + 28, "Date:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 55, y + 28, "20-Oct-2024", size=12, color=DARK)
    _text(draw, L_MARGIN + 10, y + 48, "Dentist:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 70, y + 48, "Dr. Kavita Sharma, BDS MDS (Oral Surgery)", size=12, color=DARK)
    _text(draw, 430, y + 8,  "Patient:", size=12, bold=True, color=GRAY)
    _text(draw, 490, y + 8,  "Amit Verma", size=12, color=DARK)
    _text(draw, 430, y + 28, "Age/Sex:", size=12, bold=True, color=GRAY)
    _text(draw, 494, y + 28, "36 / Male", size=12, color=DARK)
    _text(draw, 430, y + 48, "Tooth:", size=12, bold=True, color=GRAY)
    _text(draw, 478, y + 48, "#36 (Lower Left Molar)", size=12, color=DARK)
    y += 56 + 20

    _text(draw, L_MARGIN, y, "Procedure Details:", size=14, bold=True, color=BLUE)
    y += 26

    cols   = ["PROCEDURE / SERVICE",       "SESSIONS", "RATE (₹)",  "AMOUNT (₹)"]
    widths = [INNER_W - 240,                80,         80,          80]
    rows = [
        ("Root Canal Treatment – Molar (RCT)", "3",  "8,000.00", "8,000.00"),
        ("Teeth Whitening – Full Arch",         "1",  "4,000.00", "4,000.00"),
    ]

    y = _table_header(draw, y, cols, widths)
    for i, row in enumerate(rows):
        y = _table_row(draw, y, list(row), widths, shaded=(i % 2 == 1))

    y += 10
    draw.line([(L_MARGIN, y), (R_MARGIN, y)], fill=LGRAY, width=1)
    y += 8
    _total_row(draw, y, "Sub-Total:", "₹ 12,000.00", widths)
    y += 30
    _table_row(draw, y, ["GST (Exempt)", "", "", "₹ 0.00"], widths)
    y += 26 + 4
    _total_row(draw, y, "TOTAL PAYABLE:", "₹ 12,000.00", widths)
    y += 30 + 24

    # Clinical notes
    draw.rectangle([L_MARGIN, y, R_MARGIN, y + 70], fill=(250, 252, 255), outline=LGRAY, width=1)
    _text(draw, L_MARGIN + 10, y + 8, "Clinical Notes:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 110, y + 8, "RCT completed in 3 sessions; permanent crown advised.", size=12, color=DARK)
    _text(draw, L_MARGIN + 10, y + 28, "Materials:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 90, y + 28, "GuttaPercha points, Zinc oxide eugenol cement", size=12, color=DARK)
    _text(draw, L_MARGIN + 10, y + 48, "Next Visit:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 90, y + 48, "Crown fitting — within 2 weeks", size=12, color=DARK)
    y += 70 + 20

    _text(draw, L_MARGIN, y, "Payment Mode:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 120, y, "UPI — PhonePe (Ref: PHPE2410201234)", size=13, color=DARK)
    y += 28

    _line(draw, y)
    y += 14
    _text(draw, R_MARGIN, y, "Dr. Kavita Sharma", size=12, bold=True, color=GRAY, anchor="ra")
    _signature(draw, R_MARGIN - 160, y + 24, width=130)
    draw.line([(R_MARGIN - 170, y + 55), (R_MARGIN, y + 55)], fill=LGRAY, width=1)
    _text(draw, R_MARGIN, y + 59, "Smile Dental Clinic", size=11, color=GRAY, anchor="ra")

    _stamp_circle(draw, L_MARGIN + 78, y + 36, r=50, line1="PAID", line2="FULL", color=RED_DARK)

    _text(draw, W // 2, H - 20, "Retain this receipt for insurance purposes.", size=10, color=LGRAY, anchor="mt")

    img = _watermark(img, "ORIGINAL", angle=30, opacity=20)
    _save(img, "dental_bill_amit.jpg")


# ── Document 6: Prescription — Sneha Reddy / Pharmacy (TC002 clear) ──────────

def gen_prescription_sneha() -> None:
    img, draw = _new_canvas()

    _text(draw, W // 2, 28, "Dr. Priya Mehta", size=24, bold=True, color=TEAL, anchor="mt")
    _text(draw, W // 2, 58, "MBBS, Dip. Family Medicine  |  Reg. No: KA/34567/2020", size=13, color=GRAY, anchor="mt")
    _text(draw, W // 2, 78, "HealthFirst Clinic, 78 Indiranagar 100ft Road, Bengaluru – 560 038", size=12, color=GRAY, anchor="mt")
    _text(draw, W // 2, 96, "Ph: +91-80-2523 4567  |  Open: Mon–Sat  9 AM–8 PM", size=11, color=GRAY, anchor="mt")

    y = _hbar(draw, 112, color=TEAL, height=2)

    draw.rectangle([L_MARGIN, y, R_MARGIN, y + 32], fill=(240, 250, 248), outline=LGRAY, width=1)
    _text(draw, L_MARGIN + 8, y + 9,  "Patient:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 68, y + 9, "Sneha Reddy", size=13, bold=True, color=DARK)
    _text(draw, 320, y + 9, "Age:", size=12, bold=True, color=GRAY)
    _text(draw, 355, y + 9, "28 yrs", size=12, color=DARK)
    _text(draw, 420, y + 9, "Sex:", size=12, bold=True, color=GRAY)
    _text(draw, 452, y + 9, "F", size=12, color=DARK)
    _text(draw, R_MARGIN - 8, y + 9, "Date: 10-Nov-2024", size=12, color=DARK, anchor="ra")
    y += 32 + 12

    _text(draw, L_MARGIN, y, "Diagnosis:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 90, y, "Acute Gastritis with Hyperacidity", size=13, color=DARK)
    y += 28
    y = _line(draw, y)

    _text(draw, L_MARGIN, y, "℞", size=28, bold=True, color=TEAL)
    y += 36

    meds = [
        ("1.", "Tab Pantoprazole 40 mg",     "— 1-0-0 × 7 days    (Empty stomach, 30 min before breakfast)"),
        ("2.", "Syp Digene (Antacid)",        "— 10 ml TDS × 5 days (After meals)"),
        ("3.", "Tab Domperidone 10 mg",       "— 1-1-1 × 3 days    (Before meals)"),
    ]
    for num, drug, dosage in meds:
        _text(draw, L_MARGIN + 4,  y, num,  size=13, color=GRAY)
        _text(draw, L_MARGIN + 22, y, drug, size=13, bold=True, color=DARK)
        _text(draw, L_MARGIN + 22, y + 18, dosage, size=12, color=GRAY)
        y += 44

    y = _line(draw, y + 4)

    _text(draw, L_MARGIN, y, "Diet Advice:", size=13, bold=True, color=GRAY)
    y += 22
    for a in ["• Avoid spicy, oily, and fried food", "• No coffee, alcohol, or carbonated drinks",
              "• Small, frequent meals — every 3 hours"]:
        _text(draw, L_MARGIN + 12, y, a, size=12, color=GRAY)
        y += 20

    y += 10
    _text(draw, L_MARGIN, y, "Follow-up:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 80, y, "After 1 week or if symptoms persist", size=13, color=DARK)

    y = 890
    _line(draw, y)
    y += 10
    _signature(draw, L_MARGIN + 30, y + 20, width=120)
    draw.line([(L_MARGIN, y + 50), (L_MARGIN + 200, y + 50)], fill=LGRAY, width=1)
    _text(draw, L_MARGIN, y + 54, "Dr. Priya Mehta, MBBS", size=12, bold=True, color=DARK)
    _text(draw, L_MARGIN, y + 72, "HealthFirst Clinic, Bengaluru", size=11, color=GRAY)

    _stamp_circle(draw, R_MARGIN - 75, y + 42, r=48, line1="CLINIC", line2="SEAL", color=TEAL)

    img = _watermark(img, "PRESCRIPTION", angle=28, opacity=18, size=64)
    _save(img, "prescription_sneha_pharmacy.jpg")


# ── Document 7: Pharmacy Bill — Sneha Reddy (TC002 — BLURRY) ─────────────────

def gen_pharmacy_bill_sneha_blurry() -> None:
    img, draw = _new_canvas()

    # Generate a clear pharmacy bill first
    draw.rectangle([6, 6, W - 7, 85], fill=(40, 120, 80))
    _text(draw, W // 2, 16, "MEDPLUS PHARMACY", size=24, bold=True, color=(255, 255, 255), anchor="mt")
    _text(draw, W // 2, 48, "78 Indiranagar 100ft Road, Bengaluru – 560 038", size=13, color=(200, 235, 215), anchor="mt")
    _text(draw, W // 2, 66, "DL No: KA-2020-BLR-04521  |  Ph: +91-80-2345 6789", size=11, color=(170, 215, 190), anchor="mt")

    y = 100
    draw.rectangle([L_MARGIN, y, R_MARGIN, y + 50], fill=(235, 250, 240), outline=LGRAY, width=1)
    _text(draw, L_MARGIN + 10, y + 8,  "Bill No:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 70, y + 8,  "MED/2024/78901", size=12, color=DARK)
    _text(draw, L_MARGIN + 10, y + 28, "Date:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 55, y + 28, "10-Nov-2024", size=12, color=DARK)
    _text(draw, 430, y + 8,  "Patient:", size=12, bold=True, color=GRAY)
    _text(draw, 490, y + 8,  "Sneha Reddy", size=12, color=DARK)
    _text(draw, 430, y + 28, "Rx by:", size=12, bold=True, color=GRAY)
    _text(draw, 475, y + 28, "Dr. Priya Mehta", size=12, color=DARK)
    y += 50 + 18

    cols   = ["MEDICINE / PRODUCT",           "QTY", "RATE (₹)", "AMOUNT (₹)"]
    widths = [INNER_W - 230,                   60,    85,         85]
    rows = [
        ("Tab Pantoprazole 40mg (Pantop)",      "14",  "8.50",   "119.00"),
        ("Syp Digene 200ml",                   "1",  "120.00", "120.00"),
        ("Tab Domperidone 10mg (Domstal)",     "10",   "6.00",   "60.00"),
        ("ORS Sachet Electral (Pack of 4)",    "2",   "50.00",  "100.00"),
    ]

    y = _table_header(draw, y, cols, widths)
    for i, row in enumerate(rows):
        y = _table_row(draw, y, list(row), widths, shaded=(i % 2 == 1))

    y += 10
    draw.line([(L_MARGIN, y), (R_MARGIN, y)], fill=LGRAY, width=1)
    y += 8
    _total_row(draw, y, "Sub-Total:", "₹ 399.00", widths)
    y += 30
    _table_row(draw, y, ["Discount (5%)", "", "", "- ₹ 19.95"], widths)
    y += 26 + 4
    _total_row(draw, y, "NET PAYABLE:", "₹ 379.05", widths)
    y += 30 + 20

    _text(draw, L_MARGIN, y, "Payment:", size=13, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 80, y, "Cash — Amount Received ₹ 400.00 | Change ₹ 20.95", size=13, color=DARK)
    y += 28

    _line(draw, y)
    _text(draw, W // 2, y + 14, "Thank you! Get well soon.", size=12, bold=True, color=GRAY, anchor="mt")
    _text(draw, W // 2, y + 34, "Store medicines in a cool, dry place. Keep out of reach of children.", size=10, color=GRAY, anchor="mt")

    _stamp_circle(draw, L_MARGIN + 78, y + 60, r=50, line1="CASH MEMO", line2="DUPLICATE", color=(100, 100, 100))

    # Now apply heavy blur to simulate a blurry photograph
    img = img.filter(ImageFilter.GaussianBlur(radius=6))
    # Add extra noise to simulate a phone photo in bad lighting
    img = img.filter(ImageFilter.GaussianBlur(radius=3))

    _save(img, "pharmacy_bill_sneha_blurry.jpg")


# ── Document 8: Lab Report — Rajesh Kumar (Generic) ──────────────────────────

def gen_lab_report_rajesh() -> None:
    img, draw = _new_canvas()

    draw.rectangle([6, 6, W - 7, 95], fill=(55, 40, 110))
    _text(draw, W // 2, 14, "PRECISION DIAGNOSTICS PVT. LTD.", size=22, bold=True, color=(255, 255, 255), anchor="mt")
    _text(draw, W // 2, 46, "NABL Accredited Laboratory  |  Lab ID: KA-NABL-1234", size=13, color=(210, 200, 240), anchor="mt")
    _text(draw, W // 2, 64, "45 Science Park, Whitefield, Bengaluru – 560 066", size=12, color=(185, 178, 225), anchor="mt")
    _text(draw, W // 2, 80, "Ph: +91-80-6678 9000  |  lab@precisiondiag.in", size=10, color=(165, 158, 210), anchor="mt")

    y = 110
    draw.rectangle([L_MARGIN, y, R_MARGIN, y + 66], fill=(245, 243, 255), outline=LGRAY, width=1)
    pairs = [
        ("Patient:",       "Rajesh Kumar",         430, "Sample Date:", "01-Nov-2024"),
        ("Age / Sex:",     "39 Years / Male",       430, "Report Date:", "01-Nov-2024"),
        ("Ref. Doctor:",   "Dr. Arun Sharma",       430, "Sample No.:",  "PRE/2024/9821"),
        ("Reg. No.:",      "PREC-EMP001-24-1101",   430, "Lab No.:",     "LAB-BLR-004521"),
    ]
    for i, (lbl, val, rx, rlbl, rval) in enumerate(pairs):
        row_y = y + 8 + i * 15
        _text(draw, L_MARGIN + 8, row_y, lbl, size=11, bold=True, color=GRAY)
        _text(draw, L_MARGIN + 90, row_y, val, size=11, color=DARK)
        _text(draw, rx, row_y, rlbl, size=11, bold=True, color=GRAY)
        _text(draw, rx + 80, row_y, rval, size=11, color=DARK)
    y += 66 + 16

    _text(draw, W // 2, y, "HAEMATOLOGY REPORT", size=16, bold=True, color=(55, 40, 110), anchor="mt")
    y += 28

    cols   = ["TEST NAME",               "RESULT",    "UNIT",  "NORMAL RANGE",    "STATUS"]
    widths = [240,                         110,          75,      155,              140]

    y = _table_header(draw, y, cols, widths)

    results_data = [
        ("Haemoglobin",           "13.2",         "g/dL",    "13.0 – 17.0",    "NORMAL", False),
        ("Total WBC Count",       "9,800",         "/µL",     "4,500 – 11,000", "NORMAL", False),
        ("Neutrophils",           "72",            "%",       "40 – 75",        "NORMAL", True),
        ("Lymphocytes",           "22",            "%",       "20 – 45",        "NORMAL", False),
        ("Platelet Count",        "1,85,000",      "/µL",     "1,50,000–4,50,000","NORMAL",True),
        ("ESR (1 hour)",          "18",            "mm/hr",   "0 – 20",         "NORMAL", False),
        ("RBC Count",             "4.8",           "mil/µL",  "4.5 – 5.5",      "NORMAL", True),
        ("Packed Cell Volume",    "42",            "%",       "40 – 54",        "NORMAL", False),
        ("MCV",                   "88",            "fL",      "80 – 100",       "NORMAL", True),
        ("MCH",                   "27",            "pg",      "27 – 32",        "NORMAL", False),
    ]

    for test, result, unit, ref, status, shaded in results_data:
        col_color = (20, 130, 20) if status == "NORMAL" else (180, 20, 20)
        row = [test, result, unit, ref, status]
        row_y = y
        total = sum(widths)
        if shaded:
            draw.rectangle([L_MARGIN, row_y, L_MARGIN + total, row_y + 26], fill=(248, 250, 248))
        draw.rectangle([L_MARGIN, row_y, L_MARGIN + total, row_y + 26], outline=LGRAY, width=1)
        x = L_MARGIN
        for j, (val, w) in enumerate(zip(row, widths)):
            use_color = col_color if j == 4 else DARK
            use_bold = (j == 4)
            _text(draw, x + 6, row_y + 6, val, size=11, bold=use_bold, color=use_color)
            if x + w < L_MARGIN + total:
                draw.line([(x + w, row_y), (x + w, row_y + 26)], fill=LGRAY, width=1)
            x += w
        y += 26

    y += 16

    # Dengue
    _text(draw, W // 2, y, "SEROLOGY", size=14, bold=True, color=(55, 40, 110), anchor="mt")
    y += 22
    cols2   = ["TEST",               "RESULT",      "METHOD",        "INTERPRETATION"]
    widths2 = [220,                   100,            160,             240]
    y = _table_header(draw, y, cols2, widths2)
    serology = [("Dengue NS1 Antigen", "NEGATIVE", "ELISA Method", "No active dengue infection detected")]
    for row in serology:
        row_y = y
        total = sum(widths2)
        draw.rectangle([L_MARGIN, row_y, L_MARGIN + total, row_y + 28], fill=(235, 250, 240))
        draw.rectangle([L_MARGIN, row_y, L_MARGIN + total, row_y + 28], outline=LGRAY, width=1)
        x = L_MARGIN
        for val, w in zip(row, widths2):
            col = (20, 130, 20) if val == "NEGATIVE" else DARK
            _text(draw, x + 6, row_y + 7, val, size=11, bold=(val == "NEGATIVE"), color=col)
            if x + w < L_MARGIN + total:
                draw.line([(x + w, row_y), (x + w, row_y + 28)], fill=LGRAY, width=1)
            x += w
        y += 28

    y += 16
    draw.rectangle([L_MARGIN, y, R_MARGIN, y + 44], fill=(255, 250, 235), outline=LGRAY, width=1)
    _text(draw, L_MARGIN + 10, y + 8,  "Remarks:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 10, y + 26, "WBC count towards upper limit of normal. Dengue NS1 Antigen negative. Clinical correlation advised.", size=11, color=DARK)
    y += 44 + 18

    _line(draw, y)
    y += 12
    _text(draw, L_MARGIN, y, "Verified by:", size=12, bold=True, color=GRAY)
    _text(draw, L_MARGIN + 88, y, "Dr. Meena Pillai, MD (Pathology)  |  RGUHS Reg. No: 45678", size=12, color=DARK)
    y += 22
    _signature(draw, L_MARGIN + 20, y + 10, width=120)
    draw.line([(L_MARGIN, y + 42), (L_MARGIN + 200, y + 42)], fill=LGRAY, width=1)
    _text(draw, L_MARGIN, y + 46, "Dr. Meena Pillai, MD", size=11, bold=True, color=DARK)
    _text(draw, L_MARGIN, y + 62, "Consultant Pathologist", size=10, color=GRAY)

    _stamp_circle(draw, R_MARGIN - 80, y + 40, r=52, line1="NABL", line2="CERTIFIED", color=(55, 40, 110))

    _text(draw, W // 2, H - 28, "This report is electronically verified. Results are valid for 30 days.", size=10, color=LGRAY, anchor="mt")
    _text(draw, W // 2, H - 14, "For queries: lab@precisiondiag.in | Ph: +91-80-6678 9000", size=9, color=LGRAY, anchor="mt")

    _save(img, "lab_report_sample.jpg")


# ── Save helper ───────────────────────────────────────────────────────────────

def _save(img: Image.Image, filename: str) -> None:
    path = OUT_DIR / filename
    img.save(path, "JPEG", quality=92, subsampling=0)
    print(f"  ✓  {filename}  ({path.stat().st_size // 1024} KB)")


# ── README ────────────────────────────────────────────────────────────────────

def _write_readme() -> None:
    content = """\
# Sample Medical Documents

Realistic Indian medical document images generated for testing the Plum Claims Processor.
Upload these to the **Submit Claim** page (manual entry mode) to test real GPT-4o Vision processing.

## Documents

### TC004 — Clean Consultation Approval (Rajesh Kumar / City Medical Centre)
- `prescription_rajesh_consultation.jpg` — Dr. Arun Sharma prescription, viral fever
- `hospital_bill_rajesh_consultation.jpg` — City Medical Centre bill, ₹1,500 total

**How to use**: Member EMP001, Category CONSULTATION, Amount ₹1,500, Date 2024-11-01.
Expected outcome: **APPROVED** for ₹1,350 (10% co-pay).

### TC010 — Network Hospital Discount (Priya Singh / Apollo Hospitals)
- `prescription_priya_consultation.jpg` — Dr. Meena Reddy, Apollo Hospitals
- `hospital_bill_priya_apollo.jpg` — Apollo bill, ₹4,500 total

**How to use**: Member EMP002 (or any member), Category CONSULTATION, Amount ₹4,500,
Hospital Name **Apollo Hospitals**, Date 2024-10-15.
Expected outcome: **APPROVED** for ₹3,240 (20% network discount + 10% co-pay).

### TC006 — Dental Partial Approval (Amit Verma)
- `dental_bill_amit.jpg` — Smile Dental Clinic, Root Canal (₹8,000) + Teeth Whitening (₹4,000)

**How to use**: Member EMP002, Category DENTAL, Amount ₹12,000, Date 2024-10-20.
Expected outcome: **PARTIAL** approval of ₹8,000 (Teeth Whitening excluded as cosmetic).

### TC002 — Blurry Document Test (Sneha Reddy)
- `prescription_sneha_pharmacy.jpg` — Clear prescription from HealthFirst Clinic
- `pharmacy_bill_sneha_blurry.jpg` — **Intentionally blurry** pharmacy bill (heavy Gaussian blur)

**How to use**: Member EMP004, Category PHARMACY, Amount ₹380, Date 2024-11-10.
Expected outcome: **STOPPED EARLY** — system detects unreadable pharmacy bill.

### Generic Lab Report
- `lab_report_sample.jpg` — Precision Diagnostics, CBC + Dengue NS1 for Rajesh Kumar

**How to use**: Add as optional Lab Report when submitting a Consultation or Diagnostic claim.

## Notes
- All documents are 800×1100 px JPEG, quality 92
- Generated using Pillow — no real patient data
- The blurry pharmacy bill tests TC002 (unreadable document detection)
"""
    (OUT_DIR / "README.md").write_text(content)
    print("  ✓  README.md")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\nGenerating sample documents → {OUT_DIR}\n")

    random.seed(42)

    generators = [
        ("Prescription — Rajesh Kumar (TC004)",         gen_prescription_rajesh),
        ("Hospital Bill — Rajesh Kumar (TC004)",         gen_bill_rajesh),
        ("Prescription — Priya Singh / Apollo (TC010)",  gen_prescription_priya),
        ("Hospital Bill — Priya Singh / Apollo (TC010)", gen_bill_priya_apollo),
        ("Dental Bill — Amit Verma (TC006)",             gen_dental_bill_amit),
        ("Prescription — Sneha Reddy (TC002 clear)",     gen_prescription_sneha),
        ("Pharmacy Bill — Sneha Reddy (TC002 BLURRY)",   gen_pharmacy_bill_sneha_blurry),
        ("Lab Report — Rajesh Kumar (Generic)",          gen_lab_report_rajesh),
        ("README",                                       _write_readme),
    ]

    for label, fn in generators:
        print(f"  {label}")
        fn()

    total = len(list(OUT_DIR.glob("*.jpg")))
    print(f"\n✅  Done — {total} documents in {OUT_DIR}\n")


if __name__ == "__main__":
    main()
