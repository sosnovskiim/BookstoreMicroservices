import asyncio
import json

import aio_pika

from ..config import settings
from .db import (
    SessionLocal, SqlStockRepository, SqlInbox, SqlOutbox,
)
from .rabbit import declare_exchange
from ..application.use_cases import HandleOrderCreated


class OrderCreatedConsumer:
    """
    Consumer события sales.order.created (требования 7, 9).
    Обрабатывает событие через use case HandleOrderCreated:
    резервирует остатки и пишет результат в inventory.outbox.
    """

    QUEUE = "inventory.sales.order.created"
    ROUTING_KEY = "sales.order.created"

    def __init__(self, connection: aio_pika.abc.AbstractConnection):
        self.connection = connection

    async def start(self) -> None:
        channel = await self.connection.channel()
        await channel.set_qos(prefetch_count=10)  # параллельная обработка до 10 сообщений
        exchange = await declare_exchange(channel)
        queue = await channel.declare_queue(self.QUEUE, durable=True)
        await queue.bind(exchange, routing_key=self.ROUTING_KEY)

        async def on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
            # auto_ack через process(): успешный выход — ack, исключение — nack.
            async with message.process(requeue=False):
                event_id = message.message_id or ""
                event_type = message.type or self.ROUTING_KEY
                payload = json.loads(message.body)

                async with SessionLocal() as session:
                    uc = HandleOrderCreated(
                        stocks=SqlStockRepository(session),
                        inbox=SqlInbox(session),
                        outbox=SqlOutbox(session),
                        session=session,
                        commit=session.commit,
                    )
                    await uc.execute(event_id=event_id, payload=payload)

        await queue.consume(on_message)
        # Держим корутину живой, пока задачу не отменят.
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            await queue.cancel(on_message)
