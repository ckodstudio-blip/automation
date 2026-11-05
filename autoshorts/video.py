"""One soundtrack, Blender low-poly 3D render, silence-assisted scene timing."""
import json
import math
import os



def prepare_one_minute_audio(raw_audio, audio, folder):
    """Fit narration near a minute without changing pitch or cutting speech."""
    from .engine import run, duration
    source_seconds = duration(raw_audio)
    if not 50 <= source_seconds <= 70:
        raise RuntimeError(
            f'Voice length was {source_seconds:.1f}s; expected 50–70s for a one-minute story. '
            'Stopped before upload rather than cutting dialogue or adding a long silent section.')
    # Aim just below 60 seconds to leave room for tempo-filter rounding/tail.
    tempo = source_seconds / 59.5
    paced = folder/'story-paced.wav'
    run(['ffmpeg','-y','-v','error','-i',str(raw_audio),'-af',f'atempo={tempo:.8f}',
         '-ac','1','-ar','24000','-c:a','pcm_s16le',str(paced)])
    paced_seconds = duration(paced)
    if not 58.5 <= paced_seconds <= 60:
        raise RuntimeError('Voice tempo adjustment exceeded the one-minute budget; stopped before upload.')
    run(['ffmpeg','-y','-v','error','-i',str(paced),'-af','apad=whole_dur=60,atrim=duration=60',
         '-ac','1','-ar','24000','-c:a','pcm_s16le',str(audio)])


def render_video(plan, folder):
    from .engine import run, duration, stamp
    from .voice import speak_story
    from .timing import analyze, scene_at
    from .render3d import render_frames
    scenes = plan['scenes']
    raw_audio, audio = folder/'story-original.wav', folder/'story.wav'
    # Deliberately outside the frame/scene loops: one generation for all dialogue.
    speak_story(scenes, raw_audio)
    prepare_one_minute_audio(raw_audio, audio, folder)
    boundaries, levels, step = analyze(audio, scenes)
    seconds = boundaries[-1]
    (folder/'scene-timing.json').write_text(json.dumps({
        'method': 'silence-assisted approximate scene timing',
        'boundaries_seconds': boundaries,
        'note': 'Full audio is preserved; scene/subtitle timing is not exact speech alignment.'
    }, indent=2),encoding='utf-8')
    captions, number = [], 0
    for index, scene in enumerate(scenes):
        start,end = boundaries[index:index+2]
        words = scene['narration'].split()
        chunks = [' '.join(words[j:j+5]) for j in range(0,len(words),5)]
        if not chunks:
            raise ValueError('Empty narration')
        for j,text in enumerate(chunks):
            number += 1
            a=start+(end-start)*j/len(chunks)
            b=start+(end-start)*(j+1)/len(chunks)
            captions.append(f'{number}\n{stamp(a)} --> {stamp(b)}\n{text}')
    caption = folder/'story.srt'
    caption.write_text('\n\n'.join(captions),encoding='utf-8')
    caption_path = str(caption.resolve()).replace('\\','/').replace(':','\\:').replace("'", "\\'")
    family = 'Noto Sans Bengali' if os.getenv('LANGUAGE','en') == 'bn' else 'Noto Sans'
    vf = f"subtitles='{caption_path}':force_style='FontName={family},FontSize=11,Outline=1,Alignment=2,MarginV=32'"
    video = folder/'short.mp4'
    frames, count = render_frames(scenes,boundaries,levels,step,folder)
    run(['ffmpeg','-y','-v','error','-framerate','12','-start_number','0',
         '-i',str(frames/'%05d.png'),'-i',str(audio),'-t','60',
         '-vf',f"scale=720:1280:flags=lanczos,{vf}",
         '-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','veryfast','-crf','22',
         '-pix_fmt','yuv420p','-threads','2','-c:a','aac','-ar','44100','-ac','2',
         '-movflags','+faststart',str(video)], timeout=600)
    if abs(duration(video) - 60) > .15:
        raise RuntimeError('Rendered cartoon failed duration validation')
    return video
