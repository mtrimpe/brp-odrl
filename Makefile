.PHONY: setup generate clean

PYTHON = .venv/bin/python

setup: .venv
	$(PYTHON) -m pip install -q rdflib openpyxl pyparsing

.venv:
	python3 -m venv .venv

generate: setup
	$(PYTHON) generators/generate_all.py

clean:
	rm -rf csv/ ttl/
	$(PYTHON) generators/generate_all.py --clean
