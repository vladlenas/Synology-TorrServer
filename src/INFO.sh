#!/bin/bash

PKG_VERSION=$1
ARCH=$2
PKG_SIZE=$3
DSM=$4

TIMESTAMP=$(date -u +%Y%m%d-%H:%M:%S)

case $ARCH in
amd64)
  PLATFORMS="apollolake avoton braswell broadwell broadwellnk broadwellnkv2 broadwellntbap bromolow cedarview denverton epyc7002 geminilake grantley kvmx64 purley r1000 v1000 x86_64"
  ;;
386)
  PLATFORMS="evansport x86"
  ;;
arm64)
  PLATFORMS="aarch64 armv8 rtd1296 armada37xx"
  ;;
arm7)
  PLATFORMS="armv7 alpine alpine4k armada370 armada375 armada38x armadaxp comcerto2k monaco"
  ;;
arm5)
  PLATFORMS_ARM5="armv5 88f6281 88f628x"
  ;;
*)
  echo "Unsupported architecture: ${ARCH}"
  exit 1
  ;;
esac

cat <<EOF
package="TorrServer"
version="${PKG_VERSION}"
displayname="TorrServer MatriX"
dsmappname="SYNO.SDS.TorrServer"
arch="${PLATFORMS}"
os_min_ver="7.1-42661"
dsmuidir="ui"
startable="yes"
maintainer="TorrServer"
maintainer_url="https://github.com/YouROK/TorrServer"
distributor="vladlenas"
distributor_url="https://grigi.lt"
description="TorrServer, torrent to http."
description_rus="TorrServer,торрент ссылки в http."
package_icon="PACKAGE_ICON.PNG"
package_icon_256="PACKAGE_ICON_256.PNG"
create_time="${TIMESTAMP}"
extractsize=${PKG_SIZE}
EOF
