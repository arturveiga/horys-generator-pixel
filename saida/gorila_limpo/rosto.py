from PIL import Image
P=['17131e','292431','413944','5b514e','776b62','a49482','d1c2ab','f2e5c4','456a2a','79ac38','9deb38']
K='0123456789G'
im=Image.open('saida/gorila_limpo/v1_1x.png')
def put(x0,y,s):
  for i,ch in enumerate(s):
    if ch!='.': im.putpixel((x0+i,y),tuple(int(P[K.index(ch)][j:j+2],16) for j in(0,2,4))+(255,))
# rosto (x a partir de 16)
put(16,6, "3666666653")
put(16,7, "0555555550")
put(16,8, "50GG030GG05")
put(16,9, "50000400004")
put(16,10,"5544040455")
put(16,11,"0770777707")
put(16,12,"0771111770")
put(16,13,".07111170.")
put(16,14,".0700007..")
# medalhão 7x7 centrado em x24,y22
for dy,s in enumerate([".00000.","0566650","0533360","0536360","0536660","0533336",".06666."]):
  put(21,19+dy,s)
im.save('saida/gorila_limpo/v2_1x.png')
z=8;b=im.resize((48*z,64*z),Image.NEAREST);bg=Image.new('RGBA',b.size,(90,90,100,255));bg.alpha_composite(b);bg.save('saida/gorila_limpo/v2_8x.png')
