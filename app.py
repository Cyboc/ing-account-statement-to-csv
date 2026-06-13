import pdfplumber
import pandas as pd
import re
from pathlib import Path

PDF_DIR = Path("kontoauszuege")
OUTPUT_CSV = "firefly_import.csv"
STOP_PREFIXES = ("Neuer Saldo", "ING-DiBa AG", "Girokonto Nummer")

date_pattern = re.compile(r"^\d{2}\.\d{2}\.\d{4}")

line1_pattern = re.compile(
    r"^"
    r"(\d{2}\.\d{2}\.\d{4})\s+"
    r"(\S+)"
    r"(?:\s+(.+))?"
    r"\s+(-?\d[\d\.]*,\d{2})"
    r"$"
)

line2_pattern = re.compile(
    r"^"
    r"(\d{2}\.\d{2}\.\d{4})\s+"
    r"(.+)"
    r"$"
)

transactions = []

def is_stop_line(line: str) -> bool:
    return line.startswith(STOP_PREFIXES)

current = None  # hält laufende Buchung

def flush_current():
    global current
    if current:
        transactions.append(current)
        current = None

for pdf_file in PDF_DIR.glob("*.pdf"):
    print(f"Verarbeite: {pdf_file.name}")

    lines = []

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.extend([l.strip() for l in text.splitlines() if l.strip()])

    i = 0

    while i < len(lines):
        line = lines[i]

        # Fußnoten-Artefakte entfernen
        line = re.sub(r"(,\d{2})\d\b", r"\1", line)

        # neue Buchung beginnt
        if date_pattern.match(line):

            match1 = line1_pattern.match(line)

            if match1:
                flush_current()

                booking_date = match1.group(1)
                booking_type = match1.group(2)
                counterparty = match1.group(3) or ""
                amount = match1.group(4)

                amount_float = float(
                    amount.replace(".", "").replace(",", ".")
                )

                current = {
                    "Buchungsdatum": booking_date,
                    "Valuta": "",
                    "SenderEmpfaenger": counterparty,
                    "Buchungstyp": booking_type,
                    "Verwendungszweck_parts": [],   # <- neu
                    "Betrag": amount_float
                }

                i += 1

                # nächste Zeile: Start Verwendungszweck (falls vorhanden)
                if i < len(lines):
                    next_line = lines[i]

                    match2 = line2_pattern.match(next_line)

                    if match2:
                        current["Valuta"] = match2.group(1)
                        current["Verwendungszweck_parts"].append(match2.group(2).strip())

                        i += 1

                        # weitere Folgezeilen = Verwendungszweck
                        while i < len(lines):
                            line = lines[i].strip()

                            if date_pattern.match(line):
                                break

                            if is_stop_line(line):
                                break

                            current["Verwendungszweck_parts"].append(line)

                            i += 1

                        current["Verwendungszweck"] = ", ".join(
                            part for part in current["Verwendungszweck_parts"] if part
                        )

                        del current["Verwendungszweck_parts"]

                continue

        i += 1

# letzte Buchung flushen
flush_current()

df = pd.DataFrame(transactions)

df.to_csv(
    OUTPUT_CSV,
    index=False,
    sep=";"
)

print(f"\nExportiert: {OUTPUT_CSV}")
print(f"Transaktionen: {len(df)}")
