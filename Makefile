TORRSERVER_VERSION="MatriX.125"
PKG_VERSION="1.2.125"
DSM="7.1"

.PHONY: torrserver-% bin clone clean

all: torrserver-amd64 torrserver-386 torrserver-arm64 torrserver-arm7

torrserver-%:
	@./build-package.sh ${TORRSERVER_VERSION} $* ${PKG_VERSION} ${DSM}

bin:
	./build-bin.sh

clone:
	git clone ${GIT_URL}

clean:
	rm -rf spk dest_bin TorrServer build
