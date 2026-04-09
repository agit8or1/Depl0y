"""Analysis/recommendations DB models"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from datetime import datetime
from app.models.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, index=True)

    # Scope
    host_id = Column(Integer, ForeignKey("proxmox_hosts.id"), nullable=True, index=True)
    node = Column(String(100), nullable=True)
    vmid = Column(Integer, nullable=True)
    vm_name = Column(String(200), nullable=True)
    resource_label = Column(String(200), nullable=True)  # e.g. "local-lvm", "pve01"

    # Classification
    category = Column(String(50), nullable=False, index=True)  # performance|reliability|storage|configuration
    rule_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="info")  # info|warning|critical

    # Content
    title = Column(String(255), nullable=False)
    detail = Column(Text, nullable=True)
    suggestion = Column(Text, nullable=True)  # actionable next step

    # Metric snapshot
    metric_value = Column(Float, nullable=True)
    metric_unit = Column(String(20), nullable=True)   # %, GB, cores, days
    threshold = Column(Float, nullable=True)

    # Lifecycle
    dismissed = Column(Boolean, default=False, nullable=False)
    dismissed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
