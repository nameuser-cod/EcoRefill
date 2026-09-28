"""Render the connected EcoRefill flow in the supplied three-lane style."""
from pathlib import Path
import os
os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/ecorefill-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon, Circle, FancyArrowPatch
from matplotlib.path import Path as MPath
import matplotlib.patheffects as pe
import json

OUT = Path(__file__).resolve().parent
W, H = 3600, 2700
nodes, edges, labels = {}, [], []

def node(key, text, x, y, w=230, h=64, kind='action', fs=18):
    nodes[key] = dict(text=text, x=x, y=y, w=w, h=h, kind=kind, fs=fs)

def decision(key, text, x, y, w=230):
    node(key, text, x, y, w, 110, 'decision', 17)

def connector(key, text, x, y):
    node(key, text, x, y, 42, 42, 'connector', 18)

def edge(a, b, ports='BT', via=(), text='', at=None, dashed=False):
    edges.append(dict(a=a,b=b,ports=ports,via=list(via),text=text,at=at,dashed=dashed))

def label(text,x,y,fs=20,bold=False):
    labels.append((text,x,y,fs,bold))

def ret(a, key, mark, x, y, ports='BT', via=()):
    connector(key,mark,x,y)
    edge(a,key,ports,via)

# Common account access, kept inside the user and owner lanes.
for p,x in [('u',560),('o',3000)]:
    node(p+'start','',x,145,22,22,'start')
    node(p+'login','Log in to EcoRefill app',x,210,285)
    decision(p+'valid','Valid\ncredentials?',x,310,210)
    node(p+'dash','View dashboard',x,430,270)
    decision(p+'choose','Choose action',x,530,245)
    for a,b in [('start','login'),('login','valid'),('dash','choose')]:
        edge(p+a,p+b)
    edge(p+'valid',p+'dash',text='Yes',at=(x+26,382))
    edge(p+'valid',p+'login','LL',[(x-205,310),(x-205,210)],'No',(x-173,280))
    connector(p+'return','U' if p=='u' else 'O',x-205,430)
    edge(p+'return',p+'dash','RL')

# Machine initialization and its persistent ready state.
node('mstart','',1790,145,22,22,'start')
node('power','Power on EcoRefill machine',1790,200,325)
node('init','Initialize system',1790,280,280)
decision('network','Firebase\nreachable?',1790,380,230)
node('networkerror','Show connection error',2200,355,280)
node('retry','Retry connection',2200,445,240)
node('screen','Load machine screen',1790,490,280)
node('ready','Machine ready\nWait for item or button input',1790,585,340,78)
connector('mreturn','M',1560,585)
edge('mreturn','ready','RL')
for a,b in [('mstart','power'),('power','init'),('init','network'),('screen','ready'),('networkerror','retry')]:
    edge(a,b)
edge('network','screen',text='Yes',at=(1818,451))
edge('network','networkerror','RT',[(1980,380),(1980,303),(2200,303)],'No',(1990,330))
edge('retry','network','BL',[(2200,535),(1480,535),(1480,380)],'Retry',(1510,410))

# User chooses recycling, refill, or logout. Buying points belongs to refill.
label('RECYCLING',240,642,21,True)
label('WATER REFILL',895,642,21,True)
connector('ulogoutentry','L',560,650)
edge('uchoose','ulogoutentry',text='Log out',at=(607,615))
node('insert','Insert one item',240,715,245)
node('blue','Press blue button',895,690,240)
edge('uchoose','insert','LT',[(240,530)],'Recycle',(292,555))
edge('uchoose','blue','RT',[(895,530)],'Refill',(827,555))

# Recycling: inspect before asking for more items; finish before creating QR.
node('inspect','Detect material\nand check weight',1400,715,285,76)
decision('accepted','Item\naccepted?',1400,850,230)
node('sort','Sort item; add\nsession points',1265,970,220,76)
node('reject','Reject item;\nno points added',1565,970,220,76)
decision('more','More items?',240,1100,220)
node('green','Press green button',240,1250,260)
decision('earned','Session points\ngreater than zero?',1400,1250,250)
node('noreward','Show no reward;\nreset batch',1690,1250,240,76)
node('rewardqr','Display reward QR',1400,1390,260)
node('scanreward','Scan reward QR in app',240,1460,280)
decision('claim','QR valid\nand unclaimed?',1400,1540,240)
node('credit','Credit user points;\nsave reward record',1400,1690,270,76)
node('claimerror','Show claim error;\ndo not credit points',1685,1690,250,76)
node('recyclingresult','View recycling result',240,1830,270)
edge('insert','inspect','RL',[(410,715),(410,745),(1170,745),(1170,715)],'Item inserted',(600,725))
edge('ready','inspect','BL',[(1790,654),(1200,654),(1200,715)],dashed=True)
edge('inspect','accepted')
edge('accepted','sort','LT',[(1265,850)],'Yes',(1295,824))
edge('accepted','reject','RT',[(1565,850)],'No',(1520,824))
edge('sort','more','BR',[(1265,1050),(1080,1050),(1080,1100)],'Item result',(760,1080))
edge('reject','more','BR',[(1565,1050),(1080,1050),(1080,1100)])
edge('more','insert','LL',[(72,1100),(72,715)],'Yes',(97,925))
edge('more','green',text='No',at=(267,1190))
edge('green','earned','RL',text='Finish batch',at=(800,1226))
edge('earned','noreward','RL',text='No',at=(1550,1222))
edge('earned','rewardqr',text='Yes',at=(1428,1335))
ret('noreward','noreward_u','U',1690,1350)
edge('rewardqr','scanreward','LB',[(420,1390),(420,1515),(240,1515)])
edge('scanreward','claim','RL',[(1080,1460),(1080,1540)],'Claim request',(850,1436))
edge('claim','credit',text='Yes',at=(1428,1630))
edge('claim','claimerror','RT',[(1685,1540)],'No',(1604,1517))
edge('credit','recyclingresult','BL',[(1400,1740),(95,1740),(95,1830)],'Reward result',(680,1718))
ret('recyclingresult','reward_u','U',240,1930)
ret('claimerror','claimerror_u','U',1685,1870)
ret('credit','credit_m','M',1400,1820)

# Refill QR, water selection and optional point purchase.
node('refillqr','Create refill session\nand display QR',2150,690,295,76)
node('scanrefill','Scan refill QR',895,810,245)
node('select','Select water amount',895,915,250)
decision('balance','Enough\npoints?',895,1035,205)
decision('buy','Buy points?',560,1035,210)
node('pay','Pay via GCash;\nsubmit reference',560,1150,240,76)
node('pending','Wait for owner review\nNo points credited yet',560,1330,270,76)
node('balanceupdated','View updated point balance',560,1620,290)
node('confirm','Place container;\nconfirm refill',895,1790,260,76)
node('refillresult','View refill / refund result',895,2470,300)
edge('blue','refillqr','RT',[(1080,690),(1080,635),(2150,635)],'Open refill mode',(2250,620))
edge('refillqr','scanrefill','BR',[(2150,770),(1080,770),(1080,810)],'Refill QR',(1725,748))
edge('scanrefill','select')
edge('select','balance')
edge('balance','buy','LR',text='No',at=(735,1010))
edge('buy','pay',text='Yes',at=(586,1102))
ret('buy','buycancel_u','U',382,1035,'LR')
label('No',416,1007,17)
edge('pay','pending')
edge('balance','confirm','RB',[(1050,1035),(1050,1860),(895,1860)],'Yes',(1010,1072))
edge('balanceupdated','confirm','BR',[(560,1720),(1060,1720),(1060,1790)])
ret('refillresult','refill_u','U',895,2580)

# Refill validation always follows explicit user confirmation.
node('validate','Validate session, amount,\nuser balance and availability',2150,1790,335,78)
decision('allowed','Refill\nallowed?',2150,1920,220)
node('denied','Show refill error;\nrescan if QR expired',1840,1920,250,76)
node('dispense','Reserve session; deduct points;\ndispense and monitor container',2150,2045,350,78)
decision('done','Dispensing\nsuccessful?',2150,2165,225)
node('complete','Save completed refill;\ncredit owner points',1990,2290,265,76)
node('failure','Stop pump; attempt refund;\nsave failure / refund status',2300,2290,280,76)
node('reset','Show result; reset session',2150,2470,295)
edge('confirm','validate','RL',text='Confirmed refill request',at=(1880,1763))
edge('validate','allowed')
edge('allowed','denied','LR',text='No',at=(1994,1896))
ret('denied','denied_u','U',1840,2027)
edge('allowed','dispense',text='Yes',at=(2180,1994))
edge('dispense','done')
edge('done','complete','LT',[(1990,2165)],'Yes',(2028,2139))
edge('done','failure','RT',[(2300,2165)],'No',(2274,2139))
edge('complete','reset','BT',[(1990,2405),(2150,2405)])
edge('failure','reset','BT',[(2300,2405),(2150,2405)])
edge('reset','refillresult','RL',text='Actual result',at=(1460,2444))
ret('reset','reset_m','M',2150,2580)

# Owner choices use the same branch layout as the reference.
for k,t,x in [('monitor','Monitoring',2610),('alerts','Alerts',2860),('collection','Collection',3105),('payments','Payment review',3395)]:
    node(k,t,x,655,210)
    edge('ochoose',k,'BT',[(3000,594),(x,594)])
connector('ownerlogoutentry','OL',3510,530)
edge('ochoose','ownerlogoutentry','RL',text='Log out',at=(3300,506))
node('levels','View water and\nstorage levels',2610,785,220,76)
node('quality','View water quality\nand machine status',2610,915,220,76)
node('counts','View bottle/can counts;\naccepted / rejected items',2610,1045,235,76)
node('history','View recycling, refill\nand purchase records',2610,1175,230,76)
for a,b in [('monitor','levels'),('levels','quality'),('quality','counts'),('counts','history')]: edge(a,b)
ret('history','monitor_o','O',2610,1285)
node('alertdetails','Receive alerts;\nreview details',2860,785,215,76)
node('action','Take action',2860,915,210)
edge('alerts','alertdetails'); edge('alertdetails','action')
ret('action','alerts_o','O',2860,1030)
node('collect','Collect stored\nbottles and cans',3105,785,210,76)
edge('collection','collect')
ret('collect','collection_o','O',3105,915)
node('review','Open pending purchases;\nverify payment received',3395,1150,280,76)
edge('payments','review')
decision('verified','Payment verified;\nowner points sufficient?',3290,1320,300)
edge('review','verified','BL',[(3395,1222),(3080,1222),(3080,1320)])
node('approve','Approve payment;\nrequest point transfer',3100,1460,270,76)
node('notapproved','Reject with reason\nor leave pending',3420,1460,245,76)
edge('verified','approve','LT',[(3100,1320)],'Yes',(3130,1287))
edge('verified','notapproved','RT',[(3480,1320),(3480,1400),(3420,1400)],'No',(3494,1342))
edge('pay','review','RL',[(720,1150),(720,1110),(3230,1110),(3230,1150)],'Pending purchase',(1880,1088),True)
node('transfer','Validate and transfer\nowner points to user',1890,1470,265,76)
decision('transferred','Transfer\nsuccessful?',1890,1600,210)
edge('approve','transfer','LT',[(2920,1460),(2920,1395),(1890,1395)],'Approval',(2450,1371),True)
edge('transfer','transferred')
edge('transferred','balanceupdated','LR',[(1750,1600),(1750,1620)],'Yes: updated balance',(970,1598))
node('transferfail','Show purchase error;\nno refill started',2200,1600,255,76)
edge('transferred','transferfail','RL',text='No',at=(2030,1574))
ret('transferfail','transferfail_u','U',2350,1685,'BR',[(2200,1685)])
ret('approve','approve_o','O',3100,1580)
node('paymentstatus','Notify user of status;\nno points transferred',3420,1610,255,76)
edge('notapproved','paymentstatus')
ret('paymentstatus','paymentstatus_u','U',3420,1730)
ret('notapproved','notapproved_o','O',3260,1730,'BL',[(3420,1520),(3230,1520),(3230,1730)])

# Monitoring is a data feed, not part of the user's control sequence.
node('records','Sync machine readings,\nactivity records and alerts',1500,2180,365,90)
label('Monitoring data is supplied independently\nof the user or owner app session.',1500,2290,17)
edge('credit','records','LL',[(1210,1690),(1210,2180)],dashed=True)
edge('complete','records','BL',[(1990,2370),(1160,2370),(1160,2180)],dashed=True)
edge('records','levels','RT',[(1720,2180),(1720,2348),(2442,2348),(2442,724),(2610,724)],'Machine readings',(2360,744),True)
edge('records','history','RT',[(1740,2180),(1740,2388),(2450,2388),(2450,1105),(2610,1105)],'Saved records',(2390,1080),True)
edge('records','alertdetails','RT',[(1760,2180),(1760,2368),(2458,2368),(2458,706),(2860,706)],'Alerts',(2770,681),True)

# Logout is always a separate action, never a required step after a refill.
connector('ulogouttarget','L',560,2300)
node('ulogout','Log out of app',560,2410,240)
node('uend','',560,2530,32,32,'end')
edge('ulogouttarget','ulogout'); edge('ulogout','uend')
connector('ologouttarget','OL',3000,2300)
node('ologout','Log out of app',3000,2410,240)
node('oend','',3000,2530,32,32,'end')
edge('ologouttarget','ologout'); edge('ologout','oend')
label('Owner decisions and payment reviews\nrequire a signed-in owner account.',3020,2010,18)
label('Water, storage and quality indicators\nrequire supplied sensor data.',3020,2100,18)

# Render in a plain UML style, with white gaps at line crossings.
fig, ax = plt.subplots(figsize=(36,27), dpi=100)
fig.subplots_adjust(0,0,1,1)
ax.set_xlim(0,W); ax.set_ylim(H,0); ax.set_aspect('equal'); ax.axis('off')
fig.patch.set_facecolor('white')
for left,right,title in [(30,1120,'User / EcoRefill App'),(1120,2460,'EcoRefill Machine'),(2460,3570,'Device Owner / EcoRefill App')]:
    ax.add_patch(Rectangle((left,30),right-left,2600,fill=False,lw=1.4,edgecolor='#555',zorder=0))
    ax.plot([left,right],[100,100],color='#555',lw=1.2,zorder=0)
    ax.text((left+right)/2,65,title,ha='center',va='center',fontsize=20,fontweight='bold',family='DejaVu Sans')

def port(n,s):
    return dict(T=(n['x'],n['y']-n['h']/2),B=(n['x'],n['y']+n['h']/2),L=(n['x']-n['w']/2,n['y']),R=(n['x']+n['w']/2,n['y']))[s]

for e in edges:
    pts=[port(nodes[e['a']],e['ports'][0]),*e['via'],port(nodes[e['b']],e['ports'][1])]
    path=MPath(pts,[MPath.MOVETO]+[MPath.LINETO]*(len(pts)-1))
    arrow=FancyArrowPatch(path=path,arrowstyle='-|>',mutation_scale=12,lw=1.15,
                          color='#555' if e['dashed'] else '#111',
                          linestyle=(0,(4,4)) if e['dashed'] else '-',zorder=2)
    arrow.set_path_effects([pe.Stroke(linewidth=3.8,foreground='white'),pe.Normal()])
    ax.add_patch(arrow)
    if e['text'] and e['at']:
        ax.text(*e['at'],e['text'],ha='center',va='center',fontsize=12.2,color='#111',
                bbox=dict(facecolor='white',edgecolor='none',pad=1),zorder=6)

for n in nodes.values():
    x,y,w,h=n['x'],n['y'],n['w'],n['h']
    kw=dict(facecolor='white',edgecolor='#111',lw=1.25,zorder=4)
    if n['kind']=='decision': patch=Polygon([(x,y-h/2),(x+w/2,y),(x,y+h/2),(x-w/2,y)],**kw)
    elif n['kind'] in ('start','end','connector'):
        patch=Circle((x,y),w/2,**kw)
        if n['kind']=='start': patch.set_facecolor('#111')
    else: patch=Rectangle((x-w/2,y-h/2),w,h,**kw)
    ax.add_patch(patch)
    if n['kind']=='end': ax.add_patch(Circle((x,y),w/2-6,facecolor='#111',edgecolor='#111',zorder=5))
    if n['text']:
        ax.text(x,y,n['text'],ha='center',va='center',fontsize=n['fs']*.72,
                fontweight='bold' if n['kind']=='connector' else 'normal',zorder=5,linespacing=1.35)

for t,x,y,fs,bold in labels:
    ax.text(x,y,t,ha='center',va='center',fontsize=fs*.72,fontweight='bold' if bold else 'normal',
            bbox=dict(facecolor='white',edgecolor='none',pad=2),zorder=6)
ax.text(45,2660,'U = return to user dashboard     O = return to owner dashboard     M = machine ready     L / OL = logout continuation     Solid arrows: process     Dashed arrows: requests / data updates',
        ha='left',va='center',fontsize=13)
base=OUT/'ecorefill-connected-swimlane'
plt.rcParams['svg.fonttype']='none'
for ext in ['svg','pdf','png']:
    fig.savefig(base.with_suffix('.'+ext),dpi=140 if ext=='png' else 100,facecolor='white')
(OUT/'diagram-data.json').write_text(json.dumps(dict(width=W,height=H,nodes=nodes,edges=edges),indent=2))
print('Saved SVG, PDF and PNG:',base)
