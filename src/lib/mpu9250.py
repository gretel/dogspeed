_A=None
from micropython import const
from mpu6500 import MPU6500
from ak8963 import AK8963
__version__='0.3.0'
_INT_PIN_CFG=const(55)
_I2C_BYPASS_MASK=const(2)
_I2C_BYPASS_EN=const(2)
_I2C_BYPASS_DIS=const(0)
class MPU9250:
    def __init__(self,i2c,mpu6500=_A,ak8963=_A):
        if mpu6500 is _A:self.mpu6500=MPU6500(i2c)
        else:self.mpu6500=mpu6500
        char=self.mpu6500._register_char(_INT_PIN_CFG);char&=~ _I2C_BYPASS_MASK;char|=_I2C_BYPASS_EN;self.mpu6500._register_char(_INT_PIN_CFG,char)
        if ak8963 is _A:self.ak8963=AK8963(i2c)
        else:self.ak8963=ak8963
    @property
    def acceleration(self):return self.mpu6500.acceleration
    @property
    def gyro(self):return self.mpu6500.gyro
    @property
    def temperature(self):return self.mpu6500.temperature
    @property
    def magnetic(self):return self.ak8963.magnetic
    @property
    def whoami(self):return self.mpu6500.whoami
    def __enter__(self):return self
    def __exit__(self,exception_type,exception_value,traceback):0