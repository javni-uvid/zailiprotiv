#!/bin/sh
# The container's entry (Dockerfile): as root only long enough to give the volumes to the service's user, then the
# command runs as that user. A container started as another user (docker run --user) runs the command as it is.
set -e
if [ "$(id -u)" = 0 ]; then
    mkdir -p /data /tmp/uzivo
    chown -R uzivo:uzivo /data /tmp/uzivo 2>/dev/null || true
    export HOME=/home/uzivo
    exec setpriv --reuid uzivo --regid uzivo --init-groups "$@"
fi
exec "$@"
