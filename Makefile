TORRSERVER_VERSION="MatriX.85"
PKG_VERSION="1.2.85"
DSM="6.0"

.PHONY: torrserver-% clean

all: torrserver-amd64 torrserver-386 torrserver-arm64 torrserver-arm7

torrserver-%:
	@./build-package.sh ${TORRSERVER_VERSION} $* ${DSM} ${PKG_VERSION}

clean:
	rm -rf torrserver spk
