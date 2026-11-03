"""Natural Gemini speech. No silent fallback to robotic offline speech."""
import base64
import os
import logging
import time
import requests


def speak(text, destination, voice_name=None):
    from .engine import gemini_error
    model = os.getenv('TTS_MODEL', 'gemini-3.8-flash-lite-tts').strip().removeprefix('models/')
    key = os.environ['GEMINI_API_KEY'].strip()
    style = ('Natural animated-story dialogue; warm, expressive, conversational and engaging. '
             'Use varied intonation and short pauses, moderate pace. Read the transcript exactly. '
             + ('Speak Bengali with a natural Bangladeshi accent.' if os.getenv('LANGUAGE') == 'bn' else 'Speak clear English.'))
    payload = {
        'model': model,
        'input': [{'type': 'user_input', 'content': [{'type': 'text', 'text': text,
                   'annotations': [{'type': 'speech_metadata', 'style': style}]}]}],
        'response_format': {'type': 'audio'},
        'generation_config': {'speech_config': [{'voice': voice_name or os.getenv('TTS_VOICE', 'Kore').strip()}]},
    }
    # Bound each call and retry transient transport/server failures.
    # A timed-out generation may still finish remotely; retries can consume quota.
    for attempt in range(3):
        logging.info('Generating natural voice: attempt %s/3', attempt + 1)
        try:
            response = requests.post(
                'https://generativelanguage.googleapis.com/v1beta/interactions',
                headers={'x-goog-api-key': key}, json=payload, timeout=(15, 180))
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt == 2:
                raise RuntimeError(
                    'Natural voice request timed out or connection failed after 3 attempts. '
                    'Try a new workflow run later; no video was uploaded.') from None
            logging.warning('Voice connection interrupted (%s); retrying.', type(exc).__name__)
        else:
            if response.status_code not in (429, 500, 502, 503, 504) or attempt == 2:
                break
            logging.warning('Voice API returned HTTP %s; retrying.', response.status_code)
        time.sleep(5 * (2 ** attempt))
    if not response.ok:
        raise RuntimeError('Natural voice generation failed: ' + gemini_error(response, model))
    blocks = [block for step in response.json().get('steps', []) if step.get('type') == 'model_output'
              for block in step.get('content', []) if block.get('type') == 'audio' and block.get('data')]
    if not blocks:
        raise RuntimeError('TTS returned no audio. Check TTS model access/quota; no video was uploaded.')
    audio = base64.b64decode(blocks[-1]['data'], validate=True)
    if not (audio.startswith(b'RIFF') and audio[8:12] == b'WAVE'):
        raise RuntimeError('TTS did not return expected WAV audio; stopped before upload.')
    destination.write_bytes(audio)
