# THIS FUNCTIONALITY IS DEPRECATED AND SHOULD BE REPLACED WITH ALEMBIC OR OTHER MIGRATOR
import os

import psycopg2

host = os.environ.get("DB_ADDR", "localhost")
port = int(os.environ.get("DB_PORT", 5432))
dbname = os.environ.get("DB_NAME", "city_db_final")
user = os.environ.get("DB_USER", "postgres")
password = os.environ.get("DB_PASS", "postgres")

conn: psycopg2.extensions.connection = psycopg2.connect(
    host=host, port=port, dbname=dbname, user=user, password=password
)


def to_sql(data) -> str:
    if data is None:
        return "null"
    if isinstance(data, bool):
        return "true" if data else "false"
    return str(data)


def insert_values(items: list, file) -> None:
    print(f"\t({', '.join(map(to_sql, items[0]))})", end="", file=file)
    for values in items[1:]:
        print(f",\n\t({', '.join(map(to_sql, values))})", end="", file=file)
    print(";", file=file)


filename = "init_data.sql"
if os.path.exists(filename):
    os.rename(filename, f"{filename}.bak")
with open(filename, "w", encoding="utf-8") as f:
    with conn, conn.cursor() as cur:
        print("BEGIN TRANSACTION;\n", file=f)

        print("INSERT INTO living_situations (name) VALUES", file=f)
        cur.execute("SELECT concat('''', name, '''') FROM living_situations ORDER BY id")
        insert_values(cur.fetchall(), f)

        print("\nINSERT INTO social_groups (name, code, social_group_value, parent_id) VALUES", file=f)
        cur.execute(
            "SELECT\n"
            "   concat('''', name, ''''),"
            "   concat('''', code, ''''),"
            "   social_group_value,"
            "   concat('(SELECT id FROM social_groups WHERE code = ''',"
            "       (SELECT code FROM social_groups WHERE id = sg.parent_id), ''')')\n"
            " FROM social_groups sg"
            " ORDER BY code, id"
        )
        insert_values(cur.fetchall(), f)

        print("\nINSERT INTO city_infrastructure_types (name, code) VALUES", file=f)
        cur.execute(
            "SELECT concat('''', name, ''''), concat('''', code, '''')\n"
            " FROM city_infrastructure_types\n ORDER BY id"
        )
        insert_values(cur.fetchall(), f)

        print("\nINSERT INTO city_functions (name, code, city_infrastructure_type_id) VALUES", file=f)
        cur.execute(
            "SELECT"
            "   concat('''', name, ''''),"
            "   concat('''', code, ''''),"
            "   concat('(SELECT id FROM city_infrastructure_types WHERE code = ''',"
            "       (SELECT code FROM city_infrastructure_types WHERE id = city_infrastructure_type_id), ''')')"
            " FROM city_functions"
            " ORDER BY id"
        )
        insert_values(cur.fetchall(), f)

        print(
            "\nINSERT INTO city_service_types (name, code, city_function_id,"
            "       capacity_min, capacity_max, status_min, status_max,"
            " is_building, public_transport_time_normative, walking_radius_normative) VALUES",
            file=f,
        )
        cur.execute(
            "SELECT"
            "   concat('''', name, ''''),"
            "   concat('''', code, ''''),"
            "   concat('(SELECT id FROM city_functions WHERE code = ''',"
            "       (SELECT code FROM city_functions WHERE id = city_function_id), ''')'),"
            "   capacity_min,"
            "   capacity_max,"
            "   status_min,"
            "   status_max,"
            "   is_building,"
            "   public_transport_time_normative,"
            "   walking_radius_normative"
            " FROM city_service_types"
            " ORDER BY id"
        )
        insert_values(cur.fetchall(), f)

        print("\nINSERT INTO municipality_types (full_name, short_name) VALUES", file=f)
        cur.execute(
            "SELECT concat('''', full_name, ''''), concat('''', short_name, '''')"
            " FROM municipality_types ORDER BY id"
        )
        insert_values(cur.fetchall(), f)

        print("\nINSERT INTO administrative_unit_types (full_name, short_name) VALUES", file=f)
        cur.execute(
            "SELECT concat('''', full_name, ''''), concat('''', short_name, '''')"
            " FROM administrative_unit_types ORDER BY id"
        )
        insert_values(cur.fetchall(), f)

        print("\nEND TRANSACTION;", file=f)

filename = "init_provision.sql"
if os.path.exists(filename):
    os.rename(filename, f"{filename}.bak")
with open(filename, "w", encoding="utf-8") as f:
    print("BEGIN TRANSACTION;\n", file=f)

    print(
        "\nINSERT INTO provision.normatives ("
        "   city_service_type_id,"
        "   normative,"
        "   max_load,"
        "   radius_meters,"
        "   public_transport_time,"
        "   service_evaluation,"
        "   house_evaluation,"
        "   last_calculations"
        ") VALUES",
        file=f,
    )
    cur.execute(
        "SELECT"
        "   concat('(SELECT id FROM city_service_types WHERE code = ''',"
        "       (SELECT code FROM city_service_types WHERE id = city_service_type_id), ''')'),"
        "   concat('''', normative, ''''),"
        "   concat('''', max_load, ''''),"
        "   radius_meters,"
        "   public_transport_time,"
        "    concat('''', service_evaluation::text, '''::jsonb'),"
        "    concat('''', house_evaluation::text, '''::jsonb'),"
        "   null as last_calculations"
        " FROM provision.normatives"
        " ORDER BY city_service_type_id"
    )
    insert_values(cur.fetchall(), f)

    print(
        "\nINSERT INTO maintenance.social_groups_city_service_types (social_group_id, city_service_type_id) VALUES",
        file=f,
    )
    cur.execute(
        "SELECT"
        "   concat('(SELECT id FROM social_groups WHERE code = ''',"
        "       (SELECT code FROM social_groups WHERE id = social_group_id), ''')'),"
        "   concat('(SELECT id FROM city_service_types WHERE code = ''',"
        "       (SELECT code FROM city_service_types WHERE id = city_service_type_id), ''')')"
        " FROM maintenance.social_groups_city_service_types"
        " ORDER BY social_group_id, city_service_type_id"
    )
    insert_values(cur.fetchall(), f)

    print("\nEND TRANSACTION;", file=f)
