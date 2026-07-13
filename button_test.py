"""
Dumbbell Press Counter - Button & LED Test

测试按键和 LED 是否正常工作。
接线:
  按键: Pin(12) → GND (按下读到 0)
  LED:  Pin(2)  → 220Ω → GND
"""

from machine import Pin
import utime

btn = Pin(12, func=Pin.GPIO, dir=Pin.IN, pull=Pin.PULL_UP)
led = Pin(2, func=Pin.GPIO, dir=Pin.OUT)
led.off()

print("=== Button + LED Test ===")
print("Press button = LED blinks 3 times")
print("Ctrl+C to exit")
print("")

last = 1
blink_t = 0
blink_cnt = 0

while True:
    try:
        v = btn.value()

        # 按下时启动LED闪烁
        if v == 0 and last == 1:
            blink_cnt = 6  # 3次闪烁 = 6次toggle
            blink_t = utime.ticks_ms()
            print("PRESSED -> LED blink")

        # 非阻塞LED闪烁
        if blink_cnt > 0 and utime.ticks_diff(utime.ticks_ms(), blink_t) >= 150:
            led.value(1 - led.value())
            blink_cnt -= 1
            blink_t = utime.ticks_ms()
            if blink_cnt == 0:
                led.off()

        last = v
        utime.sleep_ms(20)
    except KeyboardInterrupt:
        led.off()
        print("")
        print("Test done!")
        break
