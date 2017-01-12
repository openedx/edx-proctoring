all: install test

.PHONY: install test

# not used by travis
install-system:
	echo installing apt...

# not used by travis
install-node:
	echo nodejs...

install-sys-requirements: install-system install-node
	npm config set loglevel warn

install-wheels:
	./scripts/install-wheels.sh

install-js:
	npm install

install: install-wheels install-js

install-test:
	pip install -q -r test_requirements.txt

install-python:
	pip install -q -r local_requirements.txt --exists-action w

install-coveralls:
	pip install coveralls

install-dev: install-python install-test install-coveralls

test:
	./scripts/run-tests.sh

i18n-push:
	./scripts/i18n-push.sh

i18n-pull:
	./scripts/i18n-pull.sh
