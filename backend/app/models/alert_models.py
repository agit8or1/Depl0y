"""
SQLAlchemy models for the alert rules engine.
"""
from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, String, DateTime, Float, ForeignKey, Text
from app.models.database import Base


class AlertRule(Base):
    """User-configurable alert rule stored in the database."""
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    rule_type = Column(String(50), nullable=False)   # storage_usage, node_cpu, node_memory, vm_stopped, backup_failed, login_failures
    threshold = Column(Float, nullable=True)          # e.g. 85.0 for 85%
    host_id = Column(Integer, ForeignKey("proxmox_hosts.id"), nullable=True)   # None = all hosts
    node = Column(String(100), nullable=True)         # None = all nodes
    enabled = Column(Boolean, default=True, nullable=False)
    notify_in_app = Column(Boolean, default=True, nullable=False)
    notify_webhook = Column(Boolean, default=False, nullable=False)
    notify_slack = Column(Boolean, default=False, nullable=False)
    cooldown_minutes = Column(Integer, default=60, nullable=False)
    last_fired_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AlertEvent(Base):
    """
    Record of a single alert firing.
    rule_id  — references AlertRule when triggered by a user rule (NULL for built-in rules)
    rule_key — stable string key for the built-in rule
    """
    __tablename__ = "alert_events"

    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=True)
    rule_key = Column(String(255), nullable=True, index=True)    # built-in key OR 'user_rule:{id}'
    severity = Column(String(20), nullable=False, default="warning")  # info / warning / critical
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    fired_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
