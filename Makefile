PYTHON ?= python3
SKILL = plugins/tafwid/skills/delegate

.PHONY: test
test:
	$(PYTHON) scripts/check_package.py
	$(PYTHON) -m unittest discover -s $(SKILL)/tests -v
	node --test $(SKILL)/tests/dashboard-view.test.mjs
