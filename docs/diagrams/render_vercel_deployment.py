"""Render the UML-style deployment diagram to SVG, PNG and PDF with Pillow."""
from html import escape
from math import atan2, cos, sin
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
W, H, SCALE = 1700, 1490, 2
INK = '#292929'
image = Image.new('RGB', (W * SCALE, H * SCALE), 'white')
draw = ImageDraw.Draw(image)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
       '<title id="title">EcoRefill deployment diagram — UML style</title>',
       '<desc id="desc">Black-and-white UML deployment nodes with nested artifacts. Vercel hosts the web dashboards. The Android app on the phone uses Firebase for sign-in and records, and reaches the Raspberry Pi API through Cloudflare Tunnel. The Pi runs the kiosk, Flask, YOLO and hardware controls. It saves machine alerts to Firestore and sends owner notifications through Firebase Cloud Messaging to the Android app. Tapping a notification opens Alerts.</desc>',
       f'<rect width="{W}" height="{H}" fill="white"/>']
fonts = Path('/System/Library/Fonts/Supplemental')
mac_fonts = fonts.exists()
if not mac_fonts:
    fonts = Path('/usr/share/fonts/truetype/dejavu')


def font(size, bold=False):
    name = ('Arial Bold.ttf' if bold else 'Arial.ttf') if mac_fonts else (
        'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')
    return ImageFont.truetype(str(fonts / name), size * SCALE)


def text(x, y, value, size=21, bold=False, label=False):
    f = font(size, bold)
    if label:
        bounds = draw.textbbox((x*SCALE, y*SCALE), value, font=f, anchor='mm')
        pad = 5*SCALE
        draw.rectangle((bounds[0]-pad, bounds[1]-pad, bounds[2]+pad, bounds[3]+pad), fill='white')
        width = f.getlength(value)/SCALE+10
        svg.append(f'<rect x="{x-width/2}" y="{y-size/2-5}" width="{width}" height="{size+10}" fill="white"/>')
    draw.text((x*SCALE, y*SCALE), value, font=f, fill=INK, anchor='mm')
    svg.append(f'<text x="{x}" y="{y}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" fill="{INK}" text-anchor="middle" dominant-baseline="central">{escape(value)}</text>')


def rect(x, y, w, h, fill='white', width=2):
    draw.rectangle((x*SCALE, y*SCALE, (x+w)*SCALE, (y+h)*SCALE), fill=fill, outline=INK, width=width*SCALE)
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{INK}" stroke-width="{width}"/>')


def polygon(points, fill='white', width=2):
    scaled = [(x*SCALE, y*SCALE) for x,y in points]
    draw.polygon(scaled, fill=fill)
    draw.line(scaled+[scaled[0]], fill=INK, width=width*SCALE)
    svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in points)}" fill="{fill}" stroke="{INK}" stroke-width="{width}"/>')


def node(x, y, w, h, kind, title):
    depth = 12
    polygon([(x,y),(x+depth,y-depth),(x+w+depth,y-depth),(x+w,y)], '#f6f6f6')
    polygon([(x+w,y),(x+w+depth,y-depth),(x+w+depth,y+h-depth),(x+w,y+h)], '#f0f0f0')
    rect(x,y,w,h)
    text(x+w/2,y+26,f'«{kind}»',20)
    text(x+w/2,y+57,title,26,True)


def artifact(x, y, w, h, lines, size=21):
    rect(x,y,w,h)
    # Folded-page icon used for UML artifacts in the reference.
    ix, iy = x+w-27, y+12
    polygon([(ix,iy),(ix+11,iy),(ix+18,iy+7),(ix+18,iy+24),(ix,iy+24)],width=1)
    draw.line([(px*SCALE,py*SCALE) for px,py in [(ix+11,iy),(ix+11,iy+7),(ix+18,iy+7)]],fill=INK,width=SCALE)
    svg.append(f'<polyline points="{ix+11},{iy} {ix+11},{iy+7} {ix+18},{iy+7}" fill="none" stroke="{INK}" stroke-width="1"/>')
    text(x+w/2,y+20,'«artifact»',19)
    for i,line in enumerate(lines):
        text(x+w/2,y+45+i*24,line,size)


def arrow(points, both=False):
    draw.line([(x*SCALE,y*SCALE) for x,y in points],fill=INK,width=2*SCALE)
    svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{INK}" stroke-width="2"/>')
    ends = [(points[-2],points[-1])]
    if both:
        ends.append((points[1],points[0]))
    for a,b in ends:
        angle = atan2(b[1]-a[1],b[0]-a[0])
        triangle = [b,(b[0]-12*cos(angle)+5*sin(angle),b[1]-12*sin(angle)-5*cos(angle)),
                    (b[0]-12*cos(angle)-5*sin(angle),b[1]-12*sin(angle)+5*cos(angle))]
        draw.polygon([(x*SCALE,y*SCALE) for x,y in triangle],fill=INK)
        svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in triangle)}" fill="{INK}"/>')


rect(30,25,1640,1440,width=3)
text(850,61,'EcoRefill — Deployment Diagram',34,True)
node(100,170,400,320,'cloud service','Vercel Web Hosting')
artifact(120,265,360,85,['User Dashboard','React / Vite'])
artifact(120,365,360,100,['Device Owner Dashboard','React / Vite'])
node(720,170,400,320,'cloud service','Firebase')
artifact(740,265,360,85,['Firebase Authentication'])
artifact(740,365,360,100,['Cloud Firestore Database','Records · EcoPoints · alerts'])
node(1300,170,320,320,'cloud service','FCM / Notifications')
artifact(1320,265,280,85,['Firebase Cloud Messaging','Push Notifications'],20)
artifact(1320,365,280,100,['Owner Android alerts','Tap to open Alerts'])

node(100,670,400,300,'device','Phone')
artifact(120,805,360,100,['Android App','React / Capacitor'])
node(720,670,400,420,'device','EcoRefill — Raspberry Pi 5')
artifact(740,765,360,95,['Local React Kiosk','Machine screen / QR display'])
rect(740,880,360,185)
text(920,902,'«execution environment»',19)
text(920,930,'Python / Flask',23,True)
artifact(758,950,324,95,['machine_flow.py + YOLO','Rewards · refills · alerts'],20)
node(1300,670,320,300,'device','Machine Hardware')
artifact(1320,765,280,85,['Camera · Scale','Buttons · Sensors'])
artifact(1320,860,280,85,['Sorting Servos · Pump','Machine Screen'])
node(100,1140,400,235,'cloud service','Cloudflare Tunnel')
artifact(120,1235,360,115,['HTTPS Public Pi API','Reward claims · payments','Phone registration'])

arrow([(300,490),(300,670)])
text(300,564,'Loads website',21,label=True)
text(300,593,'HTTPS',19,label=True)
arrow([(512,755),(610,755),(610,330),(720,330)],both=True)
text(610,533,'Sign-in /',21,label=True)
text(610,562,'read & write records',21,label=True)
arrow([(920,490),(920,670)],both=True)
text(920,552,'Reads & updates',21,label=True)
text(920,581,'records and alerts',21,label=True)
arrow([(1132,755),(1230,755),(1230,330),(1300,330)])
text(1230,530,'Sends machine',21,label=True)
text(1230,559,'alerts',21,label=True)
arrow([(1460,158),(1460,119),(60,119),(60,830),(100,830)])
text(880,119,"Push notifications to the owner's Android app",21,label=True)
arrow([(1132,870),(1300,870)],both=True)
text(1215,836,'Controls',21,label=True)
arrow([(300,970),(300,1128)],both=True)
text(300,1037,'Secure requests',21,label=True)
text(300,1066,'HTTPS / ID token',19,label=True)
arrow([(512,1255),(630,1255),(630,1030),(720,1030)],both=True)
text(630,1141,'Public Pi API',21,label=True)

svg.append('</svg>')
stem = OUT / 'ecorefill-vercel-deployment'
stem.with_suffix('.svg').write_text('\n'.join(svg)+'\n')
image.save(stem.with_suffix('.png'))
image.save(stem.with_suffix('.pdf'),'PDF',resolution=144)
print(stem.with_suffix('.png'))
