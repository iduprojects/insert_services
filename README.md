# insert services application

This is a part of Digital City Model project. Script and GUI application helps to insert new
  services into database and update already present ones.

## Installation

1. Install Pyhton 3 (tested on Python 3.10)
2. Clone or download this repository and open terminal in folder with downloaded data
3. (optionally) prepare virtual environment (with `poetry install; poetry shell` or manually `python -m venv venv`
  and activating it)
4. Install the utility with `pip install .`

Running on Linux might require you to install development files of OpenGL to install the project (`libqt4-opengl-dev` or
`libqt5opengl5-dev` in Debian namings)

Before connecting to the database, ensure you have city database with following tables: `buildings`, `physical_objects`,
    `functional_objects`, `city_service_types`, `city_functions`, `city_infrastructure_types`

## Usage

Command line interface help may be acuired by running `platform-management --help`

### Graphical user interface

GUI can be launched with `platform-management gui`. After that a window with credentials fields will appear.

On launch, environment variables are used to fill defaults in the credentials. User can set credentials in .env file
  and it will be read as well.

### Command line interface - administrative boundaries insertion

There are three layers of administrative boundaries in the data model:
City -> _(outer administrative boundaries)_ -> _(inner administrative boundaries)_

The second ones can be inserted with `platform-management insert-adms`. There are two types of administrative
  boundaries types: **administrative units** and **municipalities**, depending on a city division type one can relate to
  other as a parent and vice-versa.

### Command line interface - blocks insertion

Blocks are a lower level of administrative boundaries and they can be loaded only via CLI module
  `platform-management insert-blocks`.

### Command line interface - buildings insertion

In services insertion process (next step), services are joined to buildings by geometry (or address). If no building
  is found, then the new one is created without additional parameters (such as storeys count, is_living, etc.).

So, in order to keep the number of buildings without parameters to the minimum, it is considered as a good approach to
  load them before loading services, with `platform-management insert-buildings`

### Command line interface - services insertion

Launch script with `platform-management insert-services --help` to get help.

At the launch you must provide given arguments:

* `--city` or `-c` for name of the city where services would be inserted
* `--service_type` or `-T` for service type (name or code from `city_service_types` table)
* `filename` for document path with type of (.csv, .json, .geojson, .xlsx, .xls, .ods)

Database connection can be set via given arguments:

* `--db_addr` or `-H` for DBMS address (default: _localhost_)
* `--db_port` or `-P` for DBMS port (default: _5432_)
* `--db_name` or `-d` for database name (default: _citydb_)
* `--db_user` or `-U` for DBMS user (default: _postgres_)
* `--db_pass` or `-W` for DBMS user password (default: _postgres_)

Columns mapping from document to database can be configured via parameters (everything except latitude,
  longitude and address can be skipped with value "-"):

* `--document_latitude` or `-dx` for latitude field (default: _x_)
* `--document_longitude` or `-dy` for longitude field (default: _y_)
* `--document_geometry` or `-dg` for geometry field in GeoJSON format (default: _geometry_)
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
* `--log` or `-l` for setting a name for log file (default: datetime in format _YYYY-MM-DD HH-mm-ss-\<filename\>.csv_)
* `--dry_run` or `-d` for dry run (changes will be aborted, but indexes still moved)
* `--verbose` or `-v` for printing a stack traces when error happens

### Preparations before using graphical user interface (russian)

Перед вставкой объектов нужно установить сервер СУБД, настроить до доступ и создать схему с основными сущностями
  и базовыми данными. Это можно сделать, выполнив следующую последовательность действий:

1. Установить сервер PostgreSQL (версия 10+)
2. Установить к нему расширение PostGIS
3. Создать пользователя с паролем, которому разрешен вход
4. Создать пустую базу данных (например, `city_db_test`)
5. Выполнить содержимое файла `init_schema.sql` (`psql -d city_db_test -1 -f init_schema.sql`)
6. Выполнить содержимое файла `init_data.sql` (`psql -d city_db_test -1 -f init_data.sql`)
7. Добавить город в базу, муниципальные образования и административные единицы через графический интерфейс в разделе
  "Манипуляции с городами" или консольный интерфейс
8. Добавить сервисы из excel-таблиц/csv-файлов в базу через графический интерфейс в разделе "Вставка сервисов"
9. При необходимости, можно изменить данные сервисов через графический интерфейс в разделе "Изменение сервисов"

Также рекомендуется перед загрузкой сервисов добавить здания с геометрией и загрузить административные единицы,
  муниципалитеты и кварталы. На данный момент кварталы и здания могут быть загружены только через консольный интерфейс.

### Graphical user interface (russian)

1. Установите утилиту как указано в секции установки
2. Запустите `platform-management gui`
3. Подключение к БД. Задайте адрес, название БД, пользователя и пароль для PostgreSQL в блоке "База данных" и нажмите на "Проверить подключение".
  Если знак вопроса справа от кнопки заменился на зеленую галочку, подключение успешно.
  В противном случае можно посмотреть ошибку, повторив попытку с зажатой клавишей Shift.
4. Операции с городами
  * Из меню выберите пункт "Операции с городами" и нажмите "Запуск".
  * Нажмите "Добавить город" для добавления города (нужно указать его геометрию, название, количество жителей и тип административного деления).
  * Выберите город из списка и нажмите на "Изменить город" для изменения его параметров (геометрии, названия, количества жителей или типа административного деления).
  * Выберите город из списка и нажмите на "Удалить город" для удаления города из базы данных.
  * Выберите город из списка и нажмите на "Посмтореть геометрию", чтобы открылось окно с геометрией и кнопкой копирования.
  * Выберите город из списка и нажмите на "Список МО", чтобы открыть список его муниципаьлных образований.
    * Нажмите на "Добавить муниципальное образование", чтобы добавить новое МО (нужно указать его геометрию, название, количество жителей,
      тип территории и родительскую территорию).
    * Выберите МО из списка и нажмите на "Изменить муниципальное образование", чтобы изменить его параметры.
    * Выберите МО из списка и нажмите на "Удалить муниципаьлное образование", чтобы удалить его из базы данных.
    * Выберите МО из списка и нажмите на "Посмотреть геометрию", чтобы открылось окно с геометрией и кнопкой копирования.
    * Закройте окно, чтобы вернуться к списку городов
  * Выберите город из списка и нажмите на "Список АЕ", чтобы открыть список его административных единиц. Возможности аналогичны списку МО.
  * Нажмите на "Сохранить изменения в БД", чтобы сохранить внесенные изменения в базе данных, либо на "Отмена изменений", чтобы отемнить внесенные изменения.
  * После загрузки сервисов нажмите на "Обновить представления", чтобы обновить материализованные представления в базе данных
  * После загрузки сервисов нажмите на "Обновить локации объектов", чтобы обновить идентификаторы АЕ и МО у объектов, у которых они отсутствуют,
    по пирзнаку нахождения внутри геометрии.
  * Закройте это окно, чтобы вернуться обратно к начальному
5. Загрузка сервисов
  1. Из меню выберите пункт "Загрузка сервисов" и нажмите "Запуск".
  2. Отркытие файла. Перетащите файл (xlsx, csv, geojson) на кнопку "Открыть файл" или нажмите на нее и откройте файл через менеджер.
  3. Выберите тип загружаемых сервисов из выпадающего списка рядом с надписью "Тип сервиса".
  4. В блоке "Сопоставление документа" нужно выбрать использующиеся столбцы, они будут отмечены зеленым в документе.
    Если на какой-то столбец ссылается больше одного селектора, он отображается серым, это не ошибка.
    Столбец "Адрес" проверяется на соответствие заданным префиксам адреса и в зависимости от того, нашелся ли префикс, удовлетворяющий адресу,
    ячейка окрашивается в темно-зеленый или красный. Строки с красными ячейками адреса загружены не будут
    Широта и долгота - обязательные поля.
  5. В блоке "Префиксы адреса" можно задать возможные валидные префиксы адреса, которые будут заменены на общий префикс, задаваемый внизу.
    Порядок задания не важен, префиксы будут проверяться от самых длинных до самых коротких. Если добавить пустой префикс, то все объекты будут загружены.
    Количество адресов объектов, попадающих под ограничения хотя бы одного префикса, отображено счетчиком в названии блока в виде "(подходят / общее_число)"
  6. Если нужно принудительно пропустить некоторые объекты, это можно сделать, нажав двойным щелчком на ячейку колонки "Загрузить" в их строках,
    либо выделив несколько ячеек данной колонки и нажав на Numpad-. Для включения обратно в список можно воспользоваться Numpad+. Нажатие Enter переключит состояние.
  7. Если в опциях выбора нет элементов, горящих красным, доступна кнопка "Загрузить сервисы", она запускает мехаинзм загрузки сервисов в базу данных.
  8. После загрузки в документе появятся две дополнительных колонки - "Результат" и "id Функционального объекта".
    Можно сохранить обновленную таблицу для дальнейшей обработки с помощью кнопки "Сохранить результат".
    Также есть возможность повторно загрузить объекты, используя кнопку "Загрузить сервисы" (изменять таблицу нельзя, только включать-выключать загрузку).
    Кроме того, можно открыть новый файл с данными аналогично пункту 3.
6. Изменение сервисов
  * Из меню выберите пункт "Изменение сервисов" и нажмите "Запуск".
  * Выберете город для отображения сервисов из списка рядом с надписью "Город".
  * Выберете тип сервиса, загруженный в данный город, из списка рядом с надписью "Тип сервиса".
  * Нажмите на "Отобразить сервисы", чтобы получить список сервисов заданного типа в заданном городе.
  * Выберите один или несколько сервисов и нажмите на "Уделить сервис", чтобы удалить его/их из базы данных.
  * Выберите сервис из списка и нажмите на "Посмотреть геометрию", чтобы открылось окно с геометрией и кнопкой копирования.
  * Выберите сервис из списка и нажмите на "Добавить здание" или "Добвить физический объект" (в зависимости от типа сервиса),
    чтобы заменить его текущий физический объект или здание новым.
  * Выберите сервис из списка и нажмите на "Изменить здание" или "Изменить физический объект" (в зависимости от типа сервиса),
    чтобы изменить параметры его текущего физического объекта или здания.
  * Нажмите на "Экспортировать таблицу", чтобы сохранить список объектов.
  * Нажмите на "Сохранить изменения в БД", чтобы сохранить внесенные изменения, либо на "Отмена изменений", чтобы их отменить.
