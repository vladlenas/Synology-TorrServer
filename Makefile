TORRSERVER_VERSION="MatriX.104.DLNA"
PKG_VERSION="1.2.104.1"

.PHONY: torrserver-% bin clean

all: torrserver-amd64 torrserver-386 torrserver-arm64 torrserver-arm7 torrserver-arm5

torrserver-%:
	@./build-package.sh ${TORRSERVER_VERSION} $* ${PKG_VERSION} "6.0"
	@./build-package.sh ${TORRSERVER_VERSION} $* ${PKG_VERSION} "7.0"

bin:
	./build-bin.sh

clean:
	rm -rf spk dest_bin TorrServer
