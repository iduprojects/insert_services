# insert services application

This is a part of Digital City Model project. Script and GUI application helps to insert new services into database and update already present ones.  

## Installation

1. Install Pyhton 3 (tested on Python 3.9.5)
2. Clone or download this repository and open terminal in folder with downloaded data
3. Install required packages (`pip install -r requirements.txt`)

Before working, ensure you have city database with following tables: `buildings`, `physical_objects`, `phys_objs_fun_objs`,
    `functional_objects`, `service_types`, `city_functions`, `infrastructure_types`
Also, on Linux you might need to install development files of opengl from `libqt4-opengl-dev` or `libqt5opengl5-dev` (debian namings)

## Usage

### Command line interface

Launch script with `python adding_functional_objects.py --help` to get help.

At the launch you must provide given arguments:

* `--class` or `-c` for service class (tables will be named as \<class\>\_objects and \<class\>\_object\_types)
* `--type` or `-t` for service type (name from/for `service_types` table)
* `filename` for document path with type of (.csv, .json, .geojson, .xlsx, .xls, .odt)

Additional arguments for new service insertion (for `service_types` table):

* `--code` or `-C` for service code
* `--min_capacity` or `-m` for minimal service type capacity
* `--max_capacity` or `-M` for maximum service type capacity
* `--city_function` or `-f` for city function

Database connection can be set via given arguments:

* `--db_addr` or `-H` for DBMS address (default: _localhost_)
* `--db_port` or `-P` for DBMS port (default: _5432_)
* `--db_name` or `-d` for database name (default: _citydb_)
* `--db_user` or `-U` for DBMS user (default: _postgres_)
* `--db_pass` or `-W` for DBMS user password (default: _postgres_)

Columns mapping from document to database can be configured via parameters (everything except latitude, longitude and address can be skipped with value "-"):

* `--document_latitude` or `-dx` for latitude field (default: _x_)
* `--document_longitude` or `-dy` for longitude field (default: _y_)
* `--document_address` or `-dAD` for address field (default: _yand\_addr_)
* `--document_name` or `-dN` for name field (default: _name_)
* `--document_website` or `-dW` for website field (default: _contact:website_)
* `--document_phone` or `-dP` for phone number field (default: _contact:phone_)
* `--document_opening_hours` or `-dO` for opening hours field (default: _opening\_hours_)
* `--document_amenity` or `-dA` for amenity field (default: _amenity_)
* `--osm_id` or `-dI` for OpenStreetMap identificator field (default: _id_)
* `--document_additional` or `-dC` with format "`<name in db>`\*\*`<datatype>`\*\*`<name in document>`" for adding additional column (for `<class>_objects` table)

Other parameters:

* `--amenity` or `-a` for overriding amenity from amenity field; it is fully ignored when this option is used
* `--document_address_prefix` or `-dAP` for adding a document address prefix (default: _Россия, Санкт-Петербург_)
* `--types` or `-t` for locating a types file (default: _typs.json_)
* `--log` or `-l` for setting a name for log file (default: datet-ime in format _YYYY-MM-DD HH-mm-ss-\<filename\>.csv_)
* `--dry_run` or `-D` for dry run (changes will be aborted, but indexes still moved)
* `--verbose` or `-v` for printing a stack traces when error happens

### Graphical user interface

Launch GUI with `python insert_services_gui.py`

If file _types.json_ is present in the directory of launch, it will be loaded by default as types file.
