"""Initial schema with all tables

Revision ID: 001
Revises:
Create Date: 2024-01-11 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    # ===========================================
    # Users Table
    # ===========================================
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_ip", sa.String(45), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("password_reset_token", sa.String(255), nullable=True),
        sa.Column("password_reset_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_token", sa.String(255), nullable=True),
        sa.Column("settings", sa.Text(), nullable=True, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_role", "users", ["role"])

    # ===========================================
    # Processing Tasks Table (PST Files)
    # ===========================================
    op.create_table(
        "processing_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256_hash", sa.String(64), nullable=True),
        sa.Column("md5_hash", sa.String(32), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("current_phase", sa.String(100), nullable=True),
        sa.Column("progress_percent", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("emails_total", sa.Integer(), nullable=True),
        sa.Column("emails_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attachments_total", sa.Integer(), nullable=True),
        sa.Column("attachments_processed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("celery_task_id", sa.String(100), nullable=True),
        sa.Column("pst_display_name", sa.String(500), nullable=True),
        sa.Column("pst_created_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pst_modified_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_processing_tasks_user_id", "processing_tasks", ["user_id"])
    op.create_index("ix_processing_tasks_status", "processing_tasks", ["status"])
    op.create_index("ix_processing_tasks_sha256_hash", "processing_tasks", ["sha256_hash"])
    op.create_index("ix_processing_tasks_celery_task_id", "processing_tasks", ["celery_task_id"])
    op.create_index(
        "ix_processing_tasks_user_status", "processing_tasks", ["user_id", "status"]
    )
    op.create_index(
        "ix_processing_tasks_status_created", "processing_tasks", ["status", "created_at"]
    )

    # ===========================================
    # Emails Table
    # ===========================================
    op.create_table(
        "emails",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("pst_file_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("message_id", sa.String(500), nullable=True),
        sa.Column("internet_message_id", sa.String(500), nullable=True),
        sa.Column("thread_id", sa.String(500), nullable=True),
        sa.Column("in_reply_to", sa.String(500), nullable=True),
        sa.Column("references", sa.Text(), nullable=True),
        sa.Column("thread_index", sa.String(500), nullable=True),
        sa.Column("sender_email", sa.String(320), nullable=True),
        sa.Column("sender_name", sa.String(500), nullable=True),
        sa.Column("to_recipients", postgresql.ARRAY(sa.String(320)), nullable=True),
        sa.Column("cc_recipients", postgresql.ARRAY(sa.String(320)), nullable=True),
        sa.Column("bcc_recipients", postgresql.ARRAY(sa.String(320)), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("sent_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("importance", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("folder_path", sa.String(1000), nullable=True),
        sa.Column("headers", sa.Text(), nullable=True),
        sa.Column("sha256_hash", sa.String(64), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column("is_embedded", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("embedding_id", sa.String(100), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["pst_file_id"], ["processing_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_emails_pst_file_id", "emails", ["pst_file_id"])
    op.create_index("ix_emails_message_id", "emails", ["message_id"])
    op.create_index("ix_emails_internet_message_id", "emails", ["internet_message_id"])
    op.create_index("ix_emails_thread_id", "emails", ["thread_id"])
    op.create_index("ix_emails_sender_email", "emails", ["sender_email"])
    op.create_index("ix_emails_sent_date", "emails", ["sent_date"])
    op.create_index("ix_emails_received_date", "emails", ["received_date"])
    op.create_index("ix_emails_has_attachments", "emails", ["has_attachments"])
    op.create_index("ix_emails_folder_path", "emails", ["folder_path"])
    op.create_index("ix_emails_is_embedded", "emails", ["is_embedded"])
    op.create_index("ix_emails_pst_sent_date", "emails", ["pst_file_id", "sent_date"])
    op.create_index("ix_emails_sender_date", "emails", ["sender_email", "sent_date"])

    # GIN index for full-text search
    op.create_index(
        "ix_emails_search_vector",
        "emails",
        ["search_vector"],
        postgresql_using="gin",
    )

    # Partial index for unembedded emails
    op.execute(
        """
        CREATE INDEX ix_emails_not_embedded ON emails (id)
        WHERE is_embedded = false
        """
    )

    # ===========================================
    # Attachments Table
    # ===========================================
    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("email_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("md5_hash", sa.String(32), nullable=True),
        sa.Column("sha256_hash", sa.String(64), nullable=True),
        sa.Column("storage_path", sa.String(1000), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("text_extraction_error", sa.Text(), nullable=True),
        sa.Column("is_extracted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_embedded", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("embedding_id", sa.String(100), nullable=True),
        sa.Column("is_inline", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("content_id", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["email_id"], ["emails.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attachments_email_id", "attachments", ["email_id"])
    op.create_index("ix_attachments_md5_hash", "attachments", ["md5_hash"])
    op.create_index("ix_attachments_sha256_hash", "attachments", ["sha256_hash"])
    op.create_index("ix_attachments_content_type", "attachments", ["content_type"])

    # Partial index for unextracted attachments
    op.execute(
        """
        CREATE INDEX ix_attachments_not_extracted ON attachments (id)
        WHERE is_extracted = false
        """
    )

    # ===========================================
    # Evidence Table
    # ===========================================
    op.create_table(
        "evidences",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("processing_task_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("evidence_number", sa.String(100), nullable=False),
        sa.Column("case_number", sa.String(100), nullable=True),
        sa.Column("case_name", sa.String(500), nullable=True),
        sa.Column("custodian_name", sa.String(255), nullable=True),
        sa.Column("custodian_email", sa.String(320), nullable=True),
        sa.Column("source_description", sa.Text(), nullable=True),
        sa.Column("collection_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_by", sa.String(255), nullable=True),
        sa.Column("sha256_hash", sa.String(64), nullable=False),
        sa.Column("md5_hash", sa.String(32), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_status", sa.String(50), nullable=False, server_default="verified"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["processing_task_id"], ["processing_tasks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("processing_task_id"),
        sa.UniqueConstraint("evidence_number"),
    )
    op.create_index("ix_evidences_processing_task_id", "evidences", ["processing_task_id"])
    op.create_index("ix_evidences_evidence_number", "evidences", ["evidence_number"])
    op.create_index("ix_evidences_case_number", "evidences", ["case_number"])

    # ===========================================
    # Audit Logs Table
    # ===========================================
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("user_email", sa.String(320), nullable=True),
        sa.Column("user_ip", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(100), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_resource_id", "audit_logs", ["resource_id"])
    op.create_index(
        "ix_audit_logs_timestamp_action", "audit_logs", ["timestamp", "action"]
    )
    op.create_index(
        "ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"]
    )
    op.create_index(
        "ix_audit_logs_user_timestamp", "audit_logs", ["user_id", "timestamp"]
    )

    # ===========================================
    # Create function for updating search_vector
    # ===========================================
    op.execute(
        """
        CREATE OR REPLACE FUNCTION emails_search_vector_update() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector :=
                setweight(to_tsvector('english', coalesce(NEW.subject, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(NEW.sender_name, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.sender_email, '')), 'B') ||
                setweight(to_tsvector('english', coalesce(NEW.body_text, '')), 'C');
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )

    # Create trigger for automatic search_vector updates
    op.execute(
        """
        CREATE TRIGGER emails_search_vector_trigger
        BEFORE INSERT OR UPDATE OF subject, sender_name, sender_email, body_text
        ON emails
        FOR EACH ROW
        EXECUTE FUNCTION emails_search_vector_update();
        """
    )

    # ===========================================
    # Create function for updated_at
    # ===========================================
    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;
        """
    )

    # Create triggers for updated_at on all tables
    for table in ["users", "processing_tasks", "emails", "attachments", "evidences"]:
        op.execute(
            f"""
            CREATE TRIGGER {table}_updated_at_trigger
            BEFORE UPDATE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
            """
        )


def downgrade() -> None:
    # Drop triggers
    for table in ["users", "processing_tasks", "emails", "attachments", "evidences"]:
        op.execute(f"DROP TRIGGER IF EXISTS {table}_updated_at_trigger ON {table}")

    op.execute("DROP TRIGGER IF EXISTS emails_search_vector_trigger ON emails")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")
    op.execute("DROP FUNCTION IF EXISTS emails_search_vector_update()")

    # Drop tables in reverse order of creation (respecting foreign keys)
    op.drop_table("audit_logs")
    op.drop_table("evidences")
    op.drop_table("attachments")
    op.drop_table("emails")
    op.drop_table("processing_tasks")
    op.drop_table("users")

    # Drop extensions
    op.execute('DROP EXTENSION IF EXISTS "pg_trgm"')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
