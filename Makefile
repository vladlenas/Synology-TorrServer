TORRSERVER_VERSION="MatriX.101"
PKG_VERSION="1.2.101"

.PHONY: torrserver-% clean

all: torrserver-amd64 torrserver-386 torrserver-arm64 torrserver-arm7 torrserver-arm5

torrserver-%:
	@./build-package.sh ${TORRSERVER_VERSION} $* ${PKG_VERSION} "6.0"
	@./build-package.sh ${TORRSERVER_VERSION} $* ${PKG_VERSION} "7.0"
clean:
	rm -rf spk torrserver
