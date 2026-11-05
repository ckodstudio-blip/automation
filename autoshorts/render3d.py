"""Launch Blender with validated, data-only scene configuration."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time


def render_frames(scenes,boundaries,levels,step,folder,*,fps=12,width=360,height=640,samples=8,seconds=None):
    blender=shutil.which(os.getenv('BLENDER_BIN','blender'))
    if not blender:raise RuntimeError('Blender missing. Use the supplied 3D GitHub workflow install step.')
    for scene in scenes:
        for field,allowed in [('speaker',('mira','rafi')),('background',('park','space','lab')),
                              ('action',('talk','wave','point','walk','celebrate'))]:
            if scene.get(field) not in allowed:raise ValueError('Invalid 3D scene '+field)
    duration=boundaries[-1] if seconds is None else min(seconds,boundaries[-1])
    count=math.ceil(duration*fps)
    folder.mkdir(parents=True,exist_ok=True)
    config=folder/'3d-config.json';frames=folder/'3d-frames'
    if frames.exists():shutil.rmtree(frames)
    config.write_text(json.dumps({'scenes':scenes,'boundaries':boundaries,'levels':levels,'energy_step':step,
                                 'fps':fps,'width':width,'height':height,'samples':samples,'frame_count':count}),encoding='utf-8')
    script=Path(__file__).with_name('blender_scene.py')
    command=[blender,'--background','--factory-startup','--threads','2','--python-exit-code','1',
             '--python',str(script),'--','--config',str(config),'--frames',str(frames)]
    log_path=folder/'blender.log'
    print(f'Blender rendering {count} frames at {width}x{height}; this can take many minutes.',flush=True)
    with log_path.open('wb') as log:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        started=time.monotonic()
        try:
            while process.poll() is None:
                if time.monotonic()-started>9000:
                    process.kill();process.wait()
                    raise RuntimeError('Blender exceeded 150-minute render limit. Try preview mode or lower quality.')
                time.sleep(10)
                done=len(list(frames.glob('*.png'))) if frames.exists() else 0
                print(f'3D frames {done}/{count}; elapsed {int(time.monotonic()-started)}s',flush=True)
        except BaseException:
            if process.poll() is None:process.kill();process.wait()
            raise
    if process.returncode or len(list(frames.glob('*.png')))!=count:
        # Blender receives no credentials in its config. Restrict the error to
        # output lines relevant to Python/render failures rather than all logs.
        lines=log_path.read_text(errors='replace').splitlines()
        detail=' | '.join(line[:200] for line in lines[-8:])
        raise RuntimeError('Blender 3D render failed: '+detail)
    return frames,count
