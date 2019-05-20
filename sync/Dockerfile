FROM gitstore

RUN apt update && apt -y install openssh-server cron
RUN pip install zc.lockfile
COPY merger /usr/local/bin/merger
COPY check-status /usr/local/bin/check-status
RUN ssh-keygen -t rsa -N "" -f /root/.ssh/id_rsa && cp /root/.ssh/id_rsa.pub /root/.ssh/authorized_keys
EXPOSE 5000 22
RUN echo "* * * * * root /usr/local/bin/check-status" >> /etc/crontab
RUN chown root.root -R /root/.ssh
CMD /etc/init.d/cron start && /etc/init.d/ssh start && /usr/local/bin/gitstore.py
