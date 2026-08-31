"""常量定义模块 - 远大新风肺保 (FF100-Pro).

本模块定义了与远大云端服务器通信所需的全部常量，包括：
- API 接口地址与请求路径
- 云端下发控制指令编号 (sjx)
- 状态字段键名映射 (与远大官方 App 反编译数据字典一致)
- 硬件运行参数及安全边界约束
"""
from datetime import timedelta
from typing import Final

# -----------------------------------------------------------------------------
# 集成基础信息
# -----------------------------------------------------------------------------
DOMAIN: Final = "broadair"

# -----------------------------------------------------------------------------
# 远大云端 API 地址配置
# -----------------------------------------------------------------------------
# 官方服务器主机名与端口 (远大 IoT 云平台)
API_HOST: Final = "broadair.remotcon.mobi"
API_PORT: Final = 8201
API_BASE_URL: Final = f"https://{API_HOST}:{API_PORT}"

# 客户端固定 AppToken (用于登录接口计算 MD5 签名 Sign)
APP_TOKEN: Final = "8q7l82AxXB8Qo99vesUUvy1ED5tIuPT31NoIL6ZE5THH7clkfN"

# -----------------------------------------------------------------------------
# API 路由端点
# -----------------------------------------------------------------------------
# 用户登录接口
ENDPOINT_LOGIN: Final = "/api/System/Login"
# 获取名下绑定设备列表
ENDPOINT_DEVICES: Final = "/api/Equipment/GetEquipments"
# 获取肺保设备缓存状态 (GetFreshLung)
ENDPOINT_CACHE: Final = "/api/Equipment/GetFreshLung"
# 控制肺保设备 / 查询实时状态 (SetFreshLung)
ENDPOINT_CONTROL: Final = "/api/Equipment/SetFreshLung"

# -----------------------------------------------------------------------------
# 云端控制指令编号 (sjx: 数据项代码)
# 对应 SetFreshLung 接口中的 sjx 参数
# -----------------------------------------------------------------------------
# 刷新/同步设备实时状态 (cs: "")
CMD_POLL: Final = "1"
# 关机 (cs: "")
CMD_POWER_OFF: Final = "2"
# 开机 (cs: "")
CMD_POWER_ON: Final = "3"
# 设定风速档位 (cs: "1"~"3")
CMD_SET_SPEED: Final = "4"
# 设定睡眠模式 (cs: "1" 开启, "0" 关闭)
CMD_SLEEP_MODE: Final = "5"
# 设定高效滤芯使用寿命周期 (cs: 2000~10000 小时)
CMD_SET_HEPA_CYCLE: Final = "6"
# 设定粗效滤网清洗周期 (cs: 168~2160 小时)
CMD_SET_COARSE_CYCLE: Final = "7"
# 重置高效 HEPA 滤芯已用计时 (cs: "1")
CMD_RESET_HEPA_FILTER: Final = "8"
# 重置初效/粗效滤网已用计时 (cs: "1")
CMD_RESET_COARSE_FILTER: Final = "9"
# 自动调节模式开关 (cs: "1" 开启, "0" 关闭)
CMD_AUTO_MODE: Final = "18"
# 室内净化/循环送风模式开关 (cs: "1" 开启, "0" 关闭)
CMD_INDOOR_PURIFICATION: Final = "19"

# -----------------------------------------------------------------------------
# 运行参数与默认阈值 (针对 FF100-Pro 机型)
# -----------------------------------------------------------------------------
# 轮询刷新间隔 (默认 30 秒向云端同步一次)
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=30)
# FF100-Pro 最大风速档位为 3 档 (1:低速, 2:中速, 3:高速)
FAN_SPEED_COUNT: Final = 3
# 粗效滤网默认清洗周期 (小时)，若设备上报值 <168 则保底取 500
DEFAULT_PRIMARY_FILTER_LIFE: Final = 500
# 高效 HEPA 滤芯默认更换周期 (小时)，若设备上报值 <2000 则保底取 3000
DEFAULT_HEPA_FILTER_LIFE: Final = 3000

# -----------------------------------------------------------------------------
# 配置项键名 (存储于 Home Assistant ConfigEntry 中)
# -----------------------------------------------------------------------------
CONF_TOKEN: Final = "token"
CONF_ACCOUNT: Final = "account"
CONF_PASSWORD: Final = "password"
CONF_DEVICE_ID: Final = "device_id"
CONF_DEVICE_NAME: Final = "device_name"
CONF_DEVICE_MAC: Final = "device_mac"
CONF_DEVICE_MODEL: Final = "device_model"

# -----------------------------------------------------------------------------
# 设备状态数据字段映射 (云端返回的 JSON Key)
# -----------------------------------------------------------------------------
# 开关机状态 ("1": 开机, "0": 关机)
FIELD_POWER: Final = "FB_ON"
# 设定风速档位 ("1"~"3")
FIELD_GEAR: Final = "GEAR_POSITION"
# 实际运行风速档位
FIELD_RUNNING_GEAR: Final = "RUNNING_GEAR"
# 实时出风量 (m³/h)
FIELD_AIR_VOLUME: Final = "AIR_VOLUME"
# 睡眠模式 ("1": 开启, "0": 关闭)
FIELD_SLEEP_MODE: Final = "FB_SLEEPMODEL_ON"
# 自动调节模式 ("1": 开启, "0": 关闭)
FIELD_AUTO_MODE: Final = "FB_AUTOMODEL_ON"
# 室内净化循环模式 ("1": 开启, "0": 关闭)
FIELD_SUPPLY_AIR_MODE: Final = "SUPPLY_AIR_MODE"
# 室内净化模式硬件支持配置 ("1": 支持, "0": 不支持)
FIELD_SUPPLY_AIR_CONFIG: Final = "Supply_Air_Mode_Configuration"
# 故障简码 ("00": 正常)
FIELD_FAULT: Final = "FAULT"
# 完整故障描述列表 (逗号分隔文本，如 "PM2.5故障,新风机故障")
FIELD_ALL_FAULT: Final = "ALLFAULT"
# 异常提醒标识
FIELD_EXCEPTION_REMINDER: Final = "EXCEPTION_REMINDER"

# -----------------------------------------------------------------------------
# 滤网耗材监控字段
# -----------------------------------------------------------------------------
# 高效 HEPA 滤芯总寿命周期 (小时)
FIELD_HEPA_LIFE_CYCLE: Final = "EFFICIENT_LIFE_CYCLE"
# 高效 HEPA 滤芯已使用时长 (小时)
FIELD_HEPA_USED_TIME: Final = "EFFICIENT_USED_TIME"
# 高效 HEPA 滤芯清零时间戳
FIELD_HEPA_TIME_CLEARING: Final = "EFFICIENT_TIME_CLEARING"
# 粗效/初效滤网清洗周期 (小时)
FIELD_PRIMARY_CLEANING_CYCLE: Final = "PRIMARY_CLEANING_CYCLE"
# 粗效/初效滤网已使用时长 (小时)
FIELD_COARSE_USED_TIME: Final = "COARSE_USED_TIME"
# 粗效滤网清零时间戳
FIELD_COARSE_TIME_CLEARING: Final = "COARSE_TIME_CLEARING"
# 静电除尘器清洗周期 (小时)
FIELD_DUSTER_CLEANING_CYCLE: Final = "DUSTER_CLEANING_CYCLE"
# 静电除尘器已使用时长 (小时)
FIELD_DUSTER_USED_TIME: Final = "DUSTER_USED_TIME"
# 静电除尘器清零时间戳
FIELD_DUSTER_TIME_CLEARING: Final = "DUSTER_TIME_CLEARING"

# -----------------------------------------------------------------------------
# 空气质量与环境传感器字段
# -----------------------------------------------------------------------------
# 二氧化碳浓度 (ppm)
FIELD_CO2: Final = "CO2_CONCENTRATION"
# PM2.5 激光粉尘浓度 (μg/m³，FF100-Pro 使用此字段，65535 为无效哨兵值)
FIELD_PM_2_5_DUST: Final = "PM_2_5_DUST_CONCENTRATION"
# 备用 PM2.5 字段
FIELD_PM_2_5: Final = "PM_2_5"
# 室内温度 (原始数值为实际温度的 10 倍，如 250 代表 25.0 ℃)
FIELD_ROOM_TEMP: Final = "ROOM_TEMPERATURE"

# -----------------------------------------------------------------------------
# 硬件选配件安装状态标识 ("1": 已安装, "0": 未安装)
# -----------------------------------------------------------------------------
# 是否安装 CO2 检测模块
FIELD_CO2_MODULE: Final = "CO2_MODULE_ACCESSORIES"
# 是否安装 PM2.5 粉尘检测模块
FIELD_DUST_MODULE: Final = "DUST_MODULE_ACCESSORIES"
# 是否安装温度检测模块
FIELD_TEMP_MODULE: Final = "TEMPERATURE_MODULE_ACCESSORIES"

# -----------------------------------------------------------------------------
# 模块通信故障标志
# -----------------------------------------------------------------------------
FIELD_DUST_MODULE_FAILURE: Final = "DUST_MODULE_COMMUNICATION_FAILURE"
FIELD_TEMP_MODULE_FAILURE: Final = "TEMPERATURE_MODULE_FAILURE"

# -----------------------------------------------------------------------------
# 其他参数设置字段
# -----------------------------------------------------------------------------
# 粉尘调节下限值 (5~100)
FIELD_DUST_REGULATION: Final = "DUST_REGULATION_VALUE"
# 粉尘调节上限值 (5~200)
FIELD_DUST_REGULATION_UP: Final = "DUST_REGULATION_VALUE1"
# 粉尘超标报警阈值
FIELD_DUST_ALARM: Final = "DUST_ALARM_VALUE"
# CO2 调节设定值 (800~4800)
FIELD_CO2_ADJUSTMENT: Final = "CO2_ADJUSTMENT_VALUE"
# CO2 报警阈值 (1000~2000)
FIELD_CO2_ALARM: Final = "CO2_ALARM_VALUE"
# 人离开自动关机时间 (0.5~120 小时)
FIELD_MAN_OFF_TIME: Final = "MAN_OFF_TIME"
# 功能开关位掩码 (包含人离关机、粉尘调节、CO2调节开关状态)
FIELD_OPENING_FUNCTION: Final = "OPENING_FUNCTION"
# 机型分类标识 ("0" 支持人离关机等特定高级设置)
FIELD_TYPE_SELECTION: Final = "TYPE_SELECTION"

# -----------------------------------------------------------------------------
# 设备列表响应字段
# -----------------------------------------------------------------------------
DEVICE_FIELD_ID: Final = "ID"
DEVICE_FIELD_MAC: Final = "MAC"
DEVICE_FIELD_NAME: Final = "Name"
DEVICE_FIELD_MODEL: Final = "EquipmentMode"
DEVICE_FIELD_ONLINE: Final = "Online"
