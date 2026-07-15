SHELL := /bin/sh
VERSION := $(shell sed -n 's/.*"version": "\([^"]*\)".*/\1/p' manifest.json)
PACKAGE := dist/silverlists-web-extension-$(VERSION).zip
FILES := manifest.json service-worker.js options.html options.js popup.html \
	download-prompt.html download-prompt.css download-prompt.js silverlists.svg \
	silverlists-web-logo.png README.md THIRD_PARTY_NOTICES.md

.PHONY: all verify package clean

all: package

verify:
	@python3 -m json.tool manifest.json >/dev/null
	@node --check service-worker.js
	@node --check options.js
	@node --check download-prompt.js

package: verify
	@mkdir -p dist
	@rm -f $(PACKAGE)
	@zip -q $(PACKAGE) $(FILES)
	@echo "Erzeugt: $(PACKAGE)"

clean:
	@rm -rf dist
