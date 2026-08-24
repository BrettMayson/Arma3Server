FROM rust:1-bookworm AS builder

WORKDIR /build
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release

FROM debian:bookworm-slim

LABEL maintainer="Brett - github.com/brettmayson"
LABEL org.opencontainers.image.source=https://github.com/brettmayson/arma3server

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update \
    && \
    apt-get install -y --no-install-recommends --no-install-suggests \
        lib32stdc++6 \
        lib32gcc-s1 \
        libcurl4 \
        ca-certificates \
        libstdc++6 \
        libssl3 \
        libc6 \
        libavahi-client3 \
    && \
    apt-get clean autoclean \
    && \
    apt-get autoremove -y \
    && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/target/release/arma3server /usr/local/bin/arma3server

ENV RUST_LOG=info

ENV ARMA3_SERVER__BINARY=./arma3server_x64
ENV ARMA3_SERVER__CONFIG=main.cfg
ENV ARMA3_SERVER__PARAMS=
ENV ARMA3_SERVER__PROFILE=main
ENV ARMA3_SERVER__WORLD=empty
ENV ARMA3_SERVER__LIMIT_FPS=1000
ENV ARMA3_SERVER__CDLC=
ENV ARMA3_SERVER__PORT=2302
ENV ARMA3_SERVER__CLEAR_KEYS=true
ENV ARMA3_SERVER__SKIP_INSTALL=false
ENV ARMA3_HEADLESS__CLIENTS=0
ENV ARMA3_HEADLESS__PROFILE="\$profile-hc-\$i"
ENV ARMA3_MODS__LOCAL=true
ENV ARMA3_MODS__PRESET=

EXPOSE 2302/udp
EXPOSE 2303/udp
EXPOSE 2304/udp
EXPOSE 2305/udp
EXPOSE 2306/udp

WORKDIR /arma3

VOLUME /arma3/server

STOPSIGNAL SIGINT

ENTRYPOINT ["/usr/local/bin/arma3server"]
