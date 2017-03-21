FROM python:2
LABEL maintainer "louis@pydio.com"

ENV PYDIO_GIT_BRANCH 'materialUI'

WORKDIR /root

RUN apt-get update -q
RUN apt-get install --no-install-recommends -q -y \
      libzmq3-dev \
      apt-transport-https \
      git \
      curl \
    && curl -sL https://deb.nodesource.com/setup_7.x | bash - \
    && apt-get update -q && apt-get install -q -y nodejs

RUN git clone -b $PYDIO_GIT_BRANCH --recursive https://github.com/pydio/pydio-sync.git
WORKDIR /root/pydio-sync
RUN pip install -r src/pydio/sdkremote/requirements.txt
RUN pip install -r requirements.txt && python setup.py develop

WORKDIR /root/pydio-sync/src/pydio/ui
RUN npm install -g grunt-cli && npm install grunt && npm install && grunt
WORKDIR /root/pydio-sync/src/pydio

EXPOSE 5556
ENTRYPOINT ["python", "main.py"]
CMD ["--api_address", "0.0.0.0", "--api_user", "test", "--api_password", "test"]
