# A imagem do `ci-local.sh`: a do `act` para o Ubuntu do runner (o 26.04 do `ubuntu-latest` desde
# 10/2026; o 24.04 de quem o nomeia) mais o que o runner do GitHub traz
# e ela não. Cada linha nova daqui nasce de uma falha medida de «o runner tem, a imagem não»,
# com o job que a mostrou:
#   shellcheck      o job `shellcheck`: `shellcheck: command not found`, rc=127
#   python3-dev     o job `anonymity`: `Python.h: No such file` ao compilar o evdev do `.[dev]`
#   python3-yaml    o job `validate-manifest`: `No module named 'yaml'` no `python3` do sistema (o do runner o traz)
#   google-chrome   o job `anonymity`: o playwright lança `/usr/bin/google-chrome`, que o runner tem
ARG BASE=catthehacker/ubuntu:act-26.04-dev
FROM ${BASE}
RUN apt-get update \
    && apt-get install -y --no-install-recommends shellcheck python3-dev python3-yaml \
    && curl -fsSL -o /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/* /tmp/chrome.deb
