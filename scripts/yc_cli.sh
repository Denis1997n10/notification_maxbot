#!/usr/bin/env bash

# WSL can execute a Windows yc installation, but it does not resolve yc.exe as yc.
if ! command -v yc >/dev/null 2>&1 && command -v yc.exe >/dev/null 2>&1; then
  yc() {
    yc.exe "$@"
  }
  export -f yc
fi

if ! command -v yc >/dev/null 2>&1; then
  for candidate in /mnt/c/Users/*/yandex-cloud/bin/yc.exe; do
    if [[ -x "$candidate" ]]; then
      YC_INTEROP_BINARY="$candidate"
      export YC_INTEROP_BINARY
      yc() {
        "$YC_INTEROP_BINARY" "$@"
      }
      export -f yc
      break
    fi
  done
fi
