"""Original low-poly 3D cast and presets. Run with Blender --background --python."""
import argparse
import json
import math
from pathlib import Path
import sys
import time
import bpy
from mathutils import Vector


def material(name,color):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1)
    m.use_nodes=True
    m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*color,1)
    m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.7
    return m


def ball(name,location,scale,mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=8,location=location)
    ob=bpy.context.object;ob.name=name;ob.scale=scale;ob.data.materials.append(mat)
    for p in ob.data.polygons:p.use_smooth=True
    return ob


def cube(name,location,scale,mat,bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    ob=bpy.context.object;ob.name=name;ob.scale=scale;ob.data.materials.append(mat)
    if bevel:
        mod=ob.modifiers.new('Soft corners','BEVEL');mod.width=bevel;mod.segments=2
        ob.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return ob


def rod(name,start,end,radius,mat):
    bpy.ops.mesh.primitive_cylinder_add(vertices=10,radius=radius,depth=1)
    ob=bpy.context.object;ob.name=name;ob.data.materials.append(mat)
    place_rod(ob,start,end)
    return ob


def place_rod(ob,start,end):
    a,b=Vector(start),Vector(end);direction=b-a
    ob.location=(a+b)/2;ob.scale.z=direction.length
    ob.rotation_euler=direction.to_track_quat('Z','Y').to_euler()


def aim(ob,target):ob.rotation_euler=(Vector(target)-ob.location).to_track_quat('-Z','Y').to_euler()


def make_cast(name,x,shirt,mats):
    root=bpy.data.objects.new(name,None);bpy.context.collection.objects.link(root);root.location.x=x
    def parent(ob):ob.parent=root;return ob
    parent(ball(name+' shirt',(0,0,1.32),(.38,.25,.49),shirt))
    parent(ball(name+' neck',(0,0,1.89),(.12,.12,.17),mats['skin']))
    parent(ball(name+' head',(0,0,2.27),(.43,.35,.44),mats['skin']))
    parent(ball(name+' hair',(0,.015,2.59),(.44,.36,.21),mats['hair']))
    for j in range(4):
        parent(ball(name+' fringe',(-.27+j*.17,-.29,2.52),(.13,.08,.13),mats['hair']))
    eyes=[]
    for side in (-1,1):
        parent(ball(name+' ear',(side*.42,0,2.26),(.09,.09,.13),mats['skin']))
        eye=parent(ball(name+' eye',(side*.16,-.319,2.31),(.095,.045,.12),mats['white']));eyes.append(eye)
        pupil=parent(ball(name+' pupil',(side*.16,-.364,2.31),(.043,.022,.065),mats['ink']));eyes.append(pupil)
        parent(ball(name+' cheek',(side*.25,-.29,2.17),(.075,.028,.045),mats['cheek']))
    parent(ball(name+' nose',(0,-.36,2.23),(.055,.065,.065),mats['skin']))
    mouth=parent(ball(name+' mouth',(0,-.332,2.09),(.12,.035,.025),mats['mouth']))
    limbs={}
    for side in (-1,1):
        for kind in ('arm','leg'):
            mat=mats['skin'] if kind=='arm' else mats['pants']
            radius=.075 if kind=='arm' else .105
            limbs[kind,side]=[parent(rod(name+kind,(0,0,0),(0,0,1),radius,mat)),
                             parent(rod(name+kind,(0,0,0),(0,0,1),radius,mat)),
                             parent(ball(name+'joint',(0,0,0),(radius,)*3,mat)),
                             parent(ball(name+'hand' if kind=='arm' else name+'shoe',(0,0,0),
                                         (.10,.085,.11) if kind=='arm' else (.14,.23,.10),
                                         mat if kind=='arm' else mats['ink']))]
    return root,limbs,mouth,eyes


def pose(cast,t,active,action,energy,base_x):
    root,limbs,mouth,eyes=cast
    walking=active and action=='walk'
    stride=math.sin(t*7)*.22 if walking else 0
    bob=abs(math.sin(t*7))*.05 if walking else math.sin(t*2)*.015
    if active and action=='celebrate':bob+=abs(math.sin(t*6))*.16
    root.location=(base_x+(math.sin(t*.9)*.45 if walking else 0),0,bob)
    root.rotation_euler.z=math.sin(t*2)*.025
    blink=(t%3.9)<.12
    for ob in eyes:ob.scale.z=(.015 if blink else .12) if ' eye' in ob.name else (.009 if blink else .065)
    mouth.scale.z=.025+(min(energy,1)*.10 if active else 0)
    for side in (-1,1):
        shoulder=(side*.34,0,1.63);elbow=(side*.48,0,1.27);hand=(side*.48,-.06,.98)
        if active and (action=='celebrate' or (action=='wave' and side==1)):
            elbow=(side*.65,0,1.92);hand=(side*(.74+math.sin(t*8)*.12),-.04,2.32)
        elif active and action=='point' and side==1:
            elbow=(side*.65,-.05,1.69);hand=(side*.99,-.08,1.94)
        elif walking:elbow=(side*.48,stride*side*.5,1.3);hand=(side*.48,stride*side,1.02)
        a,b,joint,end=limbs['arm',side]
        place_rod(a,shoulder,elbow);place_rod(b,elbow,hand);joint.location=elbow;end.location=hand
        hip=(side*.18,0,.98);knee=(side*.18,side*stride*.5,.53);foot=(side*.18,side*stride,.13)
        a,b,joint,end=limbs['leg',side]
        place_rod(a,hip,knee);place_rod(b,knee,foot);joint.location=knee;end.location=foot


def build():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    mats={k:material(k,c) for k,c in {
        'skin':(.91,.59,.36),'hair':(.07,.09,.15),'ink':(.035,.05,.09),
        'white':(.96,.98,1),'cheek':(.92,.31,.27),'mouth':(.22,.035,.07),'pants':(.10,.19,.32),
        'orange':(.96,.39,.14),'blue':(.10,.58,.78),'grass':(.17,.49,.32),
        'trunk':(.28,.13,.07),'leaf':(.07,.36,.23),'cloud':(.92,.97,1),
        'floor':(.38,.56,.66),'violet':(.49,.29,.68),'gold':(.98,.7,.2)}.items()}
    cast=[make_cast('Mira',-1.05,mats['orange'],mats),make_cast('Rafi',1.05,mats['blue'],mats)]
    groups={}
    for kind in ('park','space','lab'):
        before=set(bpy.data.objects)
        if kind=='park':
            cube('Park ground',(0,0,-.12),(25,25,.2),mats['grass'])
            for x,y in ((-3,2),(3,2),(-4,5),(4,5)):
                rod('Trunk',(x,y,0),(x,y,2.7),.14,mats['trunk'])
                for z,r in ((2.2,.7),(2.9,.9),(3.5,.65)):
                    ball('Leaves',(x,y,z),(r,r,r),mats['leaf'])
            for x,y,z in ((-2,4,4.4),(2,6,4.8)):
                for dx in (-.5,0,.5):ball('Cloud',(x+dx,y,z),(.65,.3,.25),mats['cloud'])
        elif kind=='space':
            cube('Moon surface',(0,0,-.12),(25,25,.2),mats['violet'])
            ball('Planet',(0,6,4),(1.2,1.2,1.2),mats['blue'])
            for x,y in ((-3,3),(3,4),(-2,6)):
                ball('Moon rock',(x,y,.15),(.5,.4,.28),mats['floor'])
            for j in range(20):
                ball('Star',(-5+(j*1.71)%10,7+(j%3),1+(j*1.13)%6),(.04,)*3,mats['gold'])
        else:
            cube('Lab floor',(0,0,-.12),(25,25,.2),mats['floor'])
            cube('Lab back wall',(0,4,2),(10,.2,4),mats['cloud'])
            cube('Monitor',(0,3.75,2.3),(2,.12,1.2),mats['blue'],.05)
            cube('Table',(0,2.4,1.1),(4,1,.14),mats['orange'])
            for x in (-1.7,1.7):cube('Table leg',(x,2.4,.52),(.12,.6,1),mats['white'])
            for x,c in ((-1,mats['violet']),(1,mats['grass'])):
                ball('Experiment flask',(x,2.4,1.5),(.22,.22,.3),c)
                rod('Flask neck',(x,2.4,1.5),(x,2.4,1.95),.09,c)
        groups[kind]=list(set(bpy.data.objects)-before)
    bpy.ops.object.camera_add(location=(5,-12,6.2))
    camera=bpy.context.object;aim(camera,(0,0,1.9));camera.data.type='ORTHO';camera.data.ortho_scale=7.6
    bpy.context.scene.camera=camera
    bpy.ops.object.light_add(type='AREA',location=(-3,-4,7));bpy.context.object.data.energy=650;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=6
    bpy.context.scene.world.color=(.45,.45,.45)
    return cast,groups,camera


def render_still(scene):
    """Ubuntu Blender can ship Cycles without the optional OIDN library."""
    try:
        bpy.ops.render.render(write_still=True)
    except RuntimeError as exc:
        message=str(exc).lower()
        missing_oidn=('build without openimagedenoiser' in message or
                      'build without openimagedenoise' in message)
        if not missing_oidn or not scene.cycles.use_denoising:
            raise
        print('OpenImageDenoiser unavailable: rendering without denoising for this job.',flush=True)
        scene.cycles.use_denoising=False
        # A few more samples reduce noise when optional denoising is unavailable.
        scene.cycles.samples=max(scene.cycles.samples,16)
        for layer in scene.view_layers:
            if hasattr(layer, 'cycles') and hasattr(layer.cycles, 'use_denoising'):
                layer.cycles.use_denoising=False
        bpy.ops.render.render(write_still=True)


def render(config,frames_dir):
    cast,groups,camera=build();scene=bpy.context.scene
    scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.samples=config.get('samples',8)
    scene.cycles.use_denoising=config.get('denoise',True);scene.cycles.max_bounces=2;scene.cycles.diffuse_bounces=1
    scene.render.threads_mode='FIXED';scene.render.threads=2
    scene.render.use_persistent_data=True
    scene.render.resolution_x=config.get('width',360);scene.render.resolution_y=config.get('height',640)
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
    scene.render.film_transparent=False;scene.view_settings.view_transform='Standard'
    fps=config['fps'];count=config['frame_count'];boundaries=config['boundaries'];scenes=config['scenes'];levels=config['levels'];step=config['energy_step']
    if not 1<=count<=1800:raise ValueError('Invalid frame count')
    frames_dir.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    for frame in range(count):
        t=frame/fps
        index=next((i for i in range(len(scenes)) if t<boundaries[i+1]),len(scenes)-1)
        item=scenes[index];local=t-boundaries[index]
        kind=item['background']
        for key,objects in groups.items():
            for ob in objects:ob.hide_render=key!=kind
        scene.world.use_nodes=True
        background=scene.world.node_tree.nodes.get('Background')
        background.inputs['Color'].default_value=(.025,.035,.08,1) if kind=='space' else (.55,.78,1,1)
        background.inputs['Strength'].default_value=.7
        energy=levels[min(len(levels)-1,int(t/step))]
        for n,(name,x) in enumerate((('mira',-1.05),('rafi',1.05))):
            pose(cast[n],local,item['speaker']==name,item['action'],energy,x)
        # Small camera orbit gives a visible change in perspective.
        angle=math.sin(local*.25)*.08
        camera.location=(4.4+angle*8,-12,5.8+math.sin(local*.3)*.12);aim(camera,(0,0,1.75))
        scene.render.filepath=str(frames_dir/f'{frame:05d}.png')
        render_still(scene)
        if frame%24==0:print(f'3D progress {frame+1}/{count}; elapsed {time.monotonic()-started:.1f}s',flush=True)
    print(f'3D render complete: {count} frames in {time.monotonic()-started:.1f}s',flush=True)


if __name__=='__main__':
    argv=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    parser=argparse.ArgumentParser();parser.add_argument('--config',required=True);parser.add_argument('--frames',required=True)
    args=parser.parse_args(argv)
    render(json.loads(Path(args.config).read_text(encoding='utf-8')),Path(args.frames))
