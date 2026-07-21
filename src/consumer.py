import json
import logging

from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition


class KafkaConsumerService:
    def __init__(self, kafka_config, topic, partition, message_processor):
        self.kafka_config = kafka_config
        self.topic = topic
        self.partition = partition
        self.message_processor = message_processor
        self.consumer = Consumer(self.kafka_config)

    def process_messages(self, messages):
        messages_data = []
        for msg in messages:
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                if msg.fatal():
                    logging.error(
                        f"Message fatal error partition={msg.partition()} offset={msg.offset()}: {msg.error()}."
                    )
                    raise KafkaException(msg.error())
                logging.warn(
                    f"Message error partition={msg.partition()} offset={msg.offset()}: {msg.error()}."
                )
                continue
            try:
                data = json.loads(msg.value())
                messages_data.append((data, msg.partition(), msg.offset()))
            except json.JSONDecodeError as e:
                logging.error(
                    f"Data deserialization error partition={msg.partition()} offset={msg.offset()}: {e}."
                )
                raise Exception(e)
        return messages_data

    def start(self):
        self.topic_partition = TopicPartition(self.topic, self.partition)
        self.consumer.assign([self.topic_partition])
        logging.info(f"Kafka consumer started on {self.topic} partition {self.partition}")
        try:
            while True:
                messages = self.consumer.consume(num_messages=50, timeout=5.0)
                if not messages:
                    continue

                logging.info(
                    f"Consumed {len(messages)} messages partition={self.partition} "
                    f"offsets {messages[0].offset()}-{messages[-1].offset()}"
                )

                messages_data = self.process_messages(messages)

                if messages_data:
                    self.message_processor.process_messages(messages_data)
                    self.consumer.commit(message=messages[-1], asynchronous=False)

        except KeyboardInterrupt:
            logging.info("Kafka consumer interrupted. Exiting...")
        except KafkaException as e:
            logging.error(f"Kafka exception: {e}")
        finally:
            logging.info("Closing Kafka consumer...")
            self.consumer.close()
