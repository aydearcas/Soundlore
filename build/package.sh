#!/bin/sh
# Copy the Soundlore project to the output area for delivery
set -e
cd "$(dirname "$0")/.."
OUT=/mnt/user-data/outputs/soundlore
rm -rf "$OUT"; mkdir -p "$OUT/build" "$OUT/viewer"
cp -r README.md concepts genres sources "$OUT"/
cp build/*.py build/*.sh build/*.json build/soundlore.ttl build/soundlore.jsonld "$OUT/build/"
cp viewer/*.html viewer/*.json viewer/soundlore.ttl viewer/soundlore.jsonld "$OUT/viewer/"
find "$OUT" -type f | sed "s|$OUT/||" | sort
