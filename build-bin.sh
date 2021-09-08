#!/bin/bash

ROOT=${PWD}
SRC_DIR="TorrServer"
DEST_BIN="${ROOT}/dest_bin"
SRC_URL="https://github.com/YouROK/TorrServer.git"
GOBIN="go"
LDFLAGS="'-s -w'"
FAILURES=""
OUTPUT="${DEST_BIN}/TorrServer"
BUILD_FLAGS="-ldflags=${LDFLAGS}"
PLATFORMS=(
  'linux/amd64'
  'linux/386'
  'linux/arm64'
  'linux/arm7'
  'linux/arm5'
)

{
    if [ -d "${SRC_DIR}" ]; then
        exit=0
    else
        git clone -b new-engine ${SRC_URL}
    fi
}

type setopt >/dev/null 2>&1
#export CGO_ENABLED=0

set_goarm() {
  if [[ "$1" =~ arm([5,7]) ]]; then
    GOARCH="arm"
    GOARM="${BASH_REMATCH[1]}"
    GO_ARM="GOARM=${GOARM}"
  else
    GOARM=""
    GO_ARM=""
  fi
}

$GOBIN version

#### Build web
echo "Build web"
cd ${ROOT}/${SRC_DIR}
$GOBIN run gen_web.go

#### Build server
echo "Build server"
rm -fr "${DEST_BIN}"
cd "${ROOT}/${SRC_DIR}/server" || exit 1
$GOBIN clean -i -r -cache #--modcache
$GOBIN mod tidy
$GOBIN mod download

for PLATFORM in "${PLATFORMS[@]}"; do
  GOOS=${PLATFORM%/*}
  GOARCH=${PLATFORM#*/}
  set_goarm "$GOARCH"
  BIN_FILENAME="${OUTPUT}-${GOOS}-${GOARCH}${GOARM}"
  CMD="GOOS=${GOOS} GOARCH=${GOARCH} ${GO_ARM} ${GO_MIPS} ${GOBIN} build ${BUILD_FLAGS} -o ${BIN_FILENAME} ./cmd"
  echo "${CMD}"
  eval "$CMD" || FAILURES="${FAILURES} ${GOOS}/${GOARCH}${GOARM}"
  #CMD="upx ${BIN_FILENAME}";
  CMD="../upx ${BIN_FILENAME}";
  echo "compress with ${CMD}"
  eval "$CMD"
done

# eval errors
if [[ "${FAILURES}" != "" ]]; then
  echo ""
  echo "failed on: ${FAILURES}"
  exit 1
fi
