# Образ Sales. Контекст сборки — корень репозитория.
FROM python:3.12-slim
WORKDIR /app

COPY services/sales/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Генерируем gRPC-стабы из общего proto/catalog.proto для клиента (требование 10).
COPY proto /app/proto
RUN mkdir -p /app/src/grpc_gen && \
    python -m grpc_tools.protoc -I/app/proto \
        --python_out=/app/src/grpc_gen \
        --grpc_python_out=/app/src/grpc_gen \
        /app/proto/catalog.proto && \
    touch /app/src/grpc_gen/__init__.py && \
    sed -i 's/^import catalog_pb2/from . import catalog_pb2/' /app/src/grpc_gen/catalog_pb2_grpc.py

COPY shared /app/shared
COPY services/sales/src /app/src
COPY services/sales/pytest.ini /app/pytest.ini

ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
