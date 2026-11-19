import asyncio
import time
import serial
from app.hal.base import ActuatorSink, ActuatorCommand #Hardware abstraction layer
from app.config import settings

class UsbSerialControllerAdapter(ActuatorSink):
    """
    Sends idempotent SET_PWM commands over USB Serial (115200 bps) to the ESP32-S3
    Local Station Controller, which drives the 3-channel opto-isolated MOSFET module.
    """
    def __init__(self):
        self._ser = None
        self._executed_ids: set[str] = set()

    def _connect(self):
        if self._ser is None or not self._ser.is_open:
            #LOCAL CONTROLLER
            self._ser = serial.Serial(settings.SERIAL_PORT, settings.SERIAL_BAUD, timeout=0.2) #

    async def send_pwm(self, cmd: ActuatorCommand) -> str:
        if time.time() > cmd.expiry_ts:
            return "REJECTED_EXPIRED"
        if cmd.command_id in self._executed_ids:
            return "DUPLICATE_IGNORED"
        
#MOSFET --> 3-channels
        # Enforce safe bounds (Essential Fan kept within safe operating bounds)
        ch1 = max(0, min(100, cmd.ch1_essential_pct)) #FAN 1 
        ch2 = max(0, min(100, cmd.ch2_flexible_pct)) #FAN 2
        ch3 = max(0, min(100, cmd.ch3_led_pct)) #LED

        wire_msg = f"SET_PWM,{cmd.command_id},{ch1},{ch2},{ch3}\n".encode("ascii")
        try:
            await asyncio.to_thread(self._write_and_read, wire_msg)
            self._executed_ids.add(cmd.command_id)
            if len(self._executed_ids) > 500:
                self._executed_ids.clear()
            return "ACCEPTED"
        except Exception as exc:
            print(f"[SerialController] Error: {exc}")
            return "SERIAL_ERROR"

    def _write_and_read(self, data: bytes) -> str:
        self._connect()
        self._ser.write(data)
        self._ser.flush()
        return self._ser.readline().decode("ascii", errors="ignore").strip()