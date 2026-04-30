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
