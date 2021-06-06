FROM python:3.8-slim
MAINTAINER Manfred Touron "m@42.am"

ADD . /app
WORKDIR /app
ENTRYPOINT ["python", "frosty.py"]
EXPOSE 80
