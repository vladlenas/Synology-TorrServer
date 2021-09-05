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

  echo ">>> Downloading package:"
  mkdir -p ${dest_bin}
  wget --no-verbose -P ${dest_bin} ${src_bin}
}

make_inner_pkg() {
  local tmp_dir=$1
  local dest_dir=$2
  local dest_pkg="$dest_dir/package.tgz"
  local torrserver_bin="dest_bin/TorrServer-linux-${ARCH}"

  echo ">>> Making inner package.tgz"

  mkdir -p ${tmp_dir}/bin
  mkdir -p ${tmp_dir}/config
  cp -a ${torrserver_bin} ${tmp_dir}/bin/TorrServer
  chmod +x ${tmp_dir}/bin/TorrServer
  cp -a src/TorrServer.sc ${tmp_dir}/config/
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

  # copy scripts and icon
  mkdir -p $spk_tmp_dir/conf
  cp -r src/scripts $spk_tmp_dir
  cp -r src/PACKAGE_ICON_256.png $spk_tmp_dir
  cp -r src/PACKAGE_ICON-${DSM}.png $spk_tmp_dir/PACKAGE_ICON.png
  cp -r src/conf/resource $spk_tmp_dir/conf/
  cp -r src/conf/privilege-${DSM} $spk_tmp_dir/conf/privilege
  cp -r src/WIZARD_UIFILES $spk_tmp_dir

  # Generate INFO file
  ./src/INFO.sh ${PKG_VERSION} ${ARCH} ${pkg_size} ${DSM} >"${spk_tmp_dir}"/INFO

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
  rm -rf ./build spk/TorrServer-7.0-${TORRSERVER_VERSION}-arm5.spk
}

main() {
  echo ">>> Building package for DSM-${DSM} ${TORRSERVER_VERSION} ${ARCH}"
  download_torrserver
  make_pkg
}

main
