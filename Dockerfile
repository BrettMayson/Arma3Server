FROM cm2network/steamcmd

LABEL maintainer="Dynulo"

RUN apt-get update
RUN apt-get install python3 -y
RUN apt-get clean
RUN rm /var/lib/apt/lists/* -r

RUN mkdir /arma3

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

WORKDIR /arma3

STOPSIGNAL SIGINT

CMD ["python3","/launch.py"]
