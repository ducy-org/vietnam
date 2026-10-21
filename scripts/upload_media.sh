#!/usr/bin/env bash
set -euo pipefail

# Upload media to S3 for vietnam.ducy.org
# Excludes WAV files (MP3 versions are used instead)
#
# Prerequisites:
#   - AWS CLI configured (aws configure)
#   - S3 bucket created: aws s3 mb s3://vietnam-ducy-media
#
# Usage:
#   ./scripts/upload_media.sh              # sync all media
#   ./scripts/upload_media.sh --dry-run    # preview changes

BUCKET="s3://vietnam-ducy-media"
MEDIA_DIR="$(cd "$(dirname "$0")/.." && pwd)/public/media"

if [ ! -d "$MEDIA_DIR" ]; then
  echo "ERROR: Media directory not found: $MEDIA_DIR" >&2
  exit 1
fi

EXTRA_ARGS=""
if [[ "${1:-}" == "--dry-run" ]]; then
  EXTRA_ARGS="--dryrun"
  echo "=== DRY RUN ==="
fi

echo "Syncing $MEDIA_DIR → $BUCKET"
echo "Excluding: *.wav, .DS_Store"
echo ""

aws s3 sync "$MEDIA_DIR" "$BUCKET" \
  --exclude "*.wav" \
  --exclude ".DS_Store" \
  --exclude "*/thumbs/.DS_Store" \
  --cache-control "public, max-age=31536000, immutable" \
  --size-only \
  $EXTRA_ARGS

echo ""
echo "Done. Media available at: https://vietnam-ducy-media.s3.amazonaws.com/"
echo "Update MEDIA_URL in site config to point to CloudFront distribution."
