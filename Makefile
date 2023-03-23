gui:
	python -m platform_management gui

debug-gui:
	python -m platform_management gui --verbose

lint:
	python -m pylint --max-line-length 120 platform_management -d duplicate-code

format:
	python -m black platform_management