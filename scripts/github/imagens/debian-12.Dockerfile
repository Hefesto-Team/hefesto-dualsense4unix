# A imagem de teste do Debian 12: as dependências que o job `smoke-multi-distro` do ci.yml instala,
# já instaladas. Os testes exigem que o `RUN` abaixo seja o `install_cmd` da matriz do ci.yml.
FROM debian:12
LABEL org.opencontainers.image.source="https://github.com/Hefesto-Team/hefesto-dualsense4unix"
RUN apt-get update && apt-get install -y python3 python3-pip python3-gi gir1.2-gtk-3.0 libhidapi-hidraw0 libnotify-bin git
RUN rm -rf /var/lib/apt/lists/*
