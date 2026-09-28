# Mouser Part Lookup

A small web app that replaces the old terminal script. Upload a CSV, pick which
column has the part numbers, and get back manufacturer, description, lifecycle
status, availability, and pricing for each one - pulled live from the Mouser
Search API.

Built with procurement workflows in mind:

- **Extended cost calculator** - enter the quantity you actually need per line
  and it picks the right price break and shows the total cost, plus a tip if
  buying a few more units would drop the total price.
- **MOQ / order multiple warnings** - flags when your quantity is below the
  minimum order or not a valid order multiple.
- **Currency display** - shows Mouser's native USD pricing, or converts to
  CAD/EUR/GBP/INR/AUD/MXN/JPY/CHF for reference using a live, free FX rate
  (clearly labeled as an estimate, not an official Mouser quote in that
  currency).

## Setup

```bash
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
export MOUSER_API_KEY=your_key_here   # optional — you can also paste it in the form
python app.py
```

Open **http://127.0.0.1:5000**, upload your CSV, and go.

Get a free API key at [https://www.mouser.com/api/](https://www.mouser.com/api/).

## Project layout

```
mouser-lookup/
├── app.py              # Flask app + Mouser API wrapper
├── templates/
│   ├── index.html      # upload form
│   └── results.html    # results table
├── static/
│   └── style.css
├── requirements.txt
└── .gitignore
```
