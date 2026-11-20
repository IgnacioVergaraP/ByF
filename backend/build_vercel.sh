#!/usr/bin/env bash
set -euo pipefail

npm --prefix frontend ci --no-audit --no-fund
npm --prefix frontend run build -- --output-path ../backend/web

mkdir -p backend/tessdata
for archivo in eng.traineddata spa.traineddata LICENSE; do
    curl --fail --silent --show-error --location --retry 3 \
        "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/${archivo}" \
        --output "backend/tessdata/${archivo}"
done
