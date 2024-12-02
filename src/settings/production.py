import os
from dotenv import load_dotenv
from utils import get_secret


# Load the .env file
load_dotenv()

# ESGF2 Event Stream Service Producer/Consumer
kafka_secretsmanager = {
    "region_name": "us-east-1",
    "secret_name": os.environ.get("SECRET_NAME"),
}
sasl_secret = get_secret(kafka_secretsmanager)

event_stream = {
    "config": {
        "bootstrap.servers": "b-1.esgf2a.3wk15r.c9.kafka.us-east-1.amazonaws.com:9096,"
        "b-2.esgf2a.3wk15r.c9.kafka.us-east-1.amazonaws.com:9096,"
        "b-3.esgf2a.3wk15r.c9.kafka.us-east-1.amazonaws.com:9096",
        "security.protocol": "SASL_SSL",
        "sasl.mechanism": "SCRAM-SHA-512",
        "sasl.username": sasl_secret.get("username"),
        "sasl.password": sasl_secret.get("password"),
        "group.id": "westconsumer",
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
    },
    "topics": ["esgf2"],
}

if os.environ.get("KAFKA_CLIENT_DEBUG", False):
    event_stream["config"]["debug"] = "all"
    event_stream["config"]["log_level"] = 7

# ESGF2 West Consumer
globus_secretsservice = {
    "region_name": "us-east-1",
    "secret_name": os.environ.get("GLOBUS_SECRET_NAME"),
}
globus_search_client_credentials = get_secret(globus_secretsservice)

# ESGF2 Globus Search
globus_search = {
    # "index": "d7814ff7-51a9-4155-8b84-97e84600acd7",
    "index": "f037bb33-3413-448b-8486-8400bee5181a",
}
