import asyncio
from datetime import datetime

import aio_pika
from sqlalchemy import select

from ..config import settings
from .db import SessionLocal, OutboxModel
from .rabbit import declare_exchange, build_message


class OutboxPublisher:
    """
    Transaction outbox publisher (требование 8).
    Читает неопубликованные строки из inventory.outbox и шлёт в RabbitMQ.
    Гарантия at-least-once: если упадём между publish и commit — повторим.
    Дубликаты отсекаются inbox на стороне получателя.
    """

    def __init__(self, connection: aio_pika.abc.AbstractConnection, interval: float = 2.0):
        self.connection = connection
        self.interval = interval

    async def start(self) -> None:
        # publisher_confirms=True — брокер подтверждает приём сообщения.
        channel = await self.connection.channel(publisher_confirms=True)
        exchange = await declare_exchange(channel)

        while True:
            try:
                await self._tick(exchange)
            except asyncio.CancelledError:
                return
            except Exception:
                # В учебном проекте просто логируем; для production — метрики/алерты.
                pass
            await asyncio.sleep(self.interval)

    async def _tick(self, exchange: aio_pika.Exchange) -> None:
        async with SessionLocal() as session:
            # Берём пачку неопубликованных.
            rows = (await session.execute(
                select(OutboxModel)
                .where(OutboxModel.published_at.is_(None))
                .order_by(OutboxModel.created_at)
                .limit(100)
            )).scalars().all()

            for row in rows:
                msg = build_message(row.event_type, row.payload, str(row.id))
                try:
                    await exchange.publish(msg, routing_key=row.event_type)
                    row.published_at = datetime.utcnow()
                except Exception:
                    row.attempts += 1
            await session.commit()
