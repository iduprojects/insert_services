--- THIS SCRIPT IS DEPRECATED AND SHOULD BE REPLACED WITH ALEMBIC OR OTHER MIGRATOR ---
BEGIN TRANSACTION;

CREATE EXTENSION IF NOT EXISTS postgis;

SET default_tablespace = '';
SET default_table_access_method = heap;

-- Schemas and data types

CREATE SCHEMA social_stats;
CREATE SCHEMA provision;
CREATE SCHEMA maintenance;
CREATE TYPE social_stats_scenario AS ENUM ('neg', 'mod', 'pos');


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
    name character varying NOT NULL UNIQUE
);
ALTER TABLE living_situations OWNER TO postgres;

CREATE TABLE social_groups (
    id serial PRIMARY KEY NOT NULL,
    name character varying UNIQUE,
    code character varying UNIQUE,
    social_group_value float,
    parent_id integer REFERENCES social_groups(id)
);
ALTER TABLE social_groups OWNER TO postgres;

CREATE TABLE regions (
    id Serial PRIMARY KEY NOT NULL,
    name varchar(50) UNIQUE NOT NULL,
    code varchar(50) UNIQUE NOT NULL,
    geometry geometry(geometry, 4326) NOT NULL,
    center geometry(Point, 4326) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE regions OWNER TO postgres;

CREATE TABLE cities (
    id serial PRIMARY KEY NOT NULL,
    name character varying(50),
    code character varying(50),
    geometry geometry(Geometry, 4326) NOT NULL,
    center geometry(Point, 4326) NOT NULL,
    region_id integer REFERENCES regions(id),
    population int,
    city_division_type city_division_type DEFAULT 'ADMIN_UNIT_PARENT'::city_division_type,
    local_crs integer,
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
    municipality_id int REFERENCES municipalities(id),
    administrative_unit_id int REFERENCES administrative_units(id),
    population int,
    area float,
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
    is_building boolean NOT NULL,
    public_transport_time_normative integer,
    walking_radius_normative integer
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
    capacity integer NOT NULL,
    is_capacity_real boolean NOT NULL,
    city_infrastructure_type_id integer REFERENCES city_infrastructure_types(id) NOT NULL,
    city_function_id integer REFERENCES city_functions(id) NOT NULL,
    city_service_type_id integer REFERENCES city_service_types(id) NOT NULL,
    modeled jsonb NOT NULL DEFAULT '{}'::jsonb,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb,
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
    building_year smallint,
    building_area real,
    is_living boolean,
    living_area real,
    storeys_count smallint,
    resident_number smallint,
    population_balanced smallint,
    central_heating boolean,
    central_hotwater boolean,
    central_water boolean,
    central_electro boolean,
    central_gas boolean,
    refusechute boolean,
    ukname character varying(100),
    failure boolean,
    lift_count smallint,
    repair_years character varying(100),
    modeled jsonb NOT NULL DEFAULT '{}'::jsonb,
    properties jsonb NOT NULL DEFAULT '{}'::jsonb
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

CREATE TABLE provision.normatives (
    city_service_type_id integer REFERENCES city_service_types(id) NOT NULL PRIMARY KEY,
    normative float NOT NULL,
    max_load integer NOT NULL,
    radius_meters integer,
    public_transport_time integer,
    service_evaluation jsonb,
    house_evaluation jsonb,
    last_calculations timestamptz
);
ALTER TABLE provision.normatives OWNER TO postgres;

CREATE TABLE social_stats.sex_age_social_houses (
    id Serial NOT NULL,
    year smallint NOT NULL,
    scenario social_stats_scenario NOT NULL,
    building_id integer NOT NULL,
    social_group_id integer NOT NULL,
    men_0 smallint NOT NULL,  men_1 smallint NOT NULL,  men_2 smallint NOT NULL,  men_3 smallint NOT NULL,  men_4 smallint NOT NULL,
    men_5 smallint NOT NULL,  men_6 smallint NOT NULL,  men_7 smallint NOT NULL,  men_8 smallint NOT NULL,  men_9 smallint NOT NULL,
    men_10 smallint NOT NULL, men_11 smallint NOT NULL, men_12 smallint NOT NULL, men_13 smallint NOT NULL, men_14 smallint NOT NULL,
    men_15 smallint NOT NULL, men_16 smallint NOT NULL, men_17 smallint NOT NULL, men_18 smallint NOT NULL, men_19 smallint NOT NULL,
    men_20 smallint NOT NULL, men_21 smallint NOT NULL, men_22 smallint NOT NULL, men_23 smallint NOT NULL, men_24 smallint NOT NULL,
    men_25 smallint NOT NULL, men_26 smallint NOT NULL, men_27 smallint NOT NULL, men_28 smallint NOT NULL, men_29 smallint NOT NULL,
    men_30 smallint NOT NULL, men_31 smallint NOT NULL, men_32 smallint NOT NULL, men_33 smallint NOT NULL, men_34 smallint NOT NULL,
    men_35 smallint NOT NULL, men_36 smallint NOT NULL, men_37 smallint NOT NULL, men_38 smallint NOT NULL, men_39 smallint NOT NULL,
    men_40 smallint NOT NULL, men_41 smallint NOT NULL, men_42 smallint NOT NULL, men_43 smallint NOT NULL, men_44 smallint NOT NULL,
    men_45 smallint NOT NULL, men_46 smallint NOT NULL, men_47 smallint NOT NULL, men_48 smallint NOT NULL, men_49 smallint NOT NULL,
    men_50 smallint NOT NULL, men_51 smallint NOT NULL, men_52 smallint NOT NULL, men_53 smallint NOT NULL, men_54 smallint NOT NULL,
    men_55 smallint NOT NULL, men_56 smallint NOT NULL, men_57 smallint NOT NULL, men_58 smallint NOT NULL, men_59 smallint NOT NULL,
    men_60 smallint NOT NULL, men_61 smallint NOT NULL, men_62 smallint NOT NULL, men_63 smallint NOT NULL, men_64 smallint NOT NULL,
    men_65 smallint NOT NULL, men_66 smallint NOT NULL, men_67 smallint NOT NULL, men_68 smallint NOT NULL, men_69 smallint NOT NULL,
    men_70 smallint NOT NULL, men_71 smallint NOT NULL, men_72 smallint NOT NULL, men_73 smallint NOT NULL, men_74 smallint NOT NULL,
    men_75 smallint NOT NULL, men_76 smallint NOT NULL, men_77 smallint NOT NULL, men_78 smallint NOT NULL, men_79 smallint NOT NULL,
    men_80 smallint NOT NULL, men_81 smallint NOT NULL, men_82 smallint NOT NULL, men_83 smallint NOT NULL, men_84 smallint NOT NULL,
    men_85 smallint NOT NULL, men_86 smallint NOT NULL, men_87 smallint NOT NULL, men_88 smallint NOT NULL, men_89 smallint NOT NULL,
    men_90 smallint NOT NULL, men_91 smallint NOT NULL, men_92 smallint NOT NULL, men_93 smallint NOT NULL, men_94 smallint NOT NULL,
    men_95 smallint NOT NULL, men_96 smallint NOT NULL, men_97 smallint NOT NULL, men_98 smallint NOT NULL, men_99 smallint NOT NULL,
    men_100 smallint NOT NULL,
    women_0 smallint NOT NULL,  women_1 smallint NOT NULL,  women_2 smallint NOT NULL,  women_3 smallint NOT NULL,  women_4 smallint NOT NULL,
    women_5 smallint NOT NULL,  women_6 smallint NOT NULL,  women_7 smallint NOT NULL,  women_8 smallint NOT NULL,  women_9 smallint NOT NULL,
    women_10 smallint NOT NULL, women_11 smallint NOT NULL, women_12 smallint NOT NULL, women_13 smallint NOT NULL, women_14 smallint NOT NULL,
    women_15 smallint NOT NULL, women_16 smallint NOT NULL, women_17 smallint NOT NULL, women_18 smallint NOT NULL, women_19 smallint NOT NULL,
    women_20 smallint NOT NULL, women_21 smallint NOT NULL, women_22 smallint NOT NULL, women_23 smallint NOT NULL, women_24 smallint NOT NULL,
    women_25 smallint NOT NULL, women_26 smallint NOT NULL, women_27 smallint NOT NULL, women_28 smallint NOT NULL, women_29 smallint NOT NULL,
    women_30 smallint NOT NULL, women_31 smallint NOT NULL, women_32 smallint NOT NULL, women_33 smallint NOT NULL, women_34 smallint NOT NULL,
    women_35 smallint NOT NULL, women_36 smallint NOT NULL, women_37 smallint NOT NULL, women_38 smallint NOT NULL, women_39 smallint NOT NULL,
    women_40 smallint NOT NULL, women_41 smallint NOT NULL, women_42 smallint NOT NULL, women_43 smallint NOT NULL, women_44 smallint NOT NULL,
    women_45 smallint NOT NULL, women_46 smallint NOT NULL, women_47 smallint NOT NULL, women_48 smallint NOT NULL, women_49 smallint NOT NULL,
    women_50 smallint NOT NULL, women_51 smallint NOT NULL, women_52 smallint NOT NULL, women_53 smallint NOT NULL, women_54 smallint NOT NULL,
    women_55 smallint NOT NULL, women_56 smallint NOT NULL, women_57 smallint NOT NULL, women_58 smallint NOT NULL, women_59 smallint NOT NULL,
    women_60 smallint NOT NULL, women_61 smallint NOT NULL, women_62 smallint NOT NULL, women_63 smallint NOT NULL, women_64 smallint NOT NULL,
    women_65 smallint NOT NULL, women_66 smallint NOT NULL, women_67 smallint NOT NULL, women_68 smallint NOT NULL, women_69 smallint NOT NULL,
    women_70 smallint NOT NULL, women_71 smallint NOT NULL, women_72 smallint NOT NULL, women_73 smallint NOT NULL, women_74 smallint NOT NULL,
    women_75 smallint NOT NULL, women_76 smallint NOT NULL, women_77 smallint NOT NULL, women_78 smallint NOT NULL, women_79 smallint NOT NULL,
    women_80 smallint NOT NULL, women_81 smallint NOT NULL, women_82 smallint NOT NULL, women_83 smallint NOT NULL, women_84 smallint NOT NULL,
    women_85 smallint NOT NULL, women_86 smallint NOT NULL, women_87 smallint NOT NULL, women_88 smallint NOT NULL, women_89 smallint NOT NULL,
    women_90 smallint NOT NULL, women_91 smallint NOT NULL, women_92 smallint NOT NULL, women_93 smallint NOT NULL, women_94 smallint NOT NULL,
    women_95 smallint NOT NULL, women_96 smallint NOT NULL, women_97 smallint NOT NULL, women_98 smallint NOT NULL, women_99 smallint NOT NULL,
    women_100 smallint NOT NULL,
    PRIMARY KEY (year, scenario, building_id, social_group_id)
);
ALTER TABLE social_stats.sex_age_social_houses OWNER TO postgres;
CREATE INDEX sex_age_social_houses_house_scenario_social_group_id ON social_stats.sex_age_social_houses (building_id, scenario, social_group_id);
CREATE INDEX sex_age_social_houses_year_scenario_social_group_house ON social_stats.sex_age_social_houses (year, scenario, social_group_id, building_id);

CREATE TABLE maintenance.social_groups_city_service_types (
    social_group_id      integer REFERENCES social_groupS(id) NOT NULL,
    city_service_type_id integer REFERENCES city_service_typeS(id) NOT NULL,
    PRIMARY KEY (social_group_id, city_service_type_id)
);
ALTER TABLE maintenance.social_groups_city_service_types OWNER TO postgres;

-- Materialized views

CREATE MATERIALIZED VIEW all_services AS (
    SELECT f.id AS functional_object_id,
        p.id AS physical_object_id,
        b.id AS building_id,
        p.geometry,
        p.center,
        st.name AS city_service_type,
        st.id AS city_service_type_id,
        st.code AS city_service_type_code,
        f.name AS service_name,
        f.opening_hours,
        f.website,
        f.phone,
        b.address,
        b.is_living,
        c.name AS city,
        c.id AS city_id,
        au.name AS administrative_unit,
        au.id AS administrative_unit_id,
        mu.name AS municipality,
        mu.id AS municipality_id,
        p.block_id,
        f.capacity,
        f.is_capacity_real,
        GREATEST(f.updated_at, p.updated_at) AS updated_at,
        GREATEST(f.created_at, p.created_at) AS created_at
    FROM functional_objects f
        JOIN city_service_types st ON f.city_service_type_id = st.id
        JOIN physical_objects p ON f.physical_object_id = p.id
        JOIN cities c ON p.city_id = c.id
        LEFT JOIN buildings b ON p.id = b.physical_object_id
        LEFT JOIN administrative_units au ON p.administrative_unit_id = au.id
        LEFT JOIN municipalities mu ON p.municipality_id = mu.id
    WHERE st.code::text <> 'houses'::text
);
ALTER TABLE all_services OWNER TO postgres;

CREATE MATERIALIZED VIEW all_buildings AS (
    SELECT DISTINCT ON (b.id) b.id AS building_id,
        b.physical_object_id,
        b.address,
        b.project_type,
        b.building_year,
        b.repair_years,
        b.building_area,
        b.living_area,
        b.storeys_count,
        b.central_heating,
        b.central_hotwater,
        b.central_water,
        b.central_electro,
        b.central_gas,
        b.refusechute,
        b.ukname,
        b.lift_count,
        b.failure,
        b.is_living,
        b.resident_number,
        b.population_balanced,
        b.properties,
        b.modeled,
        f.id AS functional_object_id,
        p.osm_id,
        p.geometry,
        p.center,
        c.name AS city,
        c.id AS city_id,
        c.code AS city_code,
        au.name AS administrative_unit,
        au.id AS administrative_unit_id,
        mu.name AS municipality,
        mu.id AS municipality_id,
        p.block_id,
        f.created_at AS functional_object_created_at,
        f.updated_at AS functional_object_updated_at,
        p.created_at AS physical_object_created_at,
        p.updated_at AS physical_object_updated_at,
        GREATEST(f.updated_at, p.updated_at) AS updated_at,
        GREATEST(f.created_at, p.created_at) AS created_at
    FROM buildings b
        JOIN physical_objects p ON b.physical_object_id = p.id
        LEFT JOIN functional_objects f ON b.physical_object_id = f.physical_object_id AND f.city_service_type_id = (( SELECT city_service_types.id
            FROM city_service_types
            WHERE city_service_types.code::text = 'houses'::text))
        LEFT JOIN cities c ON p.city_id = c.id
        LEFT JOIN administrative_units au ON p.administrative_unit_id = au.id
        LEFT JOIN municipalities mu ON p.municipality_id = mu.id
);
ALTER TABLE all_buildings OWNER TO postgres;

CREATE MATERIALIZED VIEW cities_statistics AS (
    SELECT c.id,
        c.name,
        COALESCE(services_stats.unique_service_types, 0) AS unique_service_types,
        COALESCE(services_stats.total_services, 0) AS total_services,
        COALESCE(buildings_stats.living, 0) AS living_houses,
        COALESCE(buildings_stats.total, 0) AS buildings,
        GREATEST(
            c.updated_at,
            services_stats.updated_at,
            blocks_stats.updated_at,
            adm_stats.updated_at,
            mo_stats.updated_at
        ) AS updated_at
        FROM cities c
        LEFT JOIN (
            SELECT p.city_id,
                (count(DISTINCT f.city_service_type_id))::integer AS unique_service_types,
                (count(f.city_service_type_id))::integer AS total_services,
                max(GREATEST(f.updated_at, p.updated_at)) AS updated_at
            FROM (
                    functional_objects f
                    JOIN physical_objects p ON ((f.physical_object_id = p.id))
                )
            GROUP BY p.city_id
        ) services_stats ON ((services_stats.city_id = c.id))
        LEFT JOIN (
            SELECT p.city_id,
                sum(CASE WHEN (b.is_living = true) THEN 1 ELSE 0 END )::integer AS living,
                (count(b.id))::integer AS total
            FROM (
                    buildings b
                    JOIN physical_objects p ON ((b.physical_object_id = p.id))
                )
            GROUP BY p.city_id
        ) buildings_stats ON ((buildings_stats.city_id = c.id))
        LEFT JOIN (
            SELECT blocks.city_id,
                max(blocks.updated_at) AS updated_at
            FROM blocks
            GROUP BY blocks.city_id
        ) blocks_stats ON ((blocks_stats.city_id = c.id))
        LEFT JOIN (
            SELECT administrative_units.city_id,
                max(administrative_units.updated_at) AS updated_at
            FROM administrative_units
            GROUP BY administrative_units.city_id
        ) adm_stats ON ((adm_stats.city_id = c.id))
        LEFT JOIN (
            SELECT municipalities.city_id,
                max(municipalities.updated_at) AS updated_at
            FROM municipalities
            GROUP BY municipalities.city_id
        ) mo_stats ON ((mo_stats.city_id = c.id))
    ORDER BY c.id
);
ALTER TABLE cities_statistics OWNER TO postgres;

-- social materialized views

CREATE MATERIALIZED VIEW social_stats.calculated_sex_age_houses AS (
    WITH sgs AS (
        SELECT social_groups.id
        FROM social_groups
        WHERE social_groups.name LIKE '%(%)'::text
            AND social_groups.name NOT LIKE '%(%т)'::text
            AND social_groups.name NOT LIKE '%(%а)'::text
        ORDER BY social_groups.id
    )
    SELECT sh.building_id,
        sh.year,
        sh.scenario,
        sum(sh.men_0)::integer  AS men_0,  sum(sh.men_1)::integer  AS men_1,  sum(sh.men_2)::integer  AS men_2,  sum(sh.men_3)::integer  AS men_3,  sum(sh.men_4)::integer AS men_4,
        sum(sh.men_5)::integer  AS men_5,  sum(sh.men_6)::integer  AS men_6,  sum(sh.men_7)::integer  AS men_7,  sum(sh.men_8)::integer  AS men_8,  sum(sh.men_9)::integer AS men_9,
        sum(sh.men_10)::integer AS men_10, sum(sh.men_11)::integer AS men_11, sum(sh.men_12)::integer AS men_12, sum(sh.men_13)::integer AS men_13, sum(sh.men_14)::integer AS men_14,
        sum(sh.men_15)::integer AS men_15, sum(sh.men_16)::integer AS men_16, sum(sh.men_17)::integer AS men_17, sum(sh.men_18)::integer AS men_18, sum(sh.men_19)::integer AS men_19,
        sum(sh.men_20)::integer AS men_20, sum(sh.men_21)::integer AS men_21, sum(sh.men_22)::integer AS men_22, sum(sh.men_23)::integer AS men_23, sum(sh.men_24)::integer AS men_24,
        sum(sh.men_25)::integer AS men_25, sum(sh.men_26)::integer AS men_26, sum(sh.men_27)::integer AS men_27, sum(sh.men_28)::integer AS men_28, sum(sh.men_29)::integer AS men_29,
        sum(sh.men_30)::integer AS men_30, sum(sh.men_31)::integer AS men_31, sum(sh.men_32)::integer AS men_32, sum(sh.men_33)::integer AS men_33, sum(sh.men_34)::integer AS men_34,
        sum(sh.men_35)::integer AS men_35, sum(sh.men_36)::integer AS men_36, sum(sh.men_37)::integer AS men_37, sum(sh.men_38)::integer AS men_38, sum(sh.men_39)::integer AS men_39,
        sum(sh.men_40)::integer AS men_40, sum(sh.men_41)::integer AS men_41, sum(sh.men_42)::integer AS men_42, sum(sh.men_43)::integer AS men_43, sum(sh.men_44)::integer AS men_44,
        sum(sh.men_45)::integer AS men_45, sum(sh.men_46)::integer AS men_46, sum(sh.men_47)::integer AS men_47, sum(sh.men_48)::integer AS men_48, sum(sh.men_49)::integer AS men_49,
        sum(sh.men_50)::integer AS men_50, sum(sh.men_51)::integer AS men_51, sum(sh.men_52)::integer AS men_52, sum(sh.men_53)::integer AS men_53, sum(sh.men_54)::integer AS men_54,
        sum(sh.men_55)::integer AS men_55, sum(sh.men_56)::integer AS men_56, sum(sh.men_57)::integer AS men_57, sum(sh.men_58)::integer AS men_58, sum(sh.men_59)::integer AS men_59,
        sum(sh.men_60)::integer AS men_60, sum(sh.men_61)::integer AS men_61, sum(sh.men_62)::integer AS men_62, sum(sh.men_63)::integer AS men_63, sum(sh.men_64)::integer AS men_64,
        sum(sh.men_65)::integer AS men_65, sum(sh.men_66)::integer AS men_66, sum(sh.men_67)::integer AS men_67, sum(sh.men_68)::integer AS men_68, sum(sh.men_69)::integer AS men_69,
        sum(sh.men_70)::integer AS men_70, sum(sh.men_71)::integer AS men_71, sum(sh.men_72)::integer AS men_72, sum(sh.men_73)::integer AS men_73, sum(sh.men_74)::integer AS men_74,
        sum(sh.men_75)::integer AS men_75, sum(sh.men_76)::integer AS men_76, sum(sh.men_77)::integer AS men_77, sum(sh.men_78)::integer AS men_78, sum(sh.men_79)::integer AS men_79,
        sum(sh.men_80)::integer AS men_80, sum(sh.men_81)::integer AS men_81, sum(sh.men_82)::integer AS men_82, sum(sh.men_83)::integer AS men_83, sum(sh.men_84)::integer AS men_84,
        sum(sh.men_85)::integer AS men_85, sum(sh.men_86)::integer AS men_86, sum(sh.men_87)::integer AS men_87, sum(sh.men_88)::integer AS men_88, sum(sh.men_89)::integer AS men_89,
        sum(sh.men_90)::integer AS men_90, sum(sh.men_91)::integer AS men_91, sum(sh.men_92)::integer AS men_92, sum(sh.men_93)::integer AS men_93, sum(sh.men_94)::integer AS men_94,
        sum(sh.men_95)::integer AS men_95, sum(sh.men_96)::integer AS men_96, sum(sh.men_97)::integer AS men_97, sum(sh.men_98)::integer AS men_98, sum(sh.men_99)::integer AS men_99,
        sum(sh.men_100)::integer AS men_100,
        sum(sh.women_0)::integer  AS women_0,  sum(sh.women_1)::integer  AS women_1,  sum(sh.women_2)::integer  AS women_2,  sum(sh.women_3)::integer  AS women_3,  sum(sh.women_4)::integer AS women_4,
        sum(sh.women_5)::integer  AS women_5,  sum(sh.women_6)::integer  AS women_6,  sum(sh.women_7)::integer  AS women_7,  sum(sh.women_8)::integer  AS women_8,  sum(sh.women_9)::integer AS women_9,
        sum(sh.women_10)::integer AS women_10, sum(sh.women_11)::integer AS women_11, sum(sh.women_12)::integer AS women_12, sum(sh.women_13)::integer AS women_13, sum(sh.women_14)::integer AS women_14,
        sum(sh.women_15)::integer AS women_15, sum(sh.women_16)::integer AS women_16, sum(sh.women_17)::integer AS women_17, sum(sh.women_18)::integer AS women_18, sum(sh.women_19)::integer AS women_19,
        sum(sh.women_20)::integer AS women_20, sum(sh.women_21)::integer AS women_21, sum(sh.women_22)::integer AS women_22, sum(sh.women_23)::integer AS women_23, sum(sh.women_24)::integer AS women_24,
        sum(sh.women_25)::integer AS women_25, sum(sh.women_26)::integer AS women_26, sum(sh.women_27)::integer AS women_27, sum(sh.women_28)::integer AS women_28, sum(sh.women_29)::integer AS women_29,
        sum(sh.women_30)::integer AS women_30, sum(sh.women_31)::integer AS women_31, sum(sh.women_32)::integer AS women_32, sum(sh.women_33)::integer AS women_33, sum(sh.women_34)::integer AS women_34,
        sum(sh.women_35)::integer AS women_35, sum(sh.women_36)::integer AS women_36, sum(sh.women_37)::integer AS women_37, sum(sh.women_38)::integer AS women_38, sum(sh.women_39)::integer AS women_39,
        sum(sh.women_40)::integer AS women_40, sum(sh.women_41)::integer AS women_41, sum(sh.women_42)::integer AS women_42, sum(sh.women_43)::integer AS women_43, sum(sh.women_44)::integer AS women_44,
        sum(sh.women_45)::integer AS women_45, sum(sh.women_46)::integer AS women_46, sum(sh.women_47)::integer AS women_47, sum(sh.women_48)::integer AS women_48, sum(sh.women_49)::integer AS women_49,
        sum(sh.women_50)::integer AS women_50, sum(sh.women_51)::integer AS women_51, sum(sh.women_52)::integer AS women_52, sum(sh.women_53)::integer AS women_53, sum(sh.women_54)::integer AS women_54,
        sum(sh.women_55)::integer AS women_55, sum(sh.women_56)::integer AS women_56, sum(sh.women_57)::integer AS women_57, sum(sh.women_58)::integer AS women_58, sum(sh.women_59)::integer AS women_59,
        sum(sh.women_60)::integer AS women_60, sum(sh.women_61)::integer AS women_61, sum(sh.women_62)::integer AS women_62, sum(sh.women_63)::integer AS women_63, sum(sh.women_64)::integer AS women_64,
        sum(sh.women_65)::integer AS women_65, sum(sh.women_66)::integer AS women_66, sum(sh.women_67)::integer AS women_67, sum(sh.women_68)::integer AS women_68, sum(sh.women_69)::integer AS women_69,
        sum(sh.women_70)::integer AS women_70, sum(sh.women_71)::integer AS women_71, sum(sh.women_72)::integer AS women_72, sum(sh.women_73)::integer AS women_73, sum(sh.women_74)::integer AS women_74,
        sum(sh.women_75)::integer AS women_75, sum(sh.women_76)::integer AS women_76, sum(sh.women_77)::integer AS women_77, sum(sh.women_78)::integer AS women_78, sum(sh.women_79)::integer AS women_79,
        sum(sh.women_80)::integer AS women_80, sum(sh.women_81)::integer AS women_81, sum(sh.women_82)::integer AS women_82, sum(sh.women_83)::integer AS women_83, sum(sh.women_84)::integer AS women_84,
        sum(sh.women_85)::integer AS women_85, sum(sh.women_86)::integer AS women_86, sum(sh.women_87)::integer AS women_87, sum(sh.women_88)::integer AS women_88, sum(sh.women_89)::integer AS women_89,
        sum(sh.women_90)::integer AS women_90, sum(sh.women_91)::integer AS women_91, sum(sh.women_92)::integer AS women_92, sum(sh.women_93)::integer AS women_93, sum(sh.women_94)::integer AS women_94,
        sum(sh.women_95)::integer AS women_95, sum(sh.women_96)::integer AS women_96, sum(sh.women_97)::integer AS women_97, sum(sh.women_98)::integer AS women_98, sum(sh.women_99)::integer AS women_99,
        sum(sh.women_100)::integer AS women_100
    FROM social_stats.sex_age_social_houses sh
    WHERE sh.social_group_id IN (SELECT sgs.id FROM sgs)
    GROUP BY sh.building_id, sh.year, sh.scenario
    ORDER BY sh.building_id, sh.year, sh.scenario
);
ALTER TABLE social_stats.calculated_sex_age_houses OWNER TO postgres;

CREATE MATERIALIZED VIEW social_stats.calculated_sex_age_buildings AS (
    WITH sgs AS (
        SELECT social_groups.id
        FROM social_groups
        WHERE social_groups.name LIKE '%(%)'::text
            AND social_groups.name NOT LIKE '%(%т)'::text
            AND social_groups.name NOT LIKE '%(%а)'::text
        ORDER BY social_groups.id
    )
    SELECT sh.building_id,
        sh.year,
        sh.scenario,
        sum(sh.men_0)::integer  AS men_0,  sum(sh.men_1)::integer  AS men_1,  sum(sh.men_2)::integer  AS men_2,  sum(sh.men_3)::integer  AS men_3,  sum(sh.men_4)::integer AS men_4,
        sum(sh.men_5)::integer  AS men_5,  sum(sh.men_6)::integer  AS men_6,  sum(sh.men_7)::integer  AS men_7,  sum(sh.men_8)::integer  AS men_8,  sum(sh.men_9)::integer AS men_9,
        sum(sh.men_10)::integer AS men_10, sum(sh.men_11)::integer AS men_11, sum(sh.men_12)::integer AS men_12, sum(sh.men_13)::integer AS men_13, sum(sh.men_14)::integer AS men_14,
        sum(sh.men_15)::integer AS men_15, sum(sh.men_16)::integer AS men_16, sum(sh.men_17)::integer AS men_17, sum(sh.men_18)::integer AS men_18, sum(sh.men_19)::integer AS men_19,
        sum(sh.men_20)::integer AS men_20, sum(sh.men_21)::integer AS men_21, sum(sh.men_22)::integer AS men_22, sum(sh.men_23)::integer AS men_23, sum(sh.men_24)::integer AS men_24,
        sum(sh.men_25)::integer AS men_25, sum(sh.men_26)::integer AS men_26, sum(sh.men_27)::integer AS men_27, sum(sh.men_28)::integer AS men_28, sum(sh.men_29)::integer AS men_29,
        sum(sh.men_30)::integer AS men_30, sum(sh.men_31)::integer AS men_31, sum(sh.men_32)::integer AS men_32, sum(sh.men_33)::integer AS men_33, sum(sh.men_34)::integer AS men_34,
        sum(sh.men_35)::integer AS men_35, sum(sh.men_36)::integer AS men_36, sum(sh.men_37)::integer AS men_37, sum(sh.men_38)::integer AS men_38, sum(sh.men_39)::integer AS men_39,
        sum(sh.men_40)::integer AS men_40, sum(sh.men_41)::integer AS men_41, sum(sh.men_42)::integer AS men_42, sum(sh.men_43)::integer AS men_43, sum(sh.men_44)::integer AS men_44,
        sum(sh.men_45)::integer AS men_45, sum(sh.men_46)::integer AS men_46, sum(sh.men_47)::integer AS men_47, sum(sh.men_48)::integer AS men_48, sum(sh.men_49)::integer AS men_49,
        sum(sh.men_50)::integer AS men_50, sum(sh.men_51)::integer AS men_51, sum(sh.men_52)::integer AS men_52, sum(sh.men_53)::integer AS men_53, sum(sh.men_54)::integer AS men_54,
        sum(sh.men_55)::integer AS men_55, sum(sh.men_56)::integer AS men_56, sum(sh.men_57)::integer AS men_57, sum(sh.men_58)::integer AS men_58, sum(sh.men_59)::integer AS men_59,
        sum(sh.men_60)::integer AS men_60, sum(sh.men_61)::integer AS men_61, sum(sh.men_62)::integer AS men_62, sum(sh.men_63)::integer AS men_63, sum(sh.men_64)::integer AS men_64,
        sum(sh.men_65)::integer AS men_65, sum(sh.men_66)::integer AS men_66, sum(sh.men_67)::integer AS men_67, sum(sh.men_68)::integer AS men_68, sum(sh.men_69)::integer AS men_69,
        sum(sh.men_70)::integer AS men_70, sum(sh.men_71)::integer AS men_71, sum(sh.men_72)::integer AS men_72, sum(sh.men_73)::integer AS men_73, sum(sh.men_74)::integer AS men_74,
        sum(sh.men_75)::integer AS men_75, sum(sh.men_76)::integer AS men_76, sum(sh.men_77)::integer AS men_77, sum(sh.men_78)::integer AS men_78, sum(sh.men_79)::integer AS men_79,
        sum(sh.men_80)::integer AS men_80, sum(sh.men_81)::integer AS men_81, sum(sh.men_82)::integer AS men_82, sum(sh.men_83)::integer AS men_83, sum(sh.men_84)::integer AS men_84,
        sum(sh.men_85)::integer AS men_85, sum(sh.men_86)::integer AS men_86, sum(sh.men_87)::integer AS men_87, sum(sh.men_88)::integer AS men_88, sum(sh.men_89)::integer AS men_89,
        sum(sh.men_90)::integer AS men_90, sum(sh.men_91)::integer AS men_91, sum(sh.men_92)::integer AS men_92, sum(sh.men_93)::integer AS men_93, sum(sh.men_94)::integer AS men_94,
        sum(sh.men_95)::integer AS men_95, sum(sh.men_96)::integer AS men_96, sum(sh.men_97)::integer AS men_97, sum(sh.men_98)::integer AS men_98, sum(sh.men_99)::integer AS men_99,
        sum(sh.men_100)::integer AS men_100,
        sum(sh.women_0)::integer  AS women_0,  sum(sh.women_1)::integer  AS women_1,  sum(sh.women_2)::integer  AS women_2,  sum(sh.women_3)::integer  AS women_3,  sum(sh.women_4)::integer AS women_4,
        sum(sh.women_5)::integer  AS women_5,  sum(sh.women_6)::integer  AS women_6,  sum(sh.women_7)::integer  AS women_7,  sum(sh.women_8)::integer  AS women_8,  sum(sh.women_9)::integer AS women_9,
        sum(sh.women_10)::integer AS women_10, sum(sh.women_11)::integer AS women_11, sum(sh.women_12)::integer AS women_12, sum(sh.women_13)::integer AS women_13, sum(sh.women_14)::integer AS women_14,
        sum(sh.women_15)::integer AS women_15, sum(sh.women_16)::integer AS women_16, sum(sh.women_17)::integer AS women_17, sum(sh.women_18)::integer AS women_18, sum(sh.women_19)::integer AS women_19,
        sum(sh.women_20)::integer AS women_20, sum(sh.women_21)::integer AS women_21, sum(sh.women_22)::integer AS women_22, sum(sh.women_23)::integer AS women_23, sum(sh.women_24)::integer AS women_24,
        sum(sh.women_25)::integer AS women_25, sum(sh.women_26)::integer AS women_26, sum(sh.women_27)::integer AS women_27, sum(sh.women_28)::integer AS women_28, sum(sh.women_29)::integer AS women_29,
        sum(sh.women_30)::integer AS women_30, sum(sh.women_31)::integer AS women_31, sum(sh.women_32)::integer AS women_32, sum(sh.women_33)::integer AS women_33, sum(sh.women_34)::integer AS women_34,
        sum(sh.women_35)::integer AS women_35, sum(sh.women_36)::integer AS women_36, sum(sh.women_37)::integer AS women_37, sum(sh.women_38)::integer AS women_38, sum(sh.women_39)::integer AS women_39,
        sum(sh.women_40)::integer AS women_40, sum(sh.women_41)::integer AS women_41, sum(sh.women_42)::integer AS women_42, sum(sh.women_43)::integer AS women_43, sum(sh.women_44)::integer AS women_44,
        sum(sh.women_45)::integer AS women_45, sum(sh.women_46)::integer AS women_46, sum(sh.women_47)::integer AS women_47, sum(sh.women_48)::integer AS women_48, sum(sh.women_49)::integer AS women_49,
        sum(sh.women_50)::integer AS women_50, sum(sh.women_51)::integer AS women_51, sum(sh.women_52)::integer AS women_52, sum(sh.women_53)::integer AS women_53, sum(sh.women_54)::integer AS women_54,
        sum(sh.women_55)::integer AS women_55, sum(sh.women_56)::integer AS women_56, sum(sh.women_57)::integer AS women_57, sum(sh.women_58)::integer AS women_58, sum(sh.women_59)::integer AS women_59,
        sum(sh.women_60)::integer AS women_60, sum(sh.women_61)::integer AS women_61, sum(sh.women_62)::integer AS women_62, sum(sh.women_63)::integer AS women_63, sum(sh.women_64)::integer AS women_64,
        sum(sh.women_65)::integer AS women_65, sum(sh.women_66)::integer AS women_66, sum(sh.women_67)::integer AS women_67, sum(sh.women_68)::integer AS women_68, sum(sh.women_69)::integer AS women_69,
        sum(sh.women_70)::integer AS women_70, sum(sh.women_71)::integer AS women_71, sum(sh.women_72)::integer AS women_72, sum(sh.women_73)::integer AS women_73, sum(sh.women_74)::integer AS women_74,
        sum(sh.women_75)::integer AS women_75, sum(sh.women_76)::integer AS women_76, sum(sh.women_77)::integer AS women_77, sum(sh.women_78)::integer AS women_78, sum(sh.women_79)::integer AS women_79,
        sum(sh.women_80)::integer AS women_80, sum(sh.women_81)::integer AS women_81, sum(sh.women_82)::integer AS women_82, sum(sh.women_83)::integer AS women_83, sum(sh.women_84)::integer AS women_84,
        sum(sh.women_85)::integer AS women_85, sum(sh.women_86)::integer AS women_86, sum(sh.women_87)::integer AS women_87, sum(sh.women_88)::integer AS women_88, sum(sh.women_89)::integer AS women_89,
        sum(sh.women_90)::integer AS women_90, sum(sh.women_91)::integer AS women_91, sum(sh.women_92)::integer AS women_92, sum(sh.women_93)::integer AS women_93, sum(sh.women_94)::integer AS women_94,
        sum(sh.women_95)::integer AS women_95, sum(sh.women_96)::integer AS women_96, sum(sh.women_97)::integer AS women_97, sum(sh.women_98)::integer AS women_98, sum(sh.women_99)::integer AS women_99,
        sum(sh.women_100)::integer AS women_100
    FROM social_stats.sex_age_social_houses sh
    WHERE sh.social_group_id IN (SELECT sgs.id FROM sgs)
    GROUP BY sh.building_id, sh.year, sh.scenario
    ORDER BY sh.building_id, sh.year, sh.scenario
);
ALTER TABLE social_stats.calculated_sex_age_buildings OWNER TO postgres;

CREATE MATERIALIZED VIEW social_stats.calculated_social_people_buildings AS (
    SELECT sh.building_id,
    sh.year,
    sh.scenario,
    sh.social_group_id,
    sum(
        sh.men_0::integer  + sh.men_1  + sh.men_2  + sh.men_3  + sh.men_4  + sh.men_5  + sh.men_6  + sh.men_7  + sh.men_8  + sh.men_9  +
        sh.men_10 + sh.men_11 + sh.men_12 + sh.men_13 + sh.men_14 + sh.men_15 + sh.men_16 + sh.men_17 + sh.men_18 + sh.men_19 +
        sh.men_20 + sh.men_21 + sh.men_22 + sh.men_23 + sh.men_24 + sh.men_25 + sh.men_26 + sh.men_27 + sh.men_28 + sh.men_29 +
        sh.men_30 + sh.men_31 + sh.men_32 + sh.men_33 + sh.men_34 + sh.men_35 + sh.men_36 + sh.men_37 + sh.men_38 + sh.men_39 +
        sh.men_40 + sh.men_41 + sh.men_42 + sh.men_43 + sh.men_44 + sh.men_45 + sh.men_46 + sh.men_47 + sh.men_48 + sh.men_49 +
        sh.men_50 + sh.men_51 + sh.men_52 + sh.men_53 + sh.men_54 + sh.men_55 + sh.men_56 + sh.men_57 + sh.men_58 + sh.men_59 +
        sh.men_60 + sh.men_61 + sh.men_62 + sh.men_63 + sh.men_64 + sh.men_65 + sh.men_66 + sh.men_67 + sh.men_68 + sh.men_69 +
        sh.men_70 + sh.men_71 + sh.men_72 + sh.men_73 + sh.men_74 + sh.men_75 + sh.men_76 + sh.men_77 + sh.men_78 + sh.men_79 +
        sh.men_80 + sh.men_81 + sh.men_82 + sh.men_83 + sh.men_84 + sh.men_85 + sh.men_86 + sh.men_87 + sh.men_88 + sh.men_89 +
        sh.men_90 + sh.men_91 + sh.men_92 + sh.men_93 + sh.men_94 + sh.men_95 + sh.men_96 + sh.men_97 + sh.men_98 + sh.men_99 +
        sh.men_100 +
        sh.women_0 +  sh.women_1  + sh.women_2  + sh.women_3  + sh.women_4  + sh.women_5  + sh.women_6  + sh.women_7  + sh.women_8  + sh.women_9  +
        sh.women_10 + sh.women_11 + sh.women_12 + sh.women_13 + sh.women_14 + sh.women_15 + sh.women_16 + sh.women_17 + sh.women_18 + sh.women_19 +
        sh.women_20 + sh.women_21 + sh.women_22 + sh.women_23 + sh.women_24 + sh.women_25 + sh.women_26 + sh.women_27 + sh.women_28 + sh.women_29 +
        sh.women_30 + sh.women_31 + sh.women_32 + sh.women_33 + sh.women_34 + sh.women_35 + sh.women_36 + sh.women_37 + sh.women_38 + sh.women_39 +
        sh.women_40 + sh.women_41 + sh.women_42 + sh.women_43 + sh.women_44 + sh.women_45 + sh.women_46 + sh.women_47 + sh.women_48 + sh.women_49 +
        sh.women_50 + sh.women_51 + sh.women_52 + sh.women_53 + sh.women_54 + sh.women_55 + sh.women_56 + sh.women_57 + sh.women_58 + sh.women_59 +
        sh.women_60 + sh.women_61 + sh.women_62 + sh.women_63 + sh.women_64 + sh.women_65 + sh.women_66 + sh.women_67 + sh.women_68 + sh.women_69 +
        sh.women_70 + sh.women_71 + sh.women_72 + sh.women_73 + sh.women_74 + sh.women_75 + sh.women_76 + sh.women_77 + sh.women_78 + sh.women_79 +
        sh.women_80 + sh.women_81 + sh.women_82 + sh.women_83 + sh.women_84 + sh.women_85 + sh.women_86 + sh.women_87 + sh.women_88 + sh.women_89 +
        sh.women_90 + sh.women_91 + sh.women_92 + sh.women_93 + sh.women_94 + sh.women_95 + sh.women_96 + sh.women_97 + sh.women_98 + sh.women_99 +
        sh.women_100
    )::integer AS people
    FROM social_stats.sex_age_social_houses sh
    GROUP BY sh.building_id, sh.year, sh.scenario, sh.social_group_id
    ORDER BY sh.building_id, sh.year, sh.scenario, sh.social_group_id
);
ALTER TABLE social_stats.calculated_social_people_buildings OWNER TO postgres;

CREATE MATERIALIZED VIEW social_stats.calculated_people_buildings AS (
    SELECT sh.building_id,
    sh.year,
    sh.scenario,
    sum(
        sh.men_0  + sh.men_1  + sh.men_2  + sh.men_3  + sh.men_4  + sh.men_5  + sh.men_6  + sh.men_7  + sh.men_8  + sh.men_9  +
        sh.men_10 + sh.men_11 + sh.men_12 + sh.men_13 + sh.men_14 + sh.men_15 + sh.men_16 + sh.men_17 + sh.men_18 + sh.men_19 +
        sh.men_20 + sh.men_21 + sh.men_22 + sh.men_23 + sh.men_24 + sh.men_25 + sh.men_26 + sh.men_27 + sh.men_28 + sh.men_29 +
        sh.men_30 + sh.men_31 + sh.men_32 + sh.men_33 + sh.men_34 + sh.men_35 + sh.men_36 + sh.men_37 + sh.men_38 + sh.men_39 +
        sh.men_40 + sh.men_41 + sh.men_42 + sh.men_43 + sh.men_44 + sh.men_45 + sh.men_46 + sh.men_47 + sh.men_48 + sh.men_49 +
        sh.men_50 + sh.men_51 + sh.men_52 + sh.men_53 + sh.men_54 + sh.men_55 + sh.men_56 + sh.men_57 + sh.men_58 + sh.men_59 +
        sh.men_60 + sh.men_61 + sh.men_62 + sh.men_63 + sh.men_64 + sh.men_65 + sh.men_66 + sh.men_67 + sh.men_68 + sh.men_69 +
        sh.men_70 + sh.men_71 + sh.men_72 + sh.men_73 + sh.men_74 + sh.men_75 + sh.men_76 + sh.men_77 + sh.men_78 + sh.men_79 +
        sh.men_80 + sh.men_81 + sh.men_82 + sh.men_83 + sh.men_84 + sh.men_85 + sh.men_86 + sh.men_87 + sh.men_88 + sh.men_89 +
        sh.men_90 + sh.men_91 + sh.men_92 + sh.men_93 + sh.men_94 + sh.men_95 + sh.men_96 + sh.men_97 + sh.men_98 + sh.men_99 +
        sh.men_100 +
        sh.women_0 +  sh.women_1  + sh.women_2  + sh.women_3  + sh.women_4  + sh.women_5  + sh.women_6  + sh.women_7  + sh.women_8  + sh.women_9  +
        sh.women_10 + sh.women_11 + sh.women_12 + sh.women_13 + sh.women_14 + sh.women_15 + sh.women_16 + sh.women_17 + sh.women_18 + sh.women_19 +
        sh.women_20 + sh.women_21 + sh.women_22 + sh.women_23 + sh.women_24 + sh.women_25 + sh.women_26 + sh.women_27 + sh.women_28 + sh.women_29 +
        sh.women_30 + sh.women_31 + sh.women_32 + sh.women_33 + sh.women_34 + sh.women_35 + sh.women_36 + sh.women_37 + sh.women_38 + sh.women_39 +
        sh.women_40 + sh.women_41 + sh.women_42 + sh.women_43 + sh.women_44 + sh.women_45 + sh.women_46 + sh.women_47 + sh.women_48 + sh.women_49 +
        sh.women_50 + sh.women_51 + sh.women_52 + sh.women_53 + sh.women_54 + sh.women_55 + sh.women_56 + sh.women_57 + sh.women_58 + sh.women_59 +
        sh.women_60 + sh.women_61 + sh.women_62 + sh.women_63 + sh.women_64 + sh.women_65 + sh.women_66 + sh.women_67 + sh.women_68 + sh.women_69 +
        sh.women_70 + sh.women_71 + sh.women_72 + sh.women_73 + sh.women_74 + sh.women_75 + sh.women_76 + sh.women_77 + sh.women_78 + sh.women_79 +
        sh.women_80 + sh.women_81 + sh.women_82 + sh.women_83 + sh.women_84 + sh.women_85 + sh.women_86 + sh.women_87 + sh.women_88 + sh.women_89 +
        sh.women_90 + sh.women_91 + sh.women_92 + sh.women_93 + sh.women_94 + sh.women_95 + sh.women_96 + sh.women_97 + sh.women_98 + sh.women_99 +
        sh.women_100
    )::integer AS people
    FROM social_stats.calculated_sex_age_buildings sh
    GROUP BY sh.building_id, sh.year, sh.scenario
    ORDER BY sh.building_id, sh.year, sh.scenario
);
ALTER TABLE social_stats.calculated_people_buildings OWNER TO postgres;

CREATE MATERIALIZED VIEW social_stats.calculated_people_houses AS (
    SELECT sh.building_id AS house_id,
    sh.year,
    sh.scenario,
    sum(
        sh.men_0  + sh.men_1  + sh.men_2  + sh.men_3  + sh.men_4  + sh.men_5  + sh.men_6  + sh.men_7  + sh.men_8  + sh.men_9  +
        sh.men_10 + sh.men_11 + sh.men_12 + sh.men_13 + sh.men_14 + sh.men_15 + sh.men_16 + sh.men_17 + sh.men_18 + sh.men_19 +
        sh.men_20 + sh.men_21 + sh.men_22 + sh.men_23 + sh.men_24 + sh.men_25 + sh.men_26 + sh.men_27 + sh.men_28 + sh.men_29 +
        sh.men_30 + sh.men_31 + sh.men_32 + sh.men_33 + sh.men_34 + sh.men_35 + sh.men_36 + sh.men_37 + sh.men_38 + sh.men_39 +
        sh.men_40 + sh.men_41 + sh.men_42 + sh.men_43 + sh.men_44 + sh.men_45 + sh.men_46 + sh.men_47 + sh.men_48 + sh.men_49 +
        sh.men_50 + sh.men_51 + sh.men_52 + sh.men_53 + sh.men_54 + sh.men_55 + sh.men_56 + sh.men_57 + sh.men_58 + sh.men_59 +
        sh.men_60 + sh.men_61 + sh.men_62 + sh.men_63 + sh.men_64 + sh.men_65 + sh.men_66 + sh.men_67 + sh.men_68 + sh.men_69 +
        sh.men_70 + sh.men_71 + sh.men_72 + sh.men_73 + sh.men_74 + sh.men_75 + sh.men_76 + sh.men_77 + sh.men_78 + sh.men_79 +
        sh.men_80 + sh.men_81 + sh.men_82 + sh.men_83 + sh.men_84 + sh.men_85 + sh.men_86 + sh.men_87 + sh.men_88 + sh.men_89 +
        sh.men_90 + sh.men_91 + sh.men_92 + sh.men_93 + sh.men_94 + sh.men_95 + sh.men_96 + sh.men_97 + sh.men_98 + sh.men_99 +
        sh.men_100 +
        sh.women_0 +  sh.women_1  + sh.women_2  + sh.women_3  + sh.women_4  + sh.women_5  + sh.women_6  + sh.women_7  + sh.women_8  + sh.women_9  +
        sh.women_10 + sh.women_11 + sh.women_12 + sh.women_13 + sh.women_14 + sh.women_15 + sh.women_16 + sh.women_17 + sh.women_18 + sh.women_19 +
        sh.women_20 + sh.women_21 + sh.women_22 + sh.women_23 + sh.women_24 + sh.women_25 + sh.women_26 + sh.women_27 + sh.women_28 + sh.women_29 +
        sh.women_30 + sh.women_31 + sh.women_32 + sh.women_33 + sh.women_34 + sh.women_35 + sh.women_36 + sh.women_37 + sh.women_38 + sh.women_39 +
        sh.women_40 + sh.women_41 + sh.women_42 + sh.women_43 + sh.women_44 + sh.women_45 + sh.women_46 + sh.women_47 + sh.women_48 + sh.women_49 +
        sh.women_50 + sh.women_51 + sh.women_52 + sh.women_53 + sh.women_54 + sh.women_55 + sh.women_56 + sh.women_57 + sh.women_58 + sh.women_59 +
        sh.women_60 + sh.women_61 + sh.women_62 + sh.women_63 + sh.women_64 + sh.women_65 + sh.women_66 + sh.women_67 + sh.women_68 + sh.women_69 +
        sh.women_70 + sh.women_71 + sh.women_72 + sh.women_73 + sh.women_74 + sh.women_75 + sh.women_76 + sh.women_77 + sh.women_78 + sh.women_79 +
        sh.women_80 + sh.women_81 + sh.women_82 + sh.women_83 + sh.women_84 + sh.women_85 + sh.women_86 + sh.women_87 + sh.women_88 + sh.women_89 +
        sh.women_90 + sh.women_91 + sh.women_92 + sh.women_93 + sh.women_94 + sh.women_95 + sh.women_96 + sh.women_97 + sh.women_98 + sh.women_99 +
        sh.women_100
    )::integer AS people
    FROM social_stats.calculated_sex_age_buildings sh
    GROUP BY sh.building_id, sh.year, sh.scenario
    ORDER BY sh.building_id, sh.year, sh.scenario
);
ALTER TABLE social_stats.calculated_people_houses OWNER TO postgres;

CREATE MATERIALIZED VIEW social_stats.calculated_sex_age_social_administrative_units AS (
    SELECT sh.year,
        sh.scenario,
        p.administrative_unit_id,
        sh.social_group_id,
        sum(sh.men_0)::integer  AS men_0,  sum(sh.men_1)::integer  AS men_1,  sum(sh.men_2)::integer  AS men_2,  sum(sh.men_3)::integer  AS men_3,  sum(sh.men_4)::integer  AS men_4,
        sum(sh.men_5)::integer  AS men_5,  sum(sh.men_6)::integer  AS men_6,  sum(sh.men_7)::integer  AS men_7,  sum(sh.men_8)::integer  AS men_8,  sum(sh.men_9)::integer  AS men_9,
        sum(sh.men_10)::integer AS men_10, sum(sh.men_11)::integer AS men_11, sum(sh.men_12)::integer AS men_12, sum(sh.men_13)::integer AS men_13, sum(sh.men_14)::integer AS men_14,
        sum(sh.men_15)::integer AS men_15, sum(sh.men_16)::integer AS men_16, sum(sh.men_17)::integer AS men_17, sum(sh.men_18)::integer AS men_18, sum(sh.men_19)::integer AS men_19,
        sum(sh.men_20)::integer AS men_20, sum(sh.men_21)::integer AS men_21, sum(sh.men_22)::integer AS men_22, sum(sh.men_23)::integer AS men_23, sum(sh.men_24)::integer AS men_24,
        sum(sh.men_25)::integer AS men_25, sum(sh.men_26)::integer AS men_26, sum(sh.men_27)::integer AS men_27, sum(sh.men_28)::integer AS men_28, sum(sh.men_29)::integer AS men_29,
        sum(sh.men_30)::integer AS men_30, sum(sh.men_31)::integer AS men_31, sum(sh.men_32)::integer AS men_32, sum(sh.men_33)::integer AS men_33, sum(sh.men_34)::integer AS men_34,
        sum(sh.men_35)::integer AS men_35, sum(sh.men_36)::integer AS men_36, sum(sh.men_37)::integer AS men_37, sum(sh.men_38)::integer AS men_38, sum(sh.men_39)::integer AS men_39,
        sum(sh.men_40)::integer AS men_40, sum(sh.men_41)::integer AS men_41, sum(sh.men_42)::integer AS men_42, sum(sh.men_43)::integer AS men_43, sum(sh.men_44)::integer AS men_44,
        sum(sh.men_45)::integer AS men_45, sum(sh.men_46)::integer AS men_46, sum(sh.men_47)::integer AS men_47, sum(sh.men_48)::integer AS men_48, sum(sh.men_49)::integer AS men_49,
        sum(sh.men_50)::integer AS men_50, sum(sh.men_51)::integer AS men_51, sum(sh.men_52)::integer AS men_52, sum(sh.men_53)::integer AS men_53, sum(sh.men_54)::integer AS men_54,
        sum(sh.men_55)::integer AS men_55, sum(sh.men_56)::integer AS men_56, sum(sh.men_57)::integer AS men_57, sum(sh.men_58)::integer AS men_58, sum(sh.men_59)::integer AS men_59,
        sum(sh.men_60)::integer AS men_60, sum(sh.men_61)::integer AS men_61, sum(sh.men_62)::integer AS men_62, sum(sh.men_63)::integer AS men_63, sum(sh.men_64)::integer AS men_64,
        sum(sh.men_65)::integer AS men_65, sum(sh.men_66)::integer AS men_66, sum(sh.men_67)::integer AS men_67, sum(sh.men_68)::integer AS men_68, sum(sh.men_69)::integer AS men_69,
        sum(sh.men_70)::integer AS men_70, sum(sh.men_71)::integer AS men_71, sum(sh.men_72)::integer AS men_72, sum(sh.men_73)::integer AS men_73, sum(sh.men_74)::integer AS men_74,
        sum(sh.men_75)::integer AS men_75, sum(sh.men_76)::integer AS men_76, sum(sh.men_77)::integer AS men_77, sum(sh.men_78)::integer AS men_78, sum(sh.men_79)::integer AS men_79,
        sum(sh.men_80)::integer AS men_80, sum(sh.men_81)::integer AS men_81, sum(sh.men_82)::integer AS men_82, sum(sh.men_83)::integer AS men_83, sum(sh.men_84)::integer AS men_84,
        sum(sh.men_85)::integer AS men_85, sum(sh.men_86)::integer AS men_86, sum(sh.men_87)::integer AS men_87, sum(sh.men_88)::integer AS men_88, sum(sh.men_89)::integer AS men_89,
        sum(sh.men_90)::integer AS men_90, sum(sh.men_91)::integer AS men_91, sum(sh.men_92)::integer AS men_92, sum(sh.men_93)::integer AS men_93, sum(sh.men_94)::integer AS men_94,
        sum(sh.men_95)::integer AS men_95, sum(sh.men_96)::integer AS men_96, sum(sh.men_97)::integer AS men_97, sum(sh.men_98)::integer AS men_98, sum(sh.men_99)::integer AS men_99,
        sum(sh.men_100)::integer AS men_100,
        sum(sh.women_0)::integer  AS women_0,  sum(sh.women_1)::integer  AS women_1,  sum(sh.women_2)::integer  AS women_2,  sum(sh.women_3)::integer  AS women_3,  sum(sh.women_4)::integer  AS women_4,
        sum(sh.women_5)::integer  AS women_5,  sum(sh.women_6)::integer  AS women_6,  sum(sh.women_7)::integer  AS women_7,  sum(sh.women_8)::integer  AS women_8,  sum(sh.women_9)::integer  AS women_9,
        sum(sh.women_10)::integer AS women_10, sum(sh.women_11)::integer AS women_11, sum(sh.women_12)::integer AS women_12, sum(sh.women_13)::integer AS women_13, sum(sh.women_14)::integer AS women_14,
        sum(sh.women_15)::integer AS women_15, sum(sh.women_16)::integer AS women_16, sum(sh.women_17)::integer AS women_17, sum(sh.women_18)::integer AS women_18, sum(sh.women_19)::integer AS women_19,
        sum(sh.women_20)::integer AS women_20, sum(sh.women_21)::integer AS women_21, sum(sh.women_22)::integer AS women_22, sum(sh.women_23)::integer AS women_23, sum(sh.women_24)::integer AS women_24,
        sum(sh.women_25)::integer AS women_25, sum(sh.women_26)::integer AS women_26, sum(sh.women_27)::integer AS women_27, sum(sh.women_28)::integer AS women_28, sum(sh.women_29)::integer AS women_29,
        sum(sh.women_30)::integer AS women_30, sum(sh.women_31)::integer AS women_31, sum(sh.women_32)::integer AS women_32, sum(sh.women_33)::integer AS women_33, sum(sh.women_34)::integer AS women_34,
        sum(sh.women_35)::integer AS women_35, sum(sh.women_36)::integer AS women_36, sum(sh.women_37)::integer AS women_37, sum(sh.women_38)::integer AS women_38, sum(sh.women_39)::integer AS women_39,
        sum(sh.women_40)::integer AS women_40, sum(sh.women_41)::integer AS women_41, sum(sh.women_42)::integer AS women_42, sum(sh.women_43)::integer AS women_43, sum(sh.women_44)::integer AS women_44,
        sum(sh.women_45)::integer AS women_45, sum(sh.women_46)::integer AS women_46, sum(sh.women_47)::integer AS women_47, sum(sh.women_48)::integer AS women_48, sum(sh.women_49)::integer AS women_49,
        sum(sh.women_50)::integer AS women_50, sum(sh.women_51)::integer AS women_51, sum(sh.women_52)::integer AS women_52, sum(sh.women_53)::integer AS women_53, sum(sh.women_54)::integer AS women_54,
        sum(sh.women_55)::integer AS women_55, sum(sh.women_56)::integer AS women_56, sum(sh.women_57)::integer AS women_57, sum(sh.women_58)::integer AS women_58, sum(sh.women_59)::integer AS women_59,
        sum(sh.women_60)::integer AS women_60, sum(sh.women_61)::integer AS women_61, sum(sh.women_62)::integer AS women_62, sum(sh.women_63)::integer AS women_63, sum(sh.women_64)::integer AS women_64,
        sum(sh.women_65)::integer AS women_65, sum(sh.women_66)::integer AS women_66, sum(sh.women_67)::integer AS women_67, sum(sh.women_68)::integer AS women_68, sum(sh.women_69)::integer AS women_69,
        sum(sh.women_70)::integer AS women_70, sum(sh.women_71)::integer AS women_71, sum(sh.women_72)::integer AS women_72, sum(sh.women_73)::integer AS women_73, sum(sh.women_74)::integer AS women_74,
        sum(sh.women_75)::integer AS women_75, sum(sh.women_76)::integer AS women_76, sum(sh.women_77)::integer AS women_77, sum(sh.women_78)::integer AS women_78, sum(sh.women_79)::integer AS women_79,
        sum(sh.women_80)::integer AS women_80, sum(sh.women_81)::integer AS women_81, sum(sh.women_82)::integer AS women_82, sum(sh.women_83)::integer AS women_83, sum(sh.women_84)::integer AS women_84,
        sum(sh.women_85)::integer AS women_85, sum(sh.women_86)::integer AS women_86, sum(sh.women_87)::integer AS women_87, sum(sh.women_88)::integer AS women_88, sum(sh.women_89)::integer AS women_89,
        sum(sh.women_90)::integer AS women_90, sum(sh.women_91)::integer AS women_91, sum(sh.women_92)::integer AS women_92, sum(sh.women_93)::integer AS women_93, sum(sh.women_94)::integer AS women_94,
        sum(sh.women_95)::integer AS women_95, sum(sh.women_96)::integer AS women_96, sum(sh.women_97)::integer AS women_97, sum(sh.women_98)::integer AS women_98, sum(sh.women_99)::integer AS women_99,
        sum(sh.women_100)::integer AS women_100
    FROM social_stats.sex_age_social_houses sh
        JOIN buildings b ON sh.building_id = b.id
        JOIN physical_objects p ON b.physical_object_id = p.id
    GROUP BY sh.year, sh.scenario, p.administrative_unit_id, sh.social_group_id
    ORDER BY sh.year, sh.scenario, p.administrative_unit_id, sh.social_group_id
);
ALTER TABLE social_stats.calculated_sex_age_social_administrative_units OWNER TO postgres;

CREATE MATERIALIZED VIEW social_stats.calculated_sex_age_social_municipalities AS (
    SELECT sh.year,
        sh.scenario,
        p.municipality_id,
        sh.social_group_id,
        sum(sh.men_0)::integer  AS men_0,  sum(sh.men_1)::integer  AS men_1,  sum(sh.men_2)::integer  AS men_2,  sum(sh.men_3)::integer  AS men_3,  sum(sh.men_4)::integer  AS men_4,
        sum(sh.men_5)::integer  AS men_5,  sum(sh.men_6)::integer  AS men_6,  sum(sh.men_7)::integer  AS men_7,  sum(sh.men_8)::integer  AS men_8,  sum(sh.men_9)::integer  AS men_9,
        sum(sh.men_10)::integer AS men_10, sum(sh.men_11)::integer AS men_11, sum(sh.men_12)::integer AS men_12, sum(sh.men_13)::integer AS men_13, sum(sh.men_14)::integer AS men_14,
        sum(sh.men_15)::integer AS men_15, sum(sh.men_16)::integer AS men_16, sum(sh.men_17)::integer AS men_17, sum(sh.men_18)::integer AS men_18, sum(sh.men_19)::integer AS men_19,
        sum(sh.men_20)::integer AS men_20, sum(sh.men_21)::integer AS men_21, sum(sh.men_22)::integer AS men_22, sum(sh.men_23)::integer AS men_23, sum(sh.men_24)::integer AS men_24,
        sum(sh.men_25)::integer AS men_25, sum(sh.men_26)::integer AS men_26, sum(sh.men_27)::integer AS men_27, sum(sh.men_28)::integer AS men_28, sum(sh.men_29)::integer AS men_29,
        sum(sh.men_30)::integer AS men_30, sum(sh.men_31)::integer AS men_31, sum(sh.men_32)::integer AS men_32, sum(sh.men_33)::integer AS men_33, sum(sh.men_34)::integer AS men_34,
        sum(sh.men_35)::integer AS men_35, sum(sh.men_36)::integer AS men_36, sum(sh.men_37)::integer AS men_37, sum(sh.men_38)::integer AS men_38, sum(sh.men_39)::integer AS men_39,
        sum(sh.men_40)::integer AS men_40, sum(sh.men_41)::integer AS men_41, sum(sh.men_42)::integer AS men_42, sum(sh.men_43)::integer AS men_43, sum(sh.men_44)::integer AS men_44,
        sum(sh.men_45)::integer AS men_45, sum(sh.men_46)::integer AS men_46, sum(sh.men_47)::integer AS men_47, sum(sh.men_48)::integer AS men_48, sum(sh.men_49)::integer AS men_49,
        sum(sh.men_50)::integer AS men_50, sum(sh.men_51)::integer AS men_51, sum(sh.men_52)::integer AS men_52, sum(sh.men_53)::integer AS men_53, sum(sh.men_54)::integer AS men_54,
        sum(sh.men_55)::integer AS men_55, sum(sh.men_56)::integer AS men_56, sum(sh.men_57)::integer AS men_57, sum(sh.men_58)::integer AS men_58, sum(sh.men_59)::integer AS men_59,
        sum(sh.men_60)::integer AS men_60, sum(sh.men_61)::integer AS men_61, sum(sh.men_62)::integer AS men_62, sum(sh.men_63)::integer AS men_63, sum(sh.men_64)::integer AS men_64,
        sum(sh.men_65)::integer AS men_65, sum(sh.men_66)::integer AS men_66, sum(sh.men_67)::integer AS men_67, sum(sh.men_68)::integer AS men_68, sum(sh.men_69)::integer AS men_69,
        sum(sh.men_70)::integer AS men_70, sum(sh.men_71)::integer AS men_71, sum(sh.men_72)::integer AS men_72, sum(sh.men_73)::integer AS men_73, sum(sh.men_74)::integer AS men_74,
        sum(sh.men_75)::integer AS men_75, sum(sh.men_76)::integer AS men_76, sum(sh.men_77)::integer AS men_77, sum(sh.men_78)::integer AS men_78, sum(sh.men_79)::integer AS men_79,
        sum(sh.men_80)::integer AS men_80, sum(sh.men_81)::integer AS men_81, sum(sh.men_82)::integer AS men_82, sum(sh.men_83)::integer AS men_83, sum(sh.men_84)::integer AS men_84,
        sum(sh.men_85)::integer AS men_85, sum(sh.men_86)::integer AS men_86, sum(sh.men_87)::integer AS men_87, sum(sh.men_88)::integer AS men_88, sum(sh.men_89)::integer AS men_89,
        sum(sh.men_90)::integer AS men_90, sum(sh.men_91)::integer AS men_91, sum(sh.men_92)::integer AS men_92, sum(sh.men_93)::integer AS men_93, sum(sh.men_94)::integer AS men_94,
        sum(sh.men_95)::integer AS men_95, sum(sh.men_96)::integer AS men_96, sum(sh.men_97)::integer AS men_97, sum(sh.men_98)::integer AS men_98, sum(sh.men_99)::integer AS men_99,
        sum(sh.men_100)::integer AS men_100,
        sum(sh.women_0)::integer  AS women_0,  sum(sh.women_1)::integer  AS women_1,  sum(sh.women_2)::integer  AS women_2,  sum(sh.women_3)::integer  AS women_3,  sum(sh.women_4)::integer  AS women_4,
        sum(sh.women_5)::integer  AS women_5,  sum(sh.women_6)::integer  AS women_6,  sum(sh.women_7)::integer  AS women_7,  sum(sh.women_8)::integer  AS women_8,  sum(sh.women_9)::integer  AS women_9,
        sum(sh.women_10)::integer AS women_10, sum(sh.women_11)::integer AS women_11, sum(sh.women_12)::integer AS women_12, sum(sh.women_13)::integer AS women_13, sum(sh.women_14)::integer AS women_14,
        sum(sh.women_15)::integer AS women_15, sum(sh.women_16)::integer AS women_16, sum(sh.women_17)::integer AS women_17, sum(sh.women_18)::integer AS women_18, sum(sh.women_19)::integer AS women_19,
        sum(sh.women_20)::integer AS women_20, sum(sh.women_21)::integer AS women_21, sum(sh.women_22)::integer AS women_22, sum(sh.women_23)::integer AS women_23, sum(sh.women_24)::integer AS women_24,
        sum(sh.women_25)::integer AS women_25, sum(sh.women_26)::integer AS women_26, sum(sh.women_27)::integer AS women_27, sum(sh.women_28)::integer AS women_28, sum(sh.women_29)::integer AS women_29,
        sum(sh.women_30)::integer AS women_30, sum(sh.women_31)::integer AS women_31, sum(sh.women_32)::integer AS women_32, sum(sh.women_33)::integer AS women_33, sum(sh.women_34)::integer AS women_34,
        sum(sh.women_35)::integer AS women_35, sum(sh.women_36)::integer AS women_36, sum(sh.women_37)::integer AS women_37, sum(sh.women_38)::integer AS women_38, sum(sh.women_39)::integer AS women_39,
        sum(sh.women_40)::integer AS women_40, sum(sh.women_41)::integer AS women_41, sum(sh.women_42)::integer AS women_42, sum(sh.women_43)::integer AS women_43, sum(sh.women_44)::integer AS women_44,
        sum(sh.women_45)::integer AS women_45, sum(sh.women_46)::integer AS women_46, sum(sh.women_47)::integer AS women_47, sum(sh.women_48)::integer AS women_48, sum(sh.women_49)::integer AS women_49,
        sum(sh.women_50)::integer AS women_50, sum(sh.women_51)::integer AS women_51, sum(sh.women_52)::integer AS women_52, sum(sh.women_53)::integer AS women_53, sum(sh.women_54)::integer AS women_54,
        sum(sh.women_55)::integer AS women_55, sum(sh.women_56)::integer AS women_56, sum(sh.women_57)::integer AS women_57, sum(sh.women_58)::integer AS women_58, sum(sh.women_59)::integer AS women_59,
        sum(sh.women_60)::integer AS women_60, sum(sh.women_61)::integer AS women_61, sum(sh.women_62)::integer AS women_62, sum(sh.women_63)::integer AS women_63, sum(sh.women_64)::integer AS women_64,
        sum(sh.women_65)::integer AS women_65, sum(sh.women_66)::integer AS women_66, sum(sh.women_67)::integer AS women_67, sum(sh.women_68)::integer AS women_68, sum(sh.women_69)::integer AS women_69,
        sum(sh.women_70)::integer AS women_70, sum(sh.women_71)::integer AS women_71, sum(sh.women_72)::integer AS women_72, sum(sh.women_73)::integer AS women_73, sum(sh.women_74)::integer AS women_74,
        sum(sh.women_75)::integer AS women_75, sum(sh.women_76)::integer AS women_76, sum(sh.women_77)::integer AS women_77, sum(sh.women_78)::integer AS women_78, sum(sh.women_79)::integer AS women_79,
        sum(sh.women_80)::integer AS women_80, sum(sh.women_81)::integer AS women_81, sum(sh.women_82)::integer AS women_82, sum(sh.women_83)::integer AS women_83, sum(sh.women_84)::integer AS women_84,
        sum(sh.women_85)::integer AS women_85, sum(sh.women_86)::integer AS women_86, sum(sh.women_87)::integer AS women_87, sum(sh.women_88)::integer AS women_88, sum(sh.women_89)::integer AS women_89,
        sum(sh.women_90)::integer AS women_90, sum(sh.women_91)::integer AS women_91, sum(sh.women_92)::integer AS women_92, sum(sh.women_93)::integer AS women_93, sum(sh.women_94)::integer AS women_94,
        sum(sh.women_95)::integer AS women_95, sum(sh.women_96)::integer AS women_96, sum(sh.women_97)::integer AS women_97, sum(sh.women_98)::integer AS women_98, sum(sh.women_99)::integer AS women_99,
        sum(sh.women_100)::integer AS women_100
    FROM social_stats.sex_age_social_houses sh
        JOIN buildings b ON sh.building_id = b.id
        JOIN physical_objects p ON b.physical_object_id = p.id
    GROUP BY sh.year, sh.scenario, p.municipality_id, sh.social_group_id
    ORDER BY sh.year, sh.scenario, p.municipality_id, sh.social_group_id
);
ALTER TABLE social_stats.calculated_sex_age_social_municipalities OWNER TO postgres;

CREATE MATERIALIZED VIEW social_stats.calculated_sex_age_administrative_units AS (
    WITH sgs AS (
        SELECT social_groups.id
        FROM social_groups
        WHERE social_groups.name LIKE '%(%)'::text
            AND social_groups.name NOT LIKE '%(%т)'::text
            AND social_groups.name NOT LIKE '%(%а)'::text
        ORDER BY social_groups.id
    )
    SELECT sh.administrative_unit_id,
        sh.year,
        sh.scenario,
        sum(sh.men_0)::integer  AS men_0,  sum(sh.men_1)::integer  AS men_1,  sum(sh.men_2)::integer  AS men_2,  sum(sh.men_3)::integer  AS men_3,  sum(sh.men_4)::integer  AS men_4,
        sum(sh.men_5)::integer  AS men_5,  sum(sh.men_6)::integer  AS men_6,  sum(sh.men_7)::integer  AS men_7,  sum(sh.men_8)::integer  AS men_8,  sum(sh.men_9)::integer  AS men_9,
        sum(sh.men_10)::integer AS men_10, sum(sh.men_11)::integer AS men_11, sum(sh.men_12)::integer AS men_12, sum(sh.men_13)::integer AS men_13, sum(sh.men_14)::integer AS men_14,
        sum(sh.men_15)::integer AS men_15, sum(sh.men_16)::integer AS men_16, sum(sh.men_17)::integer AS men_17, sum(sh.men_18)::integer AS men_18, sum(sh.men_19)::integer AS men_19,
        sum(sh.men_20)::integer AS men_20, sum(sh.men_21)::integer AS men_21, sum(sh.men_22)::integer AS men_22, sum(sh.men_23)::integer AS men_23, sum(sh.men_24)::integer AS men_24,
        sum(sh.men_25)::integer AS men_25, sum(sh.men_26)::integer AS men_26, sum(sh.men_27)::integer AS men_27, sum(sh.men_28)::integer AS men_28, sum(sh.men_29)::integer AS men_29,
        sum(sh.men_30)::integer AS men_30, sum(sh.men_31)::integer AS men_31, sum(sh.men_32)::integer AS men_32, sum(sh.men_33)::integer AS men_33, sum(sh.men_34)::integer AS men_34,
        sum(sh.men_35)::integer AS men_35, sum(sh.men_36)::integer AS men_36, sum(sh.men_37)::integer AS men_37, sum(sh.men_38)::integer AS men_38, sum(sh.men_39)::integer AS men_39,
        sum(sh.men_40)::integer AS men_40, sum(sh.men_41)::integer AS men_41, sum(sh.men_42)::integer AS men_42, sum(sh.men_43)::integer AS men_43, sum(sh.men_44)::integer AS men_44,
        sum(sh.men_45)::integer AS men_45, sum(sh.men_46)::integer AS men_46, sum(sh.men_47)::integer AS men_47, sum(sh.men_48)::integer AS men_48, sum(sh.men_49)::integer AS men_49,
        sum(sh.men_50)::integer AS men_50, sum(sh.men_51)::integer AS men_51, sum(sh.men_52)::integer AS men_52, sum(sh.men_53)::integer AS men_53, sum(sh.men_54)::integer AS men_54,
        sum(sh.men_55)::integer AS men_55, sum(sh.men_56)::integer AS men_56, sum(sh.men_57)::integer AS men_57, sum(sh.men_58)::integer AS men_58, sum(sh.men_59)::integer AS men_59,
        sum(sh.men_60)::integer AS men_60, sum(sh.men_61)::integer AS men_61, sum(sh.men_62)::integer AS men_62, sum(sh.men_63)::integer AS men_63, sum(sh.men_64)::integer AS men_64,
        sum(sh.men_65)::integer AS men_65, sum(sh.men_66)::integer AS men_66, sum(sh.men_67)::integer AS men_67, sum(sh.men_68)::integer AS men_68, sum(sh.men_69)::integer AS men_69,
        sum(sh.men_70)::integer AS men_70, sum(sh.men_71)::integer AS men_71, sum(sh.men_72)::integer AS men_72, sum(sh.men_73)::integer AS men_73, sum(sh.men_74)::integer AS men_74,
        sum(sh.men_75)::integer AS men_75, sum(sh.men_76)::integer AS men_76, sum(sh.men_77)::integer AS men_77, sum(sh.men_78)::integer AS men_78, sum(sh.men_79)::integer AS men_79,
        sum(sh.men_80)::integer AS men_80, sum(sh.men_81)::integer AS men_81, sum(sh.men_82)::integer AS men_82, sum(sh.men_83)::integer AS men_83, sum(sh.men_84)::integer AS men_84,
        sum(sh.men_85)::integer AS men_85, sum(sh.men_86)::integer AS men_86, sum(sh.men_87)::integer AS men_87, sum(sh.men_88)::integer AS men_88, sum(sh.men_89)::integer AS men_89,
        sum(sh.men_90)::integer AS men_90, sum(sh.men_91)::integer AS men_91, sum(sh.men_92)::integer AS men_92, sum(sh.men_93)::integer AS men_93, sum(sh.men_94)::integer AS men_94,
        sum(sh.men_95)::integer AS men_95, sum(sh.men_96)::integer AS men_96, sum(sh.men_97)::integer AS men_97, sum(sh.men_98)::integer AS men_98, sum(sh.men_99)::integer AS men_99,
        sum(sh.men_100)::integer AS men_100,
        sum(sh.women_0)::integer  AS women_0,  sum(sh.women_1)::integer  AS women_1,  sum(sh.women_2)::integer  AS women_2,  sum(sh.women_3)::integer  AS women_3,  sum(sh.women_4)::integer  AS women_4,
        sum(sh.women_5)::integer  AS women_5,  sum(sh.women_6)::integer  AS women_6,  sum(sh.women_7)::integer  AS women_7,  sum(sh.women_8)::integer  AS women_8,  sum(sh.women_9)::integer  AS women_9,
        sum(sh.women_10)::integer AS women_10, sum(sh.women_11)::integer AS women_11, sum(sh.women_12)::integer AS women_12, sum(sh.women_13)::integer AS women_13, sum(sh.women_14)::integer AS women_14,
        sum(sh.women_15)::integer AS women_15, sum(sh.women_16)::integer AS women_16, sum(sh.women_17)::integer AS women_17, sum(sh.women_18)::integer AS women_18, sum(sh.women_19)::integer AS women_19,
        sum(sh.women_20)::integer AS women_20, sum(sh.women_21)::integer AS women_21, sum(sh.women_22)::integer AS women_22, sum(sh.women_23)::integer AS women_23, sum(sh.women_24)::integer AS women_24,
        sum(sh.women_25)::integer AS women_25, sum(sh.women_26)::integer AS women_26, sum(sh.women_27)::integer AS women_27, sum(sh.women_28)::integer AS women_28, sum(sh.women_29)::integer AS women_29,
        sum(sh.women_30)::integer AS women_30, sum(sh.women_31)::integer AS women_31, sum(sh.women_32)::integer AS women_32, sum(sh.women_33)::integer AS women_33, sum(sh.women_34)::integer AS women_34,
        sum(sh.women_35)::integer AS women_35, sum(sh.women_36)::integer AS women_36, sum(sh.women_37)::integer AS women_37, sum(sh.women_38)::integer AS women_38, sum(sh.women_39)::integer AS women_39,
        sum(sh.women_40)::integer AS women_40, sum(sh.women_41)::integer AS women_41, sum(sh.women_42)::integer AS women_42, sum(sh.women_43)::integer AS women_43, sum(sh.women_44)::integer AS women_44,
        sum(sh.women_45)::integer AS women_45, sum(sh.women_46)::integer AS women_46, sum(sh.women_47)::integer AS women_47, sum(sh.women_48)::integer AS women_48, sum(sh.women_49)::integer AS women_49,
        sum(sh.women_50)::integer AS women_50, sum(sh.women_51)::integer AS women_51, sum(sh.women_52)::integer AS women_52, sum(sh.women_53)::integer AS women_53, sum(sh.women_54)::integer AS women_54,
        sum(sh.women_55)::integer AS women_55, sum(sh.women_56)::integer AS women_56, sum(sh.women_57)::integer AS women_57, sum(sh.women_58)::integer AS women_58, sum(sh.women_59)::integer AS women_59,
        sum(sh.women_60)::integer AS women_60, sum(sh.women_61)::integer AS women_61, sum(sh.women_62)::integer AS women_62, sum(sh.women_63)::integer AS women_63, sum(sh.women_64)::integer AS women_64,
        sum(sh.women_65)::integer AS women_65, sum(sh.women_66)::integer AS women_66, sum(sh.women_67)::integer AS women_67, sum(sh.women_68)::integer AS women_68, sum(sh.women_69)::integer AS women_69,
        sum(sh.women_70)::integer AS women_70, sum(sh.women_71)::integer AS women_71, sum(sh.women_72)::integer AS women_72, sum(sh.women_73)::integer AS women_73, sum(sh.women_74)::integer AS women_74,
        sum(sh.women_75)::integer AS women_75, sum(sh.women_76)::integer AS women_76, sum(sh.women_77)::integer AS women_77, sum(sh.women_78)::integer AS women_78, sum(sh.women_79)::integer AS women_79,
        sum(sh.women_80)::integer AS women_80, sum(sh.women_81)::integer AS women_81, sum(sh.women_82)::integer AS women_82, sum(sh.women_83)::integer AS women_83, sum(sh.women_84)::integer AS women_84,
        sum(sh.women_85)::integer AS women_85, sum(sh.women_86)::integer AS women_86, sum(sh.women_87)::integer AS women_87, sum(sh.women_88)::integer AS women_88, sum(sh.women_89)::integer AS women_89,
        sum(sh.women_90)::integer AS women_90, sum(sh.women_91)::integer AS women_91, sum(sh.women_92)::integer AS women_92, sum(sh.women_93)::integer AS women_93, sum(sh.women_94)::integer AS women_94,
        sum(sh.women_95)::integer AS women_95, sum(sh.women_96)::integer AS women_96, sum(sh.women_97)::integer AS women_97, sum(sh.women_98)::integer AS women_98, sum(sh.women_99)::integer AS women_99,
        sum(sh.women_100)::integer AS women_100
    FROM social_stats.calculated_sex_age_social_administrative_units sh
    WHERE sh.social_group_id IN (SELECT sgs.id FROM sgs)
    GROUP BY sh.administrative_unit_id, sh.year, sh.scenario
    ORDER BY sh.administrative_unit_id, sh.year, sh.scenario
);
ALTER TABLE social_stats.calculated_sex_age_administrative_units OWNER TO postgres;

CREATE MATERIALIZED VIEW social_stats.calculated_sex_age_municipalities AS (
    WITH sgs AS (
        SELECT social_groups.id
        FROM social_groups
        WHERE social_groups.name LIKE '%(%)'::text
            AND social_groups.name NOT LIKE '%(%т)'::text
            AND social_groups.name NOT LIKE '%(%а)'::text
        ORDER BY social_groups.id
    )
    SELECT sh.municipality_id,
        sh.year,
        sh.scenario,
        sum(sh.men_0)::integer  AS men_0,  sum(sh.men_1)::integer  AS men_1,  sum(sh.men_2)::integer  AS men_2,  sum(sh.men_3)::integer  AS men_3,  sum(sh.men_4)::integer  AS men_4,
        sum(sh.men_5)::integer  AS men_5,  sum(sh.men_6)::integer  AS men_6,  sum(sh.men_7)::integer  AS men_7,  sum(sh.men_8)::integer  AS men_8,  sum(sh.men_9)::integer  AS men_9,
        sum(sh.men_10)::integer AS men_10, sum(sh.men_11)::integer AS men_11, sum(sh.men_12)::integer AS men_12, sum(sh.men_13)::integer AS men_13, sum(sh.men_14)::integer AS men_14,
        sum(sh.men_15)::integer AS men_15, sum(sh.men_16)::integer AS men_16, sum(sh.men_17)::integer AS men_17, sum(sh.men_18)::integer AS men_18, sum(sh.men_19)::integer AS men_19,
        sum(sh.men_20)::integer AS men_20, sum(sh.men_21)::integer AS men_21, sum(sh.men_22)::integer AS men_22, sum(sh.men_23)::integer AS men_23, sum(sh.men_24)::integer AS men_24,
        sum(sh.men_25)::integer AS men_25, sum(sh.men_26)::integer AS men_26, sum(sh.men_27)::integer AS men_27, sum(sh.men_28)::integer AS men_28, sum(sh.men_29)::integer AS men_29,
        sum(sh.men_30)::integer AS men_30, sum(sh.men_31)::integer AS men_31, sum(sh.men_32)::integer AS men_32, sum(sh.men_33)::integer AS men_33, sum(sh.men_34)::integer AS men_34,
        sum(sh.men_35)::integer AS men_35, sum(sh.men_36)::integer AS men_36, sum(sh.men_37)::integer AS men_37, sum(sh.men_38)::integer AS men_38, sum(sh.men_39)::integer AS men_39,
        sum(sh.men_40)::integer AS men_40, sum(sh.men_41)::integer AS men_41, sum(sh.men_42)::integer AS men_42, sum(sh.men_43)::integer AS men_43, sum(sh.men_44)::integer AS men_44,
        sum(sh.men_45)::integer AS men_45, sum(sh.men_46)::integer AS men_46, sum(sh.men_47)::integer AS men_47, sum(sh.men_48)::integer AS men_48, sum(sh.men_49)::integer AS men_49,
        sum(sh.men_50)::integer AS men_50, sum(sh.men_51)::integer AS men_51, sum(sh.men_52)::integer AS men_52, sum(sh.men_53)::integer AS men_53, sum(sh.men_54)::integer AS men_54,
        sum(sh.men_55)::integer AS men_55, sum(sh.men_56)::integer AS men_56, sum(sh.men_57)::integer AS men_57, sum(sh.men_58)::integer AS men_58, sum(sh.men_59)::integer AS men_59,
        sum(sh.men_60)::integer AS men_60, sum(sh.men_61)::integer AS men_61, sum(sh.men_62)::integer AS men_62, sum(sh.men_63)::integer AS men_63, sum(sh.men_64)::integer AS men_64,
        sum(sh.men_65)::integer AS men_65, sum(sh.men_66)::integer AS men_66, sum(sh.men_67)::integer AS men_67, sum(sh.men_68)::integer AS men_68, sum(sh.men_69)::integer AS men_69,
        sum(sh.men_70)::integer AS men_70, sum(sh.men_71)::integer AS men_71, sum(sh.men_72)::integer AS men_72, sum(sh.men_73)::integer AS men_73, sum(sh.men_74)::integer AS men_74,
        sum(sh.men_75)::integer AS men_75, sum(sh.men_76)::integer AS men_76, sum(sh.men_77)::integer AS men_77, sum(sh.men_78)::integer AS men_78, sum(sh.men_79)::integer AS men_79,
        sum(sh.men_80)::integer AS men_80, sum(sh.men_81)::integer AS men_81, sum(sh.men_82)::integer AS men_82, sum(sh.men_83)::integer AS men_83, sum(sh.men_84)::integer AS men_84,
        sum(sh.men_85)::integer AS men_85, sum(sh.men_86)::integer AS men_86, sum(sh.men_87)::integer AS men_87, sum(sh.men_88)::integer AS men_88, sum(sh.men_89)::integer AS men_89,
        sum(sh.men_90)::integer AS men_90, sum(sh.men_91)::integer AS men_91, sum(sh.men_92)::integer AS men_92, sum(sh.men_93)::integer AS men_93, sum(sh.men_94)::integer AS men_94,
        sum(sh.men_95)::integer AS men_95, sum(sh.men_96)::integer AS men_96, sum(sh.men_97)::integer AS men_97, sum(sh.men_98)::integer AS men_98, sum(sh.men_99)::integer AS men_99,
        sum(sh.men_100)::integer AS men_100,
        sum(sh.women_0)::integer  AS women_0,  sum(sh.women_1)::integer  AS women_1,  sum(sh.women_2)::integer  AS women_2,  sum(sh.women_3)::integer  AS women_3,  sum(sh.women_4)::integer  AS women_4,
        sum(sh.women_5)::integer  AS women_5,  sum(sh.women_6)::integer  AS women_6,  sum(sh.women_7)::integer  AS women_7,  sum(sh.women_8)::integer  AS women_8,  sum(sh.women_9)::integer  AS women_9,
        sum(sh.women_10)::integer AS women_10, sum(sh.women_11)::integer AS women_11, sum(sh.women_12)::integer AS women_12, sum(sh.women_13)::integer AS women_13, sum(sh.women_14)::integer AS women_14,
        sum(sh.women_15)::integer AS women_15, sum(sh.women_16)::integer AS women_16, sum(sh.women_17)::integer AS women_17, sum(sh.women_18)::integer AS women_18, sum(sh.women_19)::integer AS women_19,
        sum(sh.women_20)::integer AS women_20, sum(sh.women_21)::integer AS women_21, sum(sh.women_22)::integer AS women_22, sum(sh.women_23)::integer AS women_23, sum(sh.women_24)::integer AS women_24,
        sum(sh.women_25)::integer AS women_25, sum(sh.women_26)::integer AS women_26, sum(sh.women_27)::integer AS women_27, sum(sh.women_28)::integer AS women_28, sum(sh.women_29)::integer AS women_29,
        sum(sh.women_30)::integer AS women_30, sum(sh.women_31)::integer AS women_31, sum(sh.women_32)::integer AS women_32, sum(sh.women_33)::integer AS women_33, sum(sh.women_34)::integer AS women_34,
        sum(sh.women_35)::integer AS women_35, sum(sh.women_36)::integer AS women_36, sum(sh.women_37)::integer AS women_37, sum(sh.women_38)::integer AS women_38, sum(sh.women_39)::integer AS women_39,
        sum(sh.women_40)::integer AS women_40, sum(sh.women_41)::integer AS women_41, sum(sh.women_42)::integer AS women_42, sum(sh.women_43)::integer AS women_43, sum(sh.women_44)::integer AS women_44,
        sum(sh.women_45)::integer AS women_45, sum(sh.women_46)::integer AS women_46, sum(sh.women_47)::integer AS women_47, sum(sh.women_48)::integer AS women_48, sum(sh.women_49)::integer AS women_49,
        sum(sh.women_50)::integer AS women_50, sum(sh.women_51)::integer AS women_51, sum(sh.women_52)::integer AS women_52, sum(sh.women_53)::integer AS women_53, sum(sh.women_54)::integer AS women_54,
        sum(sh.women_55)::integer AS women_55, sum(sh.women_56)::integer AS women_56, sum(sh.women_57)::integer AS women_57, sum(sh.women_58)::integer AS women_58, sum(sh.women_59)::integer AS women_59,
        sum(sh.women_60)::integer AS women_60, sum(sh.women_61)::integer AS women_61, sum(sh.women_62)::integer AS women_62, sum(sh.women_63)::integer AS women_63, sum(sh.women_64)::integer AS women_64,
        sum(sh.women_65)::integer AS women_65, sum(sh.women_66)::integer AS women_66, sum(sh.women_67)::integer AS women_67, sum(sh.women_68)::integer AS women_68, sum(sh.women_69)::integer AS women_69,
        sum(sh.women_70)::integer AS women_70, sum(sh.women_71)::integer AS women_71, sum(sh.women_72)::integer AS women_72, sum(sh.women_73)::integer AS women_73, sum(sh.women_74)::integer AS women_74,
        sum(sh.women_75)::integer AS women_75, sum(sh.women_76)::integer AS women_76, sum(sh.women_77)::integer AS women_77, sum(sh.women_78)::integer AS women_78, sum(sh.women_79)::integer AS women_79,
        sum(sh.women_80)::integer AS women_80, sum(sh.women_81)::integer AS women_81, sum(sh.women_82)::integer AS women_82, sum(sh.women_83)::integer AS women_83, sum(sh.women_84)::integer AS women_84,
        sum(sh.women_85)::integer AS women_85, sum(sh.women_86)::integer AS women_86, sum(sh.women_87)::integer AS women_87, sum(sh.women_88)::integer AS women_88, sum(sh.women_89)::integer AS women_89,
        sum(sh.women_90)::integer AS women_90, sum(sh.women_91)::integer AS women_91, sum(sh.women_92)::integer AS women_92, sum(sh.women_93)::integer AS women_93, sum(sh.women_94)::integer AS women_94,
        sum(sh.women_95)::integer AS women_95, sum(sh.women_96)::integer AS women_96, sum(sh.women_97)::integer AS women_97, sum(sh.women_98)::integer AS women_98, sum(sh.women_99)::integer AS women_99,
        sum(sh.women_100)::integer AS women_100
    FROM social_stats.calculated_sex_age_social_municipalities sh
    WHERE sh.social_group_id IN (SELECT sgs.id FROM sgs)
    GROUP BY sh.municipality_id, sh.year, sh.scenario
    ORDER BY sh.municipality_id, sh.year, sh.scenario
);
ALTER TABLE social_stats.calculated_sex_age_municipalities OWNER TO postgres;

-- functions

CREATE FUNCTION random_between(low integer, high integer) RETURNS integer
    LANGUAGE plpgsql STRICT
    AS $$
BEGIN
    RETURN floor(random()* (high-low + 1) + low);
END;
$$;
ALTER FUNCTION random_between(low integer, high integer) OWNER TO postgres;

CREATE FUNCTION refresh_all_materialized_views(schema_arg text DEFAULT 'public'::text) RETURNS void
    LANGUAGE plpgsql
    AS $$
	DECLARE
		r RECORD;
	BEGIN
		RAISE NOTICE 'Refreshing materialized view in schema %', schema_arg;
		FOR r IN SELECT matviewname FROM pg_matviews WHERE schemaname = schema_arg and matviewname != 'age_sex_structure_district' and matviewname != 'all_services'
			and matviewname != 'social_structure_district'
		LOOP
			RAISE NOTICE 'Refreshing %.%', schema_arg, r.matviewname;
			EXECUTE 'REFRESH MATERIALIZED VIEW ' || schema_arg || '.' || r.matviewname;
		END LOOP;
	END
$$;
ALTER FUNCTION refresh_all_materialized_views(schema_arg text) OWNER TO postgres;

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
        administrative_unit_id = (SELECT au.id FROM administrative_units au WHERE au.city_id = p.city_id AND ST_CoveredBy(p.center, au.geometry) LIMIT 1)
    WHERE administrative_unit_id IS NULL;
    UPDATE physical_objects p SET
        municipality_id = (SELECT m.id FROM municipalities m WHERE m.city_id = p.city_id AND ST_CoveredBy(p.center, m.geometry) LIMIT 1)
    WHERE municipality_id IS NULL;
    UPDATE physical_objects p SET
        block_id = (SELECT b.id FROM blocks b WHERE b.city_id = p.city_id AND ST_CoveredBy(p.center, b.geometry) LIMIT 1)
    WHERE block_id IS NULL;

$$;
ALTER FUNCTION update_physical_objects_location OWNER TO postgres;

CREATE FUNCTION update_blocks_location() RETURNS void
LANGUAGE SQL AS
$$
    UPDATE blocks b SET
        administrative_unit_id = (SELECT au.id FROM administrative_units au WHERE au.city_id = b.city_id AND ST_CoveredBy(b.center, au.geometry) LIMIT 1)
    WHERE administrative_unit_id IS NULL;
    UPDATE blocks b SET
        administrative_unit_id = (SELECT au.id FROM administrative_units au WHERE au.city_id = b.city_id AND ST_Intersects(b.geometry, au.geometry) LIMIT 1)
    WHERE administrative_unit_id IS NULL;

    UPDATE blocks b SET
        municipality_id = (SELECT m.id FROM municipalities m WHERE m.city_id = b.city_id AND ST_CoveredBy(b.center, m.geometry) LIMIT 1)
    WHERE municipality_id IS NULL;
    UPDATE blocks b SET
        municipality_id = (SELECT m.id FROM municipalities m WHERE m.city_id = b.city_id AND ST_Intersects(b.geometry, m.geometry) LIMIT 1)
    WHERE municipality_id IS NULL;
$$;
ALTER FUNCTION update_blocks_location OWNER TO postgres;

END TRANSACTION;
