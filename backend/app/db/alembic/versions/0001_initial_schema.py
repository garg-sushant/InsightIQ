"""Initial schema: organizations, users, datasets, retail facts, analysis runs, AI insights, audit log.

Revision ID: 0001_initial
Revises:
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001_initial'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('organizations',
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('industry', sa.String(length=120), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_organizations_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_organizations_slug'), ['slug'], unique=True)

    op.create_table('users',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('hashed_password', sa.String(length=128), nullable=False),
    sa.Column('role', sa.Enum('owner', 'admin', 'analyst', 'viewer', name='user_role', native_enum=False), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email', name='uq_users_email')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=False)
        batch_op.create_index('ix_users_org_role', ['organization_id', 'role'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_organization_id'), ['organization_id'], unique=False)

    op.create_table('analysis_runs',
    sa.Column('status', sa.Enum('running', 'completed', 'failed', name='analysis_status', native_enum=False), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('comparison_start', sa.Date(), nullable=True),
    sa.Column('comparison_end', sa.Date(), nullable=True),
    sa.Column('filters', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('filter_fingerprint', sa.String(length=64), nullable=False),
    sa.Column('kpis', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('result', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('ai_payload', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('source_row_count', sa.Integer(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('created_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('analysis_runs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_analysis_runs_created_at'), ['created_at'], unique=False)
        batch_op.create_index('ix_analysis_runs_org_created', ['organization_id', 'created_at'], unique=False)
        batch_op.create_index('ix_analysis_runs_org_fingerprint', ['organization_id', 'filter_fingerprint'], unique=False)
        batch_op.create_index(batch_op.f('ix_analysis_runs_organization_id'), ['organization_id'], unique=False)

    op.create_table('audit_logs',
    sa.Column('action', sa.String(length=80), nullable=False),
    sa.Column('resource_type', sa.String(length=64), nullable=True),
    sa.Column('resource_id', sa.String(length=64), nullable=True),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('actor_email', sa.String(length=320), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=400), nullable=True),
    sa.Column('context', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_logs_created_at'), ['created_at'], unique=False)
        batch_op.create_index('ix_audit_logs_org_action', ['organization_id', 'action'], unique=False)
        batch_op.create_index('ix_audit_logs_org_created', ['organization_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_user_id'), ['user_id'], unique=False)

    op.create_table('datasets',
    sa.Column('entity_type', sa.Enum('orders', 'customers', 'products', 'returns', name='dataset_entity_type', native_enum=False), nullable=False),
    sa.Column('status', sa.Enum('pending', 'validating', 'ingested', 'partial', 'failed', name='dataset_status', native_enum=False), nullable=False),
    sa.Column('original_filename', sa.String(length=400), nullable=False),
    sa.Column('content_type', sa.String(length=160), nullable=True),
    sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('checksum_sha256', sa.String(length=64), nullable=True),
    sa.Column('rows_total', sa.Integer(), nullable=False),
    sa.Column('rows_accepted', sa.Integer(), nullable=False),
    sa.Column('rows_rejected', sa.Integer(), nullable=False),
    sa.Column('validation_report', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('uploaded_by_user_id', sa.Uuid(), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('datasets', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_datasets_checksum_sha256'), ['checksum_sha256'], unique=False)
        batch_op.create_index(batch_op.f('ix_datasets_created_at'), ['created_at'], unique=False)
        batch_op.create_index('ix_datasets_org_entity_created', ['organization_id', 'entity_type', 'created_at'], unique=False)
        batch_op.create_index('ix_datasets_org_status', ['organization_id', 'status'], unique=False)
        batch_op.create_index(batch_op.f('ix_datasets_organization_id'), ['organization_id'], unique=False)

    op.create_table('ai_insights',
    sa.Column('analysis_run_id', sa.Uuid(), nullable=False),
    sa.Column('insight_type', sa.Enum('executive_summary', 'root_cause', 'recommendations', 'risks', name='ai_insight_type', native_enum=False), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('structured', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True),
    sa.Column('provider', sa.String(length=64), nullable=False),
    sa.Column('model', sa.String(length=120), nullable=False),
    sa.Column('prompt_version', sa.String(length=32), nullable=False),
    sa.Column('is_fallback', sa.Boolean(), nullable=False),
    sa.Column('tokens_prompt', sa.Integer(), nullable=True),
    sa.Column('tokens_completion', sa.Integer(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['analysis_run_id'], ['analysis_runs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('analysis_run_id', 'insight_type', name='uq_ai_insights_run_type')
    )
    with op.batch_alter_table('ai_insights', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ai_insights_analysis_run_id'), ['analysis_run_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_insights_created_at'), ['created_at'], unique=False)
        batch_op.create_index('ix_ai_insights_org_created', ['organization_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_ai_insights_organization_id'), ['organization_id'], unique=False)

    op.create_table('customers',
    sa.Column('customer_ref', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('segment', sa.String(length=64), nullable=True),
    sa.Column('country', sa.String(length=80), nullable=True),
    sa.Column('region', sa.String(length=64), nullable=True),
    sa.Column('state', sa.String(length=80), nullable=True),
    sa.Column('city', sa.String(length=120), nullable=True),
    sa.Column('postal_code', sa.String(length=20), nullable=True),
    sa.Column('dataset_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'customer_ref', name='uq_customers_org_ref')
    )
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_customers_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_customers_dataset_id'), ['dataset_id'], unique=False)
        batch_op.create_index('ix_customers_org_region', ['organization_id', 'region'], unique=False)
        batch_op.create_index('ix_customers_org_segment', ['organization_id', 'segment'], unique=False)
        batch_op.create_index(batch_op.f('ix_customers_organization_id'), ['organization_id'], unique=False)

    op.create_table('products',
    sa.Column('product_ref', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=400), nullable=False),
    sa.Column('category', sa.String(length=120), nullable=True),
    sa.Column('sub_category', sa.String(length=120), nullable=True),
    sa.Column('unit_price', sa.Numeric(precision=16, scale=4), nullable=True),
    sa.Column('dataset_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'product_ref', name='uq_products_org_ref')
    )
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_products_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_products_dataset_id'), ['dataset_id'], unique=False)
        batch_op.create_index('ix_products_org_category', ['organization_id', 'category'], unique=False)
        batch_op.create_index('ix_products_org_subcategory', ['organization_id', 'sub_category'], unique=False)
        batch_op.create_index(batch_op.f('ix_products_organization_id'), ['organization_id'], unique=False)

    op.create_table('returns',
    sa.Column('order_ref', sa.String(length=64), nullable=False),
    sa.Column('returned', sa.Boolean(), nullable=False),
    sa.Column('return_date', sa.Date(), nullable=True),
    sa.Column('reason', sa.String(length=240), nullable=True),
    sa.Column('dataset_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'order_ref', name='uq_returns_org_order_ref')
    )
    with op.batch_alter_table('returns', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_returns_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_returns_dataset_id'), ['dataset_id'], unique=False)
        batch_op.create_index('ix_returns_org_return_date', ['organization_id', 'return_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_returns_organization_id'), ['organization_id'], unique=False)

    op.create_table('orders',
    sa.Column('line_ref', sa.String(length=96), nullable=False),
    sa.Column('order_ref', sa.String(length=64), nullable=False),
    sa.Column('order_date', sa.Date(), nullable=False),
    sa.Column('ship_date', sa.Date(), nullable=True),
    sa.Column('ship_mode', sa.String(length=64), nullable=True),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('product_id', sa.Uuid(), nullable=False),
    sa.Column('region', sa.String(length=64), nullable=True),
    sa.Column('country', sa.String(length=80), nullable=True),
    sa.Column('state', sa.String(length=80), nullable=True),
    sa.Column('city', sa.String(length=120), nullable=True),
    sa.Column('segment', sa.String(length=64), nullable=True),
    sa.Column('category', sa.String(length=120), nullable=True),
    sa.Column('sub_category', sa.String(length=120), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=16, scale=4), nullable=False),
    sa.Column('discount', sa.Numeric(precision=9, scale=6), nullable=False),
    sa.Column('sales', sa.Numeric(precision=16, scale=4), nullable=False),
    sa.Column('profit', sa.Numeric(precision=16, scale=4), nullable=False),
    sa.Column('dataset_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.CheckConstraint('discount >= 0 AND discount <= 1', name='ck_orders_discount_range'),
    sa.CheckConstraint('quantity >= 0', name='ck_orders_quantity_non_negative'),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organization_id', 'line_ref', name='uq_orders_org_line_ref')
    )
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_orders_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_dataset_id'), ['dataset_id'], unique=False)
        batch_op.create_index('ix_orders_org_category', ['organization_id', 'category'], unique=False)
        batch_op.create_index('ix_orders_org_customer', ['organization_id', 'customer_id'], unique=False)
        batch_op.create_index('ix_orders_org_order_date', ['organization_id', 'order_date'], unique=False)
        batch_op.create_index('ix_orders_org_order_ref', ['organization_id', 'order_ref'], unique=False)
        batch_op.create_index('ix_orders_org_product', ['organization_id', 'product_id'], unique=False)
        batch_op.create_index('ix_orders_org_region', ['organization_id', 'region'], unique=False)
        batch_op.create_index('ix_orders_org_segment', ['organization_id', 'segment'], unique=False)
        batch_op.create_index('ix_orders_org_subcategory', ['organization_id', 'sub_category'], unique=False)
        batch_op.create_index(batch_op.f('ix_orders_organization_id'), ['organization_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_orders_organization_id'))
        batch_op.drop_index('ix_orders_org_subcategory')
        batch_op.drop_index('ix_orders_org_segment')
        batch_op.drop_index('ix_orders_org_region')
        batch_op.drop_index('ix_orders_org_product')
        batch_op.drop_index('ix_orders_org_order_ref')
        batch_op.drop_index('ix_orders_org_order_date')
        batch_op.drop_index('ix_orders_org_customer')
        batch_op.drop_index('ix_orders_org_category')
        batch_op.drop_index(batch_op.f('ix_orders_dataset_id'))
        batch_op.drop_index(batch_op.f('ix_orders_created_at'))

    op.drop_table('orders')
    with op.batch_alter_table('returns', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_returns_organization_id'))
        batch_op.drop_index('ix_returns_org_return_date')
        batch_op.drop_index(batch_op.f('ix_returns_dataset_id'))
        batch_op.drop_index(batch_op.f('ix_returns_created_at'))

    op.drop_table('returns')
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_products_organization_id'))
        batch_op.drop_index('ix_products_org_subcategory')
        batch_op.drop_index('ix_products_org_category')
        batch_op.drop_index(batch_op.f('ix_products_dataset_id'))
        batch_op.drop_index(batch_op.f('ix_products_created_at'))

    op.drop_table('products')
    with op.batch_alter_table('customers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_customers_organization_id'))
        batch_op.drop_index('ix_customers_org_segment')
        batch_op.drop_index('ix_customers_org_region')
        batch_op.drop_index(batch_op.f('ix_customers_dataset_id'))
        batch_op.drop_index(batch_op.f('ix_customers_created_at'))

    op.drop_table('customers')
    with op.batch_alter_table('ai_insights', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ai_insights_organization_id'))
        batch_op.drop_index('ix_ai_insights_org_created')
        batch_op.drop_index(batch_op.f('ix_ai_insights_created_at'))
        batch_op.drop_index(batch_op.f('ix_ai_insights_analysis_run_id'))

    op.drop_table('ai_insights')
    with op.batch_alter_table('datasets', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_datasets_organization_id'))
        batch_op.drop_index('ix_datasets_org_status')
        batch_op.drop_index('ix_datasets_org_entity_created')
        batch_op.drop_index(batch_op.f('ix_datasets_created_at'))
        batch_op.drop_index(batch_op.f('ix_datasets_checksum_sha256'))

    op.drop_table('datasets')
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_logs_user_id'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_organization_id'))
        batch_op.drop_index('ix_audit_logs_org_created')
        batch_op.drop_index('ix_audit_logs_org_action')
        batch_op.drop_index(batch_op.f('ix_audit_logs_created_at'))

    op.drop_table('audit_logs')
    with op.batch_alter_table('analysis_runs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_analysis_runs_organization_id'))
        batch_op.drop_index('ix_analysis_runs_org_fingerprint')
        batch_op.drop_index('ix_analysis_runs_org_created')
        batch_op.drop_index(batch_op.f('ix_analysis_runs_created_at'))

    op.drop_table('analysis_runs')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_organization_id'))
        batch_op.drop_index('ix_users_org_role')
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.drop_index(batch_op.f('ix_users_created_at'))

    op.drop_table('users')
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_organizations_slug'))
        batch_op.drop_index(batch_op.f('ix_organizations_created_at'))

    op.drop_table('organizations')
