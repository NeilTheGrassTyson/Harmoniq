"""add melodies table and users.melody_accept_scope

Melody: directed single-track recommendation, sender → recipient, with the
lifecycle state machine from ENGINEERING_BIBLE §3. No message column —
Founder decision 2026-07-07: a Melody is an embed, not a text message.

Revision ID: c5d6e7f8a9b0
Revises: d5e6f7a8b9c0
Create Date: 2026-07-07
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c5d6e7f8a9b0"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "melodies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sender_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status", sa.String(), nullable=False, server_default=sa.text("'sent'")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "sender_id != recipient_id", name="ck_melodies_no_self_send"
        ),
        sa.CheckConstraint(
            "status IN ('sent','received','accepted','opened','rejected')",
            name="ck_melodies_status",
        ),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["track_id"], ["tracks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_melodies_sender_id", "melodies", ["sender_id"])
    op.create_index(
        "uq_melodies_pending_dedup",
        "melodies",
        ["sender_id", "recipient_id", "track_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('sent','received')"),
    )
    op.create_index(
        "ix_melodies_recipient_inbox",
        "melodies",
        ["recipient_id", "created_at", "id"],
    )
    op.create_index(
        "ix_melodies_sender_sent",
        "melodies",
        ["sender_id", "created_at", "id"],
    )

    op.add_column(
        "users",
        sa.Column(
            "melody_accept_scope",
            sa.String(),
            nullable=False,
            server_default=sa.text("'everyone'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "melody_accept_scope")
    op.drop_index("ix_melodies_sender_sent", table_name="melodies")
    op.drop_index("ix_melodies_recipient_inbox", table_name="melodies")
    op.drop_index("uq_melodies_pending_dedup", table_name="melodies")
    op.drop_index("ix_melodies_sender_id", table_name="melodies")
    op.drop_table("melodies")
