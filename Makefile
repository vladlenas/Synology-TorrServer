TORRSERVER_VERSION="MatriX.128"
PKG_VERSION="1.2.128"
DSM="7.1"

.PHONY: torrserver-% clean

all: torrserver-amd64 torrserver-386 torrserver-arm64 torrserver-arm7

torrserver-%:
	@./build-package.sh ${TORRSERVER_VERSION} $* ${PKG_VERSION} ${DSM}

clean:
	rm -rf spk dest_bin build
