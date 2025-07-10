FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        unzip \
        libmagic1 \
        libreoffice \
        dpkg \
        apt-transport-https \
        ca-certificates \
        software-properties-common \
        dbus-x11 \
        curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set environment variables
ENV HOME=/tmp
ENV SEARCH_PORT="19090"
ENV PATH="/tmp/bin:${PATH}"
ENV PYTHONPATH="/var/task"
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install Chrome and ChromeDriver
RUN mkdir -p /var/task/chromedriver && \
    wget -O /var/task/chromedriver/chromedriver-linux64.zip \
        https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.49/linux64/chromedriver-linux64.zip && \
    unzip /var/task/chromedriver/chromedriver-linux64.zip -d /var/task/chromedriver && \
    chmod +x /var/task/chromedriver/chromedriver-linux64/chromedriver && \
    rm /var/task/chromedriver/chromedriver-linux64.zip

RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -f -y && \
    rm google-chrome-stable_current_amd64.deb

# Set up dbus
ENV DBUS_SESSION_BUS_ADDRESS=unix:path=/run/dbus/system_bus_socket
RUN service dbus start

ENV PATH="/usr/bin/google-chrome:${PATH}"

# Set working directory
WORKDIR /var/task

# Copy Python project files
COPY pyproject.toml uv.lock* ./
COPY README.md ./
COPY src/ ./src/
COPY browser-use/ ./browser-use/

# Install Python dependencies using uv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --index-strategy unsafe-best-match

# Install browser-use from local directory
RUN uv add ./browser-use

# Install additional packages that might not be in pyproject.toml
RUN uv pip uninstall pdfminer pdfminer-six
RUN uv pip install aworld==0.2.4 marker-pdf==1.7.5 pdfminer-six

# Expose Flask port
EXPOSE ${SEARCH_PORT}

# Use uv to run the application
CMD ["uv", "run", "aworld-fastapi"]