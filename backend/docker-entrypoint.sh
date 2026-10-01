#!/bin/sh
# Uruchamia aplikacje jako PUID:PGID (domyslnie 1000:1000), zeby pliki w /data mialy wlasciciela
# zgodnego z uzytkownikiem hosta (np. przy montowaniu katalogu zamiast wolumenu).
# Start jako root jest potrzebny tylko do chown /data; aplikacja nigdy nie dziala jako root.
set -eu

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

if [ "$(id -u)" != "0" ]; then
  # Kontener uruchomiony juz jako nie-root (np. docker run --user) - PUID/PGID nie maja zastosowania.
  exec "$@"
fi

case "$PUID:$PGID" in
  *[!0-9:]* | :* | *:)
    echo "calico: PUID and PGID must be numbers (got PUID=$PUID, PGID=$PGID)" >&2
    exit 1
    ;;
esac
if [ "$PUID" -eq 0 ] || [ "$PGID" -eq 0 ]; then
  echo "calico: refusing to run as root - set PUID and PGID to a non-zero user and group id" >&2
  exit 1
fi

if [ -n "$(find /data \( ! -user "$PUID" -o ! -group "$PGID" \) -print -quit)" ]; then
  echo "calico: setting owner of /data to $PUID:$PGID"
  if ! chown -R "$PUID:$PGID" /data; then
    echo "calico: cannot change owner of /data - set PUID/PGID to the owner of the mounted directory or fix its permissions" >&2
    exit 1
  fi
fi

exec setpriv --reuid="$PUID" --regid="$PGID" --clear-groups "$@"
