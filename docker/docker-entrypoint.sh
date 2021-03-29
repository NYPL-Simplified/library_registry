#! /usr/bin/env sh
set -e

# Start up Supervisor, with Nginx and uWSGI
exec /usr/local/bin/supervisord