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
  produto promete que isto FAZ algo. O caminho é qualquer chamador em ``src/``,
  em ``scripts/`` (que o instalador roda), ou no **Python embutido em heredoc**
  do ``install.sh``/``uninstall.sh``.

  Essa terceira porta nasceu em 13/08/2026, e nasceu de o portão ter errado: a
  varredura só lia ``*.py`` e por isso acusava de órfã a ``strip_quirks_token``,
  que o ``uninstall.sh``:1166 chama desde julho, dentro de um
  ``python3 - "${ROOT_DIR}" <<'PYEOF'``. Um portão que acusa de dívida quem está
  certo é pior que portão nenhum: ensina a próxima pessoa a não acreditar nele.

``tests/`` NUNCA conta como caminho, e é essa linha que separa as curas soltas
do resto da árvore: 30 dos 33 símbolos que este portão acusa hoje têm chamador
em ``tests/`` e nenhum em produção — pareciam entregues.

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
2. **Uso dentro do próprio arquivo.** A regra proposta era "chamador fora do
   próprio arquivo": medi, e ela acusa **846** símbolos, porque a maioria dos
   auxiliares é usada no próprio módulo — e o módulo É produção. A regra certa é
   "chamador em qualquer lugar de ``src/``, menos o corpo do próprio símbolo"
   (o "menos" impede que recursão e auto-citação satisfaçam o portão sozinhas).
3. **Docstring e ``__all__``.** Um símbolo citado só no próprio docstring, ou só
   na lista de reexportação, não é alcançado por ninguém. Ambos são descartados
   — e é por isso que ``RumbleEngine`` aparece aqui apesar de
   ``ipc_handlers.py``:2237 afirmar, num comentário, que ele "segue em uso".
4. **Alvo de atribuição.** ``X = 1`` não é uso de ``X``. Contar o ``ast.Store``
   fazia toda constante se satisfazer com a própria linha de definição.

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

#: Territórios onde um chamador de produção pode morar. ``scripts/`` entra
#: porque o instalador roda os helpers de lá (``install.sh`` chama
#: ``scripts/fix_wireplumber_default_source.sh``, por exemplo): um símbolo
#: alcançado só por um helper de ``scripts/`` ESTÁ alcançado. Hoje isso não
#: perdoa ninguém — conferido em 12/08/2026, nenhuma das 33 acusações tem
#: chamador em ``scripts/`` — e é de propósito: a porta existe para o portão
#: não passar a mentir no dia em que alguém use uma delas de lá.
_TERRITORIOS_DE_PRODUCAO = ("scripts",)

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
    "HEFESTO_BROKER_ALLOWED_UID": (
        "Qual UID pode falar com o broker de hidraw (broker/hidraw_broker.py:76). "
        "É promessa de sistema: sem ela o broker não serve a sessão dela. "
        "MEDIDO em 12/08/2026: LIGADA, por `Environment=` em "
        "assets/systemd/hefesto-hidraw-broker.service:37, com o UID substituído "
        "pelo instalador."
    ),
    "HEFESTO_DUALSENSE4UNIX_BT_MIC": (
        "Liga o microfone por Bluetooth (daemon/subsystems/bt_mic.py:49). É "
        "feature dela, e o próprio subsystems/__init__.py:14 registra que o "
        "`BtMicSubsystem` 'nasceu órfão'. MEDIDO em 12/08/2026: sem mão."
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
        "Publicar métricas é escolha de quem instala. MEDIDO em 12/08/2026: sem "
        "mão — a única ocorrência fora de src/ é uma linha de changelog do "
        "packaging/fedora/hefesto-dualsense4unix.spec:420, que não liga nada."
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
        "(daemon/lifecycle.py:1300, na borda que alterna o teclado em runtime). "
        "Logo a FEATURE tem mão — a env é o atalho de quem quer forçar o degrau "
        "do meio sem gravar decisão nenhuma no disco dela.",
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
    "HEFESTO_DUALSENSE4UNIX_BT_MIC": (
        "MEDIDO em 12/08/2026: nenhuma porta a escreve. O `install.sh` não a "
        "cita; `assets/hefesto-dualsense4unix.service` só define "
        "`Environment=PYTHONUNBUFFERED=1`; nenhum empacotamento a escreve; e a "
        "janela apenas a CITA em texto de ajuda "
        "(app/widgets/controller_card.py:522 e :1597), o que não é escrita. O "
        "campo irmão `DaemonConfig.bt_mic_enabled` também só tem leitor "
        "(bt_mic.py:79) — lifecycle.py:207 apenas declara o default False. "
        "O QUE A FECHA: uma das quatro portas. A mais barata é `Environment=` "
        "na unit; a mais certa é um interruptor na janela, porque ligar o "
        "microfone por Bluetooth é escolha por sessão e ela é quem sabe. "
        "É DECISÃO DELA qual, e por isso isto é lacuna e não conserto."
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
        "MEDIDO em 12/08/2026: a única ocorrência fora de src/ é a linha de "
        "changelog em packaging/fedora/hefesto-dualsense4unix.spec:420, que "
        "ANUNCIA a chave sem escrevê-la em lugar nenhum — é exatamente a forma "
        "de promessa que este portão existe para acusar. O campo irmão "
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
    "utils/session.py::load_coop_enabled": (
        "MEDIDO em 12/08/2026. LÁPIDE COM NOTA DATADA — `COOP-SEM-INTERRUPTOR-01`, "
        "06/08/2026, escrita no próprio docstring: a função lia "
        "`coop_disabled.flag` e um `True` gravado por versão antiga podia deixar "
        "a máquina dela sem co-op; hoje devolve `True` sempre. O docstring "
        "declara por que o corpo fica de pé: a assinatura é contrato público "
        "que CLI, applet e testes importam, e uma lápide legível vale mais que "
        "um `ImportError` para quem for reabrir a decisão."
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
    # --- a família mais numerosa: o desligar que ninguém chama --------------
    "daemon/subsystems/ipc.py::stop_ipc": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. É a terceira instância de "
        "um mesmo defeito de forma — o `shutdown` de daemon/connection.py:821-900 "
        "derruba bt_mic, plugins, co-op, mouse, gamepad virtual, executor e o "
        "lease do broker, e não chama NENHUMA das utilitárias `stop_*` dos "
        "subsystems, que existem e fazem trabalho real (aqui: "
        "`daemon._ipc_server.stop()` e o descarte da referência). "
        "O QUE A FECHA: uma linha no `shutdown`. NÃO consertei porque a decisão "
        "é de DESENHO e vale para as três juntas: ou o `shutdown` passa a "
        "chamar as utilitárias, ou as utilitárias somem e o `shutdown` continua "
        "sendo o único dono do desligar. Escolher uma das duas metades por "
        "conta própria deixaria a árvore pior que os dois estados coerentes. "
        "INFERIDO do código, não observado num daemon vivo."
    ),
    "daemon/subsystems/udp.py::stop_udp": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. Irmã de `stop_ipc`, mesma "
        "forma e mesmo corpo (`daemon._udp_server.stop()` e descarte da "
        "referência), e mesma ausência no `shutdown` de connection.py:821-900. "
        "O QUE A FECHA: a mesma decisão de desenho descrita na entrada de "
        "`stop_ipc` — as três se fecham juntas ou nenhuma. "
        "INFERIDO do código, não observado num daemon vivo."
    ),
    "daemon/subsystems/autoswitch.py::stop_autoswitch": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. Terceira irmã: para o "
        "`AutoSwitcher` e descarta `daemon._autoswitch`. O `shutdown` não a "
        "chama, então a thread do autoswitch é derrubada pelo fim do processo "
        "em vez de por um caminho de parada — e é justamente o autoswitch que "
        "toca disco (grava o perfil ativo). "
        "O QUE A FECHA: a mesma decisão de desenho da entrada de `stop_ipc`. "
        "INFERIDO do código, não observado num daemon vivo."
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
        "MEDIDO em 12/08/2026: nenhuma instanciação em `src/`. Todas as "
        "ocorrências fora da definição são docstring, comentário ou `__all__` — "
        "inclusive daemon/ipc_handlers.py:2237, que afirma num comentário que "
        "`O RumbleEngine segue em uso`, e daemon/ipc_rumble_policy.py:5, que "
        "diz depender de `RumbleEngine.update_auto_state`. As duas frases estão "
        "erradas hoje, e este portão é a primeira coisa da árvore a discordar "
        "delas. O throttle de rumble com política vive escrito e desligado. "
        "O QUE A FECHA: descobrir se o caminho do rumble foi SUBSTITUÍDO (e "
        "então a classe é resto, e os dois comentários se substituem pela "
        "informação certa) ou se nunca foi ligado (e então é dívida do "
        "FEAT-RUMBLE-POLICY-01). Essa diferença está fora do que grep responde, "
        "e é a primeira coisa a medir com o aparelho na mão."
    ),
    "daemon/subsystems/external_mask.py::ExternalMaskRegistry": (
        "MEDIDO em 12/08/2026: o módulo inteiro (MÁSCARA-01/E1) não tem chamador "
        "em `src/` — as duas únicas ocorrências de `external_mask` fora dele são "
        "COMENTÁRIOS (integrations/uinput_gamepad.py:146, "
        "daemon/ipc_handlers.py:3834). É a maior lacuna desta lista. "
        "O QUE A FECHA: a GUI, e não o install — a máscara é escolha POR "
        "APARELHO e o registro grava em `config_dir()`, dentro do pacote, sem "
        "artefato de sistema nenhum. O desenho da tela é DECISÃO DELA e está "
        "pendente. QUANDO A TELA NASCER, apague esta entrada."
    ),
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
    "app/ipc_bridge.py::apply_draft": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. Quem a janela usa é a irmã "
        "`apply_draft_detalhado` (app/actions/lightbar_actions.py:646 e :735), "
        "e o próprio docstring de :530 explica que a detalhada é a `função "
        "primitiva` e que `as duas formas estavam desenhadas na sprint` "
        "(APLICAR-VERDADE-01/E2) — a forma booleana ficou no `__all__` e ninguém "
        "a atravessou. "
        "ESTA ENTRADA É O ACHADO DA RÉGUA: ela estava escondida enquanto o "
        "portão contava PALAVRA de literal, porque a chave de IPC "
        "`\"profile.apply_draft\"`, escrita em daemon/ipc_server.py:109 para "
        "outra coisa, a dava por alcançada. Casar o literal inteiro a revelou. "
        "O QUE A FECHA: apagar, se a detalhada é a forma que ficou; ou fiar, se "
        "o valor-verdade simples ainda é útil a algum chamador. Antes de "
        "apagar, conferir o applet do COSMIC — este portão é cego a Rust."
    ),
    "app/ipc_bridge.py::rumble_policy_set": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. É o invólucro que DESCARTA "
        "o motivo da recusa, e o próprio docstring manda preferir o irmão: "
        "`use rumble_policy_set_checked para tê-lo`. A janela usa o `_checked`. "
        "O QUE A FECHA: apagar. Esta é a candidata mais clara a `resto` desta "
        "lista — mas apagar símbolo público é mudança que ninguém pediu, e a "
        "assinatura pode estar sendo importada pelo applet do COSMIC, que vive "
        "em packaging/cosmic-applet/ e é Rust falando por IPC, fora do alcance "
        "desta varredura. Conferir antes de apagar."
    ),
    "app/ipc_bridge.py::mouse_emulation_set": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. Fala `mouse.emulation.set` "
        "por IPC — o handler do outro lado EXISTE e está fiado "
        "(daemon/ipc_server.py:152 despacha para `_handle_mouse_emulation_set`), "
        "então a promessa é do lado da JANELA: a ponte existe e nenhuma "
        "superfície a atravessa. O docstring cita a rota speed-only do "
        "BUG-MOUSE-GUI-SYNC-01 A4. "
        "O QUE A FECHA: descobrir por qual outra ponte a aba do mouse fala com "
        "o daemon hoje, e então unificar — duas pontes para o mesmo método IPC "
        "é como uma delas apodrece sem ninguém ver."
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
    "utils/session.py::save_mouse_emulation_enabled": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. O próprio docstring a "
        "declara `Wrapper legado (FEAT-MOUSE-PERSIST-01)` e manda `Preferir a "
        "função nova, que grava as velocidades junto` — e é a nova "
        "(`save_mouse_emulation`) que a janela usa. "
        "O QUE A FECHA: apagar, junto com a irmã de leitura. Não apago nesta "
        "leva porque as duas são símbolo público e podem estar sendo importadas "
        "por fora de `src/` — o applet do COSMIC e os plugins de terceiros são "
        "os dois lugares onde este portão é cego por desenho."
    ),
    "utils/session.py::load_mouse_emulation_enabled": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. Irmã de leitura da anterior, "
        "e também `Wrapper legado` pelo próprio docstring: devolve só o toggle, "
        "descartando as velocidades. Quem a janela usa é `load_mouse_preference` "
        "/ `load_mouse_emulation`. "
        "O QUE A FECHA: a mesma decisão da entrada anterior, e as duas juntas."
    ),
    "utils/session.py::load_keyboard_emulation_enabled": (
        "MEDIDO em 12/08/2026: só `tests/` a chama, e este caso é DIFERENTE dos "
        "dois anteriores: não é invólucro legado, é a única leitura da "
        "preferência de teclado emulado que aplica o default correto. O "
        "docstring documenta uma `ASSIMETRIA DELIBERADA` com o mouse (o teclado "
        "nasce LIGADO, porque carrega os atalhos, o teclado virtual em L3/R3 e "
        "as três regiões do touchpad), e essa decisão só vale se alguém "
        "chamar a função. "
        "O QUE A FECHA: chamar do boot do daemon, onde o `keyboard_emulation.flag` "
        "já é lido — daemon/main.py:104-109 declara a precedência "
        "(default < env < flag) e é lá que a assimetria tem de valer. Vale medir "
        "com o aparelho antes: se o flag já é lido por outro caminho, o "
        "default deste invólucro pode estar sendo aplicado em outro lugar."
    ),
    # --- linha de comando do kernel ----------------------------------------
    "integrations/kernel_cmdline.py::plan_cmdline": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. É a porta de entrada "
        "'string crua' do planejador (recebe `/proc/cmdline` e delega a "
        "`plan_tokens`). Quem escreve a linha de comando do kernel de verdade "
        "hoje é o instalador, em shell. "
        "O QUE A FECHA: decidir de quem é o planejamento. Enquanto o shell do "
        "install for o dono, este módulo é uma segunda implementação da mesma "
        "regra em outra linguagem — e duas implementações da mesma regra é o "
        "estado de onde nascem as divergências que o `doctor` depois tem de "
        "explicar."
    ),
    "integrations/kernel_cmdline.py::ownership_record": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. Produz o registro de dono "
        "`{'cmdline.<param>': '<dono>'}` para o estado local — o dado que diz se "
        "fomos NÓS que pusemos um parâmetro na linha de comando do kernel, e "
        "portanto se podemos removê-lo no desinstalar. Sem chamador, ninguém "
        "grava esse registro. "
        "O QUE A FECHA: o mesmo dono da entrada anterior. Esta é a de "
        "consequência mais concreta das quatro do módulo: sem registro de dono, "
        "o desinstalar não sabe o que é dele e a escolha vira 'remover o que "
        "talvez não seja nosso' ou 'deixar lixo' — as duas ruins."
    ),
    # `integrations/kernel_cmdline.py::strip_quirks_token` MOROU AQUI, e a
    # entrada afirmava "esse cuidado está escrito e nunca roda", pedindo como
    # cura que "o `uninstall.sh` chamar este caminho". SUBSTITUÍDO em
    # 13/08/2026, porque o fato era falso e não decisão a preservar: o
    # `uninstall.sh` já chama, em uninstall.sh:1166 (`rest, changed =
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
    "profiles/sanidade.py::verificar_perfis_do_disco": (
        "MEDIDO em 12/08/2026: só `tests/` a chama. É a conveniência que junta "
        "as duas metades que já existem e funcionam — carrega os perfis do XDG "
        "e roda as REGRAS sobre eles. As irmãs `verificar_perfis` e "
        "`linhas_de_relatorio` (que o docstring diz ser o que `o doctor imprime`) "
        "existem; falta quem comece a corrente. "
        "O QUE A FECHA: o `doctor` chamar isto. É a lacuna mais barata desta "
        "lista de fechar — uma chamada — e por isso mesmo não a fecho: 'barato' "
        "não é o mesmo que 'pedido', e acrescentar saída nova ao doctor muda o "
        "que ela lê quando algo quebra."
    ),
    # --- a TUI --------------------------------------------------------------
    "tui/app.py::main_async": (
        "MEDIDO em 12/08/2026: nenhum chamador em lugar nenhum — nem `tests/`, "
        "nem `scripts/`, nem `pyproject.toml`. É um ponto de entrada declarado "
        "(`Entry point síncrono que roda o asyncio app`) que nada declara: os "
        "dois consoles de `[project.scripts]` são `cli.app:main` e "
        "`app.main:main`, e a TUI entra pelo irmão `run_tui`. "
        "O QUE A FECHA: um console script em `pyproject.toml`, se a TUI for "
        "para ter entrada própria; ou apagar, se `run_tui` já é a entrada. "
        "Como este é o único acusado da lista SEM sequer um teste que o "
        "exercite, é também o mais provável de ser resto puro."
    ),
}


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
#: solta de verdade.

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
    nos comentários em prosa do próprio roteiro (uninstall.sh:1125 cita
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


class _Referencias(ast.NodeVisitor):
    """Nomes ALCANÇADOS por um trecho de código.

    Quatro decisões, cada uma nascida de um falso positivo medido (ver o
    cabeçalho do arquivo): conta palavra de literal de texto; NÃO conta
    docstring; NÃO conta o conteúdo de ``__all__``; NÃO conta alvo de
    atribuição.
    """

    def __init__(self) -> None:
        self.nomes: set[str] = set()
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
        if isinstance(no.ctx, ast.Load):
            self.nomes.add(no.id)

    def visit_Attribute(self, no: ast.Attribute) -> None:
        if isinstance(no.ctx, ast.Load):
            self.nomes.add(no.attr)
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


def promessas_sem_caminho(raiz: Path | None = None) -> dict[str, Promessa]:
    """Funções e classes públicas de módulo que nada em produção alcança.

    ``raiz`` existe para o portão poder ser apontado para uma CÓPIA de si mesmo
    (ver ``TestOPortaoMorde``) — mutilar ou aumentar ``src/`` na árvore viva
    contamina a medição de quem estiver trabalhando ao lado
    (``ARVORE-CONGELADA-01``).
    """
    alvo = _SRC if raiz is None else raiz

    # Um passe por arquivo: para cada nó de topo, o conjunto de nomes que ELE
    # alcança. Assim "quem alcança X" é a união de todos os nós menos o próprio
    # X — e recursão ou auto-citação não satisfazem o portão sozinhas.
    refs_por_no: list[tuple[Path, int, set[str]]] = []
    candidatas: list[tuple[Promessa, Path, int]] = []
    for caminho in _modulos(alvo):
        arvore = _arvore(caminho)
        for indice, no in enumerate(arvore.body):
            refs_por_no.append((caminho, indice, _refs(no)))
            if not isinstance(
                no, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            ):
                continue
            if no.name.startswith("_") or _entregue_a_framework(no):
                continue
            relativo = caminho.relative_to(alvo).as_posix()
            candidatas.append(
                (
                    Promessa(
                        chave=f"{relativo}::{no.name}",
                        nome=no.name,
                        arquivo=relativo,
                        linha=no.lineno,
                        tipo="class" if isinstance(no, ast.ClassDef) else "def",
                    ),
                    caminho,
                    indice,
                )
            )

    raiz_do_projeto = _RAIZ if raiz is None else raiz.parents[1]

    alcancados_fora: set[str] = set()
    for territorio in _TERRITORIOS_DE_PRODUCAO:
        base = raiz_do_projeto / territorio
        if not base.is_dir():
            continue
        for caminho in _modulos(base):
            try:
                alcancados_fora |= _refs(_arvore(caminho))
            except SyntaxError:  # pragma: no cover — script quebrado é problema dele
                continue
    for roteiro in _ROTEIROS_DE_PRODUCAO:
        caminho = raiz_do_projeto / roteiro
        if not caminho.is_file():
            continue
        for trecho in trechos_python_embutidos(caminho):
            try:
                alcancados_fora |= _refs(ast.parse(trecho))
            except SyntaxError:  # pragma: no cover — heredoc quebrado é do roteiro
                continue

    orfas: dict[str, Promessa] = {}
    for promessa, caminho, indice in candidatas:
        if promessa.nome in alcancados_fora:
            continue
        alcancada = any(
            promessa.nome in refs
            for arquivo, posicao, refs in refs_por_no
            if not (arquivo == caminho and posicao == indice)
        )
        if not alcancada:
            orfas[promessa.chave] = promessa
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


def _confere_razoes(registro: dict[str, str], rotulo: str) -> None:
    for chave, razao in registro.items():
        assert len(razao) > _RAZAO_MINIMA, (
            f"a razão de {chave!r} em {rotulo} tem {len(razao)} caracteres e "
            f"não diz onde o caminho se perde: {razao!r}\n"
            "ESCREVA o endereço (arquivo:linha) e o que fecharia a lacuna. "
            "Razão curta é uma isenção fingindo ser decisão."
        )
        assert _DATA.search(razao), (
            f"a razão de {chave!r} em {rotulo} não tem data.\n"
            "ESCREVA a data da medição (DD/MM/AAAA). Sem data ninguém sabe se "
            "ela envelheceu — e uma lacuna sem idade vira paisagem."
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
        _confere_razoes(_INSTRUMENTO_DE_AMBIENTE, "_INSTRUMENTO_DE_AMBIENTE")
        _confere_razoes(_PROMESSA_DE_AMBIENTE, "_PROMESSA_DE_AMBIENTE")
        _confere_razoes(_SEM_MAO_HOJE, "_SEM_MAO_HOJE")
        _confere_razoes(
            {env: razao for env, (_alvo, razao) in _MAO_FORA_DO_AMBIENTE.items()},
            "_MAO_FORA_DO_AMBIENTE",
        )


# ===========================================================================
# P3b — a promessa pública sem caminho
# ===========================================================================


class TestTodaPromessaPublicaTemCaminho:
    """O produto promete que isto faz algo — e existe por onde chegar nisto?"""

    def test_toda_promessa_solta_esta_classificada(self) -> None:
        """O caso que importa: o portão existe para pegar a PRÓXIMA.

        Não para catalogar as trinta e três de hoje — essas já estão escritas
        acima, com endereço e com o que as fecharia. O valor deste arquivo é
        que a trigésima terceira não consegue nascer calada.

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
            "Nenhum chamador em `src/`, em `scripts/`, nem no Python embutido "
            "nos heredocs de `install.sh`/`uninstall.sh`. `tests/` NÃO conta — "
            "foi assim que trinta e três curas ficaram parecendo entregues.\n"
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
        """Registro que cita símbolo apagado é cemitério, não registro."""
        publicas = _promessas_publicas_por_chave()
        for rotulo, registro in (
            ("_NAO_E_PROMESSA", _NAO_E_PROMESSA),
            ("_SEM_CAMINHO_HOJE", _SEM_CAMINHO_HOJE),
        ):
            fantasmas = sorted(set(registro) - publicas)
            assert not fantasmas, (
                f"{rotulo} cita símbolos que não existem mais como promessa "
                f"pública de módulo: {fantasmas}\n"
                "APAGUE a entrada (o símbolo saiu da árvore), ou corrija o "
                "endereço se ele só mudou de arquivo."
            )

    def test_nenhuma_lapide_sobreviveu_a_propria_cura(self) -> None:
        """O dia em que o caminho nasce é o dia de apagar a entrada.

        É o equivalente do ``xfail(strict=True)`` do molde: a lacuna que passou
        a ser alcançada REPROVA, para que ninguém herde um registro que
        descreve uma árvore que não existe mais.
        """
        soltas = set(promessas_sem_caminho())
        for rotulo, registro in (
            ("_NAO_E_PROMESSA", _NAO_E_PROMESSA),
            ("_SEM_CAMINHO_HOJE", _SEM_CAMINHO_HOJE),
        ):
            curadas = sorted(set(registro) - soltas)
            assert not curadas, (
                f"{rotulo} declara estes símbolos como sem caminho, e ALGO em "
                f"produção já os alcança: {curadas}\n"
                "APAGUE a entrada. A cura chegou e a lápide ficou — é assim "
                "que um registro honesto vira mentira, e a próxima pessoa "
                "perde uma tarde descobrindo que o texto está velho."
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
        _confere_razoes(_NAO_E_PROMESSA, "_NAO_E_PROMESSA")
        _confere_razoes(_SEM_CAMINHO_HOJE, "_SEM_CAMINHO_HOJE")


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
        assert len(soltas) < 60, (
            f"a varredura acusou {len(soltas)} promessas soltas — a régua "
            "quebrou. Em 12/08/2026 eram 33, e a regra ingênua ('chamador fora "
            "do próprio arquivo') dava 846."
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
        """A prova que vale: o portão pega a PRÓXIMA, não as trinta e três.

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
        assert chave not in promessas_sem_caminho(copia), (
            "o portão continuou acusando uma promessa JÁ FIADA — ele grita "
            "sempre, e um portão que grita sempre é desligado na primeira "
            "semana"
        )

    def test_um_chamador_so_em_tests_nao_conta_como_caminho(
        self, tmp_path: Path
    ) -> None:
        """A linha que separa as trinta e três do resto da árvore.

        MEDIDO em 12/08/2026: 30 dos 33 acusados têm chamador em ``tests/`` —
        pareciam entregues. Se ``tests/`` passar a contar, a acusação despenca
        para 3 e o portão para de ver justamente a forma mais comum do
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
            "— é exatamente esse engano que fez trinta e três curas parecerem "
            "entregues por meses"
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
            "COMENTÁRIO de uninstall.sh:1125 o satisfaz), ou ele parou de "
            "olhar o roteiro da CÓPIA e está medindo a árvore viva"
        )
        assert chave not in promessas_sem_caminho(), (
            "a árvore de verdade foi contaminada pela mordida"
        )

    def test_o_comentario_do_roteiro_nao_conta_como_chamada(self) -> None:
        """Citar não é chamar — a mesma linha que separa o P3a inteiro.

        O `uninstall.sh` cita `strip_quirks_token` DUAS vezes: numa linha `#` de
        prosa (:1125) e na chamada dentro do heredoc (:1166). Um portão que
        lesse o roteiro como texto solto ficaria verde pelo comentário, e a
        mordida acima passaria a medir nada.
        """
        embutido = "\n".join(trechos_python_embutidos(_RAIZ / "uninstall.sh"))
        assert "kc.strip_quirks_token(tok)" in embutido, (
            "o extrator não achou a chamada dentro do heredoc de "
            "uninstall.sh:1150 — o delimitador ou a linha de abertura mudaram"
        )
        assert "IDs do hefesto (strip_quirks_token do módulo puro)" not in embutido, (
            "o extrator engoliu o COMENTÁRIO de uninstall.sh:1125 junto com o "
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
            _confere_razoes({"exemplo": "porque sim"}, "_REGISTRO_FABRICADO")

    def test_a_razao_sem_data_reprova(self) -> None:
        """Idem para a data: lacuna sem idade vira paisagem."""
        with pytest.raises(AssertionError, match="não tem data"):
            _confere_razoes(
                {
                    "exemplo": (
                        "uma razão suficientemente longa para passar do piso de "
                        "cento e vinte caracteres, com endereço em arquivo.py:1 "
                        "e com o que a fecharia, mas sem nenhuma data escrita."
                    )
                },
                "_REGISTRO_FABRICADO",
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
