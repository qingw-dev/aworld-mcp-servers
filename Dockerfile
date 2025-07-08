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
RUN wget -O /var/task/chromedriver/chromedriver-linux64.zip \
    https://storage.googleapis.com/chrome-for-testing-public/138.0.7204.49/linux64/chromedriver-linux64.zip
RUN unzip /var/task/chromedriver/chromedriver-linux64.zip -d /var/task/chromedriver
RUN chmod +x /var/task/chromedriver/chromedriver-linux64/chromedriver
RUN rm /var/task/chromedriver/chromedriver-linux64.zip

RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    dpkg -i google-chrome-stable_current_amd64.deb || apt-get install -f -y && \
    rm google-chrome-stable_current_amd64.deb

WORKDIR /var/task

ADD pip.conf /root/.pip/pip.conf
ADD requirements.txt /root/requirements.txt
ADD mcp-servers.yml /root/mcp-servers.yml

ADD ./src /var/task/src
ADD ./browser-use /var/task/browser-use

RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh --no-check-certificate -O /tmp/miniconda.sh &&  \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh

ENV PATH="/opt/conda/bin:${PATH}"

# Create environment from YAML file
RUN conda config --set show_channel_urls true

# RUN conda env create -f /root/mcp-servers.yml && \
#     conda clean -a -y
RUN conda create -n py312 python=3.12

# Update PATH to use the created environment
ENV PATH="/opt/conda/envs/py312/bin:$PATH"

RUN pip install -U pip pysocks -i https://mirrors.aliyun.com/pypi/simple/
# RUN pip install -r /root/requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
RUN pip install -r /root/requirements.txt
RUN pip install aworld==0.2.4 marker-pdf==1.7.5
RUN pip install pathvalidate pdfminer.six puremagic pydub SpeechRecognition html2text pre_commit
RUN pip install "smolagents[toolkit]"
RUN pip install /var/task/browser-use

# Expose Flask port
EXPOSE ${SEARCH_PORT}

# PYTHONENV
ENV PYTHONPATH="/var/task:$PATH"

# Default to search server, but can be overridden
CMD ["/bin/bash", "-c", "source /opt/conda/bin/activate py312 && cd /var/task && python3.12 -m src.main"]