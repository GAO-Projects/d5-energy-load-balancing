# backend/app/models.py
from datetime import datetime
from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, JSON
from app.database import Base

class SensorEvent(Base):
    __tablename__ = "sensor_events"
    id = Column(Integer, primary_key=True, index=True)
    demo_id = Column(String, default="D5")
    channel_id = Column(Integer, index=True)     # 1=Essential Fan, 2=Flex Fan, 3=LED Strip
    asset_name = Column(String)
    sensor_mac = Column(String)
    sequence = Column(Integer)
    voltage_v = Column(Float)
    current_a = Column(Float)
    watts = Column(Float)
    duty_pct = Column(Integer)
    rssi = Column(Integer, nullable=True)
    quality_flag = Column(String, default="OK")  # OK, STALE, DUPLICATE, OUT_OF_RANGE
    received_time = Column(DateTime, default=datetime.utcnow, index=True)

class ControlDecisionLog(Base):
    __tablename__ = "control_decision_logs"
    id = Column(Integer, primary_key=True, index=True)
    decision_id = Column(String, unique=True, index=True)
    demo_track = Column(String)                  # physical_ai | aiot
    measured_total_watts = Column(Float)
    forecast_5s_watts = Column(Float)
    forecast_10s_watts = Column(Float)
    error_margin_watts = Column(Float)
    budget_watts = Column(Float)
    system_state = Column(String)                # OPTIMAL, SHEDDING, INFEASIBLE_BUDGET, STALE_FALLBACK, PASSIVE_MONITOR
    reason_code = Column(String)
    commanded_duties = Column(JSON)              # {"ch1": 100, "ch2": 95, "ch3": 20}
    command_id = Column(String, nullable=True)
    ack_status = Column(String, default="N/A")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)