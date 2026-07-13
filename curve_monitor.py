#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
加速度实时曲线显示器
独立于主程序运行，实时显示总加速度幅值的滚动曲线。

使用: 直接运行即可
  import curve_monitor
"""
from machine import I2C, SPI, Pin
import icm20948, utime, math, st7789, gc

SCREEN_W, SCREEN_H = 240, 240
CURVE_N = 60          # 曲线点数
CURVE_OFF = 128       # bytearray 偏移量

# ---- 5x7 Font ----
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

# ---- Curve Display ----
class CurveDisplay:
    def __init__(self, d):
        self.d = d; d.init(); d.fill(st7789.color565(0,0,0))
        self.BG = st7789.color565(0,0,0)
        self.WH = st7789.color565(255,255,255)
        self.GR = st7789.color565(60,255,60)
        self.CY = st7789.color565(60,255,255)
        self.GY = st7789.color565(100,100,100)
        self.DK = st7789.color565(40,40,40)
        self.RD = st7789.color565(80,30,30)
        self.BL = st7789.color565(30,30,80)
        # 曲线区域
        self.x1, self.y1 = 10, 50
        self.x2, self.y2 = 230, 220
        self.w = self.x2 - self.x1
        self.h = self.y2 - self.y1
        self.my = self.y1 + self.h // 2
        # 曲线缓冲
        self.cv = bytearray(CURVE_N)
        self.ci = 0
        self._ui()

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

    def _ui(self):
        d = self.d
        d.line(self.x1,self.y1,self.x2,self.y1,self.GY)
        d.line(self.x2,self.y1,self.x2,self.y2,self.GY)
        d.line(self.x2,self.y2,self.x1,self.y2,self.GY)
        d.line(self.x1,self.y2,self.x1,self.y1,self.GY)
        d.line(self.x1, self.my, self.x2, self.my, self.DK)

    def mid(self, text, s): return (SCREEN_W - len(text) * 6 * s) // 2

    def _map(self, v):
        r = (v + 200) / 400.0
        if r < 0: r = 0
        if r > 1: r = 1
        return self.y2 - int(r * self.h)

    def update(self, acc_x, acc_y, acc_z, baseline):
        d = self.d
        # 计算总幅值
        total = math.sqrt(acc_x*acc_x + acc_y*acc_y + acc_z*acc_z)
        motion = total - baseline
        # 存曲线
        cv = int(motion) + CURVE_OFF
        if cv < 0: cv = 0
        if cv > 255: cv = 255
        self.cv[self.ci] = cv
        self.ci = (self.ci + 1) % CURVE_N
        # 清空曲线区
        d.fill_rect(self.x1+1, self.y1+1, self.w-1, self.h-1, self.BG)
        # 零线
        d.line(self.x1, self.my, self.x2, self.my, self.DK)
        # 画曲线
        step = self.w // (CURVE_N - 1)
        px, py = -1, -1
        for i in range(CURVE_N):
            idx = (self.ci + i) % CURVE_N
            cv = self.cv[idx] - CURVE_OFF
            cx = self.x1 + i * step
            cy = self._map(cv)
            if px >= 0:
                d.line(px, py, cx, cy, self.GR)
            px, py = cx, cy
        # 边框
        d.line(self.x1,self.y1,self.x2,self.y1,self.GY)
        d.line(self.x2,self.y1,self.x2,self.y2,self.GY)
        d.line(self.x2,self.y2,self.x1,self.y2,self.GY)
        d.line(self.x1,self.y2,self.x1,self.y1,self.GY)
        # 文字信息（顶部）
        d.fill_rect(0, 0, SCREEN_W, 45, self.BG)
        val_s = self._i2s(int(motion))
        bl_s = self._i2s(int(baseline))
        self._txt("M:"+val_s, self._mid("M:"+val_s, 1), 5, self.CY, 1)
        self._txt("G:"+bl_s, self._mid("G:"+bl_s, 1), 18, self.GY, 1)
        self._txt("CURVE", self._mid("CURVE", 1), 31, self.GY, 1)


# ---- Main ----
def main():
    spi = SPI(0, 40000000, polarity=1, phase=0, bits=8,
              endia=0, sck=Pin(6), mosi=Pin(8))
    disp = st7789.ST7789(spi, SCREEN_W, SCREEN_H,
                         reset=Pin(11, func=Pin.GPIO, dir=Pin.OUT),
                         dc=Pin(7, func=Pin.GPIO, dir=Pin.OUT))
    imu = icm20948.ICM20948(
        I2C(0, sda=Pin(9), scl=Pin(10), freq=100000),
        accel_scale=icm20948.GPM_8)
    dsp = CurveDisplay(disp)
    gc.collect()

    # 重力基线校准
    print("Calibrating baseline (hold still)...")
    sx = sy = sz = 0.0
    for i in range(20):
        imu.dataupdate()
        sx += imu.acc_x(); sy += imu.acc_y(); sz += imu.acc_z()
        utime.sleep_ms(30)
    bx = sx / 20; by = sy / 20; bz = sz / 20
    base = math.sqrt(bx*bx + by*by + bz*bz)
    gc.collect()
    print("Baseline: %d mg" % int(base))
    print("Monitoring...")

    lt = utime.ticks_ms()
    while True:
        imu.dataupdate()
        x = imu.acc_x(); y = imu.acc_y(); z = imu.acc_z()
        now = utime.ticks_ms()
        if utime.ticks_diff(now, lt) >= 50:
            gc.collect()
            dsp.update(x, y, z, base)
            lt = now
        utime.sleep_ms(5)


if __name__ == "__main__":
    main()
