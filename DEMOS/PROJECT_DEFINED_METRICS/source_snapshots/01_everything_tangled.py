"""Snapshot 01: deliberately tangled project-defined metric fixture."""

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
    return order.customer.account.owner.profile.email.strip().lower()


def get_order(row: dict[str, Any]) -> None:
    audit_log.append(f"seen:{row['id']}")


def is_ready(order: Any) -> list[str]:
    missing = []
    if not order.customer.account.owner.profile.email:
        missing.append("email")
    if not order.customer.account.payment.default_card.token:
        missing.append("card")
    return missing


def normalize_and_save(order: dict[str, Any]) -> dict[str, Any]:
    order["sku"] = order["sku"].strip().upper()
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
    if region in ("NY", "CA"):
        amount = amount * decimal.Decimal("1.0875")
    if vip:
        amount = amount * decimal.Decimal("0.90")
    return amount


def do_stuff(order: dict[str, Any], rules: dict[str, Any]) -> int:
    score = 0
    if order.get("status") == "new":
        score += 1
        if order.get("customer", {}).get("tier") == "vip":
            score += 2
            if rules.get("rush"):
                score += 3
    if order.get("total", 0) > 500:
        score += 2
    if order.get("region") in rules.get("blocked_regions", []):
        score -= 10
    if order.get("items"):
        for item in order["items"]:
            if item.get("fragile") and rules.get("rush"):
                score -= 1
            elif item.get("hazmat"):
                score -= 5
            else:
                score += 1
    return score


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

    receipts = []
    total = decimal.Decimal("0")
    failed = []
    for row in rows:
        try:
            get_order(row)
            order = row["order"]
            cache_key = f"{customer.account.owner.profile.email}:{row['id']}"
            if feature_flags.get("dedupe") and cache_key in order_cache:
                continue
            amount = decimal.Decimal(str(row["amount"])) + decimal.Decimal(
                str(row["shipping"] if rush else 0)
            ) - decimal.Decimal(str(row.get("credit", 0)))
            if include_tax and feature_flags.get("tax") and customer.account.region.code in (
                "NY",
                "CA",
            ):
                amount = fn_hlpr(amount, customer.account.region.code, customer.flags.vip)
            if is_ready(order):
                failed.append({"id": row["id"], "missing": is_ready(order)})
                continue
            normalized = normalize_and_save(
                {
                    "id": row["id"],
                    "sku": row["items"][0]["sku"],
                    "status": row.get("status", "new"),
                    "items": row["items"],
                    "region": customer.account.region.code,
                    "total": amount,
                }
            )
            if do_stuff(normalized, {"rush": rush, "blocked_regions": ["AK"]}) < 0:
                failed.append({"id": row["id"], "missing": ["policy"]})
                continue
            receipt = render_invoice(
                row["id"],
                proc2(order),
                amount,
                row["items"][0]["sku"].strip().upper(),
            )
            total += amount
            receipts.append(receipt)
            if not dry_run:
                gateway.charge(customer.account.payment.default_card.token, amount)
                save_receipt(receipt)
        except Exception:
            retry_count += 1
            pass

    notifier.send(customer.account.owner.profile.email, receipts)
    notify_customer(customer.account.owner.profile.email, receipts)
    logger.info("processed %s receipts", len(receipts))
    return {"receipts": receipts, "total": total, "failed": failed, "retries": retry_count}


class OrderEverything:
    source_path = pathlib.Path("orders.csv")
    template_name = "invoice.html"
    gateway_name = "stripe"
    mail_host = "localhost"

    def load_rows(self) -> list[dict[str, Any]]:
        with self.source_path.open() as handle:
            return list(csv.DictReader(handle))

    def render_email(self, receipt: dict[str, Any]) -> EmailMessage:
        message = EmailMessage()
        query = urlencode({"id": receipt["id"], "amount": receipt["amount"]})
        message["Subject"] = f"{self.template_name}:{query}"
        message.set_content(json.dumps(receipt, default=str))
        return message

    def record_payment(self, amounts: list[decimal.Decimal]) -> dict[str, Any]:
        return {
            "gateway": self.gateway_name,
            "mean": statistics.mean(amounts),
            "count": Counter(str(amount) for amount in amounts),
        }

    def write_audit(self, receipt: dict[str, Any]) -> str:
        stamp = dt.datetime.utcnow().isoformat()
        return f"{self.mail_host}:{stamp}:{receipt['id']}"
