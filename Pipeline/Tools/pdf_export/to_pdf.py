"""
to_pdf.py
----------
Converts Full_Archive.txt (or any file in the same format) into a
printable, shareable PDF — one paragraph per message, grouped under date
headers, with WhatsApp's *bold*/_italic_/~strike~ formatting rendered
and media placeholder lines skipped.

Usage:
    python3 to_pdf.py [input.txt] [output.pdf]

Both arguments are optional:
    input.txt   defaults to the repo's own Full_Archive.txt
    output.pdf  defaults to Full_Archive.pdf at the project root

Requires NotoSans-Regular.ttf in the shared Tools/fonts/ folder (not
included in this repo for size reasons — download it from Google Fonts
and place it there) so the PDF renders correctly. That font folder is
shared with chat_analyzer's PDF export, so it only needs to be set up
once for both tools.
"""
import re
import sys
from pathlib import Path
from datetime import datetime

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from xml.sax.saxutils import escape

# This file lives at Pipeline/Tools/pdf_export/to_pdf.py.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_INPUT = REPO_ROOT / "Full_Archive.txt"
DEFAULT_OUTPUT = REPO_ROOT / "Full_Archive.pdf"
# Shared with chat_analyzer's pdf_report.py — one font folder for the
# whole Pipeline instead of a separate copy per tool.
FONT_DIR = SCRIPT_DIR.parent / "fonts"
FONT_PATH = FONT_DIR / "NotoSans-Regular.ttf"

# -----------------------------
# Fonts
# -----------------------------

if not FONT_PATH.exists():
    sys.exit(
        f"Font file not found: {FONT_PATH}\n"
        f"Download NotoSans-Regular.ttf (Google Fonts) and place it in "
        f"{FONT_DIR} before running this script."
    )

pdfmetrics.registerFont(
    TTFont(
        "NotoSans",
        str(FONT_PATH)
    )
)


# -----------------------------
# WhatsApp format
# -----------------------------

MESSAGE_PATTERN = re.compile(
    r"^(\d{2}-[A-Za-z]{3}-\d{4}), "
    r"(\d{2}:\d{2}(?::\d{2})?) - "
    r"(.*?): (.*)$"
)


MEDIA_WORDS = [
    "image omitted",
    "video omitted",
    "audio omitted",
    "sticker omitted",
    "gif omitted",
    "media omitted",
    "<media omitted>"
]


# -----------------------------
# Formatting
# -----------------------------

def whatsapp_format(text):

    text = escape(text)

    # bold
    text = re.sub(
        r"\*(.*?)\*",
        r"<b>\1</b>",
        text
    )

    # italic
    text = re.sub(
        r"_(.*?)_",
        r"<i>\1</i>",
        text
    )

    # strike
    text = re.sub(
        r"~(.*?)~",
        r"<strike>\1</strike>",
        text
    )

    # line breaks
    text = text.replace(
        "\n",
        "<br/>"
    )

    return text



# -----------------------------
# Styles
# -----------------------------

def styles():

    base = getSampleStyleSheet()

    return {

        "date":
        ParagraphStyle(
            "date",
            parent=base["Heading2"],
            fontName="NotoSans",
            fontSize=13,
            alignment=1,
            spaceBefore=15,
            spaceAfter=15
        ),

        "sender":
        ParagraphStyle(
            "sender",
            fontName="NotoSans",
            fontSize=10,
            spaceAfter=2
        ),

        "message":
        ParagraphStyle(
            "message",
            fontName="NotoSans",
            fontSize=10,
            leading=14,
            spaceAfter=8
        )
    }



# -----------------------------
# Main converter
# -----------------------------

def convert(txt, pdf):

    doc = SimpleDocTemplate(
        pdf,
        pagesize=A5,
        rightMargin=35,
        leftMargin=35,
        topMargin=40,
        bottomMargin=40
    )


    style = styles()

    content = []

    current_date = None


    with open(
        txt,
        encoding="utf-8",
        errors="replace"
    ) as f:


        for raw in f:

            line = raw.rstrip()


            if not line:
                continue


            match = MESSAGE_PATTERN.match(line)


            if match:

                date, time, sender, msg = match.groups()


                # Date header

                if date != current_date:

                    current_date = date

                    pretty_date = datetime.strptime(
                        date,
                        "%d-%b-%Y"
                    ).strftime(
                        "%d %B %Y"
                    )


                    content.append(
                        Paragraph(
                            pretty_date,
                            style["date"]
                        )
                    )


                # Ignore media

                lower = msg.lower()

                if any(
                    x in lower
                    for x in MEDIA_WORDS
                ):
                    continue


                content.append(
                    Paragraph(
                        f"<b>{escape(sender)}</b> "
                        f"<font size='8'>"
                        f"{time}</font>",
                        style["sender"]
                    )
                )


                content.append(
                    Paragraph(
                        whatsapp_format(msg),
                        style["message"]
                    )
                )


            else:

                # continuation of previous message

                content.append(
                    Paragraph(
                        whatsapp_format(line),
                        style["message"]
                    )
                )


    doc.build(content)



if __name__ == "__main__":

    if len(sys.argv) > 3:
        sys.exit("Usage: python3 to_pdf.py [input.txt] [output.pdf]")

    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_INPUT
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUTPUT

    if not input_path.exists():
        sys.exit(f"Input file not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    convert(
        str(input_path),
        str(output_path)
    )

    print(f"Finished: {output_path}")