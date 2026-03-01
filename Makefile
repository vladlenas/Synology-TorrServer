TORRSERVER_VERSION="MatriX.141"
PKG_VERSION="1.2.141"
DSM="7.3"

.PHONY: torrserver-% clean

all: torrserver-amd64 torrserver-386 torrserver-arm64 torrserver-arm7

torrserver-%:
	@./build-package.sh ${TORRSERVER_VERSION} $* ${PKG_VERSION} ${DSM}

clean:
	rm -rf spk dest_bin build
