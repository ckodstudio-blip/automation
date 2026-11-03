import json
import os
from pathlib import Path
import secrets
import shutil
import sys
from datetime import datetime

from . import engine as e


def main():
    errors = e.config_errors()
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    e.initialize()
    if os.getenv('RESET_YOUTUBE_TOKEN', 'false').lower() == 'true':
        e.save_setting('youtube_token', '')
    # Same day's scheduled run has a unique slot even if manually rerun in Actions.
    event = os.getenv('GITHUB_EVENT_NAME', 'workflow_dispatch')
    slot = ('daily:' + datetime.now(e.TZ).date().isoformat() if event == 'schedule'
            else 'manual:' + os.getenv('GITHUB_RUN_ID', secrets.token_hex(8)))
    job = secrets.token_hex(12)
    with e.db() as c:
        existing = c.execute('SELECT id,state FROM jobs WHERE slot=?', (slot,)).fetchone()
        if existing:
            print('This workflow slot was already attempted. Check its saved history; no duplicate upload will be made.')
            return 0
        c.execute('INSERT INTO jobs(id,slot,state,created) VALUES(?,?,?,?)', (job,slot,'queued',datetime.now(e.TZ).isoformat()))
    e.lock.acquire()
    e.pipeline(job)
    with e.db() as c:
        result = dict(c.execute('SELECT id,state,title,video_id,error FROM jobs WHERE id=?',(job,)).fetchone())
    # Error details stay in Aiven: external exceptions can contain credentials.
    public = {k: result[k] for k in ('id','state','title','video_id')}
    print(json.dumps(public, ensure_ascii=False))
    summary = os.getenv('GITHUB_STEP_SUMMARY')
    if summary:
        with open(summary, 'a') as out:
            out.write(f"## AutoShorts result\n\nJob: `{job}`\n\nStatus: **{result['state']}**\n\n")
            if result['video_id']:
                out.write('Video: https://www.youtube.com/watch?v=' + result['video_id'] + '\n')
            if result['state'] != 'uploaded':
                out.write('Check Aiven autoshorts_jobs.error for details. For needs_check, inspect YouTube Studio before retrying.\n')
    # No video retention or workflow artifacts, including failures.
    shutil.rmtree(e.DATA/job, ignore_errors=True)
    return 0 if result['state'] == 'uploaded' else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        # Only print type to avoid exposing OAuth/database credentials in CI logs.
        print(f'Workflow stopped: {type(exc).__name__}. Check secret configuration and Aiven connectivity.', file=sys.stderr)
        sys.exit(1)
