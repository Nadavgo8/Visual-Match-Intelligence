FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY vmi ./vmi
COPY web ./web
COPY prompts ./prompts
RUN useradd -m app && chown -R app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "vmi.api.server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
