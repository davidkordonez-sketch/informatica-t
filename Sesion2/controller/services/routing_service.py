"""RoutingService: Dijkstra sobre UNA instantánea (FR-03, R8). Sin estado propio."""
from __future__ import annotations

import math

import networkx as nx

from controller.exceptions import NodeNotFoundError, RouteNotFoundError
from controller.models import Metric, Route
from controller.services.topology_service import TopologyService


class RoutingService:
    def __init__(self, topology_service: TopologyService) -> None:
        self._topology_service = topology_service

    def find_route(self, src: str, dst: str, metric: Metric) -> Route:
        snapshot = self._topology_service.get_snapshot()  # una sola lectura del estado
        for node in (src, dst):
            if not snapshot.has_node(node):
                raise NodeNotFoundError(f"Node '{node}' does not exist", {"node": node})

        if src == dst:  # A-08
            return Route(src, dst, metric, [src], 0.0, [], snapshot.version)

        graph = self._topology_service.build_weighted_graph(snapshot, metric)
        try:
            path = nx.dijkstra_path(graph, src, dst, weight="weight")
        except nx.NetworkXNoPath as error:
            raise RouteNotFoundError(
                f"No active route from '{src}' to '{dst}'", {"src": src, "dst": dst}
            ) from error

        hop_costs = [float(graph[u][v]["weight"]) for u, v in zip(path, path[1:])]
        return Route(
            src=src,
            dst=dst,
            metric=metric,
            path=list(path),
            total_cost=math.fsum(hop_costs),
            hop_costs=hop_costs,
            topology_version=snapshot.version,  # la versión de la MISMA instantánea (G1)
        )
