<p align="center">
  <img src="logo.png" alt="Broad Logo" width="260">
</p>

# 远大新风肺保 (FF100-Pro) Home Assistant 自定义集成

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

本集成是专为 **远大新风肺保 (Broad AirPro Fresh FF100-Pro / FF100 系列)** 开发的 Home Assistant 自定义组件，通过远大官方 IoT 云端 API 实现对新风设备的完整状态监控与智能控制。

---

## 📱 支持机型

- **远大新风肺保 FF100-Pro** (推荐)
- 远大新风肺保 FF100 / FF100-PLUS 系列
- *注：FE6 系列（6 档风速机型）请使用原版 FE6 插件。*

---

## ✨ 功能特性与实体清单

### 1. 风扇控制实体 (`fan.<设备名称>`)
- **开关机控制**：支持远程开机与关机（`sjx: 3` / `sjx: 2`）。
- **3 档风速调节**：支持 1 档、2 档、3 档无缝调速（`sjx: 4`，对应 HA 百分比 33%、67%、100%）。
- **预设模式联动**：支持 `1`、`2`、`3` 档及 `sleep`（睡眠档）预设模式。
- **指示灯状态映射**：实时上报档位与指示灯颜色及呼吸状态（1档蓝光、2档绿光、3档黄光、睡眠档浅绿呼吸灯）。

### 2. 功能开关实体 (`switch.<设备名称>_*`)
- **睡眠模式开关** (`switch.<设备名称>_sleep_mode`)：一键开启或关闭极静音睡眠档（`sjx: 5`）。
- **室内净化模式** (`switch.<设备名称>_indoor_purification`)：开启或关闭室内空气循环净化模式（`sjx: 19`，硬件支持时自动呈现）。

### 3. 滤芯清零按钮 (`button.<设备名称>_*`)
- **重置HEPA高效滤芯计时** (`button.<设备名称>_reset_hepa_filter`)：更换全新 HEPA高效滤芯后点击清零已用计时（`sjx: 8`）。
- **重置粗效滤芯计时** (`button.<设备名称>_reset_coarse_filter`)：清洗装回粗效滤芯后点击清零已用计时（`sjx: 9`）。

### 4. 滤芯寿命周期设定 (`number.<设备名称>_*`)
- **粗效滤芯清洗周期** (`number.<设备名称>_coarse_filter_cycle`)：设定粗效滤芯清洗周期（`sjx: 7`，范围 168~2160 小时，默认 500h/720h）。
- **HEPA高效滤芯更换周期** (`number.<设备名称>_hepa_filter_cycle`)：设定 HEPA高效滤芯更换周期（`sjx: 6`，范围 2000~10000 小时，默认 3000h）。

### 5. 二进制状态传感器 (`binary_sensor.<设备名称>_*`)
- **故障报警监测** (`binary_sensor.<设备名称>_problem`)：当设备自检到故障时自动变为 `on`，方便用于 HA 异常通知自动化。
- **云端在线状态** (`binary_sensor.<设备名称>_connectivity`)：实时反馈设备与云端的连接连通性。

### 6. 遥测与滤芯寿命传感器 (`sensor.<设备名称>_*`)
- **实时风量** (`sensor.<设备名称>_air_volume`)：出风量监测（单位：m³/h）。
- **风速档位** (`sensor.<设备名称>_speed_level`)：当前运行档位（1~3 档，睡眠模式显示 0 档）。
- **故障诊断状态** (`sensor.<设备名称>_fault_status`)：实时故障解析文本（正常显示 `Normal`，故障时显示具体原因如 `粗效清洗提醒`、`新风机故障`）。
- **HEPA高效滤芯剩余寿命** (`sensor.<设备名称>_hepa_filter_life`)：HEPA高效滤芯剩余寿命百分比（%）。
- **HEPA高效滤芯已用时长** (`sensor.<设备名称>_hepa_filter_used`)：HEPA高效滤芯累计工作时长（小时，默认禁用，可在实体设置中手动启用）。
- **粗效滤芯剩余寿命** (`sensor.<设备名称>_coarse_filter_life`)：粗效滤芯清洗周期剩余百分比（%）。
- **粗效滤芯已用时长** (`sensor.<设备名称>_coarse_filter_used`)：粗效滤芯累计工作时长（小时，默认禁用，可在实体设置中手动启用）。

---

## 🛠️ 安装方法

### 方法一：通过 HACS 商店安装（推荐）

1. 打开 Home Assistant 的 **HACS** 商店。
2. 点击右上角的三个点，选择 **“自定义存储库” (Custom repositories)**。
3. 输入本仓库地址 `https://github.com/dq19871123/broadair_FF100Pro_HACS`，类别选择 **“集成” (Integration)**，点击 **“添加”**。
4. 在 HACS 中搜索 **“Broad Fresh Air (FF100-Pro)”** 并点击安装。
5. **重启 Home Assistant**。

### 方法二：手动安装

1. 下载本仓库源码。
2. 将项目目录重命名为 `broadair`，拷贝至 Home Assistant 的配置目录中：
   ```text
   config/custom_components/broadair/
   ```
3. **重启 Home Assistant**。

---

## ⚙️ 配置与接入

1. 在 Home Assistant 中进入 **“设置”** → **“设备与服务”** → **“添加集成”**。
2. 搜索并选择 **“远大新风肺保 (FF100-Pro)”**（Broad Fresh Air）。
3. 输入您的远大空气管家 **手机号** 与 **密码**。
4. 在弹出的设备列表中选择您要接入的新风肺保设备，点击完成。

> [!NOTE]
> 集成内置了 Token 自动重登机制。若会话长期过期，HA 会提示“重新认证”，只需重新输入密码即可无缝恢复。

---

## 📋 云端控制协议参考 (FF100-Pro DTU)

| 控制指令代码 (`sjx`) | 附加参数 (`cs`) | 对应操作说明 |
| :---: | :---: | :--- |
| `1` | `""` | 实时同步并查询设备当前状态 |
| `2` | `""` | 关机 |
| `3` | `""` | 开机 |
| `4` | `"1"` / `"2"` / `"3"` | 设定风速档位（1~3 档） |
| `5` | `"1"` / `"0"` | 开启 / 关闭睡眠模式 |
| `6` | `"2000"`~`"10000"` | 设定 HEPA高效滤芯更换周期（小时） |
| `7` | `"168"`~`"2160"` | 设定粗效滤芯清洗周期（小时） |
| `8` | `"1"` | HEPA高效滤芯已用计时清零 |
| `9` | `"1"` | 粗效滤芯已用计时清零 |
| `19` | `"1"` / `"0"` | 开启 / 关闭室内净化循环送风模式 |

---

## ❤️ 特别致谢 (Acknowledgements)

- 本项目基于 [bdcrrbb/broadair_FE6Pro_HACS](https://github.com/bdcrrbb/broadair_FE6Pro_HACS) 进行二次开发与 FF100-Pro 专属适配，由衷感谢原作者在架构与协议逆向上的开源贡献！
- 感谢开源社区所有为智能家居生态做出贡献的开发者。

---

## 📄 免责声明 (Disclaimer)

本集成是独立的开源项目，非远大科技集团（Broad Group）官方出品，亦未获得其官方赞助或背书。请在遵守当地法律法规的前提下合理使用。

## 📜 开源协议

本项目采用 [MIT License](LICENSE) 授权许可。
