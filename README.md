# Dumbbell Press Counter 

Waffle Nano V1 上的哑铃推举计数器。使用 ICM20948 加速度传感器检测推举动作，ST7789 屏幕显示计数，支持按键交互和 LED 反馈。

## 功能

- **总加速度幅值检测**：`sqrt(ax² + ay² + az²) - 重力基线`，方向无关
- **自动重力校准**：启动时保持静止即可
- **组计数模式**：短按按键开始一组（默认10次），自动停止
- **LED 反馈**：组完成时 LED 闪烁 2 秒
- **自动待机**：完成组后自动回到待机界面
- **长按校准**：计数为 0 时长按按键，做 2 次推举自动计算阈值
- **计数中重置**：计数过程中短按按键归零重新计
- **实时曲线**：45 点加速度波形滚动显示（已启用时）
- **大数字显示**：全屏大字计数，一目了然

## 硬件需求

| 组件 | 说明 |
|------|------|
| Waffle Nano V1 | OpenHarmony 开发板 |
| ICM20948 | 板载九轴加速度传感器 |
| ST7789 | 板载 240×240 TFT 显示屏 |
| 按键 ×1 | 接 Pin(12)，另一脚接 GND |
| LED ×1 | 接 Pin(2) → 电阻(220Ω) → GND |

## 接线

```
Waffle Nano V1
┌─────────────────────┐
│                     │
│  Pin(2)  ──── LED ──┴─── GND    (LED 反馈)
│  Pin(12) ──── 按键 ──── GND    (用户交互)
│                     │
│  Pin(9)  ──── SDA  │  (板载 ICM20948)
│  Pin(10) ──── SCL  │
│                     │
│  Pin(6)  ──── SCK  │
│  Pin(7)  ──── DC   │  (板载 ST7789)
│  Pin(8)  ──── MOSI │
│  Pin(11) ──── RST  │
└─────────────────────┘
```

## 快速开始

### 1. 上传文件到设备

将以下文件上传到 Waffle Nano：

```
dumbbell_press_counter.py   # 主程序
button_test.py              # 按键/LED 测试（可选）
```

### 2. 测试按键和 LED（可选）

```python
import button_test
```

按下按键看 LED 是否闪烁，串口输出 `PRESSED` / `RELEASED`。

### 3. 运行主程序

```python
import dumbbell_press_counter
```

或保存为 `main.py` 上电自动运行。

### 4. 使用方式

| 操作 | 功能 |
|------|------|
| **短按** | 开始一组计数（默认10次） |
| **计数中短按** | 归零重新计 |
| **计数0时长按** | 重新校准阈值（做2次推举） |
| **待机时长按** | 校准模式 |

## 文件说明

| 文件 | 用途 |
|------|------|
| `dumbbell_press_counter.py` | 主程序 |
| `button_test.py` | 按键和 LED 测试程序 |
| `README.md` | 本文件 |

## 技术细节

### 检测原理

```
motion = sqrt(ax² + ay² + az²) - gravity_baseline
```

- 总加速度幅值不受传感器方向影响
- 无论直线还是弧线运动都能检测
- 重力基线在启动时校准，运行时缓慢自适应

### 状态机

```
IDLE → PRESSING → RETURNING → LOCKED → IDLE (计数+1)
```

- IDLE: 等待运动超过阈值
- PRESSING: 追踪峰值
- RETURNING: 检测回落
- LOCKED: 计数后锁定 300ms 防反弹

### 防抖机制

- 方向验证（rising / falling）
- 最低动作时间（MIN_CYCLE_TIME = 300ms）
- 峰值超时重置（PEAK_TIMEOUT = 1500ms）
- 计数后锁定（LOCK_MS = 300ms）

### 显示布局

```
待机界面:
┌──────────────────┐
│    DUMBBELL      │
│   SHORT:SET      │
│    10 REPS       │
│    LONG:CAL      │
│      PRESS       │
└──────────────────┘

计数界面:
┌──────────────────┐
│    DUMBBELL      │
│                  │
│       5/10       │  ← 当前/目标
│                  │
│       SET        │  ← 组模式
│      M: 38       │  ← 运动幅值
└──────────────────┘
```

## 参数调节

在文件顶部可修改：

```python
PRESS_THRESHOLD = 30   # 触发推举的阈值
RETURN_DROP = 20       # 回落判定阈值
RESET_THRESHOLD = -20  # 复位阈值
MIN_CYCLE_TIME = 300   # 最小动作周期(ms)
MIN_REP_TIME = 300     # 最小推举间隔(ms)
PEAK_TIMEOUT = 1500    # 峰值超时(ms)
ALPHA = 0.3            # 低通滤波系数 (0-1)
```

## 参考

- [Waffle Nano V1 Python API 文档](https://gitee.com/blackwalnutlabs/waffle_nano_v1_python_api_document)
- [ICM20948 数据手册](https://invensense.tdk.com/products/motion-tracking/9-axis/icm-20948/)
- [ST7789 数据手册](https://cdn.sparkfun.com/assets/learn_tutorials/1/3/6/6/ST7789_V2.0.pdf)
