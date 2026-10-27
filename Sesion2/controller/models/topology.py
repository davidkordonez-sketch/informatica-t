from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from controller.models.link import Link, LinkStatus


@dataclass(frozen=True)
class Topology:
    """Instantánea INMUTABLE de la red (A-14, 02 §7.1).

    Nunca se modifica: cada fallo/restablecimiento crea una instantánea nueva con
    ``version + 1`` mediante ``with_link_status``. Así, quien tiene una referencia
    siempre ve un estado completo y coherente.
    """

    nodes: Tuple[str, ...]
    links: Tuple[Link, ...]
    version: int = 1
    # Índices derivados (no forman parte de la igualdad ni del repr).
    _node_set: frozenset = field(init=False, repr=False, compare=False)
    _link_index: Dict[frozenset, int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_node_set", frozenset(self.nodes))
        index: Dict[frozenset, int] = {}
        for position, link in enumerate(self.links):
            index.setdefault(link.key(), position)
        object.__setattr__(self, "_link_index", index)

    def has_node(self, node_id: str) -> bool:
        return node_id in self._node_set

    def get_link(self, node_a: str, node_b: str) -> Optional[Link]:
        position = self._link_index.get(frozenset((node_a, node_b)))
        return None if position is None else self.links[position]

    def with_link_status(self, node_a: str, node_b: str, status: LinkStatus) -> "Topology":
        """Crea una instantánea nueva con el enlace en ``status`` y ``version + 1``."""
        position = self._link_index.get(frozenset((node_a, node_b)))
        if position is None:
            raise KeyError(f"Link {node_a}-{node_b} does not exist")
        links = list(self.links)
        links[position] = links[position].with_status(status)
        return Topology(nodes=self.nodes, links=tuple(links), version=self.version + 1)
