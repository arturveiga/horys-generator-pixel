from PIL import Image
P=["17131E","292431","413944","5B514E","776B62","A49482","D1C2AB","F2E5C4","456A2A","79AC38","9DEB38"]
P=[tuple(int(h[i:i+2],16) for i in (0,2,4)) for h in P]
im=Image.open("gorila_andar.png").convert("RGB");W,H=im.size;px=im.load()
m=Image.new("L",im.size,0);mp=m.load()
for y in range(H):
  for x in range(W):
    r,g,b=px[x,y]
    if not(r>170 and b>170 and g<120): mp[x,y]=255
# separa quadros por colunas vazias
col=[any(mp[x,y] for y in range(0,H,2)) for x in range(W)]
seg=[];x=0
while x<W:
  if col[x]:
    s=x
    while x<W and col[x]: x+=1
    if x-s>100: seg.append((s,x))
  x+=1
print(seg)
boxes=[]
for s,e in seg:
  bb=m.crop((s,0,e,H)).getbbox();boxes.append((s+bb[0],bb[1],s+bb[2],bb[3]))
print(boxes)
# escala comum: maior altura -> 63 linhas
alt=max(b[3]-b[1] for b in boxes);esc=63/alt
pal=Image.new("P",(1,1));pal.putpalette(sum(P,())+(0,)*(768-33))
ci=im.quantize(palette=pal,dither=Image.Dither.NONE).load()
chao=max(b[3] for b in boxes)
Q=[]
for (x0,y0,x1,y1) in boxes:
  cx=(x0+x1)/2
  w,h=48,64
  q=Image.new("RGBA",(w,h))
  for gy in range(h):
    for gx in range(w):
      # pixel (gx,gy) cobre a região da fonte; chão alinhado em gy=62
      sx0=cx+(gx-24)/esc; sy0=chao-(63-gy)/esc
      v={};t=0
      for yy in range(int(sy0),int(sy0+1/esc)):
        for xx in range(int(sx0),int(sx0+1/esc)):
          if 0<=xx<W and 0<=yy<H and x0-5<=xx<=x1+5 and mp[xx,yy]: v[ci[xx,yy]]=v.get(ci[xx,yy],0)+1
          else: t+=1
      if v and sum(v.values())>=t: q.putpixel((gx,gy),P[max(v,key=v.get)]+(255,))
  Q.append(q)
for i,q in enumerate(Q): q.save(f"saida/gorila_limpo/andar_raw{i}.png")
z=6;st=Image.new('RGBA',(4*(48*z+10),64*z),(90,90,100,255))
for i,q in enumerate(Q): st.alpha_composite(q.resize((48*z,64*z),Image.NEAREST),(i*(48*z+10),0))
st.save("saida/gorila_limpo/andar_raw.png")
