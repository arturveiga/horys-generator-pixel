from PIL import Image
P=['17131e','292431','413944','5b514e','776b62','a49482','d1c2ab','f2e5c4','456a2a','79ac38','9deb38']
K='0123456789G';C=lambda k:tuple(int(P[K.index(k)][j:j+2],16) for j in(0,2,4))+(255,)
im=Image.open('saida/gorila_limpo/g4_1x.png');W,H=im.size
def put(x0,y,s):
  for i,ch in enumerate(s):
    if ch!='.': im.putpixel((x0+i,y),C(ch))
def get(x,y):
  p=im.getpixel((x,y));return None if p[3]==0 else K[P.index('%02x%02x%02x'%p[:3])]
# espiral quadrada contínua
for dy,s in enumerate(["666666666","633333333","666666663","633333363","636663363","633333333"]):
  put(18,19+dy,s)
# facetas: fronteira luz/base desce em degraus para fora
for x in range(4,18):
  yb=19+(17-x)//3
  for y in range(17,23):
    if get(x,y) in('5','6'): put(x,y,'6' if y<yb else '5')
for x in range(28,45):
  yb=19+(x-28)//3
  for y in range(17,23):
    if get(x,y) in('5','6'): put(x,y,'6' if y<yb else '5')
# abdômen 2x2: separador horizontal mais claro, vertical escuro
for dy,s in enumerate(["22222022220","22222022220","11111011110","11111011110","22222022220","11111011110"]):
  put(15,29+dy,s)
put(15,31,"22222022220");put(15,32,"11111011110")
im.save('saida/gorila_limpo/g5_1x.png')
z=8;b=im.resize((W*z,H*z),Image.NEAREST);bg=Image.new('RGBA',b.size,(90,90,100,255));bg.alpha_composite(b);bg.save('saida/gorila_limpo/g5_8x.png')
s=Image.new('RGBA',im.size,(255,255,255,255));s.paste((0,0,0,255),mask=im.getchannel('A'));s.resize(b.size,Image.NEAREST).save('saida/gorila_limpo/g5_silhueta.png')
a=Image.open('gorila2.png').convert('RGBA').resize((377,504));c=Image.new('RGBA',(377+394,504),(90,90,100,255));c.paste(a,(0,0));c.alpha_composite(bg.resize((384,504),0),(387,0));c.save('saida/gorila_limpo/g5_lado.png')
