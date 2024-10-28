import os

# Database configuration
DB_CONFIG = {
    'database': os.getenv('PGDATABASE'),
    'user': os.getenv('PGUSER'),
    'password': os.getenv('PGPASSWORD'),
    'host': os.getenv('PGHOST'),
    'port': os.getenv('PGPORT')
}

# SonarCloud API configuration
SONARCLOUD_API_URL = "https://sonarcloud.io/api"
