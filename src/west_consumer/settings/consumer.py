import os
import socket

from dotenv import load_dotenv

load_dotenv()

run_environment = os.environ.get("RUN_ENVIRONMENT", "local")
consumer_instance = os.environ["CONSUMER_INSTANCE"]
partition = int(consumer_instance)
client_id = f"{socket.gethostname()}-{consumer_instance}"

# ESGF2 Event Stream Service Consumer
if run_environment == "local":
    event_stream = {
        "config": {
            "auto.offset.reset": "earliest",
            "bootstrap.servers": os.environ.get("BOOTSTRAP_SERVERS", "broker:29092"),
            "client.id": client_id,
            "enable.auto.commit": False,
            "group.id": "westconsumer",
        },
        "topic": "esgf-local.transactions",
        "partition": partition,
    }
else:
    event_stream = {
        "config": {
            "auto.offset.reset": "earliest",
            "bootstrap.servers": os.environ.get("BOOTSTRAP_SERVERS"),
            "client.id": client_id,
            "enable.auto.commit": False,
            "group.id": os.environ.get("GROUP_ID"),
            "sasl.mechanism": "PLAIN",
            "sasl.username": os.environ.get("CONFLUENT_CLOUD_USERNAME"),
            "sasl.password": os.environ.get("CONFLUENT_CLOUD_PASSWORD"),
            "security.protocol": "SASL_SSL",
        },
        "topic": os.environ.get("TRANSACTIONS_TOPIC"),
        "partition": partition,
    }


if os.environ.get("KAFKA_CLIENT_DEBUG", False):
    event_stream["config"]["debug"] = "all"
    event_stream["config"]["log_level"] = 7

globus_search_client_credentials = {
    "client_id": os.environ.get("CLIENT_ID"),
    "client_secret": os.environ.get("CLIENT_SECRET"),
}

# ESGF2 Globus Search
globus_search = {"index": os.environ.get("GLOBUS_SEARCH_INDEX")}
