from PIL import Image
P=['17131e','292431','413944','5b514e','776b62','a49482','d1c2ab','f2e5c4','456a2a','79ac38','9deb38']
K='0123456789G';C=lambda k:tuple(int(P[K.index(k)][j:j+2],16) for j in(0,2,4))+(255,)
im=Image.open('saida/gorila_limpo/g5_1x.png');W,H=im.size
def put(x0,y,s):
  for i,ch in enumerate(s):
    if ch=='x': im.putpixel((x0+i,y),(0,0,0,0))
    elif ch!='.': im.putpixel((x0+i,y),C(ch))
# punhos: 3 dedos, brilho no nó, pontas redondas, dedo do meio mais longo
F=["055505550550",
   "044404440440",
   "044404440440",
   "044404440440",
   "033303330330",
   "x0300333030x",
   "xx0x033300xx",
   "xxxxx000xxxx"]
for dy,s in enumerate(F):
  put(0,44+dy,s); put(36,44+dy,s[::-1])
# abdômen: topo de cada massa em 413944, resto 292431
for dy,c in enumerate("211211"):
  put(15,29+dy,c*5+"0"+c*4+"0")
im.save('saida/gorila_limpo/g6_1x.png')
z=8;b=im.resize((W*z,H*z),Image.NEAREST);bg=Image.new('RGBA',b.size,(90,90,100,255));bg.alpha_composite(b);bg.save('saida/gorila_limpo/g6_8x.png')
s=Image.new('RGBA',im.size,(255,255,255,255));s.paste((0,0,0,255),mask=im.getchannel('A'));s.resize(b.size,Image.NEAREST).save('saida/gorila_limpo/g6_silhueta.png')
a=Image.open('gorila2.png').convert('RGBA').resize((377,504));c=Image.new('RGBA',(377+394,504),(90,90,100,255));c.paste(a,(0,0));c.alpha_composite(bg.resize((384,504),0),(387,0));c.save('saida/gorila_limpo/g6_lado.png')
