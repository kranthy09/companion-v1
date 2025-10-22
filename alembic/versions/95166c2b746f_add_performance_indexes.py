"""add_performance_indexes

    Revision ID: 95166c2b746f
    Revises: 1ebfb7790212
    Create Date: 2025-10-21 13:18:35.776981

    """
from typing import Sequence, Union

from alembic import op
# revision identifiers, used by Alembic.
revision: str = '95166c2b746f'
down_revision: Union[str, None] = '1ebfb7790212'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    """Add performance indexes"""

    # Notes table - Composite indexes for common queries
    op.create_index(
        'idx_notes_user_created',
        'notes',
        ['user_id', 'created_at'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_notes_user_updated',
        'notes',
        ['user_id', 'updated_at'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_notes_content_type',
        'notes',
        ['user_id', 'content_type'],
        postgresql_using='btree'
    )

    # Full-text search indexes
    op.execute("""
        CREATE INDEX idx_notes_title_gin
        ON notes USING gin(to_tsvector('english', title))
    """)

    op.execute("""
        CREATE INDEX idx_notes_content_gin
        ON notes USING gin(to_tsvector('english', content))
    """)

    # Quiz tables
    op.create_index(
        'idx_quizzes_note_created',
        'quizzes',
        ['note_id', 'created_at'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_quiz_questions_quiz',
        'quiz_questions',
        ['quiz_id'],
        postgresql_using='btree'
    )

    # Task metadata - Composite for filtering
    op.create_index(
        'idx_tasks_user_type_status',
        'task_metadata',
        ['user_id', 'task_type', 'status'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_tasks_resource',
        'task_metadata',
        ['resource_type', 'resource_id'],
        postgresql_using='btree'
    )

    # Enhanced notes
    op.create_index(
        'idx_enhanced_note_version',
        'enhanced_notes',
        ['note_id', 'version_number'],
        postgresql_using='btree'
    )

    # Questions
    op.create_index(
        'idx_questions_note_created',
        'questions',
        ['note_id', 'created_at'],
        postgresql_using='btree'
    )


def downgrade():
    """Remove performance indexes"""

    op.drop_index('idx_notes_user_created', 'notes')
    op.drop_index('idx_notes_user_updated', 'notes')
    op.drop_index('idx_notes_content_type', 'notes')
    op.drop_index('idx_notes_title_gin', 'notes')
    op.drop_index('idx_notes_content_gin', 'notes')
    op.drop_index('idx_quizzes_note_created', 'quizzes')
    op.drop_index('idx_quiz_questions_quiz', 'quiz_questions')
    op.drop_index('idx_tasks_user_type_status', 'task_metadata')
    op.drop_index('idx_tasks_resource', 'task_metadata')
    op.drop_index('idx_enhanced_note_version', 'enhanced_notes')
    op.drop_index('idx_questions_note_created', 'questions')
