"""Modelos de dominio del Controller (capa Modelo de MVC). Sin HTTP ni almacenamiento."""
from controller.models.link import Link, LinkStatus
from controller.models.link_change import LinkChange
from controller.models.metric import Metric
from controller.models.route import Route
from controller.models.topology import Topology

__all__ = ["Link", "LinkStatus", "LinkChange", "Metric", "Route", "Topology"]
