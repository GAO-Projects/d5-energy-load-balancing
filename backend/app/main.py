import asyncio
import time
import uuid
from collections import deque
from typing import Dict, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.database import init_db, AsyncSessionLocal
from app.models import SensorEvent, ControlDecisionLog

#HARDWARE ABSTRACTION LAYER --IMPORTS FROM PREV FILES
from app.hal.base import PowerReading, ActuatorCommand
from app.hal.synthetic import SyntheticBenchPlant
from app.hal.gao_gateway import GAO217030MqttAdapter
from app.hal.serial_controller import UsbSerialControllerAdapter

from app.ai.forecaster import PowerDemandForecaster
from app.ai.optimizer import PriorityLoadOptimizer

app = FastAPI(title="D5 Energy Load Balancing — Physical AI & AIoT Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Runtime state
latest_readings: Dict[int, PowerReading] = {}
total_watt_history: deque[tuple[float, float]] = deque(maxlen=50)
connected_clients: List[WebSocket] = []

runtime_config = {
    "budget_watts": settings.DEFAULT_BUDGET_WATTS,
    "demo_track": settings.DEMO_TRACK,
    "extra_demand_switch": False,
    "fault_ble_dropout": False,
}

synthetic_plant = SyntheticBenchPlant()
telemetry_source = synthetic_plant if settings.HARDWARE_MODE == "synthetic" else GAO217030MqttAdapter()
actuator_sink = synthetic_plant if settings.HARDWARE_MODE == "synthetic" else UsbSerialControllerAdapter()

forecaster = PowerDemandForecaster()
optimizer = PriorityLoadOptimizer(forecaster)

async def broadcast_ws(payload: dict):
    stale = []
    for ws in connected_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            stale.append(ws)
    for ws in stale:
        if ws in connected_clients:
            connected_clients.remove(ws)

async def handle_power_reading(reading: PowerReading):
    latest_readings[reading.channel_id] = reading
    total_w = sum(r.watts for r in latest_readings.values())
    total_watt_history.append((reading.timestamp, total_w))

    # Persist high-rate telemetry asynchronously
    async with AsyncSessionLocal() as session:
        session.add(
            SensorEvent(
                channel_id=reading.channel_id,
                asset_name=reading.asset_name,
                sensor_mac=reading.sensor_mac,
                sequence=reading.sequence,
                voltage_v=reading.voltage_v,
                current_a=reading.current_a,
                watts=reading.watts,
                duty_pct=reading.duty_pct,
                rssi=reading.rssi,
                quality_flag=reading.quality_flag,
            )
        )
        await session.commit()

async def control_loop_1hz():
    """1 Hz AI forecast, priority optimization, actuation & WebSocket dashboard broadcast."""
    while True:
        await asyncio.sleep(1.0)
        now = time.time()
        channel_watts = {ch: r.watts for ch, r in latest_readings.items()}
        ages = [now - r.timestamp for r in latest_readings.values()]
        max_age = max(ages) if ages else 999.0

        # Estimate recent power slope (W/s)
        slope = 0.0
        if len(total_watt_history) >= 5:
            t0, w0 = total_watt_history[-5]
            t1, w1 = total_watt_history[-1]
            if (t1 - t0) > 0.1:
                slope = (w1 - w0) / (t1 - t0)

        res = optimizer.evaluate(
            channel_watts=channel_watts,
            last_update_age_s=max_age,
            budget_watts=runtime_config["budget_watts"],
            slope_w_s=slope,
            demo_track=runtime_config["demo_track"],
        )

        cmd_id = None
        ack_status = "PASSIVE_NO_ACTUATION"
        if runtime_config["demo_track"] == "physical_ai":
            cmd_id = f"cmd_{uuid.uuid4().hex[:8]}"
            cmd = ActuatorCommand(
                command_id=cmd_id,
                ch1_essential_pct=res.target_duties[1],
                ch2_flexible_pct=res.target_duties[2],
                ch3_led_pct=res.target_duties[3],
                expiry_ts=now + 1.5,
            )
            ack_status = await actuator_sink.send_pwm(cmd)

        async with AsyncSessionLocal() as session:
            session.add(
                ControlDecisionLog(
                    decision_id=res.decision_id,
                    demo_track=runtime_config["demo_track"],
                    measured_total_watts=res.measured_total_watts,
                    forecast_5s_watts=res.forecast_5s_watts,
                    forecast_10s_watts=res.forecast_10s_watts,
                    error_margin_watts=res.error_margin_watts,
                    budget_watts=runtime_config["budget_watts"],
                    system_state=res.system_state,
                    reason_code=res.reason_code,
                    commanded_duties={f"ch{k}": v for k, v in res.target_duties.items()},
                    command_id=cmd_id,
                    ack_status=ack_status,
                )
            )
            await session.commit()

        await broadcast_ws({
            "timestamp": now,
            "hardware_mode": settings.HARDWARE_MODE,
            "demo_track": runtime_config["demo_track"],
            "budget_watts": runtime_config["budget_watts"],
            "data_age_s": round(max_age, 2),
            "decision": {
                "decision_id": res.decision_id,
                "system_state": res.system_state,
                "reason_code": res.reason_code,
                "measured_total_watts": res.measured_total_watts,
                "forecast_5s_watts": res.forecast_5s_watts,
                "forecast_10s_watts": res.forecast_10s_watts,
                "error_margin_watts": res.error_margin_watts,
                "target_duties": res.target_duties,
                "anomaly_score": res.anomaly_score,
                "command_id": cmd_id,
                "ack_status": ack_status,
            },
            "channels": {
                str(ch): {
                    "asset_name": r.asset_name,
                    "sensor_mac": r.sensor_mac,
                    "sequence": r.sequence,
                    "voltage_v": r.voltage_v,
                    "current_a": r.current_a,
                    "watts": r.watts,
                    "duty_pct": r.duty_pct,
                    "rssi": r.rssi,
                    "quality_flag": r.quality_flag,
                }
                for ch, r in latest_readings.items()
            },
        })

@app.on_event("startup")
async def on_startup():
    await init_db()
    asyncio.create_task(telemetry_source.start(handle_power_reading))
    asyncio.create_task(control_loop_1hz())

class ControlUpdateRequest(BaseModel):
    budget_watts: float | None = None
    demo_track: str | None = None
    extra_demand_switch: bool | None = None
    fault_ble_dropout: bool | None = None

@app.post("/api/control")
async def update_control(req: ControlUpdateRequest):
    if req.budget_watts is not None:
        runtime_config["budget_watts"] = max(1.0, min(20.0, req.budget_watts))
    if req.demo_track in ("physical_ai", "aiot"):
        runtime_config["demo_track"] = req.demo_track
    if req.extra_demand_switch is not None:
        runtime_config["extra_demand_switch"] = req.extra_demand_switch
        synthetic_plant.extra_demand_switch = req.extra_demand_switch
    if req.fault_ble_dropout is not None:
        runtime_config["fault_ble_dropout"] = req.fault_ble_dropout
        synthetic_plant.fault_ble_dropout = req.fault_ble_dropout
    return {"status": "UPDATED", "config": runtime_config}

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connected_clients:
            connected_clients.remove(websocket)
            