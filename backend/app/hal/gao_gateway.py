import json
import struct
import time
import asyncio
import aiomqtt
from typing import Callable, Awaitable, Dict
from app.hal.base import TelemetrySource, PowerReading
from app.config import settings

# Persistent MAC-to-Asset identity mapping (Reference Guide p. 19: never select by RSSI alone)
ENROLLED_NODES: Dict[str, tuple[int, str]] = {
    "AA1122334401": (1, "P1_Essential_Fan"),
    "AA1122334402": (2, "P2_Flexible_Fan"),
    "AA1122334403": (3, "P3_LED_Strip"),
}

class GAO217030MqttAdapter(TelemetrySource):
    """
    Integrates GAO 217030 BLE Gateway (Configuration Guide Sec. 4.3.1 & 4.3.2).
    Expects 'Upload Unknown = YES' so raw 12-byte INA219+ESP32 hex packets arrive in 'data1'.
    """
    def __init__(self):
        self._running = False
        self._last_seq: Dict[int, int] = {}

    def decode_hex_payload(self, dmac: str, hex_str: str, rssi: int) -> PowerReading | None:
        clean_mac = dmac.replace(":", "").upper()
        if clean_mac not in ENROLLED_NODES:
            return None

        channel_id, asset_name = ENROLLED_NODES[clean_mac]
        raw = bytes.fromhex(hex_str)
        # Look for 12-byte frame: <B H H h H B H (ch, seq, mv, ma, mw, duty, uptime)
        if len(raw) < 12:
            return None
        _, seq, v_mv, i_ma, p_mw, duty, _ = struct.unpack("<BHHhHBH", raw[-12:])

        # Sequence duplicate / gap validation
        quality = "OK"
        prev_seq = self._last_seq.get(channel_id)
        if prev_seq is not None and seq == prev_seq:
            quality = "DUPLICATE"
        self._last_seq[channel_id] = seq

        volts = round(v_mv / 1000.0, 3)
        amps = round(i_ma / 1000.0, 3)
        watts = round(p_mw / 1000.0, 3)

        if not (0.0 <= volts <= 26.0 and -3.2 <= amps <= 3.2):
            quality = "OUT_OF_RANGE"

        return PowerReading(
            channel_id=channel_id,
            asset_name=asset_name,
            sensor_mac=clean_mac,
            sequence=seq,
            voltage_v=volts,
            current_a=amps,
            watts=watts,
            duty_pct=duty,
            rssi=rssi,
            timestamp=time.time(),
            quality_flag=quality,
        )

    async def start(self, on_reading: Callable[[PowerReading], Awaitable[None]]) -> None:
        self._running = True
        while self._running:
            try:
                async with aiomqtt.Client(
                    hostname=settings.MQTT_BROKER_HOST,
                    port=settings.MQTT_BROKER_PORT,
                ) as client:
                    await client.subscribe(settings.MQTT_TOPIC)
                    async for message in client.messages:
                        if not self._running:
                            break
                        payload = json.loads(message.payload.decode("utf-8"))
                        if payload.get("msg") != "advData":
                            continue
                        for item in payload.get("obj", []):
                            reading = self.decode_hex_payload(
                                dmac=item.get("dmac", ""),
                                hex_str=item.get("data1", ""),
                                rssi=int(item.get("rssi", -100)),
                            )
                            if reading:
                                await on_reading(reading)
            except Exception as exc:
                print(f"[GAO217030MqttAdapter] Reconnecting after error: {exc}")
                await asyncio.sleep(2.0)

    async def stop(self) -> None:
        self._running = False