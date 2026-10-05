"""Combine the revised user flow with machine and owner swimlanes.

Requires Pillow. Run render_user_flow.py first if its SVG/PNG are missing.
"""
from html import escape
from math import atan2, cos, sin, hypot
from pathlib import Path
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
W, H, SCALE = 4450, 2260, 2
INK = "#242424"
img = Image.new("RGB", (W*SCALE, H*SCALE), "white")
draw = ImageDraw.Draw(img)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
       '<title id="title">EcoRefill updated activity diagram</title>',
       '<desc id="desc">Three swimlanes: User / EcoRefill App, EcoRefill Machine, and Device Owner / EcoRefill App. The revised user flow requires scanning the machine QR before buying points or water. Points purchases require owner approval. Matching letter connectors indicate communication across lanes.</desc>',
       f'<rect width="{W}" height="{H}" fill="white"/>']
font_dir = next(p for p in [Path("/System/Library/Fonts/Supplemental"), Path("/usr/share/fonts/truetype/dejavu")] if p.exists())


def font(size, bold=False):
    name = ("Arial Bold.ttf" if bold else "Arial.ttf") if "Supplemental" in str(font_dir) else ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    return ImageFont.truetype(str(font_dir/name), size*SCALE)


def text(x, y, value, size=21, bold=False, label=False):
    f = font(size, bold)
    if label:
        b = draw.textbbox((x*SCALE,y*SCALE), value, font=f, anchor="mm")
        draw.rectangle((b[0]-8,b[1]-4,b[2]+8,b[3]+4),fill="white")
        w = (b[2]-b[0])/SCALE+8
        svg.append(f'<rect x="{x-w/2}" y="{y-size/2-3}" width="{w}" height="{size+6}" fill="white"/>')
    draw.text((x*SCALE,y*SCALE),value,font=f,fill=INK,anchor="mm")
    svg.append(f'<text x="{x}" y="{y}" fill="{INK}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="middle" dominant-baseline="central">{escape(value)}</text>')


def line(points, dashed=False):
    if dashed:
        for a,b in zip(points,points[1:]):
            length = hypot(b[0]-a[0],b[1]-a[1])
            for t in range(0,int(length),14):
                p = [(a[0]+(b[0]-a[0])*u/length,a[1]+(b[1]-a[1])*u/length) for u in (t,min(t+8,length))]
                draw.line([(x*SCALE,y*SCALE) for x,y in p],fill=INK,width=2*SCALE)
    else:
        draw.line([(x*SCALE,y*SCALE) for x,y in points],fill=INK,width=2*SCALE)
    svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{INK}" stroke-width="2"'+(' stroke-dasharray="8 6"' if dashed else '')+'/>')


def polygon(points, fill="white"):
    p = [(x*SCALE,y*SCALE) for x,y in points]
    draw.polygon(p,fill=fill)
    draw.line(p+[p[0]],fill=INK,width=2*SCALE)
    svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in points)}" fill="{fill}" stroke="{INK}" stroke-width="2"/>')


def arrow(points, dashed=False):
    line(points,dashed)
    a,b = points[-2:]
    angle = atan2(b[1]-a[1],b[0]-a[0])
    polygon([b,(b[0]-12*cos(angle)+5*sin(angle),b[1]-12*sin(angle)-5*cos(angle)),(b[0]-12*cos(angle)-5*sin(angle),b[1]-12*sin(angle)+5*cos(angle))],INK)


def box(x,y,value,width=240,height=60):
    polygon([(x-width/2,y-height/2),(x+width/2,y-height/2),(x+width/2,y+height/2),(x-width/2,y+height/2)])
    for i,s in enumerate(value.split("\n")):
        text(x,y+(i-(len(value.split("\n"))-1)/2)*25,s)


def decision(x,y,value,width=200,height=110):
    polygon([(x,y-height/2),(x+width/2,y),(x,y+height/2),(x-width/2,y)])
    for i,s in enumerate(value.split("\n")):
        text(x,y+(i-(len(value.split("\n"))-1)/2)*24,s,20)


def circle(x,y,r=13,fill=INK,value=None):
    draw.ellipse(((x-r)*SCALE,(y-r)*SCALE,(x+r)*SCALE,(y+r)*SCALE),fill=fill,outline=INK,width=2*SCALE)
    svg.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{INK}" stroke-width="2"/>')
    if value:
        text(x,y,value,18,True)


def terminal(x,y):
    circle(x,y,13,"white")
    circle(x,y,8)


def connector(x,y,value,target=None,source=None):
    if target:
        arrow([(x+(20 if target[0] > x else -20),y),target],True)
    if source:
        arrow([source,(x+(20 if source[0] > x else -20),y)],True)
    circle(x,y,20,"white",value)


# Embed the existing user drawing as vector paths and a matching raster layer.
user_png = Image.open(OUT/"ecorefill-user-flow.png").convert("RGB")
img.paste(user_png.crop((0,105*SCALE,1600*SCALE,2080*SCALE)),(20*SCALE,205*SCALE))
user_svg = ET.parse(OUT/"ecorefill-user-flow.svg").getroot()
svg.append('<g transform="translate(20 100)">')
for child in user_svg:
    tag = child.tag.split("}")[-1]
    if tag in {"title","desc"} or (tag == "rect" and child.attrib.get("width") == "1600") or (tag == "text" and float(child.attrib["y"]) < 105):
        continue
    svg.append(ET.tostring(child,encoding="unicode"))
svg.append('</g>')

text(W/2,45,"EcoRefill — Updated Activity Diagram",36,True)
text(825,112,"User / EcoRefill App",28,True)
text(2260,112,"EcoRefill Machine",28,True)
text(3655,112,"Device Owner / EcoRefill App",28,True)

# Machine lane, retaining the original three machine activities.
circle(2250,225)
arrow([(2250,238),(2250,255)])
box(2250,285,"Power on")
arrow([(2250,315),(2250,345)])
box(2250,375,"Initialize")
arrow([(2250,405),(2250,440)])
decision(2250,495,"Ready?")
arrow([(2350,495),(2550,495)])
text(2460,475,"No",18,label=True)
box(2670,495,"Show error")
arrow([(2670,525),(2670,555)])
box(2670,585,"Retry")
arrow([(2550,585),(2500,585),(2500,420),(2250,420),(2250,440)])
arrow([(2250,550),(2250,600)])
text(2280,575,"Yes",18,label=True)
box(2250,630,"Show machine QR")
connector(2430,630,"Q",source=(2370,630))
arrow([(2250,660),(2250,700),(1850,700),(1850,730)])
arrow([(2250,660),(2250,730)])
arrow([(2250,660),(2250,700),(2670,700),(2670,730)])
box(1850,760,"Recycling")
box(2250,760,"Water refill")
box(2670,760,"Claim reward")
arrow([(1850,790),(1850,830)])
box(1850,860,"Detect item")
arrow([(1850,890),(1850,930)])
box(1850,960,"Check weight")
arrow([(1850,990),(1850,1025)])
decision(1850,1080,"Valid\nitem?")
arrow([(1950,1080),(2030,1080),(2030,1125)])
text(2000,1060,"No",18,label=True)
box(2030,1155,"Show\nmessage",width=150)
arrow([(1850,1135),(1850,1190)])
text(1880,1160,"Yes",18,label=True)
box(1850,1220,"Sort item")
arrow([(1850,1250),(1850,1290)])
box(1850,1320,"Add points")
arrow([(1850,1350),(1850,1430)])
box(1850,1460,"Update record")
arrow([(2030,1185),(2030,1460),(1970,1460)])

arrow([(2250,790),(2250,830)])
box(2250,860,"Detect bottle")
connector(2075,860,"W",target=(2130,860))
arrow([(2250,890),(2250,975)])
decision(2250,1030,"Bottle\nready?")
arrow([(2350,1030),(2430,1030),(2430,1110)])
text(2400,1010,"No",18,label=True)
box(2430,1140,"Show\nmessage",width=150)
arrow([(2250,1085),(2250,1220)])
text(2280,1150,"Yes",18,label=True)
box(2250,1250,"Dispense water")
arrow([(2250,1280),(2250,1430)])
box(2250,1460,"Update record")
arrow([(2430,1170),(2430,1460),(2370,1460)])

arrow([(2670,790),(2670,830)])
box(2670,860,"Scan QR")
connector(2495,860,"R",target=(2550,860))
arrow([(2670,890),(2670,930)])
box(2670,960,"Validate")
arrow([(2670,990),(2670,1045)])
decision(2670,1100,"Valid\nQR?")
arrow([(2770,1100),(2800,1100),(2800,1200)])
text(2810,1140,"No",18,label=True)
box(2800,1230,"Show\nmessage",width=130)
arrow([(2670,1155),(2670,1290)])
text(2700,1215,"Yes",18,label=True)
box(2670,1320,"Add points")
arrow([(2670,1350),(2670,1430)])
box(2670,1460,"Update record")
arrow([(2800,1260),(2800,1460),(2790,1460)])

arrow([(1850,1490),(1850,1950),(2250,1950),(2250,2000)])
arrow([(2250,1490),(2250,2000)])
arrow([(2670,1490),(2670,1950),(2250,1950),(2250,2000)])
box(2250,2030,"Sync data")
arrow([(2250,2060),(2250,2090)])
box(2250,2120,"Return to home")
arrow([(2250,2150),(2250,2172)])
terminal(2250,2185)

# Owner lane, retaining monitoring, alerts, collections and payment review.
circle(3660,225)
arrow([(3660,238),(3660,255)])
box(3660,285,"Log in")
arrow([(3660,315),(3660,360)])
decision(3660,415,"Valid\naccount?")
arrow([(3560,415),(3470,415),(3470,285),(3540,285)])
text(3510,395,"No",18,label=True)
arrow([(3660,470),(3660,530)])
text(3690,500,"Yes",18,label=True)
box(3660,560,"View dashboard")
arrow([(3660,590),(3660,630)])
box(3660,660,"Choose action")
for x,name in [(3050,"Monitor"),(3380,"Alerts"),(3710,"Collection"),(4180,"Payments")]:
    arrow([(3660,690),(3660,730),(x,730),(x,770)])
    box(x,800,name)

for x,steps in [(3050,["View status","View water","View quality","View activity"]),(3380,["View alerts","Review details","Take action"]),(3710,["View items","View records"])]:
    previous = 830
    for i,value in enumerate(steps):
        y = 900+i*100
        arrow([(x,previous),(x,y-30)])
        box(x,y,value)
        previous = y+30
    arrow([(x,previous),(x,2000),(3660,2000),(3660,2090)])

arrow([(4180,830),(4180,870)])
box(4180,900,"View requests")
connector(4005,900,"P",target=(4060,900))
arrow([(4180,930),(4180,970)])
box(4180,1000,"Verify payment")
arrow([(4180,1030),(4180,1075)])
decision(4180,1130,"Approve?")
arrow([(4080,1130),(4000,1130),(4000,1210)])
text(4040,1110,"No",18,label=True)
box(4000,1240,"Reject",width=190)
arrow([(4000,1270),(4000,1310)])
box(4000,1340,"Notify user",width=190)
arrow([(4280,1130),(4310,1130),(4310,1210)])
text(4315,1170,"Yes",18,label=True)
box(4310,1240,"Approve",width=190)
arrow([(4310,1270),(4310,1310)])
box(4310,1340,"Update points",width=190)
arrow([(4310,1370),(4310,1410)])
box(4310,1440,"Notify user",width=190)
connector(4130,1440,"O",source=(4215,1440))
arrow([(4000,1370),(4000,2000),(3660,2000),(3660,2090)])
arrow([(4310,1470),(4310,2000),(3660,2000),(3660,2090)])
box(3660,2120,"Log out")
arrow([(3660,2150),(3660,2172)])
terminal(3660,2185)

# Matching circles indicate communication across lanes without long crossings.
connector(915,760,"Q",target=(965,760))
connector(470,985,"R",source=(415,985))
connector(1080,1280,"P",source=(1015,1280))
connector(1560,1340,"W",source=(1515,1340))
connector(1080,1590,"O",target=(1015,1590))

# Frame and swimlane rules are drawn last so embedded art cannot cover them.
line([(25,85),(4425,85),(4425,2205),(25,2205),(25,85)])
line([(25,145),(4425,145)])
line([(1640,85),(1640,2205)])
line([(2885,85),(2885,2205)])
text(W/2,2235,"Matching connectors: Q = machine QR · R = recycling reward claim · W = refill request · P = payment request · O = owner approval · B = resume user refill",22)
svg.append('</svg>')
(OUT/"ecorefill-activity-flow-updated.svg").write_text("\n".join(svg))
img.save(OUT/"ecorefill-activity-flow-updated.png")
img.save(OUT/"ecorefill-activity-flow-updated.pdf","PDF",resolution=144)
print(OUT/"ecorefill-activity-flow-updated.png")
