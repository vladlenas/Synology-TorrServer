TORRSERVER_VERSION="MatriX.123"
PKG_VERSION="1.2.123"
GIT_URL=https://github.com/vladlenas/TorrServer.git
#GIT_URL=https://github.com/YouROK/TorrServer.git
#GIT_URL=-b new-torrent https://github.com/YouROK/TorrServer.git

.PHONY: torrserver-% bin clone clean

all: torrserver-amd64 torrserver-386 torrserver-arm64 torrserver-arm7 

torrserver-%:
	@./build-package.sh ${TORRSERVER_VERSION} $* ${PKG_VERSION} "6.0"
	@./build-package.sh ${TORRSERVER_VERSION} $* ${PKG_VERSION} "7.0"

bin:
	./build-bin.sh

clone:
	git clone ${GIT_URL}

clean:
	rm -rf spk dest_bin TorrServer
