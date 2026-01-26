#!/bin/bash

# R2 Upload Script for Berwaz Content
# This script uploads all GIFs to Cloudflare R2

echo "========================================="
echo "  Berwaz R2 Upload Script"
echo "========================================="
echo ""

# Check if rclone is installed
if ! command -v rclone &> /dev/null; then
    echo "Installing rclone..."
    brew install rclone
fi

# Configuration
BUCKET_NAME="berwaz"
CONTENT_DIR="./content"

# Check if content directory exists
if [ ! -d "$CONTENT_DIR" ]; then
    echo "Error: content directory not found!"
    echo "Make sure you're running this from the framevault folder"
    exit 1
fi

echo ""
echo "Before running this script, you need to:"
echo "1. Go to Cloudflare Dashboard → R2 → Manage R2 API Tokens"
echo "2. Create a new API token with Read & Write permissions"
echo "3. Note down: Access Key ID, Secret Access Key, and Account ID"
echo ""
read -p "Do you have your R2 credentials ready? (y/n): " ready

if [ "$ready" != "y" ]; then
    echo "Please get your credentials first, then run this script again."
    exit 1
fi

echo ""
read -p "Enter your Cloudflare Account ID: " ACCOUNT_ID
read -p "Enter your R2 Access Key ID: " ACCESS_KEY
read -s -p "Enter your R2 Secret Access Key: " SECRET_KEY
echo ""

# Configure rclone
echo ""
echo "Configuring rclone..."

mkdir -p ~/.config/rclone

cat > ~/.config/rclone/rclone.conf << EOF
[r2]
type = s3
provider = Cloudflare
access_key_id = $ACCESS_KEY
secret_access_key = $SECRET_KEY
endpoint = https://${ACCOUNT_ID}.r2.cloudflarestorage.com
acl = private
EOF

echo "Configuration complete!"
echo ""
echo "Starting upload... This may take a while (9GB of files)"
echo ""

# Upload with progress
rclone copy "$CONTENT_DIR" "r2:${BUCKET_NAME}/content" --progress --transfers 10

echo ""
echo "========================================="
echo "  Upload Complete!"
echo "========================================="
echo ""
echo "Your files are now at: https://pub-XXXXX.r2.dev/content/"
echo "(Replace XXXXX with your R2 public subdomain)"
echo ""
