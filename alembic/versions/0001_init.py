"""init

Revision ID: 0001_init
Revises:
Create Date: 2026-10-13 14:55:22.587548
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes  # noqa: F401  (used by column type refs)

from alembic import op

revision: str = '0001_init'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Independent tables (no FKs)
    op.create_table('audit_log',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('actor_label', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
    sa.Column('action', sqlmodel.sql.sqltypes.AutoString(length=60), nullable=False),
    sa.Column('target_kind', sqlmodel.sql.sqltypes.AutoString(length=30), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=True),
    sa.Column('extra_json', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_log_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_log_actor_id'), ['actor_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_log_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_log_target_id'), ['target_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_log_target_kind'), ['target_kind'], unique=False)

    op.create_table('category',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
    sa.Column('sensitive', sa.Boolean(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('category', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_category_is_active'), ['is_active'], unique=False)
        batch_op.create_index(batch_op.f('ix_category_name'), ['name'], unique=True)
        batch_op.create_index(batch_op.f('ix_category_sensitive'), ['sensitive'], unique=False)

    op.create_table('place',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('place', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_place_is_active'), ['is_active'], unique=False)
        batch_op.create_index(batch_op.f('ix_place_name'), ['name'], unique=True)

    op.create_table('login_attempt',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username_or_mobile', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
    sa.Column('success', sa.Boolean(), nullable=False),
    sa.Column('attempted_at', sa.DateTime(), nullable=False),
    sa.Column('ip', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('login_attempt', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_login_attempt_attempted_at'), ['attempted_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_login_attempt_username_or_mobile'), ['username_or_mobile'], unique=False)

    # 2. User table (self-referencing FK)
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('full_name', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
    sa.Column('department', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
    sa.Column('batch_or_session', sqlmodel.sql.sqltypes.AutoString(length=60), nullable=False),
    sa.Column('mobile', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False),
    sa.Column('password_hash', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('is_member_confirmed', sa.Boolean(), nullable=False),
    sa.Column('is_adult_confirmed', sa.Boolean(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', 'SUSPENDED', name='accountstatus'), nullable=False),
    sa.Column('is_moderator', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('approved_at', sa.DateTime(), nullable=True),
    sa.Column('approved_by_id', sa.Integer(), nullable=True),
    sa.Column('suspended_at', sa.DateTime(), nullable=True),
    sa.Column('telegram_chat_id', sa.Integer(), nullable=True),
    sa.Column('telegram_link_code', sqlmodel.sql.sqltypes.AutoString(length=20), nullable=True),
    sa.Column('display_name_snapshot', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=True),
    sa.ForeignKeyConstraint(['approved_by_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_batch_or_session'), ['batch_or_session'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_department'), ['department'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_full_name'), ['full_name'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_is_moderator'), ['is_moderator'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_mobile'), ['mobile'], unique=True)
        batch_op.create_index(batch_op.f('ix_user_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_telegram_chat_id'), ['telegram_chat_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_user_telegram_link_code'), ['telegram_link_code'], unique=False)

    # 3. User-dependent tables
    op.create_table('recovery_code',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('code_hash', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('recovery_code', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_recovery_code_user_id'), ['user_id'], unique=False)

    op.create_table('notification',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.Enum('NEW_CLAIM', 'CLAIM_APPROVED', 'CLAIM_REJECTED', 'POSSIBLE_MATCH', 'ITEM_RETURNED', 'TELEGRAM_LINKED', name='notificationkind'), nullable=False),
    sa.Column('payload_json', sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notification_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_is_read'), ['is_read'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_kind'), ['kind'], unique=False)
        batch_op.create_index(batch_op.f('ix_notification_user_id'), ['user_id'], unique=False)

    op.create_table('lost_report',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('place_id', sa.Integer(), nullable=False),
    sa.Column('date_lost', sa.Date(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=300), nullable=False),
    sa.Column('private_note', sqlmodel.sql.sqltypes.AutoString(length=300), nullable=False),
    sa.Column('is_open', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], ),
    sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['place_id'], ['place.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lost_report', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lost_report_category_id'), ['category_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lost_report_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_lost_report_date_lost'), ['date_lost'], unique=False)
        batch_op.create_index(batch_op.f('ix_lost_report_is_open'), ['is_open'], unique=False)
        batch_op.create_index(batch_op.f('ix_lost_report_owner_id'), ['owner_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_lost_report_place_id'), ['place_id'], unique=False)

    # 4. found_item table (approved_claim_id FK is added after claim table is created)
    op.create_table('found_item',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('finder_id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('place_id', sa.Integer(), nullable=False),
    sa.Column('date_found', sa.Date(), nullable=False),
    sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=300), nullable=False),
    sa.Column('handover_note', sqlmodel.sql.sqltypes.AutoString(length=150), nullable=False),
    sa.Column('custody', sa.Enum('FINDER', 'OFFICE', name='custody'), nullable=False),
    sa.Column('status', sa.Enum('OPEN', 'CLAIM_APPROVED', 'RETURNED', 'WITHDRAWN', 'UNCLAIMED', name='itemstatus'), nullable=False),
    sa.Column('hidden', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('returned_at', sa.DateTime(), nullable=True),
    sa.Column('unclaimed_at', sa.DateTime(), nullable=True),
    sa.Column('withdrawn_at', sa.DateTime(), nullable=True),
    sa.Column('approved_claim_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['category.id'], ),
    sa.ForeignKeyConstraint(['finder_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['place_id'], ['place.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('found_item', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_found_item_category_id'), ['category_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_found_item_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_found_item_custody'), ['custody'], unique=False)
        batch_op.create_index(batch_op.f('ix_found_item_date_found'), ['date_found'], unique=False)
        batch_op.create_index(batch_op.f('ix_found_item_finder_id'), ['finder_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_found_item_hidden'), ['hidden'], unique=False)
        batch_op.create_index(batch_op.f('ix_found_item_place_id'), ['place_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_found_item_status'), ['status'], unique=False)

    # 5. Tables referencing found_item
    op.create_table('photo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('mime_type', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
    sa.Column('width', sa.Integer(), nullable=False),
    sa.Column('height', sa.Integer(), nullable=False),
    sa.Column('data', sa.LargeBinary(), nullable=False),
    sa.Column('sha256', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['found_item.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('photo', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_photo_item_id'), ['item_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_photo_sha256'), ['sha256'], unique=False)

    op.create_table('verification_question',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('question', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
    sa.Column('answer', sqlmodel.sql.sqltypes.AutoString(length=120), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['found_item.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('verification_question', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_verification_question_item_id'), ['item_id'], unique=False)

    # 6. Claim table (references found_item and user)
    op.create_table('claim',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('claimant_id', sa.Integer(), nullable=False),
    sa.Column('note', sqlmodel.sql.sqltypes.AutoString(length=300), nullable=False),
    sa.Column('status', sa.Enum('OPEN', 'APPROVED', 'REJECTED', 'EXPIRED', 'CANCELLED', 'COMPLETED', name='claimstatus'), nullable=False),
    sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(length=300), nullable=False),
    sa.Column('decided_by_id', sa.Integer(), nullable=True),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.Column('approved_at', sa.DateTime(), nullable=True),
    sa.Column('claimant_confirmed_returned_at', sa.DateTime(), nullable=True),
    sa.Column('custodian_confirmed_returned_at', sa.DateTime(), nullable=True),
    sa.Column('cancelled_at', sa.DateTime(), nullable=True),
    sa.Column('expired_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['claimant_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['decided_by_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['item_id'], ['found_item.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('claim', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_claim_claimant_id'), ['claimant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_claim_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_claim_item_id'), ['item_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_claim_status'), ['status'], unique=False)

    # 7. Tables referencing claim & verification_question
    op.create_table('claim_answer',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('claim_id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('answer', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.ForeignKeyConstraint(['claim_id'], ['claim.id'], ),
    sa.ForeignKeyConstraint(['question_id'], ['verification_question.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('claim_answer', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_claim_answer_claim_id'), ['claim_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_claim_answer_question_id'), ['question_id'], unique=False)

    # 8. Circular FK: found_item.approved_claim_id -> claim.id
    with op.batch_alter_table('found_item', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_found_item_approved_claim_id_claim',
            'claim',
            ['approved_claim_id'],
            ['id'],
        )


def downgrade() -> None:
    # 1. Drop circular FK first
    with op.batch_alter_table('found_item', schema=None) as batch_op:
        batch_op.drop_constraint('fk_found_item_approved_claim_id_claim', type_='foreignkey')

    # 2. Drop tables in exact reverse dependency order
    with op.batch_alter_table('claim_answer', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_claim_answer_question_id'))
        batch_op.drop_index(batch_op.f('ix_claim_answer_claim_id'))
    op.drop_table('claim_answer')

    with op.batch_alter_table('claim', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_claim_status'))
        batch_op.drop_index(batch_op.f('ix_claim_item_id'))
        batch_op.drop_index(batch_op.f('ix_claim_created_at'))
        batch_op.drop_index(batch_op.f('ix_claim_claimant_id'))
    op.drop_table('claim')

    with op.batch_alter_table('verification_question', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_verification_question_item_id'))
    op.drop_table('verification_question')

    with op.batch_alter_table('photo', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_photo_sha256'))
        batch_op.drop_index(batch_op.f('ix_photo_item_id'))
    op.drop_table('photo')

    with op.batch_alter_table('found_item', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_found_item_status'))
        batch_op.drop_index(batch_op.f('ix_found_item_place_id'))
        batch_op.drop_index(batch_op.f('ix_found_item_hidden'))
        batch_op.drop_index(batch_op.f('ix_found_item_finder_id'))
        batch_op.drop_index(batch_op.f('ix_found_item_date_found'))
        batch_op.drop_index(batch_op.f('ix_found_item_custody'))
        batch_op.drop_index(batch_op.f('ix_found_item_created_at'))
        batch_op.drop_index(batch_op.f('ix_found_item_category_id'))
    op.drop_table('found_item')

    with op.batch_alter_table('lost_report', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lost_report_place_id'))
        batch_op.drop_index(batch_op.f('ix_lost_report_owner_id'))
        batch_op.drop_index(batch_op.f('ix_lost_report_is_open'))
        batch_op.drop_index(batch_op.f('ix_lost_report_date_lost'))
        batch_op.drop_index(batch_op.f('ix_lost_report_created_at'))
        batch_op.drop_index(batch_op.f('ix_lost_report_category_id'))
    op.drop_table('lost_report')

    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notification_user_id'))
        batch_op.drop_index(batch_op.f('ix_notification_kind'))
        batch_op.drop_index(batch_op.f('ix_notification_is_read'))
        batch_op.drop_index(batch_op.f('ix_notification_created_at'))
    op.drop_table('notification')

    with op.batch_alter_table('recovery_code', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_recovery_code_user_id'))
    op.drop_table('recovery_code')

    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_telegram_link_code'))
        batch_op.drop_index(batch_op.f('ix_user_telegram_chat_id'))
        batch_op.drop_index(batch_op.f('ix_user_status'))
        batch_op.drop_index(batch_op.f('ix_user_mobile'))
        batch_op.drop_index(batch_op.f('ix_user_is_moderator'))
        batch_op.drop_index(batch_op.f('ix_user_full_name'))
        batch_op.drop_index(batch_op.f('ix_user_department'))
        batch_op.drop_index(batch_op.f('ix_user_batch_or_session'))
    op.drop_table('user')

    with op.batch_alter_table('login_attempt', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_login_attempt_username_or_mobile'))
        batch_op.drop_index(batch_op.f('ix_login_attempt_attempted_at'))
    op.drop_table('login_attempt')

    with op.batch_alter_table('place', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_place_name'))
        batch_op.drop_index(batch_op.f('ix_place_is_active'))
    op.drop_table('place')

    with op.batch_alter_table('category', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_category_sensitive'))
        batch_op.drop_index(batch_op.f('ix_category_name'))
        batch_op.drop_index(batch_op.f('ix_category_is_active'))
    op.drop_table('category')

    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_log_target_kind'))
        batch_op.drop_index(batch_op.f('ix_audit_log_target_id'))
        batch_op.drop_index(batch_op.f('ix_audit_log_created_at'))
        batch_op.drop_index(batch_op.f('ix_audit_log_actor_id'))
        batch_op.drop_index(batch_op.f('ix_audit_log_action'))
    op.drop_table('audit_log')

    # Drop Postgres ENUM types if on PostgreSQL
    bind = op.get_bind()
    if bind and bind.dialect.name == "postgresql":
        for enum_name in ["notificationkind", "itemstatus", "custody", "claimstatus", "accountstatus"]:
            sa.Enum(name=enum_name).drop(bind, checkfirst=True)
