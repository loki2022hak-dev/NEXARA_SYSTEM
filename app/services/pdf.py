import os, qrcode
from fpdf import FPDF
import datetime

class NexaraPDF(FPDF):
    def __init__(self):
        super().__init__()
        # Шлях до шрифтів у Debian/Ubuntu Docker image
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        font_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        
        if os.path.exists(font_path):
            self.add_font("DejaVu", "", font_path, unicode=True)
            self.add_font("DejaVu", "B", font_bold, unicode=True)
        else:
            # Fallback для локальної розробки
            self.add_font("DejaVu", "", "DejaVuSans.ttf", unicode=True)

    def header(self):
        self.set_fill_color(15, 20, 30)
        self.rect(0, 0, 210, 297, 'F')
        self.set_font('DejaVu', 'B', 45)
        self.set_text_color(25, 35, 50)
        self.text(15, 150, "NEXARA CONFIDENTIAL")
        self.set_text_color(0, 195, 255)
        self.set_font('DejaVu', 'B', 16)
        self.cell(0, 10, 'NEXARA: АНАЛІТИЧНИЙ ЗВІТ', 0, 1, 'C')
        self.set_font('DejaVu', '', 9)
        self.set_text_color(150, 150, 150)
        self.cell(0, 5, f'UTC: {datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'R')
        self.ln(5)

def build_pdf_report(target: str, report_text: str, user_id: int):
    path = f"reports/report_{user_id}.pdf"
    qr = qrcode.make(f"NEXARA-VERIFY: {target}")
    qr_path = f"reports/qr_{user_id}.png"
    qr.save(qr_path)
    pdf = NexaraPDF()
    pdf.add_page()
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('DejaVu', 'B', 14)
    pdf.cell(0, 10, f"ЦІЛЬ: {target}", 1, 1, fill=True)
    pdf.ln(5)
    pdf.set_font('DejaVu', '', 10)
    pdf.set_text_color(220, 220, 220)
    pdf.multi_cell(0, 6, report_text)
    try:
        pdf.image(qr_path, x=170, y=260, w=25)
        os.remove(qr_path)
    except: pass
    pdf.output(path)
    return path
