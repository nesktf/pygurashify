SHELL       := /bin/bash
VENV_DIR    ?= ./.venv
SRC_DIR     := ./src
REQ_FILE    := ./requirements.txt
PY          := python3
SPEC_FILE   := ./pygurashify.spec

.PHONY: run gui venv clean build

venv: $(REQ_FILE)
	$(PY) -m venv --system-site-packages $(VENV_DIR)
	$(VENV_DIR)/bin/python -m pip install -r $(REQ_FILE)

$(VENV_DIR): venv

run: $(VENV_DIR)/
	source $(VENV_DIR)/bin/activate && $(PY) $(SRC_DIR)/cli.py

gui: $(VENV_DIR)/
	source $(VENV_DIR)/bin/activate && $(PY) $(SRC_DIR)/gui.py

build: $(VENV_DIR) $(SPEC_FILE)
	$(VENV_DIR)/bin/pyinstaller --noconfirm $(SPEC_FILE)

clean:
	rm -rf $(VENV_DIR) build dist