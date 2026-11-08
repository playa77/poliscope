#!/bin/sh
# Non-fatal sandbox restriction notice for Linux installs.
# Usage: sh sandbox-notice.sh USERNS_SYSCTL_PATH RESTRICTED_VALUE
# Both arguments are parameters so tests (and other kernels) can exercise every
# branch: restricted, unrestricted and absent sysctl paths print nothing extra
# on unrestricted/absent systems.
set -eu
if [ "$#" -ne 2 ]; then
    echo 'Usage: sh sandbox-notice.sh USERNS_SYSCTL_PATH RESTRICTED_VALUE' >&2
    exit 2
fi
if [ -f "$1" ] && [ "$(cat -- "$1")" = "$2" ]; then
    printf '%s\n' \
      'NOTE: This system restricts the sandbox mechanism (user namespaces or' \
      'AppArmor policy). The packaged application refuses to launch without a' \
      'sandbox, so the desktop launcher may silently open nothing. If that' \
      'happens, configure the user-namespace AppArmor profile for this' \
      'installation as described in the distribution guide, or ask an' \
      'administrator to set the bundled chrome-sandbox to root-owned mode' \
      '4755. Never run the app unsandboxed.'
fi
