#!/bin/sh
# Per-user, versioned installation. Never opens or removes user data/saves.
set -eu
source_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd -- "$source_dir"
sha256sum --check --status payload.sha256
version='@VERSION@'
destination=${1:-"$HOME/.local/opt/poliscope/$version"}
case "$destination" in *'
'*|*"$(printf '\r')"*) echo 'Installation path contains a line break.' >&2; exit 1;; esac
case "$destination" in /*) ;; *) echo 'Choose an absolute installation path.' >&2; exit 1;; esac
mkdir -p -- "$(dirname -- "$destination")"
# Exclusive directory creation protects existing installations, including symlinks.
mkdir -- "$destination"
cp -R -- "$source_dir/app/." "$destination/"
"$destination/resources/poliscope-engine/poliscope-engine" --self-test
# Non-fatal launch guidance; see docs/native_distribution.md for the remedy.
sh "$source_dir/sandbox-notice.sh" /proc/sys/kernel/apparmor_restrict_unprivileged_userns 1
sh "$source_dir/sandbox-notice.sh" /proc/sys/kernel/unprivileged_userns_clone 0
applications="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p -- "$applications"
# Desktop Entry quoted argument escaping (not shell interpolation).
escaped=$(printf '%s' "$destination/poliscope" | sed 's/\\/\\\\/g; s/"/\\"/g; s/`/\\`/g; s/\$/\\$/g; s/%/%%/g')
temporary=$(mktemp "$applications/poliscope.XXXXXX")
printf '[Desktop Entry]\nType=Application\nName=Poliscope\nExec="%s"\nIcon=poliscope\nTerminal=false\nCategories=Education;\n' "$escaped" > "$temporary"
mv -f -- "$temporary" "$applications/poliscope.desktop"
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
mkdir -p -- "$icons"
cp -- "$source_dir/icons/poliscope-256.png" "$icons/poliscope.png"
printf 'Installed %s. Previous versions and user data are retained.\n' "$destination"
