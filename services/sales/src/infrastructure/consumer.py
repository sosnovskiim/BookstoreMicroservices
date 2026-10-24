import asyncio
import json

import aio_pika

from .db import SessionLocal, SqlOrderRepository, SqlInbox
from .rabbit import declare_exchange
from ..application.use_cases import HandleInventoryResult


class InventoryResultConsumer:
    """
    Consumer двух типов событий от Inventory (требование 7):
      - inventory.stock.reserved  → Order CONFIRMED
      - inventory.stock.rejected  → Order CANCELLED
    Идемпотентность через inbox.
    """

    QUEUE = "sales.inventory.result"
    ROUTING_KEYS = ["inventory.stock.reserved", "inventory.stock.rejected"]

    def __init__(self, connection: aio_pika.abc.AbstractConnection):
        self.connection = connection

    async def start(self) -> None:
        channel = await self.connection.channel()
        await channel.set_qos(prefetch_count=10)
        exchange = await declare_exchange(channel)
        queue = await channel.declare_queue(self.QUEUE, durable=True)
        # Одна очередь связана с двумя routing key — один consumer, два исхода.
        for rk in self.ROUTING_KEYS:
            await queue.bind(exchange, routing_key=rk)

        async def on_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
            async with message.process(requeue=False):
                event_id = message.message_id or ""
                event_type = message.type or "unknown"
                payload = json.loads(message.body)

                async with SessionLocal() as session:
                    uc = HandleInventoryResult(
                        orders=SqlOrderRepository(session),
                        inbox=SqlInbox(session),
                        commit=session.commit,
                    )
                    await uc.execute(event_id=event_id, event_type=event_type, payload=payload)

        await queue.consume(on_message)
        try:
            await asyncio.Future()
        except asyncio.CancelledError:
            await queue.cancel(on_message)
