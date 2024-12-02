import logging
import os
import socket
from dotenv import load_dotenv


# Suppress some kafka message streams
logger = logging.getLogger("kafka")
logger.setLevel(logging.WARN)

# Paths to the .env.local and local authorization policy file
file_path = os.path.dirname(__file__)
env_path = os.path.join(file_path, ".env.local")
policy_path = os.path.join(
    file_path,
    "config",
    "access_control_policy.json"
)
policy_path = "file://" + policy_path

# Load the .env file
load_dotenv(env_path)

event_stream = {
    "config": {
        "bootstrap.servers": "host.docker.internal:9092",
        "client.id": socket.gethostname(),
        "group.id": "westconsumer",
        "auto.offset.reset": "latest",
        "enable.auto.commit": False
    },
    "topics": ["esgfng"],
}

globus_search_client_credentials = {
    "client_id": os.environ.get("CLIENT_ID"),
    "client_secret": os.environ.get("CLIENT_SECRET")
}

# ESGF2 Globus Search
globus_search = {
    "index": "58f3a9eb-51f8-410e-8e68-da4bd6617ca6",
}
