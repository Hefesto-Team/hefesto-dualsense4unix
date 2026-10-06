# A imagem de teste do Ubuntu 24.04 com o repositório do Pop!_OS por cima: o que o job
# `smoke-multi-distro` do ci.yml monta (primeiro as fontes do Pop, depois as dependências).
# Os testes exigem que o `RUN` das dependências seja o `install_cmd` da matriz do ci.yml.
# O contexto da construção é a raiz do repositório (o script das fontes vem de lá).
FROM ubuntu:24.04
LABEL org.opencontainers.image.source="https://github.com/Hefesto-Team/hefesto-dualsense4unix"
COPY scripts/ci/instalar_como_usuaria.sh /tmp/instalar_como_usuaria.sh
RUN bash /tmp/instalar_como_usuaria.sh --fontes pop --so-fontes
RUN apt-get update && apt-get install -y python3 python3-pip python3-gi gir1.2-gtk-3.0 libhidapi-hidraw0 libnotify-bin git
RUN rm -rf /var/lib/apt/lists/* /tmp/instalar_como_usuaria.sh
