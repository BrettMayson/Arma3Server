FROM debian:buster-slim

LABEL maintainer="Brett - github.com/synixebrett"

RUN apt-get update
RUN apt-get install -y --no-install-recommends --no-install-suggests \
        python3 \
        lib32stdc++6 \
        lib32gcc1 \
        wget \
        ca-certificates
RUN apt-get remove --purge -y
RUN apt-get clean autoclean
RUN apt-get autoremove -y
RUN rm /var/lib/apt/lists/* -r
RUN mkdir -p /steamcmd \
        && cd /steamcmd \
        && wget -qO- 'https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz' | tar zxf -

ENV ARMA_CONFIG=main.cfg
ENV ARMA_PROFILE=main
ENV ARMA_WORLD=empty
ENV HEADLESS_CLIENTS=0
ENV PORT=2302

EXPOSE 2302/udp
EXPOSE 2303/udp
EXPOSE 2304/udp
EXPOSE 2305/udp
EXPOSE 2306/udp

ADD launch.py /launch.py

WORKDIR /arma3

VOLUME /steamcmd

STOPSIGNAL SIGINT

CMD ["python3","/launch.py"]
