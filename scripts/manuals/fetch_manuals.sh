#!/usr/bin/env bash
# Mirror official user manuals for E4 (knowledge probe) and the benchmark's manual condition.
# Each app goes to $MANUALS/<app>/ with SOURCE.json (url, fetch date, version note).
# Photoshop help is Adobe-copyrighted: mirrored for internal question generation only, never redistributed.
# Usage: scripts/manuals/fetch_manuals.sh [app ...]   (default: all)
set -euo pipefail
MANUALS=${VE_MANUALS:-/shared/dedicated-fsx-data-repo-training-phx-gl-eks-us-west-2/home/jwanyang/visual_effect_data/manuals}
declare -A URL=(
  [gimp]="https://docs.gimp.org/2.10/en/"                       # GIMP 2.10, matches OSWorld/OSExpert (2.10.30)
  [darktable]="https://docs.darktable.org/usermanual/5.6/en/"   # stable redirects here; pinned
  [krita]="https://docs.krita.org/en/"
  [photoshop]="https://helpx.adobe.com/photoshop/user-guide.html"
)
OPENTOONZ_ZIP="https://opentoonz.readthedocs.io/_/downloads/en/latest/htmlzip/"
apps=("$@"); [ ${#apps[@]} -gt 0 ] || apps=(gimp darktable krita opentoonz photoshop)
for app in "${apps[@]}"; do
  dst="$MANUALS/$app"; mkdir -p "$dst"
  if [ -f "$dst/SOURCE.json" ]; then echo "$app already fetched"; continue; fi
  echo "fetching $app"
  if [ "$app" = opentoonz ]; then
    curl -sL "$OPENTOONZ_ZIP" -o "$dst/opentoonz-htmlzip.zip" && (cd "$dst" && unzip -q -o opentoonz-htmlzip.zip)
    src=$OPENTOONZ_ZIP
  else
    src=${URL[$app]}
    host=$(echo "$src" | awk -F/ '{print $3}'); prefix=/$(echo "$src" | cut -d/ -f4- | sed 's|[^/]*\.html$||')
    [ "$app" = photoshop ] && prefix=/photoshop/
    # Stay inside the manual's path; keep page images (figures are part of the manual).
    wget -q -e robots=off --recursive --level=inf --no-parent --page-requisites --adjust-extension --convert-links \
      --domains "$host" --include-directories "$prefix,/images,/_images,/_static" --wait=0.1 --random-wait \
      --reject-regex '\?|/(search|genindex)' -P "$dst" "$src" || true   # wget returns 8 on any 404; pages still saved
  fi
  pages=$(find "$dst" -name '*.html' | wc -l)
  printf '{"app":"%s","url":"%s","fetched":"%s","html_pages":%s}\n' "$app" "$src" "$(date -u +%FT%TZ)" "$pages" > "$dst/SOURCE.json"
  echo "$app: $pages pages"
done
