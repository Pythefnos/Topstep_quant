# topstep_quant/run_bot.py
#!/usr/bin/env python3
"""
Entry point for the Topstep Quant trading bot. 
Loads configuration, validates it, and starts the main execution coordinator.
"""
import argparse
import json
import sys

try:
    import yaml  # PyYAML for loading YAML config
except ImportError:
    print("Error: PyYAML is not installed. Please install it to parse YAML configurations.")
    sys.exit(1)

try:
    import jsonschema
except ImportError:
    print("Error: jsonschema library is not installed. Please install it for config validation.")
    sys.exit(1)

from jsonschema import ValidationError

def load_config(config_path: str) -> dict:
    """Load and parse the YAML configuration file."""
    try:
        with open(config_path, 'r') as file:
            config_data = yaml.safe_load(file)
    except FileNotFoundError:
        print(f"Configuration file not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML config: {e}")
        sys.exit(1)
    if config_data is None:
        # An empty YAML file or one that only contains comments would result in None
        print(f"Configuration file {config_path} is empty or invalid.")
        sys.exit(1)
    return config_data

def validate_config(config_data: dict, schema_path: str) -> None:
    """Validate the configuration data against the JSON schema."""
    # Load JSON schema from file
    try:
        with open(schema_path, 'r') as schema_file:
            schema = json.load(schema_file)
    except FileNotFoundError:
        print(f"Schema file not found: {schema_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON schema: {e}")
        sys.exit(1)
    # Perform validation
    try:
        jsonschema.validate(instance=config_data, schema=schema)
    except ValidationError as e:
        print(f"Configuration validation error: {e.message}")
        sys.exit(1)

def main():
    """Main function to load config, validate it, and start the trading bot coordinator."""
    parser = argparse.ArgumentParser(description="Run the Topstep Quant trading bot.")
    parser.add_argument("-c", "--config", default="config/default_settings.yaml",
                        help="Path to the YAML configuration file.")
    parser.add_argument("-s", "--schema", default="config/schema.json",
                        help="Path to the JSON schema for config validation.")
    args = parser.parse_args()

    # Load and validate configuration
    config_path = args.config
    schema_path = args.schema
    config = load_config(config_path)
    validate_config(config, schema_path)

    # Configuration is validated at this point
    print("Configuration loaded and validated successfully.")

    # Hand off to the main execution coordinator
    # In a full implementation, this is where we'd initialize and start the trading bot's main engine.
    # For example, if a coordinator class exists:
    # from topstep_quant.engine import TradingEngine
    # engine = TradingEngine(config)
    # engine.start()
    print("Starting main execution coordinator...")
    # Placeholder: Simulate handing control to the main coordinator
    # (In practice, replace this with actual trading engine startup)
    # The program would typically not exit here until the trading bot is stopped.
    return 0

if __name__ == "__main__":
    sys.exit(main())
