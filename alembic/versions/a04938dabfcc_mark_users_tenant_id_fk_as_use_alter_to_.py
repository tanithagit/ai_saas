"""mark users.tenant_id FK as use_alter to break circular dependency

Revision ID: a04938dabfcc
Revises: 9d67617af305
Create Date: 2026-07-15 10:28:10.073941

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a04938dabfcc'
down_revision: Union[str, Sequence[str], None] = '9d67617af305'
branch_labels: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    """Upgrade schema."""
    pass

def downgrade() -> None:
    """Downgrade schema."""
    pass
