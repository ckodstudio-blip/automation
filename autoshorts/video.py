"""Frame-rendered moving graphics with natural speech and approximate captions."""
import math
import os
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont


def font(size):
    candidates = ['/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf',
                  '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def wrap(draw, text, f, width):
    lines, current = [], ''
    for word in text.split():
        candidate = (current + ' ' + word).strip()
        if draw.textbbox((0, 0), candidate, font=f)[2] > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def audio_energy(path):
    """RMS by video frame; mouth closes during silence. Input is normalized PCM16."""
    import array
    import sys
    import wave
    with wave.open(str(path), 'rb') as wav:
        rate = wav.getframerate()
        values = array.array('h', wav.readframes(wav.getnframes()))
        if sys.byteorder != 'little':
            values.byteswap()
    size = rate // 25
    levels = [math.sqrt(sum(v*v for v in values[n:n+size]) / max(1,len(values[n:n+size])))
              for n in range(0,len(values),size)]
    peak = max(levels, default=0)
    return [min(1, v / max(peak*.65, 150)) if v>100 else 0 for v in levels]


def render_video(plan, folder):
    from .engine import run, duration, stamp
    language = os.getenv('LANGUAGE', 'en')
    from .voice import speak
    parts, elapsed = [], 0
    for i, scene in enumerate(plan['scenes']):
        text, audio, image, caption, out = [folder / f'scene-{i}.{suffix}' for suffix in ('txt','wav','png','srt','mp4')]
        text.write_text(scene['narration'], encoding='utf-8')
        voice_name = os.getenv('TTS_SECOND_VOICE', 'Puck') if scene['speaker'] == 'rafi' else os.getenv('TTS_VOICE', 'Kore')
        speak(scene['narration'], audio, voice_name=voice_name)
        normalized = folder / f'voice-{i}.wav'
        run(['ffmpeg','-y','-v','error','-i',str(audio),'-ac','1','-ar','24000','-c:a','pcm_s16le',str(normalized)])
        audio = normalized
        levels = audio_energy(audio)
        seconds = duration(audio) + 0.4
        elapsed += seconds
        if elapsed > 70:
            raise RuntimeError('Narration exceeds 70-second limit. Job stopped before upload.')
        words = scene['narration'].split()
        chunks = [' '.join(words[j:j+5]) for j in range(0,len(words),5)]
        if not chunks:
            raise ValueError('Empty narration')
        caption.write_text('\n\n'.join(f'{j+1}\n{stamp(j*seconds/len(chunks))} --> {stamp((j+1)*seconds/len(chunks))}\n{t}' for j,t in enumerate(chunks)), encoding='utf-8')
        # Names/paths come from application-owned temporary directories, not user input.
        caption_path = str(caption.resolve()).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
        family = 'Noto Sans Bengali' if language == 'bn' else 'Noto Sans'
        vf = f"subtitles='{caption_path}':force_style='FontName={family},FontSize=11,Outline=1,Alignment=2,MarginV=32'"
        command = ['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','720x1280',
                   '-r','25','-i','pipe:0','-i',str(audio),'-t',str(seconds),'-vf',vf,
                   '-af','apad','-map','0:v:0','-map','1:a:0','-c:v','libx264',
                   '-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-threads','2',
                   '-c:a','aac','-ar','44100','-ac','2',str(out)]
        with (folder / f'encoder-{i}.log').open('wb') as log:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
            try:
                from .cartoon import frame as cartoon_frame
                for frame in range(math.ceil(seconds * 25)):
                    level = levels[frame] if frame < len(levels) else 0
                    process.stdin.write(cartoon_frame(scene, i, frame / 25, seconds, level).tobytes())
                process.stdin.close()
                if process.wait(timeout=120) != 0:
                    raise RuntimeError('Cartoon encoder failed; check encoder logs.')
            except BaseException:
                process.kill()
                process.wait()
                raise
        parts.append(out)
    concat = folder / 'concat.txt'
    concat.write_text('\n'.join(f"file '{p.resolve()}'" for p in parts))
    video = folder / 'short.mp4'
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(video)])
    if not 1 < duration(video) <= 71:
        raise RuntimeError('Rendered video failed duration validation')
    return video
