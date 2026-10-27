"""Implementación concreta de TopologyDAO sobre un archivo JSON.

Es el ÚNICO lugar del Controller que toca el sistema de archivos (R2, RA-03).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from controller.dao.topology_dao import TopologyDAO
from controller.exceptions import InvalidTopologyError, TopologyUnavailableError
from controller.models import Link, LinkStatus, Topology

_LINK_FIELDS = ("node_a", "node_b", "delay_ms", "bandwidth_mbps", "loss_prob")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class JsonTopologyDAO(TopologyDAO):
    def __init__(self, file_path: str) -> None:
        self._file_path = Path(file_path)

    def load_topology(self) -> Topology:
        try:
            raw_text = self._file_path.read_text(encoding="utf-8")
        except OSError as error:
            raise TopologyUnavailableError(
                "Topology file could not be read",
                {"file": str(self._file_path), "reason": type(error).__name__},
            ) from error
        try:
            document = json.loads(raw_text)
        except json.JSONDecodeError as error:
            raise TopologyUnavailableError(
                "Topology file is not valid JSON",
                {"file": str(self._file_path), "line": error.lineno},
            ) from error
        return self._parse(document)

    def _parse(self, document: Any) -> Topology:
        """Solo convierte la estructura JSON en objetos; no valida rangos ni referencias."""
        if not isinstance(document, dict):
            raise InvalidTopologyError("Topology document must be a JSON object")
        nodes = document.get("nodes")
        links = document.get("links")
        if not isinstance(nodes, list) or not isinstance(links, list):
            raise InvalidTopologyError("Topology document must contain 'nodes' and 'links' lists")
        if not all(isinstance(node, str) for node in nodes):
            raise InvalidTopologyError("Every node id must be a string")
        parsed_links = []
        for position, item in enumerate(links):
            if not isinstance(item, dict) or any(name not in item for name in _LINK_FIELDS):
                raise InvalidTopologyError("Link is missing required fields", {"link_index": position})
            if not isinstance(item["node_a"], str) or not isinstance(item["node_b"], str):
                raise InvalidTopologyError("Link endpoints must be strings", {"link_index": position})
            numbers = (item["delay_ms"], item["bandwidth_mbps"], item["loss_prob"])
            if not all(_is_number(value) for value in numbers):
                raise InvalidTopologyError("Link attributes must be numbers", {"link_index": position})
            parsed_links.append(
                Link(
                    node_a=item["node_a"],
                    node_b=item["node_b"],
                    delay_ms=float(item["delay_ms"]),
                    bandwidth_mbps=float(item["bandwidth_mbps"]),
                    loss_prob=float(item["loss_prob"]),
                    status=LinkStatus.ACTIVE,
                )
            )
        return Topology(nodes=tuple(nodes), links=tuple(parsed_links), version=1)
