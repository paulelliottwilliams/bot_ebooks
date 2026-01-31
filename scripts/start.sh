#!/bin/bash
set -e

echo "Starting bot_ebooks..."

# Debug: show which database we're connecting to
python -c "
from src.bot_ebooks.config import get_settings
settings = get_settings()
# Mask password in output
import re
masked = re.sub(r'://[^:]+:[^@]+@', '://***:***@', settings.database_url)
print(f'Database URL: {masked}')
"

# Run migrations - alembic upgrade head is idempotent
# It will create tables if they don't exist, or do nothing if they do
echo "Running database migrations..."
alembic upgrade head

echo "Migration complete. Starting uvicorn..."
exec uvicorn src.bot_ebooks.main:app --host 0.0.0.0 --port ${PORT:-8000}
