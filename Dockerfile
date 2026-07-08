FROM python:3.12-slim

WORKDIR /testauth

RUN pip install fastapi uvicorn httpx authlib itsdangerous

COPY testauth.py ./

EXPOSE 8080

CMD ["uvicorn", "testauth:app", "--host", "0.0.0.0", "--port", "8080"]
