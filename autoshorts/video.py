"""Stock-free educational motion cards with offline speech and burned-in captions."""
import math
import os
from pathlib import Path
import shutil
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


def background(scene, index, total, destination):
    # Render at slightly larger resolution for smooth zoom/pan, using original shapes.
    w, h = 800, 1422
    img = Image.new('RGB', (w, h))
    draw = ImageDraw.Draw(img)
    palettes = [(21, 35, 74), (29, 26, 68), (9, 48, 58), (51, 28, 62), (18, 43, 56)]
    base = palettes[index % len(palettes)]
    for y in range(h):
        q = y / h
        draw.line((0, y, w, y), fill=tuple(int(v * (1 - q * .6)) for v in base))
    accent = [(100, 231, 211), (188, 159, 255), (106, 205, 255)][index % 3]
    for j in range(30):
        x, y = (j * 163 + index * 91) % w, (j * 211 + index * 53) % h
        draw.ellipse((x, y, x+3, y+3), fill=(70, 91, 120))
    draw.rounded_rectangle((58, 90, 742, 158), radius=22, fill=(32, 51, 77))
    draw.text((88, 109), f'CURIOUS MINDS  /  {index+1:02} OF {total:02}', font=font(24), fill=accent)
    cx, cy = 400, 405
    for radius in (80, 128, 177):
        draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), outline=accent, width=2)
    draw.ellipse((cx-58, cy-58, cx+58, cy+58), fill=accent)
    draw.text((cx-17, cy-28), str(index+1), font=font(44), fill=(14, 28, 48))
    label = scene['search'].strip().upper()
    f = font(42)
    lines = wrap(draw, label, f, 640)
    # Fit the full label instead of silently truncating it.
    while len(lines) > 4 and f.size > 20:
        f = font(f.size-2)
        lines = wrap(draw, label, f, 640)
    y = 655
    for line in lines:
        box = draw.textbbox((0, 0), line, font=f)
        draw.text(((w-(box[2]-box[0]))/2, y), line, font=f, fill='white')
        y += f.size + 16
    draw.rounded_rectangle((90, 1000, 710, 1008), radius=4, fill=(44, 63, 86))
    draw.rounded_rectangle((90, 1000, 90+int(620*(index+1)/total), 1008), radius=4, fill=accent)
    img.save(destination)


def render_video(plan, folder):
    from .engine import run, duration, stamp
    language = os.getenv('LANGUAGE', 'en')
    voice = shutil.which('espeak-ng')
    if not voice:
        raise RuntimeError('espeak-ng is missing. Run the workflow media dependency install step.')
    parts, elapsed = [], 0
    for i, scene in enumerate(plan['scenes']):
        text, audio, image, caption, out = [folder / f'scene-{i}.{suffix}' for suffix in ('txt','wav','png','srt','mp4')]
        text.write_text(scene['narration'], encoding='utf-8')
        run([voice, '-v', language, '-s', '150', '-f', str(text), '-w', str(audio)], 60)
        seconds = duration(audio) + 0.4
        elapsed += seconds
        if elapsed > 70:
            raise RuntimeError('Narration exceeds 70-second limit. Job stopped before upload.')
        background(scene, i, len(plan['scenes']), image)
        words = scene['narration'].split()
        chunks = [' '.join(words[j:j+5]) for j in range(0,len(words),5)]
        if not chunks:
            raise ValueError('Empty narration')
        caption.write_text('\n\n'.join(f'{j+1}\n{stamp(j*seconds/len(chunks))} --> {stamp((j+1)*seconds/len(chunks))}\n{t}' for j,t in enumerate(chunks)), encoding='utf-8')
        # Names/paths come from application-owned temporary directories, not user input.
        caption_path = str(caption.resolve()).replace('\\', '/').replace(':', '\\:').replace("'", "\\'")
        family = 'Noto Sans Bengali' if language == 'bn' else 'Noto Sans'
        vf = ("zoompan=z='min(zoom+0.00025,1.06)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s=720x1280:fps=25,"
              f"subtitles='{caption_path}':force_style='FontName={family},FontSize=21,Outline=2,Alignment=2,MarginV=58'")
        run(['ffmpeg','-y','-v','error','-loop','1','-framerate','25','-i',str(image),'-i',str(audio),
             '-t',str(seconds),'-vf',vf,'-af','apad','-map','0:v:0','-map','1:a:0','-c:v','libx264',
             '-preset','veryfast','-crf','24','-pix_fmt','yuv420p','-threads','2','-c:a','aac','-ar','44100','-ac','2',str(out)])
        parts.append(out)
    concat = folder / 'concat.txt'
    concat.write_text('\n'.join(f"file '{p.resolve()}'" for p in parts))
    video = folder / 'short.mp4'
    run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart',str(video)])
    if not 1 < duration(video) <= 71:
        raise RuntimeError('Rendered video failed duration validation')
    return video
