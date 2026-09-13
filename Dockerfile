FROM python:3.13-bookworm AS builder

RUN pip install poetry==2.4.3

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

WORKDIR /app

COPY pyproject.toml poetry.lock ./
RUN touch README.md

RUN --mount=type=cache,target=$POETRY_CACHE_DIR poetry install --no-root

COPY main.py ./
COPY monitors ./monitors
COPY tests ./tests
RUN poetry run python -m unittest discover -s tests

FROM python:3.13-slim-bookworm AS runtime

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

COPY --from=builder ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY main.py .
COPY monitors ./monitors

ENTRYPOINT ["python", "-m", "main"]
