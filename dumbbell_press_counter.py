#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Dumbbell Press Counter
ICM20948 + ST7789 on Waffle Nano V1
Method: total acc magnitude = sqrt(ax^2+ay^2+az^2) - gravity baseline
"""
from machine import I2C, SPI, Pin
import icm20948, utime, math, st7789, gc

SCREEN_W, SCREEN_H = 240, 240

# Default thresholds (overridden by auto-calibration)
PRESS_THRESHOLD = 30
RETURN_DROP = 20
RESET_THRESHOLD = -20
MIN_CYCLE_TIME = 300
MIN_REP_TIME = 300
PEAK_TIMEOUT = 1500
ALPHA = 0.3
DISPLAY_MS = 50

# ---- State Machine ----
LOCK_MS = 300  # 计数后锁定时间(ms)

class Detector:
    IDLE, PRESSING, RETURNING, LOCKED = range(4)

    def __init__(self):
        self.state = self.IDLE
        self.reps = 0
        self.lst = utime.ticks_ms()
        self.peak = 0.0
        self.vf = 0.0
        self.base = 1000.0
        self.ba = 0.01
        self.th_on = PRESS_THRESHOLD
        self.th_off = PRESS_THRESHOLD - 5
        self.pv = 0.0

    def set_base(self, x, y, z):
        self.base = math.sqrt(x*x + y*y + z*z)

    def lpf(self, raw, prev):
        return ALPHA * raw + (1 - ALPHA) * prev

    def update(self, x, y, z):
        now = utime.ticks_ms()
        t = math.sqrt(x*x + y*y + z*z)
        m = t - self.base
        if m < 30 and m > -30:
            self.base += self.ba * (t - self.base)
        self.vf = self.lpf(m, self.vf)
        v = self.vf
        falling = v < self.pv - 2
        self.pv = v
        done = False; sn = "IDLE"
        if self.state == self.IDLE:
            sn = "IDLE"
            if v > self.th_on:
                if utime.ticks_diff(now, self.lst) > MIN_CYCLE_TIME:
                    self.state = self.PRESSING
                    self.peak = v
                    self.lst = now
        elif self.state == self.PRESSING:
            sn = "PRESS"
            if v > self.peak: self.peak = v
            if falling and (self.peak - v) > RETURN_DROP:
                if utime.ticks_diff(now, self.lst) > MIN_CYCLE_TIME:
                    self.state = self.RETURNING
                    self.lst = now
            if utime.ticks_diff(now, self.lst) > PEAK_TIMEOUT:
                self.state = self.IDLE; self.lst = now
        elif self.state == self.RETURNING:
            sn = "RETURN"
            if v < self.th_off or v < RESET_THRESHOLD:
                if utime.ticks_diff(now, self.lst) > MIN_CYCLE_TIME:
                    self.reps += 1; done = True
                    self.state = self.LOCKED
                    self.lst = now
        elif self.state == self.LOCKED:
            sn = "LOCK"
            # 锁定期间完全不响应任何信号
            if utime.ticks_diff(now, self.lst) > LOCK_MS:
                self.state = self.IDLE; self.lst = now
        return done, sn, v

# ---- 5x7 Font (35 chars, 175 bytes) ----
FCHARS = " -0123456789:?BCXEGHILMNOPRSTUaelopst"
FDATA = bytes([
    0x00,0x00,0x00,0x00,0x00,0x08,0x08,0x08,0x08,0x08,0x3E,0x51,0x49,0x45,0x3E,0x00,0x42,0x7F,0x40,0x00,
    0x42,0x61,0x51,0x49,0x46,0x21,0x41,0x45,0x4B,0x31,0x18,0x14,0x12,0x7F,0x10,0x27,0x45,0x45,0x45,0x39,
    0x3C,0x4A,0x49,0x49,0x30,0x01,0x71,0x09,0x05,0x03,0x36,0x49,0x49,0x49,0x36,0x06,0x49,0x49,0x29,0x1E,
    0x00,0x36,0x36,0x00,0x00,0x02,0x01,0x51,0x09,0x06,0x7F,0x49,0x49,0x49,0x36,0x3E,0x41,0x41,0x41,0x22,
    0x63,0x14,0x08,0x14,0x63,0x7F,0x49,0x49,0x49,0x41,0x3E,0x41,0x41,0x51,0x32,0x7F,0x08,0x08,0x08,0x7F,
    0x00,0x41,0x7F,0x41,0x00,0x7F,0x40,0x40,0x40,0x40,0x7F,0x02,0x04,0x02,0x7F,0x7F,0x04,0x08,0x10,0x7F,
    0x3E,0x41,0x41,0x41,0x3E,0x7F,0x09,0x09,0x09,0x06,0x7F,0x09,0x19,0x29,0x46,0x46,0x49,0x49,0x49,0x31,
    0x01,0x01,0x7F,0x01,0x01,0x3F,0x40,0x40,0x40,0x3F,0x20,0x54,0x54,0x54,0x78,0x38,0x54,0x54,0x54,0x18,
    0x00,0x41,0x7F,0x40,0x00,0x38,0x44,0x44,0x44,0x38,0x7C,0x14,0x14,0x14,0x08,0x48,0x54,0x54,0x54,0x20,
    0x04,0x3F,0x44,0x40,0x20,
])

# ---- Display ----
class Display:
    def __init__(self, d):
        self.d = d; d.init(); d.fill(st7789.color565(0,0,0))
        self.BG = st7789.color565(0,0,0)
        self.WH = st7789.color565(255,255,255)
        self.GR = st7789.color565(60,255,60)
        self.YE = st7789.color565(255,255,60)
        self.CY = st7789.color565(60,255,255)
        self.GY = st7789.color565(100,100,100)

    def _ch(self, ch, px, py, c, s=1):
        i = FCHARS.find(ch)
        if i < 0: return
        b = i * 5
        for col in range(5):
            cd = FDATA[b+col]
            if cd == 0: continue
            for row in range(7):
                if cd & (1<<row):
                    sx, sy = px+col*s, py+row*s
                    if s==1: self.d.pixel(sx,sy,c)
                    else:
                        for dy in range(s):
                            for dx in range(s): self.d.pixel(sx+dx,sy+dy,c)

    def _txt(self, t, px, py, c, s=1):
        for i,ch in enumerate(t): self._ch(ch, px+i*6*s, py, c, s)

    def _mid(self, text, s): return (SCREEN_W - len(text) * 6 * s) // 2

    def _i2s(self, n):
        if n==0: return "0"
        s=""; d=""
        if n<0: s="-"; n=-n
        while n>0: d=chr(48+n%10)+d; n//=10
        return s+d if d else "0"

    def show_normal(self, reps, sn, v):
        self.d.fill(self.BG)
        self._txt("DUMBBELL", self._mid("DUMBBELL",1), 8, self.CY, 1)
        rs=self._i2s(reps)
        self._txt(rs, self._mid(rs,4), 80, self.GR, 4)
        sc=self.GY
        if sn=="PRESS": sc=self.GR
        elif sn=="RETURN": sc=self.YE
        self._txt(sn, self._mid(sn,2), 160, sc, 2)
        self._txt("M:"+self._i2s(int(v)), self._mid("M:"+self._i2s(int(v)),1), 210, self.CY, 1)

    def show_countdown(self, n):
        self.d.fill(self.BG)
        ns=self._i2s(n)
        self._txt(ns, self._mid(ns,6), 80, self.GR, 6)

    def show_set(self, cur, target):
        self.d.fill(self.BG)
        ss=self._i2s(cur)+"/"+self._i2s(target)
        self._txt(ss, self._mid(ss,3), 80, self.GR, 3)
        self._txt("SET", self._mid("SET",2), 160, self.CY, 2)

    def show_done(self, reps):
        self.d.fill(self.BG)
        self._txt("DONE", self._mid("DONE",3), 50, self.GR, 3)
        rs=self._i2s(reps)
        self._txt(rs, self._mid(rs,4), 120, self.GR, 4)
        self._txt("NEXT?", self._mid("NEXT?",1), 200, self.GY, 1)

    def show_msg(self, text, sub=""):
        self.d.fill(self.BG)
        self._txt(text, self._mid(text,2), 80, self.CY, 2)
        if sub:
            self._txt(sub, self._mid(sub,1), 160, self.GY, 1)

    def show_cal_peak(self, n, pk):
        self.d.fill(self.BG)
        self._txt("CAL "+self._i2s(n), self._mid("CAL "+self._i2s(n),2), 80, self.YE, 2)
        self._txt("Peak:"+self._i2s(int(pk)), self._mid("Peak:"+self._i2s(int(pk)),1), 160, self.GR, 1)

    def show_standby(self):
        self.d.fill(self.BG)
        self._txt("DUMBBELL", self._mid("DUMBBELL",1), 10, self.CY, 1)
        self._txt("SHORT:SET", self._mid("SHORT:SET",2), 70, self.GR, 2)
        self._txt("10 REPS", self._mid("10 REPS",2), 100, self.GR, 2)
        self._txt("LONG:CAL", self._mid("LONG:CAL",2), 145, self.YE, 2)
        self._txt("PRESS", self._mid("PRESS",3), 200, self.GY, 3)

# ---- Button + App States ----
NORMAL, SET_CD, SET_GO, DONE, CAL_CD, CAL_GO = range(6)
SET_REPS = 10
BTN = Pin(12, func=Pin.GPIO, dir=Pin.IN, pull=Pin.PULL_UP)
_btn_pd = 0  # button press down time

def rd_btn():
    global _btn_pd
    v = BTN.value()
    now = utime.ticks_ms()
    if v == 0 and _btn_pd == 0:
        _btn_pd = now
    elif v == 1 and _btn_pd > 0:
        dur = utime.ticks_diff(now, _btn_pd)
        _btn_pd = 0
        return 2 if dur >= 500 else 1
    return 0

# ---- LED ----
LED = Pin(2, func=Pin.GPIO, dir=Pin.OUT)
LED.off()
_blink_n = 0
_blink_t = 0

def led_start():
    global _blink_n, _blink_t
    _blink_n = 10  # 5次完整亮灭 = ~2秒
    _blink_t = utime.ticks_ms()
    LED.on()

def led_tick():
    global _blink_n, _blink_t
    if _blink_n == 0:
        return False
    if utime.ticks_diff(utime.ticks_ms(), _blink_t) >= 200:
        LED.value(1 - LED.value())
        _blink_n -= 1
        _blink_t = utime.ticks_ms()
        if _blink_n == 0:
            LED.off()
            return False
    return True

# ---- Main ----
def main():
    global PRESS_THRESHOLD, RETURN_DROP
    spi=SPI(0,40000000,polarity=1,phase=0,bits=8,endia=0,sck=Pin(6),mosi=Pin(8))
    disp=st7789.ST7789(spi,SCREEN_W,SCREEN_H,reset=Pin(11,func=Pin.GPIO,dir=Pin.OUT),dc=Pin(7,func=Pin.GPIO,dir=Pin.OUT))
    imu=icm20948.ICM20948(I2C(0,sda=Pin(9),scl=Pin(10),freq=100000),accel_scale=icm20948.GPM_8)
    det=Detector(); dsp=Display(disp); gc.collect()
    print("Hold still...")
    sx=sy=sz=0.0
    for i in range(15):
        imu.dataupdate(); sx+=imu.acc_x(); sy+=imu.acc_y(); sz+=imu.acc_z()
        utime.sleep_ms(30)
    det.set_base(sx/15,sy/15,sz/15); gc.collect()
    for i in range(10):
        imu.dataupdate(); det.update(imu.acc_x(),imu.acc_y(),imu.acc_z())
        utime.sleep_ms(50)
    gc.collect()
    print("Baseline: %d mg  TH:%d Drop:%d"%(int(det.base),PRESS_THRESHOLD,RETURN_DROP))
    print("Short press=Set  Long press=Calibrate")

    app_state = NORMAL
    cd_time = 0
    cal_peaks = []
    lt = utime.ticks_ms()
    blink_done = False  # 标记是否已触发LED闪烁

    while True:
        imu.dataupdate()
        x,y,z=imu.acc_x(),imu.acc_y(),imu.acc_z()
        done,sn,v=det.update(x,y,z)
        if done and app_state == SET_GO:
            print(">> Rep", det.reps)

        # ---- Button ----
        btn = rd_btn()
        if btn > 0:
            if app_state == SET_GO and btn == 1:
                # 计数中短按 → 重置归零重新计
                det.reps = 0
                dsp.show_set(0, SET_REPS)
                print(">> Reset count")
            elif app_state == SET_GO and det.reps == 0 and btn == 2:
                # 计数0时长按 → 重新校准
                app_state = CAL_CD; cd_time = 4
                dsp.show_msg("CALIBRATE", "Do 2 reps")
                cal_peaks = []
                print(">> Re-calibrate")
            elif app_state == NORMAL:
                if btn == 1:
                    app_state = SET_CD; cd_time = 4
                    dsp.show_msg("SET "+str(SET_REPS))
                    print(">> Set mode: count to", SET_REPS)
                else:
                    app_state = CAL_CD; cd_time = 4
                    dsp.show_msg("CALIBRATE", "Do 2 reps")
                    det.reps = 0
                    cal_peaks = []
                    print(">> Calibration: do 2 reps")
            elif app_state == DONE and btn == 1:
                LED.off(); blink_done = False
                app_state = SET_CD; cd_time = 4
                dsp.show_msg("SET "+str(SET_REPS))

        # ---- LED Blink (set complete) ----
        if app_state == DONE and not blink_done:
            blink_done = True
            led_start()

        # ---- App State Machine ----
        now = utime.ticks_ms()

        if app_state == SET_CD:
            if utime.ticks_diff(now, lt) >= 1000:
                cd_time -= 1; lt = now
                if cd_time <= 0:
                    app_state = SET_GO
                    det.reps = 0
                    dsp.show_set(0, SET_REPS)
                else:
                    dsp.show_countdown(cd_time)

        elif app_state == SET_GO:
            if done:
                dsp.show_set(det.reps, SET_REPS)
                if det.reps >= SET_REPS:
                    app_state = DONE
                    dsp.show_done(SET_REPS)
                    print(">> Set complete!")

        elif app_state == CAL_CD:
            if utime.ticks_diff(now, lt) >= 1000:
                cd_time -= 1; lt = now
                if cd_time <= 0:
                    app_state = CAL_GO
                    det.reps = 0
                    dsp.show_cal_peak(len(cal_peaks)+1, 0)
                else:
                    dsp.show_countdown(cd_time)

        elif app_state == CAL_GO:
            if done:
                cal_peaks.append(det.peak)
                print(">> Cal rep", len(cal_peaks), "peak:", int(det.peak))
                if len(cal_peaks) >= 2:
                    avg = sum(cal_peaks) / 2
                    PRESS_THRESHOLD = int(avg * 0.6)
                    RETURN_DROP = int(avg * 0.4)
                    det.th_on = PRESS_THRESHOLD
                    det.th_off = PRESS_THRESHOLD - 5
                    det.reps = 0
                    app_state = NORMAL
                    print("Cal done! TH=%d Drop=%d"%(PRESS_THRESHOLD,RETURN_DROP))
                    dsp.show_msg("CAL DONE", "TH:"+str(PRESS_THRESHOLD))
                    utime.sleep_ms(1500)
                else:
                    dsp.show_cal_peak(len(cal_peaks)+1, cal_peaks[-1])

        elif app_state == NORMAL:
            if utime.ticks_diff(now, lt) >= 2000:
                gc.collect()
                dsp.show_standby()
                lt = now

        # ---- Non-blocking LED blink ----
        if blink_done and not led_tick():
            blink_done = False
            app_state = NORMAL
            dsp.show_standby()

        utime.sleep_ms(5)

if __name__=="__main__": main()
