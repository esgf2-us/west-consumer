"""Pull one message from the transactions event stream.

Reuses the application's own consumer settings (broker, topic, partition,
auth) but uses a dedicated test consumer group so it does not move the
production ``westconsumer`` offsets. Does not commit.

Run from the repo root:

    CONSUMER_INSTANCE=0 uv run python test/test_transactions_pull.py
"""

import json
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# The consumer settings require CONSUMER_INSTANCE; default to partition 0.
os.environ.setdefault("CONSUMER_INSTANCE", "0")

from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition  # noqa: E402

from settings.consumer import event_stream  # noqa: E402

logging.basicConfig(format="%(asctime)s %(levelname)s - %(message)s", level=logging.INFO)

# Avoid interfering with the live consumer group's committed offsets.
TEST_GROUP_ID = "esgf2.west.test01"
POLL_TIMEOUT_SECONDS = 15.0


def pull_one_message():
    topic = event_stream["topic"]
    partition = event_stream["partition"]
    config = dict(event_stream["config"])
    config["group.id"] = TEST_GROUP_ID
    config["auto.offset.reset"] = "earliest"
    config["enable.auto.commit"] = False

    consumer = Consumer(config)
    assigned = TopicPartition(topic, partition)

    try:
        low, high = consumer.get_watermark_offsets(assigned, timeout=10)
        logging.info(
            f"Topic {topic!r} partition {partition}: low={low} high={high} "
            f"({high - low} messages available)"
        )
        if low == high:
            logging.error(f"No messages available on {topic!r} partition {partition}")
            return False

        # Read the oldest available message without committing.
        assigned.offset = low
        consumer.assign([assigned])

        msg = consumer.poll(timeout=POLL_TIMEOUT_SECONDS)
        if msg is None:
            logging.error(
                f"Timed out waiting for a message on {topic!r} partition {partition} "
                f"group_id={TEST_GROUP_ID!r}"
            )
            return False

        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                logging.error(
                    f"Reached end of {topic!r} partition {partition} with no message "
                    f"group_id={TEST_GROUP_ID!r}"
                )
                return False
            raise KafkaException(msg.error())

        key = msg.key().decode("utf-8") if msg.key() else None
        logging.info(
            f"Pulled message topic={msg.topic()} partition={msg.partition()} "
            f"offset={msg.offset()} key={key!r}"
        )

        try:
            payload = json.loads(msg.value())
            logging.info("Message value:\n%s", json.dumps(payload, indent=2, sort_keys=True))
        except (TypeError, json.JSONDecodeError):
            logging.info("Message value (raw): %r", msg.value())

        logging.info("Transactions event stream pull OK")
        return True
    except KafkaException as e:
        logging.error(f"Failed to pull message group_id={TEST_GROUP_ID!r}: {e}")
        return False
    finally:
        consumer.close()


if __name__ == "__main__":
    sys.exit(0 if pull_one_message() else 1)
