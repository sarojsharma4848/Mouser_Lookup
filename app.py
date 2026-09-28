"""
Mouser Part Number Lookup - Web App
------------------------------------
Upload a CSV, pick which column holds the part numbers, and get back
detailed product info (manufacturer, description, availability, price
breaks, etc.) pulled live from the Mouser Search API.

Run locally:
    pip install -r requirements.txt
    export MOUSER_API_KEY=your_key_here   # or paste it in the web form
    python app.py

Then open http://127.0.0.1:5000 in your browser.

Author: Saroj Sharma
"""

import base64
import csv
import io
import json
import os
import re

import requests
from flask import Flask, render_template, request, flash, redirect, url_for

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-me")

MOUSER_SEARCH_URL = "https://api.mouser.com/api/v1/search/partnumber"

# Mouser returns prices in USD; this is used purely to show an approximate
# converted figure for procurement teams working in another currency.
FX_RATE_URL = "https://api.frankfurter.app/latest"


def get_exchange_rate(target_currency):
    """Fetch a live USD -> target_currency rate. Returns (rate, date) or (None, None) on failure."""
    if target_currency == "USD":
        return 1.0, None

    try:
        response = requests.get(
            FX_RATE_URL,
            params={"base": "USD", "symbols": target_currency},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        rate = data.get("rates", {}).get(target_currency)
        return (rate, data.get("date")) if rate else (None, None)
    except requests.exceptions.RequestException:
        return None, None


def parse_price(price_str):
    """Mouser prices come back like '$1.23' or '' - pull out the float."""
    if not price_str:
        return None
    match = re.search(r"[\d.]+", price_str.replace(",", ""))
    return float(match.group()) if match else None


class MouserAPI:
    """Thin wrapper around the Mouser Search API v1."""

    def __init__(self, api_key):
        self.api_key = api_key
        self.url = f"{MOUSER_SEARCH_URL}?apiKey={self.api_key}"

    def search_part(self, part_number):
        """Look up a single part by exact Mouser part number.

        Returns (product_dict_or_None, error_message_or_None).
        """
        payload = {"SearchByPartRequest": {"mouserPartNumber": part_number}}

        try:
            response = requests.post(self.url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.HTTPError:
            return None, f"HTTP error {response.status_code}"
        except requests.exceptions.RequestException as exc:
            return None, f"Request failed: {exc}"
        except Exception as exc:
            return None, f"Unexpected error: {exc}"

        errors = data.get("Errors") or []
        if errors:
            return None, "; ".join(e.get("Message", "Unknown error") for e in errors)

        parts = data.get("SearchResults", {}).get("Parts")
        if not parts:
            return None, "No results found"

        return parts[0], None


def read_rows(csv_text):
    """Parse raw CSV text into a list of rows (each row a list of strings)."""
    reader = csv.reader(io.StringIO(csv_text))
    return [row for row in reader if row]


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", default_key=os.environ.get("MOUSER_API_KEY", ""))


@app.route("/preview", methods=["POST"])
def preview():
    """Step 1: read the CSV, show its columns, and ask which one holds the part numbers."""
    api_key = (request.form.get("api_key") or os.environ.get("MOUSER_API_KEY", "")).strip()
    display_currency = (request.form.get("display_currency") or "USD").strip().upper()
    csv_file = request.files.get("csv_file")

    if not api_key:
        flash("Please provide a Mouser API key.")
        return redirect(url_for("index"))

    if not csv_file or csv_file.filename == "":
        flash("Please choose a CSV file.")
        return redirect(url_for("index"))

    raw_bytes = csv_file.read()
    csv_text = raw_bytes.decode("utf-8-sig", errors="replace")
    rows = read_rows(csv_text)

    if not rows:
        flash("That CSV file looks empty.")
        return redirect(url_for("index"))

    num_columns = max(len(row) for row in rows)
    sample_row = rows[0]
    # Pad the sample row so every column index has something to show, even if blank.
    sample_row = sample_row + [""] * (num_columns - len(sample_row))

    # Carry the CSV content through to the next step in a hidden field.
    encoded_csv = base64.b64encode(csv_text.encode("utf-8")).decode("ascii")

    return render_template(
        "preview.html",
        api_key=api_key,
        encoded_csv=encoded_csv,
        filename=csv_file.filename,
        columns=list(enumerate(sample_row)),
        row_count=len(rows),
        display_currency=display_currency,
    )


@app.route("/upload", methods=["POST"])
def upload():
    """Step 2: extract the chosen column and run the Mouser lookups."""
    api_key = (request.form.get("api_key") or "").strip()
    encoded_csv = request.form.get("encoded_csv", "")
    has_header = request.form.get("has_header") == "on"
    column_index_raw = request.form.get("column_index")
    display_currency = (request.form.get("display_currency") or "USD").strip().upper()

    if not api_key:
        flash("Please provide a Mouser API key.")
        return redirect(url_for("index"))

    if not encoded_csv or column_index_raw is None:
        flash("Something went wrong reading that CSV. Please upload it again.")
        return redirect(url_for("index"))

    try:
        column_index = int(column_index_raw)
    except ValueError:
        flash("Please choose a valid column.")
        return redirect(url_for("index"))

    csv_text = base64.b64decode(encoded_csv.encode("ascii")).decode("utf-8")
    rows = read_rows(csv_text)

    if has_header and rows:
        rows = rows[1:]

    part_numbers = []
    for row in rows:
        if column_index < len(row):
            value = row[column_index].strip()
            if value:
                part_numbers.append(value)

    if not part_numbers:
        flash("No part numbers were found in that column.")
        return redirect(url_for("index"))

    fx_rate, fx_date = get_exchange_rate(display_currency)
    if fx_rate is None:
        # Couldn't reach the FX service (or an unsupported code) - fall back to USD only.
        display_currency = "USD"
        fx_rate = 1.0
        if request.form.get("display_currency", "USD").upper() != "USD":
            flash("Couldn't fetch a live exchange rate right now, so prices are shown in USD.")

    mouser = MouserAPI(api_key)
    results = []
    for part_number in part_numbers:
        product, error = mouser.search_part(part_number)

        pricing = None
        if product:
            price_breaks = []
            for pb in product.get("PriceBreaks", []):
                usd_price = parse_price(pb.get("Price"))
                if usd_price is None:
                    continue
                price_breaks.append({
                    "quantity": pb.get("Quantity", 0),
                    "usd_price": usd_price,
                    "display_price": round(usd_price * fx_rate, 4),
                })
            price_breaks.sort(key=lambda pb: pb["quantity"])

            min_order = product.get("Min")
            multiple = product.get("Mult")
            pricing = {
                "price_breaks": price_breaks,
                "min_order": int(min_order) if str(min_order).isdigit() else 1,
                "multiple": int(multiple) if str(multiple).isdigit() else 1,
            }

        results.append({
            "query": part_number,
            "product": product,
            "error": error,
            "pricing_json": json.dumps(pricing) if pricing else None,
        })

    return render_template(
        "results.html",
        results=results,
        display_currency=display_currency,
        fx_rate=fx_rate,
        fx_date=fx_date,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5001)
