#!/bin/bash

PKG_VERSION=$1
ARCH=$2
PKG_SIZE=$3

TIMESTAMP=$(date -u +%Y%m%d-%H:%M:%S)

case $ARCH in
amd64)
  PLATFORMS="apollolake avoton braswell broadwell broadwellnk bromolow cedarview denverton dockerx64 geminilake grantley purley kvmx64 v1000 x86 x86_64"
  ;;
386)
  PLATFORMS="evansport apollolake avoton braswell broadwell broadwellnk bromolow cedarview denverton dockerx64 geminilake grantley purley kvmx64 v1000 x86 x86_64"
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
displayname="TorrServer"
smappname="SYNO.SDS.TorrServer"
arch="${PLATFORMS}"
firmware="6.0-0000"
dsmuidir="ui"
startable="yes"
maintainer="YouROK"
maintainer_url="https://github.com/YouROK"
distributor="vladlenas"
distributor_url="https://github.com/vladlenas/Synology-TorrServer/releases"
description="TorrServer, torrent to http."
description_rus="TorrServer,торрент ссылки в http"
package_icon="PACKAGE_ICON.PNG"
package_icon_256="PACKAGE_ICON_256.PNG"
create_time="${TIMESTAMP}"
extractsize=${PKG_SIZE}
EOF
