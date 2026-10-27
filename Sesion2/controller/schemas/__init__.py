"""Esquemas de entrada/salida (capa Vista de MVC): contrato JSON de 04-api-contract.md."""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, field_validator

from controller.models import Link, LinkChange, Route, Topology


class RouteResponse(BaseModel):
    src: str
    dst: str
    metric: str
    path: List[str]
    hop_costs: List[float]
    total_cost: float
    topology_version: int

    @classmethod
    def from_domain(cls, route: Route) -> "RouteResponse":
        return cls(
            src=route.src,
            dst=route.dst,
            metric=route.metric.value,
            path=route.path,
            hop_costs=route.hop_costs,
            total_cost=route.total_cost,
            topology_version=route.topology_version,
        )


class LinkView(BaseModel):
    node_a: str
    node_b: str
    delay_ms: float
    bandwidth_mbps: float
    loss_prob: float
    status: str

    @classmethod
    def from_domain(cls, link: Link) -> "LinkView":
        return cls(
            node_a=link.node_a,
            node_b=link.node_b,
            delay_ms=link.delay_ms,
            bandwidth_mbps=link.bandwidth_mbps,
            loss_prob=link.loss_prob,
            status=link.status.value,
        )


class TopologyResponse(BaseModel):
    topology_version: int
    nodes: List[str]
    links: List[LinkView]

    @classmethod
    def from_domain(cls, topology: Topology) -> "TopologyResponse":
        return cls(
            topology_version=topology.version,
            nodes=list(topology.nodes),
            links=[LinkView.from_domain(link) for link in topology.links],
        )


class LinkRequest(BaseModel):
    node_a: str = Field(min_length=1)
    node_b: str = Field(min_length=1)

    @field_validator("node_a", "node_b")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class LinkStateView(BaseModel):
    node_a: str
    node_b: str
    status: str


class LinkStateResponse(BaseModel):
    link: LinkStateView
    topology_version: int

    @classmethod
    def from_domain(cls, change: LinkChange) -> "LinkStateResponse":
        return cls(
            link=LinkStateView(node_a=change.link.node_a, node_b=change.link.node_b, status=change.link.status.value),
            topology_version=change.topology_version,
        )


class HealthResponse(BaseModel):
    status: str
    service: str
    topology_loaded: bool
    topology_version: int
