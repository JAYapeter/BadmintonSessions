from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '89d72c59bfd5'
down_revision = 'b745b439f97a'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the existing poll table
    op.drop_table('poll')

    # Recreate the poll table without the id column, as a pure association table
    op.create_table(
        'poll',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id'), primary_key=True),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('session.id'), primary_key=True)
    )


def downgrade():
    # Recreate the old poll table with the id column (in case of rollback)
    op.create_table(
        'poll',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user.id')),
        sa.Column('session_id', sa.Integer(), sa.ForeignKey('session.id'))
    )

    # Drop the new poll association table
    op.drop_table('poll')
