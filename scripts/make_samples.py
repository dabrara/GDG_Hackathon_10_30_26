import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

DOCS = {
"bill": """RIVERSIDE GENERAL HOSPITAL - PATIENT STATEMENT
Statement date: 02 Nov 2026     Account: 88-2210-4
Patient: Jordan Rivera

Services
10/12/2026  Emergency visit, level 3 ............ $1,240.00
10/12/2026  Lab panel (CBC) ...................... $185.00
10/12/2026  Lab panel (CBC) ...................... $185.00
10/12/2026  X-ray, wrist, 2 views ................ $310.00
Insurance adjustment ............................. -$720.00
Total patient responsibility ..................... $1,200.00

Payment due by 02 Dec 2026. A late fee of $35 applies after this date.
Questions? Call Billing at 555-0142, Mon-Fri 9am-5pm.
Financial assistance may be available. Ask for an application.""",
"rx": """PHARMACY LABEL
Rx 5530921   Dr. A. Mensah
LISINOPRIL 10 MG TABLETS
Take 1 tablet by mouth once daily.
May cause dizziness. Do not use potassium supplements
without asking your doctor. Avoid pregnancy.
Qty: 30   Refills: 2   Discard after: 10/2027
Questions? Call pharmacy 555-0199""",
"lease": """RESIDENTIAL LEASE - SECTION 7 AND 9
7. Rent is $1,850 per month, due on the 1st. A late fee of 8%
of monthly rent is charged if rent is received after the 5th.
9. Tenant must give 60 days written notice before moving out.
Failure to give notice forfeits the security deposit of $1,850.
Lease auto-renews for 12 months unless notice is given
at least 60 days before 31 Jan 2027.""",
}

out = Path(__file__).resolve().parent.parent / "samples"; out.mkdir(exist_ok=True)
try:
    font = ImageFont.truetype("DejaVuSans.ttf", 26)
except Exception:
    font = ImageFont.load_default()
for name, text in DOCS.items():
    wrapped = [w for line in text.split("\n") for w in (textwrap.wrap(line, 62) or [""])]
    img = Image.new("RGB", (1150, max(1100, 80 + 36 * len(wrapped))), "white"); d = ImageDraw.Draw(img); y = 40
    for line in text.split("\n"):
        for w in (textwrap.wrap(line, 62) or [""]):
            d.text((50, y), w, fill="black", font=font); y += 36
    img.save(out / f"{name}.png")
print("wrote", list(out.iterdir()))
