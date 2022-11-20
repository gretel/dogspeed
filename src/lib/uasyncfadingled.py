# -*- coding: utf-8 -*-

"""
Version v0.4.1
Micropython driver to asynchronously drive one or more fading-
capable LED(s) at relative brightness levels adapted for (logarithmic)
human brightness perception. Provides a number of convenience methods
for dimming and fading that can be called synchronously, e.g. in a
callback handler. Additionally, almost any fading sequence can be
constructed and scheduled with simple instructions.

Copyright (C) 2021  Oliver Paulick

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

__author__ = 'Oliver Paulick'
__copyright__ = 'Copyright 2021, Oliver Paulick'
__credits__ = ['Oliver Paulick',]
__license__ = 'GPL v3.0'
__version__ = '0.4.1'
__maintainer__ = 'Oliver Paulick'
__email__ = 'alvenhar@yahoo.de'
__status__ = 'Dev'


# Built-in/Generic Imports
import uasyncio
from math import log # want log2, but isn't implemented yet, see helper function log2
from micropython import const
import utime
from machine import Pin, PWM


# constant definitions depending on the hardware (here for the original Pi Pico)
_PWM_OFF = const(0)
_PWM_MAX = const(2**16 - 1)
_PWM_FREQ = const(5000)


def log2(x: float) -> float:
    """Helper function as log2 is not (yet) implemented in the math module."""
    return log(x)/log(2)


class LED:
    """
    Core class to be imported from this module.
    Drives an LED with asynchronous fading capability at the given GPIO
    pin(s). <gpio> can be either a single pin number or a list or tuple
    of pin numbers. If several pins are defined, all LEDs connected to
    these pins will work in unison. If you need to command several LEDs
    separately, just instantiate each with their own pin.
    All brightness settings operate on a scale adapted for the logarithmic
    nature of human brightness perception with values from 0 - 100%. This
    has the side-effect that very low values (<10%) might not provide
    enough current to the LED(s) to actually light them up.
    If you know what you're doing, you can experiment with the PWM constants
    defined in this module for different effects. I take no responsibility!
    The current brightness can be retrieved via the eponymous property once
    the LED has been initialized. The fading/transition presets defined in
    this class are public to allow clients to set different defaults.
    """
    
    # public fading/transition presets
    FADE_TIME: int = 2_000 # milliseconds
    FADE_EXP: float  = 1.0 # exponent for fading transition curve
    UPDATE_INTERVAL: int = 20 # milliseconds
    
    def __init__(self, gpio):
        """Set up the LED to use the given <gpio> pin(s); either a single int or a list/tuple of ints."""
        if type(gpio) == type(int()):
            self.PWM = [PWM(Pin(gpio, mode=Pin.OUT)), ]
        elif type(gpio) in (type(list()), type(tuple())):
            self.PWM = [PWM(Pin(pin, mode=Pin.OUT)) for pin in gpio]
        else:
            raise TypeError("GPIO of undefined type!")
        for pwm in self.PWM:
            pwm.freq(_PWM_FREQ)
            pwm.duty_u16(_PWM_OFF)
        # public object data
        self.current_brightness: int = 0
        # private async and fading flags
        self._fading_in_progress: bool = False
        self._fading_force_abort: bool = False
        self._fading_force_finish: bool = False
    
    ### PUBLIC METHOD DEFINITIONS ###
    
    def set_to(self, brightness: int, fading_friendly: bool = False):
        """
        Set the LED to the given <brightness> (int between 0-100). Stops any
        fading in progress unless <fading_friendly> is given as True.
        """
        if not fading_friendly:
            self.abort_fading()
        next_pwm_duty = self._get_pwm_for_brightness(brightness)
        self.current_brightness = brightness
        for pwm in self.PWM:
            pwm.duty_u16(next_pwm_duty)
    
    def change_brightness(self, percent_step: int):
        """
        Convenience method to change the LED's brightness level by the given
        <percent_step> (int between -100/+100). Useful for dimming.
        """
        if not -100 <= percent_step <= 100:
            raise ValueError(
                "Brightness change <{}%> out of range (-100% / +100%)!".format(percent_step))
        if percent_step == 0:
            return # no change
        new_brightness = self.current_brightness + percent_step
        if new_brightness > 100:
            new_brightness = 100
        elif new_brightness < 0:
            new_brightness = 0
        self.set_to(new_brightness)
    
    def turn_on(self):
        """Convenience method to set the LED immediately to its max brightness."""
        self.set_to(100)
    
    def turn_off(self):
        """Convenience method to abort fading and turn off the LED immediately."""
        self.set_to(0)
    
    def abort_fading(self):
        """Abort any fading in progress (LED will remain at current brightness)."""
        if self._fading_in_progress:
            self._fading_force_abort = True
    
    def fade_to(self, target_brightness: int = 100,
                fade_time: int = FADE_TIME, fade_exp: float = FADE_EXP):
        """
        Convenience method to start a simple one-shot fade from the current to
        the given <brightness> (int between 0-100), taking <fade_time> ms. The
        transition curve can be set by changing <fade_exp>.
        Defaults are 100% brightness and the class's FADE_TIME and FADE_EXP.
        """
        if not 0 <= target_brightness <= 100:
            raise ValueError("Target brightness {} out of range (0-100)!".format(target_brightness))
        # schedule the fader into the event loop
        uasyncio.create_task(self._simple_fade(target_brightness, fade_time, fade_exp))
    
    def start_wave(self, brightness_range: tuple = (0, 100), wave_length: int = 4_000,
                   fade_up_exp: float = 1.0, fade_down_exp: float = 1.0):
        """
        Convenience method to start an indefinite wave pattern within a given
        <brightness_range> (a tuple of int min and max brightness, both between
        0-100) and the given <wave_length>. The transition curve can be set by
        changing <fade_up_exp> and <fade_down_exp>.
        (Defaults are 0 - 100% brightness, 4s wavelength, and a linear fade.
        """
        if len(brightness_range) != 2:
            raise ValueError("Brightness range for wave must be given as (min, max)!")
        if not 0 <= brightness_range[0] <= 100 or not 0 <= brightness_range[1] <= 100:
            raise ValueError(
                "Brightness range {} for wave out of range (0-100)!".format(brightness_range))
        if brightness_range[0] == brightness_range[1]:
            raise ValueError("The min and max brightness for a wave should not be the same value!")
        if wave_length <= 0:
            raise ValueError("Wave length must be positive!")
        # calculate and assemble the sequence
        initial_brightness = brightness_range[0]
        half_wave = wave_length // 2
        wave_sequence = [
            (brightness_range[1], half_wave, fade_up_exp),
            (brightness_range[0], half_wave, fade_down_exp),
            ]
        # schedule the fader into the event loop
        uasyncio.create_task(self._async_sequence(wave_sequence, initial_brightness))
    
    def start_heartbeat(self, brightness_range: tuple = (0, 100), pulse: int = 60):
        """
        Convenience method to start an indefinite pre-defined heartbeat pattern
        within a given <brightness_range> (a tuple of int min and max brightness,
        both between 0-100) at the given <pulse> (heartbeats per minute).
        Defaults are 0 - 100% brightness and a pulse of 60.
        """
        if len(brightness_range) != 2:
            raise ValueError("Brightness range for heartbeat pattern must be given as 2-tuple!")
        if not 0 <= brightness_range[0] <= 100 or not 0 <= brightness_range[1] <= 100:
            raise ValueError("Brightness range {} for heartbeat pattern out of range (0-100)!".format(brightness_range))
        if brightness_range[0] == brightness_range[1]:
            raise ValueError("The min and max brightness for a heartbeat pattern should not be the same value!")
        if pulse <= 0:
            raise ValueError("Heartbeat pattern pulse must be positive!")
        # calculate and assemble the sequence
        wave_length = 60_000 / pulse
        brightness_diff = brightness_range[1] - brightness_range[0]
        first_peak = brightness_range[0] + round(brightness_diff * 0.7)
        first_peak_time = round(wave_length * 0.15)
        first_dip = brightness_range[0] + round(brightness_diff * 0.4)
        first_dip_time = round(wave_length * 0.05)
        second_peak = brightness_range[1]
        second_peak_time = round(wave_length * 0.15)
        second_dip = brightness_range[0]
        second_dip_time = round(wave_length) - (first_peak_time + first_dip_time + second_peak_time)
        second_dip_exp = 2.0
        heartbeat_sequence = [
            (first_peak, first_peak_time),
            (first_dip, first_dip_time),
            (second_peak, second_peak_time),
            (second_dip, second_dip_time, second_dip_exp),
            ]
        # schedule the fader into the event loop
        uasyncio.create_task(self._async_sequence(heartbeat_sequence, initial_brightness=brightness_range[0]))
    
    def start_sequence(self, sequence: list, initial_brightness:int = -1, repeat:int = 0):
        """
        Start a user-defined fade sequence passed as a list of tuples, each
        defining one leg of the fade sequence with target brightness, time (in
        ms), and exponent (can be omitted to default to 1). Initial brightness
        will be honored if within 0-100, otherwise the first leg starts from
        the current brightness (default behavior). Unless interrupted (e.g. by
        abort_fading()), the pattern will be repeated <repeat> times, or
        indefinitely if <repeat> is set to 0 or less (default behavior).
        Target brightness for any leg can be set to a negative value to
        indicate a simple 'no-change' wait period for the respective fade_time.
        """
        if len(sequence) == 0:
            raise ValueError("Fade sequence is empty!")
        # schedule the fader into the event loop
        uasyncio.create_task(self._async_sequence(sequence, initial_brightness, repeat))
    
    ### ========================== ###
    ### PRIVATE METHOD DEFINITIONS ###
    ### ========================== ###
    
    async def _begin_fading(self):
        """Fading helper method. Not to be called directly!"""
        if self._fading_in_progress:
            self.abort_fading()
            while self._fading_in_progress:
                await uasyncio.sleep_ms(1)
        self._fading_in_progress = True
        self._fading_force_abort = False
        self._fading_force_finish = False
    
    async def _async_fading(self, target_brightness: int, fade_time: int, fade_exp: float = 1.0):
        """Core fading method. Not to be called directly!"""
        if target_brightness < 0:
            no_change = True
        elif target_brightness > 100:
            raise ValueError("Target brightness {} out of range (0-100)!".format(target_brightness))
        else:
            no_change = False
        if fade_time < self.UPDATE_INTERVAL:
            raise ValueError("Fade time <{}> too short!".format(fade_time))
        if fade_exp <= 0:
            raise ValueError("Fade exponent <{}> undefined!".format(fade_exp))
        # calculate dimming steps
        initial_brightness = self.current_brightness
        brightness_diff = target_brightness - initial_brightness
        # catch 'no-change' wait periods, either intentional or by happenstance, to save CPU time
        if no_change == True or brightness_diff == 0:
            await uasyncio.sleep_ms(fade_time)
            return
        # start timing
        fade_start = utime.ticks_ms()
        fade_target = utime.ticks_add(fade_start, fade_time)
        # start the fading cycle
        while not self._fading_force_abort:
            now = utime.ticks_ms()
            if utime.ticks_diff(now, fade_target) >= 0: # if due or overdue
                self.set_to(target_brightness, fading_friendly=True)
                return
            progress_fraction = utime.ticks_diff(now, fade_start) / fade_time
            fade_multiplier = progress_fraction ** fade_exp
            next_brightness = round(initial_brightness + (brightness_diff * fade_multiplier))
            self.set_to(next_brightness, fading_friendly=True)
            await uasyncio.sleep_ms(self.UPDATE_INTERVAL)
    
    async def _async_sequence(self, sequence: list, initial_brightness:int, repeat:int = 0):
        """Asynchronous executor for the start_fade_sequence() class method. Not to be called directly!"""
        run_forever = True if repeat <= 0 else False
        #  signal and wait for any fade in progress to abort
        await self._begin_fading()
        if 0 <= initial_brightness <= 100:
            self.set_to(initial_brightness, fading_friendly=True)
        while not self._fading_force_abort:
            for step in sequence:
                await self._async_fading(*step)
                if self._fading_force_abort:
                    break # exit the for-loop
            if run_forever:
                continue
            else:
                repeat -= 1
                if repeat == 0:
                    break # exit the while-loop
        self._fading_in_progress = False
    
    async def _simple_fade(self, target_brightness: int, fade_time: int, fade_exp: float):
        """Asynchronous executor for the fade_to() class method. Not to be called directly!"""
        #  signal and wait for any fade in progress to abort
        await self._begin_fading()
        await self._async_fading(target_brightness, fade_time, fade_exp)
        self._fading_in_progress = False
    
    def _get_pwm_for_brightness(self, brightness: int) -> int:
        """
        Return a PWM dutycycle that corresponds roughly to a relative
        <brightness> in 'percent' (int between 0-100) as perceived by a human.
        """
        if not 0 <= brightness <= 100:
            raise ValueError("Brightness <{}%> out of range (0-100%)!".format(percent))
        if brightness == 0:
            new_pwm_duty = _PWM_OFF
        elif brightness == 100:
            new_pwm_duty = _PWM_MAX
        else:
            adjusted_brightness = 2**(brightness/15) - 1
            new_pwm_duty = round(_PWM_MAX * adjusted_brightness / 100)
        return new_pwm_duty
    
#     def _calculate_current_brightness(self) -> int:
#         """
#         Return an integer percentage value (0-100%) of the approximate relative brightness perceived by a human.
#         This method is needed only for debugging. In normal operation, the current brightness can simply be accessed
#         using the current_brightness property (which is much cheaper).
#         """
#         duty = self.PWM[0].duty_u16()
#         if duty == _PWM_OFF:
#             return 0
#         elif duty == _PWM_MAX:
#             return 100
#         else:
#             return round(15*log2((duty*100/_PWM_MAX)+1))
