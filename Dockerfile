# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.7.1 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install "poetry==$POETRY_VERSION"

# Copy only requirements first to leverage Docker cache
COPY pyproject.toml poetry.lock* ./

# Install project dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy project files
COPY retail_agency/ ./retail_agency/
COPY requirements.txt .

# Create necessary directories
RUN mkdir -p inventory_results

# Create example env file
RUN echo "# OpenAI\n\
OPENAI_API_KEY=your-key-here\n\
\n\
# Slack Credentials\n\
SLACK_APP_ID=your-app-id\n\
SLACK_BOT_TOKEN=your-bot-token\n\
SLACK_APP_TOKEN=your-app-token\n\
\n\
# Notion Credentials\n\
NOTION_TOKEN=your-token\n\
NOTION_DATABASE_ID=your-database-id\n\
\n\
# Database Connection\n\
CLOUD_DB_HOST=your-host\n\
CLOUD_DB_PORT=5432\n\
CLOUD_DB_USER=your-user\n\
CLOUD_DB_PASS=your-password\n\
CLOUD_DB_NAME=your-db-name\n\
CLOUD_SCHEMA=your-schema\n" > retail_agency/.env.example

# Create a non-root user
RUN adduser --disabled-password --gecos "" appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["python", "-m", "retail_agency.app"] 