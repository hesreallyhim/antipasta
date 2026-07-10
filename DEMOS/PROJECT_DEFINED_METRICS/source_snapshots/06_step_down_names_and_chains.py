"""Snapshot 06: step-down order, clearer names, and shallow chains."""

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


@dataclass
class OrderServices:
    gateway: Any
    notifier: Any
    state: BatchState


@dataclass(frozen=True)
class ProcessingOptions:
    dry_run: bool = False
    include_tax: bool = True
    rush: bool = False


def process_orders(
    rows: list[dict[str, Any]],
    customer: Any,
    services: OrderServices,
    options: ProcessingOptions,
) -> dict[str, Any]:
    outcomes = prepare_outcomes(rows, customer, services.state, options)
    settlement = settle_outcomes(outcomes)
    charge_all(services.gateway, customer, settlement["receipts"], options, services.state)
    send_summary(customer, services.notifier, settlement["receipts"], services.state)
    return build_result(settlement, services.state)


def run_batch(rows: list[dict[str, Any]], state: BatchState) -> dict[str, int]:
    loaded_rows = prepare_batch(rows, state)
    execute_batch(loaded_rows, state)
    finish_batch(state)
    return summarize_batch(loaded_rows, state)


def prepare_outcomes(
    rows: list[dict[str, Any]],
    customer: Any,
    state: BatchState,
    options: ProcessingOptions,
) -> list[dict[str, Any]]:
    inspected_rows = inspect_rows(rows, state)
    contexts = build_contexts(inspected_rows, customer, options)
    fresh_contexts = remove_cached_contexts(contexts, state)
    priced_contexts = price_contexts(fresh_contexts, customer, options)
    return build_outcomes(priced_contexts, options, state)


def settle_outcomes(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    receipts = collect_receipts(outcomes)
    failed = collect_failures(outcomes)
    total = sum_outcome_amounts(outcomes)
    return {"receipts": receipts, "failed": failed, "total": total}


def charge_all(
    gateway: Any,
    customer: Any,
    receipts: list[dict[str, Any]],
    options: ProcessingOptions,
    state: BatchState,
) -> None:
    for receipt in receipts:
        charge_receipt(gateway, customer, receipt, options, state)


def send_summary(
    customer: Any,
    notifier: Any,
    receipts: list[dict[str, Any]],
    state: BatchState,
) -> None:
    email = owner_email(customer)
    notifier.send(email, receipts)
    notify_customer(email, receipts, state)
    LOGGER.info("processed %s receipts", len(receipts))


def build_result(settlement: dict[str, Any], state: BatchState) -> dict[str, Any]:
    return {
        "receipts": settlement["receipts"],
        "total": settlement["total"],
        "failed": settlement["failed"],
        "retries": state.retry_count,
    }


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


def inspect_rows(rows: list[dict[str, Any]], state: BatchState) -> list[dict[str, Any]]:
    inspected = []
    for row in rows:
        record_order_seen(row, state)
        inspected.append(row)
    return inspected


def build_contexts(
    rows: list[dict[str, Any]],
    customer: Any,
    options: ProcessingOptions,
) -> list[dict[str, Any]]:
    contexts = []
    for row in rows:
        contexts.append(build_row_context(row, customer, options))
    return contexts


def remove_cached_contexts(
    contexts: list[dict[str, Any]],
    state: BatchState,
) -> list[dict[str, Any]]:
    fresh = []
    for context in contexts:
        if not is_duplicate_context(context, state):
            fresh.append(context)
    return fresh


def price_contexts(
    contexts: list[dict[str, Any]],
    customer: Any,
    options: ProcessingOptions,
) -> list[dict[str, Any]]:
    priced = []
    for context in contexts:
        priced.append(apply_tax_policy(context, customer, options))
    return priced


def build_outcomes(
    contexts: list[dict[str, Any]],
    options: ProcessingOptions,
    state: BatchState,
) -> list[dict[str, Any]]:
    outcomes = []
    for context in contexts:
        outcomes.append(build_receipt_outcome(context, options, state))
    return outcomes


def owner_email(contact: Any) -> str:
    email = contact.owner_email()
    stripped = email.strip()
    return stripped.lower()


def payment_token(customer: Any) -> str:
    return customer.default_payment_token()


def record_order_seen(row: dict[str, Any], state: BatchState) -> None:
    state.audit_log.append(f"seen:{row['id']}")


def missing_ready_fields(order: Any) -> list[str]:
    missing = []
    if not order.owner_email():
        missing.append("email")
    if not order.default_payment_token():
        missing.append("card")
    return missing


def normalize_order(order: dict[str, Any]) -> dict[str, Any]:
    sku = order["sku"]
    return {**order, "sku": sku.strip().upper()}


def save_normalized_order(order: dict[str, Any], state: BatchState) -> dict[str, Any]:
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


def calculate_adjusted_amount(
    value: decimal.Decimal,
    region: str,
    is_vip: bool,
) -> decimal.Decimal:
    taxed = apply_region_tax(value, region)
    return apply_vip_discount(taxed, is_vip)


def apply_region_tax(value: decimal.Decimal, region: str) -> decimal.Decimal:
    if region in ("NY", "CA"):
        return value * decimal.Decimal("1.0875")
    return value


def apply_vip_discount(value: decimal.Decimal, is_vip: bool) -> decimal.Decimal:
    if is_vip:
        return value * decimal.Decimal("0.90")
    return value


def score_order_risk(order: dict[str, Any], rules: dict[str, Any]) -> int:
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


def build_row_context(
    row: dict[str, Any],
    customer: Any,
    options: ProcessingOptions,
) -> dict[str, Any]:
    raw_amount = decimal.Decimal(str(row["amount"]))
    shipping = shipping_amount(row, options)
    credit = decimal.Decimal(str(row.get("credit", 0)))
    amount = raw_amount + shipping - credit
    first_item = row["items"][0]
    return {
        "row": row,
        "order": row["order"],
        "cache_key": f"{owner_email(customer)}:{row['id']}",
        "amount": amount,
        "raw_sku": first_item["sku"],
    }


def shipping_amount(row: dict[str, Any], options: ProcessingOptions) -> decimal.Decimal:
    shipping_value = row["shipping"] if options.rush else 0
    return decimal.Decimal(str(shipping_value))


def is_duplicate_context(context: dict[str, Any], state: BatchState) -> bool:
    return bool(FEATURE_FLAGS.get("dedupe") and context["cache_key"] in state.order_cache)


def apply_tax_policy(
    context: dict[str, Any],
    customer: Any,
    options: ProcessingOptions,
) -> dict[str, Any]:
    region = customer.region_code()
    amount = context["amount"]
    if options.include_tax and FEATURE_FLAGS.get("tax"):
        amount = calculate_adjusted_amount(amount, region, customer.is_vip())
    return {**context, "amount": amount, "region": region}


def build_receipt_outcome(
    context: dict[str, Any],
    options: ProcessingOptions,
    state: BatchState,
) -> dict[str, Any]:
    missing = missing_ready_fields(context["order"])
    if missing:
        return failed_outcome(context, missing)
    saved = save_context_order(context, state)
    if violates_order_policy(saved, options):
        return failed_outcome(context, ["policy"])
    return successful_outcome(context)


def failed_outcome(context: dict[str, Any], missing: list[str]) -> dict[str, Any]:
    row = context["row"]
    return {"failed": {"id": row["id"], "missing": missing}}


def save_context_order(context: dict[str, Any], state: BatchState) -> dict[str, Any]:
    record = build_order_record(context)
    normalized = normalize_order(record)
    return save_normalized_order(normalized, state)


def violates_order_policy(saved: dict[str, Any], options: ProcessingOptions) -> bool:
    rules = {"rush": options.rush, "blocked_regions": ["AK"]}
    return score_order_risk(saved, rules) < 0


def successful_outcome(context: dict[str, Any]) -> dict[str, Any]:
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
    email = owner_email(context["order"])
    return render_invoice(row["id"], email, context["amount"], sku)


def collect_receipts(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [outcome["receipt"] for outcome in outcomes if "receipt" in outcome]


def collect_failures(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [outcome["failed"] for outcome in outcomes if "failed" in outcome]


def sum_outcome_amounts(outcomes: list[dict[str, Any]]) -> decimal.Decimal:
    amounts = [outcome["amount"] for outcome in outcomes if "amount" in outcome]
    return sum(amounts, decimal.Decimal("0"))


def charge_receipt(
    gateway: Any,
    customer: Any,
    receipt: dict[str, Any],
    options: ProcessingOptions,
    state: BatchState,
) -> None:
    if options.dry_run:
        return
    gateway.charge(payment_token(customer), receipt["amount"])
    save_receipt(receipt, state)


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
        now = dt.datetime.utcnow()
        stamp = now.isoformat()
        receipt_id = receipt["id"]
        return f"{self.mail_host}:{stamp}:{receipt_id}"
