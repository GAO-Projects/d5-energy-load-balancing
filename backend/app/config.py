from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://d5_user:d5_password@postgres:5432/d5_energy_db"
    MQTT_BROKER_HOST: str = "mosquitto"
    MQTT_BROKER_PORT: int = 1883
    MQTT_TOPIC: str = "kbeacon/publish/#"
    HARDWARE_MODE: str = "synthetic"  # "synthetic" or "hardware"
    SERIAL_PORT: str = "/dev/ttyACM0"
    SERIAL_BAUD: int = 115200
    DEFAULT_BUDGET_WATTS: float = 8.0
    DEMO_TRACK: str = "physical_ai"   # "physical_ai" or "aiot"
    STALE_THRESHOLD_SEC: float = 2.0  # D5 timing rule: >2s stale triggers shed
    DWELL_SECONDS: float = 3.0        # Discretionary change minimum dwell

settings = Settings()
