import json
import aio_pika
from ..config import settings


async def declare_exchange(channel: aio_pika.Channel) -> aio_pika.Exchange:
    """
    Декларирует общий topic-exchange bookstore.events.
    Durable=True — выживает при рестарте брокера (требование 9).
    """
    return await channel.declare_exchange(
        settings.rabbitmq_exchange, type=aio_pika.ExchangeType.TOPIC, durable=True,
    )


def build_message(event_type: str, payload: dict, event_id: str) -> aio_pika.Message:
    """Собирает AMQP-сообщение: body = JSON, message_id = uuid события (для inbox)."""
    return aio_pika.Message(
        body=json.dumps(payload).encode(),
        message_id=event_id,
        type=event_type,
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
