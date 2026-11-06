#!/bin/sh
# SPDX-FileCopyrightText: 2026 Netbeheer Nederland
# SPDX-License-Identifier: Apache-2.0
#
# Runs at container start (the nginx image executes /docker-entrypoint.d/*.sh)
# and writes the HMI's runtime configuration from the environment:
#
#   BFF_HOST   BFF host as the user's browser reaches it (not a container name)
#   BFF_PORT   BFF port
#   LOG_LEVEL  what the HMI logs in the browser console (src/utils/log.js),
#              and nginx's error log level (spec 0008)
#
# Unset or empty variables are left out, so the build-time (VITE_BFF_*,
# VITE_LOG_LEVEL) or built-in defaults apply. See src/config.js.
#
# RTI_CONFIG_JS and RTI_NGINX_CONF move the two files it writes (tests).
set -eu

out=${RTI_CONFIG_JS:-/usr/share/nginx/html/config.js}
nginx_conf=${RTI_NGINX_CONF:-/etc/nginx/nginx.conf}

# A JavaScript string literal: escape backslashes and double quotes.
js_string() {
  printf '"%s"' "$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')"
}

# nginx's error log level for a LOG_LEVEL, with the names and fallback of
# resolve_log_level: nginx's debug needs a debug build, so debug is info;
# info is notice (nginx's default); unknown is info, so notice.
nginx_level() {
  name=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
  case "$name" in
    debug|trace|notset) echo info ;;
    info) echo notice ;;
    warning|warn) echo warn ;;
    error|critical|fatal) echo error ;;
    ''|*[!0-9]*) echo notice ;;
    *)
      if [ "$name" -le 10 ]; then echo info
      elif [ "$name" -le 20 ]; then echo notice
      elif [ "$name" -le 30 ]; then echo warn
      else echo error
      fi ;;
  esac
}

entries=""
if [ -n "${BFF_HOST:-}" ]; then
  entries="bffHost: $(js_string "$BFF_HOST")"
fi
if [ -n "${BFF_PORT:-}" ]; then
  entries="${entries:+$entries, }bffPort: $(js_string "$BFF_PORT")"
fi
if [ -n "${LOG_LEVEL:-}" ]; then
  entries="${entries:+$entries, }logLevel: $(js_string "$LOG_LEVEL")"
fi

printf 'window.RTI_CONFIG = { %s };\n' "$entries" > "$out"
echo "40-rti-config.sh: wrote $out: { $entries }"

# nginx's error log, at main level, so it also takes nginx's own messages at
# start (conf.d/ is read inside http, which inherits main's). Each start
# begins from the image's nginx.conf, kept on the first, so an unset
# LOG_LEVEL restores its error_log. The access log stays on at every level.
nginx_orig="$nginx_conf.rti-orig"
[ -f "$nginx_orig" ] || cp "$nginx_conf" "$nginx_orig"
if [ -n "${LOG_LEVEL:-}" ]; then
  level=$(nginx_level "$LOG_LEVEL")
  line="error_log /var/log/nginx/error.log $level;"
  if grep -q '^error_log[[:space:]]' "$nginx_orig"; then
    sed "s|^error_log[[:space:]].*|$line|" "$nginx_orig" > "$nginx_conf"
  else
    { cat "$nginx_orig"; echo "$line"; } > "$nginx_conf"
  fi
  echo "40-rti-config.sh: nginx error log at $level ($nginx_conf)"
else
  cp "$nginx_orig" "$nginx_conf"
fi
