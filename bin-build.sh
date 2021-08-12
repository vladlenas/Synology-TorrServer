#!/bin/bash

git clone https://github.com/YouROK/TorrServer.git

PLATFORMS=(
  'linux/amd64'
  'linux/386'
  'linux/arm64'
  'linux/arm7'
  'linux/arm5'
)

type setopt >/dev/null 2>&1
export CGO_ENABLED=0

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

GOBIN="go"
$GOBIN version

LDFLAGS="'-s -w'"
FAILURES=""
ROOT=${PWD}
OUTPUT="${ROOT}/dest_bin/TorrServer"

#### Build web
echo "Build web"
cd ${ROOT}/TorrServer
$GOBIN run gen_web.go

#### Build server
echo "Build server"
rm -fr "${ROOT}/dest_bin"
cd "${ROOT}/TorrServer/server" || exit 1
$GOBIN clean -i -r -cache #--modcache
$GOBIN mod tidy
$GOBIN mod download

BUILD_FLAGS="-ldflags=${LDFLAGS}"

for PLATFORM in "${PLATFORMS[@]}"; do
  GOOS=${PLATFORM%/*}
  GOARCH=${PLATFORM#*/}
  set_goarm "$GOARCH"
  BIN_FILENAME="${OUTPUT}-${GOOS}-${GOARCH}${GOARM}"
  CMD="GOOS=${GOOS} GOARCH=${GOARCH} ${GO_ARM} ${GO_MIPS} ${GOBIN} build ${BUILD_FLAGS} -o ${BIN_FILENAME} ./cmd"
  echo "${CMD}"
  eval "$CMD" || FAILURES="${FAILURES} ${GOOS}/${GOARCH}${GOARM}"
  CMD="upx ${BIN_FILENAME}";
  echo "compress with ${CMD}"
  eval "$CMD"
done

# eval errors
if [[ "${FAILURES}" != "" ]]; then
  echo ""
  echo "failed on: ${FAILURES}"
  exit 1
fi

#### build .spk
cd ${ROOT}
make
exit 0
