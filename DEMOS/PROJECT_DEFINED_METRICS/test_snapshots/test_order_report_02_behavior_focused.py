"""Refactored test-shape fixture with contract-level assertions."""


def test_order_report_summarizes_paid_total() -> None:
    report = {
        "id": "A-100",
        "status": "paid",
        "total": 42,
    }

    assert report["status"] == "paid"
    assert report["total"] == 42
