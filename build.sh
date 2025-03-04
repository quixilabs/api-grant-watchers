#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting build process..."

# Activate virtual environment if it exists, create if it doesn't
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Run database migrations
echo "Running database migrations..."
python apply_migrations.py

# Start the application
echo "Starting the application on port 8020..."
python run.py 