import sys,numpy as np
from PIL import Image
S=sys.argv[1]
L=['..............kkkkkk', '.............kwwwwww', '............kwwbbbbb', '............kwbbbbbb', '............kbbbbbbb', '............kbkkkkbb', '............kbkgekbb', '........kkkkkbkkkkbs', '......kkllllkbbbbbks', '.....kllllllkkwkwkww', '....kllllmmmmkwkwkwk', '...kllmmmmmmmkwkkkkk', '..kllmmmmmmmmmkdddkk', '..klmmmmmmmmmmkmdddd', '.klmmmmmmmmmmdkmllll', '.klmmmmmmmmmmdkmllll', '.kmmmmmmmmmmddkmllmm', '.kdmmmmmmmmddkkmmmmm', '..kddmmmmmddk.kmmmmm', '..kmmmmmmmmdk.kmmmmm', '..kmmmmmmmmdk.kmmmmm', '..kmmmmmmmmdk.kmmmmm', '..kmmmmmmmmdk.kdmmmm', '..kdmmmmmmmdk.kkkkkk', '.kkddddddddkk.kuuuuu', 'kllllllllllldk.ktttty', 'klmmmmmmmmmmdk.kkkkky', 'klmmmmmmmmmmdk.kdmmm', 'kmmmmmmmmmmmdk.kdmmk', 'kmkmmmkmmmkmdk.kdmmk', 'kdkdddkdddkddk.kdmmk', '.kkkkkkkkkkkk..kdmmk', '..............kdmmk.', '.............kddmmk.', '............kdmmmmk.', '............kllmmmk.', '............kkkkkkk.']
L=[(r+'.'*20)[:20] for r in L]
P={'k':(42,31,45),'d':(76,28,72),'m':(112,52,108),'l':(150,88,140),'w':(240,204,184),'b':(200,156,160),'s':(160,108,136),
'g':(120,244,0),'e':(255,246,216),'u':(138,83,50),'t':(92,52,36),'y':(230,176,42)}
dark={'l':'m','m':'d','w':'b','b':'s'}
H=len(L);W=40;o=np.zeros((H,W,4),np.uint8)
for j,r in enumerate(L):
  full=r+r[::-1]
  for i,c in enumerate(full):
    if c=='.':continue
    if i>=20 and c in 'lm' : c=dark.get(c,c) if i>=24 else c
    o[j,i,:3]=P[c];o[j,i,3]=255
Image.fromarray(o).save(S+'/gor/v08.png')
bg=Image.new('RGBA',(W,H),(79,168,71,255));bg.alpha_composite(Image.fromarray(o));bg.resize((W*10,H*10),0).save(S+'/gor/v08_10x.png')
