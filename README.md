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

Launch script with `python adding_functional_objects.py --help` to get help

### Graphical user interface

Launch GUI with `python insert_services_gui.py`