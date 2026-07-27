import json
import logging
import time

from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition


class KafkaConsumerService:
    def __init__(self, kafka_config, topic, partition, message_processor):
        self.kafka_config = kafka_config
        self.topic = topic
        self.partition = partition
        self.message_processor = message_processor
        self.consumer = Consumer(self.kafka_config)

    def process_message(self, msg):
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                return None
            if msg.fatal():
                logging.error(
                    f"Message fatal error partition={msg.partition()} offset={msg.offset()}: {msg.error()}."
                )
                raise KafkaException(msg.error())
            logging.warning(
                f"Message error partition={msg.partition()} offset={msg.offset()}: {msg.error()}."
            )
            return None
        try:
            data = json.loads(msg.value())
            return (data, msg.key(), msg.partition(), msg.offset())
        except json.JSONDecodeError as e:
            logging.error(
                f"Data deserialization error partition={msg.partition()} offset={msg.offset()}: {e}."
            )
            raise Exception(e)

    def start(self):
        self.topic_partition = TopicPartition(self.topic, self.partition)
        self.consumer.assign([self.topic_partition])
        logging.info(f"Kafka consumer started on {self.topic} partition {self.partition}")
        try:
            while True:
                msg = self.consumer.poll(timeout=5.0)
                if msg is None:
                    time.sleep(0.1) # 100ms sleep to avoid busy-waiting
                    continue

                logging.info(
                    f"Polled message partition={msg.partition()} offset={msg.offset()}"
                )

                message_data = self.process_message(msg)
                if message_data:
                    self.message_processor.process_message(message_data)
                    self.consumer.commit(message=msg, asynchronous=False)

        except KeyboardInterrupt:
            logging.info("Kafka consumer interrupted. Exiting...")
        except KafkaException as e:
            logging.error(f"Kafka exception: {e}")
        finally:
            logging.info("Closing Kafka consumer...")
            self.consumer.close()
