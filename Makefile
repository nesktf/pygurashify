SHELL       := /bin/bash
VENV_DIR    ?= ./.venv
SRC_DIR     := ./src
REQ_FILE    := ./requirements.txt
PY          := python3

.PHONY: run gui venv clean build

venv:
	$(PY) -m venv $(VENV_DIR)
	$(VENV_DIR)/bin/pip install -r $(REQ_FILE)

$(VENV_DIR): venv

run: $(VENV_DIR)/
	source $(VENV_DIR)/bin/activate && $(PY) $(SRC_DIR)/main.py

gui: $(VENV_DIR)/
	source $(VENV_DIR)/bin/activate && $(PY) $(SRC_DIR)/gui.py

build: $(VENV_DIR)
	$(VENV_DIR)/bin/pyinstaller --onefile $(SRC_DIR)/main.py

clean:
	rm -rf $(VENV_DIR) build dist *.spec

