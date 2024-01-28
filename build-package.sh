#!/bin/bash

set -e

TORRSERVER_VERSION=$1
ARCH=$2
PKG_VERSION=$3
DSM=$4

download_torrserver() {
  local base_url="https://github.com/YouROK/TorrServer/releases/download/${TORRSERVER_VERSION}"
  local bin_name="TorrServer-linux-${ARCH}"
  local src_bin="${base_url}/${bin_name}"
  local dest_bin="dest_bin"

  if [[ -f ${dest_bin}/TorrServer-linux-${ARCH} ]]; then
    echo ">>> Binaries already exist: ${bin_name}"
    return
  fi

  echo ">>> Downloading TorrServer-linux-${ARCH}:"
  wget -q -P ${dest_bin} ${src_bin}
}

download_ffprobe() {
  local tmp_download=$1
  local ffprobe_url="https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v4.4.1/ffprobe-6.1-linux-32.zip"
  local dest_bin="dest_bin"

  if [[ -f dest_bin/ffprobe ]]; then
    echo ">>> Binaries already exist: ffprobe"
    return
  fi

  echo ">>> Downloading ffprobe:"
  mkdir -p ${dest_bin}
  wget -q -O ${tmp_downloads}/ffprob.zip ${ffprobe_url}
  unzip -q ${tmp_downloads}/ffprob.zip -d dest_bin
}

make_inner_pkg() {
  local tmp_dir=$1
  local dest_dir=$2
  local dest_pkg="$dest_dir/package.tgz"
  local torrserver_bin="dest_bin/TorrServer-linux-${ARCH}"
  local ffprobe_bin="dest_bin/ffprobe"

  echo ">>> Making inner package.tgz"

  mkdir -p ${tmp_dir}/bin
  cp -a ${torrserver_bin} ${tmp_dir}/bin/TorrServer
  cp -a ${ffprobe_bin} ${tmp_dir}/bin
  chmod +x ${tmp_dir}/bin/*
  cp -r src/ui ${tmp_dir}

  pkg_size=$(du -sk "${tmp_dir}" | awk '{print $1}')
  echo "${pkg_size}" >>"$dest_dir/extractsize_tmp"

  ls --color=no $tmp_dir | tar -cJf $dest_pkg -C "$tmp_dir" -T /dev/stdin
}

make_spk() {
  local spk_tmp_dir=$1
  local spk_dest_dir="./spk"
  local pkg_size=$(cat ${spk_tmp_dir}/extractsize_tmp)
  local spk_filename="TorrServer-${DSM}-${TORRSERVER_VERSION}-${ARCH}.spk"

  echo ">>> Making spk: ${spk_filename}"
  mkdir -p ${spk_dest_dir}
  rm "${spk_tmp_dir}/extractsize_tmp"

  cp -r src/scripts $spk_tmp_dir
  cp -r src/PACKAGE_ICON_256.PNG $spk_tmp_dir
  cp -r src/PACKAGE_ICON.PNG $spk_tmp_dir
  cp -r src/conf/ $spk_tmp_dir
  cp -r src/WIZARD_UIFILES $spk_tmp_dir

  ./src/INFO.sh ${PKG_VERSION} ${ARCH} ${pkg_size} >"${spk_tmp_dir}"/INFO

  tar -cf "${spk_dest_dir}/${spk_filename}" -C "${spk_tmp_dir}" $(ls ${spk_tmp_dir})
}

make_pkg() {
  mkdir -p ./build
  local pkg_temp_dir=$(mktemp -d -p ./build)
  local spk_temp_dir=$(mktemp -d -p ./build)

  make_inner_pkg ${pkg_temp_dir} ${spk_temp_dir}
  make_spk ${spk_temp_dir}
  echo ">>> Done"
  echo ""
}

main() {
  echo ">>> Building package for DSM-${DSM} ${TORRSERVER_VERSION} ${ARCH}"
  download_ffprobe
  download_torrserver
  make_pkg
}

main
