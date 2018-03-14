.PHONY: help upgrade requirements clean quality requirements docs \
  test test-all coverage \
	compile_translations dummy_translations extract_translations \
	fake_translations pull_translations push_translations

.DEFAULT_GOAL := help

define BROWSER_PYSCRIPT
import os, webbrowser, sys
try:
	from urllib import pathname2url
except:
	from urllib.request import pathname2url

webbrowser.open("file://" + pathname2url(os.path.abspath(sys.argv[1])))
endef
export BROWSER_PYSCRIPT
BROWSER := python -c "$$BROWSER_PYSCRIPT"

help: ## display this help message
	@echo "Please use \`make <target>' where <target> is one of"
	@perl -nle'print $& if m{^[a-zA-Z_-]+:.*?## .*$$}' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m  %-25s\033[0m %s\n", $$1, $$2}'

clean: ## remove generated byte code, coverage reports, and build artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info

upgrade: ## update the requirements/*.txt files with the latest packages satisfying requirements/*.in
	pip install -q pip-tools
	pip-compile --upgrade -o requirements/base.txt requirements/base.in
	pip-compile --upgrade -o requirements/dev.txt requirements/dev.in requirements/quality.in
	pip-compile --upgrade -o requirements/doc.txt requirements/base.in requirements/doc.in
	pip-compile --upgrade -o requirements/quality.txt requirements/quality.in
	pip-compile --upgrade -o requirements/test.txt requirements/base.in requirements/test.in
	# Let tox control the Django version for tests
	sed '/django==/d' requirements/test.txt > requirements/test.tmp
	mv requirements/test.tmp requirements/test.txt

requirements: ## install development environment requirements
	pip install -qr requirements/dev.txt --exists-action w
	pip-sync requirements/*.txt requirements/private.*

install: upgrade requirements
	./manage.py syncdb --noinput --settings=test_settings
	./manage.py migrate --settings=test_settings
	npm install

coverage: clean ## generate and view HTML coverage report
	py.test --cov-report html
	$(BROWSER) htmlcov/index.html

docs: ## generate Sphinx HTML documentation, including API docs
	tox -e docs
	$(BROWSER) docs/_build/html/index.html

quality: ## check coding style with pycodestyle and pylint
	tox -e quality

test-python: clean ## run tests in the current virtualenv
	./manage.py test edx_proctoring --verbosity=3

test-js:
	gulp test

test-all: ## run tests on every supported Python/Django combination
	tox -e quality
	tox

diff_cover: test
	diff-cover coverage.xml

## Localization targets

extract_translations: ## extract strings to be translated, outputting .mo files
	cd edx_proctoring && ../manage.py makemessages -l en -v1 -d django
	cd edx_proctoring && ../manage.py makemessages -l en -v1 -d djangojs

compile_translations: ## compile translation files, outputting .po files for each supported language
	cd edx_proctoring && ../manage.py compilemessages

detect_changed_source_translations:
	cd edx_proctoring && i18n_tool changed

pull_translations: ## pull translations from Transifex
	tx pull -af --mode reviewed

push_translations: ## push source translation files (.po) from Transifex
	cd edx_proctoring && i18n_tool transifex push

dummy_translations: ## generate dummy translation (.po) files
	cd edx_proctoring && i18n_tool dummy

build_dummy_translations: extract_translations dummy_translations compile_translations ## generate and compile dummy translation files

validate_translations: build_dummy_translations detect_changed_source_translations ## validate translations
