from PIL import Image
P=['17131e','292431','413944','5b514e','776b62','a49482','d1c2ab','f2e5c4','456a2a','79ac38','9deb38']
K='0123456789G'
im=Image.open('saida/gorila_limpo/g2_1x.png')
def put(x0,y,s):
  for i,ch in enumerate(s):
    if ch!='.': im.putpixel((x0+i,y),tuple(int(P[K.index(ch)][j:j+2],16) for j in(0,2,4))+(255,))
put(18,10,"0.0")                      # narinas
for dy,s in enumerate(["666666666","663333366","636666666","636333366","636663366","663333366","666666666"]):
  put(18,19+dy,s)                     # medalhão em G
im.save('saida/gorila_limpo/g3_1x.png')
z=8;b=im.resize((48*z,63*z),Image.NEAREST);bg=Image.new('RGBA',b.size,(90,90,100,255));bg.alpha_composite(b);bg.save('saida/gorila_limpo/g3_8x.png')
s=Image.new('RGBA',im.size,(255,255,255,255));s.paste((0,0,0,255),mask=im.getchannel('A'));s.resize(b.size,Image.NEAREST).save('saida/gorila_limpo/g3_silhueta.png')
a=Image.open('gorila2.png').convert('RGBA').resize((377,504));c=Image.new('RGBA',(377+394,504),(90,90,100,255));c.paste(a,(0,0));c.alpha_composite(bg.resize((384,504),0),(387,0));c.save('saida/gorila_limpo/g3_lado.png')
