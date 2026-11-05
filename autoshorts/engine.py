import base64
import hashlib
import json
import logging
import os
import re
from pathlib import Path
import secrets
import subprocess
import threading
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from cryptography.fernet import Fernet
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from .storage import database, initialize, MYSQL

DATA = Path(os.getenv('DATA_DIR', '/tmp/autoshorts'))
DATA.mkdir(parents=True, exist_ok=True)
TZ = ZoneInfo('Asia/Dhaka')
SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
lock = threading.Lock()


def db():
    return database()

def setting(key, default=''):
    with db() as c:
        row = c.execute('SELECT value FROM settings WHERE `key`=?', (key,)).fetchone()
    return row['value'] if row else default

def save_setting(key, value):
    with db() as c:
        sql = ('INSERT INTO settings (`key`,value) VALUES(?,?) ON DUPLICATE KEY UPDATE value=VALUES(value)' if MYSQL else 'INSERT OR REPLACE INTO settings VALUES(?,?)')
        c.execute(sql, (key, value))

def update(job, **fields):
    allowed = {'state', 'title', 'video_id', 'error'}
    assert fields and set(fields) <= allowed
    with db() as c:
        c.execute('UPDATE jobs SET ' + ','.join(f'{k}=?' for k in fields) + ' WHERE id=?', (*fields.values(), job))

def cipher():
    secret = os.environ.get('SECRET_KEY', '')
    if len(secret) < 32:
        raise RuntimeError('SECRET_KEY must contain at least 32 characters; keep it stable across deploys')
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))

def token_write(creds):
    save_setting('youtube_token', cipher().encrypt(creds.to_json().encode()).decode())

def token_exists():
    return bool(setting('youtube_token'))

def metadata(p):
    """Normalize model output and constrain YouTube metadata before publishing."""
    title = p.get('title', '')
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > 90 or any(c in title for c in '<>'):
        raise ValueError('Invalid AI title')
    p['title'] = title.strip()
    tags, seen = [], set()
    raw = p.get('tags')
    if not isinstance(raw, list):
        raise ValueError('AI tags must be an array')
    for value in raw:
        if not isinstance(value, str):
            raise ValueError('Invalid tag')
        value = ' '.join(value.strip().lstrip('#').split())
        if not value or len(value) > 40 or any(c in value for c in '<>'):
            raise ValueError('Invalid tag')
        if value.casefold() not in seen:
            tags.append(value)
            seen.add(value.casefold())
    # Conservative budget includes comma separators and quoted multiword tags.
    if not 3 <= len(tags) <= 15 or sum(len(t) + 1 + (2 if ' ' in t else 0) for t in tags) > 450:
        raise ValueError('AI tag count or character budget exceeded')
    hashtags, seen = [], set()
    raw = p.get('hashtags')
    if not isinstance(raw, list):
        raise ValueError('AI hashtags must be an array')
    for value in raw:
        if not isinstance(value, str):
            raise ValueError('Invalid hashtag')
        value = value.strip().lstrip('#')
        if not 1 <= len(value) <= 40 or not all(c == '_' or unicodedata.category(c)[0] in 'LNM' for c in value):
            raise ValueError('Invalid hashtag')
        if value.casefold() not in seen:
            hashtags.append('#' + value)
            seen.add(value.casefold())
    if not 1 <= len(hashtags) <= 5:
        raise ValueError('AI must return 1–5 relevant hashtags')
    p['tags'], p['hashtags'] = tags, hashtags
    return p

def validate_plan(p):
    if not isinstance(p, dict) or not isinstance(p.get('scenes'), list) or not 3 <= len(p['scenes']) <= 5:
        raise ValueError('AI must return 3–5 scenes')
    for k, maximum in [('title', 90), ('description', 2000)]:
        if not isinstance(p.get(k), str) or not 1 <= len(p[k]) <= maximum:
            raise ValueError('Invalid AI ' + k)
    for s in p['scenes']:
        for k, maximum in [('narration', 360), ('search', 80), ('visual_prompt', 600)]:
            if not isinstance(s.get(k), str) or not 1 <= len(s[k]) <= maximum:
                raise ValueError('Invalid scene ' + k)
    for s in p['scenes']:
        for field, choices in [('speaker', ('mira', 'rafi')), ('action', ('talk', 'wave', 'point', 'walk', 'celebrate')), ('background', ('park', 'space', 'lab'))]:
            if s.get(field) not in choices:
                raise ValueError('Invalid cartoon scene ' + field)
    if sum(len(s['narration'].split()) for s in p['scenes']) > 160:
        raise ValueError('AI narration too long')
    return metadata(p)

def safe_error_message(message, limit=1500):
    """Remove configured secrets and common credential forms before saving/logging."""
    text = str(message)
    for name in ('GEMINI_API_KEY', 'GOOGLE_CLIENT_SECRET', 'MYSQL_PASSWORD',
                 'YOUTUBE_REFRESH_TOKEN', 'SECRET_KEY'):
        secret = os.getenv(name, '')
        if secret:
            text = text.replace(secret, '[redacted]')
            stripped = secret.strip()
            if stripped:
                text = text.replace(stripped, '[redacted]')
    text = re.sub(r'(?i)([?&](?:key|api_key|access_token|refresh_token)=)[^&\s]+', r'\1[redacted]', text)
    text = re.sub(r'(?i)(Bearer\s+)\S+', r'\1[redacted]', text)
    text = re.sub(r'AIza[A-Za-z0-9_-]+', '[redacted]', text)
    return ' '.join(text.split())[:limit]


def gemini_error(response, model):
    """Expose Google's actual error message, without keys, request bodies or headers."""
    status, message = '', 'Google returned a non-JSON error response.'
    try:
        payload = response.json()
        detail = payload.get('error', {}) if isinstance(payload, dict) else {}
        if isinstance(detail, dict):
            status = str(detail.get('status', ''))
            message = str(detail.get('message', 'Google did not return an error message.'))
    except (ValueError, TypeError):
        pass
    hint = {
        400: 'Check API key and request/model support.',
        401: 'Check API authentication.',
        403: 'Check API/project permissions and key restrictions.',
        404: 'Check the exact model ID and its availability for v1beta generateContent.',
        429: 'Quota/rate limit reached; check the project quota. No paid fallback was used.',
    }.get(response.status_code, 'Check Google API availability and the detailed message.')
    return safe_error_message(f'Gemini HTTP {response.status_code}; model={model}; status={status}; message={message}; {hint}')


def make_plan():
    with db() as c:
        recent = [r['title'] for r in c.execute('SELECT title FROM jobs WHERE title IS NOT NULL ORDER BY created DESC LIMIT 50')]
    language = 'Bengali' if os.getenv('LANGUAGE', 'en') == 'bn' else 'English'
    prompt = f'''Create one original approximately 60-second animated cartoon story for a YouTube Short in {language}.
Niche: {os.getenv('NICHE', 'Nature and space facts')}.
Avoid these previous titles/topics: {json.dumps(recent)}.
Create a simple fictional adventure with a beginning, a small problem and a satisfying resolution, inspired by the niche. Use two original cartoon friends named Mira and Rafi. Never use copyrighted franchise characters. Avoid medical/financial advice. Any educational facts must be accurate; clearly distinguish fantasy from fact.
Return ONLY a JSON object with title (max 90 characters), description (max 1500 characters), tags (8–12 relevant keyword strings), hashtags (3 relevant strings), scenes (exactly 5 items).
Write an accurate, engaging title using the main topic keyword naturally; do not claim guaranteed ranking or use misleading clickbait.
Description should summarize the actual video in two short paragraphs. Do not put hashtags in description: supply them separately.
Tags must match the video, each max 40 characters, combined max 350 characters. Hashtags must have no spaces or punctuation other than an optional leading #; include #Shorts and two topic-specific hashtags. Do not invent live trend or search-volume claims.
Each scene has narration (one character speech turn, no speaker label or stage direction, max 360 characters), search (short English scene label, max 80 characters), visual_prompt (English shot description, max 600 characters), speaker (mira or rafi), action (talk, wave, point, walk or celebrate), background (park, space or lab). Alternate speakers across scenes. Make dialogue conversational and tell one coherent story. Only use these supported backgrounds and actions; do not describe unsupported objects or actions as visible. No narrator, only dialogue. Include at least one walk scene and one wave, point or celebrate scene.
Total dialogue 110–140 words, aiming for 55–65 seconds at a natural conversational pace. Give each of the 5 scenes a complete speech turn of similar length. Use an engaging opening and a clear happy ending. Do not include timing directions in the spoken text. No markdown.
These are original fictional 2D cartoons with preset characters and motions, not footage of a real event. Metadata must accurately describe the fictional story.'''
    # Accept a pasted model resource name, but call the API with one models/ prefix.
    model = os.environ['GEMINI_MODEL'].strip()
    if model.startswith('models/'):
        model = model[len('models/'):]
    if not model or not re.fullmatch(r'[A-Za-z0-9._-]+', model):
        raise ValueError('GEMINI_MODEL must contain a plain model ID, e.g. gemini-2.5-flash')
    key = os.environ['GEMINI_API_KEY'].strip()
    if not key or any(ch.isspace() for ch in key):
        raise ValueError('GEMINI_API_KEY contains whitespace/newlines. Paste only the API key in GitHub Secrets.')
    try:
        r = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            headers={'x-goog-api-key': key},
            json={'contents': [{'parts': [{'text': prompt}]}],
                  'generationConfig': {'responseMimeType': 'application/json'}},
            timeout=120)
    except requests.Timeout:
        raise RuntimeError(f'Gemini request timed out; model={model}. No automatic retry was made.') from None
    except requests.RequestException:
        raise RuntimeError(f'Gemini network request failed; model={model}. Check service connectivity.') from None
    if not r.ok:
        raise RuntimeError(gemini_error(r, model))
    try:
        value = r.json()
    except ValueError:
        raise RuntimeError(f'Gemini HTTP {r.status_code}; model={model}; response was not valid JSON.') from None
    candidates = value.get('candidates', []) if isinstance(value, dict) else []
    if not candidates:
        reason = value.get('promptFeedback', {}).get('blockReason', 'No candidate returned') if isinstance(value, dict) else 'Invalid response shape'
        raise RuntimeError(safe_error_message(f'Gemini returned no content; model={model}; reason={reason}'))
    candidate = candidates[0]
    parts = candidate.get('content', {}).get('parts', [])
    content = ''.join(part.get('text', '') for part in parts if not part.get('thought'))
    if not content.strip():
        raise RuntimeError(safe_error_message(f"Gemini returned empty text; model={model}; finishReason={candidate.get('finishReason', 'unknown')}"))
    try:
        plan = json.loads(content)
    except (ValueError, TypeError):
        raise RuntimeError(safe_error_message(f"Gemini returned invalid script JSON; model={model}; finishReason={candidate.get('finishReason', 'unknown')}")) from None
    return validate_plan(plan)


def run(args, timeout=600):
    result = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Media processing failed: ' + result.stderr[-1200:])
    return result.stdout

def duration(path):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(path)], 30).strip())

def stamp(seconds):
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'

def pipeline(job):
    uploading = False
    upload_confirmed = False
    try:
        errors = config_errors()
        if errors:
            raise RuntimeError('; '.join(errors))
        # Validate authorization before spending time generating media.
        yt = youtube()
        update(job, state='generating')
        folder = DATA / job
        folder.mkdir(exist_ok=True)
        plan = make_plan()
        digest = hashlib.sha256(plan['title'].strip().casefold().encode()).hexdigest()
        if setting('title:' + digest):
            raise RuntimeError('Duplicate title detected; refusing repeated topic')
        update(job, title=plan['title'])
        save_setting('plan:' + job, json.dumps(plan, ensure_ascii=False, indent=2))
        video, credits = render(plan, folder)
        save_setting('credits:' + job, json.dumps(credits, indent=2))
        description = plan['description'] + '\n\n' + ' '.join(plan['hashtags']) + '\n\nOriginal 2D cartoon animation. AI-assisted fictional story and synthetic character voices.'
        update(job, state='uploading')
        uploading = True
        upload = yt.videos().insert(part='snippet,status', notifySubscribers=False,
            body={'snippet': {'title': plan['title'], 'description': description[:4900], 'categoryId': '27', 'tags': plan['tags'], 'defaultLanguage': os.getenv('LANGUAGE', 'en')},
                  'status': {'privacyStatus': os.getenv('UPLOAD_PRIVACY', 'private'),
                             'selfDeclaredMadeForKids': os.getenv('MADE_FOR_KIDS', 'false').lower() == 'true',
                             'containsSyntheticMedia': os.getenv('CONTAINS_SYNTHETIC_MEDIA', 'false').lower() == 'true'}},
            media_body=MediaFileUpload(str(video), mimetype='video/mp4', chunksize=1024*1024, resumable=True))
        response = None
        while response is None:
            _, response = upload.next_chunk(num_retries=0)
        upload_confirmed = True
        update(job, state='uploaded', video_id=response['id'])
        save_setting('title:' + digest, job)
        # A confirmed YouTube upload is the canonical video copy.
        video.unlink(missing_ok=True)
    except Exception as exc:
        # Print the sanitized reason in Actions as well as storing it in Aiven.
        msg = safe_error_message(exc)
        update(job, state='needs_check' if uploading else 'failed', error=msg)
        logging.warning('Job %s failed (%s): %s', job, type(exc).__name__, msg)
    finally:
        # Delete intermediate media even when a job fails; keep plan and final output.
        folder = DATA / job
        try:
            if folder.exists():
                if upload_confirmed:
                    (folder / 'short.mp4').unlink(missing_ok=True)
                for p in folder.iterdir():
                    if p.name not in ('short.mp4', 'plan.json', 'credits.json'):
                        p.unlink(missing_ok=True)
                if not any(folder.iterdir()):
                    folder.rmdir()
        finally:
            lock.release()


def config_errors():
    keys = ['SECRET_KEY', 'GEMINI_API_KEY', 'GEMINI_MODEL', 'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET']
    if MYSQL:
        keys += ['MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_SSL_CA']
    errors = [f'Missing {k}' for k in keys if not os.getenv(k)]
    if len(os.getenv('SECRET_KEY', '')) < 32:
        errors.append('SECRET_KEY must be at least 32 characters')
    if os.getenv('LANGUAGE', 'en') not in ('en', 'bn'):
        errors.append('LANGUAGE must be en or bn')
    if os.getenv('UPLOAD_PRIVACY', 'private') not in ('private', 'unlisted', 'public'):
        errors.append('Invalid UPLOAD_PRIVACY')
    return errors


def youtube():
    encrypted = setting('youtube_token')
    if encrypted:
        try:
            info = json.loads(cipher().decrypt(encrypted.encode()))
        except Exception:
            raise RuntimeError('Cannot decrypt saved token: restore SECRET_KEY or run with RESET_YOUTUBE_TOKEN=true') from None
        creds = Credentials.from_authorized_user_info(info, SCOPES)
    else:
        refresh = os.getenv('YOUTUBE_REFRESH_TOKEN', '')
        if not refresh:
            raise RuntimeError('Set YOUTUBE_REFRESH_TOKEN in GitHub Secrets for the first run')
        creds = Credentials(token=None, refresh_token=refresh, token_uri='https://oauth2.googleapis.com/token',
                            client_id=os.environ['GOOGLE_CLIENT_ID'], client_secret=os.environ['GOOGLE_CLIENT_SECRET'], scopes=SCOPES)
    if not creds.valid:
        creds.refresh(Request())
    token_write(creds)
    return build('youtube', 'v3', credentials=creds, cache_discovery=False)


# Imported after core utilities so the renderer can call the subprocess helpers.
def render(plan, folder):
    from .video import render_video
    return render_video(plan, folder), []
