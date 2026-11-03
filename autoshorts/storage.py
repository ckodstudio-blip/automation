"""Persistent Aiven MySQL store; SQLite is an explicit test-only backend."""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import sqlite3
import ssl

import pymysql

MYSQL = os.getenv('DB_BACKEND', 'mysql') != 'sqlite'


class Connection:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=()):
        # Existing SQL uses portable table aliases and positional parameters.
        sql = re.sub(r'\bjobs\b', 'autoshorts_jobs', sql)
        sql = re.sub(r'\bsettings\b', 'autoshorts_settings', sql)
        if MYSQL:
            sql = sql.replace('?', '%s')
            cur = self.raw.cursor()
            cur.execute(sql, params)
            return cur
        return self.raw.execute(sql, params)


@contextmanager
def database():
    if MYSQL:
        ctx = ssl.create_default_context()
        ca = os.getenv('MYSQL_SSL_CA', '')
        if ca:
            ctx.load_verify_locations(cadata=ca.replace('\\n', '\n'))
        elif os.getenv('MYSQL_SSL_CA_PATH'):
            ctx.load_verify_locations(cafile=os.environ['MYSQL_SSL_CA_PATH'])
        else:
            raise RuntimeError('Set MYSQL_SSL_CA to the Aiven project CA certificate')
        raw = pymysql.connect(host=os.environ['MYSQL_HOST'], port=int(os.environ['MYSQL_PORT']),
            user=os.environ['MYSQL_USER'], password=os.environ['MYSQL_PASSWORD'],
            database=os.getenv('MYSQL_DATABASE', 'defaultdb'), charset='utf8mb4', ssl=ctx,
            connect_timeout=15, read_timeout=30, write_timeout=30,
            cursorclass=pymysql.cursors.DictCursor, autocommit=False)
    else:
        raw = sqlite3.connect(Path(os.environ['DATA_DIR']) / 'test.sqlite', timeout=30)
        raw.row_factory = sqlite3.Row
    try:
        yield Connection(raw)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def initialize():
    with database() as c:
        if MYSQL:
            c.execute('''CREATE TABLE IF NOT EXISTS jobs(
                id VARCHAR(24) PRIMARY KEY, slot VARCHAR(100) NOT NULL UNIQUE,
                state VARCHAR(30) NOT NULL, title TEXT, video_id VARCHAR(100),
                error TEXT, created VARCHAR(50) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')
            c.execute('''CREATE TABLE IF NOT EXISTS settings(
                `key` VARCHAR(191) PRIMARY KEY, value LONGTEXT NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4''')
        else:
            c.execute('CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, slot TEXT UNIQUE, state TEXT, title TEXT, video_id TEXT, error TEXT, created TEXT)')
            c.execute('CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT)')
        c.execute("UPDATE jobs SET state='needs_check',error='Server restarted during job. Check YouTube Studio before creating another video.' WHERE state IN ('queued','generating','uploading')")
