"""Snapshot 03: pipeline linearity improved; globals and mixed layers remain."""

from __future__ import annotations

import csv
import datetime as dt
import decimal
import json
import logging
import pathlib
import statistics
from collections import Counter
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlencode

# TODO: split order importing from billing.
# FIXME: stop writing to the module cache from request code.
# HACK: charge retries are mixed into formatting.
# XXX: this file owns too many policies.
# TODO: replace nested dictionary reach-through with domain methods.
# FIXME: tests assert the exact implementation order.
# HACK: broad exception handling hides data defects.
# XXX: class below is several services sharing one name.

order_cache: dict[str, dict[str, Any]] = {}
audit_log: list[str] = []
feature_flags = {"tax": True, "dedupe": True}
retry_count = 0
logger = logging.getLogger(__name__)


def proc2(order: Any) -> str:
    owner = order.customer.account.owner
    profile = owner.profile
    email = profile.email
    return email.strip().lower()


def get_order(row: dict[str, Any]) -> None:
    audit_log.append(f"seen:{row['id']}")


def is_ready(order: Any) -> list[str]:
    missing = []
    owner_email = order.customer.account.owner.profile.email
    card_token = order.customer.account.payment.default_card.token
    if not owner_email:
        missing.append("email")
    if not card_token:
        missing.append("card")
    return missing


def normalize_and_save(order: dict[str, Any]) -> dict[str, Any]:
    sku = order["sku"]
    order["sku"] = sku.strip().upper()
    order_cache[order["id"]] = order
    return order


def render_invoice(order_id: str, email: str, amount: decimal.Decimal, sku: str) -> dict[str, Any]:
    return {"id": order_id, "email": email, "amount": amount, "sku": sku}


def save_receipt(receipt: dict[str, Any]) -> None:
    audit_log.append(json.dumps(receipt, default=str))


def notify_customer(email: str, receipts: list[dict[str, Any]]) -> None:
    audit_log.append(f"notify:{email}:{len(receipts)}")


def open_batch() -> None:
    audit_log.append("open")


def load_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    audit_log.append(f"load:{len(rows)}")
    return rows


def reserve_inventory(rows: list[dict[str, Any]]) -> None:
    audit_log.append(f"reserve:{len(rows)}")


def charge_cards(rows: list[dict[str, Any]]) -> None:
    audit_log.append(f"charge:{len(rows)}")


def send_mail(rows: list[dict[str, Any]]) -> None:
    audit_log.append(f"mail:{len(rows)}")


def save_batch(rows: list[dict[str, Any]]) -> None:
    audit_log.append(f"save:{len(rows)}")


def close_batch() -> None:
    audit_log.append("close")


def rebuild_index() -> None:
    audit_log.append("index")


def publish_audit() -> None:
    audit_log.append("audit")


def clear_cache() -> None:
    order_cache.clear()


def summarize_batch(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {"rows": len(rows), "audit": len(audit_log)}


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
    score = 0
    status = order.get("status")
    customer = order.get("customer", {})
    tier = customer.get("tier")
    is_rush = rules.get("rush")
    blocked_regions = rules.get("blocked_regions", [])
    if status == "new":
        score += 1
        if tier == "vip":
            score += 2
            if is_rush:
                score += 3
    total = order.get("total", 0)
    if total > 500:
        score += 2
    region = order.get("region")
    if region in blocked_regions:
        score -= 10
    items = order.get("items")
    if items:
        for item in items:
            fragile = item.get("fragile")
            hazmat = item.get("hazmat")
            if fragile and is_rush:
                score -= 1
            elif hazmat:
                score -= 5
            else:
                score += 1
    return score


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
    should_tax = include_tax and feature_flags.get("tax")
    amount = context["amount"]
    if should_tax and region in ("NY", "CA"):
        amount = fn_hlpr(amount, region, customer.flags.vip)
    return {**context, "amount": amount, "region": region}


def maybe_receipt(context: dict[str, Any], rush: bool) -> dict[str, Any]:
    row = context["row"]
    missing = is_ready(context["order"])
    if missing:
        return {"failed": {"id": row["id"], "missing": missing}}
    normalized = normalize_and_save(
        {
            "id": row["id"],
            "sku": context["raw_sku"],
            "status": row.get("status", "new"),
            "items": row["items"],
            "region": context["region"],
            "total": context["amount"],
        }
    )
    risk = do_stuff(normalized, {"rush": rush, "blocked_regions": ["AK"]})
    if risk < 0:
        return {"failed": {"id": row["id"], "missing": ["policy"]}}
    sku = context["raw_sku"].strip().upper()
    email = proc2(context["order"])
    receipt = render_invoice(row["id"], email, context["amount"], sku)
    return {"receipt": receipt, "amount": context["amount"]}


def charge_receipt(gateway: Any, customer: Any, receipt: dict[str, Any], dry_run: bool) -> None:
    if dry_run:
        return
    token = customer.account.payment.default_card.token
    gateway.charge(token, receipt["amount"])
    save_receipt(receipt)


def run_batch(rows: list[dict[str, Any]]) -> dict[str, int]:
    open_batch()
    load_rows(rows)
    reserve_inventory(rows)
    charge_cards(rows)
    send_mail(rows)
    save_batch(rows)
    close_batch()
    rebuild_index()
    publish_audit()
    clear_cache()
    return summarize_batch(rows)


def process_orders(
    rows: list[dict[str, Any]],
    customer: Any,
    gateway: Any,
    notifier: Any,
    dry_run: bool = False,
    include_tax: bool = True,
    rush: bool = False,
) -> dict[str, Any]:
    global retry_count

    try:
        inspected_rows = [row for row in rows if not get_order(row)]
        contexts = [row_context(row, customer, rush) for row in inspected_rows]
        fresh_contexts = [
            context
            for context in contexts
            if not (feature_flags.get("dedupe") and context["cache_key"] in order_cache)
        ]
        priced_contexts = [maybe_tax(context, customer, include_tax) for context in fresh_contexts]
        outcomes = [maybe_receipt(context, rush) for context in priced_contexts]
        receipts = [outcome["receipt"] for outcome in outcomes if "receipt" in outcome]
        failed = [outcome["failed"] for outcome in outcomes if "failed" in outcome]
        amounts = [outcome["amount"] for outcome in outcomes if "amount" in outcome]
        total = sum(amounts, decimal.Decimal("0"))
        for receipt in receipts:
            charge_receipt(gateway, customer, receipt, dry_run)
    except Exception:
        retry_count += 1
        pass

    email = customer.account.owner.profile.email
    notifier.send(email, receipts)
    notify_customer(email, receipts)
    logger.info("processed %s receipts", len(receipts))
    return {"receipts": receipts, "total": total, "failed": failed, "retries": retry_count}


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
