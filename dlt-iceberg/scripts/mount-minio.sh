#!/bin/bash

# Script to mount MinIO bucket as local directory using s3fs
# This allows you to browse MinIO files in VS Code Explorer

echo "=== MinIO Mount Script for VS Code ==="
echo ""

# Check if s3fs is installed
if ! command -v s3fs &> /dev/null; then
    echo "❌ s3fs not found. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install s3fs
    else
        sudo apt-get install s3fs
    fi
fi

# Create mount point
MOUNT_DIR="$HOME/minio-mount"
mkdir -p "$MOUNT_DIR"

# MinIO credentials
echo "minioadmin:minioadmin123" > /tmp/minio-passwd
chmod 600 /tmp/minio-passwd

# Mount MinIO
echo "📂 Mounting MinIO to $MOUNT_DIR ..."
echo "   URL: http://localhost:9000"
echo ""

s3fs iceberg-data "$MOUNT_DIR" \
    -o passwd_file=/tmp/minio-passwd \
    -o url=http://localhost:9000 \
    -o use_path_request_style \
    -o allow_other \
    -o no_check_certificate

if [ $? -eq 0 ]; then
    echo "✅ MinIO mounted successfully!"
    echo ""
    echo "📂 Access files in VS Code: $MOUNT_DIR"
    echo "   File > Open Folder > Select: $MOUNT_DIR"
    echo ""
    echo "To unmount later:"
    echo "   umount $MOUNT_DIR"
else
    echo "❌ Failed to mount MinIO"
    exit 1
fi

# Cleanup
rm -f /tmp/minio-passwd
