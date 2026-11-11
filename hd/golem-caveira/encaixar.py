"""Acha posição, escala e rotação de cada parte sobre montado.png (SSD com máscara, via FFT)."""
import json, numpy as np
from PIL import Image
from scipy.signal import fftconvolve
F=4
M=Image.open("montado.png").convert("RGB")
I=np.array(M.resize((M.width//F,M.height//F),Image.BOX)).astype(float)/255
nomes=["cabeca","tronco","quadril","braco_cima_E","braco_cima_D","antebraco_E","antebraco_D","coxa_E","coxa_D","canela_E","canela_D"]
res={}
for n in nomes:
  P=Image.open(f"partes/{n}.png")
  melhor=None
  angs=[0] if n in("cabeca","tronco","quadril") else range(-25,26,5)
  for s in (0.9,0.95,1.0,1.05,1.1,1.15):
    for a in angs:
      q=P.rotate(a,expand=True,resample=Image.BICUBIC)
      q=q.resize((max(1,round(q.width*s/F)),max(1,round(q.height*s/F))),Image.BOX)
      T=np.array(q).astype(float)/255;m=(T[...,3]>0.5).astype(float);T=T[...,:3]
      ssd=0
      for c in range(3):
        ssd=ssd+fftconvolve(I[...,c]**2,m[::-1,::-1],"valid")-2*fftconvolve(I[...,c],(m*T[...,c])[::-1,::-1],"valid")+(m*T[...,c]**2).sum()
      ssd/=m.sum()
      y,x=np.unravel_index(ssd.argmin(),ssd.shape)
      if melhor is None or ssd[y,x]<melhor[0]:
        melhor=(float(ssd[y,x]),s,a,(x+q.width/2)*F,(y+q.height/2)*F)
  res[n]=dict(erro=round(melhor[0],4),escala=melhor[1],angulo=melhor[2],cx=round(melhor[3]),cy=round(melhor[4]))
  print(n,res[n])
json.dump(res,open("encaixe.json","w"),indent=1)
# prévia: partes sobre o montado esmaecido
base=M.convert("RGBA");base=Image.blend(base,Image.new("RGBA",base.size,(255,255,255,255)),0.6)
ordem=["coxa_E","coxa_D","canela_E","canela_D","quadril","braco_cima_E","braco_cima_D","antebraco_E","antebraco_D","tronco","cabeca"]
for n in ordem:
  r=res[n];P=Image.open(f"partes/{n}.png").rotate(r["angulo"],expand=True,resample=Image.BICUBIC)
  P=P.resize((round(P.width*r["escala"]),round(P.height*r["escala"])),Image.LANCZOS)
  base.alpha_composite(P,(r["cx"]-P.width//2,r["cy"]-P.height//2))
base.save("encaixe_previa.png")
