from PIL import Image
P=["17131E","292431","413944","5B514E","776B62","A49482","D1C2AB","F2E5C4","456A2A","79AC38","9DEB38"]
P=[tuple(int(h[i:i+2],16) for i in (0,2,4)) for h in P]
im=Image.open("gorila2.png").convert("RGB");W,H=im.size;px=im.load()
m=Image.new("L",im.size,0);mp=m.load()
for y in range(H):
  for x in range(W):
    r,g,b=px[x,y]
    if not(r>180 and b>180 and g<110): mp[x,y]=255
bb=m.getbbox();c=im.crop(bb);mc=m.crop(bb)
w,h=48,64
# encaixa o personagem em 48x64 mantendo proporção, colado embaixo
s=min(w/c.width,h/c.height);sw,sh=round(c.width*s),round(c.height*s)
base=Image.new("RGB",c.size);base.paste(c,mask=mc)
soma=base.resize((sw,sh),Image.BOX).load();cob=mc.resize((sw,sh),Image.BOX).load()
ox,oy=(w-sw)//2,h-sh
def perto(col):
  return min(range(len(P)),key=lambda i:sum((a-b)**2 for a,b in zip(col,P[i])))
# moda por bloco: cada pixel da fonte vai para a paleta, o bloco fica com a cor mais votada
pal=Image.new("P",(1,1));pal.putpalette(sum(P,())+(0,)*(768-33))
ci=c.quantize(palette=pal,dither=Image.Dither.NONE).load();ma=mc.load()
g=[[-1]*w for _ in range(h)]
for y in range(sh):
  for x in range(sw):
    x0,x1=int(x/s),int((x+1)/s);y0,y1=int(y/s),int((y+1)/s)
    v={};t=0
    for yy in range(y0,min(y1,c.height)):
      for xx in range(x0,min(x1,c.width)):
        if ma[xx,yy]>128: v[ci[xx,yy]]=v.get(ci[xx,yy],0)+1
        else: t+=1
    if v and sum(v.values())>=t:
      # contorno (0) só vence com folga, senão engole as placas
      if max(v,key=v.get)==0 and len(v)>1 and v[0]<0.0*sum(v.values()):
        del v[0]
      g[y+oy][x+ox]=max(v,key=v.get)
# limpeza: pixel órfão vira a cor mais comum dos 8 vizinhos (2 passes)
for _ in range(2):
  n=[r[:] for r in g]
  for y in range(h):
    for x in range(w):
      if g[y][x]<0: continue
      viz=[g[y+dy][x+dx] for dy in(-1,0,1) for dx in(-1,0,1) if (dx or dy) and 0<=y+dy<h and 0<=x+dx<w]
      if viz.count(g[y][x])==0:
        op=[v for v in viz if v>=0]
        if op: n[y][x]=max(set(op),key=op.count)
  g=n
# contorno externo de 1px: borda do sólido vira preto roxo
n=[r[:] for r in g]
for y in range(h):
  for x in range(w):
    if g[y][x]<0: continue
    for dx,dy in((1,0),(-1,0),(0,1),(0,-1)):
      xx,yy=x+dx,y+dy
      if not(0<=xx<w and 0<=yy<h) or g[yy][xx]<0: n[y][x]=0;break
g=n
out=Image.new("RGBA",(w,h))
for y in range(h):
  for x in range(w):
    if g[y][x]>=0: out.putpixel((x,y),P[g[y][x]]+(255,))
out.save("saida/gorila_limpo/g2_1x.png")
z=8;big=out.resize((w*z,h*z),Image.NEAREST);bg=Image.new("RGBA",big.size,(90,90,100,255));bg.alpha_composite(big);bg.save("saida/gorila_limpo/g2_8x.png")
print(sw,sh)
