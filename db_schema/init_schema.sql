CREATE EXTENSION IF NOT EXISTS postgis;

SET default_tablespace = '';
SET default_table_access_method = heap;

-- Basic

CREATE TYPE city_division_type AS ENUM (
    'ADMIN_UNIT_PARENT',
    'MUNICIPALITY_PARENT',
    'NO_PARENT'
);

CREATE TABLE administrative_unit_types (
    id serial PRIMARY KEY NOT NULL,
    full_name character varying(50) UNIQUE NOT NULL,
    short_name character varying(10) UNIQUE NOT NULL
);
ALTER TABLE administrative_unit_types OWNER TO postgres;

CREATE TABLE municipality_types (
    id serial PRIMARY KEY NOT NULL,
    full_name character varying(50) UNIQUE NOT NULL,
    short_name character varying(10) UNIQUE NOT NULL
);
ALTER TABLE municipality_types OWNER TO postgres;

CREATE TABLE living_situations (
    id serial PRIMARY KEY NOT NULL,
    name character varying NOT NULL UNIQUE,
    code character varying NOT NULL UNIQUE
);
ALTER TABLE living_situations OWNER TO postgres;

CREATE TABLE social_groups (
    id serial PRIMARY KEY NOT NULL,
    name character varying UNIQUE,
    code character varying UNIQUE,
    parent_id integer REFERENCES social_groups(id)
);
ALTER TABLE social_groups OWNER TO postgres;

CREATE TABLE cities (
    id serial PRIMARY KEY NOT NULL,
    name character varying(50),
    geometry geometry(Geometry, 4326) NOT NULL,
    center geometry(Point, 4326) NOT NULL,
    population int,
    city_division_type city_division_type,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE cities OWNER TO postgres;

CREATE TABLE administrative_units (
    id serial PRIMARY KEY NOT NULL,
    parent_id int REFERENCES administrative_units(id),
    city_id int REFERENCES cities(id) NOT NULL,
    type_id int REFERENCES administrative_unit_types(id),
    name character varying NOT NULL,
    geometry geometry(Geometry, 4326) NOT NULL,
    center geometry(Point, 4326),
    population int,
    municipality_parent_id int,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE administrative_units OWNER TO postgres;

CREATE TABLE municipalities (
    id serial PRIMARY KEY NOT NULL,
    parent_id int REFERENCES municipalities(id),
    city_id int REFERENCES cities(id) NOT NULL,
    type_id int REFERENCES administrative_unit_types(id),
    name character varying NOT NULL,
    geometry geometry(Geometry, 4326) NOT NULL,
    center geometry(Point, 4326),
    population int,
    admin_unit_parent_id int REFERENCES administrative_units(id),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE municipalities OWNER TO postgres;

ALTER TABLE administrative_units ADD CONSTRAINT administrative_units_municipality_id_fkey FOREIGN KEY (municipality_parent_id) REFERENCES municipalities(id);

CREATE TABLE blocks (
    id serial PRIMARY KEY NOT NULL,
    city_id int REFERENCES cities(id),
    population int,
    geometry geometry(Geometry, 4326) NOT NULL,
    center geometry(Point, 4326),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE blocks OWNER TO postgres;

CREATE TABLE city_infrastructure_types (
    id serial PRIMARY KEY NOT NULL,
    name character varying NOT NULL UNIQUE,
    code character varying NOT NULL UNIQUE
);
ALTER TABLE city_infrastructure_types OWNER TO postgres;

CREATE TABLE city_functions (
    id serial PRIMARY KEY NOT NULL,
    name character varying NOT NULL UNIQUE,
    code character varying NOT NULL UNIQUE,
    city_infrastructure_type_id integer REFERENCES city_infrastructure_types(id)
);
ALTER TABLE city_functions OWNER TO postgres;

CREATE TABLE city_service_types (
    id serial PRIMARY KEY NOT NULL,
    city_function_id integer REFERENCES city_functions(id),
    name character varying NOT NULL UNIQUE,
    code character varying NOT NULL UNIQUE,
    capacity_min integer NOT NULL,
    capacity_max integer NOT NULL,
    status_min smallint NOT NULL,
    status_max smallint NOT NULL,
    is_building boolean NOT NULL
);
ALTER TABLE city_service_types OWNER TO postgres;

-- Objects

CREATE TABLE physical_objects (
    id serial PRIMARY KEY NOT NULL,
    osm_id character varying,
    geometry geometry(Geometry, 4326) NOT NULL,
    center geometry(Point, 4326),
    city_id int REFERENCES cities(id),
    municipality_id int REFERENCES municipalities(id),
    administrative_unit_id int REFERENCES administrative_units(id),
    block_id int REFERENCES blocks(id),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE physical_objects OWNER TO postgres;

CREATE TABLE functional_objects (
    id serial PRIMARY KEY NOT NULL,
    physical_object_id int REFERENCES physical_objects(id),
    name character varying NOT NULL,
    opening_hours character varying,
    website character varying,
    phone character varying,
    capacity integer,
    city_infrastructure_type_id integer REFERENCES city_infrastructure_types(id),
    city_function_id integer REFERENCES city_functions(id),
    city_service_type_id integer REFERENCES city_service_types(id),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE functional_objects OWNER TO postgres;

-- Other

CREATE TABLE buildings (
    id serial PRIMARY KEY NOT NULL,
    physical_object_id integer REFERENCES physical_objects(id) NOT NULL,
    address character varying(200),
    project_type character varying(100),
    building_date character varying(50),
    building_area real,
    living_area real,
    storeys_count smallint,
    resident_number smallint,
    central_heating boolean,
    central_hotwater boolean,
    central_electro boolean,
    central_gas boolean,
    refusechute boolean,
    ukname character varying(100),
    failure boolean,
    lift_count smallint,
    repair_years character varying(100)
);
ALTER TABLE buildings OWNER TO postgres;

CREATE TABLE needs (
    id serial PRIMARY KEY NOT NULL,
    social_group_id integer REFERENCES social_groups(id) NOT NULL,
    living_situation_id integer REFERENCES living_situations(id) NOT NULL,
    city_service_type_id integer REFERENCES city_service_types(id) NOT NULL,
    walking integer,
    public_transport integer,
    personal_transport integer,
    intensity integer,
    UNIQUE (social_group_id, living_situation_id, city_service_type_id)
);
ALTER TABLE needs OWNER TO postgres;

CREATE TABLE "values" (
    id serial PRIMARY KEY NOT NULL,
    city_function_id integer REFERENCES city_functions(id) NOT NULL,
    social_group_id integer REFERENCES social_groups(id) NOT NULL,
    significance real,
    UNIQUE(city_function_id, social_group_id)
);
ALTER TABLE "values" OWNER TO postgres;

-- Materialized views

CREATE MATERIALIZED VIEW houses AS (
    SELECT f.id AS functional_object_id,
        p.id AS physical_object_id,
        b.id AS building_id,
        p.geometry,
        p.center,
        b.address,
        b.project_type,
        b.building_date,
        b.repair_years,
        b.building_area,
        b.living_area,
        b.storeys_count,
        b.central_heating,
        b.central_hotwater,
        b.central_electro,
        b.central_gas,
        b.refusechute,
        b.ukname,
        b.lift_count,
        b.failure,
        b.resident_number,
        c.name AS city,
        c.id AS city_id,
        au.name AS administrative_unit,
        au.id AS administrative_unit_id,
        mu.name AS municipality,
        mu.id AS municipality_id,
        p.block_id AS block_id,
        GREATEST(f.updated_at, p.updated_at) AS updated_at,
        GREATEST(f.created_at, p.created_at) AS created_at
    FROM functional_objects f
        JOIN city_service_types st ON f.city_service_type_id = st.id
        JOIN physical_objects p ON f.physical_object_id = p.id
        JOIN buildings b ON p.id = b.physical_object_id
        JOIN cities c ON p.city_id = c.id
        LEFT JOIN administrative_units au ON p.administrative_unit_id = au.id
        LEFT JOIN municipalities mu ON p.municipality_id = mu.id
    WHERE st.name = 'Жилье' AND b.resident_number > 0
);
ALTER TABLE houses OWNER TO postgres;

CREATE MATERIALIZED VIEW all_houses AS (
    SELECT f.id AS functional_object_id,
        p.id AS physical_object_id,
        b.id AS building_id,
        p.geometry,
        p.center,
        b.address,
        b.project_type,
        b.building_date,
        b.repair_years,
        b.building_area,
        b.living_area,
        b.storeys_count,
        b.central_heating,
        b.central_hotwater,
        b.central_electro,
        b.central_gas,
        b.refusechute,
        b.ukname,
        b.lift_count,
        b.failure,
        b.resident_number,
        c.name AS city,
        c.id AS city_id,
        au.name AS administrative_unit,
        au.id AS administrative_unit_id,
        mu.name AS municipality,
        mu.id AS municipality_id,
        p.block_id AS block_id,
        GREATEST(f.updated_at, p.updated_at) AS updated_at,
        GREATEST(f.created_at, p.created_at) AS created_at
    FROM functional_objects f
        JOIN city_service_types st ON f.city_service_type_id = st.id
        JOIN physical_objects p ON f.physical_object_id = p.id
        JOIN buildings b ON p.id = b.physical_object_id
        JOIN cities c ON p.city_id = c.id
        LEFT JOIN administrative_units au ON p.administrative_unit_id = au.id
        LEFT JOIN municipalities mu ON p.municipality_id = mu.id
    WHERE st.name = 'Жилье'
);
ALTER TABLE all_houses OWNER TO postgres;

CREATE MATERIALIZED VIEW all_services AS (
    SELECT f.id AS functional_object_id,
        p.id AS physical_object_id,
        b.id AS building_id,
        p.geometry,
        p.center,
        st.name AS city_service_type,
        st.id AS city_service_type_id,
        f.name AS service_name,
        f.opening_hours,
        f.website,
        f.phone,
        b.address,
        c.name AS city,
        c.id AS city_id,
        au.name AS administrative_unit,
        au.id AS administrative_unit_id,
        mu.name AS municipality,
        mu.id AS municipality_id,
        p.block_id AS block_id,
        f.capacity,
        GREATEST(f.updated_at, p.updated_at) AS updated_at,
        GREATEST(f.created_at, p.created_at) AS created_at
    FROM functional_objects f
        JOIN city_service_types st ON f.city_service_type_id = st.id
        JOIN physical_objects p ON f.physical_object_id = p.id
        JOIN cities c ON p.city_id = c.id
        LEFT JOIN buildings b ON p.id = b.physical_object_id
        LEFT JOIN administrative_units au ON p.administrative_unit_id = au.id
        LEFT JOIN municipalities mu ON p.municipality_id = mu.id
);
ALTER TABLE all_services OWNER TO postgres;

-- functions

CREATE FUNCTION random_between(low integer, high integer) RETURNS integer
    LANGUAGE plpgsql STRICT
    AS $$
BEGIN
   RETURN floor(random()* (high-low + 1) + low);
END;
$$;
ALTER FUNCTION random_between(low integer, high integer) OWNER TO postgres;

CREATE FUNCTION refreshallmaterializedviews(schema_arg text DEFAULT 'public'::text) RETURNS integer
    LANGUAGE plpgsql
    AS $$
	DECLARE
		r RECORD;
	BEGIN
		RAISE NOTICE 'Refreshing materialized view in schema %', schema_arg;
		FOR r IN SELECT matviewname FROM pg_matviews WHERE schemaname = schema_arg and matviewname != 'age_sex_structure_district' and matviewname != 'all_services' and  matviewname != 'houses'
			and matviewname != 'social_structure_district' 
		LOOP
			RAISE NOTICE 'Refreshing %.%', schema_arg, r.matviewname;
			EXECUTE 'REFRESH MATERIALIZED VIEW ' || schema_arg || '.' || r.matviewname; 
		END LOOP;
		
		RETURN 1;
	END 
$$;
ALTER FUNCTION refreshallmaterializedviews(schema_arg text) OWNER TO postgres;

CREATE FUNCTION trigger_set_timestamp() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;
ALTER FUNCTION trigger_set_timestamp() OWNER TO postgres;

CREATE FUNCTION update_physical_objects_location() RETURNS void
LANGUAGE SQL AS
$$
    UPDATE physical_objects p SET
        administrative_unit_id = (SELECT id FROM administrative_units WHERE ST_CoveredBy(p.center, geometry) LIMIT 1),
        municipality_id = (SELECT id FROM municipalities WHERE ST_CoveredBy(p.center, geometry) LIMIT 1),
        block_id = (SELECT id FROM blocks WHERE ST_CoveredBy(p.center, geometry) LIMIT 1)
    WHERE administrative_unit_id IS null OR municipality_id IS null OR block_id IS null;  
$$;
ALTER FUNCTION update_physical_objects_location OWNER TO postgres;