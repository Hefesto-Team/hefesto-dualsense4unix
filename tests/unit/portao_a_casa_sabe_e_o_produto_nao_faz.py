"""O portão da PROMESSA SEM CAMINHO — ``A-CASA-SABE-E-O-PRODUTO-NAO-FAZ-01``.

O defeito-mãe desta casa não é o código errado: é a cura ESCRITA e nunca
LIGADA. Ele já tem nome (``test_perfil_salva_tudo_cobertura_das_secoes.py``:24),
já tem cor no mapa de canais (``scripts/gerar-mapa.py``, ``--color-lacuna``) e já
teve inventário (a sprint A NOITE DOS QUATRO INVENTÁRIOS, 09/08/2026). Só não
tinha portão. Este é o portão.

A PERGUNTA NÃO É "isto é uma cura?" — essa não tem resposta mecânica, e tentar
respondê-la por convenção de nome foi medido e reprovado em 12/08/2026: 525
apelidos únicos em ``src/``, 276 deles sem nenhum arquivo em ``docs/``,
misturando ``BUG-*`` já consertado, ``AUDIT-FINDING-*``, ``FEAT-*`` e frases
inteiras. Um apelido é CITAÇÃO, não DECLARAÇÃO, e não diz do que a cura precisa.

A pergunta é: **o produto promete isto, e existe caminho de produção que o
alcance?** Promessa é uma de duas coisas, ambas com sítio de declaração e ambas
enumeráveis por varredura:

- **P3a — INTERRUPTOR**: uma env ``HEFESTO_*`` que o produto LÊ. O produto
  promete que isto pode ser ligado. O caminho é qualquer porta que a ESCREVA —
  ``install.sh``, uma unit de ``assets/``, um empacotamento, ou a janela.
  **Basta UMA**, nunca a conjunção;
- **P3b — SÍMBOLO**: uma função ou classe pública de módulo em ``src/``. O
  produto promete que isto FAZ algo. O caminho é **alcance a partir dos PONTOS
  DE ENTRADA declarados** (``_PONTOS_DE_ENTRADA``), andando pelo grafo de
  ``import``, com o nome resolvido ao **MÓDULO de origem**: ``from x.y import
  f`` seguido de ``f()`` conta para ``x.y::f``, e para mais nada. Conta também
  o **Python embutido em heredoc** do ``install.sh``/``uninstall.sh``, que é
  ponto de entrada como qualquer outro.

  A porta do heredoc nasceu em 13/08/2026, e nasceu de o portão ter errado: a
  varredura só lia ``*.py`` e por isso acusava de órfã a ``strip_quirks_token``,
  que o ``uninstall.sh``:1243 chama desde julho, dentro de um
  ``python3 - "${ROOT_DIR}" <<'PYEOF'``. Um portão que acusa de dívida quem está
  certo é pior que portão nenhum: ensina a próxima pessoa a não acreditar nele.

``tests/`` NUNCA conta como caminho, e é essa linha que separa as curas soltas
do resto da árvore: REMEDIDO em 22/08/2026, 52 dos 60 símbolos que este portão
acusa hoje têm chamador em ``tests/`` e nenhum em produção — pareciam
entregues.

E a conjunção "install E GUI" está deliberadamente FORA daqui: ela é FALSA para
quase toda a dívida. ``ExternalMaskRegistry`` quer GUI e não quer install;
``stop_ipc`` não quer nenhuma das duas, quer um chamador. Portão que exige as
duas portas grita trinta vezes com três razões, e é desligado na primeira
semana.

POR QUE É UM TESTE, E NÃO UM ``scripts/check_*.sh``
---------------------------------------------------
Três razões, e a terceira é medida:

1. o miolo é varredura de AST sobre 171 arquivos mais um registro de lacunas
   com razão escrita — e o molde que esta casa já tem para exatamente isso
   (``_SEM_ESCRITOR_HOJE``, em ``test_perfil_salva_tudo_cobertura_das_secoes``)
   é um teste;
2. quem precisa vê-lo reprovar é quem ACABOU de escrever um símbolo público
   novo. Essa pessoa roda a suíte; ela não roda, uma a uma, as onze linhas de
   portão do ``CLAUDE.md``;
3. um portão em ``scripts/`` precisa de um job no CI **e** de um hook no
   pre-commit para existir, e os dois podem ser desligados sem tocar no portão
   — foi por isso que a ``PORTÃO-VIVO-01`` teve de nascer. O caso medido está
   ao lado: ``scripts/check_paridade_transporte.py`` é ``continue-on-error`` no
   ci.yml e, MEDIDO em 12/08/2026 no commit c30c4a2, reprova em 15 linhas e
   avisa em outras 13 sem que nada mude. Um teste da suíte não tem esse botão:
   para desligá-lo é preciso apagar o arquivo, e isso aparece no diff.

O QUE ESTE PORTÃO **NÃO** VIGIA, e por quê (decisões medidas, não descuido)
---------------------------------------------------------------------------
- **Constantes de módulo.** Medi em 12/08/2026: incluí-las levaria a acusação de
  33 para 59, e as 26 a mais são majoritariamente VOCABULÁRIO DE PROTOCOLO —
  ``SAIDA_ESTEREO_NO_FONE``, ``VALID_FLAG0_LEFT_TRIGGER_FFB``, ``BLOCO_HAPTICS``
  — nomes que existem para serem escritos por quem lê a canônica e que não têm
  chamador POR DESENHO. Uma constante é um VALOR, não um comportamento; a
  promessa da classe (3) é "isto FAZ algo". Excluí-las dissolve a isenção de
  vocabulário de protocolo por construção, em vez de por lista de nomes.
  O PREÇO dessa escolha, declarado: o portão não vê
  ``daemon/subsystems/__init__.py::SUBSYSTEM_REGISTRY``, que o próprio docstring
  do módulo confessa na linha 13 (*"não é iterado por ninguém em produção"*),
  nem ``daemon/ipc_server.py::CODE_CONTROLLER_LOST`` e
  ``::CODE_CONTROLLER_DISCONNECTED``, que só existem no ``__all__``.
- **Métodos.** Pela mesma régua: um método não é sítio de promessa ao produto, é
  detalhe de uma classe que já é vigiada. Isso dissolve o CONTRATO DE PLUGIN
  (``plugin_api/plugin.py``:53-89, cujos ``on_*`` são chamados por terceiros)
  sem precisar de regra nenhuma — eles nunca entram na varredura. O preço:
  ``daemon/lifecycle.py::_stop_metrics``, que a frente B mediu, fica de fora.
  Mas o DEFEITO dele não escapa: os irmãos públicos do mesmo defeito —
  ``stop_ipc``, ``stop_udp``, ``stop_autoswitch`` — estão acusados abaixo, e são
  três instâncias que a varredura anterior não tinha visto.

AS QUATRO ARMADILHAS QUE A VARREDURA ANTERIOR CAIU, e como esta não cai
-----------------------------------------------------------------------
1. **Chamada por string** (``getattr``/despacho por nome) pegou a passada
   anterior CINCO vezes. Aqui, todo literal de texto de ``src/`` é quebrado em
   palavras e cada palavra conta como chamador. É por isso que ``_stop_bt_mic``
   (despachado em ``connection.py``:829) não aparece na lista.
   Corolário medido em 26/08/2026: uma promessa que ganha chamador de verdade
   SAI da lista sozinha — foi assim com ``app/fala_do_mapa.py::formata_pt_br``,
   que virou dono único da vírgula e cuja lápide teve de ser apagada no mesmo
   commit (``test_nenhuma_lapide_sobreviveu_a_propria_cura``).
2. **Uso dentro do próprio arquivo.** A regra proposta era "chamador fora do
   próprio arquivo": medi, e ela acusa **846** símbolos, porque a maioria dos
   auxiliares é usada no próprio módulo — e o módulo é produção QUANDO ele é
   alcançado. A régua de hoje é essa condição, escrita: chamador em qualquer nó
   de um módulo ALCANÇADO, menos o próprio símbolo (o "menos" impede que
   recursão e auto-citação satisfaçam o portão sozinhas).
3. **Docstring e ``__all__``.** Um símbolo citado só no próprio docstring, ou só
   na lista de reexportação, não é alcançado por ninguém. Ambos são descartados
   — e é por isso que ``RumbleEngine`` aparece aqui apesar de DUAS frases de
   comentário terem afirmado, por meses, que ele "segue em uso" e que uma rota
   inteira "depende" dele. Este portão foi a primeira coisa da árvore a
   discordar das duas; as duas foram substituídas pela informação certa (24/08 e
   26/08/2026), e ele continua aqui. O comentário não é chamador.
4. **Alvo de atribuição.** ``X = 1`` não é uso de ``X``. Contar o ``ast.Store``
   fazia toda constante se satisfazer com a própria linha de definição.

O QUE A RÉGUA PLANA PERDOAVA — SUBSTITUÍDA EM 22/08/2026
---------------------------------------------------------
Até 21/08/2026 a pergunta era plana: *existe algum chamador deste NOME em
``src/``, em ``scripts/`` ou num heredoc?* Ela perdoava duas coisas, e as duas
são a forma mais cara do defeito-mãe:

a. **corrente fechada em si mesma.** ``A`` chama ``B``, ``B`` chama ``A``, e
   ninguém de fora chama nenhum dos dois — os dois pareciam entregues. MEDIDO
   em 22/08/2026: o par ``integrations/prontuario_dos_jogos.py`` +
   ``integrations/api_de_entrada.py`` (19 símbolos) e
   ``profiles/curva_propria.py`` (3) passavam inteiros assim, e o
   ``SPRINT_ORDER.md`` já dizia, com outras palavras, que *"o prontuário não é
   consumido por ninguém"*;
b. **colisão de nome entre módulos.** ``prontuario_dos_jogos::Censo`` era
   perdoado por ``sentinela_do_wrapper.py``:302, que usa um ``Censo`` sem
   relação nenhuma com ele. Um nome não é um endereço.

A régua de hoje resolve as duas de uma vez: alcance a partir dos pontos de
entrada declarados, pelo grafo de ``import``, com o nome resolvido ao módulo.
Só dois idiomas continuam PLANOS, e por medição: o **literal de texto**
(despacho por ``getattr``, a armadilha 1) e o **atributo cuja base não é
módulo** (``obj.metodo()``, que a varredura não tem como resolver sem inferir
tipo). Contá-los planos custa perdão ocasional; não contá-los custaria acusar
quem está certo, que é o defeito que este portão não pode ter.

CONTAGEM da troca, MEDIDA em 22/08/2026: 33 acusações viraram 60. Nenhuma
saiu; as 27 que entraram são os 22 símbolos das três correntes fechadas acima
mais os cinco de ``hidraw_broker_client``, que perderam o perdão quando
``_TERRITORIOS_DE_PRODUCAO`` deixou de ser a pasta ``scripts/`` inteira. São
27 e não 28 porque o sexto símbolo que a pasta perdoava,
``curva_propria.py::gerar_tabela_markdown``, já está entre os 22: o módulo
inteiro dele é corrente fechada, e a régua de alcance o acusaria sozinha.
Todas estão classificadas abaixo, com endereço.

O CONTRATO DESTE ARQUIVO
-------------------------
O conjunto de acusações é DERIVADO em runtime. O que é escrito à mão é a
CLASSIFICAÇÃO de cada acusação, e ela é exaustiva: promessa nova sem caminho
reprova por estar **SEM CLASSIFICAÇÃO** — não por estar sem chamador. Essa
inversão é o que evita a denylist por prefixo, que fura calada. Só há dois
destinos, e os dois exigem razão escrita com data:

- ``_NAO_E_PROMESSA`` — não é promessa ao produto (instrumento de teste,
  diagnóstico, ou lápide com nota datada). Não é dívida;
- ``_SEM_CAMINHO_HOJE`` — é promessa, e o caminho não existe. É dívida.

Declarar é honesto e este portão não castiga honestidade (a ``ROTULOS-DE-SPRINT-01``
fixou que *um gate que castiga a honestidade é pior que gate nenhum*) — ele só
não deixa a lápide envelhecer calada: no dia em que o caminho nascer, a entrada
deixa de bater com a árvore e o portão cobra que ela seja APAGADA.
"""
from __future__ import annotations

import ast
import functools
import re
import shutil
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_SRC = _RAIZ / "src" / "hefesto_dualsense4unix"

#: Os PONTOS DE ENTRADA do produto — onde o alcance começa. Cada um traz a
#: FONTE que o declara, e ``test_todo_ponto_de_entrada_tem_fonte_viva`` confere
#: que a fonte ainda diz o que esta tabela afirma. Lista adivinhada apodrece
#: calada; lista com fonte conferida, não.
#:
#: ISTO SUBSTITUIU ``_TERRITORIOS_DE_PRODUCAO = ("scripts",)`` em 22/08/2026.
#: A nota antiga dizia que ``scripts/`` era território de produção *"porque o
#: instalador roda os helpers de lá"*. MEDIDO: o que o instalador roda de lá é
#: SHELL — ``install_udev.sh``, ``fix_wireplumber_default_source.sh``,
#: ``doctor.sh``. Nenhum ``.py`` de ``scripts/`` é rodado por instalador nem
#: COPIADO para fora do checkout (as 51 varreduras de ``scripts/**/*.py``
#: caíram todas em citação de comentário). O único Python copiado para fora é
#: ``broker/hidraw_broker.py`` — e ele está aqui embaixo, como ponto de
#: entrada. O que a pasta ``scripts/`` de fato guardava era a bancada: um
#: instrumento de bancada é da mesma espécie que ``tests/``, e ``tests/`` nunca
#: contou.
#:
#: PREÇO declarado dessa troca, MEDIDO em 22/08/2026: seis símbolos que a pasta
#: perdoava passaram a ser acusados (os cinco de ``hidraw_broker_client`` e o
#: ``gerar_tabela_markdown``) e estão classificados em ``_NAO_E_PROMESSA``.
_PONTOS_DE_ENTRADA: dict[str, tuple[str, str, str]] = {
    "cli/app.py": (
        "pyproject.toml",
        'hefesto-dualsense4unix = "hefesto_dualsense4unix.cli.app:main"',
        "console_script da CLI; é também o ExecStart da unit do daemon "
        "(assets/hefesto-dualsense4unix.service:22, `daemon start --foreground`)",
    ),
    "app/main.py": (
        "pyproject.toml",
        'hefesto-dualsense4unix-gui = "hefesto_dualsense4unix.app.main:main"',
        "console_script da janela; ExecStart de "
        "assets/hefesto-dualsense4unix-gui-hotplug.service:12",
    ),
    "__main__.py": (
        "src/hefesto_dualsense4unix/__main__.py",
        "from hefesto_dualsense4unix.cli.app import main",
        "`python -m hefesto_dualsense4unix` — a boca que não passa pelo wheel",
    ),
    "broker/hidraw_broker.py": (
        "install.sh",
        "src/hefesto_dualsense4unix/broker/hidraw_broker.py",
        "install.sh:1021 o COPIA para /usr/local/lib/hefesto-dualsense4unix/ "
        "(o .deb em scripts/build_deb.sh:323 e o flatpak em "
        "flatpak/br.andrefarias.Hefesto.yml:320 fazem o mesmo), e ele é o "
        "ExecStart de assets/systemd/hefesto-hidraw-broker.service:34",
    ),
    "integrations/sentinela_do_wrapper.py": (
        "install.sh",
        "src/hefesto_dualsense4unix/integrations/sentinela_do_wrapper.py",
        "install.sh:3367 substitui __SENTINELA__ na unit, cujo ExecStart é "
        "`python3 __SENTINELA__ --reparar` "
        "(assets/hefesto-steam-input-guard.service:29); o doctor.sh:1643 "
        "também o roda",
    ),
    "integrations/steam_input_ponte.py": (
        "scripts/disable_steam_input.sh",
        "integrations/steam_input_ponte.py",
        "roda como `python3 ${PONTE_PY} --ligar` em "
        "scripts/disable_steam_input.sh:283+298, e esse roteiro é o ExecStart "
        "de assets/hefesto-steam-input-guard.service:14 (install.sh:3368)",
    ),
    "integrations/steam_launch_options.py": (
        "install.sh",
        "src/hefesto_dualsense4unix/integrations/steam_launch_options.py",
        "install.sh:3395 o roda com `--migrate`; uninstall.sh:1467 o roda para "
        "tirar o wrapper; doctor.sh:1862 o publica como cura",
    ),
    "integrations/proton_pin.py": (
        "install.sh",
        "src/hefesto_dualsense4unix/integrations/proton_pin.py",
        "install.sh:3542 e uninstall.sh:1444 o rodam; doctor.sh:3339 também",
    ),
    "integrations/exame_da_mesa.py": (
        "scripts/doctor.sh",
        "src/hefesto_dualsense4unix/integrations/exame_da_mesa.py",
        "scripts/doctor.sh:3300 o roda — e o install.sh:3608 roda o doctor",
    ),
}

#: Roteiros de shell que EMBUTEM Python de produção. Não é caso de borda nem
#: gambiarra: é a política desta casa — *"quem DECIDE é o módulo puro
#: integrations/kernel_cmdline.py (100% stdlib, testável); aqui só traduzimos o
#: plano"* (install.sh:1592-1593). O instalador e o desinstalador abrem um
#: ``python3 - "${ROOT_DIR}" <<'PYEOF'`` (install.sh:1596, uninstall.sh:1150)
#: que importa o módulo e chama as funções dele.
#:
#: Esse Python É produção: roda na máquina dela, com ``sudo``, mexendo na linha
#: de comando do kernel. A varredura só olhava ``*.py`` (``_modulos``) e por
#: isso acusava de órfã a ``strip_quirks_token``, que o desinstalar chama.
#: MEDIDO em 13/08/2026.
_ROTEIROS_DE_PRODUCAO = ("install.sh", "uninstall.sh")

#: Abertura de heredoc alimentando um interpretador Python — ``python3 - <<'EOF'``,
#: ``python <<EOF``, ``sudo python3 - "$X" <<-'PY'``. O delimitador é CAPTURADO
#: para que o fechamento procurado seja o do próprio heredoc, e não o primeiro
#: ``EOF`` que aparecer no roteiro (um script tem vários, de coisas diferentes).
_HEREDOC_PYTHON = re.compile(
    r"""\bpython3?\b[^\n<]*<<-?\s*(['"]?)([A-Za-z_][A-Za-z0-9_]*)\1\s*$"""
)

#: Portas capazes de LIGAR um interruptor de ambiente. Basta UMA.
_PORTAS_DE_AMBIENTE: dict[str, tuple[str, ...]] = {
    "install": ("install.sh", "uninstall.sh"),
    "unit": ("assets",),
    "empacotamento": ("packaging", "flatpak"),
    "janela": (
        "src/hefesto_dualsense4unix/app",
        "src/hefesto_dualsense4unix/gui",
    ),
}


# ===========================================================================
# P3a — O INTERRUPTOR SEM MÃO
# ===========================================================================

#: Interruptores que NÃO são promessa à usuária: chave de teste, de depuração
#: ou de ajuste fino que ninguém liga em produção. Cada uma com a razão — e a
#: razão é o que permite a próxima pessoa discordar com conhecimento de causa.
#: Interruptor novo que ninguém classificar reprova por estar SEM CLASSIFICAÇÃO.
_INSTRUMENTO_DE_AMBIENTE: dict[str, str] = {
    "HEFESTO_BROKER_SOCKET": (
        "Endereço do socket do broker de hidraw. Não é escolha dela: é ponto de "
        "injeção para o teste apontar o cliente a um socket de mentira "
        "(integrations/hidraw_broker_client.py:49). Em produção o caminho vem "
        "do XDG. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_CARONA_WRAPPER": (
        "Desliga a carona do wrapper da Steam (app/actions/carona_do_wrapper.py:186). "
        "A razão está escrita na seção `O DESLIGADOR, e por que ele existe` do "
        "próprio módulo, em maiúsculas: `Ele NÃO é uma flag de produto — a regra "
        "da casa é toda cura entra no install, sem flag, e em produção a carona "
        "está sempre ligada`. Ausente = LIGADA, e é isolamento de suíte: a suíte "
        "roda na máquina DELA e um teste de GUI que chamasse `Salvar` com a "
        "carona ligada varreria o `localconfig.vdf` REAL. Quem a desliga é o "
        "`tests/conftest.py`:1197, em todo teste. MEDIDO em 18/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_ASSETS_DIR": (
        "Onde procurar os arquivos de `assets/` (daemon/service_install.py:49). "
        "Existe para o teste e para a execução a partir do fonte não dependerem "
        "de instalação; em produção o caminho é derivado do pacote. Não abre "
        "feature nenhuma. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_COMPACT_WINDOW": (
        "Abre a janela compacta, que app/app.py:1224 declara não aparecer por "
        "padrão. É superfície experimental de desenho, não escolha publicada — "
        "quando ela virar escolha, sai daqui e vira promessa. MEDIDO em "
        "12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_FAKE": (
        "Sobe o daemon com controle de mentira (daemon/main.py:18 e :113). É a "
        "chave que permite a suíte inteira rodar sem aparelho na mesa. Ligá-la "
        "em produção seria o defeito, não a cura. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_FAKE_TRANSPORT": (
        "Diz ao controle de mentira se ele deve fingir cabo ou Bluetooth "
        "(daemon/main.py:21). Irmã da chave FAKE e sem sentido fora dela — é "
        "instrumento de bancada. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_INIT_TIMEOUT_SEC": (
        "Ajuste fino do tempo de espera da inicialização do backend "
        "(core/backend_pydualsense.py:201). Número de calibração, não escolha "
        "dela: não há nada na tela que ela reconheceria como esta chave. "
        "MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME": (
        "Nome do socket de IPC (utils/xdg_paths.py:16). Isola instâncias "
        "paralelas em teste; o applet do COSMIC apenas LÊ a chave "
        "(packaging/cosmic-applet/src/ipc.rs:54) para achar o mesmo socket. "
        "Ninguém a liga como feature. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_LEDS_ROOT": (
        "Raiz falsa de `/sys/class/leds` (core/external_leds.py:39 e "
        "core/sysfs_leds.py:31). Existe para o teste ter um sysfs de mentira "
        "sob si; em produção a raiz é fixa. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_LOG_FORMAT": (
        "Formato do log (utils/logging_config.py:59). Chave de diagnóstico de "
        "quem lê log, não superfície de produto — não muda o que o aparelho faz. "
        "MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_LOG_LEVEL": (
        "Verbosidade do log (utils/logging_config.py:58). Mesma família da "
        "anterior: instrumento de quem investiga um defeito, e o caminho "
        "publicado para investigar é o `doctor`, não esta chave. MEDIDO em "
        "12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_METRICS_PORT": (
        "Porta do servidor de métricas (daemon/subsystems/metrics.py:48). É "
        "parâmetro do instrumento cujo INTERRUPTOR é `..._METRICS_ENABLED` — "
        "afinar a porta sem poder ligar o servidor não é promessa; a promessa "
        "está declarada como lacuna na chave ENABLED. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_NICE": (
        "Prioridade de escalonamento do processo do daemon (daemon/main.py:84). "
        "Ajuste de operação, não escolha publicada: a unit é quem decidiria "
        "isso, e decide por outros meios. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_NOTIFY_THROTTLE_SEC": (
        "Intervalo mínimo entre notificações repetidas "
        "(integrations/desktop_notifications.py:48). Calibração do instrumento "
        "de notificação; a promessa é a chave `..._DESKTOP_NOTIFICATIONS`, que "
        "está declarada como lacuna. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT": (
        "Desliga a detecção de janela em foco (cli/app.py:309, "
        "profiles/autoswitch.py:150). Existe para o teste do autoswitch não "
        "depender de um compositor vivo, e para a CLI poder rodar num shell sem "
        "sessão gráfica. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_NO_XWAYLAND": (
        "Faz a janela não tentar XWayland (app/main.py:30). Contorno de "
        "ambiente para rodar sob Xvfb e sob compositor sem XWayland — é a "
        "armadilha 2 do COMO-OLHAR-A-TELA, não uma escolha dela. MEDIDO em "
        "12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_PLUGINS_DIR": (
        "Onde procurar plugins (daemon/subsystems/plugins.py:157). Aponta o "
        "carregador a um diretório de mentira no teste; em produção o diretório "
        "é o do XDG. O INTERRUPTOR dos plugins é `..._PLUGINS_ENABLED`, que é "
        "outra chave. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_POLL_HZ": (
        "Frequência do laço de poll (daemon/main.py:92). Já é escolha publicada "
        "por OUTRA porta — `--poll-hz` do subcomando `daemon start` "
        "(cli/app.py:295). A env é o atalho de bancada para o mesmo número. "
        "MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS": (
        "Quantos milissegundos seguram o PS para contar como pressão longa "
        "(daemon/main.py:98). Calibração de gesto; afinada por quem mede, não "
        "escolhida por quem usa. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_PS_TOQUE_CURTO_TETO_MS": (
        "O TETO de duração do toque curto do PS "
        "(integrations/hotkey_daemon.py::_teto_do_toque_curto_do_ambiente). "
        "Irmã da PS_LONG_PRESS_MS acima e da mesma natureza: calibração de "
        "gesto, afinada por quem mede. Não abre feature nenhuma — o teto já "
        "nasce LIGADO em 700 ms, que é o que separa o toque humano (80-250 ms) "
        "do gesto de religar o controle no rádio (5.038 ms medidos no journal "
        "dela). Quem não a define recebe o comportamento certo; `=0` desliga o "
        "teto, que é a escolha de quem quer o comportamento anterior de volta. "
        "MEDIDO em 26/08/2026 (PS-TOQUE-CURTO-01, E1)."
    ),
    "HEFESTO_DUALSENSE4UNIX_REPORT_THROTTLE_SEC": (
        "Intervalo mínimo entre escritas de report de saída "
        "(core/backend_pydualsense.py:214). Número de calibração do transporte, "
        "medido com o aparelho na mão; não é superfície de escolha. MEDIDO em "
        "12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_RESET_TRAY_WARNING": (
        "Faz o aviso da bandeja ser emitido de novo (app/tray.py:273). Existe "
        "para reencenar um aviso já visto durante uma medição de tela; o "
        "caminho publicado é apagar o arquivo de estado. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED": (
        "Pula a semeadura dos perfis de fábrica (profiles/loader.py:94). Existe "
        "para o teste começar de um diretório de perfis vazio; em produção a "
        "semeadura é justamente o que se quer. MEDIDO em 12/08/2026."
    ),
}

#: Interruptores que SÃO promessa à usuária: abrem uma feature que ela pode
#: querer. Cada um precisa de UMA porta que o ligue — ou de uma lacuna
#: declarada em ``_SEM_MAO_HOJE``.
_PROMESSA_DE_AMBIENTE: dict[str, str] = {
    "HEFESTO_VARIANTE": (
        "Escolhe QUAL Hefesto este processo é — o estável dela ou o de "
        "desenvolvimento (utils/identidade.py:atual). Dela sai a casa inteira: "
        "config, perfis, socket, unit, WM_CLASS e ícone. É promessa dela, "
        "pedida em 29/08/2026 (*'Ele é instalado como OUTRO APP com a logo "
        "alterada em dev'*). MEDIDO em 29/08/2026: LIGADA, por `Environment=` "
        "na unit e por `export` no lançador, os dois escritos por "
        "`install-dev.sh`. Ausente = o app dela, com todos os literais de "
        "antes — `test_identidade_das_duas_casas.py` trava isso."
    ),
    "HEFESTO_BROKER_ALLOWED_UID": (
        "Qual UID pode falar com o broker de hidraw (broker/hidraw_broker.py:76). "
        "É promessa de sistema: sem ela o broker não serve a sessão dela. "
        "MEDIDO em 12/08/2026: LIGADA, por `Environment=` em "
        "assets/systemd/hefesto-hidraw-broker.service:37, com o UID substituído "
        "pelo instalador."
    ),
    "HEFESTO_DUALSENSE4UNIX_BT_MIC": (
        "Liga o microfone por Bluetooth para TODOS os controles "
        "(daemon/subsystems/bt_mic.py::habilitado_por_env). É feature dela. "
        "REMEDIDO em 22/08/2026 (QUATRO-MICROFONES-01): a FEATURE ganhou mão — "
        "o interruptor por controle da aba Configurações —, e a env virou o "
        "atalho à mão. Ver `_MAO_FORA_DO_AMBIENTE`."
    ),
    "HEFESTO_DUALSENSE4UNIX_DESKTOP_NOTIFICATIONS": (
        "Liga as notificações de desktop "
        "(integrations/desktop_notifications.py:224). É feature dela — bateria "
        "baixa, perfil ativado. MEDIDO em 12/08/2026: sem mão."
    ),
    "HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED": (
        "Declara que ela QUER o DualSense como microfone padrão do sistema "
        "(core/system_check.py:54), e com isso cala o alarme do doctor. É "
        "escolha dela por definição. MEDIDO em 12/08/2026: sem mão."
    ),
    "HEFESTO_DUALSENSE4UNIX_KEYBOARD_EMULATION": (
        "Liga/desliga o teclado emulado (daemon/main.py:108). É feature dela e "
        "o próprio comentário de :104 escreve a precedência: default < esta env "
        "< o `keyboard_emulation.flag`, que é a decisão DELA. MEDIDO em "
        "12/08/2026: LIGADA — não pela env, e sim pelo companheiro declarado em "
        "`_MAO_FORA_DO_AMBIENTE`."
    ),
    "HEFESTO_DUALSENSE4UNIX_METRICS_ENABLED": (
        "Liga o servidor HTTP de métricas (daemon/subsystems/metrics.py:47). "
        "Publicar métricas é escolha de quem instala. REMEDIDO em 22/08/2026: "
        "sem mão — nenhum `Environment=` em assets/, e o install.sh não menciona "
        "METRICS. Fora de src/ a chave aparece em OITO lugares e nenhum deles a "
        "ESCREVE, que é o que importa para este portão: README.md, CHANGELOG.md, "
        "docs/adr/016, docs/usage/metrics.md, o sprint DOC-QUE-NAO-MENTE-03 de "
        "03/08, tests/unit/test_metrics.py, este arquivo, e o %changelog do "
        "pacote Fedora (packaging/fedora/hefesto-dualsense4unix.spec, entrada "
        "`1:0.7.0-1`). O endereço é a ENTRADA do changelog e não a linha, de "
        "propósito: o %changelog cresce por cima, e o ponteiro por número de "
        "linha já apodreceu duas vezes em dez dias."
    ),
    "HEFESTO_DUALSENSE4UNIX_PLUGINS_ENABLED": (
        "Liga o carregamento de plugins (daemon/subsystems/plugins.py:194). É "
        "feature dela: sem isto, plugin instalado não roda. MEDIDO em "
        "12/08/2026: sem mão."
    ),
    "HEFESTO_DUALSENSE4UNIX_SYSTEM_WARNINGS_NOTIFY": (
        "Faz os avisos de infraestrutura do boot virarem notificação de desktop "
        "(daemon/lifecycle.py:3141). É escolha dela: receber ou não o aviso na "
        "tela. MEDIDO em 12/08/2026: sem mão."
    ),
}

#: A mão de uma feature nem sempre é a env: às vezes a env é só o atalho, e
#: quem de fato liga a feature é um COMPANHEIRO — um arquivo de estado, um
#: campo de config. Declarar o companheiro pelo nome é o que impede esta saída
#: de virar desculpa: o portão confere que o símbolo declarado EXISTE e que ele
#: próprio não é uma promessa sem caminho. Companheiro que apodrecer derruba a
#: env junto.
_MAO_FORA_DO_AMBIENTE: dict[str, tuple[str, str]] = {
    "HEFESTO_DUALSENSE4UNIX_KEYBOARD_EMULATION": (
        "utils/session.py::save_keyboard_emulation",
        "MEDIDO em 12/08/2026: a env é o degrau do MEIO de uma precedência de "
        "três, escrita em daemon/main.py:104 — default da dataclass (True) < "
        "esta env < `keyboard_emulation.flag`. Quem grava o flag é "
        "`save_keyboard_emulation`, e ele É chamado em produção "
        "(daemon/lifecycle.py:1481-1485, dentro de `set_keyboard_emulation`, na "
        "borda que alterna o teclado em runtime — o endereço era :1300 e caducou; "
        "RECONFERIDO em 26/08/2026, quando a frente da poda o mediu de novo "
        "JUSTAMENTE para saber se podia apagá-lo. Não pode: tem chamador vivo). "
        "Logo a FEATURE tem mão — a env é o atalho de quem quer forçar o degrau "
        "do meio sem gravar decisão nenhuma no disco dela.",
    ),
    "HEFESTO_DUALSENSE4UNIX_BT_MIC": (
        "daemon/subsystems/bt_mic.py::uniqs_declarados",
        "REMEDIDO em 22/08/2026 (QUATRO-MICROFONES-01), e esta entrada é a "
        "cura da lápide que estava aqui: até 22/08 o campo companheiro era "
        "`DaemonConfig.bt_mic_enabled`, um `bool` lido por três lugares e "
        "escrito por NENHUM. Ele saiu. O gate agora é `bt_mic_uniqs`, uma FONTE "
        "chamável que `daemon/lifecycle.py::Daemon.run` fia com "
        "`uniqs_declarados(self._maquina)` — e quem escreve o `maquina.json` é "
        "o interruptor por controle de "
        "`app/actions/config/secao_controles.py::_BlocoDoMicrofone`, gravado "
        "pelo `machine.declare` no 'Aplicar'. A env continua sem porta que a "
        "escreva, e continua certo que continue: ela liga a mesa INTEIRA, e a "
        "decisão dela de 22/08 é *'por controle'*.",
    ),
}

#: Interruptores de feature que NADA liga hoje, com o endereço da lacuna e o
#: que a fecharia. Quem entregar a cura APAGA a entrada, e é essa a única
#: manutenção.
_SEM_MAO_HOJE: dict[str, str] = {
    "HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED": (
        "MEDIDO em 12/08/2026, e este é o achado mais desconfortável da lista, "
        "porque a porta parece existir e não existe: `install.sh` TEM a opção "
        "`--keep-dualsense-mic` (declarada em :157, tratada em :260) e ela só "
        "faz `WITH_WIREPLUMBER_FIX=0`. A env nunca é escrita — a única "
        "ocorrência dela no instalador é o COMENTÁRIO de :227, que diz à "
        "usuária `ou export HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED=1`, "
        "isto é, manda ela fazer à mão o que o instalador poderia ter feito. "
        "CONSEQUÊNCIA: quem instala com `--keep-dualsense-mic` continua ouvindo "
        "o doctor alarmar que o DualSense virou a fonte padrão, e continua "
        "sendo aconselhado a rodar `doctor --fix`, que desfaria a escolha que "
        "ela acabou de fazer. Duas metades da mesma decisão, sem fio entre elas. "
        "O QUE A FECHA: `--keep-dualsense-mic` gravar a env na unit (ou no "
        "estado local que o doctor lê). É a lacuna desta lista com o caminho "
        "mais óbvio — e mesmo assim não a fecho, porque tocar no instalador não "
        "foi pedido e o passo tem de ser provado por ciclo uninstall→install."
    ),
    "HEFESTO_DUALSENSE4UNIX_PLUGINS_ENABLED": (
        "MEDIDO em 12/08/2026: nenhuma porta escreve a env, e o campo "
        "companheiro `DaemonConfig.plugins_enabled` (daemon/lifecycle.py:213) é "
        "só um default `False` com leitores — subsystems/plugins.py:195 lê os "
        "dois em OU e nenhum dos dois tem escritor. Então o subsistema de "
        "plugins não sobe nunca, por caminho nenhum. "
        "O EFEITO EM CASCATA, e é o que torna esta entrada cara: o "
        "`plugin_api/` inteiro é contrato PÚBLICO para terceiros — `on_tick`, "
        "`on_button_down`, `on_battery_change`, `on_profile_change` — e quem "
        "escrever um plugin contra esse contrato hoje não tem como fazê-lo "
        "rodar sem editar variável de ambiente à mão. O `cli/cmd_plugin.py` "
        "existe, com `list` e `reload`, e avisa no docstring que `requer daemon "
        "em execução com plugins_enabled=True`. "
        "O QUE A FECHA: um interruptor na janela ou `Environment=` na unit. É "
        "DECISÃO DELA: plugins de terceiros rodando por padrão é escolha de "
        "segurança, não de conveniência, e não é minha para tomar."
    ),
    "HEFESTO_DUALSENSE4UNIX_DESKTOP_NOTIFICATIONS": (
        "MEDIDO em 12/08/2026: zero ocorrências em install.sh, assets/, "
        "packaging/, flatpak/ e em toda a janela (app/ e gui/). A cura das "
        "notificações está inteira e desligada: `notify_battery_low` e "
        "`notify_battery_recovered` estão logo abaixo, na lista de símbolos sem "
        "caminho, pelo mesmo motivo. "
        "O QUE A FECHA: um interruptor na janela, porque notificação é "
        "incômodo pessoal e o padrão certo depende de quem usa; ou "
        "`Environment=` na unit se a decisão for que nasce ligada. Não fecho "
        "por conta própria: ligar notificação que ninguém pediu é o oposto de "
        "uma cura."
    ),
    "HEFESTO_DUALSENSE4UNIX_METRICS_ENABLED": (
        "REMEDIDO em 22/08/2026: ninguém ESCREVE a chave — nenhum "
        "`Environment=` em assets/, nada no install.sh. O %changelog do pacote "
        "Fedora (packaging/fedora/hefesto-dualsense4unix.spec, entrada "
        "`1:0.7.0-1`) a ANUNCIA sem escrevê-la, que é exatamente a forma de "
        "promessa que este portão existe para acusar. Ela é citada em outros "
        "sete lugares fora de src/ (README.md, CHANGELOG.md, ADR-016, "
        "docs/usage/metrics.md, o sprint DOC-QUE-NAO-MENTE-03, "
        "tests/unit/test_metrics.py e este arquivo), e citar não é escrever. "
        "O campo irmão "
        "`DaemonConfig.metrics_enabled` também só tem leitor (metrics.py:389). "
        "O QUE A FECHA: `Environment=` na unit ou uma opção do instalador. "
        "ATENÇÃO ao decidir: enquanto ninguém liga isto, o `MetricsSubsystem` "
        "nunca sobe — e é essa a razão de o defeito irmão (o subsystem que "
        "ninguém PARA no shutdown) nunca ter sido observado numa máquina viva."
    ),
    "HEFESTO_DUALSENSE4UNIX_SYSTEM_WARNINGS_NOTIFY": (
        "MEDIDO em 12/08/2026: nenhuma porta a escreve. O daemon calcula os "
        "avisos de infraestrutura no boot, escreve cada um no log "
        "(lifecycle.py:3138) e então descarta a notificação porque a chave está "
        "vazia — o trabalho é feito e jogado fora. "
        "O QUE A FECHA: a mesma decisão da chave `..._DESKTOP_NOTIFICATIONS`, e "
        "as duas deviam ser decididas juntas: um interruptor só de "
        "'me avise na tela' cobre as duas, e dois interruptores separados para "
        "a mesma pergunta é superfície a mais na janela dela."
    ),
}


# ===========================================================================
# P3b — A PROMESSA PÚBLICA SEM CAMINHO
# ===========================================================================

#: Acusações que NÃO são promessa ao produto. Instrumento de teste, ferramenta
#: de diagnóstico, ou lápide com nota datada — nenhuma delas deve um chamador.
#: Não é dívida: é classificação. A razão CITA a evidência que a sustenta,
#: porque "confie em mim" não é razão.
_NAO_E_PROMESSA: dict[str, str] = {
    "app/ipc_bridge.py::mic_volume_set": (
        "MEDIDO em 26/08/2026, e é a SOMBRA de uma cura que chegou. Ela é o "
        "embrulho `bool` sobre `mic_volume_set_detalhado`, e ficou sem chamador "
        "de produção no dia em que `controller_card.py` passou a chamar a "
        "detalhada — que é literalmente o que a lápide de `alvo_honrado` "
        "prescrevia como cura, e que esta leva executou. O `bool` colapsava "
        "`sem_fonte`, daemon offline e sem-controle no mesmo `False`; com a "
        "mesa cheia isso mexia no microfone de OUTRA pessoa devolvendo `True`. "
        "NÃO É PROMESSA PENDENTE, é resto: o caminho existe e está fiado. O que "
        "a apaga é a poda, junto com a do `led_set` e a do `player_leds_set`, "
        "que carregam esta mesma nota. DONO: a próxima leva. O docstring dela "
        "guarda a tabela das três camadas do microfone (firmware x fonte do "
        "sistema) e essa medição tem de sobreviver à poda."
    ),
    "daemon/subsystems/identity.py::reset_identity_registry": (
        "MEDIDO em 12/08/2026. Instrumento de isolamento entre casos: o próprio "
        "docstring diz `APENAS testes — isola estado entre casos`, e o corpo "
        "descarta o singleton `_registry`. Chamá-lo em produção apagaria a "
        "numeração dos controles no meio da sessão dela."
    ),
    "gui/widgets/button_glyph.py::limpar_cache_tinting": (
        "MEDIDO em 12/08/2026. Instrumento: o docstring diz `higiene de testes` "
        "e o corpo esvazia `_PIXBUF_TINT_CACHE`. O cache é uma otimização de "
        "desenho; limpá-lo em produção só faria a janela redesenhar glifos que "
        "já estavam certos."
    ),
    "integrations/desktop_notifications.py::reset_throttle_cache": (
        "MEDIDO em 12/08/2026. Instrumento: docstring `útil em testes`, corpo "
        "esvazia `_last_emit_at`. Existe para um caso poder emitir duas "
        "notificações seguidas sem esperar o intervalo real passar."
    ),
    "integrations/desktop_notifications.py::reset_once_cache": (
        "MEDIDO em 12/08/2026. Instrumento: docstring `útil em testes`, corpo "
        "esvazia `_announced_once`. Irmã da anterior, para a dedução por "
        "`once_key` não vazar de um caso para o seguinte."
    ),
    "utils/logging_config.py::reset_for_tests": (
        "MEDIDO em 12/08/2026. Instrumento, e o nome o declara. Reconfigura o "
        "logging entre casos; em produção o logging é configurado uma vez, no "
        "início do processo, e reconfigurá-lo perderia handlers."
    ),
    "integrations/uhid_gamepad.py::capture_dualsense_blueprint": (
        "MEDIDO em 12/08/2026. Ferramenta de diagnóstico, e o docstring o diz em "
        "maiúsculas: `(DIAGNÓSTICO)`, `irmã de scripts/capture_blueprint.py`. "
        "Está FORA do caminho de criação do vpad desde a VPAD-03/BT-01 de "
        "propósito, e o docstring explica por quê: por Bluetooth cada "
        "GET_REPORT num controle ocioso estoura o timeout de 5 s do hidp com "
        "EIO. Religá-la seria a regressão, não a cura."
    ),
    "integrations/kernel_cmdline.py::plan_cmdline": (
        "RECLASSIFICADA em 26/08/2026, e esta entrada SUBSTITUI uma que morava "
        "em `_SEM_CAMINHO_HOJE` afirmando um FATO ERRADO: que *'enquanto o "
        "shell do install for o dono, este módulo é uma segunda implementação "
        "da mesma regra em outra linguagem'*. Não existe segunda implementação. "
        "O instalador IMPORTA este próprio módulo, num heredoc Python do passo "
        "`3e` (`sys.path.insert(0, root/'src')`, depois `kc.plan_tokens(tokens)` "
        "e `kc.forbidden_reintroductions(actions)`), e o `install.sh` declara a "
        "política com todas as letras: *'quem DECIDE é o módulo puro "
        "integrations/kernel_cmdline.py (100% stdlib, testável); aqui só "
        "traduzimos o plano'*. A regra tem UM dono, e é este arquivo. "
        "O que sobra é diferença de FORMA, não de regra, e é por isso que a "
        "função não é promessa sem caminho: a produção nunca tem o "
        "`/proc/cmdline` cru na mão — lê tokens do JSON do kernelstub ou da "
        "linha do GRUB — e por isso chama a irmã `plan_tokens`, que É alcançada. "
        "Esta é a porta de string crua, irmã do `apply_plan` logo abaixo e da "
        "mesma espécie: quem tem a linha inteira usa. NÃO foi podada de "
        "propósito; a nota datada está no docstring dela."
    ),
    "profiles/sanidade.py::verificar_perfis_do_disco": (
        "RECLASSIFICADA em 26/08/2026, e esta entrada SUBSTITUI uma que morava "
        "em `_SEM_CAMINHO_HOJE` prescrevendo a cura ERRADA: *'o `doctor` chamar "
        "isto. É a lacuna mais barata desta lista de fechar — uma chamada'*. "
        "MEDIDO: o doctor JÁ faz o trabalho inteiro, e faz MELHOR. "
        "`cli/cmd_doctor.py::_linhas_perfis` chama `load_all_profiles()` dentro "
        "de um `try/except OSError`, e só então `sanidade.verificar_perfis` e "
        "`sanidade.linhas_de_relatorio`; `_print_bloco_perfis` imprime o bloco "
        "`== perfis (coerência entre eles) ==` e devolve o achado grave para o "
        "código de saída. A corrente não está quebrada: ela roda. "
        "E fiar ESTA conveniência no lugar seria PIORAR o produto — ela não tem "
        "o `except OSError`, então trocaria a linha *'não deu para ler os "
        "perfis: <erro>'* por um traceback na cara de quem foi pedir "
        "diagnóstico justamente porque algo quebrou. É atalho de teste "
        "(`test_regra_nao_se_perde_02_o_nome_novo_nascia_sem_regra.py`:319), com "
        "nota datada no próprio docstring, e não deve ganhar chamador."
    ),
    "integrations/kernel_cmdline.py::apply_plan": (
        "MEDIDO em 12/08/2026. Instrumento: o docstring diz `SIMULA o plano "
        "sobre os tokens (para testes e para o doctor comparar)` e `Não toca "
        "sistema nenhum`. Quem de fato escreve a linha de comando do kernel é "
        "o instalador, em shell; esta função existe para prever o resultado."
    ),
    # `integrations/kernel_cmdline.py::forbidden_reintroductions` MOROU AQUI, e
    # saiu em 13/08/2026 porque a classificação estava ERRADA, não porque o
    # símbolo mudou. A razão dizia "instrumento: o docstring diz `Guarda de
    # teste`" — e o instalador a chama em produção, dentro do heredoc de
    # install.sh:1633 (`violations = kc.forbidden_reintroductions(actions)`),
    # para ABORTAR o passo do cmdline quando a guarda anti-reintrodução dispara.
    # Ela só parecia instrumento porque a varredura era cega a heredoc. O portão
    # cobrou o apagamento sozinho, que é exatamente o que ele existe para fazer.
    "daemon/subsystems/gamepad.py::suspend_vpads_for_steam_input": (
        "MEDIDO em 12/08/2026. LÁPIDE COM NOTA DATADA, e a nota está no próprio "
        "corpo: `NOTA DATADA — 09/08/2026 (ESCONDER-EM-VEZ-DE-SAIR-01): fora do "
        "caminho da marca do Steam Input. Nenhuma borda da exceção chama mais "
        "esta função.` O texto declara os três motivos de ela ficar inteira — o "
        "raciocínio foi medido e não se apaga decisão medida; o co-op lê o "
        "estado que ela publica; e um daemon que subiu ANTES da cura pode estar "
        "com uma suspensão de pé, cuja saída (`resume_vpads_after_steam_input`, "
        "essa sim viva em gamepad.py:332) é o caminho de volta dele. Não deve "
        "chamador: ela deve continuar não sendo chamada."
    ),
    "core/led_control.py::apply_led_settings": (
        "MEDIDO em 13/08/2026, e esta entrada é a CORREÇÃO de uma que dizia o "
        "contrário. Ela morava em `_SEM_CAMINHO_HOJE` porque o docstring da "
        "função afirmava que sem ela `os bits nunca chegam ao controle` — e o "
        "portão tomou o sintoma descrito pelo estado da árvore. Os bits chegam: "
        "`ProfileManager.apply` emite `player_leds` no `OutputSpec` de "
        "`apply_output_defaults` (profiles/manager.py:392) e o backend converte "
        "em `_write_partial_output` (backend_pydualsense.py:2801). É LÁPIDE COM "
        "NOTA DATADA: a nota está no próprio docstring, que hoje diz o endereço "
        "do caminho vivo em vez do sintoma; a função é a forma `aplicar um "
        "LedSettings inteiro`, correta e pública, e não deve chamador porque "
        "quem manda no aparelho é o `OutputSpec` — o único que sabe dizer `não "
        "mexe neste campo` com `None`, de que a trava manual por categoria "
        "depende. A PODA É DELA: símbolo público não se apaga por conta "
        "própria. A ligação perfil→bitmask é conferida em "
        "`tests/unit/test_perfil_acende_os_pontinhos_do_jogador.py`."
    ),
    "core/led_control.py::player_bitmask": (
        "MEDIDO em 13/08/2026. Cai junto com `apply_led_settings`, pela mesma "
        "correção: é a conversão que o aplicador usa, e o caminho vivo faz a "
        "MESMA conversão inline em backend_pydualsense.py:2801 (`sum(1 << i for "
        "i, b in enumerate(out.player_leds) if b)`). A pergunta que a entrada "
        "antiga deixava em aberto era se os dois layouts divergem — não "
        "divergem, e isso deixou de ser leitura e virou teste: "
        "`test_a_conversao_do_backend_e_a_de_led_control_sao_a_mesma` compara os "
        "32 padrões possíveis. Não é dívida: é a mesma regra escrita duas vezes, "
        "com guarda contra as duas se separarem. Apagar uma delas é decisão "
        "DELA, não deste portão."
    ),
    # `utils/session.py::load_coop_enabled` MOROU AQUI e a entrada SAIU em
    # 26/08/2026 porque o SÍMBOLO foi podado — não porque a classificação
    # mudasse. A entrada dizia que o corpo ficava de pé porque "a assinatura é
    # contrato público que CLI, applet e testes importam". As duas metades da
    # razão eram falsas, e foram medidas: nenhum `.py` de `src/` a importa (a
    # CLI inclusive), e o applet do COSMIC é RUST — `packaging/cosmic-applet/`
    # tem `Cargo.toml` e `src/{main,app,ipc}.rs`, fala JSON-RPC com o daemon, e
    # não há um único `.py` sob `packaging/`. Sobrava `tests/`, que nunca foi
    # caminho. A DECISÃO MEDIDA que a lápide guardava (COOP-SEM-INTERRUPTOR-01,
    # 06/08/2026: o co-op local não tem mais opt-out) continua escrita, com a
    # data, no lugar onde a função morava, em `utils/session.py`.
    "app/audio_saida.py::estado_do_sono": (
        "MEDIDO em 18/08/2026. LÁPIDE COM NOTA DATADA, e a nota está no próprio "
        "docstring, escrita nesta data. A promessa que a fez nascer é o item 6 "
        "da `SOM-QUE-NAO-DORME-01` — `a aba Status consegue dizer o estado, "
        "inclusive denunciar a cura arrancada` — e ela ESTÁ entregue, por outro "
        "caminho: a `SOM-ACORDADO-01` mediu o desenho e escolheu dizer o estado "
        "POR CONTROLE, no rótulo da moldura de cada card, em vez de uma frase "
        "global. O caminho vivo é `RotaDeSaida.estado` (audio_saida.py:817) "
        "publicando os canais, `status_actions.py`:1038 lendo "
        "`regra_nunca_dorme_instalada()` na MESMA worker, :1249 entregando os "
        "dois ao card por `definir_estado_do_canal`, e "
        "`controller_card.py`:4216-4224 escrevendo as frases — inclusive a "
        "`DICA_CANAL_SEM_A_REGRA`, que é a cura arrancada sendo denunciada na "
        "tela. Não deve chamador: fiá-la na janela seria um SEGUNDO leitor de "
        "PipeWire lá dentro (o defeito que controller_card.py:4044-4049 descreve) "
        "para repetir o que já está escrito. A PODA É DELA — símbolo público "
        "não se apaga por conta própria, e apagar este arruinaria de quebra "
        "`texto_do_sono` e `sono_dos_sinks_do_controle`, que hoje só são "
        "alcançados por ele e que `tests/unit/test_o_alto_falante_nunca_dorme_01.py`"
        ":573-608 exercita como as funções PURAS da decisão."
    ),
    # --- A BANCADA (22/08/2026): o que só um instrumento de `scripts/` usa ----
    # Os cinco do broker entraram quando `_TERRITORIOS_DE_PRODUCAO =
    # ("scripts",)` saiu; o sexto, `gerar_tabela_markdown`, entraria de todo
    # jeito — `curva_propria.py` é corrente fechada e nenhum ponto de entrada o
    # alcança. Não é dívida nova: é a mesma linha que já valia para `tests/`,
    # aplicada à bancada. A nota de `_PONTOS_DE_ENTRADA` traz a medição.
    # `abrir_hidraw` SAIU DAQUI em 29/08/2026, e este portão foi quem mandou.
    # A lápide dizia "API de BANCADA: o único chamador é `scripts/ensaios/
    # comum.py`" — verdade em 22/08 e falsa hoje: `integrations/
    # cor_do_plastico._perguntar_ao_hidraw` passou a entrar por ela, que era o
    # conserto do "Não sei" nos dois cards dela. A lápide sobreviveu à própria
    # cura, o portão viu, e a entrada foi apagada em vez de atualizada — é a
    # regra desta casa: fato que a medição derrubou sai, não fica ao lado do
    # certo.
    "integrations/hidraw_broker_client.py::porta_provavel": (
        "MEDIDO em 22/08/2026. Instrumento: `scripts/record_hid_capture.py`"
        ":66+420 e `scripts/ensaios/comum.py`:92+481 a usam para imprimir por "
        "qual porta o ensaio está falando. É cabeçalho de relatório de bancada e "
        "não muda nada no aparelho — quem escolhe a porta em produção é "
        "`broker_client_for` (:386)."
    ),
    "integrations/hidraw_broker_client.py::estado_do_grab": (
        "MEDIDO em 22/08/2026. Instrumento, e o docstring (:735) o diz: existe "
        "para o ensaio saber se o zero que ele contou é do aparelho ou da "
        "ausência de leitura. Chamadores: "
        "`scripts/ensaio_o_keepalive_mata_o_rumble.py`:64+281 e "
        "`scripts/ensaio_rumble_em_par.py`:93. O daemon não pergunta isso — ele "
        "É quem segura o grab."
    ),
    "integrations/hidraw_broker_client.py::linha_do_grab": (
        "MEDIDO em 22/08/2026. Formata a linha de cabeçalho `grab do evdev ....` "
        "de um relatório de ensaio; chamada em "
        "`scripts/ensaio_o_keepalive_mata_o_rumble.py`:373 e "
        "`scripts/ensaio_rumble_em_par.py`:333. Irmã de `estado_do_grab`: sem o "
        "instrumento não há onde imprimir."
    ),
    "integrations/hidraw_broker_client.py::leitura_de_zero": (
        "MEDIDO em 22/08/2026. Instrumento declarado: o docstring (:744) diz que "
        "ela existe para uma CÉLULA DE TABELA de ensaio não chamar de `0` o que "
        "é `MUDO`. O único uso é a reexportação de `scripts/ensaios/comum.py`:89, "
        "marcada `# noqa: F401 - reexportado para os instrumentos`."
    ),
    "profiles/curva_propria.py::gerar_tabela_markdown": (
        "MEDIDO em 22/08/2026, e isto SUBSTITUI a nota de 15/08 que o dava por "
        "fiado em produção. O docstring (:290) diz o que ele é: gera a tabela de "
        "`docs/protocol/curvas-proprias.md`. O único chamador é "
        "`scripts/gerar-tabela-de-curvas.py`:52-83, que roda no CI com `--check` "
        "(`.github/workflows/ci.yml`:400). Gerador de documentação é instrumento, "
        "e instrumento não é caminho de produção — a mesma linha que vale para "
        "`tests/`."
    ),
    # --- CONFIG-06 (23/08/2026) apagou o único chamador do embrulho estreito -
    "app/ipc_bridge.py::machine_declare": (
        "MEDIDO em 24/08/2026 (AUDITORIA-DE-PERDA-01). Mesma forma de "
        "`led_control.py::apply_led_settings` acima: LÁPIDE COM NOTA DATADA, e "
        "a nota já estava no próprio docstring da função, escrita quando a "
        "CONFIG-06 nasceu — `machine_declare_detalhado` existe porque "
        "`machine_declare` 'está no `__all__` e a dupla `(ok, motivo)` é o "
        "contrato de quem já a chama'. Essa frase ficou falsa no mesmo dia em "
        "que foi escrita: `footer_actions.py`:323 chama "
        "`ipc_bridge.machine_declare_detalhado` diretamente, e é o ÚNICO lugar "
        "do produto que declara a mesa — não sobrou segundo chamador para a "
        "dupla estreita. O corpo de `machine_declare` (:830) CHAMA "
        "`machine_declare_detalhado` — não o contrário —, mas nada de "
        "produção chama `machine_declare`: ela virou uma casca que embrulha a "
        "variante rica sem que ninguém peça a casca. É a mesma forma do par "
        "`apply_draft`/"
        "`apply_draft_detalhado` que o próprio docstring cita como precedente "
        "— só que naquele par o embrulho estreito ainda tem para quem servir; "
        "neste não tem mais. A PODA É DELA: é símbolo público, está no "
        "`__all__` (:1293), e apagar wrapper documentado por conta própria não "
        "é deste portão."
    ),
}

#: As promessas públicas SEM CAMINHO de 12/08/2026 — a dívida, com endereço e
#: com o que a fecharia. Não são consertos desta leva: consertar qualquer uma
#: é mudança que ninguém pediu, e pelo menos duas (a máscara por aparelho e as
#: notificações) dependem de decisão DELA sobre a tela.
#:
#: No dia em que o caminho nascer, a entrada deixa de bater com a árvore e
#: ``test_a_lista_de_lacunas_nao_envelhece_calada`` cobra que ela seja apagada.
_SEM_CAMINHO_HOJE: dict[str, str] = {
    # --- 25/08/2026: `core/physical_report_reader.py` nasceu nesta madrugada, e ainda não tem tela
    "core/physical_report_reader.py::extract_motion_window": (
        "MEDIDO em 25/08/2026, na DAEMON-ACORDADO-01. Faz parte da "
        "investigação dos **15,2% de um núcleo com ninguém jogando** (6.393 "
        "chamadas `read` por segundo com quatro controles parados). ONDE O "
        "CAMINHO SE PERDE: a função foi extraída para poder ser MEDIDA sem "
        "aparelho — o laço vivo ainda usa o caminho antigo. O QUE A FECHA: a "
        "troca do laço pelo caminho medido, que precisa da bancada dela para "
        "confirmar que a conta baixou no processo vivo. "
    ),
    # --- `integrations/arranjo_da_mesa.py`: o motor GANHOU TELA em 26/08/2026,
    # e destas 37 lápides sobraram NOVE. A janela do mapa
    # (`app/widgets/mapa_da_mesa.py`) passou a montar a `Mesa` por
    # `mapa_das_portas.mesa_do_motor` e a chamar `julgar` em cada quadrado; com o
    # módulo alcançado, todo símbolo que ele usa por dentro ganhou chamador de
    # produção junto. As nove que ficam são as que NADA alcança, nem de fora nem
    # de dentro: a RECEITA (o que mover para onde), as VARIANTES, o reexame e a
    # conta de slots. A razão de cada uma está corrigida abaixo.
    #
    # A `::Entrada` já havia saído antes, por um motivo do INSTRUMENTO e não do
    # produto: `app/widgets/calibrar_entradas.py` tem `PALAVRA_DA_ENTRADA =
    # "Entrada"`, e pela armadilha 1 do topo deste arquivo todo literal de texto
    # de `src/` é quebrado em PALAVRAS — a palavra num rótulo de tela satisfazia
    # o símbolo. Fica registrado porque é o tipo de perdão que este portão dá
    # calado, e quem ler a contagem precisa saber que uma das 37 caiu por isso.
    "integrations/arranjo_da_mesa.py::adaptadores_da_mesa": (
        "MEDIDO em 25/08/2026, CORRIGIDO em 26/08/2026: portado byte a byte "
        "do motor que rodava só dentro do mockup "
        "`2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html`, com 114 testes "
        "de equivalência que rodam o original em `node`. "
        "O FATO ERRADO QUE SAIU: esta razão dizia *nenhuma tela o consome "
        "ainda*, e isso deixou de ser verdade em 26/08 — a janela do mapa monta "
        "a `Mesa` por `mapa_das_portas.mesa_do_motor` e chama `julgar` em cada "
        "quadrado, e 28 lápides deste registro caíram junto. "
        "ONDE O CAMINHO SE PERDE: o que a janela ligou é o JUÍZO POR ENTRADA "
        "(aqui serve, aqui não, e por quê). A RECEITA — o que mover para onde "
        "—, as VARIANTES, o reexame e a conta de slots continuam sem tela, e "
        "não é descuido: a `D-QUAL-REGUA-MANDA-NO-ARRANJO` diz que a escolha "
        "entre as duas réguas do arranjo é palavra DELA, a medição que ela "
        "pediu está em `tests/unit/test_as_duas_reguas_do_arranjo_divergem_"
        "onde.py`, e ela ainda não escolheu. "
        "O QUE O FECHA: a ordem de serviço da aba Conexões, depois da palavra "
        "dela sobre qual régua vence. "
    ),
    "integrations/arranjo_da_mesa.py::candidatas": (
        "MEDIDO em 25/08/2026, CORRIGIDO em 26/08/2026: portado byte a byte "
        "do motor que rodava só dentro do mockup "
        "`2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html`, com 114 testes "
        "de equivalência que rodam o original em `node`. "
        "O FATO ERRADO QUE SAIU: esta razão dizia *nenhuma tela o consome "
        "ainda*, e isso deixou de ser verdade em 26/08 — a janela do mapa monta "
        "a `Mesa` por `mapa_das_portas.mesa_do_motor` e chama `julgar` em cada "
        "quadrado, e 28 lápides deste registro caíram junto. "
        "ONDE O CAMINHO SE PERDE: o que a janela ligou é o JUÍZO POR ENTRADA "
        "(aqui serve, aqui não, e por quê). A RECEITA — o que mover para onde "
        "—, as VARIANTES, o reexame e a conta de slots continuam sem tela, e "
        "não é descuido: a `D-QUAL-REGUA-MANDA-NO-ARRANJO` diz que a escolha "
        "entre as duas réguas do arranjo é palavra DELA, a medição que ela "
        "pediu está em `tests/unit/test_as_duas_reguas_do_arranjo_divergem_"
        "onde.py`, e ela ainda não escolheu. "
        "O QUE O FECHA: a ordem de serviço da aba Conexões, depois da palavra "
        "dela sobre qual régua vence. "
    ),
    "integrations/arranjo_da_mesa.py::consequencias": (
        "MEDIDO em 25/08/2026, CORRIGIDO em 26/08/2026: portado byte a byte "
        "do motor que rodava só dentro do mockup "
        "`2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html`, com 114 testes "
        "de equivalência que rodam o original em `node`. "
        "O FATO ERRADO QUE SAIU: esta razão dizia *nenhuma tela o consome "
        "ainda*, e isso deixou de ser verdade em 26/08 — a janela do mapa monta "
        "a `Mesa` por `mapa_das_portas.mesa_do_motor` e chama `julgar` em cada "
        "quadrado, e 28 lápides deste registro caíram junto. "
        "ONDE O CAMINHO SE PERDE: o que a janela ligou é o JUÍZO POR ENTRADA "
        "(aqui serve, aqui não, e por quê). A RECEITA — o que mover para onde "
        "—, as VARIANTES, o reexame e a conta de slots continuam sem tela, e "
        "não é descuido: a `D-QUAL-REGUA-MANDA-NO-ARRANJO` diz que a escolha "
        "entre as duas réguas do arranjo é palavra DELA, a medição que ela "
        "pediu está em `tests/unit/test_as_duas_reguas_do_arranjo_divergem_"
        "onde.py`, e ela ainda não escolheu. "
        "O QUE O FECHA: a ordem de serviço da aba Conexões, depois da palavra "
        "dela sobre qual régua vence. "
    ),
    "integrations/arranjo_da_mesa.py::plano_dos_controles": (
        "MEDIDO em 25/08/2026, CORRIGIDO em 26/08/2026: portado byte a byte "
        "do motor que rodava só dentro do mockup "
        "`2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html`, com 114 testes "
        "de equivalência que rodam o original em `node`. "
        "O FATO ERRADO QUE SAIU: esta razão dizia *nenhuma tela o consome "
        "ainda*, e isso deixou de ser verdade em 26/08 — a janela do mapa monta "
        "a `Mesa` por `mapa_das_portas.mesa_do_motor` e chama `julgar` em cada "
        "quadrado, e 28 lápides deste registro caíram junto. "
        "ONDE O CAMINHO SE PERDE: o que a janela ligou é o JUÍZO POR ENTRADA "
        "(aqui serve, aqui não, e por quê). A RECEITA — o que mover para onde "
        "—, as VARIANTES, o reexame e a conta de slots continuam sem tela, e "
        "não é descuido: a `D-QUAL-REGUA-MANDA-NO-ARRANJO` diz que a escolha "
        "entre as duas réguas do arranjo é palavra DELA, a medição que ela "
        "pediu está em `tests/unit/test_as_duas_reguas_do_arranjo_divergem_"
        "onde.py`, e ela ainda não escolheu. "
        "O QUE O FECHA: a ordem de serviço da aba Conexões, depois da palavra "
        "dela sobre qual régua vence. "
    ),
    "integrations/arranjo_da_mesa.py::qualidade": (
        "MEDIDO em 25/08/2026, CORRIGIDO em 26/08/2026: portado byte a byte "
        "do motor que rodava só dentro do mockup "
        "`2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html`, com 114 testes "
        "de equivalência que rodam o original em `node`. "
        "O FATO ERRADO QUE SAIU: esta razão dizia *nenhuma tela o consome "
        "ainda*, e isso deixou de ser verdade em 26/08 — a janela do mapa monta "
        "a `Mesa` por `mapa_das_portas.mesa_do_motor` e chama `julgar` em cada "
        "quadrado, e 28 lápides deste registro caíram junto. "
        "ONDE O CAMINHO SE PERDE: o que a janela ligou é o JUÍZO POR ENTRADA "
        "(aqui serve, aqui não, e por quê). A RECEITA — o que mover para onde "
        "—, as VARIANTES, o reexame e a conta de slots continuam sem tela, e "
        "não é descuido: a `D-QUAL-REGUA-MANDA-NO-ARRANJO` diz que a escolha "
        "entre as duas réguas do arranjo é palavra DELA, a medição que ela "
        "pediu está em `tests/unit/test_as_duas_reguas_do_arranjo_divergem_"
        "onde.py`, e ela ainda não escolheu. "
        "O QUE O FECHA: a ordem de serviço da aba Conexões, depois da palavra "
        "dela sobre qual régua vence. "
    ),
    "integrations/arranjo_da_mesa.py::receita": (
        "MEDIDO em 25/08/2026, CORRIGIDO em 26/08/2026: portado byte a byte "
        "do motor que rodava só dentro do mockup "
        "`2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html`, com 114 testes "
        "de equivalência que rodam o original em `node`. "
        "O FATO ERRADO QUE SAIU: esta razão dizia *nenhuma tela o consome "
        "ainda*, e isso deixou de ser verdade em 26/08 — a janela do mapa monta "
        "a `Mesa` por `mapa_das_portas.mesa_do_motor` e chama `julgar` em cada "
        "quadrado, e 28 lápides deste registro caíram junto. "
        "ONDE O CAMINHO SE PERDE: o que a janela ligou é o JUÍZO POR ENTRADA "
        "(aqui serve, aqui não, e por quê). A RECEITA — o que mover para onde "
        "—, as VARIANTES, o reexame e a conta de slots continuam sem tela, e "
        "não é descuido: a `D-QUAL-REGUA-MANDA-NO-ARRANJO` diz que a escolha "
        "entre as duas réguas do arranjo é palavra DELA, a medição que ela "
        "pediu está em `tests/unit/test_as_duas_reguas_do_arranjo_divergem_"
        "onde.py`, e ela ainda não escolheu. "
        "O QUE O FECHA: a ordem de serviço da aba Conexões, depois da palavra "
        "dela sobre qual régua vence. "
    ),
    "integrations/arranjo_da_mesa.py::reexame": (
        "MEDIDO em 25/08/2026, CORRIGIDO em 26/08/2026: portado byte a byte "
        "do motor que rodava só dentro do mockup "
        "`2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html`, com 114 testes "
        "de equivalência que rodam o original em `node`. "
        "O FATO ERRADO QUE SAIU: esta razão dizia *nenhuma tela o consome "
        "ainda*, e isso deixou de ser verdade em 26/08 — a janela do mapa monta "
        "a `Mesa` por `mapa_das_portas.mesa_do_motor` e chama `julgar` em cada "
        "quadrado, e 28 lápides deste registro caíram junto. "
        "ONDE O CAMINHO SE PERDE: o que a janela ligou é o JUÍZO POR ENTRADA "
        "(aqui serve, aqui não, e por quê). A RECEITA — o que mover para onde "
        "—, as VARIANTES, o reexame e a conta de slots continuam sem tela, e "
        "não é descuido: a `D-QUAL-REGUA-MANDA-NO-ARRANJO` diz que a escolha "
        "entre as duas réguas do arranjo é palavra DELA, a medição que ela "
        "pediu está em `tests/unit/test_as_duas_reguas_do_arranjo_divergem_"
        "onde.py`, e ela ainda não escolheu. "
        "O QUE O FECHA: a ordem de serviço da aba Conexões, depois da palavra "
        "dela sobre qual régua vence. "
    ),
    "integrations/arranjo_da_mesa.py::sem_entrada": (
        "MEDIDO em 25/08/2026, CORRIGIDO em 26/08/2026: portado byte a byte "
        "do motor que rodava só dentro do mockup "
        "`2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html`, com 114 testes "
        "de equivalência que rodam o original em `node`. "
        "O FATO ERRADO QUE SAIU: esta razão dizia *nenhuma tela o consome "
        "ainda*, e isso deixou de ser verdade em 26/08 — a janela do mapa monta "
        "a `Mesa` por `mapa_das_portas.mesa_do_motor` e chama `julgar` em cada "
        "quadrado, e 28 lápides deste registro caíram junto. "
        "ONDE O CAMINHO SE PERDE: o que a janela ligou é o JUÍZO POR ENTRADA "
        "(aqui serve, aqui não, e por quê). A RECEITA — o que mover para onde "
        "—, as VARIANTES, o reexame e a conta de slots continuam sem tela, e "
        "não é descuido: a `D-QUAL-REGUA-MANDA-NO-ARRANJO` diz que a escolha "
        "entre as duas réguas do arranjo é palavra DELA, a medição que ela "
        "pediu está em `tests/unit/test_as_duas_reguas_do_arranjo_divergem_"
        "onde.py`, e ela ainda não escolheu. "
        "O QUE O FECHA: a ordem de serviço da aba Conexões, depois da palavra "
        "dela sobre qual régua vence. "
    ),
    "integrations/arranjo_da_mesa.py::variante_por_id": (
        "MEDIDO em 25/08/2026, CORRIGIDO em 26/08/2026: portado byte a byte "
        "do motor que rodava só dentro do mockup "
        "`2026-08-24-ABA-CONEXOES/mockup/mapa-das-portas.html`, com 114 testes "
        "de equivalência que rodam o original em `node`. "
        "O FATO ERRADO QUE SAIU: esta razão dizia *nenhuma tela o consome "
        "ainda*, e isso deixou de ser verdade em 26/08 — a janela do mapa monta "
        "a `Mesa` por `mapa_das_portas.mesa_do_motor` e chama `julgar` em cada "
        "quadrado, e 28 lápides deste registro caíram junto. "
        "ONDE O CAMINHO SE PERDE: o que a janela ligou é o JUÍZO POR ENTRADA "
        "(aqui serve, aqui não, e por quê). A RECEITA — o que mover para onde "
        "—, as VARIANTES, o reexame e a conta de slots continuam sem tela, e "
        "não é descuido: a `D-QUAL-REGUA-MANDA-NO-ARRANJO` diz que a escolha "
        "entre as duas réguas do arranjo é palavra DELA, a medição que ela "
        "pediu está em `tests/unit/test_as_duas_reguas_do_arranjo_divergem_"
        "onde.py`, e ela ainda não escolheu. "
        "O QUE O FECHA: a ordem de serviço da aba Conexões, depois da palavra "
        "dela sobre qual régua vence. "
    ),
    # --- 25/08/2026: `integrations/entradas_do_gabinete.py` nasceu nesta
    #     madrugada, e ainda não tem tela que o consuma
    # --- 25/08/2026: `integrations/lugar_declarado.py` nasceu nesta madrugada, e ainda não tem tela
    "integrations/lugar_declarado.py::declarar_a_mesa": (
        "MEDIDO em 25/08/2026: a CAL-2 da calibração. Existe para curar um "
        "defeito nomeado: hoje o ÚNICO escritor do `maquina.json` é o IPC "
        "`machine.declare`, logo **com o daemon parado nada do que ela "
        "declara chega ao disco** — o rodapé responde 'O Hefesto está "
        "desligado, não gravei o que você declarou'. Este módulo liga o "
        "`gravar_rascunho_da_mesa`, que estava escrito desde 24/08 e nunca "
        "teve chamador. ONDE O CAMINHO SE PERDE: quem o chamaria é a janela "
        "de calibração, que é da leva seguinte. O QUE O FECHA: a CAL-3. "
    ),
    # --- 25/08/2026: `integrations/mapa_das_portas.py` nasceu nesta madrugada, e ainda não tem tela
    "integrations/mapa_das_portas.py::incoerencias": (
        "MEDIDO em 25/08/2026: as quatro funções de junção da CONEXOES- "
        "MAPA-2D-01 (`portas_livres`, `vizinhas_de_verdade`, `incoerencias`, "
        "`porta_do_adaptador`). Prontas e testadas. ONDE O CAMINHO SE PERDE: "
        "quem as consome é a ORDEM-DE-SERVICO-01, que rodou na MESMA "
        "madrugada, e as tarefas de tela dela pararam no olho dela (D3). O "
        "QUE O FECHA: as frases da ordem de serviço na aba Conexões. A sprint "
        "do mapa manda explicitamente que a Frente B consuma "
        "`vizinhas_de_verdade` em vez de mexer em "
        "`mesa_de_radio.vizinhancas_apertadas`, porque a porta-filha (o "
        "extensor) muda o cálculo de vizinhança. "
    ),
    "integrations/mapa_das_portas.py::porta_do_adaptador": (
        "MEDIDO em 25/08/2026: as quatro funções de junção da CONEXOES- "
        "MAPA-2D-01 (`portas_livres`, `vizinhas_de_verdade`, `incoerencias`, "
        "`porta_do_adaptador`). Prontas e testadas. ONDE O CAMINHO SE PERDE: "
        "quem as consome é a ORDEM-DE-SERVICO-01, que rodou na MESMA "
        "madrugada, e as tarefas de tela dela pararam no olho dela (D3). O "
        "QUE O FECHA: as frases da ordem de serviço na aba Conexões. A sprint "
        "do mapa manda explicitamente que a Frente B consuma "
        "`vizinhas_de_verdade` em vez de mexer em "
        "`mesa_de_radio.vizinhancas_apertadas`, porque a porta-filha (o "
        "extensor) muda o cálculo de vizinhança. "
    ),
    # --- 26/08/2026: AS CINCO LÁPIDES DO CATÁLOGO DE ORDENS CAÍRAM.
    # A ORDEM-5 e a ORDEM-6 fecharam na leva 2
    # (`app/actions/config/secao_exame.py`): o card de ordem ganhou
    # `[Já movi — reexaminar]` e `[Ignorar]`, o selo do topo passou a dizer
    # o texto de `cabecalho()`, a dispensa dela filtra por `ordens_novas` e
    # é CONTADA por `ordens_caladas`, e `identidades` é quem separa dois
    # adaptadores de mesmo `vid:pid` pelo serial para que o produto não
    # diga "Confirmei" sem saber qual dos dois ela moveu.
    # A mordida está em `test_a_dispensa_volta_quando_o_arranjo_muda.py`.
    # `portas_do_barramento.py` é a camada de sysfs que `ordens_da_mesa`
    # consome. Ela tem chamador de produção (`mesmo_hub_fisico` importa
    # `hubs_do_mesmo_plastico` desde 25/08), mas esse chamador é o próprio
    # catálogo — que também não chega à tela. Cai tudo junto, e pela mesma
    # ORDEM-4/ORDEM-5.
    "integrations/portas_do_barramento.py::mesmo_hub_fisico": (
        "MEDIDO em 25/08/2026: a pergunta de plástico em forma de par de "
        "caminhos. Cai junto com o catálogo de ordens, que é quem a consumiria "
        "até a tela."
    ),
    "integrations/portas_do_barramento.py::mesmo_soquete_fisico": (
        "MEDIDO em 25/08/2026: o caso em que 'mude um dos dois de entrada' é a "
        "ordem errada. Cai junto com o catálogo de ordens, que é quem a "
        "consumiria até a tela."
    ),
    "integrations/portas_do_barramento.py::livres_fora_de": (
        "MEDIDO em 25/08/2026: a contra-regra de R3 virada em função. Cai junto "
        "com o catálogo de ordens, que é quem a consumiria até a tela."
    ),
    # --- 25/08/2026: TRÊS CURAS DA ONDA 0 NASCERAM SEM CHAMADOR
    # Achado por quem coordena a leva de 25/08, ao consertar duas lápides
    # caducas e ver o portão apontar outros quatro símbolos. Cada um destes é
    # a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` dentro da própria cura que a
    # combatia, e nenhum é destas frentes: quem liga cada um está nomeado.
    #
    # `app/textos_de_aplicacao.py::frase_do_desfecho` SAIU daqui em 25/08/2026,
    # na mesma edição que a ligou: `app/actions/triggers_actions.py` a importa
    # e o `_toast_trigger` a chama (GATILHOS-APLICADO-COM-PROVA/T3). A entrada
    # apontava o rodapé como quem a fecharia; quem fechou foi a aba Gatilhos, e
    # tanto faz — a promessa era ter caminho de produção. Lápide que sobrevive
    # à própria cura é o defeito que este portão existe para matar.
    # --- 26/08/2026: a janela de calibrar entradas (L1-F) nasceu inteira, e o
    #     BOTÃO que a abre chegou na L2-E, no MESMO dia. CINCO das seis lápides
    #     saíram daqui nessa edição — `LogicaDaCalibracao`, `Pergunta`, `Laudo`,
    #     `NavegacaoPorControle` e `PosseDoVocabulario` —, junto com
    #     `entradas_do_gabinete::furo_declarado`, que a janela chama (`:694`).
    #     A sexta ficou, e a razão dela já dizia por quê: quem tem de perguntar
    #     por ela é o DESPACHO do daemon, não a janela.
    "app/widgets/calibrar_entradas.py::botoes_para_o_jogo": (
        "MEDIDO em 26/08/2026, e esta é a lápide que MENOS depende da L2-E: a "
        "peneira que a posse arma, e quem tem de perguntar por ela é o "
        "DESPACHO — `daemon/lifecycle.py`, no bloco do "
        "`_dispatch_gamepad_emulation`, que hoje manda os botões CRUS ao "
        "gamepad virtual gateado só pelos 0,3 s de grace e sobrevive de "
        "propósito ao `daemon.pause` e ao modo jogo. Sem essa pergunta, "
        "confirmar uma entrada com o cabo na mão dispara um pulo ou um tiro "
        "no jogo aberto atrás da janela. "
        "ONDE O CAMINHO SE PERDE: o daemon não pergunta. NÃO fiz porque "
        "`daemon/lifecycle.py` não é posse da L1-F (regra R-A da leva: "
        "precisou de arquivo alheio, relata e para). "
        "O QUE A FECHA: uma linha no despacho, subtraindo o que esta função "
        "devolve. DONO: a Onda do daemon, ou quem coordena a leva seguinte."
    ),
    # `formata_pt_br` SAIU daqui em 26/08/2026, na edição que o ligou (BG-03):
    # ele virou o DONO ÚNICO da conversão `260.4` → `260,4`, e as duas cópias
    # que a árvore mantinha — `app/actions/config/secao_controles.py::_numero` e
    # `integrations/plano_de_radio.py::_numero`, esta última com um comentário
    # que prometia "mesma forma que…" enquanto reescrevia a conta — passaram a
    # chamá-lo. A razão antiga dizia "as abas continuam formatando número à
    # mão"; era exatamente isso, e é isso que deixou de valer. Não se guarda a
    # entrada velha ao lado da nova.
    "app/fala_do_mapa.py::Numero": (
        "MEDIDO em 25/08/2026, e REMEDIDO em 26/08 — quando a irmã dele "
        "(`formata_pt_br`) GANHOU CAMINHO e saiu daqui, e ele NÃO caiu junto. "
        "A razão antiga dizia 'cai junto com ela'; era um palpite, e a medição "
        "o derrubou. Ele é o tipo que amarra uma constante Python medida a uma "
        "célula em prosa do mapa (`fala_do_mapa.py`:200-222). "
        "ONDE O CAMINHO SE PERDE: quem publica os números medidos é a tupla "
        "crua `NUMEROS_MEDIDOS_NO_MAPA` de `integrations/radio_da_mesa.py`:153-157, "
        "com os mesmos quatro campos e nenhum construtor que os valide — o "
        "`__post_init__` do `Numero` nunca roda sobre ela. "
        "O QUE A FECHA: aquela tupla virar uma tupla de `Numero`. NÃO fiz na "
        "L3-F porque `integrations/radio_da_mesa.py` não é posse dela (regra "
        "R-A da leva de 26/08). DONO: quem tocar o medidor de rádio."
    ),
    "profiles/schema.py::resolver_teclado_emulado": (
        "MEDIDO em 25/08/2026: está no `__all__` (:1345), o próprio módulo a "
        "cita em comentário (:972), e nenhum caminho de produção a executa. "
        "ONDE O CAMINHO SE PERDE: a resolução de teclado emulado continua "
        "acontecendo onde acontecia antes. "
        "O QUE A FECHA: o carregador de perfil chamá-la. NÃO fiz porque "
        "`profiles/schema.py` é posse da frente B2 (Onda 11 - Sistema) nesta "
        "madrugada. DONO: B2, ou a Onda 6 - Perfis na leva seguinte."
    ),
    # --- A aba Configurações (23/08/2026): o censo mede, e a tela não pergunta
    # `hub_em_comum` SAIU daqui em 26/08/2026, na edição que a ligou: a seção
    # "A mesa" (`app/actions/config/secao_mesa.py::_frase_do_hub_em_comum`) a
    # chama e publica a linha do hub em comum. A razão antiga dizia "NÃO fiz
    # porque é texto novo na tela"; o texto entrou marcado `PROVISÓRIO — decisão
    # dela`, que é o caminho que a R-E da leva abriu para não travar a frente.
    "integrations/censo_do_barramento.py::filhos_de": (
        "MEDIDO em 23/08/2026, e REMEDIDO em 26/08: continua sem chamador de "
        "produção. Ela responde 'quem pendura DIRETAMENTE neste nó, em ordem "
        "de porta', que é a pergunta de baixo da linha do hub em comum — o que "
        "separa 'três adaptadores num hub sobrando' de 'três adaptadores num "
        "hub com webcam e HD externo'. "
        "ONDE O CAMINHO SE PERDE: a linha do hub que a L2-E plantou em 26/08 "
        "conta os ADAPTADORES e o destino, e não diz o que MAIS divide o hub; "
        "a seção continua sem widget onde uma lista de vizinhos caberia. "
        "O QUE A FECHA: uma segunda frase nessa mesma linha, dizendo quem mais "
        "está no hub. NÃO fiz na L2-E porque é frase nova de tela além da que "
        "a ordem daquela frente pediu, e cada frase provisória a mais é uma "
        "decisão a mais na fila dela. DONO: a frente do léxico, ou quem "
        "coordenar a leva que fizer a prova de tela desta linha."
    ),
    "integrations/apelido_do_dongle.py::costurar_a_mesa": (
        "MEDIDO em 22/08/2026, RECONFERIDO em 23/08 e DECIDIDO em 25/08: é "
        "promessa ao produto e o caminho está DELIBERADAMENTE fechado — a "
        "nota datada está no próprio docstring da função (`:588-602`), e ela "
        "diz o contrário do que um chamador faria. Desde `e5376a0` (22/08, "
        "21h26) o `scripts/bt_active_mode.sh:349` itera TODOS os adaptadores "
        "que hospedam Nintendo (`_hci_com_nintendo`, `:281`), e o mesmo commit "
        "registra que resolveu 'a duplicidade … dois escritores do mesmo "
        "alias'. "
        "ONDE O CAMINHO SE PERDE, e é de propósito: ligar esta função no "
        "install ou no arranque do daemon RECRIA a duplicidade que aquele "
        "commit desfez — dois escritores do mesmo alias de BlueZ. "
        "O QUE A FECHA: nada, e é isso que mudou. A pergunta de dono virou "
        "`D-COSTURA-BLUEZ` em `docs/data/decisoes-dela.csv` e foi DECIDIDA em "
        "25/08/2026 — **o script continua dono**. Esta entrada deixou de ser "
        "uma pergunta em aberto e passou a ser o registro de uma escolha: dar "
        "chamador a esta função é REGRESSÃO até que a decisão seja revertida, "
        "e quando for, o `bt_active_mode.sh` para de costurar NO MESMO commit."
    ),
    # LÁPIDE — PONTE-NA-TELA-01, e a cura chegou em 25/08/2026.
    #
    # Aqui moravam `app/actions/home_actions.py::desfecho_da_troca` e
    # `::toast_da_troca_de_mascara`, declaradas como dívida em 19/08/2026 com a
    # razão escrita: *"NÃO fiz porque muda assinatura e o texto que sai na tela
    # dela"*. A assinatura mudou (I1 da INÍCIO NÃO MENTE-01): o `ao_aplicar` do
    # `footer_actions._transicao_de_modo` passou a RECEBER o resultado, e os
    # dois chamadores — o "Aplicar" e o "Salvar Perfil" — repassam. As duas
    # entraram juntas, como a declaração dizia que teria de ser.
    #
    # As entradas SAÍRAM porque o `test_nenhuma_lapide_sobreviveu_a_propria_cura`
    # as reprovaria: registro que sobrevive à cura vira mentira. O texto que sai
    # na tela continua sendo palavra dela — mas isso é prova de tela, não
    # dívida de caminho, e não é aqui que se registra.
    # --- a família mais numerosa: o desligar que ninguém chama --------------
    "daemon/subsystems/ipc.py::stop_ipc": (
        "REMEDIDO em 26/08/2026, e a razão de 12/08 estava ERRADA. Ela dizia "
        "que o `shutdown` não derrubava o servidor de IPC e mandava a próxima "
        "pessoa caçar um defeito vivo; o endereço que citava "
        "(connection.py:821-900) nem existe mais. O `shutdown` está em "
        "`daemon/connection.py:1286` e derruba o IPC ele mesmo, em linha: "
        "`await asyncio.wait_for(daemon._ipc_server.stop(), timeout=2.0)` "
        "(`:1364`) e `daemon._ipc_server = None` (`:1365`). "
        "ONDE O CAMINHO SE PERDE: não há caminho perdido — há DUPLICAÇÃO. "
        "Esta utilitária faz exatamente o que aquelas duas linhas fazem, e só "
        "`tests/` a chama. "
        "O QUE A FECHA: a mesma decisão de desenho de sempre, agora com o "
        "preço certo na mesa — ou o `shutdown` passa a delegar às três "
        "utilitárias (e ganha o teto de 2 s num lugar só), ou as três somem e "
        "o `shutdown` segue dono único do desligar. Não é urgência: nada fica "
        "de pé hoje por causa disto."
    ),
    "daemon/subsystems/udp.py::stop_udp": (
        "REMEDIDO em 26/08/2026, junto com `stop_ipc`, e pelo mesmo motivo: a "
        "razão de 12/08 apontava um `shutdown` que não derruba o UDP, e o "
        "`shutdown` (`daemon/connection.py:1286`) derruba — "
        "`await asyncio.wait_for(daemon._udp_server.stop(), timeout=2.0)` "
        "(`:1368`), `daemon._udp_server = None` (`:1369`). "
        "ONDE O CAMINHO SE PERDE: em lugar nenhum; o que sobra é DUPLICAÇÃO "
        "de duas linhas, com só `tests/` chamando a utilitária. "
        "O QUE A FECHA: a decisão de desenho descrita na entrada de "
        "`stop_ipc` — as três se fecham juntas ou nenhuma."
    ),
    "daemon/subsystems/autoswitch.py::stop_autoswitch": (
        "REMEDIDO em 26/08/2026. A razão de 12/08 dizia que 'a thread do "
        "autoswitch é derrubada pelo fim do processo em vez de por um caminho "
        "de parada' — e isso é FALSO: o `shutdown` "
        "(`daemon/connection.py:1286`) chama `daemon._autoswitch.stop()` "
        "(`:1372`) e descarta a referência (`:1373`). O autoswitch toca disco, "
        "então a razão velha mandava caçar uma perda de dado que não existe. "
        "ONDE O CAMINHO SE PERDE: em lugar nenhum — DUPLICAÇÃO, como nas duas "
        "irmãs, com só `tests/` chamando a utilitária. "
        "O QUE A FECHA: a mesma decisão de desenho da entrada de `stop_ipc`."
    ),
    # --- subsystems e motores que nada instancia ---------------------------
    "daemon/subsystems/hotkey.py::HotkeySubsystem": (
        "MEDIDO em 12/08/2026: a classe existe, tem `name = 'hotkey'` e um "
        "`start` que o próprio docstring chama de `Noop`, e NÃO está no "
        "`SUBSYSTEM_REGISTRY` de daemon/subsystems/__init__.py:41. Quem sobe o "
        "hotkey de verdade é lifecycle.py:705, chamando `start_hotkey_manager` "
        "direto. A classe é uma sentinela de um registro que ninguém itera. "
        "O QUE A FECHA: ou ela entra no registro e o `lifecycle` para de subir "
        "o hotkey à mão, ou ela sai da árvore. Como o próprio "
        "`SUBSYSTEM_REGISTRY` confessa no docstring do módulo (linha 13) que "
        "`não é iterado por ninguém em produção`, fechar isto de verdade é "
        "fechar o registro inteiro — trabalho de desenho, não de uma linha."
    ),
    "core/rumble.py::RumbleEngine": (
        "MEDIDO em 12/08/2026, e REMEDIDO em 26/08/2026: nenhuma instanciação "
        "em `src/`, e agora nenhum resto de leitura também. A pergunta que esta "
        "entrada abriu — 'foi SUBSTITUÍDO ou nunca foi ligado?' — está "
        "RESPONDIDA: foi SUBSTITUÍDO. O funil vivo da política de vibração é "
        "`core/rumble.py::_effective_mult`, e as três rotas que o chamam "
        "(`daemon/ipc_rumble_policy.apply_rumble_policy`, "
        "`daemon/subsystems/rumble.reassert_rumble` e "
        "`daemon/subsystems/gamepad._game_rumble_mult`) guardam o debounce na "
        "memória do daemon (`_last_auto_mult` / `_last_auto_change_at`). As "
        "DUAS frases que afirmavam o contrário foram substituídas pela "
        "informação certa: a de `daemon/ipc_handlers.py` em 24/08 e a de "
        "`daemon/ipc_rumble_policy.py` na L3-F, em 26/08 — junto com o "
        "`getattr(daemon, '_rumble_engine')` que a sustentava. "
        "ONDE O CAMINHO SE PERDE: a classe segue na árvore, com throttle e "
        "`link()`, sem ninguém que a construa. "
        "O QUE A FECHA: **apagá-la**, que é o que 'é resto' quer dizer. NÃO "
        "fiz na L3-F porque os chamadores restantes são TESTES fora da posse "
        "dela (`test_rumble_policy.py`, `test_led_and_rumble.py`, "
        "`test_politica_de_vibracao_a_escada_que_amplifica.py`) e a regra R-A "
        "da leva de 26/08 manda relatar, não escrever em arquivo alheio. "
        "DONO: quem coordenar a leva seguinte, num commit só com os três testes."
    ),
    # `daemon/subsystems/external_mask.py::ExternalMaskRegistry` MOROU AQUI e
    # foi APAGADA em 15/08/2026, pelo motivo que a própria entrada mandava:
    # A MÁSCARA GANHOU CHAMADOR. Ela respondeu a contradição que a entrada
    # descrevia (a frase de 10/08 em `profiles/schema.py` passa a valer só para
    # o `mode`), e a máscara por jogador virou código: `registro_de_mascaras()`
    # e `mascara_efetiva()` são consultados na criação de TODO gamepad virtual
    # (`integrations/uinput_gamepad.py` e `integrations/uhid_gamepad.py`,
    # métodos `for_flavor`). O degrau que ainda falta é o de baixo — passar a
    # IDENTIDADE do jogador — e ele tem lápide própria, logo abaixo, em
    # `::vpad_ficou_para_tras`. Não se guarda a entrada velha ao lado da nova:
    # ela mandaria a próxima pessoa procurar um chamador que já existe.
    # `daemon/subsystems/external_mask.py::vpad_ficou_para_tras` MOROU AQUI e
    # foi APAGADA em 29/08/2026, pelo motivo que a própria entrada mandava: A
    # CORRENTE FECHOU. A entrada dizia, palavra por palavra, o que a fecharia —
    # "`desired_flavor` deixar de ser um valor e passar a ser função do MAC" e
    # "as mesmas duas linhas que fazem `_promote_player` passar `identity=mac`
    # ao `make_virtual_pad`" — e foi exatamente isso, sob a decisão dela
    # `D-A-MASCARA-POR-CONTROLE-VALE-NO-APLICAR`:
    #   - `integrations/virtual_pad.py::make_virtual_pad` ganhou `identity` e
    #     resolve `mascara_efetiva` ANTES de escolher o backend (a armadilha que
    #     `external_mask.py:59-68` descreveu para quem escrevesse este degrau);
    #   - `daemon/subsystems/gamepad.py` passa `primary_identity(daemon)`;
    #   - `daemon/subsystems/coop.py::_promote_player` passa `identity=mac`, e o
    #     laço do `_sync_full` chama `vpad_ficou_para_tras` — que é este símbolo,
    #     agora com chamador em produção.
    # A razão de não ter sido feito então ("`coop.py` sob edição de outra frente
    # no mesmo dia") caducou. Não se guarda a lápide ao lado da cura: ela
    # mandaria a próxima pessoa procurar um chamador que já existe.
    # --- as duas metades das notificações ----------------------------------
    "integrations/desktop_notifications.py::notify_battery_low": (
        "MEDIDO em 12/08/2026: só `tests/` a chama; em `src/` só existe a "
        "citação do exemplo em comentário (linha 220). É a outra ponta da "
        "lacuna do interruptor `..._DESKTOP_NOTIFICATIONS`: mesmo que alguém "
        "ligasse a env hoje, nada chamaria esta função, porque nenhum ponto do "
        "daemon observa a bateria caindo e a invoca. "
        "O QUE A FECHA: chamar do lugar onde a bateria já é lida — a mesma "
        "borda que hoje só atualiza a janela. A ordem certa é ligar o "
        "interruptor e o chamador na MESMA leva; ligar só um dos dois deixa a "
        "promessa igualmente vazia e mais difícil de enxergar."
    ),
    "integrations/desktop_notifications.py::notify_battery_recovered": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. É o par de "
        "`notify_battery_low` — sem ela, a dedução por `once_key` nunca é "
        "rearmada e o aviso de bateria baixa seria emitido UMA vez por processo, "
        "mesmo que ela carregasse o controle e ele descarregasse de novo. "
        "O QUE A FECHA: a mesma borda da entrada anterior, na mesma leva; as "
        "duas juntas ou nenhuma, porque metade da cura é pior que nenhuma aqui."
    ),
    # `core/led_control.py::apply_led_settings` e `::player_bitmask` MORARAM
    # AQUI e foram RECLASSIFICADOS em 13/08/2026 para `_NAO_E_PROMESSA`. A
    # pergunta que as duas entradas faziam — "descobrir por onde os LEDs chegam
    # ao aparelho HOJE" — foi respondida lendo, e a resposta é que chegam: pelo
    # `OutputSpec` de `profiles/manager.py:392`. Não eram dívida; eram uma
    # afirmação errada citada como prova. Ver as razões novas lá em cima.
    # --- a janela pedindo ao daemon ----------------------------------------
    # ELO-MUDO-01 / P1 (23/08/2026): a ponte já entrega, a aba ainda não pede.
    # As entradas desta leva nasceram JUNTAS e por decisão dela: o conserto do
    # lado da ponte é aditivo de propósito, porque os chamadores moram em
    # arquivos que outras frentes estavam editando no mesmo dia. Cada uma diz
    # qual linha a fecha.
    #
    # `trigger_set_detalhado` e `trigger_reset_detalhado` SAÍRAM daqui em
    # 25/08/2026, na mesma edição que os ligou
    # (GATILHOS-APLICADO-COM-PROVA/T3): `_apply_trigger`, `_send_trigger_named`
    # e `_reset_trigger` de `app/actions/triggers_actions.py` chamam os dois, e
    # o `_toast_trigger` decide pelo CORPO do daemon, via `frase_do_desfecho`.
    # `led_set_detalhado` e `player_leds_set_detalhado` saíram pelo mesmo
    # motivo em 26/08/2026 (BG-01): `_aplicar_cor_no_controle`,
    # `on_lightbar_off`, `_enviar_led_em_todos` e `_enviar_player_leds` de
    # `app/actions/lightbar_actions.py` chamam os dois.
    #
    # PODA DE 26/08/2026 (BG-07, LEVA-3-C): CINCO entradas de
    # `app/ipc_bridge.py` saíram daqui porque o SÍMBOLO saiu do módulo —
    # `apply_draft`, `rumble_policy_set`, `rumble_policy_set_detalhado`,
    # `trigger_reset` e `mouse_emulation_set`. Eram invólucros estreitos, sem
    # nenhum chamador de produção, e as razões deles mandavam apagar. A trava
    # que os segurava — "a assinatura pode estar sendo importada pelo applet do
    # COSMIC" — CAIU: o applet é Rust (`packaging/cosmic-applet/src/`), fala
    # JSON-RPC por socket (`ipc.rs:3`) e `grep` pelos cinco nomes ali devolve
    # ZERO. Um processo Rust não importa função Python.
    #
    # RESTAM TRÊS, abaixo: as duas da Lightbar e o mic da mesa cheia.
    "app/ipc_bridge.py::led_set": (
        "MEDIDO em 26/08/2026, e é EFEITO da própria cura (BG-01): os três "
        "chamadores de produção eram `app/actions/lightbar_actions.py` — o "
        "`Aplicar no controle`, o `Apagar` e o funil por MAC do `Todos` —, e a "
        "BG-01 trocou os três por `led_set_detalhado`, porque o `bool` desta "
        "função jogava fora o `aplicado_em`/`guardado_em` que o daemon publica "
        "desde a APLICAR-VERDADE-01. Ficou o invólucro que descarta o corpo, "
        "com zero chamadores — a mesma forma dos cinco invólucros podados em "
        "26/08/2026 pela BG-07, cuja nota está no comentário logo acima. "
        "O QUE A FECHA: apagar `led_set` e deixar só o `_detalhado`, levando o "
        "docstring do FEAT-LED-BRIGHTNESS-01/PERFIL-05 junto. "
        "FATO ERRADO, SUBSTITUÍDO em 26/08/2026: esta razão dizia que "
        "`app/ipc_bridge.py` estava no `nao_toca` da leva. Está na POSSE da "
        "LEVA-3-C, e a BG-07 podou cinco irmãos deste no mesmo arquivo. O que "
        "segurou `led_set` foi a ORDEM da frente, que nomeia cinco funções e "
        "não esta — e a razão escrita ali (`led_set` continuaria viva por "
        "outro caminho) foi MEDIDA e é falsa: AST e `grep` concordam que não "
        "há chamador nenhum em `src/` fora do próprio módulo. "
        "DONO: a próxima leva, e agora sem trava — é poda pura de dez linhas, "
        "mais os CINCO pontos que as citam em "
        "`tests/unit/test_ipc_bridge.py` (:148, :152, :176, :257, :262) e os "
        "DOIS métodos de "
        "`tests/unit/test_p1_a_resposta_do_daemon_atravessa_a_ponte.py` (:396 "
        "e :407)."
    ),
    "app/ipc_bridge.py::player_leds_set": (
        "MEDIDO em 26/08/2026: irmão exato do `led_set` acima, e pela mesma "
        "edição (BG-01). O único chamador de produção era `_enviar_player_leds` "
        "em `app/actions/lightbar_actions.py`, nas duas rotas — alvo escolhido "
        "e um pedido por MAC em `Todos` —, e as duas passaram a "
        "`player_leds_set_detalhado`, que entrega o corpo com `bits` ecoado "
        "(`ipc_handlers.py`, `_handle_led_player_set`). "
        "O QUE A FECHA: a mesma poda do `led_set`, no mesmo commit e pelo mesmo "
        "dono. DONO: a próxima leva — ver a correção de fato na razão do "
        "`led_set`, que vale igual para este."
    ),
    "app/actions/external_controllers.py::short_button_label": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. O docstring descreve uma "
        "superfície concreta que não existe: `Rótulo curto para o botão do "
        "seletor no topo (cabe ao lado dos DualSense)`, com exemplos "
        "`8BitDo · cabo`. A função irmã `brand_of`, do mesmo arquivo, é usada. "
        "O QUE A FECHA: a tela do seletor de topo, se ela for nascer. É "
        "DECISÃO DELA se esse seletor entra — e enquanto não entrar, o rótulo é "
        "desenho pronto esperando a superfície, não defeito."
    ),
    # --- preferências de sessão que a janela não lê -------------------------
    # AS TRÊS ENTRADAS QUE MORAVAM AQUI — `utils/session.py`:
    # `::save_mouse_emulation_enabled`, `::load_mouse_emulation_enabled` e
    # `::load_keyboard_emulation_enabled` — SAÍRAM em 26/08/2026 porque os três
    # símbolos foram PODADOS. As duas primeiras eram invólucros legados
    # (FEAT-MOUSE-PERSIST-01) que o próprio docstring mandava não usar; a
    # terceira somava um default PRÓPRIO a uma precedência que já tem dono.
    #
    # A TRAVA QUE AS SEGURAVA CAIU, e a queda é medida. A entrada do
    # `save_mouse_emulation_enabled` dizia: *"não apago nesta leva porque as
    # duas são símbolo público e podem estar sendo importadas por fora de
    # `src/` — o applet do COSMIC e os plugins de terceiros são os dois lugares
    # onde este portão é cego por desenho"*. MEDIDO em 26/08/2026: o applet do
    # COSMIC é RUST (`packaging/cosmic-applet/Cargo.toml` +
    # `src/{main,app,ipc}.rs`), conversa com o daemon por JSON-RPC no socket, e
    # NÃO existe um único arquivo `.py` sob `packaging/`. Ele não importa
    # Python — logo não importa estes nomes. O `plugin_api` continua sendo
    # ponto cego por desenho, mas ele é contrato de MÉTODO (`on_*`), que este
    # portão nem varre, e nenhum destes três nomes aparece nele.
    #
    # A CORREÇÃO DE FATO da terceira: a entrada mandava fechá-la *"chamando do
    # boot do daemon, onde o `keyboard_emulation.flag` já é lido"*. O boot JÁ
    # lê o flag, e não por ela: `daemon/lifecycle.py:841-842` chama
    # `load_keyboard_preference()` direto e só sobrescreve o piso quando há
    # opinião gravada. Fiá-la seria pôr um segundo default no meio de uma
    # precedência que já tem um. A ASSIMETRIA que ela documentava (teclado nasce
    # LIGADO, mouse nasce desligado) NÃO se perdeu: está escrita, com a data,
    # onde a função morava, em `utils/session.py`.
    # --- linha de comando do kernel ----------------------------------------
    # `integrations/kernel_cmdline.py::plan_cmdline` MOROU AQUI, e foi
    # RECLASSIFICADA para `_NAO_E_PROMESSA` em 26/08/2026 — não é dívida, e a
    # razão que a punha aqui era um FATO ERRADO, substituído lá.
    # `integrations/kernel_cmdline.py::ownership_record` MOROU AQUI, e a
    # entrada SAIU em 26/08/2026 porque o símbolo foi PODADO. A razão longa que
    # estava aqui já tinha corrigido, em 15/08, o fato errado de que "ninguém
    # grava esse registro": ele É gravado, em produção, pelo heredoc do passo
    # `3e` do `install.sh` (que imprime o `a.owner` de cada ação) mais o
    # `_register_cmdline_owner` do shell, que escreve
    # `~/.local/state/hefesto-dualsense4unix/cmdline-owners.conf` — o arquivo
    # que o `uninstall.sh` lê. E ela já dizia o resto: a regra do dono estava
    # escrita DUAS vezes, e as duas JÁ divergiam (o shell preserva um dono
    # anterior "hefesto"/"compartilhado" quando o plano novo diz "terceiro";
    # esta função não tinha essa lógica).
    # A entrada pedia "decidir de quem é o planejamento" e recusava fechar por
    # conta própria "porque fechar aqui é mexer no `install.sh`". A poda decide
    # sem tocar no `install.sh`: sai a forma SEM chamador, fica a que roda na
    # máquina dela. Quem quiser o par continua tendo `a.param` e `a.owner` em
    # cada `CmdlineAction` — é exatamente o que o heredoc lê.
    # `integrations/kernel_cmdline.py::strip_quirks_token` MOROU AQUI, e a
    # entrada afirmava "esse cuidado está escrito e nunca roda", pedindo como
    # cura que "o `uninstall.sh` chamar este caminho". SUBSTITUÍDO em
    # 13/08/2026, porque o fato era falso e não decisão a preservar: o
    # `uninstall.sh` já chama, em uninstall.sh:1243 (`rest, changed =
    # kc.strip_quirks_token(tok)`), dentro do heredoc que importa o módulo. Era
    # o PORTÃO que não enxergava — ver `_ROTEIROS_DE_PRODUCAO`. A entrada saiu
    # porque a varredura passou a alcançá-la, e não porque alguém a apagou à
    # mão: é o que `test_nenhuma_lapide_sobreviveu_a_propria_cura` cobra.
    # --- relatórios que ninguém pede ---------------------------------------
    # `profiles/curva_propria.py::gerar_tabela_markdown` FECHOU em 13/08/2026 e
    # a lápide saiu daqui pela porta certa: a cura que ela mesma prescrevia
    # ("um passo em `scripts/gerar-mapa.py` ou um script irmão que escreva o
    # arquivo, mais o `--check` correspondente") nasceu como
    # `scripts/gerar-tabela-de-curvas.py`, que a chama em `:83`. Quem apagou
    # esta entrada não foi a mão de ninguém: foi
    # `test_nenhuma_lapide_sobreviveu_a_propria_cura` reprovando — o portão
    # pegou a leva que o curou, que é exatamente o que ele existe para fazer.
    # RETIFICADO em 22/08/2026: o que nasceu em 13/08 foi um GERADOR DE
    # DOCUMENTAÇÃO, e a régua de alcance não o conta como caminho de produção.
    # O símbolo voltou à lista, agora em `_NAO_E_PROMESSA`, e a razão está lá.
    # A lápide fica porque o movimento de 13/08 aconteceu; a conclusão dele —
    # "o caminho de produção nasceu" — é que era falsa.
    # `profiles/sanidade.py::verificar_perfis_do_disco` MOROU AQUI, e foi
    # RECLASSIFICADA para `_NAO_E_PROMESSA` em 26/08/2026: não é dívida, e a
    # razão que a punha aqui era um FATO ERRADO, substituído lá.
    # --- a TUI --------------------------------------------------------------
    # `tui/app.py::main_async` MOROU AQUI, e a entrada SAIU em 26/08/2026
    # porque o símbolo foi PODADO. A entrada oferecia duas curas — "um console
    # script em `pyproject.toml`, se a TUI for para ter entrada própria; ou
    # apagar, se `run_tui` já é a entrada" — e a segunda é a certa: `run_tui` É
    # a entrada, e o console script novo seria produto novo, que não é decisão
    # de agente. REMEDIDO em 26/08/2026: zero chamadores em `src/`, `tests/`,
    # `scripts/`, `pyproject.toml` e nos heredocs Python do
    # `install.sh`/`uninstall.sh`.
    # --- AS TRÊS CORRENTES FECHADAS EM SI MESMAS (22/08/2026) ----------------
    # As 21 entradas abaixo são o que a régua PLANA perdoava e a régua de
    # alcance acusou. Nenhuma é dívida nova: são três módulos inteiros escritos
    # e nunca ligados, cujos símbolos se chamavam entre si e por isso pareciam
    # entregues. É o defeito-mãe desta casa na forma mais cara que ele tem.
    "profiles/curva_propria.py::CurvaPropria": (
        "MEDIDO em 22/08/2026: NENHUM módulo de `src/` importa "
        "`profiles/curva_propria.py`. O formato do efeito de gatilho próprio "
        "(CR-02) está escrito, validado e desligado — `profiles/schema.py` não o "
        "cita, e o docstring do módulo (:34) confessa o estado: *não existe "
        "nenhuma curva própria no repositório*. Até 21/08 a régua plana o "
        "perdoava pelo gerador de documentação de `scripts/`. "
        "O QUE FECHA: a ONDA-GATILHOS-05, que dá tela ao catálogo e põe a mão "
        "dela no gatilho para produzir a primeira curva. SUBSTITUÍDO em "
        "29/08/2026: esta linha dizia `a CR-04`, e a CR-04 saiu do disco com a "
        "corrente do clean-room, por decisão dela — não há mais sprint futura "
        "esperando pela primeira curva."
    ),
    "profiles/curva_propria.py::CatalogoCurvasProprias": (
        "MEDIDO em 22/08/2026. Irmã da anterior (ver `::CurvaPropria`): é o "
        "catálogo compartilhado que guarda as curvas (:259), e o único leitor "
        "dele é `scripts/gerar-tabela-de-curvas.py`:52, um gerador de "
        "documentação. Nada em `src/` o carrega do disco."
    ),
    # --- ONDA0-Z7 · O AMBIENTE PRESUMIDO 01 (24/08/2026): primitivas
    # entregues DELIBERADAMENTE sem fiação — a sprint (§10) nomeia quem
    # pendura cada uma, para não colidir com as ondas de aba em andamento.
    "app/actions/ambiente_na_tela.py::descrever_teclado_na_tela": (
        "ENTREGUE em 24/08/2026 (T-12, ONDA0-Z7); a razão foi SUBSTITUÍDA em "
        "26/08/2026 (LEVA-3-D), porque a de antes mandava pendurar esta frase "
        "e a medição derrubou a ordem. ONDE O CAMINHO SE PERDE, e agora são "
        "duas coisas: (1) a função procura `osk_disponivel` no TOPO do "
        "`state`, e o daemon a publica DENTRO do bloco `keyboard_emulation` "
        "(`daemon/ipc_handlers.py:_keyboard_emulation_payload`) — contra "
        "`tests/fixtures/state_full_quatro_controles.json`, capturado com a "
        "máquina TENDO teclado na tela, ela responde 'não consegui ler'; "
        "(2) o defeito que ela existia para curar FECHOU por outro caminho em "
        "25/08 (`e909b62`, N12): `app/actions/mouse_actions.py:_anotar_teclado"
        "_na_tela` lê a chave do lugar certo e "
        "`app/actions/input_actions.py:265 frase_do_teclado_na_tela` a "
        "transforma na frase da legenda — no gancho exato que a razão antiga "
        "nomeava. Pendurá-la hoje poria DUAS frases sobre o mesmo fato na "
        "mesma legenda, uma delas falsa. O QUE FECHA: a DECISÃO entre as duas "
        "— consertar o nível da chave e apagar a irmã, ou apagar esta. Enquanto "
        "não se decide, `tests/unit/test_ambiente_presumido_01_o_que_a_maquina"
        "_nao_tem.py::TestOQueEstaFraseNaoAlcancaNoStateFullDeVerdade` trava a "
        "medição e reprova em quem consertar o nível sem escolher."
    ),
    "app/actions/ambiente_na_tela.py::descrever_display_grafico": (
        "ENTREGUE em 24/08/2026 (T-12, ONDA0-Z7). Lê "
        "`window_detect_backend`/`window_detect_reason`, complementando (sem "
        "substituir) `daemon_actions.descrever_deteccao_de_janela`. REMEDIDO "
        "em 26/08/2026 (LEVA-3-D): ao contrário da irmã acima, esta função LÊ "
        "as chaves certas — `daemon/ipc_handlers.py:_window_detect_payload` as "
        "publica no TOPO do `state_full`, e contra os três fixtures reais ela "
        "responde a verdade. ONDE O CAMINHO SE PERDE: só falta o chamador, e "
        "ele mora fora do alcance de quem escreveu isto — o cartão é o "
        "`storm_card` do `gui/main.glade:2823` ('Saúde do sistema'), pintado "
        "por `app/actions/daemon_actions.py:1160 _refresh_window_detect_diag`, "
        "e uma frase a mais ali pede um `GtkLabel` novo no Glade (recurso de "
        "bancada, uma sprint por vez). O QUE FECHA: a Onda 11 · Sistema, com o "
        "rótulo no Glade e a pintura ao lado do `window_detect_diag_label`."
    ),
    "app/actions/ambiente_na_tela.py::descrever_steam_encontrada": (
        "ENTREGUE em 24/08/2026 (T-12, ONDA0-Z7). Lê `steam_layout_achado` — "
        "chave que NENHUMA frente desta sprint publica ainda em `state_full` "
        "(Z7-C não toca `daemon/ipc_handlers.py`, por posse declarada em §5). "
        "ONDE O CAMINHO SE PERDE: falta o publicador da chave, além do leitor "
        "de tela. O QUE FECHA: a Onda 11 · Sistema, ou quem publicar a chave "
        "primeiro (§10 da sprint)."
    ),
    "integrations/proton_pin.py::steam_root_ou_recusa": (
        "ENTREGUE em 24/08/2026 (T-09, ONDA0-Z7). `default_steam_root` "
        "continua excluindo Flatpak/Snap por decisão medida; esta função "
        "acrescenta o MOTIVO para a tela, no formato de recusa da Z1. ONDE O "
        "CAMINHO SE PERDE: Z7-C não toca `app/actions/emulation_actions.py` "
        "(posse declarada em §5) — o botão 'Travar Proton validado' ainda "
        "chama só `default_steam_root`. O QUE FECHA: a Onda 5 · Emulação liga "
        "o botão a esta função e decide a frase final com a Z1 (§10 da "
        "sprint)."
    ),
}

#: ONDA0-Z7 (24/08/2026): achado FORA do escopo desta sprint, durante a
#: execução — `app/ipc_bridge.py::machine_declare` e
#: `utils/maquina.py::gravar_maquina` JÁ estavam soltos e não-classificados
#: ANTES de qualquer mudança desta leva (conferido contra `3e7b6cb`, o commit
#: em que esta árvore nasceu — `git stash -u` + rodar este mesmo teste
#: devolve os dois, sozinhos, como únicas soltas). Não são meus para
#: declarar: nenhuma tarefa de ONDA0-Z7 os toca, e uma nota escrita às
#: pressas por quem não mediu o caminho vale menos que "NÃO VERIFICADO".
#: Relatado no relatório do executor para quem coordena decidir a régua 1-4.


# ===========================================================================
# A varredura — derivada em runtime, apontável para uma cópia
# ===========================================================================

#: Um literal de texto conta como chamador quando ele É o nome, INTEIRO — que é
#: o idioma do despacho por ``getattr``, o falso positivo que pegou a passada
#: anterior cinco vezes: ``getattr(pp, "lock_proton_for_all_games", None)``
#: (app/actions/daemon_actions.py:1477).
#:
#: MEDIDO em 12/08/2026, e por pouco esta linha não saiu errada: a primeira
#: versão contava toda PALAVRA de todo literal, e com ela a acusação caía de 33
#: para 32. O símbolo escondido era ``app/ipc_bridge.py::apply_draft``, salvo
#: por acaso pela chave de IPC ``"profile.apply_draft"`` — escrita noutro
#: módulo, para outra coisa, e que por conter a palavra o dava por alcançado.
#: Casar o literal INTEIRO não perdeu isenção legítima nenhuma (conferido: as
#: cinco chamadas por string continuam alcançadas) e devolveu uma promessa
#: solta de verdade. (Esse símbolo foi PODADO em 26/08/2026, pela BG-07; a
#: medição do instrumento é que fica — é ela que explica por que o casamento
#: é do literal inteiro, e não de palavra.)

#: Decoradores que ENTREGAM o símbolo a um framework, que passa a ser o
#: chamador. Derivado do decorador, nunca de uma lista de nomes de função:
#: hoje isenta 41 subcomandos de CLI (``@app.command``/``@app.callback`` do
#: typer, em ``cli/app.py`` e nos dez ``cli/cmd_*.py``), e isentará sozinho o
#: subcomando 42.
_DECORADORES_DE_FRAMEWORK = frozenset({"command", "callback", "hookimpl"})


@dataclass(frozen=True)
class Promessa:
    """Um símbolo público de módulo — o sítio onde o produto promete algo."""

    chave: str
    nome: str
    arquivo: str
    linha: int
    tipo: str


def _arvore(caminho: Path) -> ast.Module:
    return ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))


def _modulos(raiz: Path) -> list[Path]:
    return sorted(p for p in raiz.rglob("*.py") if "__pycache__" not in p.parts)


def trechos_python_embutidos(roteiro: Path) -> list[str]:
    """Os corpos de heredoc que um roteiro de shell entrega ao Python.

    A varredura anterior era CEGA a isto, e a cegueira tinha consequência
    escrita: uma função chamada pelo desinstalar desde julho aparecia na lista
    de dívida. Ler o shell como texto solto não serve — o nome também aparece
    nos comentários em prosa do próprio roteiro (uninstall.sh:1202 cita
    ``strip_quirks_token`` numa linha ``#``), e comentário não é chamada. O que
    vale é o corpo do heredoc, e ele é Python de verdade: sai daqui e entra em
    ``ast.parse``, pela MESMA régua que mede ``src/``.
    """
    try:
        texto = roteiro.read_text(encoding="utf-8", errors="ignore")
    except OSError:  # pragma: no cover — roteiro ilegível é problema dele
        return []
    linhas = texto.splitlines()
    trechos: list[str] = []
    indice = 0
    while indice < len(linhas):
        abertura = _HEREDOC_PYTHON.search(linhas[indice])
        indice += 1
        if abertura is None:
            continue
        delimitador = abertura.group(2)
        corpo: list[str] = []
        while indice < len(linhas) and linhas[indice].strip() != delimitador:
            corpo.append(linhas[indice])
            indice += 1
        indice += 1  # pula o próprio delimitador de fechamento
        trechos.append(textwrap.dedent("\n".join(corpo)))
    return trechos


#: O nome do pacote — a raiz de todo import que este portão sabe resolver.
_PACOTE = "hefesto_dualsense4unix"


@dataclass(frozen=True)
class _Mapa:
    """A árvore lida UMA vez: módulos, AST, o que cada um define e reexporta."""

    modulos: dict[str, Path]
    arvores: dict[str, ast.Module]
    define: dict[str, frozenset[str]]
    reexporta: dict[str, dict[str, tuple[str, str]]]


def _nome_de_modulo(alvo: Path, caminho: Path) -> str:
    partes = list(caminho.relative_to(alvo).with_suffix("").parts)
    if partes[-1] == "__init__":
        partes.pop()
    return ".".join([_PACOTE, *partes])


def _base_do_import(mapa: _Mapa, modulo: str, no: ast.ImportFrom) -> str:
    """A que módulo aponta o ``from ... import`` deste nó.

    Trata o import RELATIVO e o idioma do módulo que roda das duas formas —
    como parte do pacote e como roteiro solto. ``sentinela_do_wrapper.py``:525
    tem os dois (``from .steam_launch_options import x`` e
    ``from steam_launch_options import x``, num ``try/except ImportError``), e
    sem esta tradução o segundo apontaria para um módulo que não existe: os
    dois símbolos de ``steam_launch_options`` apareceriam órfãos. MEDIDO em
    22/08/2026.
    """
    if no.level:
        partes = modulo.split(".")
        e_pacote = mapa.modulos[modulo].name == "__init__.py"
        base = partes if e_pacote else partes[:-1]
        if no.level > 1:
            base = base[: len(base) - (no.level - 1)]
        return ".".join([*base, no.module] if no.module else base)
    alvo = no.module or ""
    if alvo.split(".")[0] != _PACOTE and modulo in mapa.modulos:
        pai = (
            modulo
            if mapa.modulos[modulo].name == "__init__.py"
            else modulo.rsplit(".", 1)[0]
        )
        irmao = f"{pai}.{alvo}"
        if irmao in mapa.modulos:
            return irmao
    return alvo


def _mapear(alvo: Path) -> _Mapa:
    modulos = {_nome_de_modulo(alvo, p): p for p in _modulos(alvo)}
    arvores = {nome: _arvore(p) for nome, p in modulos.items()}
    mapa = _Mapa(modulos, arvores, {}, {})
    for nome, arvore in arvores.items():
        definidos: set[str] = set()
        for no in arvore.body:
            if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definidos.add(no.name)
            elif isinstance(no, ast.Assign):
                definidos |= {a.id for a in no.targets if isinstance(a, ast.Name)}
            elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
                definidos.add(no.target.id)
        mapa.define[nome] = frozenset(definidos)
        reexporta: dict[str, tuple[str, str]] = {}
        for no in ast.walk(arvore):
            if not isinstance(no, ast.ImportFrom):
                continue
            base = _base_do_import(mapa, nome, no)
            if base.split(".")[0] != _PACOTE:
                continue
            for apelido in no.names:
                if apelido.name != "*":
                    reexporta[apelido.asname or apelido.name] = (base, apelido.name)
        mapa.reexporta[nome] = reexporta
    return mapa


def _canonico(mapa: _Mapa, modulo: str, nome: str) -> tuple[str, str]:
    """Segue a cadeia de reexportação até o módulo que DEFINE o símbolo.

    Sem isto, ``from hefesto_dualsense4unix.daemon import X`` contaria para o
    ``__init__.py`` e o símbolo real, uma pasta abaixo, continuaria órfão.
    """
    visto: set[tuple[str, str]] = set()
    while (
        modulo in mapa.modulos
        and nome not in mapa.define.get(modulo, frozenset())
        and (modulo, nome) not in visto
    ):
        visto.add((modulo, nome))
        proximo = mapa.reexporta.get(modulo, {}).get(nome)
        if proximo is None:
            break
        modulo, nome = proximo
    return modulo, nome


def _com_ancestrais(mapa: _Mapa, modulo: str) -> set[str]:
    """O módulo e os pacotes que o Python roda para chegar nele."""
    saida = {modulo}
    partes = modulo.split(".")
    for corte in range(1, len(partes)):
        pai = ".".join(partes[:corte])
        if pai in mapa.modulos:
            saida.add(pai)
    return saida


def _importados(mapa: _Mapa, modulo: str) -> set[str]:
    saida: set[str] = set()
    for no in ast.walk(mapa.arvores[modulo]):
        if isinstance(no, ast.Import):
            for apelido in no.names:
                if apelido.name in mapa.modulos:
                    saida |= _com_ancestrais(mapa, apelido.name)
        elif isinstance(no, ast.ImportFrom):
            base = _base_do_import(mapa, modulo, no)
            if base in mapa.modulos:
                saida |= _com_ancestrais(mapa, base)
            for apelido in no.names:
                if f"{base}.{apelido.name}" in mapa.modulos:
                    saida |= _com_ancestrais(mapa, f"{base}.{apelido.name}")
    return saida


def _tabela_de_nomes(
    mapa: _Mapa, modulo: str, arvore: ast.AST, externo: bool = False
) -> dict[str, tuple[str, object]]:
    """Nome local -> o módulo (``módulo``) ou o símbolo (``símbolo``) que ele é."""
    tabela: dict[str, tuple[str, object]] = {}
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for apelido in no.names:
                if apelido.asname:
                    tabela[apelido.asname] = ("módulo", apelido.name)
                else:
                    raiz = apelido.name.split(".")[0]
                    tabela[raiz] = ("módulo", raiz)
        elif isinstance(no, ast.ImportFrom):
            base = (no.module or "") if externo else _base_do_import(mapa, modulo, no)
            for apelido in no.names:
                if apelido.name == "*":
                    continue
                chave = apelido.asname or apelido.name
                pleno = f"{base}.{apelido.name}"
                if pleno in mapa.modulos:
                    tabela[chave] = ("módulo", pleno)
                else:
                    tabela[chave] = ("símbolo", (base, apelido.name))
    return tabela


def _raizes_de_uma_fonte_externa(mapa: _Mapa, arvore: ast.AST) -> set[str]:
    """O que um roteiro de fora do pacote importa DELE — e vira raiz do alcance."""
    raizes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for apelido in no.names:
                if apelido.name in mapa.modulos:
                    raizes |= _com_ancestrais(mapa, apelido.name)
        elif isinstance(no, ast.ImportFrom):
            base = no.module or ""
            if base in mapa.modulos:
                raizes |= _com_ancestrais(mapa, base)
            for apelido in no.names:
                if f"{base}.{apelido.name}" in mapa.modulos:
                    raizes |= _com_ancestrais(mapa, f"{base}.{apelido.name}")
    return raizes


def _fecho_de_import(mapa: _Mapa, raizes: set[str]) -> set[str]:
    alcancados: set[str] = set()
    fila = list(raizes)
    while fila:
        modulo = fila.pop()
        if modulo in alcancados:
            continue
        alcancados.add(modulo)
        fila.extend(o for o in _importados(mapa, modulo) if o not in alcancados)
    return alcancados


@dataclass(frozen=True)
class _Contexto:
    """O que é preciso para resolver um nome ao MÓDULO que o define."""

    mapa: _Mapa
    modulo: str
    tabela: dict[str, tuple[str, object]]
    definidos: frozenset[str]


class _Referencias(ast.NodeVisitor):
    """Nomes ALCANÇADOS por um trecho de código, em três coleções.

    - ``nomes`` é a régua PLANA de até 21/08/2026. Ela sobrevive por uma razão
      só: ``_regua_plana`` a usa para as mordidas provarem, lado a lado, o que
      a régua nova pega e a velha perdoava. Nenhum portão a consulta;
    - ``resolvidas`` são pares ``(módulo, nome)`` — a régua de hoje;
    - ``planas`` é o que NÃO dá para resolver sem inferir tipo: literal de
      texto (o despacho por ``getattr``) e atributo cuja base não é módulo.

    Quatro decisões valem para as três, cada uma nascida de um falso positivo
    medido (ver o cabeçalho do arquivo): conta literal de texto INTEIRO; NÃO
    conta docstring; NÃO conta o conteúdo de ``__all__``; NÃO conta alvo de
    atribuição.
    """

    def __init__(self, contexto: _Contexto | None = None) -> None:
        self.nomes: set[str] = set()
        self.resolvidas: set[tuple[str, str]] = set()
        self.planas: set[str] = set()
        self._ctx = contexto
        self._docstrings: set[int] = set()

    def _marcar_docstring(self, no: ast.AST) -> None:
        corpo = getattr(no, "body", None)
        if not corpo:
            return
        primeiro = corpo[0]
        if (
            isinstance(primeiro, ast.Expr)
            and isinstance(primeiro.value, ast.Constant)
            and isinstance(primeiro.value.value, str)
        ):
            self._docstrings.add(id(primeiro.value))

    def visit_Module(self, no: ast.Module) -> None:
        self._marcar_docstring(no)
        self.generic_visit(no)

    def visit_FunctionDef(self, no: ast.FunctionDef) -> None:
        self._marcar_docstring(no)
        self.generic_visit(no)

    def visit_AsyncFunctionDef(self, no: ast.AsyncFunctionDef) -> None:
        self._marcar_docstring(no)
        self.generic_visit(no)

    def visit_ClassDef(self, no: ast.ClassDef) -> None:
        self._marcar_docstring(no)
        self.generic_visit(no)

    def visit_Assign(self, no: ast.Assign) -> None:
        # `__all__ = [...]` é DECLARAÇÃO de reexportação, não uso. Contá-la
        # deixaria todo símbolo se auto-satisfazer citando o próprio nome.
        if any(isinstance(a, ast.Name) and a.id == "__all__" for a in no.targets):
            return
        self.generic_visit(no)

    def visit_Name(self, no: ast.Name) -> None:
        if not isinstance(no.ctx, ast.Load):
            return
        self.nomes.add(no.id)
        if self._ctx is None:
            return
        entrada = self._ctx.tabela.get(no.id)
        if entrada is not None and entrada[0] == "símbolo":
            modulo, nome = entrada[1]  # type: ignore[misc]
            self.resolvidas.add(_canonico(self._ctx.mapa, modulo, nome))
        elif no.id in self._ctx.definidos:
            self.resolvidas.add((self._ctx.modulo, no.id))

    def visit_Attribute(self, no: ast.Attribute) -> None:
        if isinstance(no.ctx, ast.Load):
            self.nomes.add(no.attr)
            if self._ctx is not None and not self._resolve_atributo(no):
                # Base que não é módulo: `self.x.metodo()`, `obj.aplicar()`. Sem
                # inferir tipo não dá para dizer de quem é o `aplicar` — conta
                # plano, e o preço está declarado no cabeçalho.
                self.planas.add(no.attr)
        self.generic_visit(no)

    def _resolve_atributo(self, no: ast.Attribute) -> bool:
        assert self._ctx is not None
        partes: list[str] = []
        atual: ast.expr = no
        while isinstance(atual, ast.Attribute):
            partes.append(atual.attr)
            atual = atual.value
        if not isinstance(atual, ast.Name):
            return False
        partes.append(atual.id)
        partes.reverse()
        entrada = self._ctx.tabela.get(partes[0])
        if entrada is None or entrada[0] != "módulo":
            return False
        alvo = ".".join([str(entrada[1]), *partes[1:-1]])
        if alvo not in self._ctx.mapa.modulos:
            return False
        self.resolvidas.add(_canonico(self._ctx.mapa, alvo, partes[-1]))
        return True

    def visit_ImportFrom(self, no: ast.ImportFrom) -> None:
        # `from x.y import f` É alcance: o nome fica ligado no módulo que
        # importa, e um reexportador é justamente um módulo que só faz isso.
        if self._ctx is not None:
            base = _base_do_import(self._ctx.mapa, self._ctx.modulo, no)
            if base in self._ctx.mapa.modulos:
                for apelido in no.names:
                    if apelido.name == "*":
                        continue
                    if f"{base}.{apelido.name}" in self._ctx.mapa.modulos:
                        continue
                    self.resolvidas.add(
                        _canonico(self._ctx.mapa, base, apelido.name)
                    )
        self.generic_visit(no)

    def visit_alias(self, no: ast.alias) -> None:
        self.nomes.add(no.name.rsplit(".", 1)[-1])
        if no.asname:
            self.nomes.add(no.asname)

    def visit_Expr(self, no: ast.Expr) -> None:
        # Literal de texto solto como comando = documentação em prosa.
        if isinstance(no.value, ast.Constant) and isinstance(no.value.value, str):
            return
        self.generic_visit(no)

    def visit_Constant(self, no: ast.Constant) -> None:
        if isinstance(no.value, str) and id(no) not in self._docstrings:
            self.nomes.add(no.value.strip())
            self.planas.add(no.value.strip())


def _refs(no: ast.AST) -> set[str]:
    visitante = _Referencias()
    visitante.visit(no)
    return visitante.nomes


def _entregue_a_framework(no: ast.AST) -> bool:
    """O símbolo é decorado por algo que passa a ser o chamador dele?"""
    for decorador in getattr(no, "decorator_list", []):
        alvo = decorador.func if isinstance(decorador, ast.Call) else decorador
        nome = (
            alvo.attr
            if isinstance(alvo, ast.Attribute)
            else alvo.id
            if isinstance(alvo, ast.Name)
            else ""
        )
        if nome in _DECORADORES_DE_FRAMEWORK:
            return True
    return False


def _candidatas(mapa: _Mapa, alvo: Path) -> list[tuple[Promessa, str, int]]:
    """As promessas públicas da árvore, com o módulo e a posição de cada uma."""
    saida: list[tuple[Promessa, str, int]] = []
    for modulo, arvore in mapa.arvores.items():
        relativo = mapa.modulos[modulo].relative_to(alvo).as_posix()
        for indice, no in enumerate(arvore.body):
            if not isinstance(
                no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            if no.name.startswith("_") or _entregue_a_framework(no):
                continue
            saida.append(
                (
                    Promessa(
                        chave=f"{relativo}::{no.name}",
                        nome=no.name,
                        arquivo=relativo,
                        linha=no.lineno,
                        tipo="class" if isinstance(no, ast.ClassDef) else "def",
                    ),
                    modulo,
                    indice,
                )
            )
    return saida


def _fontes_externas(raiz_do_projeto: Path) -> list[tuple[str, ast.Module]]:
    """O Python que roda de FORA do pacote: os heredocs dos dois roteiros."""
    saida: list[tuple[str, ast.Module]] = []
    for roteiro in _ROTEIROS_DE_PRODUCAO:
        caminho = raiz_do_projeto / roteiro
        if not caminho.is_file():
            continue
        for indice, trecho in enumerate(trechos_python_embutidos(caminho)):
            try:
                saida.append((f"{roteiro}#heredoc{indice}", ast.parse(trecho)))
            except SyntaxError:  # pragma: no cover — heredoc quebrado é do roteiro
                continue
    return saida


def modulos_alcancados(raiz: Path | None = None) -> set[str]:
    """Os módulos que o produto de fato roda, a partir de ``_PONTOS_DE_ENTRADA``.

    Exposta porque é a metade da régua que mais engana quando quebra: se o
    fecho encolher, o portão passa a acusar quem está certo, e sem poder olhar
    o fecho ninguém descobre por quê.
    """
    alvo = _SRC if raiz is None else raiz
    mapa = _mapear(alvo)
    raiz_do_projeto = _RAIZ if raiz is None else raiz.parents[1]
    raizes: set[str] = set()
    for entrada in _PONTOS_DE_ENTRADA:
        caminho = alvo / entrada
        if caminho.is_file():
            raizes |= _com_ancestrais(mapa, _nome_de_modulo(alvo, caminho))
    for _rotulo, arvore in _fontes_externas(raiz_do_projeto):
        raizes |= _raizes_de_uma_fonte_externa(mapa, arvore)
    return _fecho_de_import(mapa, raizes)


def promessas_sem_caminho(raiz: Path | None = None) -> dict[str, Promessa]:
    """Funções e classes públicas de módulo que nada em produção alcança.

    A régua, desde 22/08/2026: um símbolo está alcançado quando algum nó de
    topo de um módulo ALCANÇADO (ver ``modulos_alcancados``) o CITA com o
    nome resolvido ao módulo que o define — menos o próprio símbolo, para que
    recursão e auto-citação não satisfaçam o portão sozinhas. O que não dá para
    resolver sem inferir tipo (literal de texto e atributo de objeto) conta
    plano, e só a partir de módulo alcançado.

    ``raiz`` existe para o portão poder ser apontado para uma CÓPIA de si mesmo
    (ver ``TestOPortaoMorde``) — mutilar ou aumentar ``src/`` na árvore viva
    contamina a medição de quem estiver trabalhando ao lado
    (``ARVORE-CONGELADA-01``).
    """
    alvo = _SRC if raiz is None else raiz
    mapa = _mapear(alvo)
    raiz_do_projeto = _RAIZ if raiz is None else raiz.parents[1]
    externas = _fontes_externas(raiz_do_projeto)

    raizes: set[str] = set()
    for entrada in _PONTOS_DE_ENTRADA:
        caminho = alvo / entrada
        if caminho.is_file():
            raizes |= _com_ancestrais(mapa, _nome_de_modulo(alvo, caminho))
    for _rotulo, arvore in externas:
        raizes |= _raizes_de_uma_fonte_externa(mapa, arvore)
    alcancados = _fecho_de_import(mapa, raizes)

    refs_por_no: list[tuple[str, int, set[tuple[str, str]]]] = []
    planas: set[str] = set()
    for modulo in alcancados:
        arvore = mapa.arvores[modulo]
        contexto = _Contexto(
            mapa, modulo, _tabela_de_nomes(mapa, modulo, arvore), mapa.define[modulo]
        )
        for indice, no in enumerate(arvore.body):
            visitante = _Referencias(contexto)
            visitante.visit(no)
            refs_por_no.append((modulo, indice, visitante.resolvidas))
            planas |= visitante.planas
    for rotulo, arvore in externas:
        contexto = _Contexto(
            mapa, rotulo, _tabela_de_nomes(mapa, rotulo, arvore, externo=True),
            frozenset(),
        )
        visitante = _Referencias(contexto)
        visitante.visit(arvore)
        refs_por_no.append((rotulo, -1, visitante.resolvidas))
        planas |= visitante.planas

    orfas: dict[str, Promessa] = {}
    for promessa, modulo, indice in _candidatas(mapa, alvo):
        se_alcanca = (modulo, promessa.nome)
        if any(
            se_alcanca in refs
            for onde, posicao, refs in refs_por_no
            if not (onde == modulo and posicao == indice)
        ):
            continue
        if promessa.nome in planas:
            continue
        orfas[promessa.chave] = promessa
    return orfas


def _regua_plana(raiz: Path) -> set[str]:
    """A régua de ATÉ 21/08/2026, viva só para as mordidas mostrarem a troca.

    Ela pergunta "existe algum chamador deste NOME em qualquer lugar da
    árvore?" — sem alcance e sem módulo. Duas mordidas a chamam para provar,
    no mesmo caso, que o defeito que a nova pega era APROVADO por ela: a
    corrente fechada em si mesma e a colisão de nome entre módulos. Sem esta
    função as duas mordidas ficariam afirmando a troca sem medi-la.
    """
    refs_por_no: list[tuple[Path, int, set[str]]] = []
    candidatas: list[tuple[str, Path, int]] = []
    for caminho in _modulos(raiz):
        arvore = _arvore(caminho)
        for indice, no in enumerate(arvore.body):
            refs_por_no.append((caminho, indice, _refs(no)))
            if not isinstance(
                no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            if no.name.startswith("_") or _entregue_a_framework(no):
                continue
            relativo = caminho.relative_to(raiz).as_posix()
            candidatas.append((f"{relativo}::{no.name}", caminho, indice))
    orfas: set[str] = set()
    for chave, caminho, indice in candidatas:
        nome = chave.split("::", 1)[1]
        if not any(
            nome in refs
            for arquivo, posicao, refs in refs_por_no
            if not (arquivo == caminho and posicao == indice)
        ):
            orfas.add(chave)
    return orfas


# --- P3a: a varredura dos interruptores ------------------------------------

_ENV = re.compile(r"""["'](HEFESTO_[A-Z0-9_]+)["']""")

#: Como se ESCREVE uma variável de ambiente, por família de arquivo. Um portão
#: que só procurasse o NOME acharia comentário: medido em 12/08/2026, das seis
#: envs que um grep ingênuo dava por ligadas, quatro eram comentário, linha de
#: changelog ou LEITURA feita por outro programa.
_ESCRITA_DE_AMBIENTE = (
    # shell: `NAME=…`, `export NAME=…`, `env NAME=…`
    r"(?:^|[;&|(]|\bexport\s+|\benv\s+)\s*{nome}=",
    # unidade systemd / .desktop: `Environment=NAME=…`
    r"^\s*Environment=\"?{nome}=",
    # python: `os.environ["NAME"] = …`, `.setdefault("NAME"`, `putenv("NAME"`
    r"""\[\s*["']{nome}["']\s*\]\s*=[^=]""",
    r"""(?:setdefault|putenv)\(\s*["']{nome}["']""",
)


def _sem_comentario(texto: str) -> str:
    """Descarta linhas de comentário — shell, INI e Python usam todos ``#``."""
    return "\n".join(
        linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")
    )


def interruptores_lidos_em_src(raiz: Path | None = None) -> dict[str, str]:
    """``env -> 'arquivo:linha'`` de toda ``HEFESTO_*`` que ``src/`` lê."""
    alvo = _SRC if raiz is None else raiz
    achados: dict[str, str] = {}
    for caminho in _modulos(alvo):
        texto = caminho.read_text(encoding="utf-8")
        for correspondencia in _ENV.finditer(_sem_comentario(texto)):
            achados.setdefault(
                correspondencia.group(1),
                f"{caminho.relative_to(alvo).as_posix()}",
            )
    return achados


@functools.cache
def _texto_sem_comentario(arquivo: Path) -> str | None:
    """O arquivo sem comentários, lido UMA vez por caminho.

    CUSTO MEDIDO em 12/08/2026: sem este cache, `portas_que_ligam` relia todos
    os arquivos de todas as portas para CADA interruptor — I/O quadrático, e a
    suíte inteira passava de 4m30 para mais de 5 min só neste arquivo, a ponto
    de parecer travada. O conjunto de arquivos não muda durante a sessão (a
    guarda ARVORE-CONGELADA-01 existe justamente para garantir isso), então
    cachear por caminho é seguro e é o que torna este portão pagável.
    """
    try:
        return _sem_comentario(arquivo.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return None


#: Pastas de ARTEFATO DE BUILD — o que o compilador deixou, nunca o que alguém
#: escreveu. Elas não são porta, e lê-las custa caro nas duas pontas:
#:
#: - TEMPO, e este é o custo que JÁ se paga: MEDIDO em 13/08/2026 na árvore
#:   dela, `packaging/cosmic-applet/target` tem **18G em 42.738 arquivos**. O
#:   laço abaixo abria e lia cada um deles inteiro, como texto;
#: - VERDADE, e este é o custo que AINDA NÃO se paga — é o que torna a exclusão
#:   preventiva e não cosmética. O binário que o `cargo` produz CONTÉM as
#:   strings do fonte, inclusive os nomes de env que o applet apenas LÊ. Um
#:   `HEFESTO_…=` caindo no começo de uma linha dentro de um `.rlib`
#:   transformaria lacuna real em "tem porta", e a dívida sumiria sozinha do
#:   relatório — o pior desfecho possível para um portão, e o mesmo engano que
#:   `test_o_detector_de_ambiente_nao_confunde_citacao_com_escrita` já impede do
#:   lado do texto. MEDIDO em 13/08/2026: hoje nenhum arquivo sob `target/`
#:   dispara (`grep -rlE '^HEFESTO_[A-Z0-9_]+=' …` não devolve nada). O
#:   mecanismo é real e está provado em
#:   `test_o_que_o_build_deixou_nao_e_porta`; o disparo é questão de qual
#:   binário o próximo `cargo build` deixa lá.
#:
#: É poda por NOME de pasta, e não `git ls-files`: um portão da suíte tem de
#: valer também num sdist desempacotado, onde não há repositório nem `git` — e
#: chamar subprocesso para responder "isto é fonte?" paga um preço que a poda
#: já paga de graça.
_PASTAS_DE_ARTEFATO = frozenset(
    {"target", "build", "dist", "node_modules", ".git", "__pycache__", ".venv"}
)


def _arquivos_de_porta(caminho: Path) -> list[Path]:
    """Os arquivos de FONTE de uma porta — sem o que o build deixou para trás."""
    if caminho.is_file():
        return [caminho]
    if not caminho.is_dir():
        return []
    return [
        p
        for p in caminho.rglob("*")
        if p.is_file() and not (_PASTAS_DE_ARTEFATO & set(p.relative_to(caminho).parts))
    ]


def portas_que_ligam(env: str, raiz: Path | None = None) -> list[str]:
    """Quais portas ESCREVEM este interruptor. Basta uma para a promessa valer.

    ``raiz`` existe pela mesma razão que em ``promessas_sem_caminho``: para a
    mordida poder plantar um artefato de build numa árvore FABRICADA em vez de
    sujar a que está sendo medida ao lado (``ARVORE-CONGELADA-01``).
    """
    base_do_projeto = _RAIZ if raiz is None else raiz
    encontradas: list[str] = []
    for porta, lugares in _PORTAS_DE_AMBIENTE.items():
        for lugar in lugares:
            caminho = base_do_projeto / lugar
            arquivos = _arquivos_de_porta(caminho)
            for arquivo in arquivos:
                texto = _texto_sem_comentario(arquivo)
                if texto is None:  # pragma: no cover — binário ilegível
                    continue
                if env not in texto:
                    continue
                if any(
                    re.search(molde.format(nome=re.escape(env)), texto, re.MULTILINE)
                    for molde in _ESCRITA_DE_AMBIENTE
                ):
                    encontradas.append(porta)
                    break
            if porta in encontradas:
                break
    return encontradas


def _promessas_publicas_por_chave(raiz: Path | None = None) -> set[str]:
    """Todas as chaves de promessa pública — o denominador da varredura."""
    alvo = _SRC if raiz is None else raiz
    chaves: set[str] = set()
    for caminho in _modulos(alvo):
        for no in _arvore(caminho).body:
            if not isinstance(
                no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            if no.name.startswith("_") or _entregue_a_framework(no):
                continue
            chaves.add(f"{caminho.relative_to(alvo).as_posix()}::{no.name}")
    return chaves


# ===========================================================================
# Utilidades das razões — data e tamanho
# ===========================================================================

#: Toda razão declarada carrega data. Sem data ninguém sabe se ela envelheceu,
#: e lacuna sem idade vira paisagem.
_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")

#: O mesmo piso do molde (``_SEM_ESCRITOR_HOJE``): abaixo disto a razão não
#: cabe o endereço de onde o caminho se perde, e vira "porque sim" com mais
#: letras.
_RAZAO_MINIMA = 120


# ---------------------------------------------------------------------------
# A REGRA DE VARREDURA DESTE ARQUIVO — 25/08/2026 (AUDITORIA-DE-PERDA-01/C2)
#
# Toda régua que varre MAIS DE UM registro acumula e falha UMA VEZ, nomeando
# tudo. `assert` dentro do laço é proibido aqui, e a cicatriz é medida:
# `test_nenhuma_lapide_sobreviveu_a_propria_cura` varria os dois registros com
# o `assert` DENTRO do laço, e a primeira falha cortava o laço — o segundo
# registro nunca era lido. Foi assim que DUAS lápides caducas
# (`utils/maquina.py::gravar_maquina` e `app/ipc_bridge.py::destinos_da_aplicacao`)
# conviveram sem que ninguém soubesse que eram duas: quem via o vermelho
# consertava a primeira, rodava de novo, e só então descobria a segunda — se
# rodasse de novo.
#
# CORREÇÃO DE FATO (25/08/2026, medida por `git log`): a primeira versão desta
# nota dizia que as duas "conviveram MESES". Não conviveram, e a diferença
# importa porque muda o diagnóstico. As datas:
#   - `app/ipc_bridge.py::destinos_da_aplicacao` — lápide escrita em `c4b80da`
#     (23/08 21:50), VERDADEIRA na hora; o chamador de
#     `app/textos_de_aplicacao.py` nasceu em `12af679` (24/08 09:45). Caduca
#     por ~17h44.
#   - `utils/maquina.py::gravar_maquina` — o chamador `gravar_rascunho_da_mesa`
#     nasceu em `565a70d` (24/08 03:27) e a lápide foi escrita em `300656c`
#     (24/08 04:11), QUARENTA E QUATRO MINUTOS DEPOIS. Ela nunca descreveu uma
#     árvore anterior: nasceu contra um chamador que já estava no disco.
#   - as duas saíram em `ca481af` (25/08 03:29).
# O que isto muda: o buraco não é uma lápide que envelheceu no escuro por
# meses — é uma lápide escrita sobre uma árvore que mudou NA MESMA MADRUGADA,
# por outra frente. Numa leva com nove árvores em voo, "medi e classifiquei"
# vale por horas, não por semanas.
#
# O custo do defeito não é o laço: é que um portão que mostra metade do que vê
# ENSINA a subestimar a dívida. Quem lê "1 símbolo acusado" fecha a tarefa; a
# fila real tinha dois.
#
# `TestOPortaoNaoEscondeMetadeDoQueVe` é a régua desta regra, e ela morde: com
# o `assert` de volta dentro do laço, ela reprova nomeando qual registro ficou
# escondido.
# ---------------------------------------------------------------------------


def _razoes_mal_escritas(registro: dict[str, str], rotulo: str) -> list[str]:
    """TODA razão de um registro que não diz onde o caminho se perde.

    Devolve a lista inteira e não levanta: quem levanta é quem chama, uma vez
    só, depois de somar todos os registros.
    """
    queixas: list[str] = []
    for chave, razao in registro.items():
        if len(razao) <= _RAZAO_MINIMA:
            queixas.append(
                f"a razão de {chave!r} em {rotulo} tem {len(razao)} caracteres "
                f"e não diz onde o caminho se perde: {razao!r}"
            )
        if not _DATA.search(razao):
            queixas.append(f"a razão de {chave!r} em {rotulo} não tem data.")
    return queixas


def _confere_razoes(*registros: tuple[str, dict[str, str]]) -> None:
    """As razões de TODOS os registros passados, numa acusação só."""
    queixas = [
        queixa
        for rotulo, registro in registros
        for queixa in _razoes_mal_escritas(registro, rotulo)
    ]
    assert not queixas, (
        "há razões que não sustentam a isenção que carregam "
        f"({len(queixas)} em {len(registros)} registro(s)):\n"
        + "\n".join(f"  - {q}" for q in queixas)
        + "\nESCREVA o endereço (arquivo:linha), o que fecharia a lacuna, e a "
        "data da medição (DD/MM/AAAA). Razão curta é uma isenção fingindo ser "
        "decisão; lacuna sem idade vira paisagem."
    )


def _registros_de_promessa() -> tuple[tuple[str, dict[str, str]], ...]:
    """Os dois registros de classificação de promessa pública.

    Função, e não constante, de propósito: ela relê os globais a cada chamada,
    e é isso que deixa `TestOPortaoNaoEscondeMetadeDoQueVe` trocá-los por
    registros fabricados sem tocar na árvore de verdade.
    """
    return (
        ("_NAO_E_PROMESSA", _NAO_E_PROMESSA),
        ("_SEM_CAMINHO_HOJE", _SEM_CAMINHO_HOJE),
    )


# ===========================================================================
# P3a — o interruptor sem mão
# ===========================================================================


class TestTodoInterruptorTemMao:
    """Uma env que o produto lê promete que algo pode ser ligado."""

    def test_todo_interruptor_lido_esta_classificado(self) -> None:
        """Chave nova sem classificação reprova por ESTAR SEM CLASSIFICAÇÃO.

        É esta inversão que dispensa a denylist por prefixo (``…_FAKE``,
        ``…_LEDS_ROOT``, ``…_PROC_MARKERS``) que a passada anterior propôs e
        declarou não ter validado. Prefixo é denylist, e denylist fura calada:
        uma chave de feature que por acaso terminasse em ``_FAKE`` sairia
        isenta em silêncio. Aqui o total é DERIVADO e a classificação é
        exaustiva por construção.
        """
        lidas = set(interruptores_lidos_em_src())
        classificadas = set(_INSTRUMENTO_DE_AMBIENTE) | set(_PROMESSA_DE_AMBIENTE)
        novas = sorted(lidas - classificadas)
        assert not novas, (
            f"interruptor de ambiente sem classificação: {novas}\n"
            "DECIDA o que ele é e escreva no conjunto certo deste arquivo, "
            "COM a razão e a data:\n"
            "  _INSTRUMENTO_DE_AMBIENTE — chave de teste, diagnóstico ou "
            "calibração, que ninguém liga em produção;\n"
            "  _PROMESSA_DE_AMBIENTE    — chave que abre uma feature dela, e "
            "então precisa de quem a vire."
        )

    def test_nenhuma_classificacao_cita_chave_que_sumiu(self) -> None:
        """Chave apagada de ``src/`` não pode deixar classificação órfã.

        Sem isto os dois registros virariam cemitério, e a pergunta de cima
        passaria a ser respondida por entradas mortas.
        """
        lidas = set(interruptores_lidos_em_src())
        fantasmas = sorted(
            (set(_INSTRUMENTO_DE_AMBIENTE) | set(_PROMESSA_DE_AMBIENTE)) - lidas
        )
        assert not fantasmas, (
            f"estas chaves estão classificadas e `src/` não as lê mais: "
            f"{fantasmas}\nAPAGUE a entrada — a classificação é do que existe."
        )

    def test_nenhuma_chave_esta_nos_dois_conjuntos(self) -> None:
        """Instrumento e promessa são exclusivos; estar nos dois é não decidir."""
        ambos = sorted(set(_INSTRUMENTO_DE_AMBIENTE) & set(_PROMESSA_DE_AMBIENTE))
        assert not ambos, (
            f"estas chaves estão classificadas como instrumento E como "
            f"promessa: {ambos}\nESCOLHA uma. Uma chave que é as duas coisas é "
            "uma chave cujo dono ninguém decidiu."
        )

    def test_toda_promessa_de_ambiente_tem_quem_a_ligue(self) -> None:
        """Uma feature que ela pode querer, e alguma porta que a vire.

        MORDIDA: a régua está conferida contra contagem independente em
        ``test_a_varredura_enxerga_a_unica_env_escrita_de_verdade`` e em
        ``test_o_detector_de_ambiente_nao_confunde_citacao_com_escrita``. Sem
        essas duas provas, um detector quebrado devolveria "sem mão" para as 29
        chaves e a lista de lacunas viraria a lista de envs.
        """
        sem_mao = sorted(
            env
            for env in _PROMESSA_DE_AMBIENTE
            if env not in _SEM_MAO_HOJE
            and env not in _MAO_FORA_DO_AMBIENTE
            and not portas_que_ligam(env)
        )
        assert not sem_mao, (
            f"estas chaves abrem uma feature dela e NADA no produto as liga: "
            f"{sem_mao}\n"
            "LIGUE por UMA porta, a que fizer sentido para esta feature:\n"
            "  - `Environment=` na unit de `assets/`, se é para valer sempre;\n"
            "  - `install.sh` ou o empacotamento, se é escolha da instalação;\n"
            "  - um interruptor na janela, se é escolha DELA.\n"
            "UMA basta. Este portão nunca exige as duas — a conjunção "
            "'install E GUI' é falsa para quase toda a dívida desta casa.\n"
            "Se a mão existe mas não é a env (um flag de disco, um campo de "
            "config), declare o companheiro em `_MAO_FORA_DO_AMBIENTE`.\n"
            "Se ainda não é hora, declare a lacuna em `_SEM_MAO_HOJE`, com a "
            "razão, a data e o endereço de onde o caminho se perde."
        )

    def test_o_companheiro_declarado_existe_e_nao_e_ele_proprio_uma_lacuna(
        self,
    ) -> None:
        """Companheiro é escape, e todo escape precisa de guarda.

        Sem este caso, ``_MAO_FORA_DO_AMBIENTE`` seria o lugar onde se escreve
        "tem mão em outro lugar" sem que ninguém confira o outro lugar — e o
        portão passaria a aceitar a própria palavra como prova.
        """
        publicas = _promessas_publicas_por_chave()
        soltas = promessas_sem_caminho()
        for env, (companheiro, _razao) in _MAO_FORA_DO_AMBIENTE.items():
            assert companheiro in publicas, (
                f"{env} declara ser ligada por {companheiro!r}, que não existe "
                "mais como símbolo público em `src/`.\n"
                "ATUALIZE o endereço do companheiro, ou mova a chave para "
                "`_SEM_MAO_HOJE` — a feature ficou sem mão de novo."
            )
            assert companheiro not in soltas, (
                f"{env} declara ser ligada por {companheiro!r}, e "
                f"{companheiro!r} é ele mesmo uma promessa sem caminho: nada em "
                "produção o chama.\nA mão declarada não segura nada. Ou fie o "
                "companheiro, ou mova a chave para `_SEM_MAO_HOJE`."
            )

    def test_as_lacunas_de_ambiente_ainda_sao_lacunas(self) -> None:
        """Chave declarada sem mão que GANHOU mão tem de perder a lápide."""
        curadas = sorted(env for env in _SEM_MAO_HOJE if portas_que_ligam(env))
        assert not curadas, (
            f"estas chaves estão declaradas como lacuna e JÁ TÊM quem as "
            f"ligue: {curadas}\nAPAGUE a entrada de `_SEM_MAO_HOJE`. A cura "
            "chegou e a lápide ficou — é assim que um registro honesto vira "
            "mentira."
        )

    def test_toda_lacuna_de_ambiente_e_promessa_declarada(self) -> None:
        """Não se declara lacuna de uma chave que ninguém chamou de promessa."""
        estranhas = sorted(set(_SEM_MAO_HOJE) - set(_PROMESSA_DE_AMBIENTE))
        assert not estranhas, (
            f"estas chaves têm lacuna declarada e não estão em "
            f"`_PROMESSA_DE_AMBIENTE`: {estranhas}"
        )

    def test_as_razoes_de_ambiente_nao_envelhecem_caladas(self) -> None:
        """Toda razão de ambiente é longa e datada — as quatro famílias."""
        _confere_razoes(
            ("_INSTRUMENTO_DE_AMBIENTE", _INSTRUMENTO_DE_AMBIENTE),
            ("_PROMESSA_DE_AMBIENTE", _PROMESSA_DE_AMBIENTE),
            ("_SEM_MAO_HOJE", _SEM_MAO_HOJE),
            (
                "_MAO_FORA_DO_AMBIENTE",
                {
                    env: razao
                    for env, (_alvo, razao) in _MAO_FORA_DO_AMBIENTE.items()
                },
            ),
        )


# ===========================================================================
# P3b — a promessa pública sem caminho
# ===========================================================================


class TestTodaPromessaPublicaTemCaminho:
    """O produto promete que isto faz algo — e existe por onde chegar nisto?"""

    def test_toda_promessa_solta_esta_classificada(self) -> None:
        """O caso que importa: o portão existe para pegar a PRÓXIMA.

        Não para catalogar as sessenta de hoje — essas já estão escritas
        acima, com endereço e com o que as fecharia. O valor deste arquivo é
        que a sexagésima primeira não consegue nascer calada.

        MORDIDA: provada em ``TestOPortaoMorde``, que fabrica um símbolo
        público novo numa cópia de ``src/`` e cobra que ele apareça acusado E
        fora dos dois registros.
        """
        soltas = set(promessas_sem_caminho())
        declaradas = set(_NAO_E_PROMESSA) | set(_SEM_CAMINHO_HOJE)
        novas = sorted(soltas - declaradas)
        assert not novas, (
            "estas promessas públicas não têm chamador em produção e ninguém "
            "disse o que elas são:\n  "
            + "\n  ".join(novas)
            + "\n"
            "Nenhum módulo ALCANÇADO a partir de `_PONTOS_DE_ENTRADA` a "
            "cita, nem o Python embutido nos heredocs de "
            "`install.sh`/`uninstall.sh`. `tests/` e `scripts/` NÃO contam — "
            "foi assim que 52 das 60 curas desta lista ficaram parecendo "
            "entregues.\n"
            "FAÇA UMA das quatro:\n"
            "  1. FIE — chame de onde o produto passa, e o defeito acaba;\n"
            "  2. APAGUE — se outro caminho já a substituiu, ela é resto;\n"
            "  3. DECLARE em `_NAO_E_PROMESSA` — se não é promessa ao produto "
            "(instrumento de teste, ferramenta de diagnóstico, lápide com nota "
            "datada). A razão tem de CITAR a evidência: o docstring que diz "
            "isso, a nota datada, o script irmão;\n"
            "  4. DECLARE em `_SEM_CAMINHO_HOJE` — se é promessa e o caminho "
            "ainda não existe. A razão tem de dizer onde o caminho se perde e "
            "o que o fecharia.\n"
            "Declarar é honesto e este portão não castiga honestidade. Ele só "
            "não deixa a lápide envelhecer calada."
        )

    def test_nenhuma_declaracao_cita_simbolo_que_nao_existe(self) -> None:
        """Registro que cita símbolo apagado é cemitério, não registro.

        Acumula os DOIS registros e acusa uma vez só — ver a regra de varredura
        de 25/08/2026 no topo de `_razoes_mal_escritas`.
        """
        publicas = _promessas_publicas_por_chave()
        fantasmas = [
            f"{rotulo}: {chave}"
            for rotulo, registro in _registros_de_promessa()
            for chave in sorted(set(registro) - publicas)
        ]
        assert not fantasmas, (
            f"há {len(fantasmas)} declaração(ões) citando símbolo que não "
            "existe mais como promessa pública de módulo:\n"
            + "\n".join(f"  - {f}" for f in fantasmas)
            + "\nAPAGUE a entrada (o símbolo saiu da árvore), ou corrija o "
            "endereço se ele só mudou de arquivo."
        )

    def test_nenhuma_lapide_sobreviveu_a_propria_cura(self) -> None:
        """O dia em que o caminho nasce é o dia de apagar a entrada.

        É o equivalente do ``xfail(strict=True)`` do molde: a lacuna que passou
        a ser alcançada REPROVA, para que ninguém herde um registro que
        descreve uma árvore que não existe mais.

        MEDIDO em 25/08/2026 (AUDITORIA-DE-PERDA-01/C2): esta régua varria os
        dois registros com o ``assert`` DENTRO do laço, e a primeira falha
        cortava o laço — o segundo registro nunca era lido. Duas lápides
        caducas (``utils/maquina.py::gravar_maquina`` e
        ``app/ipc_bridge.py::destinos_da_aplicacao``) conviveram sem que
        ninguém soubesse que eram DUAS. Agora acumula e acusa uma vez só.
        As datas medidas das duas estão no topo deste arquivo, na regra de
        varredura.
        """
        soltas = set(promessas_sem_caminho())
        curadas = [
            f"{rotulo}: {chave}"
            for rotulo, registro in _registros_de_promessa()
            for chave in sorted(set(registro) - soltas)
        ]
        assert not curadas, (
            f"há {len(curadas)} lápide(s) declarando símbolo como sem caminho "
            "enquanto ALGO em produção já o alcança:\n"
            + "\n".join(f"  - {c}" for c in curadas)
            + "\nAPAGUE a entrada. A cura chegou e a lápide ficou — é assim "
            "que um registro honesto vira mentira, e a próxima pessoa perde "
            "uma tarde descobrindo que o texto está velho."
        )

    def test_nenhum_simbolo_esta_nos_dois_registros(self) -> None:
        """Ou não é promessa, ou é dívida. Estar nos dois é não ter decidido."""
        ambos = sorted(set(_NAO_E_PROMESSA) & set(_SEM_CAMINHO_HOJE))
        assert not ambos, (
            f"estes símbolos estão declarados como 'não é promessa' E como "
            f"dívida: {ambos}\nESCOLHA um."
        )

    def test_as_razoes_dos_simbolos_nao_envelhecem_caladas(self) -> None:
        """Sem isto, os registros viram o lugar onde se esconde o que incomoda."""
        _confere_razoes(*_registros_de_promessa())

    def test_todo_ponto_de_entrada_tem_fonte_viva(self) -> None:
        """A lista de entradas é o chão da régua — e chão apodrece calado.

        Cada entrada declara a FONTE que a torna entrada: o `[project.scripts]`,
        o `ExecStart`, a linha do instalador. Se a fonte deixar de dizer o que
        esta tabela afirma, o módulo continuaria alcançado por uma boca que não
        existe mais — e o portão calaria sobre um módulo inteiro sem que nada o
        denunciasse. É o mesmo defeito da lápide que sobrevive à cura, do outro
        lado da régua.
        """
        for entrada, (fonte, agulha, razao) in _PONTOS_DE_ENTRADA.items():
            alvo = _SRC / entrada
            assert alvo.is_file(), (
                f"o ponto de entrada {entrada!r} não existe mais em `src/`.\n"
                f"Declarado por: {razao}\n"
                "APAGUE a entrada se a boca morreu, ou corrija o caminho."
            )
            arquivo = _RAIZ / fonte
            assert arquivo.is_file(), (
                f"a FONTE de {entrada!r} sumiu: {fonte}\nDeclarado por: {razao}"
            )
            assert agulha in arquivo.read_text(encoding="utf-8", errors="ignore"), (
                f"a fonte {fonte} não diz mais o que declara {entrada!r} como "
                f"ponto de entrada — a agulha {agulha!r} não está lá.\n"
                f"Declarado por: {razao}\n"
                "CONFIRA se a boca mudou de forma (e corrija a agulha) ou se "
                "ela morreu (e então o módulo virou dívida, não entrada)."
            )


# ===========================================================================
# O portão apontado para si mesmo
# ===========================================================================


def _copia_de_src(destino: Path) -> Path:
    """Uma cópia de ``src/`` onde se pode fabricar defeito sem sujar a árvore.

    Mutilar (ou aumentar) ``src/`` na árvore viva contamina a medição de quem
    estiver trabalhando ao lado — é a ``ARVORE-CONGELADA-01``, e é a mesma
    razão pela qual o molde copia ``app/`` para um tmp antes de arrancar um
    escritor.
    """
    copia = destino / "src" / "hefesto_dualsense4unix"
    copia.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        _SRC, copia, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    # Os roteiros de shell vão junto desde 13/08/2026: o Python embutido neles é
    # caminho de produção (ver `_ROTEIROS_DE_PRODUCAO`), e uma cópia sem eles
    # mediria uma árvore onde o `uninstall.sh` não existe. A mordida do heredoc
    # passaria por AUSÊNCIA em vez de por medição — o modo mais silencioso de um
    # teste deixar de morder.
    for roteiro in _ROTEIROS_DE_PRODUCAO:
        origem = _RAIZ / roteiro
        if origem.is_file():
            shutil.copy2(origem, destino / roteiro)
    # `scripts/` ia junto entre 15/08 e 22/08/2026, quando ele era
    # `_TERRITORIOS_DE_PRODUCAO`. Parou de ir porque parou de ser porta: a
    # medição está na nota de `_PONTOS_DE_ENTRADA`. A cópia é mais barata por
    # isso — 1,7 MB em 81 arquivos a menos.
    return copia


class TestOPortaoMorde:
    """Um portão que nunca reprovou é uma decoração com nome de portão.

    Estes casos exercitam o INSTRUMENTO, não o produto. Se a varredura parasse
    de enxergar chamadores, TODOS os casos acima ficariam verdes sem medir nada
    — e é exatamente essa falha que esta classe pega.
    """

    def test_a_varredura_enxerga_os_chamadores_que_existem(self) -> None:
        """A régua conferida contra contagem independente.

        Se a varredura estivesse quebrada, devolveria "sem caminho" para tudo e
        a lista de lacunas viraria a lista de símbolos. Os quatro sinais abaixo
        estão fiados em produção hoje, cada um por um IDIOMA diferente de
        chamada; se algum aparecer acusado, é a régua que quebrou, não o
        produto.
        """
        soltas = promessas_sem_caminho()
        assert len(soltas) < 135, (
            f"a varredura acusou {len(soltas)} promessas soltas — a régua "
            "quebrou. MEDIDO em 22/08/2026: 60 com a régua de alcance (eram 33 "
            "com a régua plana), e a regra ingênua ('chamador fora do próprio "
            "arquivo') dava 846. REMEDIDO em 24/08/2026 (ONDA0-Z7): 72 na "
            "árvore de então (já perto do teto antigo de 75, sem ninguém "
            "notar — nota para quem coordena) e 76 depois das cinco primitivas "
            "desta sprint, todas DECLARADAS em `_SEM_CAMINHO_HOJE` com o gancho "
            "de quem as liga. O teto sobe para 80: folga sobre o crescimento "
            "normal do registro, não sobre um scanner quebrado — se ele voltar "
            "a subir sem `_SEM_CAMINHO_HOJE` crescer junto, É a régua quebrando."
        )
        # O fecho de import é a metade que mais engana quando quebra: se ele
        # encolher, o portão passa a acusar quem está certo, e a acusação sobe
        # em bloco. MEDIDO em 22/08/2026: 196 dos 201 módulos são alcançados;
        # os 5 de fora são as três correntes fechadas classificadas acima mais
        # `xlib_window` e `tui/screens`.
        alcancados = modulos_alcancados()
        assert len(alcancados) > 150, (
            f"o fecho de import alcançou só {len(alcancados)} módulos — algum "
            "ponto de entrada de `_PONTOS_DE_ENTRADA` deixou de existir, ou a "
            "resolução de import quebrou. Em 22/08/2026 eram 196 de 201."
        )
        assert (
            "daemon/subsystems/gamepad.py::resume_vpads_after_steam_input"
            not in soltas
        ), (
            "a varredura não vê chamada direta (gamepad.py:332) — e é ela que "
            "prova que a saída da ESCONDER-EM-VEZ-DE-SAIR-01 continua viva"
        )
        # A testemunha do despacho por STRING é escolhida por MEDIÇÃO, não por
        # plausibilidade: arrancada a leitura de literais, ESTE é o símbolo que
        # passa a ser acusado. Uma testemunha que continuasse alcançada por
        # outro caminho deixaria este caso verde para sempre sem medir nada —
        # foi o que aconteceu com o primeiro candidato (`set_coop_outputs`, que
        # é MÉTODO e por isso nunca entra na varredura).
        assert (
            "integrations/proton_pin.py::lock_proton_for_all_games" not in soltas
        ), (
            "a varredura não vê despacho por STRING — `getattr(pp, "
            '"lock_proton_for_all_games", None)` em '
            "app/actions/daemon_actions.py:1477 é o ÚNICO caminho deste "
            "símbolo. Foi assim que a passada anterior errou cinco vezes numa "
            "só medição."
        )
        assert not any(chave.startswith("cli/cmd_") for chave in soltas), (
            "algum subcomando de CLI foi acusado: a isenção por decorador "
            "(@app.command) parou de funcionar e o portão vai gritar 41 vezes"
        )
        assert not any(chave.startswith("plugin_api/") for chave in soltas), (
            "o contrato de plugin foi acusado — os hooks `on_*` são chamados "
            "por terceiros e não podem ser cobrados por chamador em `src/`"
        )

    def test_a_varredura_enxerga_a_unica_env_escrita_de_verdade(self) -> None:
        """O detector de ESCRITA de ambiente, contra contagem independente.

        Um detector que não visse escrita nenhuma devolveria "sem mão" para as
        29 chaves, e o portão estaria medindo o próprio silêncio. Hoje há
        exatamente UMA escrita real na árvore — se ela sumir daqui, é o
        detector que quebrou.
        """
        assert portas_que_ligam("HEFESTO_BROKER_ALLOWED_UID") == ["unit"], (
            "o detector não vê `Environment=HEFESTO_BROKER_ALLOWED_UID=` em "
            "assets/systemd/hefesto-hidraw-broker.service:37 — a régua de "
            "escrita de ambiente quebrou"
        )

    def test_o_detector_de_ambiente_nao_confunde_citacao_com_escrita(self) -> None:
        """Citar não é ligar, e é essa diferença que o portão inteiro mede.

        MEDIDO em 12/08/2026: das seis chaves que um `grep` ingênuo dava por
        ligadas, quatro eram comentário, linha de changelog, texto de ajuda, ou
        LEITURA feita por outro programa. Se este caso passar a falhar, o
        portão voltou a aceitar menção como prova — e a dívida some sozinha do
        relatório, que é o pior desfecho possível para um portão.
        """
        assert not portas_que_ligam(
            "HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED"
        ), "o detector aceitou o COMENTÁRIO de install.sh:227 como escrita"
        assert not portas_que_ligam("HEFESTO_DUALSENSE4UNIX_METRICS_ENABLED"), (
            "o detector aceitou a linha de CHANGELOG do .spec como escrita"
        )
        assert not portas_que_ligam("HEFESTO_DUALSENSE4UNIX_BT_MIC"), (
            "o detector aceitou o TEXTO DE AJUDA do controller_card como escrita"
        )
        assert not portas_que_ligam("HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME"), (
            "o detector aceitou a LEITURA do applet (ipc.rs:54) como escrita"
        )

    def test_uma_promessa_fabricada_e_acusada_sem_estar_na_lista(
        self, tmp_path: Path
    ) -> None:
        """A prova que vale: o portão pega a PRÓXIMA, não as já escritas.

        Fabrica-se, numa CÓPIA de ``src/``, um módulo com uma função e uma
        classe públicas que ninguém chama — exatamente a forma de uma cura
        escrita e nunca ligada. As duas TÊM de ser acusadas, e TÊM de estar
        fora dos dois registros: é isso que garante que a entrega seguinte não
        nasce calada só porque a lista de hoje já está preenchida.
        """
        copia = _copia_de_src(tmp_path)
        (copia / "daemon" / "cura_recem_nascida.py").write_text(
            '"""Uma cura escrita e nunca ligada — o defeito-mãe, fabricado."""\n'
            "\n\n"
            "def rearmar_o_gatilho_da_cor() -> bool:\n"
            '    """Faz algo importante que nada no produto pede."""\n'
            "    return True\n"
            "\n\n"
            "class RegistroDeCoresPorAparelho:\n"
            '    """Uma classe que ninguém instancia."""\n'
            "\n"
            "    def aplicar(self) -> None:\n"
            "        return None\n",
            encoding="utf-8",
        )

        soltas = set(promessas_sem_caminho(copia))
        fabricadas = {
            "daemon/cura_recem_nascida.py::rearmar_o_gatilho_da_cor",
            "daemon/cura_recem_nascida.py::RegistroDeCoresPorAparelho",
        }
        assert fabricadas <= soltas, (
            "o portão NÃO acusou a promessa fabricada — ele não pega a "
            f"próxima, só cataloga as de hoje. Acusadas: "
            f"{sorted(soltas & fabricadas)}"
        )
        declaradas = set(_NAO_E_PROMESSA) | set(_SEM_CAMINHO_HOJE)
        assert not (fabricadas & declaradas), (
            "a promessa fabricada está nos registros de classificação — a "
            "mordida está medindo a lista, não o portão"
        )
        assert not (fabricadas & set(promessas_sem_caminho())), (
            "a árvore de verdade foi contaminada pela mordida"
        )

    def test_fiar_a_promessa_fabricada_a_faz_sumir_da_acusacao(
        self, tmp_path: Path
    ) -> None:
        """A outra metade: o portão CALA quando a cura é entregue.

        Sem este caso, ``promessas_sem_caminho`` poderia estar acusando tudo o
        que é novo por construção — e um portão que grita sempre é pior que um
        que nunca grita, porque ensina a ignorá-lo.

        Desde 22/08/2026 "entregue" tem um degrau a mais, e o caso o exercita:
        não basta existir um chamador, o chamador tem de ser ALCANÇADO. Aqui a
        borda nova é fiada ao ``cli/app.py``, que é ponto de entrada declarado
        — e a cura só sai da acusação nesse instante. Um chamador que ninguém
        alcança é a corrente fechada, não a cura.
        """
        copia = _copia_de_src(tmp_path)
        (copia / "daemon" / "cura_recem_nascida.py").write_text(
            "def rearmar_o_gatilho_da_cor() -> bool:\n    return True\n",
            encoding="utf-8",
        )
        chave = "daemon/cura_recem_nascida.py::rearmar_o_gatilho_da_cor"
        assert chave in promessas_sem_caminho(copia)

        (copia / "daemon" / "chamador_da_cura.py").write_text(
            "from hefesto_dualsense4unix.daemon.cura_recem_nascida import (\n"
            "    rearmar_o_gatilho_da_cor,\n"
            ")\n"
            "\n\n"
            "def borda_do_produto() -> bool:\n"
            "    return rearmar_o_gatilho_da_cor()\n",
            encoding="utf-8",
        )
        assert chave in promessas_sem_caminho(copia), (
            "a cura sumiu da acusação com um chamador que NINGUÉM alcança — o "
            "fecho de import parou de valer e a corrente fechada em si mesma "
            "voltou a passar"
        )

        entrada = copia / "cli" / "app.py"
        entrada.write_text(
            "from hefesto_dualsense4unix.daemon.chamador_da_cura import (\n"
            "    borda_do_produto,\n"
            ")\n\n"
            + entrada.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        assert chave not in promessas_sem_caminho(copia), (
            "o portão continuou acusando uma promessa JÁ FIADA — ele grita "
            "sempre, e um portão que grita sempre é desligado na primeira "
            "semana"
        )

    def test_um_chamador_so_em_tests_nao_conta_como_caminho(
        self, tmp_path: Path
    ) -> None:
        """A linha que separa a dívida solta do resto da árvore.

        REMEDIDO em 22/08/2026: 52 dos 60 acusados têm chamador em ``tests/`` —
        pareciam entregues. Se ``tests/`` passar a contar, a acusação despenca
        para 8 e o portão para de ver justamente a forma mais comum do
        defeito.
        """
        copia = _copia_de_src(tmp_path)
        (copia / "daemon" / "cura_recem_nascida.py").write_text(
            "def rearmar_o_gatilho_da_cor() -> bool:\n    return True\n",
            encoding="utf-8",
        )
        testes = tmp_path / "tests" / "unit"
        testes.mkdir(parents=True)
        (testes / "test_cura_recem_nascida.py").write_text(
            "from hefesto_dualsense4unix.daemon.cura_recem_nascida import (\n"
            "    rearmar_o_gatilho_da_cor,\n"
            ")\n"
            "\n\n"
            "def test_a_cura_devolve_true() -> None:\n"
            "    assert rearmar_o_gatilho_da_cor() is True\n",
            encoding="utf-8",
        )
        assert (
            "daemon/cura_recem_nascida.py::rearmar_o_gatilho_da_cor"
            in promessas_sem_caminho(copia)
        ), (
            "o portão aceitou um chamador de `tests/` como caminho de produção "
            "— é exatamente esse engano que fez 52 das 60 curas desta lista "
            "parecerem entregues por meses"
        )

    def test_arrancar_o_unico_chamador_de_uma_cura_viva_a_acusa(
        self, tmp_path: Path
    ) -> None:
        """A mordida sobre o produto de verdade, e não sobre um exemplo.

        ``resume_vpads_after_steam_input`` está viva por UM chamador
        (gamepad.py:332), e essa é a saída do ciclo da
        ``ESCONDER-EM-VEZ-DE-SAIR-01`` — a que devolve o gamepad virtual a um
        daemon que subiu antes da cura. Arrancada a linha da CÓPIA, o portão
        TEM de acusar. É a prova de que ele mede a árvore, e não um arquivo
        fabricado que se comporta bem.
        """
        copia = _copia_de_src(tmp_path)
        alvo = copia / "daemon" / "subsystems" / "gamepad.py"
        texto = alvo.read_text(encoding="utf-8")
        chamada = "resume_vpads_after_steam_input(daemon)"
        assert chamada in texto, (
            "a chamada mudou de forma — esta mordida precisa de outro alvo, "
            "senão ela deixa de morder em silêncio"
        )
        alvo.write_text(texto.replace(chamada, "None"), encoding="utf-8")

        chave = "daemon/subsystems/gamepad.py::resume_vpads_after_steam_input"
        assert chave in promessas_sem_caminho(copia), (
            "arrancado o único chamador, o portão NÃO acusou — ele não morde"
        )
        assert chave not in promessas_sem_caminho(), (
            "a árvore de verdade foi contaminada pela mordida"
        )

    def test_comentar_a_chamada_do_desinstalar_devolve_a_acusacao(
        self, tmp_path: Path
    ) -> None:
        """A mordida do heredoc, sobre a árvore de verdade.

        Ela prova as DUAS metades de uma vez, e é por isso que ela vale mais que
        conferir a lista à mão: com o `uninstall.sh` inteiro, o portão CALA
        sobre `strip_quirks_token`; arrancada a chamada da CÓPIA, ele VOLTA a
        acusar. Se alguém tivesse "curado" a lacuna apagando a entrada do
        registro, a segunda metade continuaria calada — e este caso reprovaria.
        """
        copia = _copia_de_src(tmp_path)
        chave = "integrations/kernel_cmdline.py::strip_quirks_token"
        assert chave not in promessas_sem_caminho(copia), (
            "com o `uninstall.sh` inteiro o portão AINDA acusa "
            f"{chave!r} — a varredura continua cega ao Python embutido em "
            "heredoc, e a lista de dívida segue cobrando de quem está certo"
        )

        roteiro = tmp_path / "uninstall.sh"
        texto = roteiro.read_text(encoding="utf-8")
        chamada = "rest, changed = kc.strip_quirks_token(tok)"
        assert chamada in texto, (
            "a chamada mudou de forma no `uninstall.sh` — esta mordida precisa "
            "de outro alvo, senão ela deixa de morder em silêncio"
        )
        roteiro.write_text(
            texto.replace(chamada, "rest, changed = None, False"), encoding="utf-8"
        )

        assert chave in promessas_sem_caminho(copia), (
            "arrancada a chamada do heredoc, o portão NÃO voltou a acusar "
            f"{chave!r}. Ou ele está lendo o roteiro como texto solto (e o "
            "COMENTÁRIO de uninstall.sh:1202 o satisfaz), ou ele parou de "
            "olhar o roteiro da CÓPIA e está medindo a árvore viva"
        )
        assert chave not in promessas_sem_caminho(), (
            "a árvore de verdade foi contaminada pela mordida"
        )

    def test_o_ponto_de_entrada_declarado_e_o_que_abre_o_alcance(
        self, tmp_path: Path
    ) -> None:
        """A mordida de ``_PONTOS_DE_ENTRADA``, sobre a árvore de verdade.

        Ela SUBSTITUI ``test_o_chamador_em_scripts_e_caminho_de_producao``, que
        mediu a porta de ``scripts/`` enquanto ela existiu (15→22/08/2026), e
        prova a mesma coisa que aquela provava, sobre a porta que a substituiu:
        um ponto de entrada declarado é a ÚNICA coisa entre um módulo inteiro e
        a lista de dívida. Se a lista esvaziar ou apodrecer, o portão passa a
        cobrar de quem está certo — que é o defeito que ``strip_quirks_token``
        já custou uma vez.

        O alvo é ``integrations/steam_input_ponte.py``: onze símbolos públicos
        que NADA em ``src/`` importa, e que só existem porque
        ``scripts/disable_steam_input.sh``:283+298 roda o arquivo com
        ``python3 ${PONTE_PY} --ligar``. É a forma mais pura da entrada por
        roteiro, e por isso a testemunha certa.
        """
        copia = _copia_de_src(tmp_path)
        chave = "integrations/steam_input_ponte.py::garantir_ponte"
        assert chave not in promessas_sem_caminho(copia), (
            f"com a lista inteira o portão AINDA acusa {chave!r} — o ponto de "
            "entrada declarado não abre alcance nenhum, e um módulo que a unit "
            "do guarda roda a cada saída da Steam vira dívida"
        )

        # O alvo da mordida é o ARQUIVO do ponto de entrada, não uma chamada:
        # é a existência dele que faz o fecho começar ali. Apagá-lo é o
        # equivalente exato de tirá-lo de `_PONTOS_DE_ENTRADA`.
        (copia / "integrations" / "steam_input_ponte.py").unlink()

        soltas = promessas_sem_caminho(copia)
        # CANÁRIO TROCADO DUAS VEZES, e as duas trocas são o próprio portão
        # funcionando. Era `prontuario_dos_jogos.py::Prontuario`, e aquele
        # módulo GANHOU CAMINHO em 25/08. Virou
        # `app/fala_do_mapa.py::formata_pt_br`, e ele ganhou caminho em 26/08
        # (BG-03: virou o dono único da vírgula, e a lápide dele foi apagada no
        # mesmo commit) — esta linha reprovou, que é exatamente o que ela
        # promete fazer. Hoje é `app/fala_do_mapa.py::Numero`, irmão dele no
        # mesmo módulo, que a medição de 26/08 mostrou NÃO ter caído junto.
        # Enquanto estiver declarado em `_SEM_CAMINHO_HOJE`, serve. No dia em
        # que alguém o fiar, o conserto é trocar o canário de novo, não
        # silenciar.
        assert "app/fala_do_mapa.py::Numero" in soltas, (
            "sem o ponto de entrada a varredura devolveu algo inesperado — a "
            "medição de controle caiu junto e este caso não prova nada"
        )
        assert chave not in _promessas_publicas_por_chave(copia), (
            "o arquivo foi apagado da cópia e o símbolo continua sendo listado "
            "como promessa pública — a mordida está medindo a árvore viva"
        )
        assert chave not in promessas_sem_caminho(), (
            "a árvore de verdade foi contaminada pela mordida"
        )

    def test_a_corrente_fechada_em_si_mesma_nao_passa_mais(
        self, tmp_path: Path
    ) -> None:
        """DEFEITO (a): ``A`` chama ``B``, ``B`` chama ``A``, e mais ninguém.

        Os dois pareciam entregues, e é a forma mais cara do defeito-mãe —
        três módulos reais desta árvore passavam assim (a nota do cabeçalho
        traz a medição). Aqui a diferença é provada no MESMO caso: a régua
        plana de até 21/08 APROVA a corrente, a régua de alcance REPROVA.
        """
        copia = _copia_de_src(tmp_path)
        (copia / "daemon" / "corrente_fechada.py").write_text(
            "def entrar_no_ciclo() -> int:\n"
            "    return sair_do_ciclo() + 1\n"
            "\n\n"
            "def sair_do_ciclo() -> int:\n"
            "    if False:\n"
            "        return entrar_no_ciclo()\n"
            "    return 0\n",
            encoding="utf-8",
        )
        chaves = {
            "daemon/corrente_fechada.py::entrar_no_ciclo",
            "daemon/corrente_fechada.py::sair_do_ciclo",
        }

        plana = _regua_plana(copia)
        assert not (chaves & plana), (
            "a régua PLANA acusou a corrente fechada — então ela não é a régua "
            "de ontem, e esta mordida não está medindo a troca de 22/08/2026"
        )
        assert chaves <= set(promessas_sem_caminho(copia)), (
            "a régua de ALCANCE deixou passar a corrente fechada em si mesma: "
            "dois símbolos que ninguém alcança se satisfazendo um ao outro. É "
            "exatamente o defeito que a troca de 22/08/2026 existe para fechar"
        )
        assert not (chaves & set(promessas_sem_caminho())), (
            "a árvore de verdade foi contaminada pela mordida"
        )

    def test_a_colisao_de_nome_entre_modulos_nao_perdoa_mais(
        self, tmp_path: Path
    ) -> None:
        """DEFEITO (b): um nome não é um endereço.

        A régua plana perguntava se o NOME aparecia em algum lugar. Com isso,
        um ``Censo`` chamado num módulo absolvia o ``Censo`` órfão de outro —
        e foi assim, literalmente, que ``prontuario_dos_jogos.py``:549 se
        escondeu atrás de ``sentinela_do_wrapper.py``:302 por meses.
        """
        copia = _copia_de_src(tmp_path)
        (copia / "daemon" / "orfa_com_nome_comum.py").write_text(
            "class LevantamentoDaMesa:\n"
            '    """A órfã de verdade — ninguém a instancia."""\n'
            "\n"
            "    def valor(self) -> int:\n"
            "        return 0\n",
            encoding="utf-8",
        )
        # O homônimo mora num módulo ALCANÇADO (o `cli/app.py` é ponto de
        # entrada declarado) e não tem relação nenhuma com a órfã acima.
        (copia / "cli" / "homonimo_alcancado.py").write_text(
            "class LevantamentoDaMesa:\n"
            "    def valor(self) -> int:\n"
            "        return 1\n"
            "\n\n"
            "def usar() -> int:\n"
            "    return LevantamentoDaMesa().valor()\n",
            encoding="utf-8",
        )
        alvo = copia / "cli" / "app.py"
        alvo.write_text(
            "from hefesto_dualsense4unix.cli.homonimo_alcancado import usar\n\n"
            + alvo.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        chave = "daemon/orfa_com_nome_comum.py::LevantamentoDaMesa"

        assert chave not in _regua_plana(copia), (
            "a régua PLANA acusou a órfã mesmo com o homônimo presente — então "
            "ela não é a régua de ontem, e esta mordida não mede a troca"
        )
        assert chave in promessas_sem_caminho(copia), (
            "a régua de ALCANCE perdoou a órfã por causa de um homônimo em "
            "outro módulo — o nome voltou a valer como endereço, e a colisão "
            "de nome (defeito b de 22/08/2026) está de volta"
        )
        assert (
            "cli/homonimo_alcancado.py::LevantamentoDaMesa"
            not in promessas_sem_caminho(copia)
        ), (
            "o homônimo ALCANÇADO foi acusado junto — a resolução por módulo "
            "ficou estrita demais e passou a cobrar de quem está fiado"
        )
        assert chave not in promessas_sem_caminho(), (
            "a árvore de verdade foi contaminada pela mordida"
        )

    def test_o_comentario_do_roteiro_nao_conta_como_chamada(self) -> None:
        """Citar não é chamar — a mesma linha que separa o P3a inteiro.

        O `uninstall.sh` cita `strip_quirks_token` DUAS vezes: numa linha `#` de
        prosa (:1202) e na chamada dentro do heredoc (:1243). Um portão que
        lesse o roteiro como texto solto ficaria verde pelo comentário, e a
        mordida acima passaria a medir nada.
        """
        embutido = "\n".join(trechos_python_embutidos(_RAIZ / "uninstall.sh"))
        assert "kc.strip_quirks_token(tok)" in embutido, (
            "o extrator não achou a chamada dentro do heredoc de "
            "uninstall.sh:1150 — o delimitador ou a linha de abertura mudaram"
        )
        assert "IDs do hefesto (strip_quirks_token do módulo puro)" not in embutido, (
            "o extrator engoliu o COMENTÁRIO de uninstall.sh:1202 junto com o "
            "heredoc — ele está pegando texto demais, e menção viraria prova"
        )

    def test_uma_chave_de_ambiente_inventada_aparece_sem_mao(self) -> None:
        """Se ``portas_que_ligam`` devolvesse algo para qualquer coisa, a
        metade P3a estaria verde por construção."""
        assert not portas_que_ligam("HEFESTO_DUALSENSE4UNIX_CHAVE_QUE_NAO_EXISTE")

    def test_o_que_o_build_deixou_nao_e_porta(self, tmp_path: Path) -> None:
        """Um `.rlib` não liga interruptor nenhum — e reprova nos dois sentidos.

        O laço lê cada arquivo como TEXTO. O binário que o `cargo` deixa em
        `packaging/cosmic-applet/target` (18G em 42.738 arquivos, MEDIDO em
        13/08/2026) carrega as strings do fonte, e basta uma delas parecer
        escrita de ambiente para uma lacuna real virar "tem porta" — a dívida
        sumindo sozinha do relatório. Hoje nenhuma dispara; este caso existe
        para que o dia em que uma disparar não seja um dia de silêncio.

        As duas metades estão aqui de propósito: sem a segunda, a poda poderia
        ter cegado o detector inteiro e este caso ficaria verde por não achar
        NADA, que é o modo mais comum de uma exclusão passar despercebida.
        """
        env = "HEFESTO_DUALSENSE4UNIX_CHAVE_QUE_NAO_EXISTE"
        applet = tmp_path / "packaging" / "cosmic-applet"
        artefato = applet / "target" / "debug"
        artefato.mkdir(parents=True)
        # O formato importa: o que engana o detector é a string do fonte caindo
        # LOGO DEPOIS de um byte de quebra de linha dentro do blob — e é assim
        # que ela cai, porque o `cargo` empacota as strings uma por linha na
        # seção de dados. Um blob onde o nome não começa linha não engana
        # ninguém, e um caso montado assim ficaria verde sem medir a poda.
        (artefato / "libhefesto_applet.rlib").write_text(
            f"\x7fELF\x00\x00\n{env}=1\n\x00", encoding="utf-8"
        )
        assert not portas_que_ligam(env, tmp_path), (
            "um artefato sob `target/` foi aceito como porta — o portão passou "
            "a acreditar no que o compilador deixou, e a dívida some sozinha"
        )

        # A outra metade: o MESMO texto, uma pasta acima, CONTINUA sendo porta.
        (applet / "hefesto-applet.service").write_text(
            f"[Service]\nEnvironment={env}=1\n", encoding="utf-8"
        )
        assert portas_que_ligam(env, tmp_path) == ["empacotamento"], (
            "a poda cegou o detector para uma porta de VERDADE em "
            "`packaging/` — a exclusão levou junto o que ela devia preservar"
        )

    def test_a_unica_porta_real_da_arvore_sobrevive_a_poda(self) -> None:
        """A poda medida contra a árvore viva, e não contra a plausibilidade.

        `_PASTAS_DE_ARTEFATO` é uma EXCLUSÃO, e toda exclusão pode levar junto o
        que devia preservar. A conferência barata é a testemunha que já existe:
        a única escrita de ambiente real desta árvore mora em `assets/`, e ela
        tem de continuar sendo achada depois da poda. Se um dia uma porta
        legítima nascer sob um dos nomes podados (um `packaging/*/build/`
        versionado), é aqui que a conta não vai fechar.
        """
        assert portas_que_ligam("HEFESTO_BROKER_ALLOWED_UID") == ["unit"], (
            "a poda de `_PASTAS_DE_ARTEFATO` levou junto a única porta de "
            "verdade da árvore — a exclusão ficou larga demais"
        )

    def test_a_razao_curta_demais_reprova(self) -> None:
        """A guarda das razões, apontada para si mesma.

        Sem este caso, ``_confere_razoes`` poderia estar aceitando qualquer
        coisa e os registros virariam ``{"x": "ok"}`` sem ninguém notar.
        """
        with pytest.raises(AssertionError, match="não diz onde o caminho se perde"):
            _confere_razoes(("_REGISTRO_FABRICADO", {"exemplo": "porque sim"}))

    def test_a_razao_sem_data_reprova(self) -> None:
        """Idem para a data: lacuna sem idade vira paisagem."""
        with pytest.raises(AssertionError, match="não tem data"):
            _confere_razoes(
                (
                    "_REGISTRO_FABRICADO",
                    {
                        "exemplo": (
                            "uma razão suficientemente longa para passar do "
                            "piso de cento e vinte caracteres, com endereço em "
                            "arquivo.py:1 e com o que a fecharia, mas sem "
                            "nenhuma data escrita."
                        )
                    },
                )
            )


# ===========================================================================
# P5 — o portão não esconde metade do que vê
# ===========================================================================

#: Duas lápides fabricadas, uma para cada registro. Os caminhos NÃO existem em
#: `src/`, e é isso que as faz contar como "curadas" (fora de
#: `promessas_sem_caminho`) e como "fantasmas" (fora de
#: `_promessas_publicas_por_chave`) ao mesmo tempo.
_LAPIDE_FABRICADA_A = "fabricado/primeiro.py::cura_alfa_que_nunca_existiu"
_LAPIDE_FABRICADA_B = "fabricado/segundo.py::cura_beta_que_nunca_existiu"

_RAZAO_FABRICADA = (
    "razão fabricada só para esta mordida, longa o bastante para passar do "
    "piso de cento e vinte caracteres, com endereço em fabricado/x.py:1, com "
    "o que a fecharia, e com data 25/08/2026."
)


class TestOPortaoNaoEscondeMetadeDoQueVe:
    """As réguas que varrem DOIS registros nomeiam os dois, não só o primeiro.

    POR QUE ESTA CLASSE EXISTE — MEDIDO em 25/08/2026 (AUDITORIA-DE-PERDA-01,
    agente C2). As três réguas abaixo varriam mais de um registro com o
    ``assert`` DENTRO do laço. Em Python, o ``assert`` levanta: a primeira
    falha aborta o laço e o resto dos registros nunca é lido. O portão ficava
    vermelho — então parecia estar funcionando — e mostrava METADE do que
    tinha visto.

    O preço já foi pago: ``utils/maquina.py::gravar_maquina`` e
    ``app/ipc_bridge.py::destinos_da_aplicacao`` eram DUAS lápides caducas, em
    registros diferentes, e ninguém soube que eram duas. Quem lê "1 símbolo
    acusado" fecha a tarefa; a fila real tinha dois. É a família
    "o portão que não mede o que promete", vista de dentro. As datas medidas
    das duas estão no topo deste arquivo, na regra de varredura — elas
    conviveram HORAS, não meses, e é isso que aponta a causa para "árvore que
    mudou na mesma madrugada, por outra frente".

    MORDIDA de todas as três: devolver o ``assert`` para dentro do laço (ou
    voltar `_confere_razoes` a levantar na primeira queixa). O caso reprova
    dizendo exatamente qual registro ficou escondido.
    """

    def test_a_lapide_curada_nomeia_os_dois_registros(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Uma lápide caduca em CADA registro; as duas têm de sair na acusação."""
        monkeypatch.setitem(
            globals(), "_NAO_E_PROMESSA", {_LAPIDE_FABRICADA_A: _RAZAO_FABRICADA}
        )
        monkeypatch.setitem(
            globals(), "_SEM_CAMINHO_HOJE", {_LAPIDE_FABRICADA_B: _RAZAO_FABRICADA}
        )
        monkeypatch.setitem(
            globals(), "promessas_sem_caminho", lambda raiz=None: {}
        )

        with pytest.raises(AssertionError) as erro:
            TestTodaPromessaPublicaTemCaminho().test_nenhuma_lapide_sobreviveu_a_propria_cura()

        _os_dois_registros_saem_na_acusacao(str(erro.value), "lápide curada")

    def test_o_simbolo_fantasma_nomeia_os_dois_registros(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Idem para o cemitério: citar símbolo apagado, nos dois registros."""
        monkeypatch.setitem(
            globals(), "_NAO_E_PROMESSA", {_LAPIDE_FABRICADA_A: _RAZAO_FABRICADA}
        )
        monkeypatch.setitem(
            globals(), "_SEM_CAMINHO_HOJE", {_LAPIDE_FABRICADA_B: _RAZAO_FABRICADA}
        )
        monkeypatch.setitem(
            globals(), "_promessas_publicas_por_chave", lambda raiz=None: set()
        )

        with pytest.raises(AssertionError) as erro:
            TestTodaPromessaPublicaTemCaminho().test_nenhuma_declaracao_cita_simbolo_que_nao_existe()

        _os_dois_registros_saem_na_acusacao(str(erro.value), "símbolo fantasma")

    def test_a_razao_mal_escrita_nomeia_os_dois_registros(self) -> None:
        """E a guarda das razões: uma queixa em cada registro, as duas na conta.

        Aqui a perda era DUPLA — o ``assert`` cortava dentro do registro E os
        quatro registros de ambiente eram conferidos em quatro chamadas
        sequenciais, então a primeira queixa escondia as outras três listas
        inteiras.
        """
        with pytest.raises(AssertionError) as erro:
            _confere_razoes(
                ("_REGISTRO_FABRICADO_A", {_LAPIDE_FABRICADA_A: "porque sim"}),
                ("_REGISTRO_FABRICADO_B", {_LAPIDE_FABRICADA_B: "porque sim"}),
            )

        _os_dois_registros_saem_na_acusacao(str(erro.value), "razão mal escrita")

    def test_a_regua_da_acusacao_dupla_sabe_recusar(self) -> None:
        """O dublê que só sabe passar não é dublê.

        Se `_os_dois_registros_saem_na_acusacao` aceitasse qualquer texto, as
        três provas acima passariam com o defeito de volta. Aqui ela vê uma
        mensagem que nomeia SÓ o primeiro — que é exatamente o que o `assert`
        dentro do laço produzia — e tem de recusar.
        """
        with pytest.raises(AssertionError, match="escondeu"):
            _os_dois_registros_saem_na_acusacao(
                f"_NAO_E_PROMESSA declara: {_LAPIDE_FABRICADA_A}", "fabricado"
            )


def _os_dois_registros_saem_na_acusacao(mensagem: str, regua: str) -> None:
    """As duas lápides fabricadas têm de estar na MESMA mensagem de falha."""
    faltando = [
        alvo
        for alvo in (_LAPIDE_FABRICADA_A, _LAPIDE_FABRICADA_B)
        if alvo not in mensagem
    ]
    assert not faltando, (
        f"a régua da {regua} escondeu {len(faltando)} de 2 achados: "
        f"{faltando}\n"
        "O `assert` voltou para DENTRO do laço que varre os registros: a "
        "primeira falha aborta o laço e o resto nunca é lido. ACUMULE e "
        "falhe uma vez só, nomeando tudo — ver a regra de varredura de "
        "25/08/2026 no topo deste arquivo.\n"
        f"Mensagem que saiu: {mensagem}"
    )


# ─────────────────────────────────────────────────────────────────────────
# POR QUE ESTE ARQUIVO NÃO SE CHAMA `test_*` — 12/08/2026
#
# Ela decidiu, quando o portão foi proposto: "script duro, no CI e no
# pre-commit". O agente que o escreveu entregou como teste dentro da suíte, e
# o preço apareceu na primeira execução: MEDIDO, este arquivo sozinho levava
# mais de 5 minutos e a suíte inteira (que roda em 4m30) parecia travada. Com
# o cache de leitura em `_texto_sem_comentario` caiu para ~2 min — ainda caro
# demais para viver ao lado de 9000 testes que custam 4m30 SOMADOS.
#
# Sem o prefixo `test_`, o pytest não o coleta na varredura padrão; ele
# continua sendo executável — e é executado — quando apontado pelo caminho,
# que é como o job próprio do CI o chama. O portão NÃO está desligado: está
# fora do caminho quente.
#
# O passo que falta, e que é o que ela pediu desde o começo: convertê-lo em
# `scripts/check_*.py` de verdade, no molde dos outros portões da casa, com
# saída que diz o que FAZER. Enquanto isso não acontece, este comentário é a
# nota datada que impede a mudança de passar por acidente.
# ─────────────────────────────────────────────────────────────────────────
