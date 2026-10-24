# Образ Identity. Контекст сборки — корень репозитория (см. docker-compose).
FROM python:3.12-slim
WORKDIR /app

# Сначала зависимости — чтобы слой кешировался и не пересобирался при правке кода.
COPY services/identity/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Копируем общий модуль и исходники сервиса.
COPY shared /app/shared
COPY services/identity/src /app/src
COPY services/identity/pytest.ini /app/pytest.ini

# PYTHONPATH=/app — чтобы `import src.` и `import shared.` работали.
ENV PYTHONPATH=/app
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
