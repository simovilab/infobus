#!/bin/bash
# WebSocket Demo Setup Script
# 
# This script automates the setup and running of the WebSocket demo.
# Usage: ./demos/websocket/run_trip_demo.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ...existing code from run_trip_demo.sh...
