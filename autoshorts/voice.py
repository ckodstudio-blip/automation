"""Whole-story Gemini TTS. One request by default; never retry HTTP 429."""
import base64
import binascii
import io
import logging
import os
import time
import wave
import requests


def _style():
    language = 'Bengali with a natural Bangladeshi accent' if os.getenv('LANGUAGE', 'en') == 'bn' else 'clear English'
    return ('Warm, expressive, gentle animated-story dialogue. Moderate, consistent pace. '
            'Read the transcript exactly without reading speaker names. Speak ' + language +
            '. Leave a clear brief silence between speech turns; do not overlap speakers. No music or sound effects.')


def _request_audio(content, speech_config, destination):
    from .engine import gemini_error
    model = os.getenv('TTS_MODEL', 'gemini-3.8-flash-lite-tts').strip().removeprefix('models/')
    key = os.environ['GEMINI_API_KEY'].strip()
    try:
        attempts = int(os.getenv('TTS_MAX_ATTEMPTS', '1'))
    except ValueError:
        raise ValueError('TTS_MAX_ATTEMPTS must be 1, 2 or 3') from None
    if attempts not in (1, 2, 3):
        raise ValueError('TTS_MAX_ATTEMPTS must be 1, 2 or 3')
    payload = {
        'model': model,
        'input': [{'type': 'user_input', 'content': content}],
        'response_format': {'type': 'audio'},
        'generation_config': {'speech_config': speech_config},
    }
    for attempt in range(attempts):
        logging.info('Generating entire story voice: attempt %s/%s', attempt + 1, attempts)
        try:
            response = requests.post(
                'https://generativelanguage.googleapis.com/v1beta/interactions',
                headers={'x-goog-api-key': key}, json=payload, timeout=(15, 240))
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt == attempts - 1:
                raise RuntimeError(
                    'Whole-story voice request timed out or connection failed. '
                    'No video was uploaded. A timed-out generation may still consume provider quota.') from None
            logging.warning('Voice connection interrupted (%s); retrying.', type(exc).__name__)
        else:
            # A daily limit cannot be solved by retrying immediately. Also stop
            # short-term 429s to conserve this small free quota.
            if response.status_code == 429:
                raise RuntimeError('Voice quota/rate limit reached. No immediate retry made. ' +
                                   gemini_error(response, model))
            if response.ok:
                break
            if response.status_code not in (500, 502, 503, 504) or attempt == attempts - 1:
                raise RuntimeError('Natural voice generation failed: ' + gemini_error(response, model))
            logging.warning('Voice API returned HTTP %s; retrying.', response.status_code)
        time.sleep(5 * (2 ** attempt))
    try:
        result = response.json()
        blocks = [block for step in result.get('steps', []) if step.get('type') == 'model_output'
                  for block in step.get('content', []) if block.get('type') == 'audio' and block.get('data')]
        if not blocks:
            raise ValueError('missing audio')
        audio = base64.b64decode(blocks[-1]['data'], validate=True)
        with wave.open(io.BytesIO(audio), 'rb') as wav:
            if wav.getnframes() < 1 or wav.getcomptype() != 'NONE':
                raise ValueError('empty or compressed WAV')
    except (ValueError, TypeError, AttributeError, KeyError, binascii.Error, wave.Error, EOFError):
        raise RuntimeError('TTS returned no valid PCM WAV audio. Stopped before upload; no automatic regeneration.') from None
    destination.write_bytes(audio)


def speak_story(scenes, destination):
    """Send all turns in one multi-speaker request, using the same two voices."""
    if not scenes:
        raise ValueError('Empty story')
    content = []
    for index, scene in enumerate(scenes):
        speaker = scene.get('speaker')
        text = scene.get('narration', '').strip()
        if speaker not in ('mira', 'rafi') or not text or any(c in text for c in '<>'):
            raise ValueError('Invalid story speaker or dialogue; narration cannot contain audio tags')
        # The API recognizes pause tags. These tags never enter subtitles.
        if index < len(scenes) - 1:
            text += ' <short pause>'
        content.append({'type': 'text', 'text': text,
                        'annotations': [{'type': 'speech_metadata', 'speaker': speaker, 'style': _style()}]})
    config = {'speakers': [
        {'speaker': 'mira', 'voice': os.getenv('TTS_VOICE', 'Kore').strip()},
        {'speaker': 'rafi', 'voice': os.getenv('TTS_SECOND_VOICE', 'Puck').strip()},
    ]}
    _request_audio(content, config, destination)


def speak(text, destination, voice_name=None):
    """Compatibility for the older single-speaker renderer."""
    content = [{'type': 'text', 'text': text,
                'annotations': [{'type': 'speech_metadata', 'style': _style()}]}]
    config = [{'voice': voice_name or os.getenv('TTS_VOICE', 'Kore').strip()}]
    _request_audio(content, config, destination)
