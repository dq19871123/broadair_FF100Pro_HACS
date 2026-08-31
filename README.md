# 远大新风肺保 (FF100-Pro) Home Assistant 自定义集成

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

本集成是专为 **远大新风肺保 (Broad AirPro Fresh FF100-Pro / FF100 系列)** 开发的 Home Assistant 自定义组件，通过远大官方 IoT 云端 API 实现对新风设备的完整状态监控与智能控制。

---

## 📱 支持机型

- **远大新风肺保 FF100-Pro** (推荐)
- 远大新风肺保 FF100 / FF100-PLUS 系列
- *注：FE6 系列（6 档风速）请使用原版 FE6 插件。*

---

## ✨ 功能特性与实体清单

### 1. 风扇控制实体 (`fan.<设备名称>`)
- **开关机控制**：支持远程开机与关机（`sjx: 3` / `sjx: 2`）。
- **3 档风速调节**：支持 1 档、2 档、3 档无缝调速（`sjx: 4`，对应 HA 百分比 33%、67%、100%）。
- **预设模式联动**：支持 `1`、`2`、`3` 档及 `sleep`（睡眠档）预设模式。

### 2. 功能开关实体 (`switch.<设备名称>_*`)
- **睡眠模式开关** (`switch.<设备名称>_sleep_mode`)：一键开启或关闭极静音睡眠档（`sjx: 5`）。
- **自动模式开关** (`switch.<设备名称>_auto_mode`)：开启或关闭设备根据环境指标自动调速（`sjx: 18`）。
- **室内净化模式** (`switch.<设备名称>_indoor_purification`)：开启或关闭室内空气循环净化模式（`sjx: 19`，硬件支持时自动呈现）。

### 3. 滤网清零按钮 (`button.<设备名称>_*`)
- **重置 HEPA 滤芯计时** (`button.<设备名称>_reset_hepa_filter`)：更换全新 HEPA 高效滤芯后点击清零已用计时（`sjx: 8`）。
- **重置粗效滤网计时** (`button.<设备名称>_reset_coarse_filter`)：清洗装回粗效滤网后点击清零已用计时（`sjx: 9`）。

### 4. 二进制状态传感器 (`binary_sensor.<设备名称>_*`)
- **故障报警监测** (`binary_sensor.<设备名称>_problem`)：当设备自检到故障时自动变为 `on`，方便用于 HA 异常通知自动化。
- **云端在线状态** (`binary_sensor.<设备名称>_connectivity`)：实时反馈设备与云端的连接连通性。

### 5. 遥测与滤网寿命传感器 (`sensor.<设备名称>_*`)
- **实时风量** (`sensor.<设备名称>_air_volume`)：出风量监测（单位：$m^3/h$）。
- **风速档位** (`sensor.<设备名称>_speed_level`)：当前运行档位（1~3 档，睡眠模式显示 0 档）。
- **故障诊断状态** (`sensor.<设备名称>_fault_status`)：实时故障解析文本（正常显示 `Normal`，故障时显示具体原因如 `PM2.5故障`）。
- **HEPA 滤芯剩余寿命** (`sensor.<设备名称>_hepa_filter_life`)：高效滤网剩余寿命百分比（%）。
- **HEPA 滤芯已用时长** (`sensor.<设备名称>_hepa_filter_used`)：高效滤网累计工作时长（小时）。
- **粗效滤网剩余寿命** (`sensor.<设备名称>_coarse_filter_life`)：初效/粗效滤网清洗周期剩余百分比（%）。
- **粗效滤网已用时长** (`sensor.<设备名称>_coarse_filter_used`)：初效滤网累计工作时长（小时）。
- **静电除尘器寿命** (`sensor.<设备名称>_duster_filter_life`)：静电除尘器剩余寿命百分比（选配时自动激活）。

### 6. 环境空气质量传感器（根据硬件选配件动态适配）
- **PM2.5 激光颗粒浓度** (`sensor.<设备名称>_pm25`)：实时室内粉尘浓度（$\mu g/m^3$，附带空气质量优良等级评定）。
- **二氧化碳浓度** (`sensor.<设备名称>_co2`)：CO2 浓度值（ppm）。
- **室内温度** (`sensor.<设备名称>_temperature`)：室内温度检测（℃，已自动除以 10 修正）。

---

## 🛠️ 安装方法

### 方法一：通过 HACS 商店安装（推荐）

1. 打开 Home Assistant 的 **HACS** 商店。
2. 点击右上角的三个点，选择 **“自定义存储库” (Custom repositories)**。
3. 输入本仓库的 GitHub URL，类别选择 **“集成” (Integration)**，点击 **“添加”**。
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
| `8` | `"1"` | 高效 HEPA 滤芯已用计时清零 |
| `9` | `"1"` | 初效粗效滤网已用计时清零 |
| `18` | `"1"` / `"0"` | 开启 / 关闭自动调节模式 |
| `19` | `"1"` / `"0"` | 开启 / 关闭室内净化循环送风模式 |

---

## ❤️ 特别致谢 (Acknowledgements)

- 本项目基于 [bdcrrbb/broadair_FE6Pro_HACS](https://github.com/bdcrrbb/broadair_FE6Pro_HACS) 进行二次开发与 FF100-Pro 专属适配，由衷感谢原作者在架构与协议逆向上的开源贡献！
- 感谢开源社区所有为智能家居生态做出贡献的开发者。

---

## 📄 免责声明 (Disclaimer)

本集成是独立的开源项目，非远大科技集团（Broad Group）官方出品，亦未获得其官方赞助或背书。请在遵守当地法律法规的前提下合理使用。

## 📜 开源协议

本项目采用 [MIT License](file:///C:/Data/Sourcecode/broadair_FF100Pro_HACS/LICENSE) 授权许可。
