# A imagem de teste do Arch: as dependências que o job `smoke-multi-distro` do ci.yml instala, já
# instaladas. Os testes exigem que o `RUN` abaixo seja o `install_cmd` da matriz do ci.yml.
FROM archlinux:latest
LABEL org.opencontainers.image.source="https://github.com/Hefesto-Team/hefesto-dualsense4unix"
RUN pacman -Syu --noconfirm python python-pip python-gobject gtk3 hidapi libnotify python-evdev python-pydantic python-pydantic-core gcc linux-api-headers git
RUN pacman -Scc --noconfirm
