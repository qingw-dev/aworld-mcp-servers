FROM ubuntu:24.04

ENV HOME=/tmp/npm

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3.12 \
        python3-pip \
        wget \
        unzip

ENV PATH="/tmp/npm/bin:${PATH}"
ENV SEARCH_PORT="19090"

RUN python3 --version
RUN pip --version

ADD requirements.txt /root/requirements.txt
ADD entrypoint.sh /var/task/entrypoint.sh
ADD pip.conf /root/.pip/pip.conf
ADD ./src/rag/search_server.py /var/task/search_server.py

RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh --no-check-certificate -O /tmp/miniconda.sh &&  \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh

ENV PATH="/opt/conda/bin:${PATH}"

ARG PIP_OPTIONS='-i https://mirrors.aliyun.com/pypi/simple/'

RUN pip install -U pip pysocks ${PIP_OPTIONS}

# 一次性安装所有依赖
RUN conda create -n py312 python=3.12 -y && \
    /opt/conda/bin/conda run -n py312 pip install -i https://mirrors.aliyun.com/pypi/simple/ -r /root/requirements.txt --no-cache-dir && \
    conda clean -a -y

ENV PATH="/opt/conda/envs/py312/bin:$PATH"
RUN chmod +x /var/task/entrypoint.sh

# Expose Flask port
EXPOSE ${SEARCH_PORT}

# Default to search server, but can be overridden
CMD ["/bin/bash", "-c", "source /opt/conda/bin/activate py312 && python3.12 -u /var/task/search_server.py"]