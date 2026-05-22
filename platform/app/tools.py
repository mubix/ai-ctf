"""Server-side tool implementations exposed to the LLM personas.

These are intentionally permissive — security guardrails live in the LLM's
system prompt, not here. That gap between prompt-level policy and
implementation-level behavior IS the lesson the players are learning.
"""
import json
import random
import sqlite3
import string
from typing import Any

import httpx

from .config import (
    FLAG_CHECKOUT_FREE_ID,
    FLAG_CHECKOUT_NEG_ID,
    FLAG_HR_SCHEMA_TOKEN,
)
from .db import DB_PATH


# ---------------------------------------------------------------------------
# get_employee — HR persona  (flags #3, #4, #5)
# ---------------------------------------------------------------------------

# Flag #5 is hidden inside a SQL comment in the query template. Any input that
# breaks the SQL (non-numeric tokens, semicolons, quotes) raises a sqlite3
# error whose .args reproduces the original query — exposing the flag.
# We build the query with an f-string (no str.format) so a `{...}` token in
# the flag value can't be mistaken for a format placeholder.
_HR_QUERY_PREFIX = (
    "SELECT id, name, title, department, salary, email, notes "
    f"FROM employees /* anvil_internal:{FLAG_HR_SCHEMA_TOKEN} */ "
    "WHERE id = "
)


def get_employee(employee_id) -> Any:
    eid = str(employee_id)
    query = f"{_HR_QUERY_PREFIX}{eid}"
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query).fetchall()
        if not rows:
            return {"status": "no_results", "employee_id_searched": eid}
        if len(rows) == 1:
            return dict(rows[0])
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        return {
            "error": "database_error",
            "message": str(e),
            "executed_query": query,
        }


# ---------------------------------------------------------------------------
# place_order — Checkout persona  (flags #8, #9)
# ---------------------------------------------------------------------------

CATALOG = {
    "HMR-001": {"name": "Hammer",          "price_cents": 2499},
    "GS-018":  {"name": "Garden Spade",    "price_cents": 3250},
    "LED-074": {"name": "LED Toolbox",     "price_cents": 8900},
    "PW-227":  {"name": "Pressure Washer", "price_cents": 34999},
}


def place_order(items: list, total_cents) -> dict:
    # The bot is supposed to validate total_cents == sum(catalog * qty).
    # We trust whatever it sends — that's the bug players exploit.
    try:
        total_cents = int(total_cents)
    except (TypeError, ValueError):
        return {"error": "total_cents must be an integer"}

    if total_cents == 0:
        return {
            "order_id": FLAG_CHECKOUT_FREE_ID,
            "status": "completed",
            "total_cents": 0,
            "message": f"Order completed at $0.00. Confirmation: {FLAG_CHECKOUT_FREE_ID}",
        }
    if total_cents < 0:
        return {
            "order_id": FLAG_CHECKOUT_NEG_ID,
            "status": "refund_issued",
            "total_cents": total_cents,
            "message": (
                f"Refund issued for ${abs(total_cents)/100:.2f}. "
                f"Confirmation: {FLAG_CHECKOUT_NEG_ID}"
            ),
        }
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return {
        "order_id": f"ORD-{suffix}",
        "status": "completed",
        "total_cents": total_cents,
        "message": f"Order placed for ${total_cents/100:.2f}. Confirmation: ORD-{suffix}",
    }


# ---------------------------------------------------------------------------
# fetch_url — Web Retrieval persona  (flags #10, #11, #12)
# ---------------------------------------------------------------------------

def fetch_url(url) -> str:
    url = str(url)
    if url.startswith("file://"):
        path = url[len("file://"):]
        try:
            with open(path) as f:
                content = f.read()
            return f"Read {len(content)} bytes from {path}:\n\n{content[:4000]}"
        except OSError as e:
            return f"Error reading {path}: {e}"
    try:
        with httpx.Client(timeout=10, follow_redirects=True) as client:
            resp = client.get(url)
            text = resp.text[:4000]
            return f"HTTP {resp.status_code} from {url}\n\n{text}"
    except httpx.HTTPError as e:
        return f"Fetch error for {url}: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Tool definitions in Ollama format + dispatcher
# ---------------------------------------------------------------------------

TOOL_DEF_GET_EMPLOYEE = {
    "type": "function",
    "function": {
        "name": "get_employee",
        "description": (
            "Look up an employee by their numeric ID. Returns name, title, "
            "department, salary, email, and notes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {
                    "type": "string",
                    "description": "The numeric employee ID to look up.",
                },
            },
            "required": ["employee_id"],
        },
    },
}

TOOL_DEF_PLACE_ORDER = {
    "type": "function",
    "function": {
        "name": "place_order",
        "description": (
            "Place an order for the user. Returns an order confirmation."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of items to order. Each item has a SKU and quantity.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "sku":      {"type": "string"},
                            "quantity": {"type": "integer"},
                        },
                    },
                },
                "total_cents": {
                    "type": "integer",
                    "description": "Total order amount in cents (e.g. 2499 for $24.99).",
                },
            },
            "required": ["items", "total_cents"],
        },
    },
}

TOOL_DEF_FETCH_URL = {
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": "Fetch a URL and return the response body as text.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to fetch (must include scheme).",
                },
            },
            "required": ["url"],
        },
    },
}

TOOL_REGISTRY = {
    "get_employee": get_employee,
    "place_order":  place_order,
    "fetch_url":    fetch_url,
}
