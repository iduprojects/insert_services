import psycopg2

host = 'localhost'
port = 5432
dbname = 'city_db_final'
user = 'postgres'
password = 'postgres'

conn: 'psycopg2.connection' = psycopg2.connect(host=host, port=port, dbname=dbname, user=user, password=password)

def to_sql(data) -> str:
    if data is None:
        return 'null'
    if isinstance(data, bool):
        return 'true' if data else 'false'
    return str(data)

def insert_values(items: list, file) -> None:
    print(f"\t({', '.join(map(to_sql, items[0]))})", end='', file=file)
    for values in items[1:]:
        print(f",\n\t({', '.join(map(to_sql, values))})", end='', file=file)
    print(';', file=file)

with open('init_data_new.sql', 'w', encoding='utf-8') as f:
    with conn, conn.cursor() as cur:
        print('BEGIN TRANSACTION;\n', file=f)

        print('INSERT INTO living_situations (name) VALUES', file=f)
        cur.execute("SELECT concat('''', name, '''') FROM living_situations ORDER BY id")
        insert_values(cur.fetchall(), f)

        print("\nINSERT INTO social_groups (name, code, social_group_value, parent_id) VALUES", file=f)
        cur.execute("SELECT concat('''', name, ''''), concat('''', code, ''''), social_group_value,"
                " concat('(SELECT id FROM social_groups WHERE code = ''', (SELECT code FROM social_groups WHERE id = sg.parent_id), ''')')"
                " FROM social_groups sg ORDER BY id")
        insert_values(cur.fetchall(), f)

        print('\nINSERT INTO city_infrastructure_types (name, code) VALUES', file=f)
        cur.execute("SELECT concat('''', name, ''''), concat('''', code, '''') FROM city_infrastructure_types ORDER BY id")
        insert_values(cur.fetchall(), f)

        print("\nINSERT INTO city_functions (name, code, city_infrastructure_type_id) VALUES", file=f)
        cur.execute("SELECT concat('''', name, ''''), concat('''', code, ''''),"
                " concat('(SELECT id FROM city_infrastructure_types WHERE code = ''', (SELECT code FROM city_infrastructure_types WHERE id = city_infrastructure_type_id), ''')')"
                " FROM city_functions ORDER BY id")
        insert_values(cur.fetchall(), f)

        print("\nINSERT INTO city_service_types (name, code, city_function_id, capacity_min, capacity_max, status_min, status_max, is_building) VALUES", file=f)
        cur.execute("SELECT concat('''', name, ''''), concat('''', code, ''''),"
                " concat('(SELECT id FROM city_functions WHERE code = ''', (SELECT code FROM city_functions WHERE id = city_function_id), ''')'),"
                " capacity_min, capacity_max, status_min, status_max, is_building"
                " FROM city_service_types ORDER BY id")
        insert_values(cur.fetchall(), f)

        print("\nINSERT INTO municipality_types (full_name, short_name) VALUES", file=f)
        cur.execute("SELECT concat('''', full_name, ''''), concat('''', short_name, '''')"
                " FROM municipality_types ORDER BY id")
        insert_values(cur.fetchall(), f)

        print("\nINSERT INTO administrative_unit_types (full_name, short_name) VALUES", file=f)
        cur.execute("SELECT concat('''', full_name, ''''), concat('''', short_name, '''')"
                " FROM administrative_unit_types ORDER BY id")
        insert_values(cur.fetchall(), f)

        print('\nEND TRANSACTION;', file=f)
