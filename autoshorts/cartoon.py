"""Original procedural 2D characters; all motion drawn locally, no stock assets."""
import math
from functools import lru_cache
from PIL import Image, ImageDraw

W,H=720,1280

@lru_cache(maxsize=3)
def backdrop(kind):
    im=Image.new('RGB',(W,H)); d=ImageDraw.Draw(im)
    top,bottom={'park':((112,201,241),(222,249,237)),
                'space':((19,24,68),(55,44,98)),
                'lab':((164,218,234),(235,247,244))}[kind]
    for y in range(H):
        q=y/H
        d.line((0,y,W,y),fill=tuple(round(a*(1-q)+b*q) for a,b in zip(top,bottom)))
    if kind=='park':
        d.ellipse((535,130,640,235),fill='#fff0a5')
        d.ellipse((-230,640,560,1220),fill='#70c49d')
        d.ellipse((260,600,1100,1220),fill='#97d3a5')
        for x in (35,650):
            d.rounded_rectangle((x-13,540,x+13,870),radius=10,fill='#a27159')
            for ox,oy in ((-35,0),(35,0),(0,-55)):
                d.ellipse((x+ox-65,440+oy,x+ox+65,570+oy),fill='#3d9b78')
    elif kind=='space':
        for j in range(80):
            x,y=(j*127)%W,(j*193)%880
            d.ellipse((x,y,x+3,y+3),fill='#d8e7ff')
        d.ellipse((470,240,625,395),fill='#c4a1e5')
        d.ellipse((495,270,525,300),fill='#9d7ec7')
        d.arc((430,280,675,355),0,360,fill='#e9cef6',width=12)
    else:
        for x in (35,410):
            d.rounded_rectangle((x,200,x+275,530),radius=24,fill='#5498b1',outline='#f4fbff',width=8)
            d.line((x+137,210,x+137,520),fill='#c1e4ef',width=6)
            d.line((x+8,365,x+267,365),fill='#c1e4ef',width=6)
        d.rectangle((35,640,685,680),fill='#e1aa79')
        d.rectangle((60,680,80,830),fill='#778da0')
        d.rectangle((640,680,660,830),fill='#778da0')
        for x,c in ((90,'#9bddb0'),(570,'#bea2f1')):
            d.rounded_rectangle((x,560,x+55,635),radius=15,fill=c,outline='#496d88',width=4)
    d.rectangle((0,870,W,H),fill={'park':'#a9d2ae','space':'#747397','lab':'#b2ccd3'}[kind])
    d.line((0,875,W,875),fill='#e0f0dc',width=5)
    return im


def character(draw,x,y,t,color,active,action,energy,flip=False):
    # Feet are planted at y. Head/torso bob and arms/legs respond to the action.
    walking=active and action=='walk'
    phase=t*8
    bob=(abs(math.sin(phase))*7 if walking else math.sin(t*2.4)*3)
    if active and action=='celebrate': bob+=abs(math.sin(t*7))*20
    y-=bob
    skin='#ffd6b0'; ink='#28394d'; hair='#35435a'
    def limb(points,fill,width):
        draw.line(points,fill=ink,width=width+6,joint='curve')
        draw.line(points,fill=fill,width=width,joint='curve')
        for px,py in (points[0],points[-1]):
            r=width/2;draw.ellipse((px-r,py-r,px+r,py+r),fill=fill)
    stride=math.sin(phase)*25 if walking else 0
    for side in (-1,1):
        hip=(x+side*23,y-133)
        knee=(x+side*25+side*stride*.45,y-76)
        foot=(x+side*27-side*stride,y-13)
        limb([hip,knee,foot],'#3e526f',21)
        draw.rounded_rectangle((foot[0]-19,foot[1]-8,foot[0]+26,foot[1]+10),radius=9,fill=ink)
    draw.rounded_rectangle((x-48,y-252,x+48,y-127),radius=24,fill=color,outline=ink,width=5)
    draw.rounded_rectangle((x-28,y-245,x+28,y-223),radius=8,fill='#f5faf5')
    direction=-1 if flip else 1
    for side in (-1,1):
        shoulder=(x+side*44,y-232)
        elbow=(x+side*66,y-190)
        hand=(x+side*64,y-148)
        if active and (action=='celebrate' or (action=='wave' and side==direction)):
            elbow=(x+side*83,y-269)
            hand=(x+side*(93+math.sin(t*9)*15),y-322)
        elif active and action=='point' and side==direction:
            elbow=(x+side*82,y-235)
            hand=(x+side*115,y-258+math.sin(t*3)*5)
        elif walking:
            hand=(x+side*66+side*stride,y-165)
        limb([shoulder,elbow,hand],skin,16)
        draw.ellipse((hand[0]-11,hand[1]-11,hand[0]+11,hand[1]+11),fill=skin,outline=ink,width=2)
    # Rounded head, hair, ears and expressive eyes.
    cy=y-300
    for side in (-1,1):draw.ellipse((x+side*49-10,cy-5,x+side*49+10,cy+19),fill=skin,outline=ink,width=3)
    draw.rounded_rectangle((x-52,cy-54,x+52,cy+51),radius=40,fill=skin,outline=ink,width=4)
    draw.pieslice((x-54,cy-66,x+54,cy+30),180,355,fill=hair)
    draw.polygon([(x-48,cy-10),(x-35,cy-40),(x+28,cy-35),(x+49,cy-6),(x+40,cy-49),(x-39,cy-48)],fill=hair)
    blink=(t%3.7)<.12
    for side in (-1,1):
        ex=x+side*20
        if blink:draw.line((ex-8,cy+2,ex+8,cy+2),fill=ink,width=4)
        else:
            draw.ellipse((ex-9,cy-9,ex+9,cy+12),fill='white')
            draw.ellipse((ex-4+direction,cy-5,ex+4+direction,cy+8),fill=ink)
        draw.arc((ex-10,cy-23,ex+10,cy-7),185,350,fill=ink,width=3)
    draw.ellipse((x-39,cy+15,x-24,cy+23),fill='#efb3a2')
    draw.ellipse((x+24,cy+15,x+39,cy+23),fill='#efb3a2')
    if active and energy>.05:
        opening=3+int(min(energy,1)*15)
        draw.ellipse((x-13,cy+24-opening/2,x+13,cy+24+opening),fill='#623c4b')
        draw.arc((x-10,cy+25,x+10,cy+24+opening),0,180,fill='#ed9b9d',width=4)
    else:draw.arc((x-13,cy+12,x+13,cy+32),0,180,fill=ink,width=3)


def frame(scene,index,t,length,energy):
    kind=scene.get('background','park')
    im=backdrop(kind).copy(); d=ImageDraw.Draw(im)
    # Drift clouds / an orbiting satellite so scenery moves independently.
    if kind=='park':
        for j in range(3):
            x=(j*270+t*13)%1000-160; y=270+j%2*90
            for ox,oy,r in ((0,0,30),(40,-12,40),(85,0,32)):
                d.ellipse((x+ox-r,y+oy-r,x+ox+r,y+oy+r),fill='#f6fcff')
    elif kind=='space':
        x=360+math.cos(t*.6)*180;y=360+math.sin(t*.6)*100
        d.rounded_rectangle((x-20,y-12,x+20,y+12),radius=5,fill='#d9e7f5')
        d.rectangle((x-65,y-18,x-26,y+18),fill='#69b7d4');d.rectangle((x+26,y-18,x+65,y+18),fill='#69b7d4')
    else:
        for j in range(5):
            y=580-(t*24+j*31)%150;x=115+math.sin(t+j)*12
            d.ellipse((x-5,y-5,x+5,y+5),outline='#439ca9',width=2)
    speaker=scene.get('speaker','mira'); action=scene.get('action','talk')
    for name,x,c,flip in [('mira',220,'#f6a66e',False),('rafi',500,'#79b9d6',True)]:
        active=name==speaker
        if active and action=='walk': x+=math.sin(t*.9)*48
        d.ellipse((x-65,865,x+65,883),fill={'park':'#87b595','space':'#626383','lab':'#93b4c0'}[kind])
        character(d,x,870,t,c,active,action,energy,flip)
    # Caption panel is intentionally empty; FFmpeg shapes Unicode subtitles over it.
    d.rounded_rectangle((40,965,680,1160),radius=28,fill='#22364c')
    d.rounded_rectangle((45,1200,675,1208),radius=4,fill='#d2e3df')
    d.rectangle((45,1200,45+max(1,int(630*t/max(length,.1))),1208),fill='#f7bd72')
    # A short fade in makes scene cuts less abrupt.
    if t<.2:
        im=Image.blend(Image.new('RGB',im.size,'#18263b'),im,max(0,t/.2))
    return im
