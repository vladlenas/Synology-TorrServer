#!/bin/bash

set -e

PKG_VERSION="${1:?Package version is required}"
ARCH="${2:?Architecture is required}"
PKG_SIZE="${3:?Package size is required}"

TIMESTAMP="$(date -u +%Y%m%d-%H:%M:%S)"

# TorrServer requires DSM 7.3 or newer.
OS_MIN_VER="7.3-81180"

case "${ARCH}" in

    amd64)
        PLATFORMS="x86_64 apollolake avoton braswell broadwell broadwellnk broadwellnkv2 broadwellntbap bromolow denverton epyc7002 geminilake grantley kvmx64 purley r1000 v1000"
        ;;

    arm64)
        PLATFORMS="aarch64 armv8 rtd1296 rtd1619b armada37xx"
        ;;

    arm7)
        PLATFORMS="alpine alpine4k armada38x monaco"
        ;;

    *)
        echo "ERROR: Unsupported architecture: ${ARCH}" >&2
        echo "Supported architectures: amd64, arm64, arm7" >&2
        exit 1
        ;;

esac

cat <<EOF
package="TorrServer"
version="${PKG_VERSION}"
displayname="TorrServer"
dsmappname="SYNO.SDS.TorrServer"
arch="${PLATFORMS}"
os_min_ver="${OS_MIN_VER}"
dsmuidir="ui"
startable="yes"
maintainer="TorrServer"
maintainer_url="https://github.com/YouROK/TorrServer"
distributor="vladlenas"
distributor_url="https://grigi.lt"
description="TorrServer, torrent to http."
description_rus="TorrServer, торрент ссылки в http."
package_icon="PACKAGE_ICON.PNG"
package_icon_256="PACKAGE_ICON_256.PNG"
create_time="${TIMESTAMP}"
extractsize=${PKG_SIZE}
EOF
