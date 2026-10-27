"""Esquemas de entrada/salida del Router (capa Vista). Validan solo el FORMATO (A-09)."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from router.models import ForwardingResult, Packet


class MetricName(str, Enum):
    DELAY = "delay"
    BANDWIDTH = "bandwidth"
    LOSS = "loss"


class PacketRequest(BaseModel):
    packet_id: str = Field(min_length=1)
    src: str = Field(min_length=1)
    dst: str = Field(min_length=1)
    metric: MetricName = MetricName.DELAY
    payload: Optional[str] = None

    @field_validator("packet_id", "src", "dst")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    def to_domain(self) -> Packet:
        return Packet(self.packet_id, self.src, self.dst, self.metric.value, self.payload)


class RouteView(BaseModel):
    path: List[str]
    total_cost: float
    topology_version: int


class HopView(BaseModel):
    hop: int
    from_node: str
    to_node: str
    status: str


class WarningView(BaseModel):
    code: str
    message: str


class ForwardingResultResponse(BaseModel):
    packet_id: str
    status: str
    src: str
    dst: str
    metric: str
    route: Optional[RouteView]
    trace: List[HopView]
    reason: Optional[str]
    log_persisted: bool
    warnings: List[WarningView]
    timestamp: str

    @classmethod
    def from_domain(cls, result: ForwardingResult) -> "ForwardingResultResponse":
        return cls(
            packet_id=result.packet_id,
            status=result.status.value,
            src=result.src,
            dst=result.dst,
            metric=result.metric,
            route=None
            if result.route is None
            else RouteView(
                path=result.route.path,
                total_cost=result.route.total_cost,
                topology_version=result.route.topology_version,
            ),
            trace=[HopView(hop=h.hop, from_node=h.from_node, to_node=h.to_node, status=h.status) for h in result.trace],
            reason=result.reason,
            log_persisted=result.log_persisted,
            warnings=[WarningView(code=w.code, message=w.message) for w in result.warnings],
            timestamp=result.timestamp,
        )


class HealthResponse(BaseModel):
    status: str
    service: str
