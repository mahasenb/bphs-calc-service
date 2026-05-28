FROM python:3.10-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE EPHEMERIS_LICENSE.md ./
RUN pip install --no-cache-dir -e .

COPY bphs_core ./bphs_core
COPY app ./app
# data/ephe must be volume-mounted or COPY'd separately (not committed to git)
RUN mkdir -p data/ephe

EXPOSE 8000

RUN adduser --disabled-password --gecos '' appuser
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
