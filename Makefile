# topstep_quant/Makefile
.PHONY: lint test run docker

# Lint the code with ruff and type-check with mypy
lint:
	ruff . && mypy .

# Run the test suite
test:
	pytest

# Run the trading bot with the default configuration
run:
	python run_bot.py

# Build and run the Docker container for the trading bot
docker:
	docker-compose up --build
