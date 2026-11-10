from PIL import Image
g=Image.open('saida/gorila_limpo/g6_1x.png').convert('RGBA')
corte=29  # linhas 0..28 = cabeça, ombros e peito
topo=g.crop((0,0,48,corte))
Q=[]
for i,dy in enumerate([0,-1,0,-1]):
  r=Image.open(f'saida/gorila_limpo/andar_raw{i}.png').convert('RGBA')
  f=Image.new('RGBA',(48,64))
  # baixo: do quadro novo, abaixo do corte
  f.paste(r.crop((0,corte+dy,48,64)),(0,corte+dy))
  f.alpha_composite(topo,(0,max(dy,0)) if dy>=0 else (0,0)) if dy>=0 else None
  if dy<0:
    t=Image.new('RGBA',(48,corte));t.paste(topo.crop((0,1,48,corte)),(0,0));
    # passa 1 px mais alto: recorta a primeira linha e cola em y=0
    f.alpha_composite(topo.crop((0,0,48,corte)),(0,0)) if False else None
    tmp=Image.new('RGBA',(48,64));tmp.paste(topo,(0,dy+1-1+0));
    f.alpha_composite(Image.new('RGBA',(48,64)),(0,0))
    for y in range(corte):
      for x in range(48):
        p=topo.getpixel((x,y))
        if p[3] and y+dy>=0: f.putpixel((x,y+dy),p)
  Q.append(f)
for i,q in enumerate(Q): q.save(f'saida/gorila_limpo/andar{i}.png')
z=6;st=Image.new('RGBA',(4*(48*z+10),64*z),(90,90,100,255))
for i,q in enumerate(Q): st.alpha_composite(q.resize((48*z,64*z),Image.NEAREST),(i*(48*z+10),0))
st.save('saida/gorila_limpo/andar_quadros.png')
big=[]
for q in Q:
  bg=Image.new('RGBA',(48*z,64*z),(90,90,100,255));bg.alpha_composite(q.resize((48*z,64*z),Image.NEAREST));big.append(bg.convert('P',palette=Image.ADAPTIVE))
big[0].save('saida/gorila_limpo/andar.gif',save_all=True,append_images=big[1:],duration=200,loop=0)
sh=Image.new('RGBA',(192,64));[sh.paste(q,(i*48,0)) for i,q in enumerate(Q)];sh.save('saida/gorila_limpo/andar_sheet.png')
