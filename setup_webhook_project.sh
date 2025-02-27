#!/bin/bash
# Script to create FastAPI webhook project structure

# Create directory structure
mkdir -p app/api/routes app/core app/models app/services app/utils tests

# Create __init__.py files
touch app/__init__.py app/api/__init__.py app/api/routes/__init__.py app/core/__init__.py app/models/__init__.py app/services/__init__.py app/utils/__init__.py tests/__init__.py

# Create main application files
touch app/main.py app/api/routes/webhooks.py app/api/dependencies.py app/core/config.py app/core/security.py app/core/logging.py app/models/webhook.py app/services/webhook_handler.py app/utils/helpers.py

# Create test files
touch tests/conftest.py tests/test_webhooks.py

# Create other project files
touch .env .env.example .gitignore requirements.txt README.md run.py

# Generate requirements file
pip freeze > requirements.txt

# Create a basic .gitignore file
echo "venv/
__pycache__/
*.py[cod]
*$py.class
.env
.pytest_cache/
.coverage
htmlcov/" > .gitignore

# Create sample .env files
echo "SECRET_KEY=your_secret_key_here
WEBHOOK_SECRET=your_webhook_secret_here" > .env
echo "SECRET_KEY=example_secret_key
WEBHOOK_SECRET=example_webhook_secret" > .env.example

echo "Project structure created successfully!"