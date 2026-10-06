# A imagem do `ci-local.sh`: a do `act` para o Ubuntu 24.04 mais o que o runner do GitHub traz
# e ela não. Cada linha nova daqui nasce de uma falha medida de «o runner tem, a imagem não»,
# com o job que a mostrou:
#   shellcheck      o job `shellcheck`: `shellcheck: command not found`, rc=127 (o 24.04 traz o 0.9.0, o do runner)
#   python3-dev     o job `anonymity`: `Python.h: No such file` ao compilar o evdev do `.[dev]`
#   google-chrome   o job `anonymity`: o playwright lança `/usr/bin/google-chrome`, que o runner tem
FROM catthehacker/ubuntu:act-24.04
RUN apt-get update \
    && apt-get install -y --no-install-recommends shellcheck python3-dev \
    && curl -fsSL -o /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/* /tmp/chrome.deb
