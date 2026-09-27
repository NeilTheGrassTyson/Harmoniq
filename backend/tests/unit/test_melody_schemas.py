"""
The Melody response schemas are the privacy boundary between the two views
of the same row. These pin the one field that must never cross it.
"""

from app.schemas.melody import MelodyInboxItem, MelodySentItem


def test_recipient_view_carries_delivery_time() -> None:
    assert "received_at" in MelodyInboxItem.model_fields


def test_sender_view_has_no_read_receipt() -> None:
    # Delivery time on the sender's item would tell them when the recipient
    # opened their inbox — the recipient's activity, shown without their
    # choice (HARMONIQ.md §6). Senders get outcomes, not read receipts.
    assert "received_at" not in MelodySentItem.model_fields


def test_both_views_date_the_outcome() -> None:
    assert "responded_at" in MelodyInboxItem.model_fields
    assert "responded_at" in MelodySentItem.model_fields
