CODE_DIR := platform_management
EXECUTABLE := platform-management

gui:
	poetry run $(EXECUTABLE) gui

debug-gui:
	poetry run $(EXECUTABLE) gui --verbose

lint:
	poetry run pylint $(CODE_DIR)

format:
	poetry run isort $(CODE_DIR)
	poetry run black $(CODE_DIR)

install:
	pip install .

install-dev:
	poetry install --with dev

install-dev-pip:
	pip install -e . --config-settings editable_mode=strict

build:
	poetry build

clean:
	rm -rf ./build ./dist ./$(EXECUTABLE).egg-info

install-from-build:
	python -m wheel install dist/$(CODE_DIR)-*.whl
