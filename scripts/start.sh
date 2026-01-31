#!/bin/bash
set -e

echo "Starting bot_ebooks..."

# Debug: show which database we're connecting to
python -c "
from src.bot_ebooks.config import get_settings
import psycopg2

settings = get_settings()
# Mask password in output
import re
masked = re.sub(r'://[^:]+:[^@]+@', '://***:***@', settings.database_url)
print(f'Database URL: {masked}')

# Check actual state and fix if needed
conn = psycopg2.connect(settings.database_url)
cur = conn.cursor()

# Check if agents table exists
cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='agents')\")
tables_exist = cur.fetchone()[0]

# Check if alembic thinks migration is done
cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='alembic_version')\")
alembic_exists = cur.fetchone()[0]

print(f'Tables exist: {tables_exist}')
print(f'Alembic version table exists: {alembic_exists}')

# If alembic_version exists but tables don't, we need to reset alembic
if alembic_exists and not tables_exist:
    print('Alembic thinks migrations ran but tables are missing - resetting alembic_version')
    cur.execute('DELETE FROM alembic_version')
    conn.commit()
    print('Cleared alembic_version table')

cur.close()
conn.close()
"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

echo "Migration complete. Starting uvicorn..."
exec uvicorn src.bot_ebooks.main:app --host 0.0.0.0 --port ${PORT:-8000}
