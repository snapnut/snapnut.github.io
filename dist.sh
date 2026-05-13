#!/bin/bash

SOURCE_DIR="./public"
BUILD_DIR="dist"

echo "Cleaning old dist"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

echo "Syncing"
cp -r "$SOURCE_DIR/." "$BUILD_DIR/"

echo "Processing"

python _helpdist.py "$BUILD_DIR"

echo "Ready"
