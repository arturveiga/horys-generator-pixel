from PIL import Image
g=Image.open('saida/gorila_limpo/g6_1x.png').convert('RGBA')
def vazio(): return Image.new('RGBA',(48,64))
# camada de cima: linhas 0-28 inteiras + abdômen (x15-30, y29-34)
topo=vazio();topo.paste(g.crop((0,0,48,29)),(0,0));topo.paste(g.crop((15,29,31,35)),(15,29))
punho=g.crop((0,44,12,52))   # punho esquerdo aprovado (12x8)
def sobre(dst,src,x,y):
  for yy in range(src.height):
    for xx in range(src.width):
      p=src.getpixel((xx,yy))
      if p[3] and 0<=x+xx<48 and 0<=y+yy<64: dst.putpixel((x+xx,y+yy),p)
def mover(img,box,dx,dy):
  r=img.crop(box);img.paste((0,0,0,0),box);sobre(img,r,box[0]+dx,box[1]+dy)
# lado = 'L' braço esquerdo da imagem à frente; pé livre nas passagens
cfg=[dict(bob=0,lado='L',pe=None),dict(bob=-1,lado=None,pe=(4,46,22,63)),
     dict(bob=0,lado='R',pe=None),dict(bob=-1,lado=None,pe=(27,46,46,63))]
Q=[]
for i,c in enumerate(cfg):
  r=Image.open(f'saida/gorila_limpo/andar_raw{i}.png').convert('RGBA')
  if c['pe']: mover(r,c['pe'],0,-3)       # ergue o pé livre 3 px
  f=vazio()
  # baixo do quadro novo, sem a área do tronco
  for y in range(64):
    for x in range(48):
      p=r.getpixel((x,y))
      if not p[3]: continue
      if y<29+c['bob']: continue
      if y<35+c['bob'] and 15<=x<=30: continue
      f.putpixel((x,y),p)
  # punhos: gramática do g6 colada na base de cada punho
  for x0,x1,flip in((0,13,False),(35,48,True)):
    base=max([y for y in range(30,49) for x in range(x0,x1) if f.getpixel((x,y))[3]],default=None)
    if base:
      pp=punho.transpose(Image.FLIP_LEFT_RIGHT) if flip else punho
      sobre(f,pp,x0 if not flip else 36,base-7)
  t=topo.copy()
  if c['lado']:
    mx=(0,0,24,29) if c['lado']=='L' else (24,0,48,29)
    mover(t,mx,0,1)                       # ombro do braço que avança desce
    mover(t,(15,0,32,14),-1 if c['lado']=='L' else 1,0)  # cabeça vai para o lado
  sobre(f,t,0,c['bob'])
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
