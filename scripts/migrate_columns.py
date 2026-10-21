from sqlalchemy import text
from app.core.database import engine

def migrate():
    cols = [
        ('users', 'phone', 'VARCHAR(50) NULL'),
        ('users', 'email_signature', 'TEXT NULL'),
        ('users', 'avatar_url', 'VARCHAR(255) NULL'),
        ('users', 'monthly_quota', 'FLOAT DEFAULT 0.0'),
        ('users', 'status', 'VARCHAR(50) DEFAULT \'ACTIVE\''),
        ('users', 'team_id', 'INT NULL'),
    ]
    with engine.connect() as conn:
        for t, col, col_def in cols:
            try:
                conn.execute(text(f'ALTER TABLE {t} ADD COLUMN {col} {col_def}'))
                conn.commit()
            except Exception:
                pass
