FROM python:2
LABEL maintainer "louis@pydio.com"

WORKDIR /root

RUN apt-get update -q
RUN apt-get install --no-install-recommends -q -y \
      libzmq3-dev \
      apt-transport-https \
      curl \
    && curl -sL https://deb.nodesource.com/setup_7.x | bash - \
    && apt-get update -q && apt-get install -q -y nodejs

COPY . /root
WORKDIR /root
RUN pip install -r src/pydio/sdkremote/requirements.txt
RUN pip install -r requirements.txt && python setup.py develop

WORKDIR /root/src/pydio/ui
RUN npm install -g grunt-cli && npm install grunt && npm install && grunt
WORKDIR /root/src/pydio



VOLUME ["/root/.local/share/Pydio/"]  # application data
VOLUME ["/workspace"]  # path for mounting workspaces

EXPOSE 5556
ENTRYPOINT ["python", "main.py"]
CMD ["--api_address", "0.0.0.0", "--api_user", "test", "--api_password", "test"]
