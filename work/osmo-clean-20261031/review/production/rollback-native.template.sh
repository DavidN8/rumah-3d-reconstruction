#!/usr/bin/env bash
set -euo pipefail
TASK=__TASK__
RELEASE=__RELEASE__
PREVIOUS=__PREVIOUS__
exec 9>/var/lib/vz/rumah-deploy/native-release.lock
flock -n 9
test "$(pct exec 710 -- readlink -f /var/www/rumah/current)" = "$RELEASE"
pct exec 710 -- test -d "$PREVIOUS"
NEXT=/var/www/rumah/current.public-rollback-$$
pct exec 710 -- ln -s "$PREVIOUS" "$NEXT"
pct exec 710 -- mv -Tf "$NEXT" /var/www/rumah/current
date -Is > "$TASK/public-verification-rollback.done"
printf 'Previous release restored after public verification failure.\n'
