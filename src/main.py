import logging

from consumer import KafkaConsumerService
from globus import ConsumerSearchClient
from settings.consumer import (event_stream, globus_search,
                               globus_search_client_credentials)

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


if __name__ == "__main__":
    message_processor = ConsumerSearchClient(
        globus_search_client_credentials, globus_search.get("index")
    )

    consumer_service = KafkaConsumerService(
        event_stream.get("config"),
        event_stream.get("topics"),
        message_processor,
    )
    consumer_service.start()
