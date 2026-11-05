"""Silent 6-second 3D preview. Uses no database, Gemini or YouTube credentials."""
from pathlib import Path
import argparse
import sys
import subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from autoshorts.render3d import render_frames

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='/tmp/autoshorts/preview.mp4')
    args=parser.parse_args();output=Path(args.output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
    scenes=[{'speaker':'mira','action':'wave','background':'park'},
            {'speaker':'rafi','action':'walk','background':'space'},
            {'speaker':'mira','action':'celebrate','background':'lab'}]
    levels=[.6 if i%10<7 else 0 for i in range(300)]
    frames,count=render_frames(scenes,[0,2,4,6],levels,.02,output.parent,fps=12,width=360,height=640,samples=8)
    subprocess.run(['ffmpeg','-y','-v','error','-framerate','12','-i',str(frames/'%05d.png'),
                    '-vf','scale=720:1280:flags=lanczos','-c:v','libx264','-preset','veryfast',
                    '-crf','22','-pix_fmt','yuv420p','-movflags','+faststart',str(output)],check=True)
    print('Silent 3D preview created:',output)
