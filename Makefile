CODE_DIR := platform_management

gui:
	python -m $(CODE_DIR) gui

debug-gui:
	python -m $(CODE_DIR) gui --verbose

lint:
	pylint $(CODE_DIR)

format:
	isort $(CODE_DIR)
	black $(CODE_DIR)

install:
	pip install .

install-dev:
	pip install -e . --config-settings editable_mode=strict

build:
	poetry build

clean:
	rm -rf ./build ./dist ./$(CODE_DIR).egg-info

install-from-build:
	python -m wheel install dist/$(CODE_DIR)-*.whl
