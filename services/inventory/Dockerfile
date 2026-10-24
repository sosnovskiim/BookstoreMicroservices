# Образ Inventory. Контекст сборки — корень репозитория.
FROM python:3.12-slim
WORKDIR /app

# Зависимости отдельным слоем — переиспользуется при правке кода.
COPY services/inventory/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Общий модуль (JWT) и исходники сервиса.
COPY shared /app/shared
COPY services/inventory/src /app/src
COPY services/inventory/pytest.ini /app/pytest.ini

ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
