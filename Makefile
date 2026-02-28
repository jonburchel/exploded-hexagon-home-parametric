.PHONY: setup regen auto ui

setup:
	python -m pip install -r requirements.txt

regen:
	python -m src.main regen

auto:
	python -m src.main auto

ui:
	python -m src.ui

