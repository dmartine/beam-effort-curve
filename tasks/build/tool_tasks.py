"""Build tasks/tools.jsonl (multi-step agent tasks) and tasks/tool_schema.jsonl (schema stress).

Before writing, every task is checked: expected arguments validate against the tool's
schema, a perfect agent replaying the expected calls gets a canned output for each one,
and that perfect transcript grades as correct.

    python -m tasks.build.tool_tasks
"""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from src.graders import tools as grader
from src.run import lookup_tool

SOURCE = "written for this repo (2026-10); checked by replay in tasks/build/tool_tasks.py"
ANSWER_RULE = "When the task asks a question, end your reply with a line 'ANSWER: <answer>'."


def fn(_name, _description, _required=(), /, **props):
    return {"type": "function", "function": {"name": _name, "description": _description, "parameters": {
        "type": "object", "properties": props, "required": list(_required)}}}


S, I, N, B = {"type": "string"}, {"type": "integer"}, {"type": "number"}, {"type": "boolean"}
DATE = {"type": "string", "description": "YYYY-MM-DD"}


def enum(*v):
    return {"type": "string", "enum": list(v)}


def call(name, **arguments):
    return {"name": name, "arguments": arguments}


def any_order(*calls):
    return {"any_order": list(calls)}


def ok(**match):
    return {"match": match, "output": {"status": "ok"}}


def rec(output, **match):
    return {"match": match, "output": output}


# ---------------------------------------------------------------- worlds

SHOP = dict(
    system="You are an operations assistant for an online store. Today is 2026-10-21. Use the tools to look things up "
           "and to act; never guess data, and take only the actions the task asks for. " + ANSWER_RULE,
    tools=[
        fn("get_order", "Look up an order.", ["order_id"], order_id=S),
        fn("get_customer", "Look up a customer and their order ids.", ["customer_id"], customer_id=S),
        fn("get_stock", "Units of a SKU at one warehouse.", ["sku", "warehouse"], sku=S, warehouse=enum("NORTH", "SOUTH", "EAST")),
        fn("reserve", "Reserve units of a SKU at a warehouse for an order.", ["order_id", "sku", "warehouse", "quantity"],
           order_id=S, sku=S, warehouse=enum("NORTH", "SOUTH", "EAST"), quantity=I),
        fn("cancel_order", "Cancel an order that has not shipped.", ["order_id"], order_id=S),
        fn("issue_refund", "Refund part or all of an order.", ["order_id", "amount_cents", "reason"],
           order_id=S, amount_cents=I, reason=S),
        fn("send_message", "Send a message to a customer.", ["customer_id", "text"], customer_id=S, text=S),
    ],
    read_only=["get_order", "get_customer", "get_stock"],
)

CAL = dict(
    system="You are a scheduling assistant for Morgan (morgan@northwind.io). Today is Wednesday 2026-10-21. Use the tools; "
           "never guess data, and take only the actions the task asks for. Times are 24-hour HH:MM. " + ANSWER_RULE,
    tools=[
        fn("find_contact", "Search contacts by name. May return several matches.", ["name"], name=S),
        fn("list_events", "Morgan's events on a date.", ["date"], date=DATE),
        fn("create_event", "Create an event on Morgan's calendar and invite attendees.",
           ["title", "date", "start_time", "duration_minutes", "attendees"],
           title=S, date=DATE, start_time=S, duration_minutes=I, attendees={"type": "array", "items": S}),
        fn("move_event", "Move an existing event.", ["event_id", "new_date", "new_start_time"],
           event_id=S, new_date=DATE, new_start_time=S),
        fn("send_email", "Send an email from Morgan.", ["to", "subject", "body"], to=S, subject=S, body=S),
    ],
    read_only=["find_contact", "list_events"],
)

TRAVEL = dict(
    system="You are a travel and expenses assistant. Today is 2026-10-21. Use convert_currency for every currency "
           "conversion; never use your own exchange rates or guess data, and take only the actions the task asks for. "
           + ANSWER_RULE,
    tools=[
        fn("search_flights", "Search flights for one direction on one date.", ["origin", "destination", "date"],
           origin=S, destination=S, date=DATE),
        fn("convert_currency", "Convert an amount between currencies at today's rate.", ["amount", "from_currency", "to_currency"],
           amount=N, from_currency=S, to_currency=S),
        fn("book_flight", "Book a flight for a passenger.", ["flight_id", "passenger_name"], flight_id=S, passenger_name=S),
        fn("file_expense", "File an expense claim in US cents.", ["amount_usd_cents", "category", "description"],
           amount_usd_cents=I, category=enum("airfare", "lodging", "meals", "ground_transport", "other"), description=S),
    ],
    read_only=["search_flights", "convert_currency"],
)

ACCT = dict(
    system="You are a billing support agent for a SaaS product. Today is 2026-10-21. Use the tools; never guess data, "
           "and take only the actions the task asks for. " + ANSWER_RULE,
    tools=[
        fn("get_user", "Look up a user by email (exact match).", ["email"], email=S),
        fn("get_invoices", "All invoices for a user, newest first.", ["user_id"], user_id=S),
        fn("get_plan_price", "Monthly price of a plan in cents.", ["plan"], plan=enum("starter", "team", "pro")),
        fn("change_plan", "Change a user's plan.", ["user_id", "plan"], user_id=S, plan=enum("starter", "team", "pro")),
        fn("issue_credit", "Credit a user's account.", ["user_id", "amount_cents", "reason"], user_id=S, amount_cents=I, reason=S),
    ],
    read_only=["get_user", "get_invoices", "get_plan_price"],
)

TOOL_TASKS = []


def tool_task(world, prompt, tool_responses, expected_calls, answer_contains=(), tier="core"):
    TOOL_TASKS.append(dict(world=world, prompt=prompt, tool_responses=tool_responses,
                           expected_calls=expected_calls, answer_contains=list(answer_contains), tier=tier))


# ---------------------------------------------------------------- shop

tool_task(SHOP, "Order ORD-742 needs its item reserved at whichever warehouse has the most units of it in stock.", {
    "get_order": [rec({"order_id": "ORD-742", "sku": "SKU-19", "quantity": 4, "status": "processing"}, order_id="ORD-742")],
    "get_stock": [rec({"units": 6}, sku="SKU-19", warehouse="NORTH"), rec({"units": 11}, sku="SKU-19", warehouse="SOUTH"),
                  rec({"units": 9}, sku="SKU-19", warehouse="EAST")],
    "reserve": [ok(order_id="ORD-742")],
}, [call("get_order", order_id="ORD-742"),
    any_order(call("get_stock", sku="SKU-19", warehouse="NORTH"), call("get_stock", sku="SKU-19", warehouse="SOUTH"),
              call("get_stock", sku="SKU-19", warehouse="EAST")),
    call("reserve", order_id="ORD-742", sku="SKU-19", warehouse="SOUTH", quantity=4)])

tool_task(SHOP, "Reserve stock for order ORD-810. Use the NORTH warehouse if it has enough units for the whole order; "
                "otherwise use EAST.", {
    "get_order": [rec({"order_id": "ORD-810", "sku": "SKU-44", "quantity": 5, "status": "processing"}, order_id="ORD-810")],
    "get_stock": [rec({"units": 3}, sku="SKU-44", warehouse="NORTH"), rec({"units": 8}, sku="SKU-44", warehouse="EAST"),
                  rec({"units": 20}, sku="SKU-44", warehouse="SOUTH")],
    "reserve": [ok(order_id="ORD-810")],
}, [call("get_order", order_id="ORD-810"), call("get_stock", sku="SKU-44", warehouse="NORTH"),
    call("reserve", order_id="ORD-810", sku="SKU-44", warehouse="EAST", quantity=5)])

tool_task(SHOP, "Customer C-301 asked for a full refund of order ORD-655. Our policy: refunds only within 30 days of "
                "delivery. If the order is outside the window, do not refund; message the customer explaining why.", {
    "get_order": [rec({"order_id": "ORD-655", "customer_id": "C-301", "total_cents": 8999, "status": "delivered",
                       "delivered_date": "2026-09-10"}, order_id="ORD-655")],
    "send_message": [ok(customer_id="C-301")],
}, [call("get_order", order_id="ORD-655"), call("send_message", customer_id="C-301")])

tool_task(SHOP, "Order ORD-702 arrived with every unit of the ceramic mugs damaged. Refund just those units with reason "
                "\"damaged\". Do not message the customer.", {
    "get_order": [rec({"order_id": "ORD-702", "status": "delivered", "delivered_date": "2026-10-18", "items": [
        {"sku": "SKU-3", "name": "linen apron", "quantity": 1, "unit_price_cents": 2400},
        {"sku": "SKU-8", "name": "ceramic mug", "quantity": 2, "unit_price_cents": 1299},
        {"sku": "SKU-9", "name": "pour-over stand", "quantity": 1, "unit_price_cents": 3150}]}, order_id="ORD-702")],
    "issue_refund": [ok(order_id="ORD-702")],
}, [call("get_order", order_id="ORD-702"), call("issue_refund", order_id="ORD-702", amount_cents=2598, reason="damaged")])

tool_task(SHOP, "Please cancel order ORD-733 if it can still be cancelled. Can it be cancelled? Answer yes or no.", {
    "get_order": [rec({"order_id": "ORD-733", "status": "shipped", "shipped_date": "2026-10-20"}, order_id="ORD-733")],
}, [call("get_order", order_id="ORD-733")], ["ANSWER: no"])

tool_task(SHOP, "Customer C-77 wants every one of their orders that has not shipped yet cancelled.", {
    "get_customer": [rec({"customer_id": "C-77", "order_ids": ["ORD-901", "ORD-902", "ORD-903"]}, customer_id="C-77")],
    "get_order": [rec({"order_id": "ORD-901", "status": "processing"}, order_id="ORD-901"),
                  rec({"order_id": "ORD-902", "status": "shipped"}, order_id="ORD-902"),
                  rec({"order_id": "ORD-903", "status": "processing"}, order_id="ORD-903")],
    "cancel_order": [ok(order_id="ORD-901"), ok(order_id="ORD-903")],
}, [call("get_customer", customer_id="C-77"),
    any_order(call("get_order", order_id="ORD-901"), call("get_order", order_id="ORD-902"), call("get_order", order_id="ORD-903")),
    any_order(call("cancel_order", order_id="ORD-901"), call("cancel_order", order_id="ORD-903"))])

tool_task(SHOP, "How much has customer C-12 spent in total on orders that were not cancelled? Answer in dollars like $12.34.", {
    "get_customer": [rec({"customer_id": "C-12", "order_ids": ["ORD-501", "ORD-544", "ORD-610"]}, customer_id="C-12")],
    "get_order": [rec({"order_id": "ORD-501", "status": "delivered", "total_cents": 12050}, order_id="ORD-501"),
                  rec({"order_id": "ORD-544", "status": "cancelled", "total_cents": 4999}, order_id="ORD-544"),
                  rec({"order_id": "ORD-610", "status": "shipped", "total_cents": 6690}, order_id="ORD-610")],
}, [call("get_customer", customer_id="C-12"),
    any_order(call("get_order", order_id="ORD-501"), call("get_order", order_id="ORD-544"), call("get_order", order_id="ORD-610"))],
    ["ANSWER: $187.40"])

# ---------------------------------------------------------------- calendar

tool_task(CAL, "Book a 30-minute sync called \"Pricing sync\" with Priya tomorrow at the earliest time between 09:00 and "
               "12:00 when I'm free for the whole 30 minutes.", {
    "find_contact": [rec({"matches": [{"name": "Priya Raman", "email": "priya@northwind.io"}]})],
    "list_events": [rec({"events": [
        {"id": "ev-1", "title": "Standup", "start_time": "09:00", "end_time": "10:00"},
        {"id": "ev-2", "title": "1:1 Leo", "start_time": "10:00", "end_time": "10:30"},
        {"id": "ev-3", "title": "Vendor call", "start_time": "10:45", "end_time": "11:00"},
        {"id": "ev-4", "title": "Hiring panel", "start_time": "11:30", "end_time": "12:00"}]}, date="2026-10-22")],
    "create_event": [ok()],
}, [any_order(call("find_contact"), call("list_events", date="2026-10-22")),
    call("create_event", date="2026-10-22", start_time="11:00", duration_minutes=30, attendees=["priya@northwind.io"])])

tool_task(CAL, "Email Sam from Contoso with the subject \"Contract draft\" saying the draft will be ready Friday.", {
    "find_contact": [rec({"matches": [{"name": "Sam Ortiz", "company": "Fabrikam", "email": "sam.ortiz@fabrikam.example"},
                                      {"name": "Sam Lee", "company": "Contoso", "email": "sam.lee@contoso.example"}]})],
    "send_email": [ok()],
}, [call("find_contact"), call("send_email", to="sam.lee@contoso.example", subject="Contract draft")])

tool_task(CAL, "Move my design review this Friday to the same time on the following Monday.", {
    "list_events": [rec({"events": [{"id": "ev-30", "title": "Lunch", "start_time": "12:00", "end_time": "13:00"},
                                    {"id": "ev-31", "title": "Design review", "start_time": "14:00", "end_time": "15:00"}]},
                        date="2026-10-23"),
                    rec({"events": []})],
    "move_event": [ok(event_id="ev-31")],
}, [call("list_events", date="2026-10-23"),
    call("move_event", event_id="ev-31", new_date="2026-10-26", new_start_time="14:00")])

tool_task(CAL, "Create a 60-minute \"Budget review\" tomorrow at 15:00 with Dana (dana@northwind.io). If it fails because "
               "of a conflict, try again one hour later.", {
    "create_event": [rec({"status": "error", "error": "conflict: dana@northwind.io is busy 15:00-16:00"}, start_time="15:00"),
                     ok(start_time="16:00")],
}, [call("create_event", date="2026-10-22", start_time="15:00", duration_minutes=60, attendees=["dana@northwind.io"]),
    call("create_event", date="2026-10-22", start_time="16:00", duration_minutes=60, attendees=["dana@northwind.io"])])

tool_task(CAL, "How many meetings longer than 45 minutes do I have on Thursday and Friday this week combined? "
               "Answer with a number.", {
    "list_events": [
        rec({"events": [{"id": "a", "title": "Standup", "start_time": "09:00", "end_time": "09:15"},
                        {"id": "b", "title": "Roadmap", "start_time": "10:00", "end_time": "11:30"},
                        {"id": "c", "title": "Interview", "start_time": "13:00", "end_time": "13:45"}]}, date="2026-10-22"),
        rec({"events": [{"id": "d", "title": "Offsite planning", "start_time": "09:00", "end_time": "12:00"},
                        {"id": "e", "title": "Design review", "start_time": "14:00", "end_time": "15:00"},
                        {"id": "f", "title": "Coffee", "start_time": "16:00", "end_time": "16:30"}]}, date="2026-10-23")],
}, [any_order(call("list_events", date="2026-10-22"), call("list_events", date="2026-10-23"))], ["ANSWER: 3"])

# ---------------------------------------------------------------- travel

LIS_FNC = {"flights": [
    {"flight_id": "TP1349-1114", "departs": "06:10", "arrives": "07:55", "price": 129, "currency": "EUR"},
    {"flight_id": "FR8221-1114", "departs": "11:20", "arrives": "13:05", "price": 39, "currency": "EUR"},
    {"flight_id": "U27612-1114", "departs": "09:40", "arrives": "11:25", "price": 58, "currency": "EUR"},
    {"flight_id": "TP1351-1114", "departs": "10:15", "arrives": "12:00", "price": 51, "currency": "EUR"}]}

tool_task(TRAVEL, "Book Dana Ruiz on the cheapest flight from LIS to FNC on 2026-11-14 that arrives before 12:00.", {
    "search_flights": [rec(LIS_FNC, origin="LIS", destination="FNC", date="2026-11-14")],
    "book_flight": [ok()],
}, [call("search_flights", origin="LIS", destination="FNC", date="2026-11-14"),
    call("book_flight", flight_id="U27612-1114", passenger_name="Dana Ruiz")])

tool_task(TRAVEL, "Two options for Kai Moreno on 2026-12-03, London to Lisbon: BA500 (flight_id BA500-1203) at 142 GBP or "
                  "TP1363 (flight_id TP1363-1203) at 158 EUR. Book whichever is cheaper in US dollars.", {
    "convert_currency": [rec({"amount": 179.92, "currency": "USD"}, from_currency="GBP"),
                         rec({"amount": 171.06, "currency": "USD"}, from_currency="EUR")],
    "book_flight": [ok()],
}, [any_order(call("convert_currency", amount=142, from_currency="GBP", to_currency="USD"),
              call("convert_currency", amount=158, from_currency="EUR", to_currency="USD")),
    call("book_flight", flight_id="TP1363-1203", passenger_name="Kai Moreno")])

tool_task(TRAVEL, "File an expense for my Funchal hotel stay: 412.80 EUR, category lodging.", {
    "convert_currency": [rec({"amount": 447.06, "currency": "USD"}, amount=412.8, from_currency="EUR")],
    "file_expense": [ok()],
}, [call("convert_currency", amount=412.8, from_currency="EUR", to_currency="USD"),
    call("file_expense", amount_usd_cents=44706, category="lodging")])

tool_task(TRAVEL, "Book Ana Costa on the cheapest flight from LIS to OPO on 2026-11-20 and the cheapest flight back from "
                  "OPO to LIS on 2026-11-22.", {
    "search_flights": [
        rec({"flights": [{"flight_id": "TP1940-1120", "price": 74, "currency": "EUR"},
                         {"flight_id": "TP1944-1120", "price": 61, "currency": "EUR"}]}, origin="LIS", destination="OPO"),
        rec({"flights": [{"flight_id": "TP1951-1122", "price": 55, "currency": "EUR"},
                         {"flight_id": "TP1957-1122", "price": 89, "currency": "EUR"}]}, origin="OPO", destination="LIS")],
    "book_flight": [ok()],
}, [any_order(call("search_flights", origin="LIS", destination="OPO", date="2026-11-20"),
              call("search_flights", origin="OPO", destination="LIS", date="2026-11-22")),
    any_order(call("book_flight", flight_id="TP1944-1120", passenger_name="Ana Costa"),
              call("book_flight", flight_id="TP1951-1122", passenger_name="Ana Costa"))])

# ---------------------------------------------------------------- accounts

tool_task(ACCT, "ravi@lumen.test says they were charged twice in October. If there is a duplicate October charge, credit "
                "the amount of one charge with reason \"duplicate charge\".", {
    "get_user": [rec({"user_id": "u-4410", "plan": "team"}, email="ravi@lumen.test")],
    "get_invoices": [rec({"invoices": [
        {"id": "in-93", "date": "2026-10-05", "amount_cents": 9900, "plan": "team"},
        {"id": "in-92", "date": "2026-10-05", "amount_cents": 9900, "plan": "team"},
        {"id": "in-81", "date": "2026-09-05", "amount_cents": 9900, "plan": "team"}]}, user_id="u-4410")],
    "issue_credit": [ok(user_id="u-4410")],
}, [call("get_user", email="ravi@lumen.test"), call("get_invoices", user_id="u-4410"),
    call("issue_credit", user_id="u-4410", amount_cents=9900, reason="duplicate charge")])

tool_task(ACCT, "Our rule: a team-plan user may be downgraded to starter only if they were billed for at most 5 seats on "
                "each of their last 3 invoices. Downgrade mo@delta.test if the rule allows it. Was the downgrade allowed? "
                "Answer yes or no.", {
    "get_user": [rec({"user_id": "u-2001", "plan": "team"}, email="mo@delta.test")],
    "get_invoices": [rec({"invoices": [
        {"id": "in-7", "date": "2026-10-01", "seats": 3}, {"id": "in-6", "date": "2026-09-01", "seats": 4},
        {"id": "in-5", "date": "2026-08-01", "seats": 6}, {"id": "in-4", "date": "2026-07-01", "seats": 2}]},
        user_id="u-2001")],
}, [call("get_user", email="mo@delta.test"), call("get_invoices", user_id="u-2001")], ["ANSWER: no"])

tool_task(ACCT, "Jo.Smith@Example.com can't see their invoices. Find their account (emails are stored lowercase) and tell "
                "me the amount of their most recent invoice in dollars like $12.34.", {
    "get_user": [rec({"user_id": "u-77", "plan": "pro"}, email="jo.smith@example.com"),
                 rec({"error": "user not found"})],
    "get_invoices": [rec({"invoices": [{"id": "in-301", "date": "2026-10-03", "amount_cents": 4900},
                                       {"id": "in-288", "date": "2026-09-03", "amount_cents": 4900},
                                       {"id": "in-270", "date": "2026-08-03", "amount_cents": 1900}]}, user_id="u-77")],
}, [call("get_user", email="jo.smith@example.com"), call("get_invoices", user_id="u-77")], ["ANSWER: $49.00"])

tool_task(ACCT, "lee@acme.test moved to the starter plan before their latest invoice, but that invoice charged the pro "
                "price. Credit the difference between what that invoice charged and the starter price, with reason "
                "\"plan change\".", {
    "get_user": [rec({"user_id": "u-512", "plan": "starter", "plan_changed": "2026-10-01"}, email="lee@acme.test")],
    "get_invoices": [rec({"invoices": [{"id": "in-640", "date": "2026-10-05", "amount_cents": 4900, "plan": "pro"},
                                       {"id": "in-611", "date": "2026-09-05", "amount_cents": 4900, "plan": "pro"}]},
                         user_id="u-512")],
    "get_plan_price": [rec({"plan": "starter", "price_cents": 1900}, plan="starter"),
                       rec({"plan": "pro", "price_cents": 4900}, plan="pro"),
                       rec({"plan": "team", "price_cents": 9900}, plan="team")],
    "issue_credit": [ok(user_id="u-512")],
}, [call("get_user", email="lee@acme.test"),
    any_order(call("get_invoices", user_id="u-512"), call("get_plan_price", plan="starter")),
    call("issue_credit", user_id="u-512", amount_cents=3000, reason="plan change")])

# ---------------------------------------------------------------- hard tier
# Longer chains, distractor records, mid-chain tool failures, and arithmetic over tool results.

SHOP2 = dict(SHOP, tools=SHOP["tools"] + [
    fn("get_sales", "Units of a SKU sold at one warehouse in the last 7 days.", ["sku", "warehouse"],
       sku=S, warehouse=enum("NORTH", "SOUTH", "EAST"))],
    read_only=SHOP["read_only"] + ["get_sales"])

CAL2 = dict(CAL, tools=CAL["tools"] + [
    fn("get_free_busy", "Busy intervals for any colleague on a date.", ["email", "date"], email=S, date=DATE)],
    read_only=CAL["read_only"] + ["get_free_busy"])


def hard(*args, **kwargs):
    tool_task(*args, tier="hard", **kwargs)


hard(SHOP, "Order ORD-950 needs its full quantity reserved. If no warehouse has enough on its own, reserve as many units "
           "as possible at the warehouse with the most stock, then the rest at the next-most, and so on.", {
    "get_order": [rec({"order_id": "ORD-950", "sku": "SKU-61", "quantity": 14, "status": "processing"}, order_id="ORD-950")],
    "get_stock": [rec({"units": 6}, sku="SKU-61", warehouse="NORTH"), rec({"units": 9}, sku="SKU-61", warehouse="SOUTH"),
                  rec({"units": 4}, sku="SKU-61", warehouse="EAST")],
    "reserve": [ok(order_id="ORD-950")],
}, [call("get_order", order_id="ORD-950"),
    any_order(call("get_stock", sku="SKU-61", warehouse="NORTH"), call("get_stock", sku="SKU-61", warehouse="SOUTH"),
              call("get_stock", sku="SKU-61", warehouse="EAST")),
    call("reserve", order_id="ORD-950", sku="SKU-61", warehouse="SOUTH", quantity=9),
    call("reserve", order_id="ORD-950", sku="SKU-61", warehouse="NORTH", quantity=5)])

hard(SHOP, "Reserve order ORD-961 at the warehouse with the most units of its item. If a reservation fails, try the "
           "warehouse with the next-most units that can still cover the whole order.", {
    "get_order": [rec({"order_id": "ORD-961", "sku": "SKU-70", "quantity": 8, "status": "processing"}, order_id="ORD-961")],
    "get_stock": [rec({"units": 12}, sku="SKU-70", warehouse="NORTH"), rec({"units": 10}, sku="SKU-70", warehouse="SOUTH"),
                  rec({"units": 3}, sku="SKU-70", warehouse="EAST")],
    "reserve": [rec({"status": "error", "error": "warehouse NORTH is offline for maintenance"}, warehouse="NORTH"),
                ok(warehouse="SOUTH")],
}, [call("get_order", order_id="ORD-961"),
    any_order(call("get_stock", sku="SKU-70", warehouse="NORTH"), call("get_stock", sku="SKU-70", warehouse="SOUTH"),
              call("get_stock", sku="SKU-70", warehouse="EAST")),
    call("reserve", order_id="ORD-961", sku="SKU-70", warehouse="NORTH", quantity=8),
    call("reserve", order_id="ORD-961", sku="SKU-70", warehouse="SOUTH", quantity=8)])

hard(SHOP, "Customer C-90 says the glass carafe arrived broken in every order delivered to them in October 2026. For each "
           "of their orders delivered in October 2026, refund only the carafe units, with reason \"damaged\". Orders "
           "that are not delivered, or were delivered outside October, get nothing.", {
    "get_customer": [rec({"customer_id": "C-90", "order_ids": ["ORD-11", "ORD-12", "ORD-13", "ORD-14"]}, customer_id="C-90")],
    "get_order": [
        rec({"order_id": "ORD-11", "status": "delivered", "delivered_date": "2026-10-03",
             "items": [{"name": "glass carafe", "quantity": 1, "unit_price_cents": 3400}]}, order_id="ORD-11"),
        rec({"order_id": "ORD-12", "status": "delivered", "delivered_date": "2026-09-28",
             "items": [{"name": "glass carafe", "quantity": 1, "unit_price_cents": 3400}]}, order_id="ORD-12"),
        rec({"order_id": "ORD-13", "status": "shipped",
             "items": [{"name": "glass carafe", "quantity": 1, "unit_price_cents": 3400}]}, order_id="ORD-13"),
        rec({"order_id": "ORD-14", "status": "delivered", "delivered_date": "2026-10-15",
             "items": [{"name": "stoneware mug", "quantity": 4, "unit_price_cents": 1150},
                       {"name": "glass carafe", "quantity": 2, "unit_price_cents": 3400}]}, order_id="ORD-14")],
    "issue_refund": [ok(order_id="ORD-11"), ok(order_id="ORD-14")],
}, [call("get_customer", customer_id="C-90"),
    any_order(call("get_order", order_id="ORD-11"), call("get_order", order_id="ORD-12"),
              call("get_order", order_id="ORD-13"), call("get_order", order_id="ORD-14")),
    any_order(call("issue_refund", order_id="ORD-11", amount_cents=3400, reason="damaged"),
              call("issue_refund", order_id="ORD-14", amount_cents=6800, reason="damaged"))])

hard(SHOP2, "At its current 7-day sales rate, which warehouse will run out of SKU-77 first? Answer with the warehouse "
            "name in capitals.", {
    "get_stock": [rec({"units": 40}, sku="SKU-77", warehouse="NORTH"), rec({"units": 25}, sku="SKU-77", warehouse="SOUTH"),
                  rec({"units": 9}, sku="SKU-77", warehouse="EAST")],
    "get_sales": [rec({"units_sold_7d": 70}, sku="SKU-77", warehouse="NORTH"),
                  rec({"units_sold_7d": 35}, sku="SKU-77", warehouse="SOUTH"),
                  rec({"units_sold_7d": 14}, sku="SKU-77", warehouse="EAST")],
}, [any_order(*[call(f, sku="SKU-77", warehouse=w) for f in ("get_stock", "get_sales") for w in ("NORTH", "SOUTH", "EAST")])],
    ["ANSWER: NORTH"])

hard(CAL2, "Find the earliest 60-minute slot on 2026-10-22 or 2026-10-23, between 09:00 and 17:00, when I, Priya "
           "(priya@northwind.io) and Leo (leo.marsh@northwind.io) are all free, and book \"Launch retro\" there with both "
           "of them. List attendees in alphabetical order.", {
    "list_events": [
        rec({"events": [{"id": "m1", "title": "Workshop", "start_time": "09:00", "end_time": "12:00"},
                        {"id": "m2", "title": "Customer visit", "start_time": "13:00", "end_time": "15:00"}]}, date="2026-10-22"),
        rec({"events": [{"id": "m3", "title": "Board prep", "start_time": "09:00", "end_time": "10:30"}]}, date="2026-10-23")],
    "get_free_busy": [
        rec({"busy": [["12:00", "13:30"], ["15:30", "17:00"]]}, email="priya@northwind.io", date="2026-10-22"),
        rec({"busy": [["10:00", "11:00"]]}, email="priya@northwind.io", date="2026-10-23"),
        rec({"busy": [["15:00", "16:00"]]}, email="leo.marsh@northwind.io", date="2026-10-22"),
        rec({"busy": [["11:00", "11:30"], ["12:30", "13:00"]]}, email="leo.marsh@northwind.io", date="2026-10-23")],
    "create_event": [ok()],
}, [any_order(call("list_events", date="2026-10-22"), call("list_events", date="2026-10-23"),
              call("get_free_busy", email="priya@northwind.io", date="2026-10-22"),
              call("get_free_busy", email="priya@northwind.io", date="2026-10-23"),
              call("get_free_busy", email="leo.marsh@northwind.io", date="2026-10-22"),
              call("get_free_busy", email="leo.marsh@northwind.io", date="2026-10-23")),
    call("create_event", date="2026-10-23", start_time="11:30", duration_minutes=60,
         attendees=["leo.marsh@northwind.io", "priya@northwind.io"])])

hard(CAL, "Leo (leo.marsh@northwind.io) is out this Friday, 2026-10-23. Move each of my Friday meetings that includes Leo "
          "to the same time on Monday 2026-10-26; if I already have something at that Monday time, move it one hour "
          "later instead.", {
    "list_events": [
        rec({"events": [
            {"id": "f1", "title": "Standup", "start_time": "09:00", "end_time": "09:15", "attendees": ["leo.marsh@northwind.io", "priya@northwind.io"]},
            {"id": "f2", "title": "Lunch", "start_time": "12:00", "end_time": "13:00", "attendees": []},
            {"id": "f3", "title": "Pricing deep dive", "start_time": "14:00", "end_time": "15:00", "attendees": ["leo.marsh@northwind.io"]},
            {"id": "f4", "title": "Recruiting sync", "start_time": "16:00", "end_time": "16:30", "attendees": ["dana@northwind.io"]}]},
            date="2026-10-23"),
        rec({"events": [{"id": "n1", "title": "Weekly planning", "start_time": "09:00", "end_time": "10:00", "attendees": []},
                        {"id": "n2", "title": "Ops review", "start_time": "15:00", "end_time": "16:00", "attendees": []}]},
            date="2026-10-26")],
    "move_event": [ok(event_id="f1"), ok(event_id="f3")],
}, [any_order(call("list_events", date="2026-10-23"), call("list_events", date="2026-10-26")),
    any_order(call("move_event", event_id="f1", new_date="2026-10-26", new_start_time="10:00"),
              call("move_event", event_id="f3", new_date="2026-10-26", new_start_time="14:00"))])

hard(TRAVEL, "Book Lena Fischer from LIS to FRA via MAD on 2026-11-30: one flight LIS to MAD and one MAD to FRA, with at "
             "least 60 minutes between landing in MAD and departing MAD, at the lowest total price.", {
    "search_flights": [
        rec({"flights": [{"flight_id": "IB3101-1130", "departs": "07:00", "arrives": "09:15", "price": 80, "currency": "EUR"},
                         {"flight_id": "TP1026-1130", "departs": "10:00", "arrives": "12:15", "price": 45, "currency": "EUR"},
                         {"flight_id": "IB3105-1130", "departs": "13:30", "arrives": "15:45", "price": 52, "currency": "EUR"}]},
            origin="LIS", destination="MAD"),
        rec({"flights": [{"flight_id": "LH1121-1130", "departs": "12:45", "arrives": "15:15", "price": 40, "currency": "EUR"},
                         {"flight_id": "IB3530-1130", "departs": "14:00", "arrives": "16:30", "price": 75, "currency": "EUR"},
                         {"flight_id": "LH1123-1130", "departs": "16:30", "arrives": "19:00", "price": 58, "currency": "EUR"}]},
            origin="MAD", destination="FRA")],
    "book_flight": [ok()],
}, [any_order(call("search_flights", origin="LIS", destination="MAD", date="2026-11-30"),
              call("search_flights", origin="MAD", destination="FRA", date="2026-11-30")),
    any_order(call("book_flight", flight_id="TP1026-1130", passenger_name="Lena Fischer"),
              call("book_flight", flight_id="LH1123-1130", passenger_name="Lena Fischer"))])

hard(TRAVEL, "File each of these receipts as its own expense: taxi 38.50 EUR (ground_transport), team dinner 61.20 GBP "
             "(meals), hotel 980.00 CHF (lodging), train 54.00 USD (ground_transport).", {
    "convert_currency": [rec({"amount": 41.70, "currency": "USD"}, from_currency="EUR"),
                         rec({"amount": 77.55, "currency": "USD"}, from_currency="GBP"),
                         rec({"amount": 1123.43, "currency": "USD"}, from_currency="CHF"),
                         rec({"amount": 54.0, "currency": "USD"}, from_currency="USD")],
    "file_expense": [ok()],
}, [any_order(call("convert_currency", amount=38.5, from_currency="EUR", to_currency="USD"),
              call("convert_currency", amount=61.2, from_currency="GBP", to_currency="USD"),
              call("convert_currency", amount=980, from_currency="CHF", to_currency="USD"),
              call("file_expense", amount_usd_cents=4170, category="ground_transport"),
              call("file_expense", amount_usd_cents=7755, category="meals"),
              call("file_expense", amount_usd_cents=112343, category="lodging"),
              call("file_expense", amount_usd_cents=5400, category="ground_transport"))])

hard(ACCT, "kim@orbit.test switched from the team plan to pro partway through October. Policy: credit the unused part of "
           "the old plan, computed as old plan price x (days from the change date through 2026-10-31, inclusive) / 31, "
           "rounded down to a whole cent. Use reason \"proration\".", {
    "get_user": [rec({"user_id": "u-808", "plan": "pro", "previous_plan": "team", "plan_changed": "2026-10-15"},
                     email="kim@orbit.test")],
    "get_plan_price": [rec({"plan": "team", "price_cents": 9900}, plan="team"),
                       rec({"plan": "pro", "price_cents": 4900}, plan="pro"),
                       rec({"plan": "starter", "price_cents": 1900}, plan="starter")],
    "issue_credit": [ok(user_id="u-808")],
}, [call("get_user", email="kim@orbit.test"), call("get_plan_price", plan="team"),
    call("issue_credit", user_id="u-808", amount_cents=5429, reason="proration")])

hard(ACCT, "Audit sana@kite.test's invoices. A duplicate is an invoice with the same date and the same amount as another "
           "invoice of theirs. For each set of duplicates, keep one charge and issue one credit per extra charge, for "
           "that amount, with reason \"duplicate charge\".", {
    "get_user": [rec({"user_id": "u-3030", "plan": "team"}, email="sana@kite.test")],
    "get_invoices": [rec({"invoices": [
        {"id": "in-9", "date": "2026-10-05", "amount_cents": 9900},
        {"id": "in-8", "date": "2026-10-05", "amount_cents": 1900},
        {"id": "in-7", "date": "2026-09-05", "amount_cents": 9900},
        {"id": "in-6", "date": "2026-09-05", "amount_cents": 9900},
        {"id": "in-5", "date": "2026-08-05", "amount_cents": 4900},
        {"id": "in-4", "date": "2026-08-05", "amount_cents": 4900},
        {"id": "in-3", "date": "2026-08-05", "amount_cents": 4900},
        {"id": "in-2", "date": "2026-07-05", "amount_cents": 4900}]}, user_id="u-3030")],
    "issue_credit": [ok(user_id="u-3030")],
}, [call("get_user", email="sana@kite.test"), call("get_invoices", user_id="u-3030"),
    any_order(call("issue_credit", user_id="u-3030", amount_cents=9900, reason="duplicate charge"),
              call("issue_credit", user_id="u-3030", amount_cents=4900, reason="duplicate charge"),
              call("issue_credit", user_id="u-3030", amount_cents=4900, reason="duplicate charge"))])

# ---------------------------------------------------------------- schema stress (single action, exact arguments)

SCHEMA_SYSTEM = ("You are an assistant that operates business systems through tools. Call the tool with exactly the "
                 "arguments the request specifies: no extra optional fields, correct JSON types.")
SCHEMA_TASKS = []


def schema_task(prompt, tool, arguments):
    SCHEMA_TASKS.append(dict(prompt=prompt, tool=tool, arguments=arguments))


schema_task(
    "Ship two boxes to Inês Duarte, Rua das Flores 12, Porto, 4050-262, Portugal (country code PT). Box one weighs 2.5 kg "
    "and is 30 by 20 by 15 cm; box two weighs 0.8 kg and is 20 by 20 by 10 cm. Signature required.",
    fn("create_shipment", "Create a shipment.", ["recipient", "packages", "signature_required"],
       recipient={"type": "object", "required": ["name", "address"], "properties": {
           "name": S, "address": {"type": "object", "required": ["line1", "city", "postal_code", "country"], "properties": {
               "line1": S, "line2": S, "city": S, "postal_code": S, "country": {"type": "string", "pattern": "^[A-Z]{2}$"}}}}},
       packages={"type": "array", "items": {"type": "object", "required": ["weight_kg", "dimensions_cm"], "properties": {
           "weight_kg": N, "dimensions_cm": {"type": "object", "required": ["length", "width", "height"],
                                             "properties": {"length": I, "width": I, "height": I}}}}},
       signature_required=B),
    {"recipient": {"name": "Inês Duarte", "address": {"line1": "Rua das Flores 12", "city": "Porto",
                                                       "postal_code": "4050-262", "country": "PT"}},
     "packages": [{"weight_kg": 2.5, "dimensions_cm": {"length": 30, "width": 20, "height": 15}},
                  {"weight_kg": 0.8, "dimensions_cm": {"length": 20, "width": 20, "height": 10}}],
     "signature_required": True},
)

schema_task(
    "Open a ticket titled \"Login page times out\" with priority high. Leave it unassigned with no due date and no labels.",
    fn("create_ticket", "Create a support ticket.", ["title", "priority"], title=S,
       priority=enum("low", "medium", "high", "urgent"), assignee=S, due_date=DATE,
       labels={"type": "array", "items": S}),
    {"title": "Login page times out", "priority": "high"},
)

schema_task(
    "Set zone 3 to heat mode at 21.5 degrees Celsius.",
    fn("set_thermostat", "Set a thermostat zone.", ["zone_id", "target_celsius", "mode"],
       zone_id=I, target_celsius=N, mode=enum("heat", "cool", "auto", "off")),
    {"zone_id": 3, "target_celsius": 21.5, "mode": "heat"},
)

schema_task(
    "Schedule the sales report to run every week at 08:00.",
    fn("schedule_report", "Schedule a report once (date string) or on a recurrence (object).", ["report", "when"],
       report=enum("sales", "inventory", "churn"),
       when={"anyOf": [{"type": "string", "description": "one-off date YYYY-MM-DD"},
                       {"type": "object", "required": ["every", "at"],
                        "properties": {"every": enum("day", "week", "month"), "at": {"type": "string", "description": "HH:MM"}}}]}),
    {"report": "sales", "when": {"every": "week", "at": "08:00"}},
)

schema_task(
    "Give user u-88 write and read access but not admin. List permissions in alphabetical order.",
    fn("set_permissions", "Replace a user's permissions.", ["user_id", "permissions"], user_id=S,
       permissions={"type": "array", "uniqueItems": True, "items": enum("admin", "read", "write")}),
    {"user_id": "u-88", "permissions": ["read", "write"]},
)

schema_task(
    "Remove the phone number from profile u-19 (set it to null). Change nothing else.",
    fn("update_profile", "Update profile fields. Omitted fields are unchanged; null clears a field.", ["user_id"],
       user_id=S, phone={"type": ["string", "null"]}, display_name={"type": ["string", "null"]}),
    {"user_id": "u-19", "phone": None},
)

schema_task(
    "Invoice customer C-450: 3 units of SKU-A1; 10 units of SKU-B7 with a 15 percent discount; and 1 unit of SKU-Z9 with a "
    "fixed discount of 5.50.",
    fn("create_invoice", "Create an invoice.", ["customer_id", "lines"], customer_id=S,
       lines={"type": "array", "items": {"type": "object", "required": ["sku", "quantity"], "properties": {
           "sku": S, "quantity": I, "discount": {"type": "object", "required": ["type", "value"],
                                               "properties": {"type": enum("percent", "fixed"), "value": N}}}}}),
    {"customer_id": "C-450", "lines": [
        {"sku": "SKU-A1", "quantity": 3},
        {"sku": "SKU-B7", "quantity": 10, "discount": {"type": "percent", "value": 15}},
        {"sku": "SKU-Z9", "quantity": 1, "discount": {"type": "fixed", "value": 5.5}}]},
)

schema_task(
    "Search my notes for this exact phrase, including the punctuation and symbols: "
    "<tag a=\"1\"> & 'quoted' \\ path </tag>",
    fn("search_notes", "Full-text search over notes. The query is matched literally.", ["query"], query=S),
    {"query": "<tag a=\"1\"> & 'quoted' \\ path </tag>"},
)

schema_task(
    "Do a dry run of transferring 12,500,000.00 dollars, expressed in cents, from account 0012345678 to account 0098765432. "
    "Account numbers are strings and keep their leading zeros.",
    fn("transfer", "Move money between accounts.", ["amount_cents", "from_account", "to_account", "dry_run"],
       amount_cents=I, from_account=S, to_account=S, dry_run=B),
    {"amount_cents": 1250000000, "from_account": "0012345678", "to_account": "0098765432", "dry_run": True},
)

schema_task(
    "Set the alert level for service checkout to level 2 and mute it for 90 minutes.",
    fn("set_alert", "Configure alerting for a service.", ["service", "level", "mute_minutes"], service=S,
       level={"type": "string", "enum": ["1", "2", "3"]}, mute_minutes=I),
    {"service": "checkout", "level": "2", "mute_minutes": 90},
)


# ---------------------------------------------------------------- build + checks

def flat(steps):
    for s in steps:
        yield from s.get("any_order", [s])


def check(task, tools):
    problems = []
    schemas = {t["function"]["name"]: t["function"]["parameters"] for t in tools}
    perfect = []
    for c in flat(task["expected_calls"]):
        if c["name"] not in schemas:
            problems.append(f"unknown tool {c['name']}")
            continue
        # expected args are a subset; validate the properties they set
        partial = dict(schemas[c["name"]], required=[])
        problems += [f"{c['name']}: {e.message}" for e in Draft202012Validator(partial).iter_errors(c["arguments"])]
        output = lookup_tool(task, c["name"], c["arguments"])
        if "no record found" in json.dumps(output):
            problems.append(f"no canned output for {c['name']} {c['arguments']}")
        perfect.append({"name": c["name"], "arguments": c["arguments"], "parse_error": None})
    answer = " ".join(task.get("answer_contains", []))
    g = grader.grade(task, {"tool_calls": perfect, "content": f"Done. {answer}"})
    if not g["correct"]:
        problems.append(f"perfect replay grades as {g}")
    return problems


def main():
    root = Path(__file__).resolve().parents[1]
    problems, rows = [], []
    for k, t in enumerate(TOOL_TASKS, 1):
        w = t["world"]
        row = {"id": f"tool-{k:03d}", "category": "tools", "grader": "tools", "tier": t["tier"],
               "messages": [{"role": "system", "content": w["system"]}, {"role": "user", "content": t["prompt"]}],
               "tools": w["tools"], "read_only": w["read_only"], "tool_responses": t["tool_responses"],
               "expected_calls": t["expected_calls"], "answer_contains": t["answer_contains"], "source": SOURCE}
        problems += [f"{row['id']}: {p}" for p in check(row, w["tools"])]
        rows.append(row)
    schema_rows = []
    for k, t in enumerate(SCHEMA_TASKS, 1):
        name = t["tool"]["function"]["name"]
        row = {"id": f"schema-{k:03d}", "category": "tool_schema", "grader": "tools", "tier": "core",
               "messages": [{"role": "system", "content": SCHEMA_SYSTEM}, {"role": "user", "content": t["prompt"]}],
               "tools": [t["tool"]], "read_only": [], "tool_responses": {name: [ok()]},
               "expected_calls": [{"name": name, "arguments": t["arguments"], "exact": True}], "source": SOURCE}
        full = Draft202012Validator(t["tool"]["function"]["parameters"]).iter_errors(t["arguments"])
        problems += [f"{row['id']}: {e.message}" for e in full]
        problems += [f"{row['id']}: {p}" for p in check(row, [t["tool"]])]
        schema_rows.append(row)
    if problems:
        raise SystemExit("\n".join(problems))
    for name, data in (("tools.jsonl", rows), ("tool_schema.jsonl", schema_rows)):
        with (root / name).open("w") as f:
            for r in data:
                f.write(json.dumps(r) + "\n")
        print(f"{len(data)} tasks -> {root / name}")


if __name__ == "__main__":
    main()
