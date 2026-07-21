"""Simple connectivity check for the transactions event stream.

Reuses the application's own consumer settings and verifies that the
configured broker is reachable, the transactions topic exists, and the
assigned partition's offsets can be queried.

Run from the repo root:

    CONSUMER_INSTANCE=0 python test/test_transactions_access.py
"""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# The consumer settings require CONSUMER_INSTANCE; default to partition 0.
os.environ.setdefault("CONSUMER_INSTANCE", "0")

from confluent_kafka import Consumer, KafkaException, TopicPartition  # noqa: E402

from settings.consumer import event_stream  # noqa: E402

logging.basicConfig(format="%(asctime)s %(levelname)s - %(message)s", level=logging.INFO)


def check_access():
    topic = event_stream["topic"]
    partition = event_stream["partition"]
    consumer = Consumer(event_stream["config"])

    try:
        try:
            metadata = consumer.list_topics(topic=topic, timeout=10)
        except KafkaException as e:
            logging.error(f"Failed to reach broker: {e}")
            return False

        topic_metadata = metadata.topics.get(topic)
        if topic_metadata is None or topic_metadata.error is not None:
            error = getattr(topic_metadata, "error", "not found")
            logging.error(f"Topic {topic!r} is not accessible: {error}")
            return False

        partitions = sorted(topic_metadata.partitions)
        logging.info(f"Topic {topic!r} is accessible with {len(partitions)} partitions: {partitions}")

        if partition not in topic_metadata.partitions:
            logging.error(f"Assigned partition {partition} does not exist on topic {topic!r}")
            return False

        try:
            low, high = consumer.get_watermark_offsets(TopicPartition(topic, partition), timeout=10)
        except KafkaException as e:
            logging.error(f"Failed to read offsets for partition {partition}: {e}")
            return False

        logging.info(
            f"Partition {partition} offsets: low={low} high={high} ({high - low} messages available)"
        )
        logging.info("Transactions event stream access OK")
        return True
    finally:
        consumer.close()


if __name__ == "__main__":
    sys.exit(0 if check_access() else 1)
