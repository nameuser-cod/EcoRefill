"""Render the revised user activity flow as SVG, PNG and PDF (requires Pillow)."""
from html import escape
from math import atan2, cos, sin
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent
W, H, SCALE = 1600, 2080, 2
INK = "#242424"
img = Image.new("RGB", (W * SCALE, H * SCALE), "white")
draw = ImageDraw.Draw(img)
svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
       '<title id="title">EcoRefill revised user activity flow</title>',
       '<desc id="desc">Buying points and buying water share a machine QR scan. GCash purchases require owner approval before points are added. Users with insufficient points can buy points and return to their refill, rescanning if the QR expired. Recycling uses a separate reward QR.</desc>',
       f'<rect width="{W}" height="{H}" fill="white"/>']
font_paths = [Path("/System/Library/Fonts/Supplemental"), Path("/usr/share/fonts/truetype/dejavu")]
font_dir = next((p for p in font_paths if p.exists()), None)


def font(size, bold=False):
    if font_dir is None:
        return ImageFont.load_default(size=size * SCALE)
    name = ("Arial Bold.ttf" if bold else "Arial.ttf") if "Supplemental" in str(font_dir) else ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    return ImageFont.truetype(str(font_dir / name), size * SCALE)


def text(x, y, value, size=21, bold=False, label=False):
    f = font(size, bold)
    if label:
        bounds = draw.textbbox((x*SCALE, y*SCALE), value, font=f, anchor="mm")
        draw.rectangle((bounds[0]-6*SCALE, bounds[1]-3*SCALE, bounds[2]+6*SCALE, bounds[3]+3*SCALE), fill="white")
        width = (bounds[2]-bounds[0])/SCALE + 12
        svg.append(f'<rect x="{x-width/2}" y="{y-size/2-3}" width="{width}" height="{size+6}" fill="white"/>')
    draw.text((x*SCALE, y*SCALE), value, font=f, fill=INK, anchor="mm")
    svg.append(f'<text x="{x}" y="{y}" fill="{INK}" font-family="Arial,Helvetica,sans-serif" font-size="{size}" font-weight="{700 if bold else 400}" text-anchor="middle" dominant-baseline="central">{escape(value)}</text>')


def polygon(points, fill="white", width=2):
    scaled = [(x*SCALE, y*SCALE) for x, y in points]
    draw.polygon(scaled, fill=fill)
    draw.line(scaled + [scaled[0]], fill=INK, width=width*SCALE)
    svg.append(f'<polygon points="{" ".join(f"{x},{y}" for x,y in points)}" fill="{fill}" stroke="{INK}" stroke-width="{width}"/>')


def box(x, y, lines, width=290, height=60):
    polygon([(x-width/2,y-height/2),(x+width/2,y-height/2),(x+width/2,y+height/2),(x-width/2,y+height/2)])
    for i, value in enumerate(lines.split("\n")):
        text(x, y+(i-(len(lines.split("\n"))-1)/2)*25, value)


def decision(x, y, lines, width=230, height=100):
    polygon([(x,y-height/2),(x+width/2,y),(x,y+height/2),(x-width/2,y)])
    for i, value in enumerate(lines.split("\n")):
        text(x, y+(i-(len(lines.split("\n"))-1)/2)*24, value, 20)


def circle(x, y, radius=13, fill=INK, value=None):
    draw.ellipse(((x-radius)*SCALE,(y-radius)*SCALE,(x+radius)*SCALE,(y+radius)*SCALE),fill=fill,outline=INK,width=2*SCALE)
    svg.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{fill}" stroke="{INK}" stroke-width="2"/>')
    if value:
        text(x,y,value,18,True)


def arrow(points):
    draw.line([(x*SCALE,y*SCALE) for x,y in points],fill=INK,width=2*SCALE)
    svg.append(f'<polyline points="{" ".join(f"{x},{y}" for x,y in points)}" fill="none" stroke="{INK}" stroke-width="2"/>')
    a,b = points[-2:]
    angle = atan2(b[1]-a[1], b[0]-a[0])
    polygon([b,(b[0]-12*cos(angle)+5*sin(angle),b[1]-12*sin(angle)-5*cos(angle)),(b[0]-12*cos(angle)-5*sin(angle),b[1]-12*sin(angle)+5*cos(angle))],fill=INK,width=1)


text(800,42,"User / EcoRefill App — Revised Activity Flow",30,True)
text(800,80,"Scan the machine QR before buying points or buying water",22)
circle(900,125)
arrow([(900,138),(900,155)])
box(900,185,"Log in")
arrow([(900,215),(900,245)])
decision(900,295,"Valid\naccount?")
arrow([(785,295),(695,295),(695,185),(755,185)])
text(735,276,"No",label=True)
arrow([(900,345),(900,370)])
text(925,358,"Yes",18,label=True)
box(900,400,"View dashboard")
arrow([(900,430),(900,450)])
decision(900,500,"Choose\nactivity")

# The recycling reward remains separate from the machine purchase QR.
arrow([(785,500),(250,500),(250,540)])
text(490,481,"Recycle",label=True)
box(250,570,"Insert recyclable item")
arrow([(250,600),(250,630)])
decision(250,680,"More\nitems?")
arrow([(135,680),(65,680),(65,570),(105,570)])
text(93,653,"Yes",18,label=True)
arrow([(250,730),(250,765)])
text(276,748,"No",18,label=True)
box(250,795,"Press green button")
arrow([(250,825),(250,855)])
box(250,885,"Scan recycling reward QR")
arrow([(250,915),(250,945)])
decision(250,995,"Valid reward\nQR?")
arrow([(135,995),(65,995),(65,885),(105,885)])
text(91,965,"No",18,label=True)
arrow([(250,1045),(250,1080)])
text(278,1063,"Yes",18,label=True)
box(250,1110,"Claim recycling points")
arrow([(250,1140),(250,1170)])
box(250,1200,"View updated points")

# One shared scan establishes the machine and its owner for both purchases.
arrow([(1015,500),(1100,500),(1100,540)])
text(1240,483,"Buy points / water",label=True)
box(1100,570,"Press blue button on machine",width=310)
arrow([(1100,600),(1100,630)])
box(1100,660,"Scan machine refill QR",width=310)
arrow([(1100,690),(1100,720)])
decision(1100,770,"Valid,\nactive QR?")
arrow([(1215,770),(1410,770),(1410,725)])
text(1265,750,"No",18,label=True)
box(1410,690,"Show error /\nrequest new QR",width=230,height=70)
arrow([(1410,655),(1410,625),(1280,625),(1280,660),(1255,660)])
arrow([(1100,820),(1100,850)])
text(1127,835,"Yes",18,label=True)
decision(1100,900,"Buy points\nor buy water?",width=260)
arrow([(970,900),(850,900),(850,970)])
text(854,882,"Buy points",20,label=True)
arrow([(1230,900),(1350,900),(1350,970)])
text(1350,882,"Buy water",20,label=True)
circle(1350,938,18,"white","B")

box(850,1000,"Enter number of points")
arrow([(850,1030),(850,1060)])
box(850,1090,"Pay owner via GCash")
arrow([(850,1120),(850,1150)])
box(850,1180,"Submit payment details")
arrow([(850,1210),(850,1240)])
box(850,1270,"Wait for owner verification")
arrow([(850,1300),(850,1330)])
decision(850,1380,"Payment\napproved?")
arrow([(735,1380),(535,1380),(535,1410)])
text(650,1361,"No",18,label=True)
box(535,1450,"View rejection /\ncontact owner",width=260,height=80)
arrow([(850,1430),(850,1460)])
text(879,1447,"Yes",18,label=True)
box(850,1490,"Points added after approval",height=60)
arrow([(850,1520),(850,1550)])
box(850,1580,"View updated balance")
arrow([(850,1610),(850,1640)])
decision(850,1690,"Buy water\nnow?")
arrow([(850,1740),(850,1760)])
text(880,1750,"Yes",18,label=True)
box(850,1800,"Return to refill /\nrescan if QR expired",height=80)
arrow([(995,1800),(1060,1800)])
circle(1080,1800,20,"white","B")

box(1350,1000,"Select water amount")
arrow([(1350,1030),(1350,1060)])
decision(1350,1110,"Enough\npoints?")
arrow([(1235,1110),(1150,1110),(1150,1000),(995,1000)])
text(1107,1055,"No: buy points",19,label=True)
arrow([(1350,1160),(1350,1200)])
text(1380,1180,"Yes",18,label=True)
box(1350,1240,"Place container /\nconfirm refill",height=80)
arrow([(1350,1280),(1350,1320)])
box(1350,1370,"Machine checks container\nand points; dispenses water",height=100,width=350)
arrow([(1350,1420),(1350,1460)])
box(1350,1500,"View refill result / history",height=80,width=330)

# Completed activities merge; B returns to the existing refill options above.
arrow([(250,1230),(250,1880),(900,1880),(900,1900)])
arrow([(535,1490),(535,1880),(900,1880),(900,1900)])
arrow([(735,1690),(705,1690),(705,1880),(900,1880),(900,1900)])
text(709,1725,"No",18,label=True)
arrow([(1350,1540),(1350,1880),(900,1880),(900,1900)])
box(900,1930,"Return to dashboard")
arrow([(900,1960),(900,1975)])
box(900,1993,"Log out",height=36)
arrow([(900,2011),(900,2030)])
circle(900,2042,12,"white")
circle(900,2042,7)

svg.append("</svg>")
(OUT / "ecorefill-user-flow.svg").write_text("\n".join(svg))
img.save(OUT / "ecorefill-user-flow.png")
img.save(OUT / "ecorefill-user-flow.pdf", "PDF", resolution=144)
print(OUT / "ecorefill-user-flow.png")
