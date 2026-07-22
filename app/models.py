from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Incident(Base):
    __tablename__ = "incidents"

    alert_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    received_at: Mapped[str] = mapped_column(String)

    alert_type: Mapped[str] = mapped_column(String)
    server: Mapped[str] = mapped_column(String)
    value: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String)

    investigation_status: Mapped[str] = mapped_column(String)
    probable_cause: Mapped[str] = mapped_column(String)
    recommended_action: Mapped[str] = mapped_column(String)
    confidence: Mapped[int] = mapped_column(Integer)