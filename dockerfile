FROM python:alpine

LABEL version="1.0"
LABEL maintainer="David AUFFRAY"
LABEL databases="redis"
LABEL project="sysbus"

ENV URL_LIVEBOX http://192.168.1.1/
ENV USER_LIVEBOX admin
ENV PASSWORD_LIVEBOX Au7da5yz
ENV VERSION_LIVEBOX lb3

WORKDIR /root/

COPY sysbus.py /root/
COPY requirements.txt /root/

RUN apk update
RUN pip3 install -r /root/requirements.txt

CMD [ "python3","sysbus.py" ]