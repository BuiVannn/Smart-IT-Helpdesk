#!/bin/sh
set -e
until mc alias set local http://minio:9000 "$S3_ACCESS_KEY" "$S3_SECRET_KEY" 2>/dev/null; do
  echo "Đang chờ MinIO..."; sleep 2
done
mc mb --ignore-existing "local/$S3_BUCKET"
echo "MinIO sẵn sàng, bucket: $S3_BUCKET"
