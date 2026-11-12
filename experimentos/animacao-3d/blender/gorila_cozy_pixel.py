"""Pós do render do gorila cozy: paleta travada, contorno 1 px, limpeza, folha + GIF por ação/direção.
    python -I gorila_cozy_pixel.py <pasta anim>   (lê <pasta>/bruto/<acao>_<dir>/NNNN.png)"""
import os,sys,numpy as np
from PIL import Image
from collections import Counter
base=sys.argv[1]
PAL=["#4c1c48","#70346c","#96588c","#a06c88","#c89ca0","#f0ccb8","#5c3424","#8a5332","#a06a18","#e6b02a","#78f400","#2a1f2d"]
C=np.array([[int(h[i:i+2],16) for i in (1,3,5)] for h in PAL]);K=C[-1]
def proc(im):
  a=np.pad(np.array(im.convert('RGBA')).astype(int),((2,2),(2,2),(0,0))); m=a[...,3]>127
  d=((a[...,None,:3]-C[None,None])**2).sum(-1); o=np.zeros(a.shape,np.uint8)
  o[...,:3]=C[d.argmin(-1)]; o[...,3]=np.where(m,255,0)
  H,W=m.shape
  for _ in range(1):
    n=o.copy()
    for y in range(1,H-1):
      for x in range(1,W-1):
        if not m[y,x]: continue
        c=tuple(o[y,x,:3]); nb=[tuple(o[yy,xx,:3]) for yy,xx in ((y-1,x),(y+1,x),(y,x-1),(y,x+1)) if m[yy,xx]]
        if nb and c not in nb and c!=tuple(C[10]): n[y,x,:3]=Counter(nb).most_common(1)[0][0]
    o=n
  # contorno por fora (1 px)
  mm=m.copy(); ring=np.zeros_like(m)
  for dy,dx in ((1,0),(-1,0),(0,1),(0,-1)): ring|=np.roll(mm,(dy,dx),(0,1))
  ring&=~mm; o[ring,:3]=K; o[ring,3]=255
  return o
dirs={'s':'s','e':'e','n':'n'}
saida=os.path.join(base,'final'); os.makedirs(saida,exist_ok=True)
todas={}
for nome in sorted(os.listdir(os.path.join(base,'bruto'))):
  p=os.path.join(base,'bruto',nome)
  if not os.path.isdir(p): continue
  todas[nome]=[proc(Image.open(os.path.join(p,f))) for f in sorted(os.listdir(p))]
for nome in list(todas):
  if nome.endswith('_e'): todas[nome[:-2]+'_w']=[f[:,::-1].copy() for f in todas[nome]]
al=np.zeros(todas[next(iter(todas))][0].shape[:2],bool)
for fr in todas.values():
  for f in fr: al|=f[...,3]>0
ys,xs=np.where(al); y0,y1,x0,x1=ys.min(),ys.max()+1,xs.min(),xs.max()+1
for nome,fr in todas.items():
  fr=[f[y0:y1,x0:x1] for f in fr]; h,w=fr[0].shape[:2]
  folha=Image.new('RGBA',(w*len(fr),h))
  for i,f in enumerate(fr): folha.paste(Image.fromarray(f),(i*w,0))
  folha.save(os.path.join(saida,f'{nome}.png'))
  g=[]
  for f in fr:
    bg=Image.new('RGBA',(w,h),(79,168,71,255)); bg.alpha_composite(Image.fromarray(f)); g.append(bg.resize((w*6,h*6),0).convert('P',palette=Image.ADAPTIVE))
  g[0].save(os.path.join(saida,f'{nome}_6x.gif'),save_all=True,append_images=g[1:],duration=125,loop=0)
print(w,h,sorted(todas))
