# A imagem de teste do Fedora 42: as dependências que o job `smoke-multi-distro` do ci.yml instala,
# já instaladas. Os testes exigem que o `RUN` abaixo seja o `install_cmd` da matriz do ci.yml.
FROM fedora:42
LABEL org.opencontainers.image.source="https://github.com/Hefesto-Team/hefesto-dualsense4unix"
RUN dnf install -y python3 python3-pip python3-gobject gtk3 hidapi libnotify gcc python3-devel kernel-headers git
RUN dnf clean all
