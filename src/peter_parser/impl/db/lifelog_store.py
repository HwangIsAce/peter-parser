"""Lifelog store for events and entities using JanusGraph."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import __

from peter_parser.common.config import Config


class LifelogStore:
    """Store lifelog events and entities in JanusGraph."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> None:
        host = host or Config.JANUSGRAPH_HOST
        port = port or Config.JANUSGRAPH_PORT
        self._conn = DriverRemoteConnection(
            f"ws://{host}:{port}/gremlin",
            "g",
        )
        self._g = traversal().withRemote(self._conn)

    def close(self) -> None:
        """Close the connection to JanusGraph."""
        self._conn.close()

    def save_event(
        self,
        day: str,
        event_uuid: str,
        event_data: Dict[str, Any],
        entities: List[Dict[str, Any]],
    ) -> None:
        """Save a lifelog event and its entities to graph. Uses count() to execute without returning Vertex objects."""
        g = self._g

        # Ensure Day exists (execute without returning Vertex)
        _ = g.V().has("Day", "date", day).fold().coalesce(
            __.unfold(),
            __.addV("Day").property("date", day),
        ).count().next()

        # Add Event (execute without returning Vertex)
        _ = g.addV("Event").property("uuid", event_uuid).property(
            "when", event_data.get("when", "")
        ).property("what", event_data.get("what", "")).property(
            "where", event_data.get("where", "")
        ).property("who", event_data.get("who", "")).property(
            "why_how", event_data.get("why_how", "")
        ).property("description", event_data.get("description", "")).count().next()

        # Event -PART_OF-> Day (execute without returning Edge)
        _ = g.V().has("Event", "uuid", event_uuid).as_("e").V().has("Day", "date", day).as_("d").addE("PART_OF").from_("e").to("d").count().next()

        for e in entities:
            canonical = (e.get("canonical") or "").strip()
            if not canonical:
                continue
            etype = e.get("type") or "other"

            # Ensure Entity exists (execute without returning Vertex)
            _ = g.V().has("Entity", "text", canonical).fold().coalesce(
                __.unfold(),
                __.addV("Entity").property("text", canonical).property("type", etype).property("mention_count", 0),
            ).count().next()

            # Event -CONTAINS-> Entity (execute without returning Edge)
            _ = g.V().has("Event", "uuid", event_uuid).as_("ev").V().has("Entity", "text", canonical).as_("ent").addE("CONTAINS").from_("ev").to("ent").count().next()

            # Increment mention_count: .values() returns Long only, no Vertex
            try:
                cnt = g.V().has("Entity", "text", canonical).values("mention_count").next()
            except StopIteration:
                cnt = 0
            _ = g.V().has("Entity", "text", canonical).property("mention_count", int(cnt) + 1).count().next()