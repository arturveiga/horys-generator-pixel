from PIL import Image
P=['17131e','292431','413944','5b514e','776b62','a49482','d1c2ab','f2e5c4','456a2a','79ac38','9deb38']
K='0123456789G';C=lambda k:tuple(int(P[K.index(k)][j:j+2],16) for j in(0,2,4))+(255,)
im=Image.open('saida/gorila_limpo/g3_1x.png');W,H=im.size
def put(x0,y,s):
  for i,ch in enumerate(s):
    if ch!='.': im.putpixel((x0+i,y),C(ch))
def get(x,y):
  p=im.getpixel((x,y));return None if p[3]==0 else K[P.index('%02x%02x%02x'%p[:3])]
lim=[]
# 1) vãos braço-tronco de 3 px
for y in range(30,44):
  for x in (12,13,14,31,32,33):
    im.putpixel((x,y),(0,0,0,0));lim.append((x,y))
# contorno nas bordas novas
for x,y in lim:
  for dx in(-1,1):
    xx=x+dx
    if 0<=xx<W and get(xx,y) is not None: im.putpixel((xx,y),C('0'))
# 2) medalhão: quadrados concêntricos com miolo
for dy,s in enumerate(["633333336","636666636","636636636","636666636","633333336","666666666"]):
  put(18,19+dy,s)
# 3) facetas diagonais no peito (sombra embaixo, corte 1:2)
for y in range(21,25):
  for x in range(4,4+(y-20)*3):
    if get(x,y)=='6': put(x,y,'5')
for y in range(19,25):
  for x in range(42-(y-18)*2,43):
    if get(x,y)=='6': put(x,y,'5')
# 4) abdômen 2x2
for dy,s in enumerate(["22222022220","22222022220","11111011110","00000000000","22222022220","11111011110"]):
  put(15,29+dy,"0"+s[:-1] if False else s)
# 5) quinas dos punhos
for x,y in((0,49),(47,49),(0,48),(47,48)):
  im.putpixel((x,y),(0,0,0,0))
im.save('saida/gorila_limpo/g4_1x.png')
z=8;b=im.resize((W*z,H*z),Image.NEAREST);bg=Image.new('RGBA',b.size,(90,90,100,255));bg.alpha_composite(b);bg.save('saida/gorila_limpo/g4_8x.png')
s=Image.new('RGBA',im.size,(255,255,255,255));s.paste((0,0,0,255),mask=im.getchannel('A'));s.resize(b.size,Image.NEAREST).save('saida/gorila_limpo/g4_silhueta.png')
a=Image.open('gorila2.png').convert('RGBA').resize((377,504));c=Image.new('RGBA',(377+394,504),(90,90,100,255));c.paste(a,(0,0));c.alpha_composite(bg.resize((384,504),0),(387,0));c.save('saida/gorila_limpo/g4_lado.png')
