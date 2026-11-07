# A imagem do `ci-local.sh`: a do `act` para o Ubuntu do runner (o 26.04 do `ubuntu-latest` desde
# 10/2026; o 24.04 de quem o nomeia) mais o que o runner do GitHub traz
# e a imagem não. Cada linha nova daqui nasce de uma falha medida de «o runner tem, a imagem não»,
# com o job que a mostrou:
#   shellcheck      o job `shellcheck`: `shellcheck: command not found`, rc=127
#   python3-dev     o job `anonymity`: `Python.h: No such file` ao compilar o evdev do `.[dev]`
#   python3-yaml    o job `validate-manifest`: `No module named 'yaml'` no `python3` do sistema (o do runner o traz)
#   google-chrome   o job `anonymity`: o playwright lança `/usr/bin/google-chrome`, que o runner tem
#   patchelf        os Pythons do `actions/python-versions` nascem com RUNPATH em /opt/hostedtoolcache: sem o conserto,
#                   `python3` em ambiente limpo sai com «libpython3.10.so.1.0: cannot open shared object file»
#   sound-theme-freedesktop  o `gtk-real`: sem o arquivo do som, `tocar_confirmacao` para antes de acordar o canal
#   xvfb            o `lint-test`: a guarda da tela em tests/conftest.py recusa sem `Xvfb` (rc=1), que o runner traz
#   runner          o `gtk-real`: 42 arquivos reprovavam só como root (`id -u`=0); o GitHub roda como `runner`, uid 1001
#   os Pythons      `mapa-de-canais` e `lint-test`: o runner os traz no cache de ferramentas; sem isso o setup-python
#                   busca o manifesto a cada job, e o manifesto cortado no meio sai 0 sem Python nenhum. A pasta não é
#                   a /opt/hostedtoolcache porque o `act` monta ali o volume `act-toolcache`. A lista
#                   cobre toda versão que um workflow pede (a régua em tests/unit/test_o_ci_de_casa_e_o_do_github.py).
ARG BASE=catthehacker/ubuntu:act-26.04-dev
FROM ${BASE}
RUN apt-get update \
    && apt-get install -y --no-install-recommends shellcheck python3-dev python3-yaml sound-theme-freedesktop patchelf xvfb \
    && curl -fsSL -o /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get install -y --no-install-recommends /tmp/chrome.deb \
    && rm -rf /var/lib/apt/lists/* /tmp/chrome.deb
ENV FERRAMENTAS_DO_RUNNER=/opt/ferramentas-do-runner PYTHONS_DO_RUNNER="3.10 3.11 3.12"
COPY runner-do-github.sh /usr/local/sbin/runner-do-github.sh
RUN bash /usr/local/sbin/runner-do-github.sh "$FERRAMENTAS_DO_RUNNER" $PYTHONS_DO_RUNNER
ENV USER=runner RUNNER_USER=runner AGENT_TOOLSDIRECTORY=/opt/ferramentas-do-runner RUNNER_TOOL_CACHE=/opt/ferramentas-do-runner
USER runner
