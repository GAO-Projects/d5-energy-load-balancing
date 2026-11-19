from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Awaitable, Dict, Optional

@dataclass
class PowerReading:
    channel_id: int        # 1: Essential Fan, 2: Flexible Fan, 3: LED Strip
    asset_name: str
    sensor_mac: str
    sequence: int
    voltage_v: float
    current_a: float
    watts: float
    duty_pct: int
    rssi: int
    timestamp: float
    quality_flag: str = "OK"

@dataclass
class ActuatorCommand:
    command_id: str
    ch1_essential_pct: int
    ch2_flexible_pct: int
    ch3_led_pct: int
    expiry_ts: float

class TelemetrySource(ABC):
    @abstractmethod
    async def start(self, on_reading: Callable[[PowerReading], Awaitable[None]]) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

class ActuatorSink(ABC):
    @abstractmethod
    async def send_pwm(self, cmd: ActuatorCommand) -> str:
        """Returns ACK status: ACCEPTED, DUPLICATE_IGNORED, or ERROR."""
        pass