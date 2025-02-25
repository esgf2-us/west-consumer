import os
import socket

from dotenv import load_dotenv

# Load the .env file
load_dotenv()

run_environment = os.environ.get("RUN_ENVIRONMENT", None)

# ESGF2 Event Stream Service Consumer
if run_environment == "local":
    event_stream = {
        "config": {
            "auto.offset.reset": "latest",
            "bootstrap.servers": "localhost:9092",
            "client.id": socket.gethostname(),
            "enable.auto.commit": False,
            "group.id": "westconsumer",
        },
        "topics": ["esgfng"],
    }
else:
    event_stream = {
        "config": {
            "auto.offset.reset": "latest",
            "bootstrap.servers": "b-1.esgf2a.3wk15r.c9.kafka.us-east-1.amazonaws.com:9096,"
            "b-2.esgf2a.3wk15r.c9.kafka.us-east-1.amazonaws.com:9096,"
            "b-3.esgf2a.3wk15r.c9.kafka.us-east-1.amazonaws.com:9096",
            "enable.auto.commit": False,
            "group.id": "westconsumer",
            "sasl.mechanism": "SCRAM-SHA-512",
            "sasl.username": os.environ.get("CONFLUENT_CLOUD_USERNAME"),
            "sasl.password": os.environ.get("CONFLUENT_CLOUD_PASSWORD"),
            "security.protocol": "SASL_SSL",
        },
        "topics": ["esgfng"],
    }

if os.environ.get("KAFKA_CLIENT_DEBUG", False):
    event_stream["config"]["debug"] = "all"
    event_stream["config"]["log_level"] = 7

globus_search_client_credentials = {
    "client_id": os.environ.get("CLIENT_ID"),
    "client_secret": os.environ.get("CLIENT_SECRET"),
}

# ESGF2 Globus Search
globus_search = {
    "index": "f037bb33-3413-448b-8486-8400bee5181a",
}
