FROM python:3.13-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        fonts-wqy-zenhei \
        fonts-liberation \
        gnupg \
        libdrm2 \
        libnspr4 \
        libnss3 \
        libxrandr2 \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libatspi2.0-0 \
        libgbm1 \
        libgtk-3-0 \
        libpango-1.0-0 \
        libvulkan1 \
        libxcomposite1 \
        libxdamage1 \
        libxfixes3 \
        libxkbcommon0 \
        xdg-utils \
        xvfb \
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
    rm -rf /var/lib/apt/lists/* && \
    fc-cache -fv

RUN apt --fix-broken install -y

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

# RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
#     dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -f -y && \
#     rm google-chrome-stable_current_amd64.deb

# ---------- 2. 添加 Google 官方仓库 ----------
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
        > /etc/apt/sources.list.d/google-chrome.list

# ---------- 3. 安装 Chrome ----------
RUN apt-get update && \
    apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# ---------- 4. （可选）验证安装 ----------
RUN google-chrome-stable --version

# Set up dbus
RUN mkdir -p /run/dbus
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

# Install aworld (compatible version)
RUN uv pip install marker-pdf==1.8.1

# Install browser-use from local directory
RUN uv add ./browser-use


# Expose Flask port
EXPOSE ${SEARCH_PORT}

# Use uv to run the application
CMD ["uv", "run", "aworld-fastapi"]