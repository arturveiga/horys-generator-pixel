import sys
from PIL import Image
P=['17131e','292431','413944','5b514e','776b62','a49482','d1c2ab','f2e5c4','456a2a','79ac38','9deb38']
K='0123456789G';im=Image.open(sys.argv[1])
print('   '+''.join(str(x//10) for x in range(48)));print('   '+''.join(str(x%10) for x in range(48)))
for y in range(64):
  print('%2d '%y+''.join('.' if im.getpixel((x,y))[3]==0 else K[P.index('%02x%02x%02x'%im.getpixel((x,y))[:3])] for x in range(48)))
