FROM bitnami/minideb:latest
LABEL description="A Docker container for GitStore" \
      version="0.1.0" \
      maintainer="sam@serotine.org"

RUN apt update && apt install -y python python-pygit2 python-pip git vim
RUN pip install flask
COPY gitstore.py /usr/local/bin/gitstore.py
COPY merger /usr/local/bin/merger
RUN chmod 755 /usr/local/bin/gitstore.py
RUN mkdir /srv/gitstore
EXPOSE 5000
CMD /usr/local/bin/gitstore.py
#CMD /bin/bash

