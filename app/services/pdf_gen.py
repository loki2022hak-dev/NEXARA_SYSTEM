from fpdf import FPDF
import datetime, os

class NexaraPDF(FPDF):
    def header(self):
        self.set_fill_color(15, 15, 25)
        self.rect(0, 0, 210, 297, 'F')
        self.set_text_color(0, 195, 255)
        self.add_font("DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", unicode=True)
        self.set_font("DejaVu", "", 16)
        self.cell(0, 10, "NEXARA INTELLIGENCE REPORT", 0, 1, 'C')
        self.set_draw_color(0, 195, 255)
        self.line(10, 20, 200, 20)

def generate_report_v2(target, data, path):
    pdf = NexaraPDF()
    pdf.add_page()
    pdf.set_text_color(200, 200, 200)
    pdf.set_font("DejaVu", "", 10)
    
    content = f"Об'єкт: {target}\nДата: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
    content += "АНАЛІТИЧНИЙ ЗВІТ (ОДКРИТІ ДЖЕРЕЛА):\n" + "-"*40 + "\n"
    content += data
    
    pdf.multi_cell(0, 7, content)
    pdf.set_y(-20)
    pdf.set_font("DejaVu", "", 8)
    pdf.cell(0, 10, f"NEXARA SECURITY VERIFIED | QR: {hash(target)}", 0, 0, 'R')
    pdf.output(path)
