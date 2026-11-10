from PIL import Image
g=Image.open('saida/gorila_limpo/g6_1x.png').convert('RGBA')
def vazio(): return Image.new('RGBA',(48,64))
def sobre(dst,src,x,y):
  for yy in range(src.height):
    for xx in range(src.width):
      p=src.getpixel((xx,yy))
      if p[3] and 0<=x+xx<48 and 0<=y+yy<64: dst.putpixel((x+xx,y+yy),p)
def mover(img,box,dx,dy):
  r=img.crop(box);img.paste((0,0,0,0),box);sobre(img,r,box[0]+dx,box[1]+dy)
topo=vazio();topo.paste(g.crop((0,0,48,29)),(0,0));topo.paste(g.crop((15,29,31,35)),(15,29))
bL=g.crop((0,29,12,52));bR=g.crop((36,29,48,52))   # braços aprovados (antebraço + punho)
# (bob, deslize x do tronco, dy braço E, dx braço E, dy braço D, dx braço D, pé livre)
cfg=[(0,-1,-3,1,0,0,None),(-1,0,-1,1,-1,0,(4,46,22,63)),
     (0,1,0,0,-3,-1,None),(-1,0,-1,0,-1,-1,(27,46,46,63))]
Q=[]
for i,(bob,sx,dyL,dxL,dyR,dxR,pe) in enumerate(cfg):
  r=Image.open(f'saida/gorila_limpo/andar_raw{i}.png').convert('RGBA')
  if pe: mover(r,pe,0,-3)
  # tira braços e tronco da imagem nova: fica só cintura, pernas e pés
  for y in range(0,50):
    for x in range(48):
      if y<29+bob or x<=14 or x>=33 or (y<35+bob and 15<=x<=30): r.putpixel((x,y),(0,0,0,0))
  f=r
  sobre(f,bL,0+dxL,29+bob+dyL)
  sobre(f,bR,36+dxR,29+bob+dyR)
  sobre(f,topo,sx,bob)
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
