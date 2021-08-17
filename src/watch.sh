#!/bin/sh

PORT="${1}"
PATTERN="${2:-.*\.py$}"

# required
if [ -z "${PORT}" ]; then
    echo "${0}: argument required: port"; exit 1
fi
echo "watching ..."

# actually
fswatch -0r -i "${PATTERN}" -e '.*' . | xargs -0 -n1 -I {} mpremote ${PORT} cp {} :
