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


def motion_frame(base, index, seconds, length):
    image = base.copy()
    draw = ImageDraw.Draw(image)
    accent = [(100,231,211),(188,159,255),(106,205,255)][index % 3]
    # Mask old central decoration. Each frame moves planets and orbit paths.
    draw.rounded_rectangle((165,180,555,550), radius=45, fill=(10,20,40))
    cx, cy = 360, 365
    for j, radius in enumerate((70,115,157)):
        draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),outline=(44,69,96),width=2)
        angle = seconds * (0.55 + j * .23) * (-1 if j == 1 else 1) + index + j * 2
        x, y = cx + math.cos(angle)*radius, cy + math.sin(angle)*radius
        r = 10 + j*3
        draw.ellipse((x-r,y-r,x+r,y+r),fill=accent)
    pulse = 29 + 4*math.sin(seconds*2.5)
    draw.ellipse((cx-pulse,cy-pulse,cx+pulse,cy+pulse),fill=accent)
    # Moving particle field and a time-based sweep at the bottom.
    for j in range(22):
        x = (j*107 + seconds*(12+j%4*7)) % 700 + 10
        y = (j*89 - seconds*18) % 1200 + 30
        if 180 < y < 550 or y < 80:
            draw.ellipse((x,y,x+3,y+3),fill=accent)
    draw.rounded_rectangle((81,900,639,907),radius=3,fill=(44,63,86))
    end = 81 + max(1,int(558*min(seconds/length,1)))
    draw.rectangle((81,900,end,907),fill=accent)
    return image


def render_video(plan, folder):
    from .engine import run, duration, stamp
    language = os.getenv('LANGUAGE', 'en')
    from .voice import speak
    parts, elapsed = [], 0
    for i, scene in enumerate(plan['scenes']):
        text, audio, image, caption, out = [folder / f'scene-{i}.{suffix}' for suffix in ('txt','wav','png','srt','mp4')]
        text.write_text(scene['narration'], encoding='utf-8')
        speak(scene['narration'], audio)
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
        vf = f"subtitles='{caption_path}':force_style='FontName={family},FontSize=21,Outline=2,Alignment=2,MarginV=58'"
        command = ['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','720x1280',
                   '-r','25','-i','pipe:0','-i',str(audio),'-t',str(seconds),'-vf',vf,
                   '-af','apad','-map','0:v:0','-map','1:a:0','-c:v','libx264',
                   '-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-threads','2',
                   '-c:a','aac','-ar','44100','-ac','2',str(out)]
        with (folder / f'encoder-{i}.log').open('wb') as log:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
            try:
                base = Image.open(image).convert('RGB').resize((720,1280))
                for frame in range(math.ceil(seconds * 25)):
                    process.stdin.write(motion_frame(base, i, frame / 25, seconds).tobytes())
                process.stdin.close()
                if process.wait(timeout=120) != 0:
                    raise RuntimeError('Motion encoder failed; check encoder logs.')
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
