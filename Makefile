TORRSERVER_VERSION="MatriX.81"
DSM="6.0"

.PHONY: torrserver-% clean

all: torrserver-amd64 torrserver-386 torrserver-arm64 torrserver-arm7

torrserver-%:
	@./build-package.sh ${TORRSERVER_VERSION} $* ${DSM}

clean:
	rm -rf torrserver spk
