# insert services application

This is a part of Digital City Model project. Script and GUI application helps to insert new services into database and update already present ones.  

## Installation

1. Install Pyhton 3 (tested on Python 3.9.5)
2. Clone or download this repository and open terminal in folder with downloaded data
3. Install required packages (`pip install -r requirements.txt`)

Before working, ensure you have city database with following tables: `buildings`, `physical_objects`, ,
    `functional_objects`, `service_types`, `city_functions`, `infrastructure_types`
Also, on Linux you might need to install development files of opengl from `libqt4-opengl-dev` or `libqt5opengl5-dev` (debian namings)

## Usage

### Command line interface

Launch script with `python adding_functional_objects.py --help` to get help.

At the launch you must provide given arguments:

* `--service_type` or `-t` for service type (name from/for `city_service_types` table)
* `filename` for document path with type of (.csv, .json, .geojson, .xlsx, .xls, .odt)

Additional arguments for new service type insertion (for `city_service_types` table):

* `--service_type_code` or `-C` for service code
* `--min_capacity` or `-mC` for minimal service type capacity
* `--max_capacity` or `-MC` for maximum service type capacity
* `--min_status` or `-mS` for minimal service type status
* `--max_status` or `-MS` for maximum service type status
* `--city_function` or `-f` for city function (name or code)

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
* `--document_capacity` or `-dA` for capacity field (default skipped)
* `--osm_id` or `-dI` for OpenStreetMap identificator field (default: _id_)

Other parameters:

* `--document_address_prefix` or `-dAP` for adding a document address prefix (default: _Россия, Санкт-Петербург_)
* `--new_address_prefix` or `-nAP` for setting a prefix to add to every new address (default empty)
* `--log` or `-l` for setting a name for log file (default: datet-ime in format _YYYY-MM-DD HH-mm-ss-\<filename\>.csv_)
* `--dry_run` or `-D` for dry run (changes will be aborted, but indexes still moved)
* `--verbose` or `-v` for printing a stack traces when error happens

### Graphical user interface

(russian)

1. Запустите `python insert_services_gui.py`
2. Подключение к БД. Задайте адрес, название БД, пользователя и пароль для PostgreSQL в блоке "База данных" и нажмите на "Проверить подключение".  
  Если знак вопроса справа от кнопки заменился на зеленую галочку, подключение успешно.  
  В противном случае можно посмотреть ошибку, повторив попытку с зажатой клавишей Shift.
3. Отркытие файла. Перетащите файл (xlsx, csv, geojson) на кнопку "Открыть файл" или нажмите на нее и откройте файл через менеджер.
4. Установка параметров типа сервиса.
  * Если тип сервиса уже присутствует в базе данных, то поставьте галочку "Выбрать тип сервиса" и сделайте выбор из выпадающего списка рядом с надписью "Тип сервиса"
  * Если вносится тип, отсутствующий в базе данных, то галочка не используется. В "Тип сервиса" вносится название (на русском языке),  
    в "Код сервиса" - код (на английском, во множественном числе), из выпаюащего списка выбирается городская функция, которой тип сервиса принадлежит.  
    Минимальная и максимальная мощности - целые числа, максимальная не меньше минимальной.  
    Минимальный и максимальный статусы - целые числа, максимальные не меньше минимального.  
    Если представитель типа сервиса представляет собой здание, то нужно установить галочку "Сервис-здание?".
5. В блоке "Сопоставление документа" нужно выбрать использующиеся столбцы, они будут отмечены зеленым в документе.  
  Если на какой-то столбец ссылается больше одного селектора, он отображается серым, это не ошибка.  
  Столбец "Адрес" проверяется на соответствие заданным префиксам адреса и в зависимости от того, нашелся ли префикс, удовлетворяющий адресу,
  ячейка окрашивается в темно-зеленый или красный. Строки с красными ячейками адреса загружены не будут  
  Широта и долгота - обязательные поля.
6. В блоке "Префиксы адреса" можно задать возможные валидные префиксы адреса, которые будут заменены на общий префикс, задаваемый внизу.  
  Порядок задания не важен, префиксы будут проверяться от самых длинных до самых коротких. Если добавить пустой префикс, то все объекты будут загружены.  
  Количество адресов объектов, попадающих под ограничения хотя бы одного префикса, отображено счетчиком в названии блока в виде "(подходят / общее_число)"
7. Если нужно принудительно пропустить некоторые объекты, это можно сделать, нажав двойным щелчком на ячейку колонки "Загрузить" в их строках,
  либо выделив несколько ячеек данной колонки и нажав на Numpad-. Для включения обратно в список можно воспользоваться Numpad+. Нажатие Enter переключит состояние.
8. Если в опциях выбора нет элементов, горящих красным, доступна кнопка "Загрузить сервисы", она запускает мехаинзм загрузки сервисов в базу данных.
9. После загрузки в документе появятся две дополнительных колонки - "Результат" и "id Функционального объекта".  
  Можно сохранить обновленную таблицу для дальнейшей обработки с помощью кнопки "Сохранить результат".  
  Также есть возможность повторно загрузить объекты, используя кнопку "Загрузить сервисы" (изменять таблицу нельзя, только включать-выключать загрузку).  
  Кроме того, можно открыть новый файл с данными аналогично пункту 3.