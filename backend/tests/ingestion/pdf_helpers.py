from fpdf import FPDF
from fpdf.enums import XPos, YPos


def make_pdf_bytes(text: str, *, title: str | None = None) -> bytes:
    """Build a minimal real PDF for loader tests, so parsing is exercised
    against actual PDF bytes rather than a hand-rolled fixture format."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    if title:
        pdf.set_title(title)
    for line in text.split("\n"):
        # Without an explicit cursor reset, multi_cell leaves `x` wherever
        # the previous line ended, so the next call's available width
        # (measured to the right margin) shrinks toward zero.
        pdf.multi_cell(0, 10, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    return bytes(pdf.output())
