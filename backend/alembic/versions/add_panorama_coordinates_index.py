"""add panorama coordinates index

Revision ID: add_panorama_coordinates_index
Revises: previous_revision
Create Date: 2024-03-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_panorama_coordinates_index'
down_revision = 'previous_revision'  # Замените на предыдущую ревизию
branch_labels = None
depends_on = None

def upgrade():
    # Создаем составной индекс для координат
    op.create_index(
        'idx_panorama_coordinates',
        'panoramas',
        ['latitude', 'longitude']
    )

def downgrade():
    # Удаляем индекс при откате
    op.drop_index('idx_panorama_coordinates') 