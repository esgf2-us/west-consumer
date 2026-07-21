FROM public.ecr.aws/sam/build-python3.12:latest-x86_64

ENV LD_LIBRARY_PATH=/lib:/usr/lib:/usr/local/lib
ENV PATH=/root/.local/bin:/sbin:/usr/sbin:${PATH}

RUN dnf upgrade -y
RUN dnf group install -y "Development Tools"
RUN dnf install -y gcc git libcurl-devel make openssl openssl-devel which

RUN git clone https://github.com/confluentinc/librdkafka  && \
    cd librdkafka && git checkout tags/v2.6.0 && \
    ./configure --install-deps && make && make install && \
    ldconfig

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /var/task

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

ENV PATH=/var/task/.venv/bin:${PATH}

COPY supervisord.conf /etc/supervisord.conf
COPY ./src .

CMD ["supervisord", "-n", "-c", "/etc/supervisord.conf"]