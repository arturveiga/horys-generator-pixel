import sys
from PIL import Image
P=['17131e','292431','413944','5b514e','776b62','a49482','d1c2ab','f2e5c4','456a2a','79ac38','9deb38']
K='0123456789G'
im=Image.open(sys.argv[1]);out=sys.argv[2]
def put(x0,y,s):
  for i,ch in enumerate(s):
    if ch!='.': im.putpixel((x0+i,y),tuple(int(P[K.index(ch)][j:j+2],16) for j in(0,2,4))+(255,))
# gola: placas limpas no lugar do xadrez
put(18,16,"66666666666")
put(18,17,"55555555555")
put(18,18,"44555555544")
put(18,19,"554");put(28,19,"45")
# abdômen: quatro massas
for dy,s in enumerate(["1222221222221","2333321333332","2222221222222","1111111111111","2333321333332","2222221222222"]):
  put(17,27+dy,s)
im.save(out+"_1x.png")
z=8;b=im.resize((48*z,64*z),Image.NEAREST);bg=Image.new('RGBA',b.size,(90,90,100,255));bg.alpha_composite(b);bg.save(out+"_8x.png")
# silhueta
s=Image.new('RGBA',im.size,(255,255,255,255));s.paste((0,0,0,255),mask=im.getchannel('A'));s.resize((48*z,64*z),Image.NEAREST).save(out+"_silhueta.png")
# peitoral lateral sem xadrez
for dy,s in enumerate(["665555","655554","555544","555443","554433","544333"]):
  put(15,19+dy,s)
im.save(out+"_1x.png");b=im.resize((48*z,64*z),Image.NEAREST);bg=Image.new('RGBA',b.size,(90,90,100,255));bg.alpha_composite(b);bg.save(out+"_8x.png")
