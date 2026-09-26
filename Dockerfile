FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY frontend ./frontend
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts
COPY data ./data
RUN mkdir -p uploads
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
