from utime import sleep_ms
from machine import I2C
from vector3d import Vector3d
class MPUException(OSError):0
def bytes_toint(msb,lsb):
    if not msb&128:return msb<<8|lsb
    return-((msb^255)<<8|(lsb^255)+1)
class MPU6050:
    _I2Cerror='I2C failure when communicating with IMU';_mpu_addr=104,105;_chip_id=104
    def __init__(self,side_str,device_addr=None,transposition=(0,1,2),scaling=(1,1,1)):
        self._accel=Vector3d(transposition,scaling,self._accel_callback);self._gyro=Vector3d(transposition,scaling,self._gyro_callback);self.buf1=bytearray(1);self.buf2=bytearray(2);self.buf3=bytearray(3);self.buf6=bytearray(6);sleep_ms(200)
        if isinstance(side_str,str):self._mpu_i2c=I2C(side_str)
        elif hasattr(side_str,'readfrom'):self._mpu_i2c=side_str
        else:raise ValueError('Invalid I2C instance')
        if device_addr is None:
            devices=set(self._mpu_i2c.scan());mpus=devices.intersection(set(self._mpu_addr));number_of_mpus=len(mpus)
            if number_of_mpus==0:raise MPUException("No MPU's detected")
            elif number_of_mpus==1:self.mpu_addr=mpus.pop()
            else:raise ValueError("Two MPU's detected: must specify a device address")
        else:
            if device_addr not in(0,1):raise ValueError('Device address must be 0 or 1')
            self.mpu_addr=self._mpu_addr[device_addr]
        self.chip_id;self.wake();self.passthrough=True;self.accel_range=0;self.gyro_range=0
    def _read(self,buf,memaddr,addr):self._mpu_i2c.readfrom_mem_into(addr,memaddr,buf)
    def _write(self,data,memaddr,addr):self.buf1[0]=data;self._mpu_i2c.writeto_mem(addr,memaddr,self.buf1)
    def wake(self):
        try:self._write(1,107,self.mpu_addr)
        except OSError:raise MPUException(self._I2Cerror)
        return'awake'
    def sleep(self):
        try:self._write(64,107,self.mpu_addr)
        except OSError:raise MPUException(self._I2Cerror)
        return'asleep'
    @property
    def chip_id(self):
        try:self._read(self.buf1,117,self.mpu_addr)
        except OSError:raise MPUException(self._I2Cerror)
        chip_id=int(self.buf1[0])
        if chip_id!=self._chip_id:raise ValueError('Bad chip ID retrieved: MPU communication failure')
        return chip_id
    @property
    def sensors(self):return self._accel,self._gyro
    @property
    def temperature(self):
        try:self._read(self.buf2,65,self.mpu_addr)
        except OSError:raise MPUException(self._I2Cerror)
        return bytes_toint(self.buf2[0],self.buf2[1])/340+35
    @property
    def passthrough(self):
        try:self._read(self.buf1,55,self.mpu_addr);return self.buf1[0]&2>0
        except OSError:raise MPUException(self._I2Cerror)
    @passthrough.setter
    def passthrough(self,mode):
        if type(mode)is bool:
            val=2 if mode else 0
            try:self._write(val,55,self.mpu_addr);self._write(0,106,self.mpu_addr)
            except OSError:raise MPUException(self._I2Cerror)
        else:raise ValueError('pass either True or False')
    @property
    def sample_rate(self):
        try:self._read(self.buf1,25,self.mpu_addr);return self.buf1[0]
        except OSError:raise MPUException(self._I2Cerror)
    @sample_rate.setter
    def sample_rate(self,rate):
        if rate<0 or rate>255:raise ValueError('Rate must be in range 0-255')
        try:self._write(rate,25,self.mpu_addr)
        except OSError:raise MPUException(self._I2Cerror)
    @property
    def filter_range(self):
        try:self._read(self.buf1,26,self.mpu_addr);res=self.buf1[0]&7
        except OSError:raise MPUException(self._I2Cerror)
        return res
    @filter_range.setter
    def filter_range(self,filt):
        if filt in range(7):
            try:self._write(filt,26,self.mpu_addr)
            except OSError:raise MPUException(self._I2Cerror)
        else:raise ValueError('Filter coefficient must be between 0 and 6')
    @property
    def accel_range(self):
        try:self._read(self.buf1,28,self.mpu_addr);ari=self.buf1[0]//8
        except OSError:raise MPUException(self._I2Cerror)
        return ari
    @accel_range.setter
    def accel_range(self,accel_range):
        ar_bytes=0,8,16,24
        if accel_range in range(len(ar_bytes)):
            try:self._write(ar_bytes[accel_range],28,self.mpu_addr)
            except OSError:raise MPUException(self._I2Cerror)
        else:raise ValueError('accel_range can only be 0, 1, 2 or 3')
    @property
    def gyro_range(self):
        try:self._read(self.buf1,27,self.mpu_addr);gri=self.buf1[0]//8
        except OSError:raise MPUException(self._I2Cerror)
        return gri
    @gyro_range.setter
    def gyro_range(self,gyro_range):
        gr_bytes=0,8,16,24
        if gyro_range in range(len(gr_bytes)):
            try:self._write(gr_bytes[gyro_range],27,self.mpu_addr)
            except OSError:raise MPUException(self._I2Cerror)
        else:raise ValueError('gyro_range can only be 0, 1, 2 or 3')
    @property
    def accel(self):return self._accel
    def _accel_callback(self):
        try:self._read(self.buf6,59,self.mpu_addr)
        except OSError:raise MPUException(self._I2Cerror)
        self._accel._ivector[0]=bytes_toint(self.buf6[0],self.buf6[1]);self._accel._ivector[1]=bytes_toint(self.buf6[2],self.buf6[3]);self._accel._ivector[2]=bytes_toint(self.buf6[4],self.buf6[5]);scale=16384,8192,4096,2048;self._accel._vector[0]=self._accel._ivector[0]/scale[self.accel_range];self._accel._vector[1]=self._accel._ivector[1]/scale[self.accel_range];self._accel._vector[2]=self._accel._ivector[2]/scale[self.accel_range]
    def get_accel_irq(self):self._read(self.buf6,59,self.mpu_addr);self._accel._ivector[0]=bytes_toint(self.buf6[0],self.buf6[1]);self._accel._ivector[1]=bytes_toint(self.buf6[2],self.buf6[3]);self._accel._ivector[2]=bytes_toint(self.buf6[4],self.buf6[5])
    @property
    def gyro(self):return self._gyro
    def _gyro_callback(self):
        try:self._read(self.buf6,67,self.mpu_addr)
        except OSError:raise MPUException(self._I2Cerror)
        self._gyro._ivector[0]=bytes_toint(self.buf6[0],self.buf6[1]);self._gyro._ivector[1]=bytes_toint(self.buf6[2],self.buf6[3]);self._gyro._ivector[2]=bytes_toint(self.buf6[4],self.buf6[5]);scale=131,65.5,32.8,16.4;self._gyro._vector[0]=self._gyro._ivector[0]/scale[self.gyro_range];self._gyro._vector[1]=self._gyro._ivector[1]/scale[self.gyro_range];self._gyro._vector[2]=self._gyro._ivector[2]/scale[self.gyro_range]
    def get_gyro_irq(self):self._read(self.buf6,67,self.mpu_addr);self._gyro._ivector[0]=bytes_toint(self.buf6[0],self.buf6[1]);self._gyro._ivector[1]=bytes_toint(self.buf6[2],self.buf6[3]);self._gyro._ivector[2]=bytes_toint(self.buf6[4],self.buf6[5])