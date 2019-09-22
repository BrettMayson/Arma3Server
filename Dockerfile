FROM cm2network/steamcmd:root

LABEL maintainer="Dynulo"

RUN apt-get update
RUN apt-get install python3 -y
RUN apt-get clean
RUN rm /var/lib/apt/lists/* -r

ENV ARMA_CONFIG=main.cfg
ENV ARMA_PROFILE=main
ENV ARMA_WORLD=empty
ENV HEADLESS_CLIENTS=0

EXPOSE 2301/udp
EXPOSE 2302/udp
EXPOSE 2303/udp
EXPOSE 2304/udp
EXPOSE 2305/udp

ADD launch.py /launch.py

USER steam

WORKDIR /home/steam

STOPSIGNAL SIGINT

CMD ["python3","/launch.py"]
