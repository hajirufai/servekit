FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir pytest

# Run tests to verify build
RUN pytest -v

# Default: run hello world example
EXPOSE 8080
CMD ["python", "-m", "examples.hello"]
