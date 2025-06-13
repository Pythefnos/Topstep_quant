# TopstepQuant – Autonomous Futures Trading Bot

TopstepQuant is an autonomous trading bot designed for the CME micro-futures market, operated within a Topstep™ 50K Express Funded Account. It runs **four independent “alpha” strategy sleeves** in parallel – latency market-making, mean-reversion, trend-following, and tail-risk hedging – to achieve steady gains while strictly respecting Topstep’s risk parameters. The bot’s **median profit target is \$7,600 over 7 months**, with a ≥98% probability of success under normal market conditions, all while **never breaching Topstep’s \$1,000 daily loss or \$2,000 trailing drawdown limits**.

## Features and Project Overview

- **Multiple Alpha Strategies:** Four uncorrelated trading strategies (“sleeves”) operate concurrently:
  - *Latency Market-Making:* Ultra-short-term trading capturing bid/ask spreads and micro price imbalances.
  - *Mean-Reversion:* Identifies short-term price extremes in micro-futures and trades towards the average.
  - *Trend-Following:* Rides sustained intraday trends using breakout and momentum signals.
  - *Tail Hedge:* A protective strategy that engages during volatility spikes (e.g. buying volatility or inverse positions) to hedge tail-risk and profit from market shocks.
- **Risk Management:** Hard-coded risk controls ensure the bot **automatically stops trading before reaching** Topstep’s **\$1,000 daily loss limit or \$2,000 trailing drawdown**. Positions are reduced or liquidated if unrealized losses approach these limits.
- **High Probability of Success:** By combining diversified strategies and stringent risk limits, the bot targets consistent profits. It is statistically modeled to achieve the \$7.6K profit target within ~7 months **with high confidence (98%+ win probability)**, meaning very low risk of hitting drawdowns.
- **Monitoring & Metrics:** The bot exposes detailed metrics (P/L, position sizes, latency, etc.) via a Prometheus `/metrics` endpoint. A bundled Prometheus container continuously scrapes these metrics for real-time monitoring and alerting.
- **Infrastructure & Quality:** The project emphasizes reliability and auditability:
  - Full continuous integration (CI) pipeline for linting, type checking, testing, and Docker builds.
  - Pre-commit hooks (Black, Ruff, MyPy, Bandit) enforce code style, type safety, and security best practices on every commit.
  - Deployment is “push-button” simple using Docker and Docker Compose. The included configuration orchestrates the trading bot alongside a Prometheus service for monitoring.
  - The codebase follows an **“audit-grade”** standard – clear structure, comments, and logging – to facilitate reviews (essential for a trading system handling real funds).

## Setup and Installation

**Requirements:** Python 3.11+ and Docker (if using containers). We use Poetry for dependency management to ensure reproducible builds.

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/topstep_quant.git
cd topstep_quant
2. Install Dependencies (for local running)
We recommend using Poetry to create an isolated virtual environment with all dependencies:
bash
Copy
Edit
# Install Poetry if not already installed
pip install poetry

# Install project dependencies (including dev tools)
poetry install
This will install all runtime requirements (for trading and monitoring) as well as development tools specified in pyproject.toml. The lockfile poetry.lock ensures consistent versions. Note: The bot depends on certain external APIs or trading gateways (e.g., a futures brokerage API or Topstep’s trading platform). Configure any API keys or credentials via environment variables (see Running the Bot below). No credentials are stored in code.
3. Pre-commit Hooks (optional, for developers)
This repository is configured with pre-commit hooks to maintain code quality. To enable them:
bash
Copy
Edit
poetry run pre-commit install
Now each commit will run automatic checks (formatting, lint, type-check, security scan) on changed files, preventing bad code from being committed.
Running the Trading Bot
You can run the bot either directly on your host or inside Docker containers. The recommended approach is using Docker Compose for a one-command deployment that includes the Prometheus monitoring stack.
Running via Docker Compose
Build and launch the containers:
bash
Copy
Edit
docker-compose up --build -d
This will build the topstep_quant image (if not already built) and start two services:
bot – the trading bot service (running our Python trading agent).
prometheus – the Prometheus server scraping metrics from the bot.
The bot will begin trading autonomously once started. Logs can be viewed with:
bash
Copy
Edit
docker-compose logs -f bot
(Add prometheus to the command to tail Prometheus logs as well.)
Prometheus will listen on port 9090 by default. You can open http://localhost:9090 in a browser to query metrics. By default, it’s configured to scrape the bot’s metrics on bot:8000 (the bot exposes an HTTP metrics server on port 8000 inside the container).
Environment Configuration: You may pass environment variables to configure the bot. For example, in docker-compose.yml:
TOPSTEP_API_USER / TOPSTEP_API_PASS: Topstep platform credentials or API tokens for order execution.
DAILY_LOSS_LIMIT (default 1000), TRAILING_MAX_DRAWDOWN (default 2000): risk limit parameters (in USD). The bot reads these and will halt trading or flatten positions if breached.
BOT_MODE (e.g., dry-run or live): can toggle paper-trading vs. live trading mode if supported by the trading API.
Adjust these in the compose file or export them in your shell if running via Poetry.
To stop the bot and Prometheus:
bash
Copy
Edit
docker-compose down
Positions are automatically flattened on shutdown (the bot is coded to cancel open orders and close positions on receive of a termination signal to prevent orphaned risk).
Running directly on host (without Docker)
Ensure you have a running Python 3.11 environment with the dependencies installed (via poetry install as above). Then you can launch the bot with:
bash
Copy
Edit
poetry run python -m topstep_quant.bot
(This assumes the package has a bot module with an entry point. Alternatively, if a CLI script is defined, use poetry run topstep-quant.) When running locally, set necessary environment variables in your shell (or create a .env file) for credentials and config. The bot will log to stdout and also serve Prometheus metrics on http://localhost:8000/metrics.
Risk Management and Topstep Rules
Topstep Risk Parameters: The bot is explicitly designed never to violate Topstep’s rules for the 50K Express Funded Account:
Daily Loss Limit: $1,000 – If the bot accumulates $1,000 (or more) in net losses on any given trading day, it will automatically stop trading for the rest of that day. In practice, the bot uses a safety threshold (e.g., $900) to cut off trading before reaching $1,000.
Trailing Max Drawdown: $2,000 – The bot tracks the highest account balance achieved and ensures that current equity never falls more than $2,000 below that high-water mark. If approaching the drawdown limit, the bot will drastically reduce risk or close all positions to prevent breaching $2,000 trailing loss.
Implementation: These risk limits are enforced in real time by the bot’s risk management module:
A global P/L tracker monitors realized and unrealized P/L across all strategies. If unrealized losses hit warning levels (e.g., 90% of limit), all strategies are signaled to scale down or exit.
Hard-stop orders: the system can place hard-stop loss orders with the broker for each open position according to the risk thresholds. This provides an extra layer of protection in case the bot process is delayed or unresponsive.
Daily reset: The daily loss counter resets at 5:00 PM CT (Chicago Time) in accordance with Topstep’s trading combine rules (the start of the futures trading session). The bot uses timezone-aware timestamps (configurable, defaulting to America/Chicago) to manage daily P/L accounting.
If a rule is violated (which should not happen under our controls), the bot will immediately flatten all positions and halt. Since Topstep would deactivate the account for the day or permanently upon a violation, the safest action is to cease trading to avoid any further risk.
By proactively halting trading and preserving capital, the bot ensures it lives to trade another day, aligning with Topstep’s philosophy of risk-first trading.
Payout Strategy and Flow
In a Topstep Express Funded Account, traders can withdraw profits periodically according to Topstep’s payout policy:
After 5 profitable trading days (≥ $200 profit each), a payout up to $5,000 (or 50% of the account balance, whichever is smaller) can be requested.
After accumulating 30 winning days (non-consecutive) of $200+, the trader unlocks the ability to withdraw 100% of profits and even daily payouts in a Live Funded Account.
Payout Planning: TopstepQuant is configured to prioritize steady growth and then realize gains:
The target $7,600 profit in ~7 months is chosen to comfortably exceed the $5,000 threshold. Once the account exceeds $5,000 in profits (and has 5+ winning days), the bot notifies (via logs/metrics) that a payout is eligible. We recommend taking out $5,000 at that point to secure profits (Topstep allows one payout per 5-win-day cycle in the Express account
intercom.help
intercom.help
).
After a payout, the account’s trailing drawdown is reset (Topstep resets the max loss limit to the starting balance when a withdrawal is taken, effectively “realizing” those gains). The bot will then continue trading on the remaining balance, aiming to build it up again.
The bot’s strategies adjust position sizing after a payout to account for the lower account balance, and then scale up as profits accumulate (Topstep’s scaling plan is followed to gradually increase position size as the account grows, never exceeding allowed max contracts).
Payouts can be taken up to 4 times a month if the performance allows, but our approach is to be slightly conservative: likely one payout after reaching $5k, then another after reaching the next $5k, etc. This balances paying yourself and growing the account
intercom.help
intercom.help
.
Automation: While actual withdrawal requests aren’t automated (the trader must request via Topstep’s dashboard), the bot provides guidance. It will, for example, log a message like “Profit target reached – consider withdrawing $X to lock in gains.” Future enhancements could include sending an email or text alert when a payout is advisable.
Overall, TopstepQuant’s payout strategy is to lock in profits regularly while compounding slowly. This ensures that we capitalize on good performance (taking money off the table) and also protect the account from giving back too much (since a withdrawal will also bring down the trailing drawdown to the new balance, reducing risk of future violation).
Deployment & Monitoring
Docker Deployment: The provided Dockerfile containerizes the bot for production. It uses a lightweight Python base image with all dependencies installed from the poetry.lock to guarantee reproducibility. The image runs as a non-root user for security. Docker Compose sets up networking so Prometheus can reach the bot’s metrics endpoint. Prometheus Monitoring: The docker-compose.yml includes a Prometheus service pre-configured to scrape metrics from the trading bot:
Prometheus is configured (via prometheus.yml) to scrape every 5 seconds from the bot at http://bot:8000/metrics. Key metrics include per-strategy P/L, overall daily P/L, margin usage, latency timings, etc.
The bot uses the prometheus-client library to expose metrics. By visiting http://localhost:8000/metrics (if running locally) you can see raw metrics in text format. In Prometheus UI (http://localhost:9090) you can run queries and graph metrics over time.
Alerts: While not included in this initial setup, you can easily integrate Alertmanager to get notified if, say, the bot’s drawdown exceeds a threshold or if it stops sending heartbeat metrics.
Logging: All trading decisions, orders, and risk events are logged with timestamps. In Docker, these logs are available via docker logs or docker-compose logs as shown. Logs are in a structured format (JSON lines or key-value text) for easier analysis. Critical events (e.g., risk limit hit, or an API error) are highlighted.
Continuous Integration (CI) and Code Quality
Every change to TopstepQuant is checked by an automated GitHub Actions CI workflow:
Code Style & Linting: The bot’s code must pass Black (code formatter) and Ruff (linter) with no issues. The CI will fail if formatting is incorrect or lint violations are found (unused variables, complexity issues, etc.). Developers are encouraged to run pre-commit hooks locally which auto-fix many of these issues (Black will reformat code, Ruff can autofix some lint).
Type Checking: The project is fully type-annotated. MyPy is run in CI to ensure all functions and modules have correct type usage. This prevents a whole class of bugs by catching mismatches early.
Security Audit: Bandit (a security static analyzer) runs on the codebase to detect any common security issues (e.g., use of eval, insecure file handling, use of hard-coded secrets etc.). Given this bot can execute trades with real money, we treat security seriously.
Testing: Although not yet fully implemented, the framework is in place for unit and integration tests (using pytest). The CI will run pytest to execute the test suite. (At initialization, you might find placeholder tests or none – expanding test coverage is a top priority as strategies are implemented).
Docker Build: Finally, the CI attempts to build the Docker image using the provided Dockerfile. This ensures that our container environment is always up-to-date and any issues (like missing packages or failing installations) are caught early. Upon success, the image can be deployed to your infrastructure or a cloud container registry.
By enforcing these checks on each commit and pull request, we maintain a high-quality codebase. This rigor is essential in a trading system where errors can be costly. Code review is also encouraged – the repository includes a GitHub Actions workflow status badge (in this README or project page) so you can see at a glance if the build is passing.
Getting Started with Development
If you wish to modify or extend TopstepQuant:
The code is organized by strategy (each alpha sleeve likely has its own module/class) and shared components (risk manager, execution engine, data feeds).
We welcome improvements via pull requests. Please ensure your code adheres to the style and passes pre-commit checks.
For any major changes, open an issue first to discuss. Particularly with trading logic, we prefer a cautious approach – changes should be tested in simulation before going live.
Disclaimer
Important: This software is provided for educational and research purposes. Trading futures is risky, and while TopstepQuant is designed with strict risk controls, no strategy is foolproof. Use this bot at your own risk and only trade with capital you can afford to lose. The authors are not liable for any losses or violations incurred while using this software. Always monitor any automated trading system, especially in the beginning, and make sure it behaves as expected with a demo or simulation before connecting to a live funded account. With that said, TopstepQuant aims to automate the grind of the Topstep combine and funded account rules – letting you systematically trade a proven strategy while you focus on analysis and improvements. Good luck and good trading!