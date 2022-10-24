_E='(%s, %s, %s)'
_D=False
_C=0.0
_B=None
_A=1.0
__version__='0.0.0+auto.0'
__repo__='https://github.com/Adafruit/Adafruit_CircuitPython_FancyLED.git'
from math import floor
class CRGB:
    def __init__(self,red,green=_C,blue=_C):
        if isinstance(red,CHSV):
            hsv=red;hue=hsv.hue*6.0;sxt=floor(hue);frac=hue-sxt;sxt=int(sxt)%6
            if sxt==0:r,g,b=_A,frac,_C
            elif sxt==1:r,g,b=_A-frac,_A,_C
            elif sxt==2:r,g,b=_C,_A,frac
            elif sxt==3:r,g,b=_C,_A-frac,_A
            elif sxt==4:r,g,b=frac,_C,_A
            else:r,g,b=_A,_C,_A-frac
            invsat=_A-hsv.saturation;self.red=(r*hsv.saturation+invsat)*hsv.value;self.green=(g*hsv.saturation+invsat)*hsv.value;self.blue=(b*hsv.saturation+invsat)*hsv.value
        else:self.red=clamp_norm(red);self.green=clamp_norm(green);self.blue=clamp_norm(blue)
    def __repr__(self):return self.red,self.green,self.blue
    def __str__(self):return _E%(self.red,self.green,self.blue)
    def __len__(self):return 3
    def __getitem__(self,key):
        if key==0:return self.red
        if key==1:return self.green
        if key==2:return self.blue
        raise IndexError
    def pack(self,white=_B):
        if white:
            if isinstance(white,float):white=denormalize(white)
            else:white=clamp(white,0,255)
            return denormalize(self.red),denormalize(self.green),denormalize(self.blue),white
        return denormalize(self.red)<<16|denormalize(self.green)<<8|denormalize(self.blue)
class CHSV:
    def __init__(self,h,s=_A,v=_A):
        if isinstance(h,float):self.hue=h
        else:self.hue=float(h)/256.0
        self.saturation=clamp_norm(s);self.value=clamp_norm(v)
    def __repr__(self):return self.hue,self.saturation,self.value
    def __str__(self):return _E%(self.hue,self.saturation,self.value)
    def __len__(self):return 3
    def __getitem__(self,key):
        if key==0:return self.hue
        if key==1:return self.saturation
        if key==2:return self.value
        raise IndexError
    def pack(self,white=_B):return CRGB(self).pack(white)
def clamp(val,lower,upper):return max(lower,min(val,upper))
def normalize(val,inplace=_D):
    if isinstance(val,int):return clamp(val,0,255)/255.0
    if inplace:
        for (i,n) in enumerate(val):val[i]=normalize(n)
        return _B
    return[normalize(n)for n in val]
def clamp_norm(val):
    if isinstance(val,float):return clamp(val,_C,_A)
    return normalize(val)
def denormalize(val,inplace=_D):
    if isinstance(val,float):return clamp(int(val*256.0),0,255)
    if inplace:
        for (i,n) in enumerate(val):val[i]=denormalize(n)
        return _B
    return[denormalize(n)for n in val]
def unpack(val):return CRGB((val&16711680)/16711680.0,(val&65280)/65280.0,(val&255)/255.0)
def mix(color1,color2,weight2=0.5):
    clamp(weight2,_C,_A);weight1=_A-weight2
    if isinstance(color1,CHSV):
        if isinstance(color2,CHSV):hue=color1.hue+(color2.hue-color1.hue)*weight2;sat=color1.saturation*weight1+color2.saturation*weight2;val=color1.value*weight1+color2.value*weight2;return CHSV(hue,sat,val)
        color1=CRGB(color1)
        if isinstance(color2,int):color2=unpack(color2)
    else:
        if isinstance(color2,CHSV):color2=CRGB(color2)
        elif isinstance(color2,int):color2=unpack(color2)
        if isinstance(color1,int):color1=unpack(color1)
    return CRGB(color1.red*weight1+color2.red*weight2,color1.green*weight1+color2.green*weight2,color1.blue*weight1+color2.blue*weight2)
GFACTOR=2.7
def gamma_adjust(val,gamma_value=_B,brightness=_A,inplace=_D):
    if isinstance(val,float):
        if gamma_value is _B:gamma_value=GFACTOR
        return pow(val,gamma_value)*brightness
    if isinstance(val,(list,tuple)):
        if isinstance(val[0],float):
            if gamma_value is _B:gamma_value=GFACTOR
            if inplace:
                for (i,x) in enumerate(val):val[i]=pow(val[i],gamma_value)*brightness
                return _B
            newlist=[]
            for x in val:newlist.append(pow(x,gamma_value)*brightness)
            return newlist
        if gamma_value is _B:gamma_red,gamma_green,gamma_blue=GFACTOR,GFACTOR,GFACTOR
        elif isinstance(gamma_value,float):gamma_red,gamma_green,gamma_blue=gamma_value,gamma_value,gamma_value
        else:gamma_red,gamma_green,gamma_blue=gamma_value[0],gamma_value[1],gamma_value[2]
        if isinstance(brightness,float):brightness_red,brightness_green,brightness_blue=brightness,brightness,brightness
        else:brightness_red,brightness_green,brightness_blue=brightness[0],brightness[1],brightness[2]
        if inplace:
            for (i,x) in enumerate(val):
                if isinstance(x,CHSV):x=CRGB(x)
                val[i]=CRGB(pow(x.red,gamma_red)*brightness_red,pow(x.green,gamma_green)*brightness_green,pow(x.blue,gamma_blue)*brightness_blue)
            return _B
        newlist=[]
        for x in val:
            if isinstance(x,CHSV):x=CRGB(x)
            newlist.append(CRGB(pow(x.red,gamma_red)*brightness_red,pow(x.green,gamma_green)*brightness_green,pow(x.blue,gamma_blue)*brightness_blue))
        return newlist
    if gamma_value is _B:gamma_red,gamma_green,gamma_blue=GFACTOR,GFACTOR,GFACTOR
    elif isinstance(gamma_value,float):gamma_red,gamma_green,gamma_blue=gamma_value,gamma_value,gamma_value
    else:gamma_red,gamma_green,gamma_blue=gamma_value[0],gamma_value[1],gamma_value[2]
    if isinstance(brightness,float):brightness_red,brightness_green,brightness_blue=brightness,brightness,brightness
    else:brightness_red,brightness_green,brightness_blue=brightness[0],brightness[1],brightness[2]
    if isinstance(val,CHSV):val=CRGB(val)
    return CRGB(pow(val.red,gamma_red)*brightness_red,pow(val.green,gamma_green)*brightness_green,pow(val.blue,gamma_blue)*brightness_blue)
def palette_lookup(palette,position):position%=_A;weight2=position*len(palette);idx=int(floor(weight2));weight2-=idx;color1=palette[idx];idx=(idx+1)%len(palette);color2=palette[idx];return mix(color1,color2,weight2)
def expand_gradient(gradient,length):
    gradient=sorted(gradient);least=gradient[0][0];most=gradient[-1][0];newlist=[]
    for i in range(length):
        pos=i/float(length-1)
        if pos<=least:below,above=0,0
        elif pos>=most:below,above=-1,-1
        else:
            below,above=0,-1
            for (n,x) in enumerate(gradient):
                if pos>=x[0]:below=n
            for (n,x) in enumerate(gradient[-1:0:-1]):
                if pos<=x[0]:above=-1-n
        r=gradient[above][0]-gradient[below][0]
        if r<=0:newlist.append(gradient[below][1])
        else:weight2=(pos-gradient[below][0])/r;color1=gradient[below][1];color2=gradient[above][1];newlist.append(mix(color1,color2,weight2))
    return newlist