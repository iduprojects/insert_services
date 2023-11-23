"""Materialized views refresh methods are defined here."""
from __future__ import annotations

import psycopg2
import psycopg2.extensions
from loguru import logger


def refresh_materialized_views(
    cur: psycopg2.extensions.cursor, materialized_views_names: list[str] | None = ...
) -> None:
    """Refresh given materialized views (default all_buildings and all_services)."""

    if materialized_views_names is None:
        return
    if materialized_views_names is ...:
        materialized_views_names = ["all_buildings", "all_services"]

    for name in materialized_views_names:
        logger.info("Refreshing materialized view '{}'", name)
        cur.execute(f"REFRESH MATERIALIZED VIEW {name}")


def update_physical_objects_locations(cur: psycopg2.extensions.cursor, city_id: int | None = None) -> None:
    """Update physical_objects references to blocks, administrative units and municipalities"""
    logger.info("Filling missing administrative units")
    cur.execute(
        "UPDATE physical_objects p SET"
        "   administrative_unit_id = (SELECT au.id FROM administrative_units au"
        "       WHERE au.city_id = p.city_id AND ST_CoveredBy(p.center, au.geometry) LIMIT 1)"
        "WHERE administrative_unit_id IS null" + (" AND city_id = %s" if city_id is not None else ""),
        ((city_id,) if city_id is not None else None),
    )
    logger.info("Filling missing municipalities")
    cur.execute(
        "UPDATE physical_objects p SET"
        "   municipality_id = (SELECT m.id FROM municipalities m"
        "       WHERE m.city_id = p.city_id AND ST_CoveredBy(p.center, m.geometry) LIMIT 1)"
        "WHERE municipality_id IS null" + (" AND city_id = %s" if city_id is not None else ""),
        ((city_id,) if city_id is not None else None),
    )
    logger.info("Filling missing blocks")
    cur.execute(
        "UPDATE physical_objects p SET"
        "   block_id = (SELECT b.id FROM blocks b"
        "       WHERE b.city_id = p.city_id"
        "           AND ("
        "               b.administrative_unit_id = p.administrative_unit_id"
        "               OR b.municipality_id = p.municipality_id"
        "           )"
        "           AND ST_CoveredBy(p.center, b.geometry)"
        "       LIMIT 1"
        "   )"
        "WHERE block_id IS null",
        ((city_id,) if city_id is not None else None),
    )


def update_buildings_area(cur: psycopg2.extensions.cursor) -> None:
    """Update buildings area as ST_Area(physical_object.geometry::geography) and living area as building_area
    * storeys_count * 0.7 while setting modeled->>'living_area'=1"""
    logger.info("Updating buildings area")
    cur.execute(
        "UPDATE buildings"
        " SET building_area = ("
        "   SELECT ST_Area(geometry::geography)"
        "   FROM physical_objects"
        "   WHERE id = physical_object_id"
        " )"
        " WHERE building_area is NULL"
    )
    logger.debug("Updated {} buildings building_area", cur.rowcount)

    logger.info("Modeling living_area")
    cur.execute(
        "UPDATE buildings"
        " SET"
        "   living_area = building_area * storeys_count * 0.7,"
        "   modeled = modeled || '{\"living_area\": 1}'::jsonb"
        " WHERE"
        "   is_living = true"
        "   AND building_area IS NOT NULL"
        "   AND storeys_count IS NOT NULL"
        "   AND (living_area IS NULL OR modeled->>'living_area' = '1' OR building_area * storeys_count < living_area)"
    )
    logger.debug("Updated {} buildings living area", cur.rowcount)
