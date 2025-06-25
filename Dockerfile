FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.12 \
        python3-pip \
        wget \
        unzip \
        libmagic1 \
        libreoffice

ENV HOME=/tmp
ENV SEARCH_PORT="19090"
ENV PATH="/tmp/bin:${PATH}"

RUN python3 --version
RUN pip --version
RUN libreoffice --version

RUN mkdir -p /var/task/chromedriver
RUN curl -o /var/task/chromedriver/chromedriver-linux64.zip \
    https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.49/linux64/chromedriver-linux64.zip
RUN unzip /var/task/chromedriver/chromedriver-linux64.zip -d /var/task/chromedriver
RUN chmod +x /var/task/chromedriver/chromedriver
RUN rm /var/task/chromedriver/chromedriver-linux64.zip

WORKDIR /var/task

ADD pip.conf /root/.pip/pip.conf
ADD requirements.txt /root/requirements.txt
ADD mcp-servers.yml /root/mcp-servers.yml

ADD ./src /var/task/src

RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh --no-check-certificate -O /tmp/miniconda.sh &&  \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh

ENV PATH="/opt/conda/bin:${PATH}"

# Create environment from YAML file
RUN conda config --add channels https://mirrors.aliyun.com/anaconda/pkgs/main/
RUN conda config --add channels https://mirrors.aliyun.com/anaconda/pkgs/free/
RUN conda config --add channels https://mirrors.aliyun.com/anaconda/cloud/conda-forge/
RUN conda config --set show_channel_urls true

RUN conda env create -f /root/mcp-servers.yml && \
    conda clean -a -y

# Update PATH to use the created environment
ENV PATH="/opt/conda/envs/mcp-servers/bin:$PATH"

RUN pip install -U pip pysocks -i https://mirrors.aliyun.com/pypi/simple/

# Expose Flask port
EXPOSE ${SEARCH_PORT}

# Default to search server, but can be overridden
CMD ["/bin/bash", "-c", "source /opt/conda/bin/activate py312 && python3.12 -u /var/task/src/rag/search_server.py"]