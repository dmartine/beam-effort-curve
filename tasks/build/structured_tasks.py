"""Build tasks/structured.jsonl. Every gold object is validated against its schema
and must score 100% with the grader before the task is written out.

    python -m tasks.build.structured_tasks
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.graders import structured as grader

SUFFIX = "\n\nReply with the JSON object only, matching this JSON Schema:\n"
SOURCE = "written for this repo (2026-10); gold output validated in tasks/build/structured_tasks.py"
TASKS = []

DATE = {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}
TIME = {"type": "string", "pattern": r"^\d{2}:\d{2}$"}
STR, INT, NUM, BOOL = {"type": "string"}, {"type": "integer"}, {"type": "number"}, {"type": "boolean"}


def obj(**props):
    return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}


def arr(items):
    return {"type": "array", "items": items}


def nullable(s):
    return {"anyOf": [s, {"type": "null"}]}


def enum(*vals):
    return {"enum": list(vals)}


def task(instructions, text, schema, expected, ignore_fields=()):
    TASKS.append((f"{instructions.strip()}\n\nInput:\n{text.strip()}", schema, expected, list(ignore_fields)))


task(
    "Convert this revision log to JSON, newest first. Author names are capitalized as in the rest of the log. "
    "A revision is breaking only if the log says so explicitly.",
    """
v2.1 - shipped 3 Sept 2026 by Ana (no breaking changes)
v2.0 / 2026-08-14 / R. Okafor / BREAKING: removed legacy auth
v1.9, July 30th 2026, ana, minor fixes
v1.10 was never released
""",
    obj(revisions=arr(obj(version=STR, date=DATE, author=STR, breaking=BOOL))),
    {"revisions": [
        {"version": "v2.1", "date": "2026-09-03", "author": "Ana", "breaking": False},
        {"version": "v2.0", "date": "2026-08-14", "author": "R. Okafor", "breaking": True},
        {"version": "v1.9", "date": "2026-07-30", "author": "Ana", "breaking": False}]},
)

task(
    "Extract the invoice. Money amounts are integers in cents. Line items keep the order they appear in. "
    "total_cents is the amount due after the discount and tax exactly as stated on the invoice.",
    """
INVOICE #INV-2026-0447        Issued: Oct 2, 2026     Payment due within 30 days
Bill to: Harbor Lane Coffee

  3 x  Espresso grinder burr set ........ $64.50 ea
  1 x  Annual maintenance plan ........... $420.00
  12 x Descaling tablets (pack) .......... $3.25 ea

Subtotal: $652.50   Loyalty discount (10%): -$65.25   Sales tax 8%: $46.98
AMOUNT DUE (USD): $634.23
""",
    obj(invoice_number=STR, issue_date=DATE, due_date=DATE, currency=STR, customer=STR,
        line_items=arr(obj(description=STR, quantity=INT, unit_price_cents=INT)), total_cents=INT),
    {"invoice_number": "INV-2026-0447", "issue_date": "2026-10-02", "due_date": "2026-11-01", "currency": "USD",
     "customer": "Harbor Lane Coffee",
     "line_items": [
         {"description": "Espresso grinder burr set", "quantity": 3, "unit_price_cents": 6450},
         {"description": "Annual maintenance plan", "quantity": 1, "unit_price_cents": 42000},
         {"description": "Descaling tablets (pack)", "quantity": 12, "unit_price_cents": 325}],
     "total_cents": 63423},
)

task(
    "Extract the meeting that was finally agreed on in this email thread (all emails were sent in October 2026). Use 24-hour time. attendees is the sorted list of "
    "email addresses (lowercase) of the organizer plus everyone who confirmed. location is null if it is a video call.",
    """
From: priya@northwind.io
Can we do the Q4 roadmap review Thursday Nov 5 at 2pm, 90 min, room Atlas?

From: Leo.Marsh@northwind.io
Thursday 2pm clashes for me. Friday Nov 6 same time works.

From: priya@northwind.io
OK, Friday Nov 6, 2:30pm instead (room is booked till 2:30), still 90 minutes, Atlas. Leo, Sam, you in?

From: sam@contoso.com
Yes. I'll join remotely but count me in.

From: leo.marsh@northwind.io
Confirmed. Also adding dana@northwind.io, she said yes on chat.
""",
    obj(title=STR, date=DATE, start_time=TIME, duration_minutes=INT, location=nullable(STR), attendees=arr(STR)),
    {"title": "Q4 roadmap review", "date": "2026-11-06", "start_time": "14:30", "duration_minutes": 90,
     "location": "Atlas",
     "attendees": ["dana@northwind.io", "leo.marsh@northwind.io", "priya@northwind.io", "sam@contoso.com"]},
    ignore_fields=["title"],
)

task(
    "Normalize these US addresses in input order. street keeps the number and street name with standard abbreviations "
    "spelled out (St -> Street, Ave -> Avenue, Blvd -> Boulevard, Rd -> Road, Pkwy -> Parkway) and unit numbers dropped. state is the "
    "two-letter code; zip is the 5-digit ZIP as a string.",
    """
1) 1600 amphitheatre pkwy, mountain view california 94043
2) 350 Fifth Ave Apt 3B, New York, NY 10118-0110
3) 742 evergreen terrace springfield, OR, 97477
4) 1 Infinite Loop / Cupertino / Calif. / 95014
""",
    obj(addresses=arr(obj(street=STR, city=STR, state={"type": "string", "pattern": "^[A-Z]{2}$"},
                          zip={"type": "string", "pattern": r"^\d{5}$"}))),
    {"addresses": [
        {"street": "1600 Amphitheatre Parkway", "city": "Mountain View", "state": "CA", "zip": "94043"},
        {"street": "350 Fifth Avenue", "city": "New York", "state": "NY", "zip": "10118"},
        {"street": "742 Evergreen Terrace", "city": "Springfield", "state": "OR", "zip": "97477"},
        {"street": "1 Infinite Loop", "city": "Cupertino", "state": "CA", "zip": "95014"}]},
)

task(
    "List every ERROR-level entry in chronological order (the log is not sorted). timestamp is ISO 8601 in UTC with a Z "
    "suffix; convert offsets. code is the integer after 'code='. Ignore WARN and INFO lines.",
    """
2026-10-20T14:05:12+02:00 [ERROR] payments  code=502 upstream gateway timeout
2026-10-20T11:59:59Z      [WARN]  payments  code=429 retrying
2026-10-20T12:01:00Z      [ERROR] auth      code=401 token signature invalid
2026-10-20T07:30:00-05:00 [ERROR] search    code=500 index shard unavailable
2026-10-20T12:10:00Z      [INFO]  auth      code=200 recovered
""",
    obj(errors=arr(obj(timestamp=STR, service=STR, code=INT, message=STR))),
    {"errors": [
        {"timestamp": "2026-10-20T12:01:00Z", "service": "auth", "code": 401, "message": "token signature invalid"},
        {"timestamp": "2026-10-20T12:05:12Z", "service": "payments", "code": 502, "message": "upstream gateway timeout"},
        {"timestamp": "2026-10-20T12:30:00Z", "service": "search", "code": 500, "message": "index shard unavailable"}]},
)

task(
    "Extract the recipe. quantity is a number (convert fractions to decimals). unit is one of the allowed values; use "
    "\"piece\" for countable items with no unit. Ingredients keep the order they are listed; item is the lowercase ingredient name as written, without preparation notes.",
    """
GRANDMA'S SKILLET CORNBREAD  (makes 8 wedges, serves 8)
- 1 1/2 cups cornmeal
- 1/2 cup All-Purpose Flour
- 2 tsp baking powder
- 1 Tbsp sugar
- 2 eggs
- 240 ml buttermilk
- 60 g butter, melted
Heat a cast iron skillet in a 220C oven. Whisk dry, whisk wet, combine, bake 20 min.
""",
    obj(name=STR, servings=INT, oven_celsius=INT,
        ingredients=arr(obj(item=STR, quantity=NUM, unit=enum("g", "ml", "tsp", "tbsp", "cup", "piece")))),
    {"name": "Grandma's Skillet Cornbread", "servings": 8, "oven_celsius": 220, "ingredients": [
        {"item": "cornmeal", "quantity": 1.5, "unit": "cup"},
        {"item": "all-purpose flour", "quantity": 0.5, "unit": "cup"},
        {"item": "baking powder", "quantity": 2, "unit": "tsp"},
        {"item": "sugar", "quantity": 1, "unit": "tbsp"},
        {"item": "eggs", "quantity": 2, "unit": "piece"},
        {"item": "buttermilk", "quantity": 240, "unit": "ml"},
        {"item": "butter", "quantity": 60, "unit": "g"}]},
    ignore_fields=["name"],
)

task(
    "Extract each review in input order. rating is the integer star rating 1-5. sentiment follows the rating only: "
    "4-5 positive, 3 neutral, 1-2 negative.",
    """
[SKU-88123] ★★★★☆ "Battery is great, the case is flimsy."
[SKU-10002] three stars. Does the job, nothing special.
[SKU-88123] 1/5 - stopped charging after a week!!
[SKU-55010] Rated it five out of five even though shipping was slow.
[SKU-10002] ★★☆☆☆ Meh.
""",
    obj(reviews=arr(obj(product_id=STR, rating={"type": "integer", "minimum": 1, "maximum": 5},
                        sentiment=enum("positive", "neutral", "negative")))),
    {"reviews": [
        {"product_id": "SKU-88123", "rating": 4, "sentiment": "positive"},
        {"product_id": "SKU-10002", "rating": 3, "sentiment": "neutral"},
        {"product_id": "SKU-88123", "rating": 1, "sentiment": "negative"},
        {"product_id": "SKU-55010", "rating": 5, "sentiment": "positive"},
        {"product_id": "SKU-10002", "rating": 2, "sentiment": "negative"}]},
)

task(
    "Extract the flight segments in travel order. Airports are IATA codes. depart and arrive are local times at that "
    "airport as YYYY-MM-DDTHH:MM (24-hour). A '+1' after a time means the next day.",
    """
Your trip, booking ref QX7P2L
Leg 2: TP 1350  Lisbon (LIS) 07:05  ->  Madeira Funchal (FNC) 08:55   Sat 14 Nov 2026
Leg 1: UA 64    Newark (EWR) 7:25 PM -> Lisbon (LIS) 7:10 AM +1         Thu 12 Nov 2026
Return: TP 1702 Funchal (FNC) 18:40 -> Porto (OPO) 21:00, then TP 1830 OPO 22:15 -> LIS 23:10, both Fri 20 Nov 2026
""",
    obj(booking_ref=STR, segments=arr(obj(flight=STR, origin=STR, destination=STR, depart=STR, arrive=STR))),
    {"booking_ref": "QX7P2L", "segments": [
        {"flight": "UA 64", "origin": "EWR", "destination": "LIS", "depart": "2026-11-12T19:25", "arrive": "2026-11-13T07:10"},
        {"flight": "TP 1350", "origin": "LIS", "destination": "FNC", "depart": "2026-11-14T07:05", "arrive": "2026-11-14T08:55"},
        {"flight": "TP 1702", "origin": "FNC", "destination": "OPO", "depart": "2026-11-20T18:40", "arrive": "2026-11-20T21:00"},
        {"flight": "TP 1830", "origin": "OPO", "destination": "LIS", "depart": "2026-11-20T22:15", "arrive": "2026-11-20T23:10"}]},
)

task(
    "Convert the table to JSON rows in input order. revenue_usd is an integer number of dollars (\"1.2k\" means 1200, "
    "\"$3.4M\" means 3400000). growth_pct is a number (\"+4.5%\" -> 4.5). Use null for missing values (n/a, -, blank).",
    """
| Region      | Revenue  | YoY growth |
|-------------|----------|------------|
| North East  | $3,400   | +4.5%      |
| Southwest   | 1.2k     | -0.8 %     |
| Pacific NW  | n/a      | 12%        |
| Gulf Coast  | $3.4M    | -          |
| Mountain    | 950      |            |
""",
    obj(rows=arr(obj(region=STR, revenue_usd=nullable(INT), growth_pct=nullable(NUM)))),
    {"rows": [
        {"region": "North East", "revenue_usd": 3400, "growth_pct": 4.5},
        {"region": "Southwest", "revenue_usd": 1200, "growth_pct": -0.8},
        {"region": "Pacific NW", "revenue_usd": None, "growth_pct": 12},
        {"region": "Gulf Coast", "revenue_usd": 3400000, "growth_pct": None},
        {"region": "Mountain", "revenue_usd": 950, "growth_pct": None}]},
)

task(
    "Turn this bug report into the structured form. severity: \"critical\" if data is lost or the app is unusable, "
    "\"major\" if a feature is broken with no workaround, \"minor\" otherwise. steps are the reproduction steps in order, "
    "without numbering.",
    """
hey team - export is busted. go to Reports, pick any report, click Export > CSV and the file downloads but it's empty
(0 bytes). expected the rows I see on screen obviously. PDF export still works fine so I'm using that for now.
I'm on macOS 15.1, Chrome 131, app version 4.12.0
""",
    obj(title=STR, severity=enum("critical", "major", "minor"), steps=arr(STR), expected=STR, actual=STR,
        workaround=nullable(STR), environment=obj(os=STR, browser=STR, app_version=STR)),
    {"title": "CSV export produces an empty file", "severity": "minor",
     "steps": ["Go to Reports", "Pick any report", "Click Export > CSV"],
     "expected": "The CSV contains the rows shown on screen", "actual": "The downloaded file is empty (0 bytes)",
     "workaround": "Use PDF export",
     "environment": {"os": "macOS 15.1", "browser": "Chrome 131", "app_version": "4.12.0"}},
    ignore_fields=["title", "steps", "expected", "actual", "workaround"],
)

task(
    "Extract the contact. Collapse repeated spaces in names. Phone numbers are E.164 (assume US +1 when no country code). type is lowercase. Keep phones "
    "and emails in input order; emails are lowercase.",
    """
BEGIN:VCARD
FN:Dr. Amara  Okonkwo-Reyes
TEL;TYPE=CELL:(415) 555-0134
TEL;TYPE=WORK:+44 20 7946 0958
EMAIL:Amara.OR@Example.org
EMAIL;TYPE=WORK:amara@reyeslab.example
ORG:Reyes Lab;Genomics
END:VCARD
""",
    obj(full_name=STR, organization=STR, department=STR,
        phones=arr(obj(type=enum("cell", "work", "home"), number={"type": "string", "pattern": r"^\+\d{8,15}$"})),
        emails=arr(STR)),
    {"full_name": "Dr. Amara Okonkwo-Reyes", "organization": "Reyes Lab", "department": "Genomics",
     "phones": [{"type": "cell", "number": "+14155550134"}, {"type": "work", "number": "+442079460958"}],
     "emails": ["amara.or@example.org", "amara@reyeslab.example"]},
)

task(
    "Extract only the newest release from this changelog. Each section is a list of entries without the leading dash or "
    "issue references like (#123). Sections that are absent are empty lists.",
    """
## [3.0.0] - 2026-10-01
### Removed
- Python 3.9 support (#812)
### Added
- `--dry-run` flag for sync (#790)
- Parquet export (#801)
### Fixed
- Crash when config file is empty (#799)

## [2.9.4] - 2026-08-11
### Fixed
- Typo in help text
""",
    obj(version=STR, date=DATE, added=arr(STR), changed=arr(STR), fixed=arr(STR), removed=arr(STR)),
    {"version": "3.0.0", "date": "2026-10-01", "added": ["`--dry-run` flag for sync", "Parquet export"],
     "changed": [], "fixed": ["Crash when config file is empty"], "removed": ["Python 3.9 support"]},
)

task(
    "Parse this week's timesheet. Times are 24-hour HH:MM; a bare hour like \"9\" means 09:00 and times after a "
    "noon crossing are afternoon (\"1:30\" after a morning entry is 13:30). entries keep input order. "
    "minutes_by_project sums the minutes per project; projects are lowercase.",
    """
Mon: 9-12:30 ACME, 1:30-5 internal
Tue: 8:45-11:15 acme
Wed: off
Thu: 10-11 Internal, 11-3 ACME
""",
    obj(entries=arr(obj(day=enum("mon", "tue", "wed", "thu", "fri"), start=TIME, end=TIME, project=STR, minutes=INT)),
        minutes_by_project={"type": "object", "additionalProperties": INT}),
    {"entries": [
        {"day": "mon", "start": "09:00", "end": "12:30", "project": "acme", "minutes": 210},
        {"day": "mon", "start": "13:30", "end": "17:00", "project": "internal", "minutes": 210},
        {"day": "tue", "start": "08:45", "end": "11:15", "project": "acme", "minutes": 150},
        {"day": "thu", "start": "10:00", "end": "11:00", "project": "internal", "minutes": 60},
        {"day": "thu", "start": "11:00", "end": "15:00", "project": "acme", "minutes": 240}],
     "minutes_by_project": {"acme": 600, "internal": 270}},
)

task(
    "Convert this INI file to JSON: one object per section, keys as written. Values become typed: true/false/yes/no -> "
    "boolean, whole numbers -> integer, decimals -> number, comma-separated values -> array of trimmed strings, "
    "anything else -> string. Comments (; or #) are dropped.",
    """
[server]
host = 0.0.0.0
port = 8080
debug = no   ; turn on locally
# timeouts in seconds
timeout = 2.5

[features]
enabled = search, export ,  beta-ui
max_upload_mb = 250
banner = Welcome back, friend
""",
    obj(server=obj(host=STR, port=INT, debug=BOOL, timeout=NUM),
        features=obj(enabled=arr(STR), max_upload_mb=INT, banner={"anyOf": [STR, arr(STR)]})),
    {"server": {"host": "0.0.0.0", "port": 8080, "debug": False, "timeout": 2.5},
     "features": {"enabled": ["search", "export", "beta-ui"], "max_upload_mb": 250,
                  "banner": ["Welcome back", "friend"]}},
)

task(
    "Extract the order. Quantities are integers. A line that is struck out with ~~ ~~ was cancelled and must be left out. "
    "gift_message is null if there is none.",
    """
Order 55-1092 for Mei Lin (mei.lin@example.com), ship express
- 2x Linen napkins, sage
- ~~1x Table runner, sage~~
- 1x Table runner, oat
- 6x Beeswax candles (tall)
Note on card: "Happy housewarming!"
""",
    obj(order_id=STR, customer=obj(name=STR, email=STR), shipping=enum("standard", "express"),
        items=arr(obj(name=STR, quantity=INT)), gift_message=nullable(STR)),
    {"order_id": "55-1092", "customer": {"name": "Mei Lin", "email": "mei.lin@example.com"}, "shipping": "express",
     "items": [{"name": "Linen napkins, sage", "quantity": 2}, {"name": "Table runner, oat", "quantity": 1},
               {"name": "Beeswax candles (tall)", "quantity": 6}],
     "gift_message": "Happy housewarming!"},
)


def main():
    out = Path(__file__).resolve().parents[1] / "structured.jsonl"
    rows, problems = [], []
    for k, (prompt, schema, expected, ignore_fields) in enumerate(TASKS, 1):
        tid = f"struct-{k:03d}"
        errors = [e.message for e in Draft202012Validator(schema).iter_errors(expected)]
        g = grader.grade({"schema": schema, "expected": expected, "ignore_fields": ignore_fields},
                         {"content": json.dumps(expected)})
        if errors or not g["correct"]:
            problems.append(f"{tid}: {errors or g}")
        rows.append({"id": tid, "category": "structured", "grader": "structured",
                     "prompt": prompt + SUFFIX + json.dumps(schema), "schema": schema, "expected": expected,
                     "ignore_fields": ignore_fields,
                     "source": SOURCE})
        print(tid, "ok" if not errors and g["correct"] else "PROBLEM")
    if problems:
        raise SystemExit("\n".join(problems))
    with out.open("w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(f"{len(rows)} tasks -> {out}")


if __name__ == "__main__":
    main()
