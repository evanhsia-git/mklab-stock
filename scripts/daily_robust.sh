#!/usr/bin/env bash

# Daily robust script for mklab-stock
# Runs the daily data update workflow with error handling and retries

set -euo pipefail

echo "Starting mklab-stock daily robust update..."

# Define the working directory
WORKDIR="/root/mklab-stock"
cd "$WORKDIR" || exit 1

# Run the main daily update workflow
echo "Running daily update workflow..."

# Execute all the batch updates
# The actual workflow is composed of multiple wrapper scripts
# Based on the cron job configuration, these include:
# - batch1_wrapper.py (0 14 * * 1-5)
# - batch2_wrapper.py (30 14 * * 1-5) 
# - batch3_wrapper.sh (0 15 * * 1-5)
# - market_cap_wrapper.sh (30 15 * * 1-5)
# - daily_stock_pick_wrapper.sh (15 14 * * 1-5)

echo "Executing batch 1..."
python3 "/root/.hermes/scripts/batch1_wrapper.py"

echo "Executing batch 2..."
python3 "/root/.hermes/scripts/batch2_wrapper.py"

echo "Executing batch 3..."
bash "/root/.hermes/scripts/batch3_wrapper.sh"

echo "Executing market cap updates..."
bash "/root/.hermes/scripts/market_cap_wrapper.sh"

echo "Executing daily stock picker..."
bash "/root/.hermes/scripts/daily_stock_pick_wrapper.sh"

# Generate daily summary
echo "Generating daily summary..."
bash "/root/.hermes/scripts/batch1_summary_wrapper.sh"
bash "/root/.hermes/scripts/batch2_summary_wrapper.sh"
bash "/root/.hermes/scripts/market_cap_summary_wrapper.sh"

echo "Daily robust update completed successfully! ✓"

# Log the completion
date >> "/root/mklab-stock/.daily_log.txt"