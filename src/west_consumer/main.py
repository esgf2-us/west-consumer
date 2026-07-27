import logging

from west_consumer.consumer import KafkaConsumerService
from west_consumer.globus import ConsumerSearchClient
from west_consumer.producer import KafkaProducer
from west_consumer.settings.consumer import (
    consumer_instance,
    event_stream,
    globus_search,
    globus_search_client_credentials,
)
from west_consumer.settings.producer import error_event_stream, success_event_stream

logging.basicConfig(
    format=f"%(asctime)s %(levelname)s C{consumer_instance} - %(message)s",
    level=logging.INFO,
)


if __name__ == "__main__":
    error_producer = KafkaProducer(
        config=error_event_stream.get("config"),
        topic=error_event_stream.get("topic"),
    )
    success_producer = KafkaProducer(
        config=success_event_stream.get("config"),
        topic=success_event_stream.get("topic"),
    )

    message_processor = ConsumerSearchClient(
        globus_search_client_credentials,
        globus_search.get("index"),
        error_producer,
        success_producer,
    )

    consumer_service = KafkaConsumerService(
        event_stream.get("config"),
        event_stream.get("topic"),
        event_stream.get("partition"),
        message_processor,
    )
    consumer_service.start()
