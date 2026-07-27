import logging
import os
import socket

from dotenv import load_dotenv

# Load the .env file
load_dotenv()

# Suppress some kafka message streams
logger = logging.getLogger("kafka")
logger.setLevel(logging.WARN)

run_environment = os.environ.get("RUN_ENVIRONMENT", "local")


# Kafka connection details
if run_environment == "local":
    _kafka_config = {
        "bootstrap.servers": "broker:29092",
        "client.id": socket.gethostname(),
    }
    error_event_stream = {
        "config": _kafka_config,
        "topic": "esgf-local.errors",
    }
    success_event_stream = {
        "config": _kafka_config,
        "topic": "esgf-local.success",
    }
else:
    _kafka_config = {
        "bootstrap.servers": os.environ.get("BOOTSTRAP_SERVERS"),
        "security.protocol": "SASL_SSL",
        "sasl.mechanisms": "PLAIN",
        "sasl.username": os.environ.get("CONFLUENT_CLOUD_USERNAME"),
        "sasl.password": os.environ.get("CONFLUENT_CLOUD_PASSWORD"),
    }
    error_event_stream = {
        "config": _kafka_config,
        "topic": os.environ.get("ERRORS_TOPIC", "esgf-local.errors"),
    }
    # Temporary workaround for missing success topic
    success_event_stream = {
        "config": _kafka_config,
        "topic": error_event_stream["topic"].removesuffix("errors") + "success",
    }

print(error_event_stream)
print(success_event_stream)
