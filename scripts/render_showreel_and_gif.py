import json, math, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/media'
OUT.mkdir(parents=True, exist_ok=True)
DATA = json.loads((ROOT/'web/public/data/tectonic_showcase_v1.json').read_text(encoding='utf-8'))
ASSETS = ROOT/'web/public/assets'
FF = imageio_ffmpeg.get_ffmpeg_exe()
W,H = 1920,1080
FPS = 12

def font(size, bold=False):
    paths = ['C:/Windows/Fonts/msyhbd.ttc' if bold else 'C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf', 'C:/Windows/Fonts/arial.ttf']
    for p in paths:
        if Path(p).exists(): return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)
F = {n:font(n,n>=40) for n in (25,32,40,48,60,76,96)}
def label(d,xy,s,size=40,color='#f7f7f7'):
    d.text(xy,s,font=F[size],fill=color,stroke_width=0)
def image(path,box):
    im=Image.open(path).convert('RGB')
    return ImageOps.fit(im,(box[2],box[3]),method=Image.Resampling.LANCZOS)
def ease(x): return max(0,min(1,x))**2*(3-2*max(0,min(1,x)))
cache={}
def get(path,box):
    key=(str(path),box[2],box[3])
    if key not in cache: cache[key]=image(path,box)
    return cache[key]
def paste(im,path,box): im.paste(get(path,box),(box[0],box[1]))
def wipe(im,a,b,box,p):
    paste(im,a,box); right=get(b,box); k=int(box[2]*ease(p)); im.paste(right.crop((0,0,k,box[3])),(box[0],box[1])); d=ImageDraw.Draw(im); x=box[0]+k; d.line((x,box[1],x,box[1]+box[3]),fill='#ffffff',width=5)
def seam(im,case,idx,box,progress):
    d=ImageDraw.Draw(im); segs=case['tiers'][idx]['homography_projection']['seam_segments']
    for s in segs[:int(len(segs)*ease(progress))]:
        a,b=s['start'],s['end']; d.line((box[0]+a['x']*box[2]/800,box[1]+a['y']*box[3]/600,box[0]+b['x']*box[2]/800,box[1]+b['y']*box[3]/600), fill='#72e9ff',width=3)
def ast(i,kind): return ASSETS/'ast_comparisons'/f'cmp_{i:02}_{kind}.webp'
def case_img(c,i): return ROOT/'web/public'/c['tiers'][i]['image_url'].lstrip('/')
curated=sorted((ASSETS/'curated_80').glob('*.webp'))

def frame(t):
    im=Image.new('RGB',(W,H),'#080b11'); d=ImageDraw.Draw(im)
    d.rectangle((0,0,18,H),fill='#58dbe9')
    label(d,(75,40),'SPATIAL AI  /  DUAL ENGINE',25,'#8ba2b4')
    d.line((75,88,1845,88),fill='#263440',width=2)
    if t<12:
        label(d,(80,125),'灵感串色，预算失控。',76)
        label(d,(80,230),'PROMPT LEAKAGE  /  BUDGET PRESSURE',32,'#74e3ee')
        box=(850,320,880,580); wipe(im,ast(1,'naive'),ast(1,'ast'),box,(t%6)/6)
        d=ImageDraw.Draw(im); label(d,(85,395),'¥18.6万',76); label(d,(85,505),'↓  预算情境',40,'#a6b9c4'); label(d,(85,575),'¥7.0万',96,'#75e6ee')
        label(d,(85,745),'多图混合如何保留各自的设计意图？',32); label(d,(85,805),'效果图如何连接构造与成本？',32)
        label(d,(85,985),'预算数字为演示情境；案例测算见后文',25,'#abb9c3')
    elif t<45:
        u=t-12; label(d,(80,120),'01  AetherVault  [0 → 1]',60)
        label(d,(80,205),'跨域美学，从灵感混合到作用域隔离',40,'#8ce8f0')
        if u<10:
            for n in range(20):
                idx=(n+int(u*3))%len(curated); x=80+(n%10)*174; y=300+(n//10)*174
                paste(im,curated[idx],(x,y,158,158))
            d=ImageDraw.Draw(im); label(d,(80,690),'80 SPECIMENS  /  5 DOMAINS',48)
            for n in range(8):
                x=82+n*216; d.rectangle((x,795,x+160,805),fill='#273943'); d.rectangle((x,795,x+int(160*(0.2+0.8*ease((u-n*.35)/5))),805),fill='#71e8f1')
            label(d,(80,850),'8 轴光谱  ×  5 点黄金锚点',40)
        else:
            i=min(3,1+int((u-10)/7.7)); local=(u-10)%7.7; box=(650,290,1080,640)
            wipe(im,ast(i,'naive'),ast(i,'ast'),box,(math.sin(local*.7)+1)/2)
            d=ImageDraw.Draw(im); label(d,(80,340),'Scoped',60); label(d,(80,420),'Prompt AST',60); label(d,(80,545),'作用域隔离',40,'#8ce8f0'); label(d,(80,625),'20 组三槽任务',32); label(d,(80,680),'0 外来实体泄漏',40)
            label(d,(680,940),'SCOPED AST',25); label(d,(1390,940),'NAIVE MULTI-IMAGE',25)
        d=ImageDraw.Draw(im); label(d,(80,1000),'<20 ms 重排   /   ¥0.00596 每图   /   20 任务零实体泄漏',32,'#e6f7f9')
    elif t<80:
        u=t-45; label(d,(80,120),'02  TectonicLoop  [1 → N]',60)
        label(d,(80,205),'从立面效果到可建造、可计价',40,'#8ce8f0')
        ci=0 if u<15 else (1 if u<25 else 2); c=DATA['cases'][ci]; local=u-(0 if ci==0 else 15 if ci==1 else 25)
        if ci==0: a,b=(0,1) if local<7.5 else (1,2); local=local%7.5
        else: a,b=0,2
        box=(650,285,1040,780); wipe(im,case_img(c,a),case_img(c,b),box,(math.sin(local*.7)+1)/2)
        seam(im,c,b,box,min(1,local/4)); d=ImageDraw.Draw(im)
        label(d,(80,325),f'CASE 0{ci+1}',48); label(d,(80,405),f'TIER {a} → {b}',48,'#8ce8f0')
        label(d,(80,520),'H / H^-1',60); label(d,(80,600),'平面拼缝投影',32)
        label(d,(80,710),'30 SKU × 8 规则',40); label(d,(80,785),'86.7%  /  13 of 15',40)
        label(d,(80,850),'±15% 历史结算回测',25)
        label(d,(80,915),'已知小计 ¥' + c['tiers'][a]['summary']['known_subtotal_cny'] + ' → ¥' + c['tiers'][b]['summary']['known_subtotal_cny'],25,'#8ce8f0')
        label(d,(80,995),'缺价阻断：UNKNOWN_PRICE_MISSING',25,'#f8d687')
    else:
        label(d,(80,150),'AI vs NON-AI',96); label(d,(80,265),'DISCIPLINE',96,'#78e4ed')
        label(d,(80,450),'AI 负责感知与生成。',48); label(d,(80,535),'几何、排序和算账交给确定性工具。',48)
        d.rectangle((80,700,1835,930),outline='#47626d',width=3)
        label(d,(120,740),'LIVE INSTANT SHOWCASE',32,'#84e7f0'); label(d,(120,800),'frostales-code.github.io/spatial-ai-portfolio',40)
        label(d,(120,870),'GITHUB  /  frostales-code/spatial-ai-portfolio',32)
    return im

def video():
    cmd=[FF,'-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-an','-vf','fps=24','-c:v','libx264','-preset','veryfast','-crf','25','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/'showreel_90s.mp4')]
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        for n in range(90*FPS):
            p.stdin.write(frame(n/FPS).tobytes())
            if n%120==0: print(f'render {n/FPS:.0f}s',flush=True)
    finally: p.stdin.close()
    if p.wait(): raise RuntimeError('video encoding failed')
def gif():
    # The same real comparison and facade material, re-cut for a seamless loop.
    tmp=OUT/'hero_source.mp4'
    cmd=[FF,'-y','-f','rawvideo','-pix_fmt','rgb24','-s','960x540','-r','8','-i','-','-an','-c:v','libx264','-preset','veryfast','-crf','26','-pix_fmt','yuv420p',str(tmp)]
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.DEVNULL)
    for n in range(96):
        t=22+(n/8)*1.8 if n<48 else 45+((n-48)/8)*2
        p.stdin.write(frame(t).resize((960,540),Image.Resampling.LANCZOS).tobytes())
    p.stdin.close()
    if p.wait(): raise RuntimeError('GIF source failed')
    filt='fps=8,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle'
    subprocess.run([FF,'-y','-i',str(tmp),'-filter_complex',filt,'-loop','0',str(OUT/'hero_showcase.gif')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    tmp.unlink()
if __name__=='__main__': video(); gif()
