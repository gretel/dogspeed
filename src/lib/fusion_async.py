try:import uasyncio as asyncio
except ImportError:import asyncio
from math import sqrt,atan2,asin,degrees,radians
from deltat import DeltaT
class Fusion:
    declination=0
    def __init__(self,read_coro,timediff=None):self.read_coro=read_coro;self.magbias=0,0,0;self.expect_ts=timediff is not None;self.deltat=DeltaT(timediff);self.q=[1.0,0.0,0.0,0.0];GyroMeasError=radians(40);self.beta=sqrt(3.0/4.0)*GyroMeasError;self.pitch=0;self.heading=0;self.roll=0
    async def calibrate(self,stopfunc):
        res=await self.read_coro();mag=res[2];magmax=list(mag);magmin=magmax[:]
        while not stopfunc():
            res=await self.read_coro();magxyz=res[2]
            for x in range(3):magmax[x]=max(magmax[x],magxyz[x]);magmin[x]=min(magmin[x],magxyz[x])
        self.magbias=tuple(map(lambda a,b:(a+b)/2,magmin,magmax))
    async def start(self,slow_platform=False):
        data=await self.read_coro()
        if len(data)==2 or self.expect_ts and len(data)==3:asyncio.create_task(self._update_nomag(slow_platform))
        else:asyncio.create_task(self._update_mag(slow_platform))
    async def _update_nomag(self,slow_platform):
        while True:
            if self.expect_ts:accel,gyro,ts=await self.read_coro()
            else:accel,gyro=await self.read_coro();ts=None
            ax,ay,az=accel;gx,gy,gz=(radians(x)for x in gyro);q1,q2,q3,q4=(self.q[x]for x in range(4));_2q1=2*q1;_2q2=2*q2;_2q3=2*q3;_2q4=2*q4;_4q1=4*q1;_4q2=4*q2;_4q3=4*q3;_8q2=8*q2;_8q3=8*q3;q1q1=q1*q1;q2q2=q2*q2;q3q3=q3*q3;q4q4=q4*q4;norm=sqrt(ax*ax+ay*ay+az*az)
            if norm==0:return
            norm=1/norm;ax*=norm;ay*=norm;az*=norm;s1=_4q1*q3q3+_2q3*ax+_4q1*q2q2-_2q2*ay;s2=_4q2*q4q4-_2q4*ax+4*q1q1*q2-_2q1*ay-_4q2+_8q2*q2q2+_8q2*q3q3+_4q2*az;s3=4*q1q1*q3+_2q1*ax+_4q3*q4q4-_2q4*ay-_4q3+_8q3*q2q2+_8q3*q3q3+_4q3*az;s4=4*q2q2*q4-_2q2*ax+4*q3q3*q4-_2q3*ay;norm=1/sqrt(s1*s1+s2*s2+s3*s3+s4*s4);s1*=norm;s2*=norm;s3*=norm;s4*=norm;qDot1=0.5*(-q2*gx-q3*gy-q4*gz)-self.beta*s1;qDot2=0.5*(q1*gx+q3*gz-q4*gy)-self.beta*s2;qDot3=0.5*(q1*gy-q2*gz+q4*gx)-self.beta*s3;qDot4=0.5*(q1*gz+q2*gy-q3*gx)-self.beta*s4
            if slow_platform:await asyncio.sleep_ms(0)
            deltat=self.deltat(ts);q1+=qDot1*deltat;q2+=qDot2*deltat;q3+=qDot3*deltat;q4+=qDot4*deltat;norm=1/sqrt(q1*q1+q2*q2+q3*q3+q4*q4);self.q=q1*norm,q2*norm,q3*norm,q4*norm;self.heading=0;self.pitch=degrees(-asin(2.0*(self.q[1]*self.q[3]-self.q[0]*self.q[2])));self.roll=degrees(atan2(2.0*(self.q[0]*self.q[1]+self.q[2]*self.q[3]),self.q[0]*self.q[0]-self.q[1]*self.q[1]-self.q[2]*self.q[2]+self.q[3]*self.q[3]))
    async def _update_mag(self,slow_platform):
        while True:
            if self.expect_ts:accel,gyro,mag,ts=await self.read_coro()
            else:accel,gyro,mag=await self.read_coro();ts=None
            mx,my,mz=(mag[x]-self.magbias[x]for x in range(3));ax,ay,az=accel;gx,gy,gz=(radians(x)for x in gyro);q1,q2,q3,q4=(self.q[x]for x in range(4));_2q1=2*q1;_2q2=2*q2;_2q3=2*q3;_2q4=2*q4;_2q1q3=2*q1*q3;_2q3q4=2*q3*q4;q1q1=q1*q1;q1q2=q1*q2;q1q3=q1*q3;q1q4=q1*q4;q2q2=q2*q2;q2q3=q2*q3;q2q4=q2*q4;q3q3=q3*q3;q3q4=q3*q4;q4q4=q4*q4;norm=sqrt(ax*ax+ay*ay+az*az)
            if norm==0:return
            norm=1/norm;ax*=norm;ay*=norm;az*=norm;norm=sqrt(mx*mx+my*my+mz*mz)
            if norm==0:return
            norm=1/norm;mx*=norm;my*=norm;mz*=norm;_2q1mx=2*q1*mx;_2q1my=2*q1*my;_2q1mz=2*q1*mz;_2q2mx=2*q2*mx;hx=mx*q1q1-_2q1my*q4+_2q1mz*q3+mx*q2q2+_2q2*my*q3+_2q2*mz*q4-mx*q3q3-mx*q4q4;hy=_2q1mx*q4+my*q1q1-_2q1mz*q2+_2q2mx*q3-my*q2q2+my*q3q3+_2q3*mz*q4-my*q4q4;_2bx=sqrt(hx*hx+hy*hy);_2bz=-_2q1mx*q3+_2q1my*q2+mz*q1q1+_2q2mx*q4-mz*q2q2+_2q3*my*q4-mz*q3q3+mz*q4q4;_4bx=2*_2bx;_4bz=2*_2bz;s1=-_2q3*(2*q2q4-_2q1q3-ax)+_2q2*(2*q1q2+_2q3q4-ay)-_2bz*q3*(_2bx*(0.5-q3q3-q4q4)+_2bz*(q2q4-q1q3)-mx)+(-_2bx*q4+_2bz*q2)*(_2bx*(q2q3-q1q4)+_2bz*(q1q2+q3q4)-my)+_2bx*q3*(_2bx*(q1q3+q2q4)+_2bz*(0.5-q2q2-q3q3)-mz);s2=_2q4*(2*q2q4-_2q1q3-ax)+_2q1*(2*q1q2+_2q3q4-ay)-4*q2*(1-2*q2q2-2*q3q3-az)+_2bz*q4*(_2bx*(0.5-q3q3-q4q4)+_2bz*(q2q4-q1q3)-mx)+(_2bx*q3+_2bz*q1)*(_2bx*(q2q3-q1q4)+_2bz*(q1q2+q3q4)-my)+(_2bx*q4-_4bz*q2)*(_2bx*(q1q3+q2q4)+_2bz*(0.5-q2q2-q3q3)-mz)
            if slow_platform:await asyncio.sleep_ms(0)
            s3=-_2q1*(2*q2q4-_2q1q3-ax)+_2q4*(2*q1q2+_2q3q4-ay)-4*q3*(1-2*q2q2-2*q3q3-az)+(-_4bx*q3-_2bz*q1)*(_2bx*(0.5-q3q3-q4q4)+_2bz*(q2q4-q1q3)-mx)+(_2bx*q2+_2bz*q4)*(_2bx*(q2q3-q1q4)+_2bz*(q1q2+q3q4)-my)+(_2bx*q1-_4bz*q3)*(_2bx*(q1q3+q2q4)+_2bz*(0.5-q2q2-q3q3)-mz);s4=_2q2*(2*q2q4-_2q1q3-ax)+_2q3*(2*q1q2+_2q3q4-ay)+(-_4bx*q4+_2bz*q2)*(_2bx*(0.5-q3q3-q4q4)+_2bz*(q2q4-q1q3)-mx)+(-_2bx*q1+_2bz*q3)*(_2bx*(q2q3-q1q4)+_2bz*(q1q2+q3q4)-my)+_2bx*q2*(_2bx*(q1q3+q2q4)+_2bz*(0.5-q2q2-q3q3)-mz);norm=1/sqrt(s1*s1+s2*s2+s3*s3+s4*s4);s1*=norm;s2*=norm;s3*=norm;s4*=norm;qDot1=0.5*(-q2*gx-q3*gy-q4*gz)-self.beta*s1;qDot2=0.5*(q1*gx+q3*gz-q4*gy)-self.beta*s2;qDot3=0.5*(q1*gy-q2*gz+q4*gx)-self.beta*s3;qDot4=0.5*(q1*gz+q2*gy-q3*gx)-self.beta*s4;deltat=self.deltat(ts);q1+=qDot1*deltat;q2+=qDot2*deltat;q3+=qDot3*deltat;q4+=qDot4*deltat;norm=1/sqrt(q1*q1+q2*q2+q3*q3+q4*q4);self.q=q1*norm,q2*norm,q3*norm,q4*norm;self.heading=self.declination+degrees(atan2(2.0*(self.q[1]*self.q[2]+self.q[0]*self.q[3]),self.q[0]*self.q[0]+self.q[1]*self.q[1]-self.q[2]*self.q[2]-self.q[3]*self.q[3]));self.pitch=degrees(-asin(2.0*(self.q[1]*self.q[3]-self.q[0]*self.q[2])));self.roll=degrees(atan2(2.0*(self.q[0]*self.q[1]+self.q[2]*self.q[3]),self.q[0]*self.q[0]-self.q[1]*self.q[1]-self.q[2]*self.q[2]+self.q[3]*self.q[3]))