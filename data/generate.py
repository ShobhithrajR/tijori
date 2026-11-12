"""Deterministic synthetic Indian-document dataset for Tijori (lane 3).

Each document is assembled from labelled segments, so every entity span is
computed while the text is rendered. That makes the labels exact by
construction: ``text[start:end] == entity["text"]`` for every entity.

Stdlib only, no network. Run::

    python -m data.generate

Schema: CONTRACT.md section 8.
"""

from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path

SEED = 2026
DATASET_PATH = Path(__file__).with_name("dataset.jsonl")

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
GSTIN_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
STATE_CODES = ("07", "09", "19", "24", "27", "29", "33", "36")

FIRST_NAMES = (
    "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Ananya", "Rohit", "Kavya",
    "Arjun", "Meera", "Sanjay", "Pooja", "Arun", "Divya", "Karan", "Neha",
    "Suresh", "Anjali", "Manish", "Ritika", "Deepak", "Shruti", "Vijay",
    "Sakshi", "Nikhil", "Isha", "Ramesh", "Tanvi", "Ajay", "Swati",
)

LAST_NAMES = (
    "Sharma", "Patel", "Iyer", "Reddy", "Nair", "Gupta", "Singh", "Desai",
    "Kulkarni", "Menon", "Joshi", "Rao", "Chopra", "Bhat", "Verma", "Mishra",
    "Pillai", "Shetty", "Agarwal", "Das",
)

# (street/locality, city, state, PIN)
ADDRESSES = (
    ("Flat 402, Sunrise Apartments, 12 MG Road, Indiranagar", "Bengaluru", "Karnataka", "560038"),
    ("House 18, Sector 21, Dwarka", "New Delhi", "Delhi", "110075"),
    ("B-704, Lodha Paradise, Eastern Express Highway, Thane West", "Thane", "Maharashtra", "400601"),
    ("23, 3rd Cross Street, Jayanagar 4th Block", "Bengaluru", "Karnataka", "560011"),
    ("Shop 6, Anna Salai, Teynampet", "Chennai", "Tamil Nadu", "600018"),
    ("Plot 145, Gachibowli Main Road, Serilingampally", "Hyderabad", "Telangana", "500032"),
    ("12/3, Park Street, Near GPO", "Kolkata", "West Bengal", "700016"),
    ("A-11, Vaishali Nagar, Ajmer Road", "Jaipur", "Rajasthan", "302021"),
    ("Flat 9C, Shanti Residency, Satellite Road", "Ahmedabad", "Gujarat", "380015"),
    ("House 77, Model Town, Near bus stand", "Ludhiana", "Punjab", "141002"),
    ("5, Koregaon Park Lane 6", "Pune", "Maharashtra", "411001"),
    ("D-32, Sector 62", "Noida", "Uttar Pradesh", "201309"),
    ("Flat 1104, Prestige Lakeside Habitat, Whitefield", "Bengaluru", "Karnataka", "560066"),
    ("28, Civil Lines, Behind Collector Office", "Nagpur", "Maharashtra", "440001"),
)

DOMAINS = ("gmail.com", "yahoo.in", "outlook.com", "example.co.in", "hotmail.com")

AADHAAR_STYLES = ("plain", "spaces", "hyphens")


def gstin_checksum(body: str) -> str:
    """Return the 15th GSTIN character for a 14-character body."""
    total = 0
    for index, char in enumerate(body):
        value = GSTIN_CHARS.index(char)
        product = value * (2 if index % 2 else 1)
        total += product // 36 + product % 36
    return GSTIN_CHARS[(36 - total % 36) % 36]


def _luhn_digit(prefix: str) -> str:
    total = 0
    for index, char in enumerate(reversed(prefix)):
        digit = int(char)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


def person_value(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def aadhaar_value(rng: random.Random) -> str:
    digits = str(rng.randint(2, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(11))
    style = rng.choice(AADHAAR_STYLES)
    if style == "spaces":
        return f"{digits[:4]} {digits[4:8]} {digits[8:]}"
    if style == "hyphens":
        return f"{digits[:4]}-{digits[4:8]}-{digits[8:]}"
    return digits


def pan_value(rng: random.Random, surname: str) -> str:
    prefix = "".join(rng.choice(LETTERS) for _ in range(3))
    return f"{prefix}P{surname[0]}{rng.randint(1000, 9999)}{rng.choice(LETTERS)}"


def gstin_value(rng: random.Random, pan: str) -> str:
    body = rng.choice(STATE_CODES) + pan + "1Z"
    return body + gstin_checksum(body)


def voter_id_value(rng: random.Random) -> str:
    prefix = "".join(rng.choice(LETTERS) for _ in range(3))
    return f"{prefix}{rng.randint(1000000, 9999999)}"


def passport_value(rng: random.Random) -> str:
    return f"{rng.choice(LETTERS)}{rng.randint(1000000, 9999999)}"


def phone_value(rng: random.Random) -> str:
    number = str(rng.randint(6, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(9))
    style = rng.choice(("intl", "local", "dashed"))
    if style == "intl":
        return f"+91 {number[:5]} {number[5:]}"
    if style == "dashed":
        return f"{number[:5]}-{number[5:]}"
    return f"0{number}"


def email_value(rng: random.Random, person: str) -> str:
    first, last = person.lower().split(" ", 1)
    suffix = rng.choice(("", "", str(rng.randint(1, 99))))
    return f"{first}.{last}{suffix}@{rng.choice(DOMAINS)}"


def dob_value(rng: random.Random) -> str:
    year = rng.randint(1960, 2003)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    style = rng.choice(("slash", "dash", "long"))
    if style == "slash":
        return f"{day:02d}/{month:02d}/{year}"
    if style == "dash":
        return f"{day:02d}-{month:02d}-{year}"
    months = ("January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December")
    return f"{day} {months[month - 1]} {year}"


def address_value(rng: random.Random) -> str:
    line, city, state, pin = rng.choice(ADDRESSES)
    return f"{line}, {city}, {state} {pin}"


def bank_account_value(rng: random.Random) -> str:
    return str(rng.randint(1, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(rng.randint(11, 14)))


def credit_card_value(rng: random.Random) -> str:
    prefix = rng.choice(("4", "5")) + "".join(str(rng.randint(0, 9)) for _ in range(14))
    digits = prefix + _luhn_digit(prefix)
    style = rng.choice(("spaced", "plain"))
    if style == "spaced":
        return " ".join(digits[i:i + 4] for i in range(0, 16, 4))
    return digits


def other_value(rng: random.Random, kind: str) -> str:
    if kind == "policy":
        return f"POL-{rng.randint(2020, 2026)}-{rng.randint(10000, 99999)}"
    if kind == "customer":
        return f"CUST-{rng.randint(10000, 99999)}"
    return f"REF-{rng.randint(100000, 999999)}"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render(segments: list[tuple]) -> tuple[str, list[dict]]:
    """Render segments and compute exact spans.

    ``("text", "...")`` appends literal text.
    ``("entity", TYPE, value)`` appends a labelled value.
    """
    parts: list[str] = []
    entities: list[dict] = []
    cursor = 0
    for segment in segments:
        kind = segment[0]
        if kind == "text":
            parts.append(segment[1])
            cursor += len(segment[1])
            continue
        if kind != "entity":
            raise ValueError(f"unknown segment kind: {kind!r}")
        _, entity_type, value = segment
        if not value:
            raise ValueError("empty entity value")
        start = cursor
        parts.append(value)
        cursor += len(value)
        entities.append({"type": entity_type, "text": value, "start": start, "end": cursor})
    return "".join(parts), entities


# ---------------------------------------------------------------------------
# Document builders. Each returns a segment list.
# ---------------------------------------------------------------------------


def loan_document(rng: random.Random, lang: str, opts: dict) -> list[tuple]:
    person = person_value(rng)
    surname = person.split(" ", 1)[1]
    pan = pan_value(rng, surname)
    aadhaar = aadhaar_value(rng)
    address = address_value(rng)
    dob = dob_value(rng)
    phone = phone_value(rng)
    email = email_value(rng, person)
    bank = bank_account_value(rng)
    amount = rng.choice(("2,50,000", "5,00,000", "7,50,000", "12,00,000"))
    purpose = rng.choice(("home renovation", "higher education", "medical expenses", "business expansion"))

    if lang == "hi-en":
        segments: list[tuple] = [
            ("text", "LOAN APPLICATION FORM\n\n"),
            ("text", "Mera naam "), ("entity", "PERSON", person), ("text", " hai.\n"),
            ("text", "Date of birth: "), ("entity", "DOB", dob), ("text", "\n"),
            ("text", "Pata: "), ("entity", "ADDRESS", address), ("text", "\n"),
            ("text", "Aadhaar number: "), ("entity", "AADHAAR", aadhaar), ("text", "\n"),
            ("text", "PAN card: "), ("entity", "PAN", pan), ("text", "\n"),
            ("text", "Mobile number: "), ("entity", "PHONE", phone), ("text", "\n"),
            ("text", "Email: "), ("entity", "EMAIL", email), ("text", "\n"),
            ("text", "Bank account: "), ("entity", "BANK_ACCOUNT", bank), ("text", "\n"),
        ]
        if opts.get("gstin"):
            segments += [("text", "Business GSTIN: "), ("entity", "GSTIN", gstin_value(rng, pan)), ("text", "\n")]
        if opts.get("passport"):
            segments += [("text", "Passport: "), ("entity", "PASSPORT", passport_value(rng)), ("text", "\n")]
        segments += [
            ("text", f"Mujhe Rs {amount} ka loan chahiye {purpose} ke liye.\n"),
            ("text", "Main confirm karta hoon ki upar di gayi details sahi hain."),
        ]
        return segments

    segments = [
        ("text", "LOAN APPLICATION FORM\n\n"),
        ("text", "Applicant name: "), ("entity", "PERSON", person), ("text", "\n"),
        ("text", "Date of birth: "), ("entity", "DOB", dob), ("text", "\n"),
        ("text", "Residential address: "), ("entity", "ADDRESS", address), ("text", "\n"),
        ("text", "Aadhaar number: "), ("entity", "AADHAAR", aadhaar), ("text", "\n"),
        ("text", "PAN: "), ("entity", "PAN", pan), ("text", "\n"),
        ("text", "Mobile: "), ("entity", "PHONE", phone), ("text", "\n"),
        ("text", "Email: "), ("entity", "EMAIL", email), ("text", "\n"),
        ("text", "Bank account for disbursal: "), ("entity", "BANK_ACCOUNT", bank), ("text", "\n"),
    ]
    if opts.get("gstin"):
        segments += [("text", "Business GSTIN: "), ("entity", "GSTIN", gstin_value(rng, pan)), ("text", "\n")]
    if opts.get("passport"):
        segments += [("text", "Passport number: "), ("entity", "PASSPORT", passport_value(rng)), ("text", "\n")]
    segments += [
        ("text", f"Loan amount requested: Rs {amount} for {purpose}.\n"),
        ("text", "Declaration: I confirm that the details provided above are correct."),
    ]
    return segments


def kyc_document(rng: random.Random, lang: str, opts: dict) -> list[tuple]:
    person = person_value(rng)
    surname = person.split(" ", 1)[1]
    pan = pan_value(rng, surname)
    aadhaar = aadhaar_value(rng)
    address = address_value(rng)
    dob = dob_value(rng)
    phone = phone_value(rng)
    email = email_value(rng, person)
    voter = voter_id_value(rng)

    if lang == "hi-en":
        segments: list[tuple] = [
            ("text", "KYC VERIFICATION RECORD\n\n"),
            ("text", "Poora naam: "), ("entity", "PERSON", person), ("text", "\n"),
            ("text", "Date of birth: "), ("entity", "DOB", dob), ("text", "\n"),
            ("text", "Ghar ka pata: "), ("entity", "ADDRESS", address), ("text", "\n"),
            ("text", "Aadhaar: "), ("entity", "AADHAAR", aadhaar), ("text", "\n"),
            ("text", "PAN: "), ("entity", "PAN", pan), ("text", "\n"),
            ("text", "Voter ID: "), ("entity", "VOTER_ID", voter), ("text", "\n"),
            ("text", "Mobile: "), ("entity", "PHONE", phone), ("text", "\n"),
            ("text", "Email: "), ("entity", "EMAIL", email), ("text", "\n"),
        ]
        if opts.get("passport"):
            segments += [("text", "Passport number: "), ("entity", "PASSPORT", passport_value(rng)), ("text", "\n")]
        segments += [
            ("text", "Verification video KYC ke through complete hui.\n"),
            ("text", "Customer ne documents original mein dikhaye."),
        ]
        return segments

    segments = [
        ("text", "KYC VERIFICATION RECORD\n\n"),
        ("text", "Full name: "), ("entity", "PERSON", person), ("text", "\n"),
        ("text", "Date of birth: "), ("entity", "DOB", dob), ("text", "\n"),
        ("text", "Residential address: "), ("entity", "ADDRESS", address), ("text", "\n"),
        ("text", "Aadhaar number: "), ("entity", "AADHAAR", aadhaar), ("text", "\n"),
        ("text", "PAN: "), ("entity", "PAN", pan), ("text", "\n"),
        ("text", "Voter ID (EPIC): "), ("entity", "VOTER_ID", voter), ("text", "\n"),
        ("text", "Mobile number: "), ("entity", "PHONE", phone), ("text", "\n"),
        ("text", "Email: "), ("entity", "EMAIL", email), ("text", "\n"),
    ]
    if opts.get("passport"):
        segments += [("text", "Passport number: "), ("entity", "PASSPORT", passport_value(rng)), ("text", "\n")]
    segments += [
        ("text", "Verification completed through video KYC.\n"),
        ("text", "Documents were shown in original by the customer."),
    ]
    return segments


def support_document(rng: random.Random, lang: str, opts: dict) -> list[tuple]:
    person = person_value(rng)
    phone = phone_value(rng)
    email = email_value(rng, person)
    customer_id = other_value(rng, "customer")
    order = f"ORD{rng.randint(100000, 999999)}"
    issue = rng.choice((
        "payment was debited twice but the order shows failed",
        "refund has not arrived after ten working days",
        "delivery is delayed and the courier is not responding",
        "account was locked after an OTP mismatch",
    ))

    if lang == "hi-en":
        segments: list[tuple] = [
            ("text", f"SUPPORT TICKET #{order}\n\n"),
            ("text", "Customer ka naam: "), ("entity", "PERSON", person), ("text", "\n"),
            ("text", "Registered mobile: "), ("entity", "PHONE", phone), ("text", "\n"),
            ("text", "Email: "), ("entity", "EMAIL", email), ("text", "\n"),
            ("text", "Customer ID: "), ("entity", "OTHER", customer_id), ("text", "\n"),
        ]
        if opts.get("card"):
            segments += [("text", "Card used: "), ("entity", "CREDIT_CARD", credit_card_value(rng)), ("text", "\n")]
        if opts.get("address"):
            segments += [("text", "Billing address: "), ("entity", "ADDRESS", address_value(rng)), ("text", "\n")]
        segments += [
            ("text", f"Issue: {issue}.\n"),
            ("text", "Kripya jaldi resolve karein, paisa wapas chahiye."),
        ]
        return segments

    segments = [
        ("text", f"SUPPORT TICKET #{order}\n\n"),
        ("text", "Customer name: "), ("entity", "PERSON", person), ("text", "\n"),
        ("text", "Registered mobile: "), ("entity", "PHONE", phone), ("text", "\n"),
        ("text", "Email: "), ("entity", "EMAIL", email), ("text", "\n"),
        ("text", "Customer ID: "), ("entity", "OTHER", customer_id), ("text", "\n"),
    ]
    if opts.get("card"):
        segments += [("text", "Card used: "), ("entity", "CREDIT_CARD", credit_card_value(rng)), ("text", "\n")]
    if opts.get("address"):
        segments += [("text", "Billing address: "), ("entity", "ADDRESS", address_value(rng)), ("text", "\n")]
    segments += [
        ("text", f"Issue: {issue}.\n"),
        ("text", "Request: please resolve this at the earliest."),
    ]
    return segments


def insurance_document(rng: random.Random, lang: str, opts: dict) -> list[tuple]:
    person = person_value(rng)
    surname = person.split(" ", 1)[1]
    dob = dob_value(rng)
    address = address_value(rng)
    policy = other_value(rng, "policy")
    incident = f"{rng.randint(1, 28):02d}/{rng.randint(1, 12):02d}/{rng.choice((2025, 2026))}"
    amount = rng.choice(("45,000", "1,20,000", "3,50,000", "8,00,000"))
    claim_type = rng.choice(("hospitalisation", "vehicle damage", "accidental injury", "home damage"))

    if lang == "hi-en":
        segments: list[tuple] = [
            ("text", "INSURANCE CLAIM FORM\n\n"),
            ("text", "Policy number: "), ("entity", "OTHER", policy), ("text", "\n"),
            ("text", "Claimant: "), ("entity", "PERSON", person), ("text", "\n"),
            ("text", "Date of birth: "), ("entity", "DOB", dob), ("text", "\n"),
            ("text", "Address: "), ("entity", "ADDRESS", address), ("text", "\n"),
            ("text", f"Incident date: {incident}; claim type: {claim_type}.\n"),
        ]
        if opts.get("aadhaar"):
            segments += [("text", "Aadhaar: "), ("entity", "AADHAAR", aadhaar_value(rng)), ("text", "\n")]
        if opts.get("pan"):
            segments += [("text", "PAN: "), ("entity", "PAN", pan_value(rng, surname)), ("text", "\n")]
        if opts.get("bank"):
            segments += [("text", "Settlement bank account: "), ("entity", "BANK_ACCOUNT", bank_account_value(rng)), ("text", "\n")]
        if opts.get("card"):
            segments += [("text", "Premium card: "), ("entity", "CREDIT_CARD", credit_card_value(rng)), ("text", "\n")]
        segments += [
            ("text", f"Claim amount: Rs {amount}.\n"),
            ("text", "Kripya claim ko jaldi process karein."),
        ]
        return segments

    segments = [
        ("text", "INSURANCE CLAIM FORM\n\n"),
        ("text", "Policy number: "), ("entity", "OTHER", policy), ("text", "\n"),
        ("text", "Claimant: "), ("entity", "PERSON", person), ("text", "\n"),
        ("text", "Date of birth: "), ("entity", "DOB", dob), ("text", "\n"),
        ("text", "Address: "), ("entity", "ADDRESS", address), ("text", "\n"),
        ("text", f"Incident date: {incident}; claim type: {claim_type}.\n"),
    ]
    if opts.get("aadhaar"):
        segments += [("text", "Aadhaar: "), ("entity", "AADHAAR", aadhaar_value(rng)), ("text", "\n")]
    if opts.get("pan"):
        segments += [("text", "PAN: "), ("entity", "PAN", pan_value(rng, surname)), ("text", "\n")]
    if opts.get("bank"):
        segments += [("text", "Settlement bank account: "), ("entity", "BANK_ACCOUNT", bank_account_value(rng)), ("text", "\n")]
    if opts.get("card"):
        segments += [("text", "Premium card: "), ("entity", "CREDIT_CARD", credit_card_value(rng)), ("text", "\n")]
    segments += [
        ("text", f"Claim amount: Rs {amount}.\n"),
        ("text", "Request: please process this claim at the earliest."),
    ]
    return segments


# ---------------------------------------------------------------------------
# Dataset assembly
# ---------------------------------------------------------------------------

#: (doc_type, id_prefix, count)
PLAN = (
    ("loan_application", "loan", 13),
    ("kyc", "kyc", 13),
    ("support_ticket", "support", 12),
    ("insurance_claim", "insurance", 12),
)


def _options(doc_type: str, index: int) -> dict:
    if doc_type == "loan_application":
        return {"gstin": index <= 10, "passport": index <= 4}
    if doc_type == "kyc":
        return {"passport": index <= 10}
    if doc_type == "support_ticket":
        return {"card": index <= 10, "address": index <= 4}
    return {"aadhaar": index <= 6, "pan": index <= 6, "bank": index <= 6, "card": index <= 2}


BUILDERS = {
    "loan_application": loan_document,
    "kyc": kyc_document,
    "support_ticket": support_document,
    "insurance_claim": insurance_document,
}


def build_documents(seed: int = SEED) -> list[dict]:
    """Build the full 50-document dataset deterministically."""
    rng = random.Random(seed)
    documents: list[dict] = []
    for doc_type, prefix, count in PLAN:
        builder = BUILDERS[doc_type]
        for index in range(1, count + 1):
            language = "hi-en" if (index - 1) % 3 == 0 else "en"
            text, entities = render(builder(rng, language, _options(doc_type, index)))
            documents.append({
                "id": f"{prefix}_{index:03d}",
                "doc_type": doc_type,
                "language": language,
                "text": text,
                "entities": entities,
            })
    return documents


def write_dataset(path: Path = DATASET_PATH, seed: int = SEED) -> list[dict]:
    documents = build_documents(seed)
    path.write_text(
        "".join(json.dumps(doc, ensure_ascii=False) + "\n" for doc in documents),
        encoding="utf-8",
    )
    return documents


def main() -> int:
    documents = write_dataset()
    types = Counter(e["type"] for doc in documents for e in doc["entities"])
    print(f"wrote {len(documents)} documents to {DATASET_PATH}")
    print("doc types :", dict(Counter(d["doc_type"] for d in documents)))
    print("languages :", dict(Counter(d["language"] for d in documents)))
    print("entities  :", dict(sorted(types.items())))
    print("total     :", sum(types.values()), "labelled entities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
