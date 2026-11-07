#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
cd "$root"
export PYTHONDONTWRITEBYTECODE=1
python3 tools/prepare.py
build="$root/.build"
sdk="$build/sdk"
if [[ ! -f "$sdk/toolchain/prospero.mk" ]]; then
  unzip -q -o vendor/archives/sdk.zip -d "$build"
  make -C "$build/sdk-a7685ce8e97ce1f8a4f38253a41d54241c9124f1" -j2 DESTDIR="$sdk" install > "$build/sdk-build.log" 2>&1
fi
http="$build/http"
if [[ ! -f "$http/lib/libmicrohttpd.a" ]]; then
  tar -xzf vendor/archives/libmicrohttpd-1.0.1.tar.gz -C "$build"
  (
    cd "$build/libmicrohttpd-1.0.1"
    export CC="$sdk/bin/prospero-clang" AR="$sdk/bin/prospero-ar" NM="$sdk/bin/prospero-nm" RANLIB="$sdk/bin/prospero-ranlib"
    ./configure --host=x86_64-pc-freebsd12 --disable-shared --enable-static --disable-curl --disable-examples --disable-https --prefix="$http"
    make -j2
    make install
  ) > "$build/http-build.log" 2>&1
fi
vendor="$root/vendor/installer"
"$sdk/bin/prospero-clang" -O2 -Wall -Wextra -Werror -Wno-unused-parameter -Wno-unreachable-code-generic-assoc \
  -I"$build" -Isrc -I"$vendor/src" -I"$vendor/third_party/cjson" -I"$http/include" \
  src/main.c src/image.c "$vendor/src/crypto/sha256.c" "$vendor/src/titles.c" \
  "$vendor/src/install/install.c" "$vendor/src/install/installed.c" "$vendor/src/install/loopback.c" \
  "$vendor/third_party/cjson/cJSON.c" "$build/assets.S" "$http/lib/libmicrohttpd.a" \
  -lpthread -lSceAppInstUtil -o dist/Y2JB-installer.elf
"$sdk/bin/prospero-strip" dist/Y2JB-installer.elf
python3 tools/verify.py
