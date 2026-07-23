FROM ubuntu:24.04

ARG LAB_PUBLIC_KEY

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
       ca-certificates curl nginx openssh-server python3 sudo \
    && useradd --create-home --shell /bin/bash lab \
    && printf 'lab ALL=(ALL) NOPASSWD:ALL\n' > /etc/sudoers.d/lab \
    && chmod 0440 /etc/sudoers.d/lab \
    && install --directory --owner=lab --group=lab --mode=0700 /home/lab/.ssh \
    && printf '%s\n' "$LAB_PUBLIC_KEY" > /home/lab/.ssh/authorized_keys \
    && chown lab:lab /home/lab/.ssh/authorized_keys \
    && chmod 0600 /home/lab/.ssh/authorized_keys \
    && mkdir /run/sshd \
    && rm -rf /var/lib/apt/lists/*

EXPOSE 22 80

CMD ["/usr/sbin/sshd", "-D", "-e"]
