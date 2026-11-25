
"""add company identity resolution

Revision ID: b91e6f62600d
Revises: 1a8cb601b48f
Create Date: 2026-11-24 10:14:21.598425

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b91e6f62600d"
down_revision: Union[str, Sequence[str], None] = "1a8cb601b48f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create canonical companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cik", sa.String(length=10), nullable=True),
        sa.Column("canonical_name", sa.String(length=255), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cik", name="uq_companies_cik"),
        sa.UniqueConstraint(
            "normalized_name",
            name="uq_companies_normalized_name",
        ),
    )

    op.create_index(
        "ix_companies_id",
        "companies",
        ["id"],
        unique=False,
    )

    # Create company aliases table
    op.create_table(
        "company_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("normalized_alias", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "company_id",
            "normalized_alias",
            name="uq_company_alias_company_normalized",
        ),
    )

    op.create_index(
        "ix_company_aliases_company_id",
        "company_aliases",
        ["company_id"],
        unique=False,
    )
    op.create_index(
        "ix_company_aliases_id",
        "company_aliases",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_company_aliases_normalized_alias",
        "company_aliases",
        ["normalized_alias"],
        unique=False,
    )

    # Add canonical company reference to financial documents
    op.add_column(
        "financial_documents",
        sa.Column("company_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_financial_documents_company_id",
        "financial_documents",
        ["company_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_financial_documents_company_id_companies",
        "financial_documents",
        "companies",
        ["company_id"],
        ["id"],
    )

    # Add canonical company reference to financial metrics
    op.add_column(
        "financial_metrics",
        sa.Column("company_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_financial_metrics_company_id",
        "financial_metrics",
        ["company_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_financial_metrics_company_id_companies",
        "financial_metrics",
        "companies",
        ["company_id"],
        ["id"],
    )


def downgrade() -> None:
    # Remove financial metric company reference
    op.drop_constraint(
        "fk_financial_metrics_company_id_companies",
        "financial_metrics",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_financial_metrics_company_id",
        table_name="financial_metrics",
    )
    op.drop_column("financial_metrics", "company_id")

    # Remove financial document company reference
    op.drop_constraint(
        "fk_financial_documents_company_id_companies",
        "financial_documents",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_financial_documents_company_id",
        table_name="financial_documents",
    )
    op.drop_column("financial_documents", "company_id")

    # Remove company aliases
    op.drop_index(
        "ix_company_aliases_normalized_alias",
        table_name="company_aliases",
    )
    op.drop_index(
        "ix_company_aliases_id",
        table_name="company_aliases",
    )
    op.drop_index(
        "ix_company_aliases_company_id",
        table_name="company_aliases",
    )
    op.drop_table("company_aliases")

    # Remove companies
    op.drop_index(
        "ix_companies_id",
        table_name="companies",
    )
    op.drop_table("companies")
