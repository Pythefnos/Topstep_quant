# Production Docker image for TopstepQuant trading bot
# Uses multi-stage build to ensure a clean, small runtime image.

# Stage 1: Build dependencies using Poetry
FROM python:3.11-slim AS builder

# Install system dependencies (if any needed for science libs, e.g., numpy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_VERSION=1.5.1
RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app

# Copy project files (pyproject and lock for deps, and the app code)
COPY pyproject.toml poetry.lock /app/
# Install project dependencies (without dev) in the builder stage
RUN poetry config virtualenvs.create false && poetry install --only main --no-interaction --no-ansi

# Now copy the actual application code
COPY topstep_quant/ /app/topstep_quant/

# (Optional) Run tests or lint in build stage if needed (could be done in CI instead)

# Stage 2: Runtime image
FROM python:3.11-slim AS runtime

# Create a non-root user for running the app, for security
RUN useradd --user-group --create-home --no-log-init --shell /bin/bash appuser

# Copy dependencies from builder to runtime (uses the same Python version)
COPY --from=builder /usr/local/lib/python3.11/ /usr/local/lib/python3.11/

# Copy our application code
COPY --from=builder /app/topstep_quant/ /app/topstep_quant/

# Ensure ownership by non-root user
RUN chown -R appuser:appuser /app

WORKDIR /app
USER appuser

# Expose the Prometheus metrics port
EXPOSE 8000

# Entrypoint/Command: run the trading bot
# Using Poetry isn't necessary at runtime since we installed libs to system site-packages
CMD ["python", "-m", "topstep_quant.bot"]
