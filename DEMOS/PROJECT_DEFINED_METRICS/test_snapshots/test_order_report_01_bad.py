"""Bad test-shape fixture for project-defined test-smell metrics."""

from unittest.mock import Mock


def test_order_report_hard_codes_everything() -> None:
    gateway = Mock()
    notifier = Mock()

    report = {
        "id": "A-100",
        "status": "paid",
        "currency": "USD",
        "total": 42,
        "discount": 3,
        "tax": 4,
        "shipping": 7,
        "customer": "Ada",
        "email": "ada@example.com",
        "items": ["book", "pen"],
    }

    gateway.charge("tok_live", 42)
    notifier.send("ada@example.com", report)

    assert report["id"] == "A-100"
    assert report["status"] == "paid"
    assert report["currency"] == "USD"
    assert report["total"] == 42
    assert report["discount"] == 3
    assert report["tax"] == 4
    assert report["shipping"] == 7
    assert report["customer"] == "Ada"
    assert report["email"] == "ada@example.com"
    assert report["items"] == ["book", "pen"]
    gateway.charge.assert_called_once_with("tok_live", 42)
    notifier.send.assert_called_once_with("ada@example.com", report)
    assert report == {
        "id": "A-100",
        "status": "paid",
        "currency": "USD",
        "total": 42,
        "discount": 3,
        "tax": 4,
        "shipping": 7,
        "customer": "Ada",
        "email": "ada@example.com",
        "items": ["book", "pen"],
    }
