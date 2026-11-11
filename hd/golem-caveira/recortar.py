"""Recorta a folha de partes em PNGs separados (fundo magenta -> transparente)."""
from PIL import Image
import numpy as np
from scipy import ndimage
im=np.array(Image.open("partes.png").convert("RGB")).astype(int)
r,g,b=im[...,0],im[...,1],im[...,2]
fundo=(r>170)&(b>170)&(g<120)
# franja: tons rosados misturados com o fundo
franja=(r-g>90)&(b-g>90)
obj=~(fundo|franja)
obj=ndimage.binary_opening(obj,iterations=1)
lab,n=ndimage.label(ndimage.binary_closing(obj,iterations=3))
out=[]
for i,sl in enumerate(ndimage.find_objects(lab),1):
  h=sl[0].stop-sl[0].start;w=sl[1].stop-sl[1].start
  if h*w<1500: continue
  m=(lab[sl]==i)&obj[sl]
  rgba=np.zeros((h,w,4),np.uint8);rgba[...,:3]=im[sl];rgba[...,3]=m*255
  out.append((sl[0].start,sl[1].start,w,h,rgba))
for k,(y,x,w,h,a) in enumerate(sorted(out)):
  Image.fromarray(a).save(f"partes/p{k:02d}.png");print(k,x,y,w,h)
