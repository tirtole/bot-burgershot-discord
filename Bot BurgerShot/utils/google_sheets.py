import re
from datetime import datetime

import gspread

from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE, FACTURE_SHEET_NAME


# On s'arrête à "Effectué :"
# Les colonnes Autocrat après ça ne sont pas remplies par le bot.
FACTURE_COLUMNS_COUNT = 25


def get_facture_sheet():
    client = gspread.service_account(filename=GOOGLE_CREDENTIALS_FILE)
    spreadsheet = client.open_by_key(GOOGLE_SHEET_ID)
    return spreadsheet.worksheet(FACTURE_SHEET_NAME)


def clean_number(value: str):
    value = str(value).strip()
    value = value.replace("€", "").replace("$", "").replace(" ", "")
    value = value.replace(",", ".")

    number = float(value)

    if number.is_integer():
        return int(number)

    return number


def get_next_facture_number(sheet):
    facture_numbers = sheet.col_values(6)

    max_number = 0

    for value in facture_numbers[1:]:
        value = str(value).strip()
        match = re.search(r"(\d+)", value)

        if match:
            number = int(match.group(1))
            max_number = max(max_number, number)

    return f"#{max_number + 1:04d}"


def append_facture_row(
    entreprise: str,
    adresse: str,
    mail: str,
    destinataire: str,
    telephone: str,
    items: list[dict],
    note: str | None = None,
    effectue: bool = False
):
    if not items:
        raise ValueError("Tu dois ajouter au moins 1 item.")

    if len(items) > 5:
        raise ValueError("Tu peux mettre maximum 5 items par facture.")

    sheet = get_facture_sheet()

    numero_facture = get_next_facture_number(sheet)
    date_facture = datetime.now().strftime("%d/%m/%Y")

    total = 0

    cleaned_items = []

    for item in items:
        nom = str(item["nom"]).strip()
        quantite = clean_number(item["quantite"])
        prix = clean_number(item["prix"])

        if not nom:
            raise ValueError("Un item ne peut pas avoir un nom vide.")

        if quantite <= 0:
            raise ValueError(f"La quantité de `{nom}` doit être supérieure à 0.")

        if prix < 0:
            raise ValueError(f"Le prix de `{nom}` ne peut pas être négatif.")

        item_total = quantite * prix
        total += item_total

        cleaned_items.append({
            "nom": nom,
            "quantite": quantite,
            "prix": prix,
            "total": item_total
        })

    if note is None or not str(note).strip():
        note = f"Facture {entreprise}"

    row = [""] * FACTURE_COLUMNS_COUNT

    row[0] = entreprise
    row[1] = adresse
    row[2] = mail
    row[3] = destinataire
    row[4] = telephone
    row[5] = numero_facture
    row[6] = date_facture

    for index, item in enumerate(cleaned_items):
        row[7 + index] = item["nom"]
        row[12 + index] = item["quantite"]
        row[17 + index] = item["prix"]

    row[22] = total
    row[23] = note
    row[24] = "Oui" if effectue else "Non"

    sheet.append_row(row, value_input_option="USER_ENTERED")

    return {
        "numero_facture": numero_facture,
        "date": date_facture,
        "entreprise": entreprise,
        "adresse": adresse,
        "mail": mail,
        "destinataire": destinataire,
        "telephone": telephone,
        "items": cleaned_items,
        "total": total,
        "note": note,
        "effectue": "Oui" if effectue else "Non"
    }