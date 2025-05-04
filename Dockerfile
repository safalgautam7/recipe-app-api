# Use lightweight Python 3.10 on Alpine 3.21
FROM python:3.10-alpine3.21
LABEL maintainer="notme"

# Disable Python output buffering
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy dependencies files first (for better layer caching)
COPY ./requirements.txt /tmp/requirements.txt
COPY ./requirements.dev.txt /tmp/requirements.dev.txt
COPY ./scripts /scripts

ARG DEV=false

# Create virtual environment and install dependencies
RUN python -m venv /py && \
    /py/bin/pip install --no-cache-dir --upgrade pip && \
    apk add --update --no-cache postgresql-client jpeg-dev && \
    apk add --update --no-cache --virtual .tmp-build-deps \
        build-base postgresql-dev musl-dev zlib zlib-dev linux-headers && \
    /py/bin/pip install --no-cache-dir -r /tmp/requirements.txt && \
    if [ "$DEV" = "true" ]; then \
        /py/bin/pip install --no-cache-dir -r /tmp/requirements.dev.txt; \
    fi && \
    rm -rf /tmp/requirements*.txt && \
    apk del .tmp-build-deps

# Copy application code
COPY ./app /app

# Add a non-root user for security
RUN adduser --disabled-password --no-create-home django-user && \
mkdir -p /vol/web/media && \
mkdir -p /vol/web/static && \
chown -R django-user:django-user /vol && \
chmod -R 755 /vol && \
chmod -R +x /scripts


# Set the virtual environment path
ENV PATH="/scripts:/py/bin:$PATH"

# Expose Django default port
EXPOSE 8000

# Switch to non-root user for security
USER django-user

CMD ["run.sh"]

# Default command (commented out as you have it)
# CMD ["gunicorn", "--bind", "0.0.0.0:8000", "recipe-app-api.wsgi:application"]