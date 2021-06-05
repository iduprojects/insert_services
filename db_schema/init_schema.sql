CREATE EXTENSION IF NOT EXISTS postgis;

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
		FOR r IN SELECT matviewname FROM pg_matviews WHERE schemaname = schema_arg and matviewname != 'age_sex_structure_district' and matviewname != 'age_sex_structure_municipality' and matviewname != 'all_services' and  matviewname != 'houses'
			and matviewname != 'social_structure_district' and matviewname != 'social_structure_municipality' 
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


SET default_tablespace = '';
SET default_table_access_method = heap;

-- Most basic

CREATE TABLE basement_types (
    id serial PRIMARY KEY NOT NULL,
    name character varying NOT NULL UNIQUE,
    code character varying NOT NULL UNIQUE
);
ALTER TABLE basement_types OWNER TO postgres;

CREATE TABLE floor_types (
    id serial PRIMARY KEY NOT NULL,
    name character varying NOT NULL UNIQUE,
    code character varying NOT NULL UNIQUE
);
ALTER TABLE floor_types OWNER TO postgres;

CREATE TABLE pollution_categories (
    id serial PRIMARY KEY NOT NULL,
    name character varying NOT NULL UNIQUE,
    code character varying NOT NULL UNIQUE
);
ALTER TABLE pollution_categories OWNER TO postgres;

CREATE TABLE living_situations (
    id serial PRIMARY KEY NOT NULL,
    name character varying NOT NULL UNIQUE,
    code character varying NOT NULL UNIQUE
);
ALTER TABLE living_situations OWNER TO postgres;

CREATE TABLE confessions (
    id serial PRIMARY KEY NOT NULL,
    name character varying,
    code character varying
);
ALTER TABLE confessions OWNER TO postgres;

CREATE TABLE religions (
    id serial PRIMARY KEY NOT NULL,
    name character varying,
    code character varying
);
ALTER TABLE religions OWNER TO postgres;

CREATE TABLE religious_object_types (
    id serial PRIMARY KEY NOT NULL,
    name character varying NOT NULL,
    code character varying NOT NULL UNIQUE
);
ALTER TABLE religious_object_types OWNER TO postgres;

-- Basic tables

CREATE TABLE social_groups (
    id serial PRIMARY KEY NOT NULL,
    name character varying UNIQUE,
    code character varying UNIQUE,
    parent_id integer REFERENCES social_groups(id)
);
ALTER TABLE social_groups OWNER TO postgres;

CREATE TABLE districts (
    id serial PRIMARY KEY NOT NULL,
    full_name character varying NOT NULL,
    short_name character varying NOT NULL,
    population integer,
    geometry geometry(Geometry, 4326) NOT NULL,
    center geometry(Point, 4326),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE districts OWNER TO postgres;

CREATE TABLE municipalities (
    id serial PRIMARY KEY NOT NULL,
    district_id integer REFERENCES districts(id),
    full_name character varying NOT NULL,
    short_name character varying NOT NULL,
    geometry geometry(Geometry, 4326) NOT NULL,
    center geometry(Point, 4326),
    population integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE municipalities OWNER TO postgres;

CREATE TABLE blocks (
    id serial PRIMARY KEY NOT NULL,
    municipality_id integer REFERENCES municipalities(id),
    population integer,
    geometry geometry(Geometry, 4326) NOT NULL,
    center geometry(Point, 4326),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE blocks OWNER TO postgres;

CREATE TABLE infrastructure_types (
    id serial PRIMARY KEY NOT NULL,
    name character varying NOT NULL UNIQUE,
    code character varying NOT NULL UNIQUE
);
ALTER TABLE infrastructure_types OWNER TO postgres;

CREATE TABLE city_functions (
    id serial PRIMARY KEY NOT NULL,
    name character varying NOT NULL UNIQUE,
    code character varying NOT NULL UNIQUE,
    infrastructure_type_id integer REFERENCES infrastructure_types(id)
);
ALTER TABLE city_functions OWNER TO postgres;

CREATE TABLE service_types (
    id serial PRIMARY KEY NOT NULL,
    name character varying NOT NULL UNIQUE,
    code character varying NOT NULL UNIQUE,
    capacity_min integer,
    capacity_max integer,
    city_function_id integer REFERENCES city_functions(id),
    status_min smallint,
    status_max smallint
);
ALTER TABLE service_types OWNER TO postgres;

-- Objects

CREATE TABLE physical_objects (
    id serial PRIMARY KEY NOT NULL,
    parent_id integer REFERENCES physical_objects(id),
    pollution_category_id smallint REFERENCES pollution_categories(id),
    osm_id character varying,
    geometry geometry(Geometry, 4326) NOT NULL,
    description character varying NOT NULL,
    center geometry(Point, 4326) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE physical_objects OWNER TO postgres;

CREATE TABLE functional_objects (
    id serial PRIMARY KEY NOT NULL,
    name character varying NOT NULL,
    opening_hours character varying,
    website character varying,
    phone character varying,
    capacity integer,
    city_function_id integer REFERENCES city_functions(id),
    service_type_id integer REFERENCES service_types(id),
    infrastructure_type_id integer REFERENCES infrastructure_types(id),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE functional_objects OWNER TO postgres;

CREATE TABLE phys_objs_fun_objs (
    phys_obj_id serial  NOT NULL,
    fun_obj_id serial NOT NULL,
    PRIMARY KEY(phys_obj_id, fun_obj_id)
);
ALTER TABLE phys_objs_fun_objs OWNER TO postgres;

CREATE TABLE religious_objects (
    id serial PRIMARY KEY NOT NULL,
    functional_object_id integer REFERENCES functional_objects(id) NOT NULL,
    type_id smallint REFERENCES religious_object_types(id),
    religion_id integer REFERENCES religions(id),
    confession_id integer REFERENCES confessions(id),
    properties jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE religious_objects OWNER TO postgres;

CREATE TABLE residential_objects (
    id serial PRIMARY KEY NOT NULL,
    functional_object_id integer REFERENCES functional_objects(id) NOT NULL,
    living_space double precision,
    residents_number smallint,
    gascentral boolean,
    hotwater boolean,
    electricity boolean,
    garbage_chute smallint,
    lift smallint,
    failure boolean,
    properties jsonb,
    population_balanced integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE residential_objects OWNER TO postgres;

-- Other

CREATE TABLE stat_age_sex_structure_house (
    id serial PRIMARY KEY NOT NULL,
    house_id integer REFERENCES residential_objects(id),
    age smallint,
    men_number smallint,
    women_number smallint,
    district_id integer REFERENCES districts(id),
    municipality_id integer REFERENCES municipalities(id)
);
ALTER TABLE stat_age_sex_structure_house OWNER TO postgres;

CREATE TABLE buildings (
    id serial PRIMARY KEY NOT NULL,
    physical_object_id integer REFERENCES physical_objects(id) NOT NULL,
    basement_type_id integer,
    floor_type_id integer,
    address character varying NOT NULL,
    year_construct integer,
    year_repair integer,
    basement_area double precision,
    height double precision,
    floors smallint,
    project_type character varying,
    is_temp boolean,
    properties jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);
ALTER TABLE buildings OWNER TO postgres;

CREATE TABLE stat_age_sex_social_district (
    id serial PRIMARY KEY NOT NULL,
    district_id integer REFERENCES districts(id) NOT NULL,
    social_group_id integer REFERENCES social_groups(id) NOT NULL,
    age smallint,
    year smallint,
    men integer,
    women integer
);
ALTER TABLE stat_age_sex_social_district OWNER TO postgres;

CREATE TABLE functional_objects_blocks (
    block_id integer NOT NULL,
    service_id integer REFERENCES service_types(id) NOT NULL,
    count integer NOT NULL,
    service_load_mean integer NOT NULL,
    service_load_min integer NOT NULL,
    service_load_max integer NOT NULL,
    reserve_resourses_mean integer NOT NULL,
    reserve_resourses_min integer NOT NULL,
    reserve_resourses_max integer NOT NULL,
    evaluation_mean integer NOT NULL,
    evaluation_min integer NOT NULL,
    evaluation_max integer NOT NULL
);
ALTER TABLE functional_objects_blocks OWNER TO postgres;

CREATE TABLE functional_objects_districts (
    district_id integer REFERENCES districts(id) NOT NULL,
    service_id integer REFERENCES service_types(id) NOT NULL,
    count integer NOT NULL,
    service_load_min integer NOT NULL,
    service_load_mean integer NOT NULL,
    service_load_max integer NOT NULL,
    reserve_resourses_min integer NOT NULL,
    reserve_resourses_mean integer NOT NULL,
    reserve_resourses_max integer NOT NULL,
    evaluation_mean integer NOT NULL,
    evaluation_min integer NOT NULL,
    evaluation_max integer NOT NULL
);
ALTER TABLE functional_objects_districts OWNER TO postgres;

CREATE TABLE functional_objects_municipalities (
    municipality_id integer REFERENCES municipalities(id) NOT NULL,
    service_id integer REFERENCES service_types(id) NOT NULL,
    count integer NOT NULL,
    service_load_mean integer NOT NULL,
    service_load_min integer NOT NULL,
    service_load_max integer NOT NULL,
    reserve_resourses_mean integer NOT NULL,
    reserve_resourses_min integer NOT NULL,
    reserve_resourses_max integer NOT NULL,
    evaluation_mean integer NOT NULL,
    evaluation_min integer NOT NULL,
    evaluation_max integer NOT NULL
);
ALTER TABLE functional_objects_municipalities OWNER TO postgres;

CREATE TABLE functional_objects_values (
    functional_object_id integer REFERENCES functional_objects(id) NOT NULL,
    radius integer,
    transport_time integer,
    houses_in_radius integer NOT NULL,
    people_in_radius integer NOT NULL,
    service_load integer NOT NULL,
    needed_capacity integer NOT NULL,
    reserve_resource integer NOT NULL,
    evaluation integer NOT NULL
);
ALTER TABLE functional_objects_values OWNER TO postgres;

CREATE TABLE houses_provision (
    house_id integer REFERENCES residential_objects(id) NOT NULL,
    service_type_id integer NOT NULL,
    reserve_resource integer NOT NULL,
    provision integer NOT NULL,
    PRIMARY KEY(house_id, service_type_id)
);
ALTER TABLE houses_provision OWNER TO postgres;

CREATE TABLE needs (
    id serial PRIMARY KEY NOT NULL,
    social_group_id integer REFERENCES social_groups(id) NOT NULL,
    living_situation_id integer REFERENCES living_situations(id) NOT NULL,
    service_type_id integer REFERENCES service_types(id) NOT NULL,
    walking integer,
    public_transport integer,
    personal_transport integer,
    intensity integer,
    UNIQUE (social_group_id, living_situation_id, service_type_id)
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

CREATE TABLE stat_social_structure_house (
    id serial PRIMARY KEY NOT NULL,
    house_id integer REFERENCES residential_objects(id),
    social_group_id integer REFERENCES social_groups(id),
    number smallint,
    district_id integer REFERENCES districts(id),
    municipality_id integer REFERENCES municipalities(id)
);
ALTER TABLE stat_social_structure_house OWNER TO postgres;

CREATE TABLE stat_age_sex_structure_municipality (
    id serial PRIMARY KEY NOT NULL,
    municipality_id integer REFERENCES municipalities(id),
    age smallint,
    men_number smallint,
    women_number smallint,
    year smallint
);
ALTER TABLE stat_age_sex_structure_municipality OWNER TO postgres;

CREATE MATERIALIZED VIEW stat_age_sex_structure_district AS
 SELECT row_number() OVER () AS id,
    m.district_id,
    sassm.age,
    sum(sassm.men_number) AS men_number,
    sum(sassm.women_number) AS women_number
   FROM (stat_age_sex_structure_municipality sassm
     JOIN municipalities m ON ((sassm.municipality_id = m.id)))
  GROUP BY m.district_id, sassm.age
  WITH NO DATA;
ALTER TABLE stat_age_sex_structure_district OWNER TO postgres;

CREATE MATERIALIZED VIEW stat_social_structure_district AS
 SELECT row_number() OVER () AS id,
    stat_age_sex_social_district.district_id,
    stat_age_sex_social_district.social_group_id,
    (sum(stat_age_sex_social_district.men) + sum(stat_age_sex_social_district.women)) AS number
   FROM stat_age_sex_social_district
  GROUP BY stat_age_sex_social_district.district_id, stat_age_sex_social_district.social_group_id
  WITH NO DATA;
ALTER TABLE stat_social_structure_district OWNER TO postgres;

CREATE MATERIALIZED VIEW stat_social_structure_municipality AS
 SELECT row_number() OVER () AS id,
    stat_social_structure_house.municipality_id,
    stat_social_structure_house.social_group_id,
    sum(stat_social_structure_house.number) AS number
   FROM stat_social_structure_house
  GROUP BY stat_social_structure_house.municipality_id, stat_social_structure_house.social_group_id
  WITH NO DATA;
ALTER TABLE stat_social_structure_municipality OWNER TO postgres;

CREATE TABLE value_types (
    id serial PRIMARY KEY NOT NULL,
    parent_id integer REFERENCES value_types(id),
    name character varying NOT NULL,
    code character varying NOT NULL UNIQUE
);
ALTER TABLE value_types OWNER TO postgres;

-- Materialized views

CREATE MATERIALIZED VIEW houses AS
 SELECT f.id,
    r.id AS residential_object_id,
    p.geometry,
    p.center,
    b.address,
    b.year_construct,
    b.year_repair,
    b.floors,
    b.height,
    b.basement_area,
    b.project_type,
    b.is_temp,
    f.name,
    f.capacity,
    f.opening_hours,
    f.website,
    f.phone,
    bt.name AS basement_type,
    ft.name AS floor_type,
    pc.name AS pollution_category,
    r.living_space,
    r.residents_number,
    r.population_balanced,
    r.gascentral,
    r.hotwater,
    r.electricity,
    r.garbage_chute,
    r.lift,
    r.failure,
    p.description,
    dt.id AS district_id,
    mt.id AS municipality_id,
    bl.id AS block_id,
    GREATEST(r.updated_at, f.updated_at, p.updated_at, b.updated_at) AS updated_at,
    GREATEST(r.created_at, f.created_at, p.created_at, b.created_at) AS created_at
   FROM (((((((((((residential_objects r
     JOIN functional_objects f ON ((r.functional_object_id = f.id)))
     JOIN phys_objs_fun_objs pf ON ((f.id = pf.fun_obj_id)))
     JOIN physical_objects p ON ((pf.phys_obj_id = p.id)))
     JOIN buildings b ON ((p.id = b.physical_object_id)))
     JOIN infrastructure_types it ON ((it.id = f.infrastructure_type_id)))
     LEFT JOIN pollution_categories pc ON ((p.pollution_category_id = pc.id)))
     LEFT JOIN basement_types bt ON ((b.basement_type_id = bt.id)))
     LEFT JOIN floor_types ft ON ((b.floor_type_id = ft.id)))
     LEFT JOIN districts dt ON (
        CASE
            WHEN ((st_geometrytype(p.geometry) = 'ST_Polygon'::text) OR (st_geometrytype(p.geometry) = 'ST_MultiPolygon'::text)) THEN (st_intersects(p.geometry, dt.geometry) AND ((st_area(st_intersection(p.geometry, dt.geometry)) / st_area(p.geometry)) > (0.5)::double precision))
            ELSE st_within(p.geometry, dt.geometry)
        END))
     LEFT JOIN municipalities mt ON (
        CASE
            WHEN ((st_geometrytype(p.geometry) = 'ST_Polygon'::text) OR (st_geometrytype(p.geometry) = 'ST_MultiPolygon'::text)) THEN (st_intersects(p.geometry, mt.geometry) AND ((st_area(st_intersection(p.geometry, mt.geometry)) / st_area(p.geometry)) > (0.5)::double precision))
            ELSE st_within(p.geometry, mt.geometry)
        END))
     LEFT JOIN blocks bl ON (
        CASE
            WHEN ((st_geometrytype(p.geometry) = 'ST_Polygon'::text) OR (st_geometrytype(p.geometry) = 'ST_MultiPolygon'::text)) THEN (st_intersects(p.geometry, bl.geometry) AND ((st_area(st_intersection(p.geometry, bl.geometry)) / st_area(p.geometry)) > (0.5)::double precision))
            ELSE st_within(p.geometry, bl.geometry)
        END))
  WHERE ((r.living_space IS NOT NULL) AND (r.living_space <> (0)::double precision) AND (r.failure IS NOT NULL) AND (r.population_balanced IS NOT NULL))
  WITH NO DATA;
ALTER TABLE houses OWNER TO postgres;

CREATE MATERIALIZED VIEW all_services AS
 SELECT p.id AS phys_id,
    f.id AS func_id,
    p.geometry,
    p.center,
    p.description,
    f.name AS service_name,
    f.opening_hours,
    f.website,
    f.phone,
    b.address,
    dt.id AS district_id,
    dt.short_name AS district_name,
    mt.id AS municipal_id,
    mt.short_name AS municipal_name,
    bl.id AS block_id,
    b.year_construct,
    b.year_repair,
    b.floors,
    b.height,
    b.basement_area,
    b.project_type,
    bt.name AS basement_type,
    ft.name AS floor_type,
    pc.name AS pollution_category,
    f.capacity,
    st.name AS service_type,
    p.created_at AS phys_created_at,
    p.updated_at AS phys_updated_at,
    f.created_at AS func_created_at,
    f.updated_at AS func_updated_at
   FROM ((((((((((functional_objects f
     JOIN service_types st ON ((f.service_type_id = st.id)))
     JOIN phys_objs_fun_objs pf ON ((f.id = pf.fun_obj_id)))
     JOIN physical_objects p ON ((pf.phys_obj_id = p.id)))
     LEFT JOIN buildings b ON ((p.id = b.physical_object_id)))
     LEFT JOIN pollution_categories pc ON ((p.pollution_category_id = pc.id)))
     LEFT JOIN basement_types bt ON ((b.basement_type_id = bt.id)))
     LEFT JOIN floor_types ft ON ((b.floor_type_id = ft.id)))
     LEFT JOIN districts dt ON (
        CASE
            WHEN ((st_geometrytype(p.geometry) = 'ST_Polygon'::text) OR (st_geometrytype(p.geometry) = 'ST_MultiPolygon'::text)) THEN (st_intersects(p.geometry, dt.geometry) AND ((st_area(st_intersection(p.geometry, dt.geometry)) / st_area(p.geometry)) > (0.5)::double precision))
            ELSE st_within(p.geometry, dt.geometry)
        END))
     LEFT JOIN municipalities mt ON (
        CASE
            WHEN ((st_geometrytype(p.geometry) = 'ST_Polygon'::text) OR (st_geometrytype(p.geometry) = 'ST_MultiPolygon'::text)) THEN (st_intersects(p.geometry, mt.geometry) AND ((st_area(st_intersection(p.geometry, mt.geometry)) / st_area(p.geometry)) > (0.5)::double precision))
            ELSE st_within(p.geometry, mt.geometry)
        END))
     LEFT JOIN blocks bl ON (
        CASE
            WHEN ((st_geometrytype(p.geometry) = 'ST_Polygon'::text) OR (st_geometrytype(p.geometry) = 'ST_MultiPolygon'::text)) THEN (st_intersects(p.geometry, bl.geometry) AND ((st_area(st_intersection(p.geometry, bl.geometry)) / st_area(p.geometry)) > (0.5)::double precision))
            ELSE st_within(p.geometry, bl.geometry)
        END))
  WITH NO DATA;
ALTER TABLE all_services OWNER TO postgres;