# DriveLegal India

DriveLegal India is an **offline informational reference and challan estimator** for traffic-law topics across all 28 Indian states and 8 Union Territories. It lets a user choose a location, violation, and applicable vehicle category, then calculates a reference amount using the bundled data package.

> This application does not query official challan records, use geolocation, or provide legal advice. Amounts can vary by effective government notification, state compounding schedule, court order, and enforcement circumstances. Verify a real challan through the official [Parivahan e-Challan portal](https://echallan.parivahan.gov.in) or the relevant state transport department.

## Features

| Feature | Description |
|---|---|
| Challan estimator | Calculates a transparent reference amount with fine, surcharge, repeat, and quantity components |
| Legal section distinction | Displays the underlying rule/duty section separately from the penalty section |
| Traffic-law catalogue & search | Complete 18-section statutory catalogue with live search across sections, titles, and legal provisions |
| Valid vehicle choices | Filters vehicle categories according to the offence record instead of allowing every combination |
| Quantity-based penalties | Supports excess passengers and excess tonnes where the statute uses a quantity |
| Multi-offence challan cart | Accumulate multiple simultaneous offences into an itemized summary with a combined reference total |
| State compounding schedules | Verified Section 200 MVA compounding fees and gazette citations for Delhi, Karnataka, Maharashtra, Gujarat, Tamil Nadu, and Uttar Pradesh |
| Inter-state compounding matrix | Side-by-side comparison table analyzing central statutory fines against state compounding rates across all verified states |
| State/UT reference rules | Covers 36 locations with speed, helmet, surcharge, and enforcement-reference records |
| Citizen rights & redressal guide | Offline reference for DigiLocker document validity (Rule 139 CMVR), 15-day grace periods, Virtual Courts, and 24/7 emergency helplines |
| Offline receipt export | Export single or itemized multi-offence calculation breakdowns directly as offline reference receipts |
| Offline runtime | Loads all application data locally and does not require a runtime API or remote image |
| Automated CI & tests | Matrix testing across Python 3.11, 3.12, and 3.13 covering schema validation and calculator behavior |

## Project structure

```text
Drive-Legal/
├── .github/workflows/ci.yml  # GitHub Actions automated CI matrix
├── app.py                    # Streamlit presentation layer
├── app_core.py               # Import-safe data loading, validation, and calculator logic
├── data/
│   ├── national_fines.json   # Fine records and legal semantics
│   ├── vehicle_types.json    # Vehicle labels and reference multipliers
│   ├── state_data.json       # State/UT reference records & compounding schedules
│   ├── legal_sections.json   # Bundled traffic-law catalogue
│   ├── metadata.json         # Schema version, sources, review date, disclaimer
│   └── README.md             # Data-maintenance policy
├── tests/
│   └── test_app_core.py      # Unit and validation tests
├── requirements.txt          # Pinned runtime dependency
├── requirements-dev.txt      # Runtime plus pytest
├── LICENSE
└── CONTRIBUTING.md
```

## Installation and use

Python 3.11 or newer is recommended. Create a virtual environment, install the runtime dependency, and start Streamlit:

```bash
python -m venv .venv
source .venv/bin/activate       # Linux/macOS
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
streamlit run app.py
```

The application opens at `http://localhost:8501`. After installation, application data and images are local; no network request is required for the normal interface.

## Testing

Install development requirements and run the complete test suite:

```bash
pip install -r requirements-dev.txt
pytest -q
python -m py_compile app.py app_core.py
```

Continuous integration runs the complete check suite automatically on every pull request and push to `main` across Python 3.11, 3.12, and 3.13 via `.github/workflows/ci.yml`.

## Data and legal sources

The central legal references are the [Motor Vehicles Act, 1988](https://www.indiacode.nic.in/bitstream/123456789/9460/1/a1988-59.pdf) and the [Motor Vehicles (Amendment) Act, 2019](https://www.indiacode.nic.in/repealedfileopen?rfilename=A2019-32.pdf). The data package records whether a value is an Act reference or a state-level reference requiring additional notification verification. Every data record includes source identifiers and the package includes a review date.

State speed limits, surcharges, and enforcement notes are reference data. They should not be interpreted as a complete or current compilation of every local order. Contributors must add source and effective-date information when updating a state record.

## Contribution workflow

Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request. Keep the project offline, update tests when changing calculator behavior, preserve the rule-section/penalty-section distinction, and use the exact legal source and effective notification for any fine update.
