_A=None
__version__='0.3.0'
import ustruct,utime
from machine import I2C,Pin
from micropython import const
_WIA=const(0)
_HXL=const(3)
_HXH=const(4)
_HYL=const(5)
_HYH=const(6)
_HZL=const(7)
_HZH=const(8)
_ST2=const(9)
_CNTL1=const(10)
_ASAX=const(16)
_ASAY=const(17)
_ASAZ=const(18)
_MODE_POWER_DOWN=0
MODE_SINGLE_MEASURE=1
MODE_CONTINOUS_MEASURE_1=2
MODE_CONTINOUS_MEASURE_2=6
MODE_EXTERNAL_TRIGGER_MEASURE=4
_MODE_SELF_TEST=8
_MODE_FUSE_ROM_ACCESS=15
OUTPUT_14_BIT=0
OUTPUT_16_BIT=16
_SO_14BIT=0.6
_SO_16BIT=0.15
class AK8963:
	def __init__(self,i2c,address=12,mode=MODE_CONTINOUS_MEASURE_1,output=OUTPUT_16_BIT,offset=(0,0,0),scale=(1,1,1)):
		self.i2c=i2c;self.address=address;self._offset=offset;self._scale=scale
		if 72!=self.whoami:raise RuntimeError('AK8963 not found in I2C bus.')
		self._register_char(_CNTL1,_MODE_FUSE_ROM_ACCESS);asax=self._register_char(_ASAX);asay=self._register_char(_ASAY);asaz=self._register_char(_ASAZ);self._register_char(_CNTL1,_MODE_POWER_DOWN);self._adjustement=0.5*(asax-128)/128+1,0.5*(asay-128)/128+1,0.5*(asaz-128)/128+1;self._register_char(_CNTL1,mode|output)
		if output is OUTPUT_16_BIT:self._so=_SO_16BIT
		else:self._so=_SO_14BIT
	@property
	def magnetic(self):xyz=list(self._register_three_shorts(_HXL));self._register_char(_ST2);xyz[0]*=self._adjustement[0];xyz[1]*=self._adjustement[1];xyz[2]*=self._adjustement[2];so=self._so;xyz[0]*=so;xyz[1]*=so;xyz[2]*=so;xyz[0]-=self._offset[0];xyz[1]-=self._offset[1];xyz[2]-=self._offset[2];xyz[0]*=self._scale[0];xyz[1]*=self._scale[1];xyz[2]*=self._scale[2];return tuple(xyz)
	@property
	def adjustement(self):return self._adjustement
	@property
	def whoami(self):return self._register_char(_WIA)
	def calibrate(self,count=256,delay=200):
		self._offset=0,0,0;self._scale=1,1,1;reading=self.magnetic;minx=maxx=reading[0];miny=maxy=reading[1];minz=maxz=reading[2]
		while count:utime.sleep_ms(delay);reading=self.magnetic;minx=min(minx,reading[0]);maxx=max(maxx,reading[0]);miny=min(miny,reading[1]);maxy=max(maxy,reading[1]);minz=min(minz,reading[2]);maxz=max(maxz,reading[2]);count-=1
		offset_x=(maxx+minx)/2;offset_y=(maxy+miny)/2;offset_z=(maxz+minz)/2;self._offset=offset_x,offset_y,offset_z;avg_delta_x=(maxx-minx)/2;avg_delta_y=(maxy-miny)/2;avg_delta_z=(maxz-minz)/2;avg_delta=(avg_delta_x+avg_delta_y+avg_delta_z)/3;scale_x=avg_delta/avg_delta_x;scale_y=avg_delta/avg_delta_y;scale_z=avg_delta/avg_delta_z;self._scale=scale_x,scale_y,scale_z;return self._offset,self._scale
	def _register_short(self,register,value=_A,buf=bytearray(2)):
		A='<h'
		if value is _A:self.i2c.readfrom_mem_into(self.address,register,buf);return ustruct.unpack(A,buf)[0]
		ustruct.pack_into(A,buf,0,value);return self.i2c.writeto_mem(self.address,register,buf)
	def _register_three_shorts(self,register,buf=bytearray(6)):self.i2c.readfrom_mem_into(self.address,register,buf);return ustruct.unpack('<hhh',buf)
	def _register_char(self,register,value=_A,buf=bytearray(1)):
		if value is _A:self.i2c.readfrom_mem_into(self.address,register,buf);return buf[0]
		ustruct.pack_into('<b',buf,0,value);return self.i2c.writeto_mem(self.address,register,buf)
	def __enter__(self):return self
	def __exit__(self,exception_type,exception_value,traceback):0