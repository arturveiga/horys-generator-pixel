from PIL import Image
b=Image.open('saida/gorila_limpo/g6_1x.png').convert('RGBA');W,H=b.size
def quadro(dc,db):
  # dc: desce cabeça+tronco (y<=34, x15-30); db: desce braços (y<=51, fora do tronco)
  f=b.copy()
  if dc:
    reg=b.crop((15,0,31,35));f.paste((0,0,0,0),(15,0,31,dc));f.paste(reg,(15,dc),reg)
    # ombros/peito largo junto (y<=28)
    reg2=b.crop((0,0,W,29))
    lim=Image.new('RGBA',(W,29+dc));lim.paste(reg2,(0,dc))
    f.paste((0,0,0,0),(0,0,W,dc));
    for y in range(29+dc):
      for x in range(W):
        p=lim.getpixel((x,y))
        if p[3] or y<dc: f.putpixel((x,y),p)
  if db:
    for x0,x1 in((0,15),(31,W)):
      reg=f.crop((x0,30,x1,52));f.paste(reg,(x0,30+db),reg)
  return f
Q=[quadro(0,0),quadro(1,0),quadro(1,1),quadro(0,1)]
z=6;big=[]
for q in Q:
  bg=Image.new('RGBA',(W*z,H*z),(90,90,100,255));bg.alpha_composite(q.resize((W*z,H*z),Image.NEAREST));big.append(bg.convert('P',palette=Image.ADAPTIVE))
big[0].save('saida/gorila_limpo/idle.gif',save_all=True,append_images=big[1:],duration=[260,180,260,180],loop=0)
sh=Image.new('RGBA',(W*4,H));[sh.paste(q,(i*W,0)) for i,q in enumerate(Q)];sh.save('saida/gorila_limpo/idle_sheet.png')
st=Image.new('RGBA',(W*4*z+30,H*z),(90,90,100,255))
for i,q in enumerate(Q): st.alpha_composite(q.resize((W*z,H*z),Image.NEAREST),(i*(W*z+10),0))
st.save('saida/gorila_limpo/idle_quadros.png')
