#!/bin/bash

echo "Starting bot_ebooks..."

# Check if tables already exist (from previous migration attempts)
# Use || true to prevent set -e from killing the script
python -c "
from src.bot_ebooks.config import get_settings
import psycopg2

settings = get_settings()
conn = psycopg2.connect(settings.database_url)
cur = conn.cursor()

# Check if agents table exists
cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='agents')\")
tables_exist = cur.fetchone()[0]

# Check if alembic_version has our migration
cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version')\")
alembic_exists = cur.fetchone()[0]

migration_tracked = False
if alembic_exists:
    cur.execute(\"SELECT COUNT(*) FROM alembic_version WHERE version_num='001'\")
    migration_tracked = cur.fetchone()[0] > 0

cur.close()
conn.close()

print(f'Tables exist: {tables_exist}')
print(f'Migration tracked: {migration_tracked}')

if tables_exist and not migration_tracked:
    print('NEED_STAMP')
    exit(1)
else:
    print('NEED_MIGRATE')
    exit(0)
" && NEED_STAMP=false || NEED_STAMP=true

if [ "$NEED_STAMP" = true ]; then
    echo "Stamping existing database with current migration..."
    alembic stamp head
else
    echo "Running migrations..."
    alembic upgrade head
fi

echo "Starting uvicorn..."
exec uvicorn src.bot_ebooks.main:app --host 0.0.0.0 --port ${PORT:-8000}
