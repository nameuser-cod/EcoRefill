"""Generate matching SVG, HTML, Mermaid, and editable diagrams.net flowcharts."""
from pathlib import Path
import html
import json
import math
import xml.etree.ElementTree as ET

OUT = Path(__file__).resolve().parent
PAGES = []

def page(key, title, subtitle, height):
    p = dict(key=key, title=title, subtitle=subtitle, height=height, nodes={}, edges=[])
    PAGES.append(p)
    return p

def node(p, key, text, role, x, y, kind="action", width=270):
    p['nodes'][key] = dict(text=text, role=role, x=x, y=y, kind=kind,
                           w=width, h=110 if kind == 'decision' else max(76, 34+22*len(text.split('\n'))))

def edge(p, a, b, label='', ports='BT', via=(), at=None):
    p['edges'].append(dict(a=a, b=b, label=label, ports=ports, via=list(via), at=at))

p = page('01-access', '1. Sign in and choose an activity',
         'User and owner sessions are independent. Machine operation does not require an owner to be logged in.', 1500)
for prefix, x, role in [('u', 360, 'USER'), ('o', 1140, 'OWNER')]:
    node(p, prefix+'start', 'Open EcoRefill app', role, x, 180, 'terminal')
    node(p, prefix+'login', 'Log in', role, x, 310)
    node(p, prefix+'valid', 'Credentials valid?', 'SYSTEM', x, 465, 'decision')
    node(p, prefix+'error', 'Show login error', 'SYSTEM', x+300, 465, width=220)
    node(p, prefix+'dash', 'Open dashboard', role, x, 630)
    edge(p, prefix+'start', prefix+'login')
    edge(p, prefix+'login', prefix+'valid')
    edge(p, prefix+'valid', prefix+'error', 'No', 'RL', at=(x+205,440))
    edge(p, prefix+'error', prefix+'login', ports='TL', via=[(x+300,250),(x-175,250),(x-175,310)])
    edge(p, prefix+'valid', prefix+'dash', 'Yes', at=(x+28,565))
node(p, 'uchoice', 'Choose activity', 'USER', 360, 800, 'decision')
node(p, 'recycle', '2. Recycling flow\nReturn here when finished', 'USER + MACHINE', 190, 990, 'link')
node(p, 'refill', '3. Water refill flow\nReturn here when finished', 'USER + MACHINE', 530, 990, 'link')
node(p, 'ulogout', 'Log out / End session', 'USER', 360, 1280, 'terminal')
edge(p, 'udash','uchoice')
edge(p, 'uchoice','recycle','Recycle','LT',[(190,800)],(185,770))
edge(p, 'uchoice','refill','Refill','RT',[(530,800)],(525,770))
edge(p, 'uchoice','ulogout','Log out', at=(402,1160))
edge(p, 'recycle','udash', ports='LT', via=[(35,990),(35,565),(360,565)])
edge(p, 'refill','udash', ports='RT', via=[(720,990),(720,565),(360,565)])
node(p, 'ochoice', 'Choose activity', 'OWNER', 1140, 800, 'decision')
node(p, 'manage', 'Monitor / Handle alerts /\nCollect bottles and cans', 'OWNER', 980, 990)
node(p, 'payments', '4. Join at owner review\nReturn here after review', 'OWNER + SYSTEM', 1330, 990, 'link')
node(p, 'ologout', 'Log out / End session', 'OWNER', 1140, 1280, 'terminal')
edge(p, 'odash','ochoice')
edge(p, 'ochoice','manage','Manage','LT',[(980,800)],(960,770))
edge(p, 'ochoice','payments','Payments','RT',[(1330,800)],(1340,770))
edge(p, 'ochoice','ologout','Log out', at=(1182,1160))
edge(p, 'manage','odash', ports='LT', via=[(805,990),(805,565),(1140,565)])
edge(p, 'payments','odash', ports='RT', via=[(1530,990),(1530,565),(1140,565)])

p = page('02-recycling', '2. Recycle items and claim points',
         'Entry: signed-in user chooses recycling. Accepted and rejected items both finish inspection before the next-item decision.', 2390)
node(p,'rstart','Machine ready / Start recycling','USER + MACHINE',800,180,'terminal')
node(p,'insert','Insert one item','USER',800,310)
node(p,'inspect','Inspect the item','MACHINE',800,440)
node(p,'accept','Item accepted?','MACHINE',800,605,'decision')
node(p,'sort','Sort item and add\nsession points','MACHINE',420,770)
node(p,'reject','Return rejected item;\nadd no points','MACHINE',1180,770)
node(p,'more','More items?','USER',800,940,'decision')
node(p,'green','Press GREEN button','USER',800,1110)
node(p,'earned','Session points > 0?','MACHINE',800,1270,'decision')
node(p,'none','Show no reward','MACHINE',1180,1270)
node(p,'reward','Display reward QR','MACHINE',800,1430)
node(p,'scan','Scan reward QR in app','USER',800,1560)
node(p,'claim','Claim valid and unclaimed?','SYSTEM',800,1720,'decision',330)
node(p,'claimerror','Show error; do not credit points','SYSTEM',1220,1720,width=290)
node(p,'retry','Retry with valid QR?','USER',1220,1900,'decision')
node(p,'credit','Credit user points once;\nsave reward transaction','SYSTEM',800,1910)
node(p,'rend','Show result; machine returns to\nrecycling; user returns to Section 1','USER + MACHINE',800,2220,'terminal',430)
for a,b in [('rstart','insert'),('insert','inspect'),('inspect','accept'),('sort','more'),('reject','more'),('green','earned'),('reward','scan'),('scan','claim'),('credit','rend')]:
    if a in ('sort','reject'): edge(p,a,b,ports='BT',via=[(p['nodes'][a]['x'],860),(800,860)])
    else: edge(p,a,b)
edge(p,'accept','sort','Yes','LT',[(420,605)],(580,580))
edge(p,'accept','reject','No','RT',[(1180,605)],(1015,580))
edge(p,'more','insert','Yes','LL',[(170,940),(170,310)],(340,915))
edge(p,'more','green','No',at=(825,1040))
edge(p,'earned','reward','Yes',at=(830,1370))
edge(p,'earned','none','No','RL',at=(1000,1245))
edge(p,'none','rend',ports='RR',via=[(1510,1270),(1510,2220)])
edge(p,'claim','credit','Yes',at=(825,1830))
edge(p,'claim','claimerror','No','RL',at=(1010,1695))
edge(p,'claimerror','retry')
edge(p,'retry','scan','Yes','RT',[(1450,1900),(1450,1490),(800,1490)],(1470,1780))
edge(p,'retry','rend','No / Cancel','BR',[(1220,2140),(1080,2140),(1080,2220)],(1275,2060))

p = page('03-refill', '3. Select, pay for, and dispense water',
         'Entry: signed-in user chooses refill. Payment approval adds points; only a validated refill request can start dispensing.', 3260)
for key,text,role,y in [
 ('blue','Press BLUE button / Select refill','USER',180),
 ('qr','Create refill session; display QR','MACHINE',310),
 ('selection','Scan valid refill QR;\nselect water amount','USER',440),
 ('confirm','Place container and\nconfirm refill request','USER',790),
 ('validate','Validate session, amount,\nbalance and machine availability','SYSTEM / MACHINE',940),
 ('reserve','Reserve refill and\ndeduct points atomically','SYSTEM',1300),
 ('dispense','Dispense water; monitor container','MACHINE',1450),
 ('success','Save completed refill','SYSTEM',1820),
 ('result','Show actual refill / refund result','USER APP',2560),
 ('reset','Return machine to recycling mode','MACHINE',2710)]:
    node(p,key,text,role,740,y,width=310)
node(p,'balance','Enough points?','USER APP',740,620,'decision')
node(p,'buy','Buy points?','USER',1240,620,'decision')
node(p,'purchase','4. Point purchase flow\nReturn with purchase status','USER + OWNER',1240,810,'link',320)
node(p,'resume','Resume refill; scan new QR\nif the session expired','USER',1240,980,width=320)
node(p,'cancelbuy','Cancel refill','USER',1240,1190)
node(p,'valid','Refill request valid?','SYSTEM / MACHINE',740,1120,'decision')
node(p,'invalid','Show reason; no deduction\nand no dispensing','SYSTEM',270,1120,width=310)
node(p,'retryrefill','Retry refill?','USER',270,1320,'decision')
node(p,'complete','Dispensing complete?','MACHINE',740,1630,'decision')
node(p,'stop','Stop dispensing on\nerror or timeout','MACHINE',1240,1630)
node(p,'refund','Attempt refund of deducted points','SYSTEM',1240,1790,width=330)
node(p,'refunded','Refund successful?','SYSTEM',1240,1970,'decision')
node(p,'refundok','Record failed refill\nand successful refund','SYSTEM',1090,2150)
node(p,'refundpending','Record failed refill;\nrefund unresolved','SYSTEM',1430,2310,width=280)
node(p,'end','Return to user dashboard\nSection 1','USER',740,2950,'terminal',350)
for a,b in [('blue','qr'),('qr','selection'),('selection','balance'),('confirm','validate'),('validate','valid'),('reserve','dispense'),('dispense','complete'),('success','result'),('result','reset'),('reset','end'),('purchase','resume'),('stop','refund'),('refund','refunded')]: edge(p,a,b)
edge(p,'balance','confirm','Yes',at=(770,720))
edge(p,'balance','buy','No','RL',at=(980,595))
edge(p,'buy','purchase','Yes',at=(1270,735))
edge(p,'buy','cancelbuy','No','RR',[(1545,620),(1545,1190)],(1530,725))
edge(p,'resume','selection','Recheck QR and balance','RT',[(1490,980),(1490,365),(740,365)],(1300,345))
edge(p,'cancelbuy','reset',ports='RL',via=[(1585,1190),(1585,2840),(520,2840),(520,2710)])
edge(p,'valid','reserve','Yes',at=(770,1230))
edge(p,'valid','invalid','No','LR',at=(510,1090))
edge(p,'invalid','retryrefill')
edge(p,'retryrefill','blue','Yes','LL',[(40,1320),(40,180)],(70,800))
edge(p,'retryrefill','reset','No / Cancel','BL',[(270,2710)],(210,1700))
edge(p,'complete','success','Yes',at=(770,1740))
edge(p,'complete','stop','No','RL',at=(990,1605))
edge(p,'refunded','refundok','Yes','LT',[(1090,1970)],(1050,1940))
edge(p,'refunded','refundpending','No','RT',[(1430,1970)],(1420,1940))
edge(p,'refundok','result',ports='BT',via=[(1090,2490),(740,2490)])
edge(p,'refundpending','result',ports='BT',via=[(1430,2490),(740,2490)])

p = page('04-payment', '4. Buy points and verify payment',
         'Called from the refill selection page. The signed-in owner reviews purchases in Transactions; records do not replace owner login.', 2400)
node(p,'pstart','Enter points to purchase','USER',800,180,'terminal')
node(p,'available','Purchase available?','SYSTEM',800,360,'decision')
node(p,'unavailable','Show unavailable;\nno payment / no points transferred','USER APP',1240,360,width=330)
node(p,'submit','Pay via GCash and\nsubmit payment reference','USER',800,550)
node(p,'pending','Save pending purchase;\nno points credited yet','SYSTEM',800,710)
node(p,'review','Review received payment\nand purchase details','SIGNED-IN OWNER',800,870)
node(p,'status','Review status?','OWNER',800,1040,'decision')
node(p,'wait','Keep pending; wait for review\nNo points credited','SYSTEM',360,1040,width=310)
node(p,'rejectpay','Reject payment; notify user\nNo points credited','OWNER / SYSTEM',1240,1040,width=330)
node(p,'transfer','Validate owner balance and\ntransfer eligibility','SYSTEM',800,1250)
node(p,'allowed','Transfer allowed?','SYSTEM',800,1430,'decision')
node(p,'blocked','Show transfer pending / error\nDo not credit points','SYSTEM',1240,1430,width=330)
node(p,'creditpoints','Transfer owner points to user\nand record approved purchase once','SYSTEM',800,1640,width=370)
node(p,'pend','Show purchase status; return to\nSection 3: resume refill and recheck\nQR validity and available balance','USER APP',800,2090,'terminal',440)
for a,b in [('pstart','available'),('submit','pending'),('pending','review'),('review','status'),('transfer','allowed'),('creditpoints','pend')]: edge(p,a,b)
edge(p,'available','submit','Yes',at=(830,470))
edge(p,'available','unavailable','No','RL',at=(1010,335))
edge(p,'unavailable','pend',ports='RR',via=[(1530,360),(1530,2090)])
edge(p,'status','wait','Pending','LR',at=(590,1015))
edge(p,'wait','review',ports='TT',via=[(360,795),(800,795)])
edge(p,'status','rejectpay','Rejected','RL',at=(1010,1015))
edge(p,'rejectpay','pend',ports='RR',via=[(1490,1040),(1490,2090)])
edge(p,'status','transfer','Approved',at=(855,1160))
edge(p,'allowed','creditpoints','Yes',at=(830,1545))
edge(p,'allowed','blocked','No','RL',at=(1010,1405))
edge(p,'blocked','pend',ports='BR',via=[(1240,1930),(1080,1930),(1080,2090)])

COLORS = {'decision':('#fff3cf','#a47716'), 'terminal':('#e4f4e9','#26734d'),
          'link':('#efeaff','#7154a6'), 'action':('#edf5ff','#3d6689')}

def port(n, side):
    return {'T':(n['x'],n['y']-n['h']/2), 'B':(n['x'],n['y']+n['h']/2),
            'L':(n['x']-n['w']/2,n['y']), 'R':(n['x']+n['w']/2,n['y'])}[side]

def points(p,e):
    a=port(p['nodes'][e['a']],e['ports'][0]); b=port(p['nodes'][e['b']],e['ports'][1])
    return [a]+e['via']+[b]

def svg(p):
    h=p['height']
    s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{h}" viewBox="0 0 1600 {h}" role="img" aria-labelledby="title">',
       f'<title id="title">{html.escape(p["title"])}</title>',
       '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#43515e"/></marker></defs>',
       f'<rect width="1600" height="{h}" fill="white"/>',
       '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#192b39}.edge{fill:none;stroke:#43515e;stroke-width:2;stroke-linejoin:round;marker-end:url(#arrow)}.label{font-size:17px;paint-order:stroke;stroke:white;stroke-width:8px;stroke-linejoin:round}.role{font-size:12px;letter-spacing:1px;font-weight:700;fill:#526978}</style>',
       f'<text x="55" y="53" font-size="32" font-weight="700">{html.escape(p["title"])}</text>',
       f'<text x="55" y="87" font-size="16">{html.escape(p["subtitle"])}</text>',
       '<path d="M55 108 H1545" stroke="#b7d8c4" stroke-width="3"/>']
    for e in p['edges']:
        pts=points(p,e)
        s.append('<polyline class="edge" points="'+' '.join(f'{x},{y}' for x,y in pts)+'"/>')
    for key,n in p['nodes'].items():
        x,y,w,nh=n['x'],n['y'],n['w'],n['h']; fill,stroke=COLORS[n['kind']]
        if n['kind']=='decision':
            s.append(f'<polygon points="{x},{y-nh/2} {x+w/2},{y} {x},{y+nh/2} {x-w/2},{y}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        else:
            radius=30 if n['kind']=='terminal' else 9
            s.append(f'<rect x="{x-w/2}" y="{y-nh/2}" width="{w}" height="{nh}" rx="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        lines=n['text'].split('\n')
        top=y-(len(lines)*22+14)/2+10
        s.append(f'<text class="role" text-anchor="middle" x="{x}" y="{top}">{html.escape(n["role"])}</text>')
        for i,line in enumerate(lines):
            s.append(f'<text text-anchor="middle" font-size="18" x="{x}" y="{top+23+i*22}">{html.escape(line)}</text>')
    for e in p['edges']:
        if e['label']:
            a,b=points(p,e)[:2]; x,y=e['at'] or ((a[0]+b[0])/2+25,(a[1]+b[1])/2)
            s.append(f'<text class="label" text-anchor="middle" x="{x}" y="{y}">{html.escape(e["label"])}</text>')
    s.append(f'<text x="55" y="{h-35}" font-size="15" fill="#526978">EcoRefill · Rectangles: actions · Diamonds: decisions · Purple boxes: linked sections · Actor shown inside each node</text></svg>')
    return '\n'.join(s)

def drawio():
    root=ET.Element('mxfile',host='app.diagrams.net',type='device')
    for p in PAGES:
        d=ET.SubElement(root,'diagram',id=p['key'],name=p['title'])
        model=ET.SubElement(d,'mxGraphModel',dx='1600',dy=str(p['height']),grid='1',gridSize='10',page='1',pageWidth='1600',pageHeight=str(p['height']))
        r=ET.SubElement(model,'root'); ET.SubElement(r,'mxCell',id='0'); ET.SubElement(r,'mxCell',id='1',parent='0')
        title=ET.SubElement(r,'mxCell',id='title',value=p['title'],style='text;html=0;fontSize=30;fontStyle=1;align=left;',vertex='1',parent='1')
        ET.SubElement(title,'mxGeometry',x='55',y='20',width='1490',height='60',attrib={'as':'geometry'})
        for k,n in p['nodes'].items():
            fill,stroke=COLORS[n['kind']]
            shape='rhombus;' if n['kind']=='decision' else 'rounded=1;arcSize=15;'
            cell=ET.SubElement(r,'mxCell',id=k,value=n['role']+'\n'+n['text'],style=shape+f'whiteSpace=wrap;html=0;fontSize=17;fillColor={fill};strokeColor={stroke};',vertex='1',parent='1')
            ET.SubElement(cell,'mxGeometry',x=str(n['x']-n['w']/2),y=str(n['y']-n['h']/2),width=str(n['w']),height=str(n['h']),attrib={'as':'geometry'})
        coords={'T':('0.5','0'),'B':('0.5','1'),'L':('0','0.5'),'R':('1','0.5')}
        for i,e in enumerate(p['edges']):
            ex,ey=coords[e['ports'][0]]; ix,iy=coords[e['ports'][1]]
            cell=ET.SubElement(r,'mxCell',id='edge'+str(i),value=e['label'],source=e['a'],target=e['b'],edge='1',parent='1',style=f'edgeStyle=segmentEdgeStyle;rounded=0;html=0;endArrow=block;endFill=1;fontSize=15;labelBackgroundColor=#ffffff;exitX={ex};exitY={ey};entryX={ix};entryY={iy};')
            geo=ET.SubElement(cell,'mxGeometry',relative='1',attrib={'as':'geometry'})
            if e['via']:
                arr=ET.SubElement(geo,'Array',attrib={'as':'points'})
                for x,y in e['via']: ET.SubElement(arr,'mxPoint',x=str(x),y=str(y))
    return ET.tostring(root,encoding='unicode',xml_declaration=True)

def png(p):
    """Rasterize the same graph primitives for a directly viewable export."""
    from PIL import Image, ImageDraw, ImageFont
    im=Image.new('RGB',(1600,p['height']),'white'); d=ImageDraw.Draw(im)
    font_dir=Path('/System/Library/Fonts/Supplemental')
    def font(size,bold=False):
        return ImageFont.truetype(str(font_dir/('Arial Bold.ttf' if bold else 'Arial.ttf')),size)
    def txt(x,y,value,size=18,bold=False,fill='#192b39',center=True):
        d.text((x,y),value,font=font(size,bold),anchor='ms' if center else 'ls',fill=fill)
    txt(55,53,p['title'],32,True,center=False)
    txt(55,87,p['subtitle'],16,center=False)
    d.line([(55,108),(1545,108)],fill='#b7d8c4',width=3)
    for e in p['edges']:
        pts=points(p,e); d.line(pts,fill='#43515e',width=2,joint='curve')
        x,y=pts[-1]; ax,ay=pts[-2]; angle=math.atan2(y-ay,x-ax)
        arrow=[(x,y),(x-14*math.cos(angle)+6*math.sin(angle),y-14*math.sin(angle)-6*math.cos(angle)),
               (x-14*math.cos(angle)-6*math.sin(angle),y-14*math.sin(angle)+6*math.cos(angle))]
        d.polygon(arrow,fill='#43515e')
    for n in p['nodes'].values():
        x,y,w,h=n['x'],n['y'],n['w'],n['h']; fill,stroke=COLORS[n['kind']]
        if n['kind']=='decision':
            shape=[(x,y-h/2),(x+w/2,y),(x,y+h/2),(x-w/2,y)]
            d.polygon(shape,fill=fill); d.line(shape+[shape[0]],fill=stroke,width=2)
        else:
            d.rounded_rectangle((x-w/2,y-h/2,x+w/2,y+h/2),radius=30 if n['kind']=='terminal' else 9,fill=fill,outline=stroke,width=2)
        lines=n['text'].split('\n'); top=y-(len(lines)*22+14)/2+10
        txt(x,top,n['role'],12,True,fill='#526978')
        for i,line in enumerate(lines): txt(x,top+23+i*22,line)
    for e in p['edges']:
        if e['label']:
            a,b=points(p,e)[:2]; x,y=e['at'] or ((a[0]+b[0])/2+25,(a[1]+b[1])/2)
            f=font(17); bounds=d.textbbox((x,y),e['label'],font=f,anchor='ms')
            d.rectangle((bounds[0]-5,bounds[1]-3,bounds[2]+5,bounds[3]+3),fill='white')
            txt(x,y,e['label'],17)
    txt(55,p['height']-35,'EcoRefill · Rectangles: actions · Diamonds: decisions · Purple boxes: linked sections · Actor shown inside each node',15,center=False)
    im.save(OUT/(p['key']+'.png'))

def mermaid(p):
    lines=['flowchart TD']
    for k,n in p['nodes'].items():
        value=n['role']+'<br/>'+n['text'].replace('\n','<br/>')
        a,b=('{','}') if n['kind']=='decision' else ('([','])') if n['kind']=='terminal' else ('[',']')
        lines.append(f'    {k}{a}"{value}"{b}')
    for e in p['edges']:
        label=f'|"{e["label"]}"|' if e['label'] else ''
        lines.append(f'    {e["a"]} -->{label} {e["b"]}')
    return '\n'.join(lines)

def validate():
    for p in PAGES:
        ns=p['nodes']; outgoing={k:[] for k in ns}
        for e in p['edges']:
            assert e['a'] in ns and e['b'] in ns
            outgoing[e['a']].append(e)
            pts=points(p,e)
            for a,b in zip(pts,pts[1:]):
                assert a[0]==b[0] or a[1]==b[1], (p['key'],e,'non-orthogonal')
                for k,n in ns.items():
                    l,r=n['x']-n['w']/2+2,n['x']+n['w']/2-2
                    t,d=n['y']-n['h']/2+2,n['y']+n['h']/2-2
                    hit=(a[0]==b[0] and l<a[0]<r and max(min(a[1],b[1]),t)<min(max(a[1],b[1]),d)) or (a[1]==b[1] and t<a[1]<d and max(min(a[0],b[0]),l)<min(max(a[0],b[0]),r))
                    assert not hit, (p['key'],e['a'],e['b'],'line crosses node',k)
        for k,n in ns.items():
            if n['kind']=='decision':
                assert len(outgoing[k])>=2, (p['key'],k)
                assert all(e['label'] for e in outgoing[k]), (p['key'],k)
            elif not outgoing[k]:
                assert n['kind']=='terminal', (p['key'],k,'dead end')
    recycling=PAGES[1]; refill=PAGES[2]; payment=PAGES[3]
    assert [e['b'] for e in recycling['edges'] if e['a']=='insert']==['inspect']
    assert [e['b'] for e in recycling['edges'] if e['a']=='scan']==['claim']
    assert [e['a'] for e in refill['edges'] if e['b']=='success']==['complete']
    assert [e['a'] for e in payment['edges'] if e['b']=='creditpoints']==['allowed']

validate()
sections=[]
md=['# EcoRefill — Corrected activity flow','',
    'Both users and device owners sign in. The machine has no login. The four linked sections describe one workflow; purple callouts identify the destination and return point.', '',
    'Points are credited only after a valid reward claim or a verified, successfully transferred purchase. A failed refill is recorded as failed, with its actual refund status. The machine returns to recycling mode after the refill result.', '']
for p in PAGES:
    markup=svg(p)
    png(p)
    (OUT/(p['key']+'.svg')).write_text(markup)
    sections.append(f'<section id="{p["key"]}">{markup}</section>')
    md += ['## '+p['title'], '', p['subtitle'], '', '```mermaid', mermaid(p), '```', '']
    (OUT/(p['key']+'.mmd')).write_text(mermaid(p)+'\n')
(OUT/'ecorefill-corrected-flow.md').write_text('\n'.join(md))
(OUT/'ecorefill-corrected-flow.drawio').write_text(drawio())
(OUT/'flow-data.json').write_text(json.dumps(PAGES,indent=2))
nav=''.join(f'<a href="#{p["key"]}">{html.escape(p["title"])}</a>' for p in PAGES)
(OUT/'ecorefill-corrected-flow.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>EcoRefill — Corrected activity flow</title><style>
*{box-sizing:border-box}body{margin:0;background:#edf2ef;font-family:Arial,sans-serif;color:#192b39}header{padding:24px 32px;background:#133d2c;color:white}h1{margin:0 0 10px;font-size:25px}header p{margin:0 0 14px;max-width:950px;line-height:1.5}nav{display:flex;gap:12px;flex-wrap:wrap}nav a{color:white;border:1px solid #709784;padding:9px 14px;border-radius:6px;text-decoration:none}main{max-width:1600px;margin:auto;padding:24px}section{background:white;margin-bottom:30px;box-shadow:0 2px 15px #173b2512;border-radius:12px;overflow:hidden;scroll-margin:20px}svg{display:block;width:100%;height:auto}@media print{header{display:none}main{padding:0}section{box-shadow:none;break-after:page;border-radius:0;margin:0}svg{max-height:95vh}}@media(max-width:850px){main{padding:8px}section{overflow:auto}svg{min-width:1000px}}</style><header><h1>EcoRefill — Corrected activity flow</h1><p>Start with sign-in, then follow the linked recycling, refill, and purchase flows. Actor labels identify who performs each action. Both users and owners sign in; the machine runs independently.</p><nav>'''+nav+'</nav></header><main>'+''.join(sections)+'</main></html>')
print(f'Generated {len(PAGES)} linked diagrams with {sum(len(p["nodes"]) for p in PAGES)} nodes and {sum(len(p["edges"]) for p in PAGES)} verified connections in {OUT}')
