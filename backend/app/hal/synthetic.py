import asyncio
import random
import time
from typing import Callable, Awaitable, Dict
from app.hal.base import TelemetrySource, ActuatorSink, PowerReading, ActuatorCommand

class SyntheticBenchPlant(TelemetrySource, ActuatorSink):
    """
    High-fidelity synthetic twin of the D5 0.85m x 0.55m bench:
    - Ch 1 (node_01): Essential 12V Guarded Fan (~4.0 W at 100% duty)
    - Ch 2 (node_02): Flexible 12V Guarded Fan (~3.0 W at 100% duty, nonlinear stall below 25%)
    - Ch 3 (node_03): Dimmable 12V SMD2835 LED Strip (~3.0 W at 100% duty)
    - Supports operator load switch surge (+2.2 W), BLE dropout fault injection, and closed-loop PWM response.
    """
    def __init__(self):
        self._running = False
        self.duties: Dict[int, int] = {1: 100, 2: 100, 3: 100}
        self.actual_watts: Dict[int, float] = {1: 4.0, 2: 3.0, 3: 3.0} #WATT ALLOCATION 
        self.sequences: Dict[int, int] = {1: 0, 2: 0, 3: 0} 
        self.extra_demand_switch: bool = False
        self.fault_ble_dropout: bool = False
        self._seen_cmds: set[str] = set()

    async def send_pwm(self, cmd: ActuatorCommand) -> str:
        if time.time() > cmd.expiry_ts:
            return "REJECTED_EXPIRED"
        if cmd.command_id in self._seen_cmds:
            return "DUPLICATE_IGNORED"
        self._seen_cmds.add(cmd.command_id)
        self.duties[1] = cmd.ch1_essential_pct
        self.duties[2] = cmd.ch2_flexible_pct
        self.duties[3] = cmd.ch3_led_pct
        return "ACCEPTED"

#TOGGLE SWITCH
    def _compute_target_watts(self, ch: int) -> float:
        d = self.duties[ch] / 100.0
        if ch == 1:
            base = 4.0 * (d ** 1.15)
            # Operator toggle switch injects +2.2W surge on Ch1 auxiliary bus
            return base + (2.2 if self.extra_demand_switch else 0.0)
        elif ch == 2:
            # Guarded fan stalls below 20% PWM; cubic aerodynamic power curve
            return 0.0 if d < 0.20 else 3.0 * (d ** 1.25)
        else:
            # LED strip linear PWM dimming
            return 3.0 * d

    async def start(self, on_reading: Callable[[PowerReading], Awaitable[None]]) -> None:
        self._running = True
        assets = {
            1: ("P1_Essential_Fan", "AA1122334401"),
            2: ("P2_Flexible_Fan", "AA1122334402"),
            3: ("P3_LED_Strip", "AA1122334403"),
        }
        while self._running:
            if not self.fault_ble_dropout:
                now = time.time()
                for ch in (1, 2, 3):
                    target = self._compute_target_watts(ch)
                    # First-order exponential lag (tau ~ 0.35s) to model motor/thermal inertia
                    self.actual_watts[ch] += 0.45 * (target - self.actual_watts[ch])
                    noisy_w = max(0.0, self.actual_watts[ch] + random.gauss(0.0, 0.035))
                    volts = round(12.02 - 0.015 * noisy_w + random.gauss(0.0, 0.01), 3)
                    amps = round(noisy_w / volts, 3) if volts > 0 else 0.0
                    self.sequences[ch] += 1
                    name, mac = assets[ch]

                    await on_reading(
                        PowerReading(
                            channel_id=ch,
                            asset_name=name,
                            sensor_mac=mac,
                            sequence=self.sequences[ch],
                            voltage_v=volts,
                            current_a=amps,
                            watts=round(noisy_w, 3),
                            duty_pct=self.duties[ch],
                            rssi=-52 + random.randint(-3, 3),
                            timestamp=now,
                            quality_flag="OK",
                        )
                    )
            await asyncio.sleep(0.20)  # Exact 5 Hz broadcast cadence per D5 specification

    async def stop(self) -> None:
        self._running = False