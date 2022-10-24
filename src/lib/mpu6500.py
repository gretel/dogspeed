_A=None
__version__='0.3.0'
import ustruct,utime
from machine import I2C,Pin
from micropython import const
_GYRO_CONFIG=const(27)
_ACCEL_CONFIG=const(28)
_ACCEL_CONFIG2=const(29)
_ACCEL_XOUT_H=const(59)
_ACCEL_XOUT_L=const(60)
_ACCEL_YOUT_H=const(61)
_ACCEL_YOUT_L=const(62)
_ACCEL_ZOUT_H=const(63)
_ACCEL_ZOUT_L=const(64)
_TEMP_OUT_H=const(65)
_TEMP_OUT_L=const(66)
_GYRO_XOUT_H=const(67)
_GYRO_XOUT_L=const(68)
_GYRO_YOUT_H=const(69)
_GYRO_YOUT_L=const(70)
_GYRO_ZOUT_H=const(71)
_GYRO_ZOUT_L=const(72)
_WHO_AM_I=const(117)
ACCEL_FS_SEL_2G=const(0)
ACCEL_FS_SEL_4G=const(8)
ACCEL_FS_SEL_8G=const(16)
ACCEL_FS_SEL_16G=const(24)
_ACCEL_SO_2G=16384
_ACCEL_SO_4G=8192
_ACCEL_SO_8G=4096
_ACCEL_SO_16G=2048
GYRO_FS_SEL_250DPS=const(0)
GYRO_FS_SEL_500DPS=const(8)
GYRO_FS_SEL_1000DPS=const(16)
GYRO_FS_SEL_2000DPS=const(24)
_GYRO_SO_250DPS=131
_GYRO_SO_500DPS=62.5
_GYRO_SO_1000DPS=32.8
_GYRO_SO_2000DPS=16.4
_TEMP_SO=333.87
_TEMP_OFFSET=21
SF_G=1
SF_M_S2=9.80665
SF_DEG_S=1
SF_RAD_S=0.017453292519943
class MPU6500:
	def __init__(self,i2c,address=104,accel_fs=ACCEL_FS_SEL_2G,gyro_fs=GYRO_FS_SEL_250DPS,accel_sf=SF_M_S2,gyro_sf=SF_RAD_S,gyro_offset=(0,0,0)):
		self.i2c=i2c;self.address=address
		if self.whoami not in[113,112]:raise RuntimeError('MPU6500 not found in I2C bus.')
		self._accel_so=self._accel_fs(accel_fs);self._gyro_so=self._gyro_fs(gyro_fs);self._accel_sf=accel_sf;self._gyro_sf=gyro_sf;self._gyro_offset=gyro_offset
	@property
	def acceleration(self):so=self._accel_so;sf=self._accel_sf;xyz=self._register_three_shorts(_ACCEL_XOUT_H);return tuple([value/so*sf for value in xyz])
	@property
	def gyro(self):so=self._gyro_so;sf=self._gyro_sf;ox,oy,oz=self._gyro_offset;xyz=self._register_three_shorts(_GYRO_XOUT_H);xyz=[value/so*sf for value in xyz];xyz[0]-=ox;xyz[1]-=oy;xyz[2]-=oz;return tuple(xyz)
	@property
	def temperature(self):temp=self._register_short(_TEMP_OUT_H);return(temp-_TEMP_OFFSET)/_TEMP_SO+_TEMP_OFFSET
	@property
	def whoami(self):return self._register_char(_WHO_AM_I)
	def calibrate(self,count=256,delay=0):
		A=0.0;ox,oy,oz=A,A,A;self._gyro_offset=A,A,A;n=float(count)
		while count:utime.sleep_ms(delay);gx,gy,gz=self.gyro;ox+=gx;oy+=gy;oz+=gz;count-=1
		self._gyro_offset=ox/n,oy/n,oz/n;return self._gyro_offset
	def _register_short(self,register,value=_A,buf=bytearray(2)):
		A='>h'
		if value is _A:self.i2c.readfrom_mem_into(self.address,register,buf);return ustruct.unpack(A,buf)[0]
		ustruct.pack_into(A,buf,0,value);return self.i2c.writeto_mem(self.address,register,buf)
	def _register_three_shorts(self,register,buf=bytearray(6)):self.i2c.readfrom_mem_into(self.address,register,buf);return ustruct.unpack('>hhh',buf)
	def _register_char(self,register,value=_A,buf=bytearray(1)):
		if value is _A:self.i2c.readfrom_mem_into(self.address,register,buf);return buf[0]
		ustruct.pack_into('<b',buf,0,value);return self.i2c.writeto_mem(self.address,register,buf)
	def _accel_fs(self,value):
		self._register_char(_ACCEL_CONFIG,value)
		if ACCEL_FS_SEL_2G==value:return _ACCEL_SO_2G
		elif ACCEL_FS_SEL_4G==value:return _ACCEL_SO_4G
		elif ACCEL_FS_SEL_8G==value:return _ACCEL_SO_8G
		elif ACCEL_FS_SEL_16G==value:return _ACCEL_SO_16G
	def _gyro_fs(self,value):
		self._register_char(_GYRO_CONFIG,value)
		if GYRO_FS_SEL_250DPS==value:return _GYRO_SO_250DPS
		elif GYRO_FS_SEL_500DPS==value:return _GYRO_SO_500DPS
		elif GYRO_FS_SEL_1000DPS==value:return _GYRO_SO_1000DPS
		elif GYRO_FS_SEL_2000DPS==value:return _GYRO_SO_2000DPS
	def __enter__(self):return self
	def __exit__(self,exception_type,exception_value,traceback):0