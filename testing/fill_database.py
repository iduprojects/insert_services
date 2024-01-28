import os
import subprocess
import sys
import time
import geopandas as gpd
import psycopg2
import pg_save

db_user = "postgres"
db_password = "postgres"
db_host = "127.0.0.1"
db_port = "5454"
db_name = "city_db"

db_dsn = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

print("Setting up the database")
res = subprocess.call(["docker", "compose", "down"])
if res != 0:
    print("`docker compose down` failed, exiting")
    sys.exit(1)
res = subprocess.call(["docker", "compose", "up", "-d"])
if res != 0:
    print("`docker compose up -d` failed, exiting")
    sys.exit(1)
wait_time = int(os.environ.get("WAIT_TIME", 30))
print(
    f"Sleeping {wait_time} seconds or until Ctrl+C is hit (if this is not enough for postgresql to start on your system,"
    " increase the time by setting WAIT_TIME environment variable or comment out `docker compose down` call)"
)
try:
    time.sleep(wait_time)
except KeyboardInterrupt:
    pass

print("Creating city_db database")
res = subprocess.call(["psql", "-c", "create database city_db", db_dsn[: db_dsn.rfind("/")] + "/postgres"])
if res != 0:
    print("Error on schema creation")
    sys.exit(1)

time.sleep(1)

print("Preparing schema")
res = subprocess.call(["psql", "-f", "../db_schema/init_schema.sql", db_dsn])
if res != 0:
    print("Error on schema preparation")
    sys.exit(1)

time.sleep(1)

print("Preparing base data")
res = subprocess.call(
    ["psql", "-f", "../db_schema/init_data.sql", db_dsn],
    env=os.environ | {"PGCLIENTENCODING": "utf-8"},
)
if res != 0:
    print("Error on data preparation")
    sys.exit(1)

get_conn = lambda: psycopg2.connect(db_dsn)

with get_conn() as conn, conn.cursor() as cur:
    print("Inserting city")
    cities: gpd.GeoDataFrame = gpd.read_file("test_city/city.geojson")
    city = cities.iloc[0].to_dict()
    cur.execute(
        "WITH geom AS (SELECT ST_GeomFromText(%(geometry)s) as geometry)"
        " INSERT INTO cities (name, code, population, geometry, center)"
        " VALUES (%(name)s, %(code)s, %(population)s, (SELECT geometry FROM geom), (SELECT ST_Centroid(geometry) FROM geom))",
        {
            "name": city["name"],
            "code": city["code"],
            "population": city["population"],
            "geometry": str(city["geometry"]),
        },
    )

    print("Inserting administrative units")
    administrative_units: gpd.GeoDataFrame = gpd.read_file("test_city/administrative_units.geojson")
    for _, (city_code, name, geometry) in administrative_units[["city_code", "name", "geometry"]].iterrows():
        cur.execute(
            "WITH geom AS (SELECT ST_GeomFromText(%(geometry)s) as geometry)"
            " INSERT INTO administrative_units (city_id, type_id, name, geometry, center)"
            " VALUES ("
            "   (SELECT id FROM cities WHERE code = %(city_code)s),"
            "   1,"
            "   %(name)s,"
            "   (SELECT geometry FROM geom),"
            "   (SELECT ST_Centroid(geometry) FROM geom)"
            ")",
            {"city_code": city_code, "name": name, "geometry": str(geometry)},
        )

    print("Inserting municipalities")
    municipalities: gpd.GeoDataFrame = gpd.read_file("test_city/municipalities.geojson")
    for _, (au_name, name, geometry) in municipalities[["au_name", "name", "geometry"]].iterrows():
        cur.execute(
            "WITH geom AS (SELECT ST_GeomFromText(%(geometry)s) as geometry)"
            " INSERT INTO municipalities (city_id, admin_unit_parent_id, type_id, name, geometry, center)"
            " VALUES ("
            "   (SELECT city_id FROM administrative_units WHERE name = %(au_name)s),"
            "   (SELECT id FROM administrative_units WHERE name = %(au_name)s),"
            "   1,"
            "   %(name)s,"
            "   (SELECT geometry FROM geom),"
            "   (SELECT ST_Centroid(geometry) FROM geom)"
            ")",
            {"au_name": au_name, "name": name, "geometry": str(geometry)},
        )

print("Inserting buildings")
res = subprocess.call(
    [
        "platform-management",
        "insert-buildings",
        "-H",
        db_host,
        "-P",
        db_port,
        "-D",
        db_name,
        "-U",
        db_user,
        "-W",
        db_password,
        "--city",
        city["code"],
        "--document_storeys_count",
        "floors",
        "--log_filename",
        "-",
        "--skip_logs",
        "test_city/buildings.geojson",
    ]
)
if res != 0:
    print("Could not insert buildings")
res = subprocess.call(
    [
        "platform-management",
        "operation",
        "-H",
        db_host,
        "-P",
        db_port,
        "-D",
        db_name,
        "-U",
        db_user,
        "-W",
        db_password,
        "update-buildings-area",
    ]
)
res = subprocess.call(
    [
        "platform-management",
        "operation",
        "-H",
        db_host,
        "-P",
        db_port,
        "-D",
        db_name,
        "-U",
        db_user,
        "-W",
        db_password,
        "refresh-materialized-views",
    ]
)

actual_buildings_filename = "actual_buildings.geojson"
print(f"Exporting uploaded buildings to '{actual_buildings_filename}'")
with get_conn() as conn, conn.cursor() as cur:
    uploaded_buildings = pg_save.querying.select(
        conn,
        "SELECT *" " FROM all_buildings" " ORDER BY administrative_unit_id, municipality_id",
    )
    pg_save.export.to_geojson(uploaded_buildings, actual_buildings_filename)
