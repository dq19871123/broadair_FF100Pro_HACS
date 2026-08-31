"""风扇实体平台 - 远大新风肺保 (FF100-Pro).

本模块将远大新风肺保设备映射为标准的 Home Assistant Fan 实体：
- 开关机控制 (Turn On / Turn Off)
- 3 档风速调节 (Speed 1~3, 映射至百分比 33%, 67%, 100%)
- 预设模式联动 (Preset Modes: 1, 2, 3, sleep)
- 睡眠模式与普通档位之间的互斥与状态恢复
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_MAC,
    CONF_DEVICE_MODEL,
    CONF_DEVICE_NAME,
    DOMAIN,
    FAN_SPEED_COUNT,
    FIELD_GEAR,
    FIELD_POWER,
    FIELD_RUNNING_GEAR,
    FIELD_SLEEP_MODE,
)
from .coordinator import BroadAirCoordinator

_LOGGER = logging.getLogger(__name__)

# 预设模式标识定义
PRESET_MODE_SLEEP = "sleep"
PRESET_MODES = ["1", "2", "3", PRESET_MODE_SLEEP]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """通过 ConfigEntry 异步初始化并注册 Fan 实体."""
    coordinator: BroadAirCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BroadAirFan(coordinator, entry)])


class BroadAirFan(CoordinatorEntity[BroadAirCoordinator], FanEntity):
    """远大新风肺保 FF100-Pro 风扇实体实现类."""

    # 实体命名直接沿用设备主名称
    _attr_has_entity_name = True
    _attr_name = None

    # 支持的功能特性声明：调速、预设模式、开关控制
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    # 声明总档位数为 3 (对应百分比步长约 33.3%)
    _attr_speed_count = FAN_SPEED_COUNT
    _attr_preset_modes = PRESET_MODES

    def __init__(
        self,
        coordinator: BroadAirCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """初始化风扇实体.

        Args:
            coordinator: 数据同步调度器
            entry: 当前集成的配置项条目
        """
        super().__init__(coordinator)

        self._device_id = entry.data[CONF_DEVICE_ID]
        self._attr_unique_id = f"{self._device_id}_fan"

        # 注册设备信息 (使同一设备下的传感器、开关、风扇聚合在同一个设备卡片中)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=entry.data.get(CONF_DEVICE_NAME, "Broad Fresh Air"),
            manufacturer="Broad (远大)",
            model=entry.data.get(CONF_DEVICE_MODEL, "FF100-Pro"),
        )

        # 若存在 MAC 地址则添加网络连接标识
        mac = entry.data.get(CONF_DEVICE_MAC)
        if mac:
            self._attr_device_info["connections"] = {("mac", mac)}

    @property
    def is_on(self) -> bool | None:
        """读取设备当前开关机状态 (FB_ON: 1 为开机, 0 为关机)."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(FIELD_POWER) == "1"

    @property
    def is_sleep_mode(self) -> bool:
        """判断当前是否正处于睡眠模式 (FB_SLEEPMODEL_ON: 1 为开启)."""
        if self.coordinator.data is None:
            return False
        return self.coordinator.data.get(FIELD_SLEEP_MODE) == "1"

    @property
    def preset_mode(self) -> str | None:
        """获取当前预设模式.

        若处于睡眠模式则返回 'sleep'，否则返回当前运行档位 ('1', '2', '3')。
        """
        if self.coordinator.data is None:
            return None

        if self.is_sleep_mode:
            return PRESET_MODE_SLEEP

        gear = self.coordinator.data.get(FIELD_GEAR) or self.coordinator.data.get(
            FIELD_RUNNING_GEAR
        )

        if gear and str(gear) in ("1", "2", "3"):
            return str(gear)

        return None

    @property
    def percentage(self) -> int | None:
        """计算当前风速对应的百分比数值 (0~100%).

        - 关机: 0%
        - 睡眠档 / 1 档: 33%
        - 2 档: 67%
        - 3 档: 100%
        """
        if not self.is_on:
            return 0

        if self.coordinator.data is None:
            return None

        # 睡眠模式下转速极低，按 1 档百分比显示
        if self.is_sleep_mode:
            return round(1 * 100 / FAN_SPEED_COUNT)

        gear = self.coordinator.data.get(FIELD_GEAR) or self.coordinator.data.get(
            FIELD_RUNNING_GEAR
        )

        if gear is None:
            return None

        try:
            gear_int = int(gear)
            gear_int = max(1, min(FAN_SPEED_COUNT, gear_int))
            return round(gear_int * 100 / FAN_SPEED_COUNT)
        except (ValueError, TypeError):
            _LOGGER.warning("解析风速档位异常，原始值为: %s", gear)
            return None

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """开机指令处理.

        支持开机的同时指定目标百分比或预设模式。
        """
        _LOGGER.debug(
            "开启新风设备 %s (目标百分比=%s, 目标预设=%s)",
            self._device_id,
            percentage,
            preset_mode,
        )

        # 1. 先下发开机指令
        await self.coordinator.client.set_power(self._device_id, True)

        # 2. 如果携带了目标预设模式
        if preset_mode == PRESET_MODE_SLEEP:
            await self.coordinator.client.set_sleep_mode(self._device_id, True)
        elif preset_mode is not None and preset_mode in ("1", "2", "3"):
            if self.is_sleep_mode:
                await self.coordinator.client.set_sleep_mode(self._device_id, False)
            await self.coordinator.client.set_speed(self._device_id, int(preset_mode))
        # 3. 如果携带了目标速度百分比
        elif percentage is not None and percentage > 0:
            if self.is_sleep_mode:
                await self.coordinator.client.set_sleep_mode(self._device_id, False)
            speed = max(1, min(FAN_SPEED_COUNT, round(percentage * FAN_SPEED_COUNT / 100)))
            await self.coordinator.client.set_speed(self._device_id, speed)

        # 立即触发状态轮询更新
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """关机指令处理."""
        _LOGGER.debug("关闭新风设备 %s", self._device_id)

        await self.coordinator.client.set_power(self._device_id, False)
        await self.coordinator.async_request_refresh()

    async def async_set_percentage(self, percentage: int) -> None:
        """设定风速百分比 (Home Assistant 滑块控制).

        将 0~100% 映射到 1~3 档：
        - percentage == 0: 关机
        - 1%~33%: 1 档
        - 34%~66%: 2 档
        - 67%~100%: 3 档
        """
        _LOGGER.debug("设置设备 %s 目标百分比为 %d%%", self._device_id, percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        # 换算为 1~3 档位
        speed = max(1, min(FAN_SPEED_COUNT, round(percentage * FAN_SPEED_COUNT / 100)))

        # 若当前为关机状态，先执行开机
        if not self.is_on:
            await self.coordinator.client.set_power(self._device_id, True)

        # 若当前正处于睡眠模式，设置新风速前需先退出睡眠模式
        if self.is_sleep_mode:
            await self.coordinator.client.set_sleep_mode(self._device_id, False)

        await self.coordinator.client.set_speed(self._device_id, speed)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """切换预设模式 (1, 2, 3, sleep)."""
        _LOGGER.debug("设置设备 %s 预设模式为 %s", self._device_id, preset_mode)

        if preset_mode not in PRESET_MODES:
            _LOGGER.error("非法的预设模式: %s (支持列表: %s)", preset_mode, PRESET_MODES)
            return

        # 若当前关机，先执行开机
        if not self.is_on:
            await self.coordinator.client.set_power(self._device_id, True)

        if preset_mode == PRESET_MODE_SLEEP:
            # 开启睡眠模式
            await self.coordinator.client.set_sleep_mode(self._device_id, True)
        else:
            # 切换为指定常规档位 (若此前在睡眠模式则退出)
            if self.is_sleep_mode:
                await self.coordinator.client.set_sleep_mode(self._device_id, False)
            await self.coordinator.client.set_speed(self._device_id, int(preset_mode))

        await self.coordinator.async_request_refresh()
