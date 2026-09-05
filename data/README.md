# DriveLegal India data package

The `data/` directory is the runtime source of truth for the application. Every file is bundled with the repository and loaded from a path relative to `app_core.py`; the application does not fetch legal data or images at runtime.

| File | Purpose |
|---|---|
| `national_fines.json` | National reference records, with rule section, penalty section, fine basis, valid vehicle categories, repeat policy, and source identifiers |
| `vehicle_types.json` | Vehicle labels and reference multipliers |
| `state_data.json` | State/UT speed, surcharge, helmet, and enforcement reference information |
| `legal_sections.json` | Bundled traffic-law catalogue rendered by the Traffic Laws tab |
| `metadata.json` | Schema version, review date, legal-source URLs, and product disclaimer |

## Schema policy

A fine record distinguishes the **rule section** from the **penalty section**. For example, red-light jumping uses Section 119 as the traffic-sign duty and Section 184 as the penalty provision described by the 2019 amendment. This distinction prevents the UI from presenting a penalty section as though it were the underlying traffic duty.

A record may be `fixed`, `per_excess_passenger`, or `base_plus_excess_tonne`. Quantity-based records require an explicit quantity in the calculator. Vehicle categories are used to prevent invalid combinations; the application does not multiply a statutory amount by an arbitrary vehicle factor unless a record explicitly opts in.

The `source_status` value is `act_reference` when the record is directly grounded in the central Act text, `state_notification` when grounded in an official state gazette notification under Section 200 of the Act, and `reference_only` when the amount or state rule requires additional notification verification. Verified state records include `notification_id`, `effective_date`, `jurisdiction`, and a `compounding_schedule` dictionary detailing compoundable offence amounts under Section 200 of the Motor Vehicles Act (currently provided for Delhi, Karnataka, Maharashtra, Gujarat, Kerala, Rajasthan, Tamil Nadu, and Uttar Pradesh). Unsupported state values remain visibly `reference_only`. Reference-only state surcharges are displayed as context but are not added to a calculation unless an offence record explicitly opts in with supporting evidence.

Repeat treatment is `explicit` only when the record contains a specific repeat amount. Records marked `reference_only` do not offer a repeat calculation; the application does not invent a generic doubled amount.

The traffic-law catalogue (`legal_sections.json`) maintains parity with the national fine records, ensuring every statutory penalty section referenced in the calculator has a corresponding educational entry explaining duties, scope, and penalties.

## Updating data

Update the relevant JSON file, add or revise source metadata, and run:

```bash
python -m json.tool data/national_fines.json >/dev/null
python -m json.tool data/vehicle_types.json >/dev/null
python -m json.tool data/state_data.json >/dev/null
python -m json.tool data/metadata.json >/dev/null
python -m json.tool data/legal_sections.json >/dev/null
pytest -q
```

Do not describe a reference amount as an official current challan amount unless the applicable notification and effective date have been verified. The application is an offline informational reference, not an official challan lookup service or legal-advice system.
