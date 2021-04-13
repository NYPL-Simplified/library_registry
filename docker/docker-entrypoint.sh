#!/bin/sh
set -e

PG_READY=""
PG_READY_WAIT_SECONDS=5
COUNT=0

cd /libreg_app

until [ -n "$PG_READY" ] || [ $COUNT -gt 5 ]; do
    COUNT=$((COUNT+1))

    pipenv run python > /dev/null 2>&1 <<EOF
import os,sys,psycopg2
try:
  psycopg2.connect(os.environ.get('SIMPLIFIED_PRODUCTION_DATABASE'))
except Exception:
  sys.exit(1)
sys.exit(0)
EOF

    if [ $? -eq 0 ]; then
        PG_READY="true"
    else
        echo "--- Postgres unavailable, sleeping $PG_READY_WAIT_SECONDS seconds"
        sleep $PG_READY_WAIT_SECONDS
    fi
done

# Start up Supervisor, with Nginx and uWSGI
exec /usr/local/bin/supervisord -c /etc/supervisord.conf