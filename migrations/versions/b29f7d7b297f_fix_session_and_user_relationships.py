"""Fix session and user relationships

Revision ID: b29f7d7b297f
Revises: 45dc39fc1a68
Create Date: 2024-10-17 15:25:31.414094

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b29f7d7b297f'
down_revision = '45dc39fc1a68'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Create a new table with the desired column type
    op.create_table(
        'session_new',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('slots', sa.Integer(), nullable=False)
    )

    # Step 2: Copy data from the old 'session' table to the new 'session_new' table
    conn = op.get_bind()
    conn.execute("""
        INSERT INTO session_new (id, date, slots)
        SELECT id, date, slots
        FROM session
    """)

    # Step 3: Drop the old 'session' table
    op.drop_table('session')

    # Step 4: Rename 'session_new' to 'session'
    op.rename_table('session_new', 'session')


def downgrade():
    # This function is for rolling back changes if necessary
    op.create_table(
        'session_old',
        sa.Column('id', sa.Integer(), primary_key=True),
        # Change back to string type if needed
        sa.Column('date', sa.String(), nullable=False),
        sa.Column('slots', sa.Integer(), nullable=False)
    )

    conn = op.get_bind()
    conn.execute("""
        INSERT INTO session_old (id, date, slots)
        SELECT id, date, slots
        FROM session
    """)

    op.drop_table('session')
    op.rename_table('session_old', 'session')
