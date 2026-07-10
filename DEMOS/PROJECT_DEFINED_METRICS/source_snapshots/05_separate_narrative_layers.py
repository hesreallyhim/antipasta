"""Snapshot 05: orchestration and leaf computation are separated."""

from __future__ import annotations

import csv
import datetime as dt
import decimal
import json
import logging
import pathlib
import statistics
from collections import Counter
from dataclasses import dataclass, field
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlencode

# TODO: split order importing from billing.
# FIXME: tests assert the exact implementation order.
# XXX: class below is several services sharing one name.

LOGGER = logging.getLogger(__name__)
FEATURE_FLAGS = {"tax": True, "dedupe": True}


@dataclass
class BatchState:
    order_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    audit_log: list[str] = field(default_factory=list)
    retry_count: int = 0


def proc2(order: Any) -> str:
    owner = order.customer.account.owner
    profile = owner.profile
    email = profile.email
    return email.strip().lower()


def get_order(row: dict[str, Any], state: BatchState) -> None:
    state.audit_log.append(f"seen:{row['id']}")


def is_ready(order: Any) -> list[str]:
    missing = []
    owner_email = order.customer.account.owner.profile.email
    card_token = order.customer.account.payment.default_card.token
    if not owner_email:
        missing.append("email")
    if not card_token:
        missing.append("card")
    return missing


def normalize_and_save(order: dict[str, Any], state: BatchState) -> dict[str, Any]:
    sku = order["sku"]
    order["sku"] = sku.strip().upper()
    state.order_cache[order["id"]] = order
    return order


def render_invoice(order_id: str, email: str, amount: decimal.Decimal, sku: str) -> dict[str, Any]:
    return {"id": order_id, "email": email, "amount": amount, "sku": sku}


def save_receipt(receipt: dict[str, Any], state: BatchState) -> None:
    state.audit_log.append(json.dumps(receipt, default=str))


def notify_customer(email: str, receipts: list[dict[str, Any]], state: BatchState) -> None:
    state.audit_log.append(f"notify:{email}:{len(receipts)}")


def open_batch(state: BatchState) -> None:
    state.audit_log.append("open")


def load_rows(rows: list[dict[str, Any]], state: BatchState) -> list[dict[str, Any]]:
    state.audit_log.append(f"load:{len(rows)}")
    return rows


def reserve_inventory(rows: list[dict[str, Any]], state: BatchState) -> None:
    state.audit_log.append(f"reserve:{len(rows)}")


def charge_cards(rows: list[dict[str, Any]], state: BatchState) -> None:
    state.audit_log.append(f"charge:{len(rows)}")


def send_mail(rows: list[dict[str, Any]], state: BatchState) -> None:
    state.audit_log.append(f"mail:{len(rows)}")


def save_batch(rows: list[dict[str, Any]], state: BatchState) -> None:
    state.audit_log.append(f"save:{len(rows)}")


def close_batch(state: BatchState) -> None:
    state.audit_log.append("close")


def rebuild_index(state: BatchState) -> None:
    state.audit_log.append("index")


def publish_audit(state: BatchState) -> None:
    state.audit_log.append("audit")


def clear_cache(state: BatchState) -> None:
    state.order_cache.clear()


def summarize_batch(rows: list[dict[str, Any]], state: BatchState) -> dict[str, int]:
    return {"rows": len(rows), "audit": len(state.audit_log)}


def fn_hlpr(value: decimal.Decimal, region: str, vip: bool) -> decimal.Decimal:
    amount = value
    taxed_regions = ("NY", "CA")
    if region in taxed_regions:
        tax_rate = decimal.Decimal("1.0875")
        amount = amount * tax_rate
    if vip:
        vip_rate = decimal.Decimal("0.90")
        amount = amount * vip_rate
    return amount


def do_stuff(order: dict[str, Any], rules: dict[str, Any]) -> int:
    status_score = score_status(order, rules)
    total_score = score_total(order)
    region_score = score_region(order, rules)
    item_score = score_items(order, rules)
    return status_score + total_score + region_score + item_score


def score_status(order: dict[str, Any], rules: dict[str, Any]) -> int:
    status = order.get("status")
    customer = order.get("customer", {})
    tier = customer.get("tier")
    is_rush = rules.get("rush")
    if status == "new" and tier == "vip" and is_rush:
        return 6
    if status == "new" and tier == "vip":
        return 3
    if status == "new":
        return 1
    return 0


def score_total(order: dict[str, Any]) -> int:
    total = order.get("total", 0)
    if total > 500:
        return 2
    return 0


def score_region(order: dict[str, Any], rules: dict[str, Any]) -> int:
    region = order.get("region")
    blocked_regions = rules.get("blocked_regions", [])
    if region in blocked_regions:
        return -10
    return 0


def score_items(order: dict[str, Any], rules: dict[str, Any]) -> int:
    items = order.get("items") or []
    return sum(score_item(item, rules) for item in items)


def score_item(item: dict[str, Any], rules: dict[str, Any]) -> int:
    fragile = item.get("fragile")
    hazmat = item.get("hazmat")
    is_rush = rules.get("rush")
    if fragile and is_rush:
        return -1
    if hazmat:
        return -5
    return 1


def row_context(row: dict[str, Any], customer: Any, rush: bool) -> dict[str, Any]:
    order = row["order"]
    owner_email = customer.account.owner.profile.email
    cache_key = f"{owner_email}:{row['id']}"
    raw_amount = decimal.Decimal(str(row["amount"]))
    shipping_value = row["shipping"] if rush else 0
    shipping = decimal.Decimal(str(shipping_value))
    credit = decimal.Decimal(str(row.get("credit", 0)))
    amount = raw_amount + shipping - credit
    first_item = row["items"][0]
    raw_sku = first_item["sku"]
    return {
        "row": row,
        "order": order,
        "cache_key": cache_key,
        "amount": amount,
        "raw_sku": raw_sku,
    }


def maybe_tax(context: dict[str, Any], customer: Any, include_tax: bool) -> dict[str, Any]:
    region = customer.account.region.code
    should_tax = include_tax and FEATURE_FLAGS.get("tax")
    amount = context["amount"]
    if should_tax and region in ("NY", "CA"):
        amount = fn_hlpr(amount, region, customer.flags.vip)
    return {**context, "amount": amount, "region": region}


def maybe_receipt(context: dict[str, Any], rush: bool, state: BatchState) -> dict[str, Any]:
    row = context["row"]
    missing = is_ready(context["order"])
    if missing:
        return {"failed": {"id": row["id"], "missing": missing}}
    normalized = normalize_and_save(build_order_record(context), state)
    risk = do_stuff(normalized, {"rush": rush, "blocked_regions": ["AK"]})
    if risk < 0:
        return {"failed": {"id": row["id"], "missing": ["policy"]}}
    receipt = render_receipt(context)
    return {"receipt": receipt, "amount": context["amount"]}


def build_order_record(context: dict[str, Any]) -> dict[str, Any]:
    row = context["row"]
    return {
        "id": row["id"],
        "sku": context["raw_sku"],
        "status": row.get("status", "new"),
        "items": row["items"],
        "region": context["region"],
        "total": context["amount"],
    }


def render_receipt(context: dict[str, Any]) -> dict[str, Any]:
    row = context["row"]
    sku = context["raw_sku"].strip().upper()
    email = proc2(context["order"])
    return render_invoice(row["id"], email, context["amount"], sku)


def inspect_rows(rows: list[dict[str, Any]], state: BatchState) -> list[dict[str, Any]]:
    inspected = []
    for row in rows:
        get_order(row, state)
        inspected.append(row)
    return inspected


def build_contexts(
    rows: list[dict[str, Any]],
    customer: Any,
    rush: bool,
) -> list[dict[str, Any]]:
    contexts = []
    for row in rows:
        contexts.append(row_context(row, customer, rush))
    return contexts


def remove_cached_contexts(
    contexts: list[dict[str, Any]],
    state: BatchState,
) -> list[dict[str, Any]]:
    fresh = []
    for context in contexts:
        is_duplicate = FEATURE_FLAGS.get("dedupe") and context["cache_key"] in state.order_cache
        if not is_duplicate:
            fresh.append(context)
    return fresh


def price_contexts(
    contexts: list[dict[str, Any]],
    customer: Any,
    include_tax: bool,
) -> list[dict[str, Any]]:
    priced = []
    for context in contexts:
        priced.append(maybe_tax(context, customer, include_tax))
    return priced


def build_outcomes(
    contexts: list[dict[str, Any]],
    rush: bool,
    state: BatchState,
) -> list[dict[str, Any]]:
    outcomes = []
    for context in contexts:
        outcomes.append(maybe_receipt(context, rush, state))
    return outcomes


def collect_receipts(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [outcome["receipt"] for outcome in outcomes if "receipt" in outcome]


def collect_failures(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [outcome["failed"] for outcome in outcomes if "failed" in outcome]


def sum_outcome_amounts(outcomes: list[dict[str, Any]]) -> decimal.Decimal:
    amounts = [outcome["amount"] for outcome in outcomes if "amount" in outcome]
    return sum(amounts, decimal.Decimal("0"))


def prepare_outcomes(
    rows: list[dict[str, Any]],
    customer: Any,
    state: BatchState,
    include_tax: bool,
    rush: bool,
) -> list[dict[str, Any]]:
    inspected_rows = inspect_rows(rows, state)
    contexts = build_contexts(inspected_rows, customer, rush)
    fresh_contexts = remove_cached_contexts(contexts, state)
    priced_contexts = price_contexts(fresh_contexts, customer, include_tax)
    return build_outcomes(priced_contexts, rush, state)


def charge_all(
    gateway: Any,
    customer: Any,
    receipts: list[dict[str, Any]],
    dry_run: bool,
    state: BatchState,
) -> None:
    for receipt in receipts:
        charge_receipt(gateway, customer, receipt, dry_run, state)


def charge_receipt(
    gateway: Any,
    customer: Any,
    receipt: dict[str, Any],
    dry_run: bool,
    state: BatchState,
) -> None:
    if dry_run:
        return
    token = customer.account.payment.default_card.token
    gateway.charge(token, receipt["amount"])
    save_receipt(receipt, state)


def send_summary(
    customer: Any,
    notifier: Any,
    receipts: list[dict[str, Any]],
    state: BatchState,
) -> None:
    email = customer.account.owner.profile.email
    notifier.send(email, receipts)
    notify_customer(email, receipts, state)
    LOGGER.info("processed %s receipts", len(receipts))


def process_orders(
    rows: list[dict[str, Any]],
    customer: Any,
    gateway: Any,
    notifier: Any,
    state: BatchState,
    dry_run: bool = False,
    include_tax: bool = True,
    rush: bool = False,
) -> dict[str, Any]:
    outcomes = prepare_outcomes(rows, customer, state, include_tax, rush)
    receipts = collect_receipts(outcomes)
    failed = collect_failures(outcomes)
    total = sum_outcome_amounts(outcomes)
    charge_all(gateway, customer, receipts, dry_run, state)
    send_summary(customer, notifier, receipts, state)
    return {"receipts": receipts, "total": total, "failed": failed, "retries": state.retry_count}


def prepare_batch(rows: list[dict[str, Any]], state: BatchState) -> list[dict[str, Any]]:
    open_batch(state)
    return load_rows(rows, state)


def execute_batch(rows: list[dict[str, Any]], state: BatchState) -> None:
    reserve_inventory(rows, state)
    charge_cards(rows, state)
    send_mail(rows, state)
    save_batch(rows, state)


def finish_batch(state: BatchState) -> None:
    close_batch(state)
    rebuild_index(state)
    publish_audit(state)
    clear_cache(state)


def run_batch(rows: list[dict[str, Any]], state: BatchState) -> dict[str, int]:
    loaded_rows = prepare_batch(rows, state)
    execute_batch(loaded_rows, state)
    finish_batch(state)
    return summarize_batch(loaded_rows, state)


class OrderEverything:
    source_path = pathlib.Path("orders.csv")
    template_name = "invoice.html"
    gateway_name = "stripe"
    mail_host = "localhost"

    def load_rows(self) -> list[dict[str, Any]]:
        with self.source_path.open() as handle:
            rows = list(csv.DictReader(handle))
        return rows

    def render_email(self, receipt: dict[str, Any]) -> EmailMessage:
        message = EmailMessage()
        query_data = {"id": receipt["id"], "amount": receipt["amount"]}
        query = urlencode(query_data)
        message["Subject"] = f"{self.template_name}:{query}"
        body = json.dumps(receipt, default=str)
        message.set_content(body)
        return message

    def record_payment(self, amounts: list[decimal.Decimal]) -> dict[str, Any]:
        rendered_amounts = [str(amount) for amount in amounts]
        count_by_amount = Counter(rendered_amounts)
        mean_amount = statistics.mean(amounts)
        return {"gateway": self.gateway_name, "mean": mean_amount, "count": count_by_amount}

    def write_audit(self, receipt: dict[str, Any]) -> str:
        stamp = dt.datetime.utcnow().isoformat()
        receipt_id = receipt["id"]
        return f"{self.mail_host}:{stamp}:{receipt_id}"
