#!/usr/bin/env python3

import os
import sys
import psycopg2


def check_connection():
    db_string = os.environ.get("SIMPLIFIED_PRODUCTION_DATABASE") or "NO VALUE FOUND!"
    print("DB String from env:", db_string)
    if db_string.startswith('postgres'):
        print("Trying to connect...")
        try:
            conn = psycopg2.connect(db_string)
            print("Got a connection successfully:", conn)
        except Exception as e:
            print("Something went wrong:", str(e))


if __name__ == '__main__':
    sys.exit(check_connection())
