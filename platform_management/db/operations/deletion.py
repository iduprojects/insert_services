"""Objects deletion logic is defined here."""

import psycopg2.extensions


def delete_functional_object(cur: psycopg2.extensions.cursor, functional_object_id: int) -> None:
    """Delete functional object from the database, also deleting physical_object if the service was non-building
    type.
    """
    cur.execute("DELETE FROM functional_objects WHERE id = %s RETURNING physical_object_id", (functional_object_id,))
    phys_id = cur.fetchone()
    if phys_id is None:  # no service was deleted
        return
    phys_id: int = phys_id[0]
    cur.execute("SELECT EXISTS(SELECT 1 FROM buildings WHERE physical_object_id = %s)", (phys_id,))
    if cur.fetchone()[0]:  # do not delete building on service deletion
        return
    cur.execute("SELECT count(id) FROM functional_objects WHERE physical_object_id = %s", (phys_id,))
    if cur.fetchone()[0] == 0:
        cur.execute("DELETE FROM physical_objects WHERE id = %s", (phys_id,))


def delete_building(cur: psycopg2.extensions.cursor, building_id: int) -> None:
    """Delete building with all its functional objects and physical_object"""
    cur.execute("SELECT physical_object_id FROM buildings WHERE id = %s", (building_id,))
    phys_id = cur.fetchone()
    if phys_id is None:  # building does not exist
        return
    phys_id: int = phys_id[0]
    cur.execute("DELETE FROM functional_objects WHERE physical_object_id = %s", (phys_id,))
    cur.execute("DELETE FROM buildings WHERE id = %s", (building_id,))
    cur.execute("DELETE FROM physical_objects WHERE id = %s", (phys_id,))
