#!/bin/bash

git clone https://github.com/YouROK/TorrServer.git

type setopt >/dev/null 2>&1
export CGO_ENABLED=0

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

#### linux-am64
GOOS="linux"
GOARCH="amd64"
BIN_FILENAME="${OUTPUT}-${GOOS}-${GOARCH}"
CMD="GOOS=linux GOARCH=${GOARCH} ${GOBIN} build ${BUILD_FLAGS} -o ${BIN_FILENAME} ./cmd"
echo "${CMD}"
eval $CMD || FAILURES="${FAILURES} ${PLATFORM}"

#### linux-386
GOARCH="386"
BIN_FILENAME="${OUTPUT}-${GOOS}-${GOARCH}"
CMD="GOOS=${GOOS} GOARCH=${GOARCH} ${GOBIN} build ${BUILD_FLAGS} -o ${BIN_FILENAME} ./cmd"
echo "${CMD}"
eval $CMD || FAILURES="${FAILURES} ${PLATFORM}"

#### linux-arm64
GOARCH="arm64"
BIN_FILENAME="${OUTPUT}-${GOOS}-${GOARCH}"
CMD="GOOS=${GOOS} GOARCH=${GOARCH} ${GOBIN} build ${BUILD_FLAGS} -o ${BIN_FILENAME} ./cmd"
echo "${CMD}"
eval $CMD || FAILURES="${FAILURES} ${PLATFORM}"

#### linux-arm7
GOARCH="arm"
GOARM="7"
BIN_FILENAME="${OUTPUT}-${GOOS}-${GOARCH}${GOARM}"
CMD="GOOS=${GOOS} GOARCH=${GOARCH} GOARM=${GOARM} ${GOBIN} build ${BUILD_FLAGS} -o ${BIN_FILENAME} ./cmd"
echo "${CMD}"
eval "${CMD}" || FAILURES="${FAILURES} ${GOOS}/${GOARCH}${GOARM}"

#### linux-arm5
GOARCH="arm"
GOARM="5"
BIN_FILENAME="${OUTPUT}-${GOOS}-${GOARCH}${GOARM}"
CMD="GOOS=${GOOS} GOARCH=${GOARCH} GOARM=${GOARM} ${GOBIN} build ${BUILD_FLAGS} -o ${BIN_FILENAME} ./cmd"
echo "${CMD}"
eval "${CMD}" || FAILURES="${FAILURES} ${GOOS}/${GOARCH}${GOARM}"

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
