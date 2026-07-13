## Dumbbell Press Counter 🏋️

Waffle Nano  上的哑铃推举计数器。使用 ICM20948 加速度传感器检测推举动作，ST7789 屏幕显示，按键交互 + LED 反馈。

## 文件说明

| 文件 | 说明 |
|------|------|
| `dumbbell_press_counter.py` | **主程序** — 大数字显示 + 按键交互 + 组计数 + LED 反馈 |
| `curve_monitor.py` | **曲线显示器** — 实时加速度滚动曲线（独立运行） |
| `button_test.py` | **测试程序** — 按键和 LED 功能测试 |

## 硬件接线

```
Waffle Nano V1 (板载传感器，无需额外接线即可运行主程序)

外接:
  Pin(2)  ── LED ── 220Ω ── GND     (可选，组完成时闪烁)
  Pin(12) ── 按键 ── GND             (推荐，交互操作)
```

**无需外接任何元件也能运行**，只是只能用串口看计数结果。

## 主程序使用 (`dumbbell_press_counter.py`)

### 操作方式

| 操作 | 功能 |
|------|------|
| **短按** | 开始一组计数（默认 10 次）→ 倒计时 3-2-1 → 开始计数 |
| **计数中短按** | 归零重新计 |
| **计数 0 时长按** | 进入校准：做 2 次推举，自动计算阈值 |
| **待机时长按** | 进入校准模式 |
| 组完成后 | LED 闪烁 2 秒 → 自动回到待机 |

### 屏幕显示

```
待机界面                 计数界面
┌──────────────────┐    ┌──────────────────┐
│    DUMBBELL      │    │    DUMBBELL      │
│   SHORT:SET      │    │                  │
│    10 REPS       │    │       5/10       │ ← 当前/目标
│    LONG:CAL      │    │       SET        │ ← 状态
│      PRESS       │    │      M: 38       │ ← 运动幅值(mg)
└──────────────────┘    └──────────────────┘
```

## 曲线显示器 (`curve_monitor.py`)

独立程序，显示 60 点实时滚动曲线，用于观察加速度信号：

```
┌──────────────────┐
│ M: 32    G: 1002 │ ← 运动幅值 / 重力基线
│      CURVE       │
├──────────────────┤
│                  │
│   ╱╲    ╱╲      │
│  ╱  ╲  ╱  ╲     │ ← 60点滚动曲线
│ ╱    ╲╱    ╲    │
│                  │
└──────────────────┘
```

运行：`import curve_monitor`

## 技术原理

### 检测算法

```
motion = sqrt(ax² + ay² + az²) - gravity_baseline
```

- **总加速度幅值**：方向无关，无论直线还是弧线运动都能检测
- **基线校准**：启动时保持静止 1 秒自动计算
- **基线自适应**：静止时缓慢跟踪漂移

### 状态机

```
IDLE → PRESSING → RETURNING → LOCKED → IDLE (计数+1)
  ↑        ↑           ↑         ↑
  │   运动>阈值   从峰值回落  锁定300ms
  │     +方向上升  >Drop阈值  防反弹
```

### 防抖机制

| 机制 | 说明 |
|------|------|
| 方向验证 | 必须经历上升 → 下降才算有效 |
| 最低动作时间 | 300ms 内不重复触发 |
| 峰值超时 | 1500ms 无变化自动重置 |
| 计数后锁定 | 300ms 内不响应任何信号 |

### 校准模式

长按进入，做 2 次标准推举，系统自动计算：

```
TH (触发阈值)   = 平均峰值 × 0.6
Drop (回落阈值) = 平均峰值 × 0.4
Reset (复位阈值) = -平均峰值 × 0.3
```

## 参数调节

打开 `dumbbell_press_counter.py` 修改顶部常量：

```python
PRESS_THRESHOLD = 30    # 触发阈值
RETURN_DROP = 20        # 回落阈值
RESET_THRESHOLD = -20   # 复位阈值
MIN_CYCLE_TIME = 300    # 最小动作周期(ms)
MIN_REP_TIME = 300      # 推举间隔(ms)
PEAK_TIMEOUT = 1500     # 峰值超时(ms)
ALPHA = 0.3             # 滤波系数(0-1)
LOCK_MS = 300           # 计数后锁定(ms)
SET_REPS = 10           # 每组次数
```

## 测试

先上传 `button_test.py` 测试按键和 LED：

```python
import button_test
# 按按键 → LED 闪烁 3 次 + 串口输出
```

## 参考

- [Waffle Nano V1 Python API 文档](https://gitee.com/blackwalnutlabs/waffle_nano_v1_python_api_document)
- [ICM20948](https://invensense.tdk.com/products/motion-tracking/9-axis/icm-20948/) | [ST7789](https://cdn.sparkfun.com/assets/learn_tutorials/1/3/6/6/ST7789_V2.0.pdf)
