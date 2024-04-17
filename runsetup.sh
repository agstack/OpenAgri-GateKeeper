#!/bin/bash

# Run initial_setup file
echo "Running initial setup"
python manage.py initial_setup

# Start the Django app
echo "Starting Django server..."
exec python3 run_waitress.py
