FROM ubuntu:24.04

ENV DEBIAN_FRONTEND noninteractive

RUN apt-get update && apt-get -y upgrade && \
    apt-get -y install python3.10 && \
    apt update && apt install python3-pip -y

RUN apt-get --no-install-recommends install libreoffice -y
RUN apt-get install -y libreoffice-java-common

RUN apt-get install -y unoconv

RUN python3 -m pip config set global.break-system-packages true

ADD requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt

ARG CACHEBUST=1


CMD ["python3", "--version"]