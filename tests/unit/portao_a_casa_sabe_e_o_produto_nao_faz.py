"""O portão da PROMESSA SEM CAMINHO — ``A-CASA-SABE-E-O-PRODUTO-NAO-FAZ-01``."""
from __future__ import annotations

import ast
import contextlib
import functools
import re
import shutil
import textwrap
from dataclasses import dataclass
from pathlib import Path

import pytest

_RAIZ = Path(__file__).resolve().parents[2]
_SRC = _RAIZ / "src" / "hefesto_dualsense4unix"

#: SHELL — ``install_udev.sh``, ``fix_wireplumber_default_source.sh``,
_PONTOS_DE_ENTRADA: dict[str, tuple[str, str, str]] = {
    "cli/app.py": (
        "pyproject.toml",
        'hefesto-dualsense4unix = "hefesto_dualsense4unix.cli.app:main"',
        "console_script da CLI; é também o ExecStart da unit do daemon "
        "(assets/hefesto-dualsense4unix.service:22, `daemon start --foreground`)",
    ),
    "__main__.py": (
        "src/hefesto_dualsense4unix/__main__.py",
        "from hefesto_dualsense4unix.cli.app import main",
        "`python -m hefesto_dualsense4unix` — a boca que não passa pelo wheel",
    ),
    "broker/hidraw_broker.py": (
        "scripts/lib/camada_de_maquina.sh",
        "src/hefesto_dualsense4unix/broker/hidraw_broker.py",
        "ENDEREÇO CORRIGIDO em 31/08/2026, e quem mandou corrigir foi esta "
        "própria régua: a fonte era `install.sh` e o commit a53f44e2 do mesmo "
        "dia (*a camada de máquina ganha casa própria*) mudou a boca de lugar "
        "— as dez curas de HOST saíram do instalador e viraram "
        "`scripts/lib/camada_de_maquina.sh`, que o `install.sh`:988 passa a "
        "carregar com `source`. O `install_broker_host` de lá (:169) é quem "
        "COPIA o arquivo para /usr/local/lib/hefesto-dualsense4unix/ com "
        "`sudo install -Dm755`, e o ExecStart continua sendo "
        "assets/systemd/hefesto-hidraw-broker.service:34. O .deb "
        "(scripts/build_deb.sh:346) e o flatpak fazem o mesmo por conta "
        "própria. A boca não morreu; ela mudou de arquivo, que é exatamente o "
        "caso que esta régua manda CONFERIR em vez de apagar",
    ),
    "integrations/sentinela_do_wrapper.py": (
        "install.sh",
        "src/hefesto_dualsense4unix/integrations/sentinela_do_wrapper.py",
        "install.sh:3972 substitui __SENTINELA__ na unit, cujo ExecStart é "
        "`python3 __SENTINELA__ --reparar` "
        "(assets/hefesto-steam-input-guard.service:29); o doctor.sh:1982 "
        "(check_sentinela_wrapper, --censo) também o roda",
    ),
    "integrations/steam_input_ponte.py": (
        "scripts/disable_steam_input.sh",
        "integrations/steam_input_ponte.py",
        "roda como `python3 ${PONTE_PY} --ligar` em "
        "scripts/disable_steam_input.sh:283+298, e esse roteiro é o ExecStart "
        "de assets/hefesto-steam-input-guard.service:14 (install.sh:3973)",
    ),
    "integrations/steam_launch_options.py": (
        "install.sh",
        "src/hefesto_dualsense4unix/integrations/steam_launch_options.py",
        "install.sh:4018 o roda com `--migrate`; uninstall.sh:1966 o roda para "
        "tirar o wrapper; doctor.sh:2228 o publica como cura",
    ),
    "integrations/proton_pin.py": (
        "install.sh",
        "src/hefesto_dualsense4unix/integrations/proton_pin.py",
        "install.sh:4190 (--ensure) e uninstall.sh:1944 o rodam; "
        "doctor.sh:4056 (check_proton_pin, --report) também",
    ),
    "integrations/opcoes_por_jogo.py": (
        "install.sh",
        "src/hefesto_dualsense4unix/integrations/opcoes_por_jogo.py",
        "install.sh:4336 substitui __OPCOES_POR_JOGO__ na unit, cujo ExecStart "
        "é `python3 __OPCOES_POR_JOGO__ --aplicar` "
        "(assets/hefesto-steam-input-guard.service:54) — o mesmo caminho dos "
        "irmãos __SENTINELA__ e __PROTON_PIN__, que rodam na mesma unit",
    ),
    "integrations/audio_ks_dualsense.py": (
        "install.sh",
        "src/hefesto_dualsense4unix/integrations/audio_ks_dualsense.py",
        "install.sh:3295 o copia para ~/.local/share/hefesto-dualsense4unix/"
        "bin/hefesto-audio-ks, e o assets/hefesto-launch.sh:511 "
        "(curar_audio_ks) o roda a cada jogo lançado; uninstall.sh:2006 o "
        "roda com --remover-de-todos",
    ),
    "integrations/exame_da_mesa.py": (
        "scripts/doctor.sh",
        "src/hefesto_dualsense4unix/integrations/exame_da_mesa.py",
        "scripts/doctor.sh:3978 (check_exame_da_mesa) o roda — e o "
        "install.sh:4265 roda o doctor",
    ),
}

_ROTEIROS_DE_PRODUCAO = ("install.sh", "uninstall.sh", "scripts/lib/camada_de_maquina.sh")

#: `app/actions/perfis_web.py`, `gui/aba_sistema.py`) deixam de ser promessa sem
_PILOTO_DA_INTERFACE_NOVA = "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"

_PASTA_DA_PONTE = "src/hefesto_dualsense4unix/interface"

_MODULO_DA_PONTE = _PASTA_DA_PONTE.removeprefix("src/").replace("/", ".")

_CADEIA_DA_INTERFACE_NOVA: tuple[tuple[str, str, str], ...] = (
    (
        "packaging/hefesto-dualsense4unix.desktop",
        "Exec=env HEFESTO_NA_TELA=1 @RAIZ@/run.sh --gui",
        "o `.desktop` do app — o `@RAIZ@` é substituído pelo caminho da "
        "árvore pelo `install.sh`. É o ícone que ela clica, e é ele que "
        "declara a tela: o `run.sh` não a declara, e todo instrumento que o "
        "chama continua desviado.",
    ),
    (
        "run.sh",
        'exec python3 "${HERE}/scripts/abrir_interface.py"',
        "o motor: ativa a venv desta árvore, desarma o pixbuf de terminal "
        "empacotado e entrega ao envoltório de identidade. O XWayland só vem "
        "com o opt-in (`HEFESTO_DUALSENSE4UNIX_XWAYLAND=1` ou "
        "`--force-xwayland`), desde a ordem dela de 19/09/2026. Aqui havia "
        "`python3 -m …app.main`, a janela GTK velha.",
    ),
    (
        "scripts/abrir_interface.py",
        '"src" / "hefesto_dualsense4unix" / "interface" / "hefesto_vivo.py"',
        "o envoltório versionado: veste `prgname`, `program_class` e ícone no "
        "PROCESSO e só então carrega o piloto com `runpy`, sem mudar uma linha "
        "dele.",
    ),
)

_LANCADORES: tuple[str, ...] = tuple(
    fonte for fonte, _agulha, _razao in _CADEIA_DA_INTERFACE_NOVA if fonte.endswith(".py")
)

_HEREDOC_PYTHON = re.compile(
    r"""\bpython3?\b[^\n<]*<<-?\s*(['"]?)([A-Za-z_][A-Za-z0-9_]*)\1\s*$"""
)

_PORTAS_DE_AMBIENTE: dict[str, tuple[str, ...]] = {
    "install": ("install.sh", "uninstall.sh"),
    "unit": ("assets",),
    "empacotamento": ("packaging", "flatpak"),
    "janela": (
        "src/hefesto_dualsense4unix/app",
        "src/hefesto_dualsense4unix/gui",
    ),
}


_INSTRUMENTO_DE_AMBIENTE: dict[str, str] = {
    "HEFESTO_RADIO_DE_VERDADE": (
        "22/09/2026 — o ESCAPE da guarda do rádio "
        "(`integrations/gesto_de_reconexao._a_suite_esta_rodando`). Ela nasceu "
        "de um estrago medido: o passo de rádio do «Reconectar controles» "
        "nasceu sem trava e a primeira corrida de 457 testes chamou "
        "`Disconnect` e `Connect` nos QUATRO DualSense da mesa dela, ao vivo. "
        "Com a suíte no ar o `busctl` deste módulo recusa; "
        "`HEFESTO_RADIO_DE_VERDADE=1` devolve o bus a quem PRECISA medi-lo, e "
        "transfere para quem declarou a responsabilidade pelo rádio dela. É "
        "instrumento e não promessa: o produto instalado não lê esta chave, "
        "nenhum fluxo dela passa por aqui, e ligá-la não abre feature nenhuma."
    ),
    "HEFESTO_AVISO_DE_VERDADE": (
        "25/09/2026 — o ESCAPE da guarda do aviso da área de trabalho "
        "(`integrations/desktop_notifications._a_suite_esta_rodando`). Ela "
        "nasceu de uma foto dela: três «Teclado na tela aberto pelo L3.» na "
        "tela dela às 20h18, mandados pela SUÍTE — 22 avisos no lote do teclado "
        "e do hotkey, medidos num barramento de mentira. Com a suíte no ar o "
        "`notify` recusa antes do barramento; `HEFESTO_AVISO_DE_VERDADE=1` "
        "devolve o caminho inteiro ao teste que o declara com o barramento "
        "dublado, e o `tests/conftest.py` a tira do ambiente herdado. É "
        "instrumento e não promessa: fora da suíte ela não muda nada, nenhum "
        "fluxo dela passa por aqui, e ligá-la não abre feature nenhuma."
    ),
    "HEFESTO_NA_TELA": (
        "04/09/2026 — o ESCAPE da guarda TELA-DELA-01/02. Sem ele, a suíte e "
        "os 21 instrumentos de `scripts/` que abrem `Gtk.Window` desviam a "
        "janela para um `Xvfb` próprio, porque ela tem UMA tela e uma janela "
        "que nasce nela quebra o trabalho dela — reportado por ela duas vezes "
        "no mesmo dia. `HEFESTO_NA_TELA=1` devolve a sessão viva para quem "
        "PRECISA ver a janela (depurar um layout com gerenciador de janelas). "
        "É instrumento e não promessa: nenhum fluxo dela passa por aqui, o "
        "produto instalado não lê esta chave, e ligá-la não abre feature "
        "nenhuma — só transfere para quem ligou a responsabilidade pela tela."
    ),
    "HEFESTO_BANCADA": (
        "Desvia para onde os geradores de página ESCREVEM "
        "(interface/onde.py:_DESVIO). Existe para UMA coisa: deixar um portão "
        "rodar os dez geradores num diretório temporário e comparar o que SAIU "
        "com o que está no disco, sem tocar na bancada dela. O próprio módulo "
        "escreve a razão de ele não agir sozinho: `Ele NÃO tem efeito quando a "
        "variável não está posta, que é sempre — nenhum fluxo dela passa por "
        "aqui, e um desvio que agisse sozinho seria pior que a doença`. Não "
        "abre feature nenhuma; ausente é o caminho de produção. MEDIDO em "
        "01/09/2026."
    ),
    "HEFESTO_SEM_JANELA": (
        "A TRAVA DA TELA DELA (gui/ponte_da_tela.py:janela_proibida_na_tela). "
        "Quem a exporta não consegue abrir janela visível nesta máquina: a "
        "`JanelaDaAba` cai para `Gtk.OffscreenWindow` mesmo quando o chamador "
        "pediu janela na tela, e o visor `interface/ver.py` recusa dizendo. "
        "NÃO abre nem fecha feature nenhuma do produto: ausente é o caminho de "
        "produção, e o lançador dela abre exatamente como sempre. Ela existe "
        "para quem TRABALHA na máquina dela — uma leva de agente, um portão, "
        "um ensaio —, e nasceu de uma foto: com treze frentes em voo, oito "
        "cópias da mesma janela nasceram empilhadas na tela dela, em cima do "
        "que ela estava fazendo. O `--oculta` já existia e não bastou porque a "
        "regra vivia no prompt de quem abre, e todo caminho novo nasce sem "
        "ela. MEDIDO em 02/09/2026."
    ),
    "HEFESTO_BROKER_SOCKET": (
        "Endereço do socket do broker de hidraw. Não é escolha dela: é ponto de "
        "injeção para o teste apontar o cliente a um socket de mentira "
        "(integrations/hidraw_broker_client.py:22). Em produção o caminho vem "
        "do XDG. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_CARONA_WRAPPER": (
        "Desliga a carona do wrapper da Steam (app/actions/carona_do_wrapper.py:183). "
        "A razão está escrita na seção `O DESLIGADOR, e por que ele existe` do "
        "próprio módulo, em maiúsculas: `Ele NÃO é uma flag de produto — a regra "
        "da casa é toda cura entra no install, sem flag, e em produção a carona "
        "está sempre ligada`. Ausente = LIGADA, e é isolamento de suíte: a suíte "
        "roda na máquina DELA e um teste de GUI que chamasse `Salvar` com a "
        "carona ligada varreria o `localconfig.vdf` REAL. Quem a desliga é o "
        "`tests/conftest.py`:1197, em todo teste. MEDIDO em 18/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_ASSETS_DIR": (
        "Onde procurar os arquivos de `assets/` (daemon/service_install.py:35). "
        "Existe para o teste e para a execução a partir do fonte não dependerem "
        "de instalação; em produção o caminho é derivado do pacote. Não abre "
        "feature nenhuma. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_FAKE": (
        "Sobe o daemon com controle de mentira (daemon/main.py:13 e :113). É a "
        "chave que permite a suíte inteira rodar sem aparelho na mesa. Ligá-la "
        "em produção seria o defeito, não a cura. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_FAKE_TRANSPORT": (
        "Diz ao controle de mentira se ele deve fingir cabo ou Bluetooth "
        "(daemon/main.py:16). Irmã da chave FAKE e sem sentido fora dela — é "
        "instrumento de bancada. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_INIT_TIMEOUT_SEC": (
        "Ajuste fino do tempo de espera da inicialização do backend "
        "(core/backend_pydualsense.py:149). Número de calibração, não escolha "
        "dela: não há nada na tela que ela reconheceria como esta chave. "
        "MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME": (
        "Nome do socket de IPC (utils/xdg_paths.py:15). Isola instâncias "
        "paralelas em teste; o applet do COSMIC apenas LÊ a chave "
        "(packaging/cosmic-applet/src/ipc.rs:54) para achar o mesmo socket. "
        "Ninguém a liga como feature. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_LEDS_ROOT": (
        "Raiz falsa de `/sys/class/leds` (core/external_leds.py:38 e "
        "core/sysfs_leds.py:30). Existe para o teste ter um sysfs de mentira "
        "sob si; em produção a raiz é fixa. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_LOG_FORMAT": (
        "Formato do log (utils/logging_config.py:29). Chave de diagnóstico de "
        "quem lê log, não superfície de produto — não muda o que o aparelho faz. "
        "MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_LOG_LEVEL": (
        "Verbosidade do log (utils/logging_config.py:28). Mesma família da "
        "anterior: instrumento de quem investiga um defeito, e o caminho "
        "publicado para investigar é o `doctor`, não esta chave. MEDIDO em "
        "12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_METRICS_PORT": (
        "Porta do servidor de métricas (daemon/subsystems/metrics.py:21). É "
        "parâmetro do instrumento cujo INTERRUPTOR é `..._METRICS_ENABLED` — "
        "afinar a porta sem poder ligar o servidor não é promessa; a promessa "
        "está declarada como lacuna na chave ENABLED. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_NICE": (
        "Prioridade de escalonamento do processo do daemon (daemon/main.py:66). "
        "Ajuste de operação, não escolha publicada: a unit é quem decidiria "
        "isso, e decide por outros meios. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_NOTIFY_THROTTLE_SEC": (
        "Intervalo mínimo entre notificações repetidas "
        "(integrations/desktop_notifications.py:22). Calibração do instrumento "
        "de notificação; a promessa é a chave `..._DESKTOP_NOTIFICATIONS`, que "
        "está declarada como lacuna. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_NO_WINDOW_DETECT": (
        "Desliga a detecção de janela em foco (cli/app.py:265, "
        "profiles/autoswitch.py:70). Existe para o teste do autoswitch não "
        "depender de um compositor vivo, e para a CLI poder rodar num shell sem "
        "sessão gráfica. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_PLUGINS_DIR": (
        "Onde procurar plugins (daemon/subsystems/plugins.py:112). Aponta o "
        "carregador a um diretório de mentira no teste; em produção o diretório "
        "é o do XDG. O INTERRUPTOR dos plugins é `..._PLUGINS_ENABLED`, que é "
        "outra chave. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_POLL_HZ": (
        "Frequência do laço de poll (daemon/main.py:69). Já é escolha publicada "
        "por OUTRA porta — `--poll-hz` do subcomando `daemon start` "
        "(cli/app.py:251). A env é o atalho de bancada para o mesmo número. "
        "MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_PS_LONG_PRESS_MS": (
        "Quantos milissegundos seguram o PS para contar como pressão longa "
        "(daemon/main.py:73). Calibração de gesto; afinada por quem mede, não "
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
        "(core/backend_pydualsense.py:162). Número de calibração do transporte, "
        "medido com o aparelho na mão; não é superfície de escolha. MEDIDO em "
        "12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_RESET_TRAY_WARNING": (
        "Faz o aviso da bandeja ser emitido de novo (app/tray.py:171). Existe "
        "para reencenar um aviso já visto durante uma medição de tela; o "
        "caminho publicado é apagar o arquivo de estado. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_DUALSENSE4UNIX_SKIP_PRESET_SEED": (
        "Pula a semeadura dos perfis de fábrica (profiles/loader.py:79). Existe "
        "para o teste começar de um diretório de perfis vazio; em produção a "
        "semeadura é justamente o que se quer. MEDIDO em 12/08/2026."
    ),
    "HEFESTO_RADIO_TRAVA": (
        "23/09/2026, O-DIARIO-DO-RADIO-01 — desvia a trava comum do rádio "
        "(`integrations/diario_do_radio.caminho_da_trava`, e o mesmo nome no "
        "`bt_health_watchdog.sh`). Existe para a régua pôr o watchdog root e o "
        "daemon disputando um arquivo de `tmp_path`, e não a trava de "
        "/run/hefesto-dualsense4unix que segura o watchdog DELA. O produto "
        "instalado não a escreve: sem ela, cada lado acha a trava comum sozinho."
    ),
    "HEFESTO_RADIO_DIARIO": (
        "23/09/2026, O-DIARIO-DO-RADIO-01 — desvia o diário comum do rádio de "
        "quem roda como ela (`integrations/diario_do_radio.caminho_do_diario`). "
        "É o gancho da régua e de quem mede à mão; o produto instalado não o "
        "escreve, e sem ele o diário mora em ~/.local/state, que é o que a "
        "sprint pede. Ligá-lo não abre feature nenhuma."
    ),
    "HEFESTO_RADIO_DIARIO_ROOT": (
        "23/09/2026, O-DIARIO-DO-RADIO-01 — desvia o diário dos motores ROOT "
        "(`diario_do_radio.caminho_do_diario_do_root`, a ponte privilegiada e o "
        "watchdog). Com a suíte no ar o leitor Python já não o abre sem este "
        "gancho, e a ponte o APAGA sob sudo junto com os outros ganchos: nenhum "
        "fluxo dela passa por aqui, e o produto instalado não o escreve."
    ),
    "HEFESTO_MEMORIA_ENSAIO": (
        "25/09/2026, ESQUECER-OS-CONTROLES-01 — a GUARDA do lar de mentira "
        "(`utils/memoria_dos_controles.conferir_o_ensaio`): ligada, qualquer "
        "raiz que resolva para o lar ou o `/var/lib` de verdade faz o comando "
        "RECUSAR antes de tocar em qualquer coisa, e o `Sistema` fica inerte "
        "(não para o daemon dela, não pergunta à Steam dela). É a régua quem a "
        "liga; o comando dela nunca, e ligá-la não abre feature nenhuma."
    ),
    "HEFESTO_MEMORIA_BLUEZ": (
        "25/09/2026, ESQUECER-OS-CONTROLES-01 — desvia o armazenamento do BlueZ "
        "para o lar de mentira da régua (`Raizes.do_ambiente`). Sob root o "
        "desvio MORRE (`raizes_do_root` volta às raízes reais), e com as três "
        "raízes do root desviadas a parte do root roda no próprio processo, sem "
        "sudo. Nenhum fluxo dela passa por aqui."
    ),
    "HEFESTO_MEMORIA_VARLIB": (
        "25/09/2026, ESQUECER-OS-CONTROLES-01 — desvia o `/var/lib/<slug>` (as "
        "cópias de pareamento e o diário do root) para o lar de mentira, com a "
        "mesma regra do `HEFESTO_MEMORIA_BLUEZ`: morre sob root, e desviar só "
        "parte das raízes do root faz o comando recusar."
    ),
    "HEFESTO_MEMORIA_GUARDADO_ROOT": (
        "25/09/2026, ESQUECER-OS-CONTROLES-01 — desvia a pasta onde a parte do "
        "root guarda (`/var/lib/hefesto-memoria-guardada`), com a mesma regra "
        "dos outros dois desvios do root. Nenhum fluxo dela passa por aqui."
    ),
    "HEFESTO_MEMORIA_SISTEMA": (
        "25/09/2026, ESQUECER-OS-CONTROLES-01 — desvia a raiz onde o «limpa?» "
        "procura o que o install escreve no sistema (`/etc`, `/usr/local`, "
        "`/run`), para a régua montar um sistema de mentira. Sob root volta a "
        "`/`, e o «limpa?» só LÊ. Nenhum fluxo dela passa por aqui."
    ),
}

_PROMESSA_DE_AMBIENTE: dict[str, str] = {
    "HEFESTO_DUALSENSE4UNIX_CONEXAO_ZUMBI": (
        "A chave que DESLIGA o vigia das conexões de rádio "
        "(daemon/subsystems/conexoes.py). É promessa dela, de 18/09/2026: "
        "«o produto precisa ser inteligente pra evitar problemas como esse» "
        "— o link que conecta e não vira controle deixa o DualSense no "
        "padrão de fábrica, barra azul e jogador 1. Por isso ela nasce "
        "LIGADA e a chave só serve para desligar: `is_enabled` devolve True "
        "quando a variável não existe, e o `_safe_start` do `run()` sobe o "
        "vigia. MEDIDO em 20/09/2026: ausente do ambiente = ligada, e o "
        "vigia leu a mesa dela (três links em dois adaptadores, quatro "
        "controles com hidraw) acusando ZERO zumbis."
    ),
    "HEFESTO_BROKER_ALLOWED_UID": (
        "Qual UID pode falar com o broker de hidraw (broker/hidraw_broker.py:77). "
        "É promessa de sistema: sem ela o broker não serve a sessão dela. "
        "MEDIDO em 12/08/2026: LIGADA, por `Environment=` em "
        "assets/systemd/hefesto-hidraw-broker.service:37, com o UID substituído "
        "pelo instalador."
    ),
    "HEFESTO_BROKER_NO_NASCE_FECHADO": (
        "Se o nó hidraw do DualSense físico NASCE FECHADO — `0600 root`, pela "
        "regra `assets/73-hefesto-ps5-controller.rules` da cura O-NO-NASCE-FECHADO-01 "
        "(broker/hidraw_broker.py:91). É promessa dela, decidida em "
        "20/09/2026: «o Hefesto tem que ter prioridade em tudo e isso deveria "
        "estar no install por default». Ela acopla as duas metades da cura — "
        "a udev decide o NASCIMENTO do nó, e esta env conta ao broker qual é o "
        "REPOUSO para onde ele devolve o nó no restore/EOF. "
        "MEDIDO em 20/09/2026: LIGADA, por `Environment=` em "
        "assets/systemd/hefesto-hidraw-broker.service:44, com o valor "
        "renderizado pelo instalador (1 por default; 0 com `--no-fechar-o-no`)."
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
        "(integrations/desktop_notifications.py:140). É feature dela — bateria "
        "baixa, perfil ativado. MEDIDO em 12/08/2026: sem mão."
    ),
    "HEFESTO_DUALSENSE4UNIX_DUALSENSE_MIC_INTENDED": (
        "Declara que ela QUER o DualSense como microfone padrão do sistema "
        "(core/system_check.py:119), e com isso cala o alarme do doctor. É "
        "escolha dela por definição. MEDIDO em 12/08/2026: sem mão."
    ),
    "HEFESTO_DUALSENSE4UNIX_KEYBOARD_EMULATION": (
        "Liga/desliga o teclado emulado (daemon/main.py:79). É feature dela e "
        "o próprio comentário de :104 escreve a precedência: default < esta env "
        "< o `keyboard_emulation.flag`, que é a decisão DELA. MEDIDO em "
        "12/08/2026: LIGADA — não pela env, e sim pelo companheiro declarado em "
        "`_MAO_FORA_DO_AMBIENTE`."
    ),
    "HEFESTO_DUALSENSE4UNIX_METRICS_ENABLED": (
        "Liga o servidor HTTP de métricas (daemon/subsystems/metrics.py:20). "
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
        "Liga o carregamento de plugins (daemon/subsystems/plugins.py:149). É "
        "feature dela: sem isto, plugin instalado não roda. MEDIDO em "
        "12/08/2026: sem mão."
    ),
    "HEFESTO_DUALSENSE4UNIX_SYSTEM_WARNINGS_NOTIFY": (
        "Faz os avisos de infraestrutura do boot virarem notificação de desktop "
        "(daemon/lifecycle.py:1993). É escolha dela: receber ou não o aviso na "
        "tela. MEDIDO em 12/08/2026: sem mão."
    ),
}

_MAO_FORA_DO_AMBIENTE: dict[str, tuple[str, str]] = {
    "HEFESTO_DUALSENSE4UNIX_CONEXAO_ZUMBI": (
        "daemon/subsystems/conexoes.py::ConexoesSubsystem",
        "A MÃO É O DEFAULT, e por isso não há porta que LIGUE esta chave: "
        "o vigia das conexões nasce de pé. `ConexoesSubsystem.is_enabled` "
        "devolve True quando a variável não existe no ambiente, e o "
        "`_safe_start` do `Daemon.run()` o sobe — a classe está no "
        "`SUBSYSTEM_REGISTRY` e tem chamador em produção. A env só serve "
        "para DESLIGAR, e uma chave que só desliga não pode exigir quem a "
        "ligue: procurar por ela em `assets/` ou no `install.sh` seria "
        "medir a ausência de um `Environment=` que, se existisse, mataria a "
        "feature. Decisão dela, 18/09/2026: «o produto precisa ser "
        "inteligente pra evitar problemas como esse» — nada que nasça "
        "desligado cura o controle que conecta e não vira controle.",
    ),
    "HEFESTO_DUALSENSE4UNIX_KEYBOARD_EMULATION": (
        "utils/session.py::save_keyboard_emulation",
        "MEDIDO em 12/08/2026: a env é o degrau do MEIO de uma precedência de "
        "três, escrita em daemon/main.py:78 — default da dataclass (True) < "
        "esta env < `keyboard_emulation.flag`. Quem grava o flag é "
        "`save_keyboard_emulation`, e ele É chamado em produção "
        "(daemon/lifecycle.py:743-747, dentro de `set_keyboard_emulation`, na "
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

#: sai com: OS-INTERRUPTORES-QUE-NINGUEM-LIGA-01
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
        "companheiro `DaemonConfig.plugins_enabled` (daemon/lifecycle.py:117) é "
        "só um default `False` com leitores — subsystems/plugins.py:150 lê os "
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
        "`DaemonConfig.metrics_enabled` também só tem leitor (metrics.py:294). "
        "O QUE A FECHA: `Environment=` na unit ou uma opção do instalador. "
        "ATENÇÃO ao decidir: enquanto ninguém liga isto, o `MetricsSubsystem` "
        "nunca sobe — e é essa a razão de o defeito irmão (o subsystem que "
        "ninguém PARA no shutdown) nunca ter sido observado numa máquina viva."
    ),
    "HEFESTO_DUALSENSE4UNIX_SYSTEM_WARNINGS_NOTIFY": (
        "MEDIDO em 12/08/2026: nenhuma porta a escreve. O daemon calcula os "
        "avisos de infraestrutura no boot, escreve cada um no log "
        "(lifecycle.py:1990) e então descarta a notificação porque a chave está "
        "vazia — o trabalho é feito e jogado fora. "
        "O QUE A FECHA: a mesma decisão da chave `..._DESKTOP_NOTIFICATIONS`, e "
        "as duas deviam ser decididas juntas: um interruptor só de "
        "'me avise na tela' cobre as duas, e dois interruptores separados para "
        "a mesma pergunta é superfície a mais na janela dela."
    ),
}


_NAO_E_PROMESSA: dict[str, str] = {
    "daemon/ganho_da_haptica.py::linear_do_cru": (
        "29/09/2026, O-GANHO-DA-HAPTICA-TEM-DONO-01 — é o instrumento das "
        "réguas, não promessa ao produto: traduz o volume CRU que o servidor de "
        "som de mentira de `tests/unit/test_o_ganho_da_haptica_tem_dono.py` "
        "guarda (:127, :159) para o fator de amplitude. O produto lê a placa pelo "
        "`%` do leitor da casa (`volumes_do_sink`) e usa as irmãs `linear_do_pct` "
        "e `pct_do_linear`, que têm chamador no dono do ganho"
    ),
    "core/formas_do_endereco.py::formas_do_endereco": (
        "28/09/2026, O-REGISTRO-COPIADO-NAO-ENTREGA-O-ENDERECO-01 — são as "
        "formas de UM endereço para as RÉGUAS, e não uma promessa ao produto: "
        "a docstring diz «É o que as réguas de forma procuram», e o item 9 da "
        "sprint nomeia quem as lê (`scripts/check_o_endereco_dela_em_toda_forma.py`, "
        "`scripts/check_endereco_de_radio.py` e "
        "`tests/unit/test_docs_mac_anonimato.py`), que `scripts/` e `tests/` "
        "não contam para este portão. O produto mascara por `mascarar` e "
        "`mascarar_endereco`, que não precisam das formas."
    ),
    "core/faixa_sintetica.py::e_endereco_sintetico": (
        "18/09/2026, UM-NUMERO-SO-01 — é a leitura da lista de faixas de teste "
        "desta casa, e o dono dela existe para o PORTÃO, não para o produto. "
        "As três faixas moravam digitadas dentro de "
        "`scripts/check_faixa_sintetica.py`, que não é pacote; quando o "
        "produto precisou da mesma lista, a alternativa era digitá-la de novo "
        "do outro lado — duas definições de \"é lixo\", que é como esta casa "
        "fabrica divergência. Quem a chama é `check_faixa_sintetica.py` (o "
        "`--limpar`, que o `doctor --fix` roda), e `scripts/` não conta para "
        "este portão. **E a ausência de chamador em produção é MEDIDA, não "
        "descuido:** a primeira cura de 18/09 expurgava a faixa dentro do "
        "`identity.order_entries` e foi RECUADA pela suíte no mesmo dia — 27 "
        "réguas desta casa usam `aa:bb:cc` como endereço de controle de "
        "verdade, e 236 arquivos a citam. Expurgar no produto é regra sobre a "
        "nossa suíte, não sobre o aparelho."
    ),
    "integrations/censo_dos_lancadores.py::sabe_ler": (
        "09/09/2026, LANCADORES-ZERO-01 — é a pergunta que uma RÉGUA faz ao "
        "módulo, e não uma promessa ao produto: a tela nunca a chama, porque "
        "`biblioteca_do_cartao` já devolve o estado certo para os quatro "
        "casos (`LIDO`, `NUNCA_ABERTO`, `ILEGIVEL`, `SEM_BIBLIOTECA`) e a "
        "frase sai de `BibliotecaDoLancador.resumo`. Perguntar "
        "\"sei ler?\" antes de ler seria a segunda verdade sobre a mesma "
        "tabela `_LEITORES`. Quem chama é "
        "`tests/unit/test_a_aba_lancadores_diz_a_verdade.py::"
        "test_os_cinco_lancadores_ganharam_leitor_de_biblioteca`, que existe "
        "para reprovar no dia em que um dos cinco perder o leitor — a régua "
        "que ANTES provava o contrário, e que escrevia o próprio gatilho de "
        "virada. Evidência: `tests/unit/"
        "test_o_censo_dos_lancadores_le_a_biblioteca.py`, 13 casos com lar de "
        "mentira; arrancar o leitor do Heroic reprova oito."
    ),
    "interface/frases_que_ela_baniu.py::texto_visivel_no_produto": (
        "06/09/2026, A-REGUA-DA-PALAVRA-VE-O-PRODUTO-01 — é a irmã de "
        "`texto_visivel` e não é promessa pela MESMA razão: o produto não lê a "
        "própria página, ele a ESCREVE. A diferença entre as duas é o que a "
        "folha do piloto esconde (`.nota{display:none !important}`), e ela "
        "existe porque a régua acusava 34 ocorrências de `mesa` \"em o "
        "produto\" sobre uma tela que não mostrava nenhuma. Quem chama são o "
        "portão `tests/unit/test_a_palavra_mesa_nao_chega_a_tela.py` "
        "(`test_a_palavra_nao_e_lida_em_nenhuma_das_dez_paginas_do_produto`) e "
        "o instrumento `interface/olhar.py --palavra --publicado` — os dois "
        "mundos que este portão não conta, e com razão. Evidência: "
        "`tests/unit/test_a_regua_da_palavra_ve_o_produto.py`, que a morde nos "
        "dois sentidos — arrancar a folha devolve as 34, e apagar a tela "
        "inteira reprova em `test_a_leitura_do_produto_nao_apaga_a_tela`."
    ),
    "interface/frases_que_ela_baniu.py::texto_visivel": (
        "06/09/2026, A-PALAVRA-MESA-SAI-01 — é a LEITURA de uma régua, e o "
        "produto nunca lê a própria página: ele a ESCREVE. Quem chama são o "
        "portão `tests/unit/test_a_palavra_mesa_nao_chega_a_tela.py` e o "
        "instrumento `interface/olhar.py --palavra`, que são os dois mundos "
        "que esta régua não conta, e com razão. Ela vive no módulo da lista "
        "porque a decisão que ela aplica é a MESMA — o que está dentro de "
        "`<code>` é nome interno e não é palavra de tela —, e duas cópias "
        "dessa decisão divergiriam no dia em que a lista ganhasse a segunda "
        "palavra. Evidência: o docstring dela cita a conferência contra o "
        "`innerText` do Chrome, e o `test_o_stripper_nao_engole_a_dica_nem_"
        "inventa_tamanho` a morde."
    ),
    "core/acoes_de_botao.py::por_grupo": (
        "A lista agrupada como a tela a desenha "
        "(core/acoes_de_botao.py). Quem a chama e o GERADOR da aba Navegacao, "
        "`interface/aba06.py` - que e BANCADA e sai da conta pela poda de "
        "`promessas_sem_caminho`. Ela nasceu em 01/09/2026 justamente para a "
        "lista deixar de ser DIGITADA no gerador: as duas copias ja tinham "
        "divergido, e a da tela deixava de fora o Backspace e o Delete "
        "que o produto emite no touchpad. A IRMA dela, `token_do_rotulo`, e do "
        "produto: o gesto `guardar-definicoes` a chama a cada Guardar. "
        "MEDIDO em 01/09/2026."
    ),
    "interface/monta.py::larg_rotulos": (
        "Auxiliar do gerador do mockup (interface/monta.py:125), chamado só pelos "
        "dez `interface/abaNN.py` — que são BANCADA e saem da conta pela poda de "
        "`promessas_sem_caminho`. O produto não gera página em tempo de execução: "
        "ele lê o HTML já escrito em `interface/paginas/`. MEDIDO em 01/09/2026."
    ),
    "interface/pacotes/a01_jogar.py::mascaras_montaveis": (
        "Pergunta ao catálogo do vpad quais máscaras o produto SABE MONTAR "
        "(`external_mask.mascaras_validas`), e quem a chama é o GERADOR da aba "
        "Jogar — `interface/aba01.py:629` e `:1799` —, que é BANCADA e sai da "
        "conta pela poda de `promessas_sem_caminho`. "
        "E ISSO ESTÁ CERTO, e a razão é do dado: a lista de máscaras montáveis "
        "é do CÓDIGO, e não do estado da máquina: ela não muda entre dois tiques. "
        "Por isso o chip cinza do `Nintendo Pro` vai CRAVADO no HTML publicado, "
        "em vez de ser repintado dez vezes por segundo com a mesma resposta. "
        "A IRMÃ dela é do produto e não está aqui: `mascara_do_controle` (o "
        "gesto) recusa em tempo de execução lendo a mesma fonte, e é ela que "
        "põe a frase no cartão quando alguém clica assim mesmo. "
        "MEDIDO em 04/09/2026, na leva das quinze queixas dela."
    ),
    "interface/monta.py::monta": (
        "O gerador do esqueleto das dez páginas. A página que ele escreve É o que o "
        "WebView renderiza, mas quem o chama são os dez `interface/abaNN.py`, que "
        "são BANCADA: rodam à mão, escrevem em `mockup/`, e o produto lê o HTML já "
        "pronto de `interface/paginas/`. A poda da bancada em "
        "`promessas_sem_caminho` tira os geradores da conta e, com eles, os "
        "chamadores desta função. MEDIDO em 01/09/2026."
    ),
    "interface/monta.py::botao_cinza": (
        "Auxiliar do gerador do mockup (a peça S-03 da D-03, 04/09/2026), que "
        "quem chama são os dez `interface/abaNN.py` — BANCADA, e por isso fora da "
        "conta pela poda de `promessas_sem_caminho`. É a mesma classificação que "
        "`interface/monta.py::monta` carrega logo acima, pela mesma razão medida: "
        "o produto não gera página em tempo de execução, ele lê o HTML já escrito "
        "em `interface/paginas/`. O docstring da função diz o mecanismo, e a "
        "régua `tests/unit/test_o_botao_cinza_diz_a_razao.py` a exercita."
    ),
    "core/virtual_motion.py::sensores_vivos_na_janela": (
        "SENSOR-DE-VERDADE-01, 04/09/2026. Régua do ENSAIO de bancada, não "
        "promessa ao produto: ela lê uma janela "
        "de motion e diz que sensor ainda carrega dado. Quem a chama é "
        "`scripts/ensaios/o_jogo_para_de_ver_o_giro.py` — instrumento, e por "
        "isso fora da conta. O produto não precisa dela: quem decide o que sai "
        "é `janela_com_sensores`, fiada no `_emit` do `PhysicalReportReader`. O "
        "docstring dela diz o limite (zero num quadro é indício, não prova) e "
        "`tests/unit/test_o_sensor_desliga_de_verdade.py` a exercita."
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
    "broker/hidraw_broker.py::physical_nodes_exposure": (
        "13/09/2026, RESTOS-DA-ONDA-DOIS-01 — FERRAMENTA DE DIAGNÓSTICO desde "
        "hoje. O chamador em produção era "
        "`EmulationActionsMixin._steam_input_excecao_status`, que a aba 07 "
        "chamava a cada leitura do cartão da Steam só para medir o `efetiva`, "
        "e o `efetiva` já não chegava à tela desde a FRASES-E-DICAS-03. A "
        "sprint tirou a varredura, e a nota datada está na docstring de "
        "`EmulationActionsMixin._steam_input_excecoes`. Quem continua "
        "chamando é o `_censo_de_fisicos` de `scripts/doctor.sh`, num heredoc "
        "Python, e o comentário dele diz por quê: é o MESMO critério de físico "
        "que o broker usa, e duas réguas para a mesma pergunta já produziram "
        "alarme falso nesta casa. Desde a RESTOS-DA-ONDA-TRES-01 a docstring da "
        "função diz o mesmo: só o `doctor.sh` consulta. Evidência: "
        "`tests/unit/test_r06_status_honesto.py::TestExposicaoDoFisico` a "
        "exercita, e `tests/unit/test_os_restos_da_onda_dois.py::"
        "test_a_07_a_leitura_do_steam_input_nao_varre_hidraw` reprova se a 07 "
        "voltar a chamá-la."
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
    "integrations/kernel_cmdline.py::apply_plan": (
        "MEDIDO em 12/08/2026. Instrumento: o docstring diz `SIMULA o plano "
        "sobre os tokens (para testes e para o doctor comparar)` e `Não toca "
        "sistema nenhum`. Quem de fato escreve a linha de comando do kernel é "
        "o instalador, em shell; esta função existe para prever o resultado."
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

    # 56 citações em `interface/`, `rumble_actions` 28, `input_actions` 21,
    "app/actions/footer_actions.py::FooterActionsMixin": (
        "06/09/2026 — LÁPIDE. Era mixin do `HefestoApp`, que saiu com a janela. "
        "O módulo é produção viva: `interface/pacotes/rodape.py` e as dez abas "
        "o citam 16 vezes. Evidência: `grep -rn footer_actions "
        "src/hefesto_dualsense4unix/interface/`."
    ),
    "app/actions/home_actions.py::HomeActionsMixin": (
        "06/09/2026 — LÁPIDE. Era mixin do `HefestoApp` (`app/app.py`), que "
        "saiu com a janela. O módulo é produção viva, e a maior de todas: 56 "
        "citações em `src/hefesto_dualsense4unix/interface/` — é dele que sai o "
        "`id_da_pagina` e o censo da aba Início. Evidência: `grep -rn "
        "home_actions src/hefesto_dualsense4unix/interface/`."
    ),
    "app/actions/input_actions.py::InputActionsMixin": (
        "06/09/2026 — LÁPIDE. Era mixin do `HefestoApp` (`app/app.py`), que "
        "saiu com a janela. O módulo é produção viva: 21 citações em "
        "`src/hefesto_dualsense4unix/interface/`, entre elas o mapa de teclas "
        "que a aba 06 lê. Evidência: `grep -rn input_actions "
        "src/hefesto_dualsense4unix/interface/`."
    ),
    "app/actions/launch_wrapper_dialog.py::LaunchWrapperDialogMixin": (
        "06/09/2026 — LÁPIDE, mesma razão. 15 citações do módulo em "
        "`interface/`. O plano D-19 §2 já dizia que este é um dos quatro de "
        "`app/actions/` sem chamador na interface nova, e que isso NÃO o torna "
        "da janela."
    ),
    "app/actions/rumble_actions.py::RumbleActionsMixin": (
        "06/09/2026 — LÁPIDE. Era mixin do `HefestoApp` (`app/app.py`), que "
        "saiu com a janela. O módulo é produção viva: 28 citações em "
        "`src/hefesto_dualsense4unix/interface/`, entre elas "
        "`texto_do_alcance_da_intensidade` (`interface/aba05.py:589`) e "
        "`BTN_GIVE_BACK_TO_GAME` (`aba05.py:90`). Evidência: `grep -rn "
        "rumble_actions src/hefesto_dualsense4unix/interface/`."
    ),
    "app/actions/triggers_actions.py::TriggersActionsMixin": (
        "06/09/2026 — LÁPIDE. Era mixin do `HefestoApp` (`app/app.py`), que "
        "saiu com a janela. O módulo é produção viva: 16 citações em "
        "`src/hefesto_dualsense4unix/interface/`, e é dele que a aba 03 lê os "
        "19 modos de gatilho. Evidência: `grep -rn triggers_actions "
        "src/hefesto_dualsense4unix/interface/`."
    ),
    "integrations/tray.py::TrayController": (
        "19/09/2026 — LÁPIDE, e ela é o efeito direto da `TRAY-ORFAO-01`. Este "
        "era o tray POBRE: clicar no ícone abria a TUI no terminal, a lista de "
        "perfis não marcava o ativo, e a linha de estado era remontada aqui em "
        "vez de vir do dono. O `cli/cmd_tray.py` passou a subir o "
        "`app.tray.AppTray`, que tem «Abrir painel», o submenu com o ativo "
        "marcado e `N controles` de `daemon.state_full` — medido na máquina "
        "dela no mesmo dia, com o daemon vivo. Decisão dela: *\"o tray faz o "
        "mesmo mas melhor\"*. "
        "`probe_gi_availability`, do MESMO arquivo, continua vivo e é chamado "
        "pelo `app/tray.py:21` — por isso a classe ganha lápide em vez de o "
        "arquivo ir para o código aposentado."
    ),
    "app/gui_dialogs.py::presentar_dialogos_em_curso": (
        "06/09/2026 — LÁPIDE. Ela trazia para a frente os diálogos abertos "
        "quando a JANELA era reapresentada, e o único chamador era o "
        "`app/app.py`. A interface nova não tem diálogo GTK modal: o que ela "
        "usa é o canal de recado das dez páginas."
    ),
    "app/theme.py::apply_theme": (
        "06/09/2026 — LÁPIDE do CHAMADOR, não do módulo. `apply_theme` aplicava "
        "o `gui/theme.css` na `Gtk.Window` do `app/app.py`. O `theme.css` "
        "CONTINUA vivo e com dois donos — `scripts/paleta_da_casa.py` e "
        "`tests/unit/test_paleta_unica.py` derivam dele as cores da casa —, e "
        "`app/theme.escalar_css` continua sendo chamado pelas réguas de "
        "geometria. O que morreu foi a janela onde a folha era pendurada."
    ),
    "utils/memoria_dos_controles.py::conferir_a_casa": (
        "25/09/2026, ESQUECER-OS-CONTROLES-01 — é o «a máquina está limpa?» da "
        "rotina de controle de qualidade, e quem o chama é "
        "`scripts/guardar-e-devolver-a-casa.py limpa`. Não tem chamador no "
        "produto POR CONSTRUÇÃO, e o docstring do script diz por quê: ele roda "
        "DEPOIS do `uninstall.sh`, quando o comando do Hefesto e a `.venv` já "
        "não existem, com o `python3` do sistema carregando este módulo pelo "
        "caminho. Um ponto de entrada do produto que o chamasse não existiria "
        "na hora em que a pergunta é feita."
    ),
    "interface/pacotes/a08_conexoes.py::rotulo_do_controle": (
        "26/09/2026, A-08-O-CHECKUP-ABSORVE-A-GESTAO-01 — o rótulo LONGO do "
        "controle («Sony • Player N • plástico • via») deixou de ser pintado "
        "pelo tique quando a linha da Gestão virou o cartão, que mostra o "
        "`rotulo_curto_do_controle`. Quem o chama é o gerador da 08 "
        "(`interface/aba08.py`, o `rotulo = _pacote08.rotulo_do_controle` e a "
        "régua interna que confere que o lugar vazio não o traz) — é o dono do "
        "texto que o desenho escreve, e o gerador não é caminho do produto."
    ),
    "core/o_modo_no_ar.py::modo_contra_o_ar": (
        "28/09/2026, O-DOCTOR-PERGUNTA-O-MODO-E-A-HORA-DO-PAD-01 — FERRAMENTA "
        "DE DIAGNÓSTICO. Quem a chama é o `check_o_modo_no_ar` de "
        "`scripts/doctor.sh`, num heredoc Python, com o `daemon.state_full` do "
        "socket; e o doctor roda no fim de todo install (a conferência final "
        "do `install.sh`). A docstring do módulo diz o mesmo: «Quem lê é o "
        "`doctor.sh`». A tela não a lê de propósito (a sprint, item 3: um aviso "
        "novo na tela é desenho). Evidência: "
        "`tests/unit/test_o_doctor_pergunta_o_modo_e_a_hora_do_pad.py::"
        "TestODoctorPergunta` roda a checagem pelo doctor."
    ),
    "core/o_modo_no_ar.py::ModoDoJogador": (
        "28/09/2026, O-DOCTOR-PERGUNTA-O-MODO-E-A-HORA-DO-PAD-01 — a linha que "
        "`modo_contra_o_ar` devolve e que o `check_o_modo_no_ar` de "
        "`scripts/doctor.sh` imprime pela `frase()`. Mesma razão da função: "
        "ferramenta de diagnóstico, sem caminho na tela por decisão da sprint."
    ),
    "core/o_modo_no_ar.py::hora_do_pad": (
        "28/09/2026, O-DOCTOR-PERGUNTA-O-MODO-E-A-HORA-DO-PAD-01 — FERRAMENTA "
        "DE DIAGNÓSTICO. Quem a chama é o `check_a_hora_do_pad` de "
        "`scripts/doctor.sh`, num heredoc Python, com o diário do kernel e o "
        "da unit do daemon; o produto não lê diário. A docstring do módulo "
        "diz: «Quem lê é o `doctor.sh`». Evidência: "
        "`tests/unit/test_o_doctor_pergunta_o_modo_e_a_hora_do_pad.py::"
        "TestAHoraDoPad` e o `test_a_noite_reprova_a_hora_no_doctor`."
    ),
    "core/o_modo_no_ar.py::HoraDoPad": (
        "28/09/2026, O-DOCTOR-PERGUNTA-O-MODO-E-A-HORA-DO-PAD-01 — a medida que "
        "`hora_do_pad` devolve e que o `check_a_hora_do_pad` de "
        "`scripts/doctor.sh` imprime pela `frase()`. Mesma razão da função: "
        "ferramenta de diagnóstico, e o produto não lê diário."
    ),
    "interface/monta.py::folha_das_cores": (
        "29/09/2026, A-TELA-PERGUNTA-AO-DONO-01 — a folha inteira dos 28 modelos "
        "é da BANCADA, não promessa ao produto: quem a chama são os geradores das "
        "abas 05 e 06 (`aba05.FOLHA_DOS_28`, `aba06`) e a mesa de medição "
        "(`scripts/mesa_de_medicao.py`), e nem `interface/abaNN.py` nem "
        "`scripts/` contam para este portão. A página publicada leva a folha "
        "podada de cada desenho (`monta._so_o_colorway`)."
    ),
    "interface/monta.py::folha_de_realce": (
        "29/09/2026, A-TELA-PERGUNTA-AO-DONO-01 — a regra CSS do `apertados=` de "
        "`monta.svg` é do INSTRUMENTO: quem a chama é a mesa de medição "
        "(`scripts/mesa_de_medicao.py`), e nenhuma aba aponta uma peça do "
        "desenho. A primeira aba que precisar apontar uma peça publica esta folha "
        "e passa `apertados=`; até lá, `scripts/` não conta para este portão."
    ),
    "integrations/alto_falante_bt.py::common_de_audio": (
        "29/09/2026, O-ALTO-FALANTE-TEM-UM-CAMINHO-SO-01 — INSTRUMENTO, não "
        "promessa, e a nota de 28/09/2026 no docstring o diz: o `0x35` da ponte "
        "não leva `common` (`ARRANJO_035`). Quem chama são os ensaios do rádio "
        "(`scripts/ensaios/o_som_que_sai.py` e os irmãos) e as réguas da bomba e "
        "do governador, que o importam deste módulo com nome e assinatura fixos."
    ),
    "integrations/alto_falante_bt.py::fonte_com_ritmo": (
        "29/09/2026, O-ALTO-FALANTE-TEM-UM-CAMINHO-SO-01 — INSTRUMENTO, não "
        "promessa, e a nota de 28/09/2026 no docstring o diz: a ponte lê o "
        "monitor do nó por `pw-record`, que já entrega no tempo real "
        "(`fonte_do_monitor_do_no`). Quem chama é o ensaio de bancada "
        "(`scripts/ensaios/o_som_que_sai.py`) e as réguas da bomba e do "
        "governador."
    ),
    "integrations/alto_falante_bt.py::diagnosticar": (
        "29/09/2026, O-ALTO-FALANTE-TEM-UM-CAMINHO-SO-01 — DIAGNÓSTICO DE "
        "BANCADA, e a nota de 28/09/2026 no docstring o diz: quem chama é o "
        "ensaio `scripts/ensaios/o_som_que_sai.py --sink`. O produto pergunta o "
        "que precisa a `a_ponte_do_radio_pode_subir` e a "
        "`ha_gravador_de_monitor`; o laudo fica no módulo porque a frase da "
        "libopus dele tem régua própria."
    ),
    "integrations/arranjo_da_mesa.py::adaptadores_da_mesa": (
        "29/09/2026, A-CONEXOES-DIZ-O-QUE-O-PRODUTO-JA-MEDE-01 — não é promessa "
        "ao produto: `adaptadores_da_mesa` é parte da gêmea Python do motor do "
        "arranjo que nasceu em JavaScript no mockup "
        "`mockup/congelados/2026-08-24-mapa-das-portas.html`, presa a ele pelos "
        "testes de equivalência "
        "(`tests/unit/test_arranjo_da_mesa_bate_com_o_mockup.py`). A escolha "
        "entre esta régua e a do `plano_de_radio` é palavra DELA, com a "
        "divergência medida na mão "
        "(D-A-REGUA-DO-ARRANJO-SE-DECIDE-COM-A-DIVERGENCIA-NA-MAO, "
        "`tests/unit/test_as_duas_reguas_do_arranjo_divergem_onde.py`): apagá-la "
        "decidiria por ela, e ligá-la também."
    ),
    "integrations/arranjo_da_mesa.py::candidatas": (
        "29/09/2026, A-CONEXOES-DIZ-O-QUE-O-PRODUTO-JA-MEDE-01 — não é promessa "
        "ao produto: `candidatas` é parte da gêmea Python do motor do arranjo que "
        "nasceu em JavaScript no mockup "
        "`mockup/congelados/2026-08-24-mapa-das-portas.html`, presa a ele pelos "
        "testes de equivalência "
        "(`tests/unit/test_arranjo_da_mesa_bate_com_o_mockup.py`). A escolha "
        "entre esta régua e a do `plano_de_radio` é palavra DELA, com a "
        "divergência medida na mão "
        "(D-A-REGUA-DO-ARRANJO-SE-DECIDE-COM-A-DIVERGENCIA-NA-MAO, "
        "`tests/unit/test_as_duas_reguas_do_arranjo_divergem_onde.py`): apagá-la "
        "decidiria por ela, e ligá-la também."
    ),
    "integrations/arranjo_da_mesa.py::consequencias": (
        "29/09/2026, A-CONEXOES-DIZ-O-QUE-O-PRODUTO-JA-MEDE-01 — não é promessa "
        "ao produto: `consequencias` é parte da gêmea Python do motor do arranjo "
        "que nasceu em JavaScript no mockup "
        "`mockup/congelados/2026-08-24-mapa-das-portas.html`, presa a ele pelos "
        "testes de equivalência "
        "(`tests/unit/test_arranjo_da_mesa_bate_com_o_mockup.py`). A escolha "
        "entre esta régua e a do `plano_de_radio` é palavra DELA, com a "
        "divergência medida na mão "
        "(D-A-REGUA-DO-ARRANJO-SE-DECIDE-COM-A-DIVERGENCIA-NA-MAO, "
        "`tests/unit/test_as_duas_reguas_do_arranjo_divergem_onde.py`): apagá-la "
        "decidiria por ela, e ligá-la também."
    ),
    "integrations/arranjo_da_mesa.py::plano_dos_controles": (
        "29/09/2026, A-CONEXOES-DIZ-O-QUE-O-PRODUTO-JA-MEDE-01 — não é promessa "
        "ao produto: `plano_dos_controles` é parte da gêmea Python do motor do "
        "arranjo que nasceu em JavaScript no mockup "
        "`mockup/congelados/2026-08-24-mapa-das-portas.html`, presa a ele pelos "
        "testes de equivalência "
        "(`tests/unit/test_arranjo_da_mesa_bate_com_o_mockup.py`). A escolha "
        "entre esta régua e a do `plano_de_radio` é palavra DELA, com a "
        "divergência medida na mão "
        "(D-A-REGUA-DO-ARRANJO-SE-DECIDE-COM-A-DIVERGENCIA-NA-MAO, "
        "`tests/unit/test_as_duas_reguas_do_arranjo_divergem_onde.py`): apagá-la "
        "decidiria por ela, e ligá-la também."
    ),
    "integrations/arranjo_da_mesa.py::qualidade": (
        "29/09/2026, A-CONEXOES-DIZ-O-QUE-O-PRODUTO-JA-MEDE-01 — não é promessa "
        "ao produto: `qualidade` é parte da gêmea Python do motor do arranjo que "
        "nasceu em JavaScript no mockup "
        "`mockup/congelados/2026-08-24-mapa-das-portas.html`, presa a ele pelos "
        "testes de equivalência "
        "(`tests/unit/test_arranjo_da_mesa_bate_com_o_mockup.py`). A escolha "
        "entre esta régua e a do `plano_de_radio` é palavra DELA, com a "
        "divergência medida na mão "
        "(D-A-REGUA-DO-ARRANJO-SE-DECIDE-COM-A-DIVERGENCIA-NA-MAO, "
        "`tests/unit/test_as_duas_reguas_do_arranjo_divergem_onde.py`): apagá-la "
        "decidiria por ela, e ligá-la também."
    ),
    "integrations/arranjo_da_mesa.py::receita": (
        "29/09/2026, A-CONEXOES-DIZ-O-QUE-O-PRODUTO-JA-MEDE-01 — não é promessa "
        "ao produto: `receita` é parte da gêmea Python do motor do arranjo que "
        "nasceu em JavaScript no mockup "
        "`mockup/congelados/2026-08-24-mapa-das-portas.html`, presa a ele pelos "
        "testes de equivalência "
        "(`tests/unit/test_arranjo_da_mesa_bate_com_o_mockup.py`). A escolha "
        "entre esta régua e a do `plano_de_radio` é palavra DELA, com a "
        "divergência medida na mão "
        "(D-A-REGUA-DO-ARRANJO-SE-DECIDE-COM-A-DIVERGENCIA-NA-MAO, "
        "`tests/unit/test_as_duas_reguas_do_arranjo_divergem_onde.py`): apagá-la "
        "decidiria por ela, e ligá-la também."
    ),
    "integrations/arranjo_da_mesa.py::reexame": (
        "29/09/2026, A-CONEXOES-DIZ-O-QUE-O-PRODUTO-JA-MEDE-01 — não é promessa "
        "ao produto: `reexame` é parte da gêmea Python do motor do arranjo que "
        "nasceu em JavaScript no mockup "
        "`mockup/congelados/2026-08-24-mapa-das-portas.html`, presa a ele pelos "
        "testes de equivalência "
        "(`tests/unit/test_arranjo_da_mesa_bate_com_o_mockup.py`). A escolha "
        "entre esta régua e a do `plano_de_radio` é palavra DELA, com a "
        "divergência medida na mão "
        "(D-A-REGUA-DO-ARRANJO-SE-DECIDE-COM-A-DIVERGENCIA-NA-MAO, "
        "`tests/unit/test_as_duas_reguas_do_arranjo_divergem_onde.py`): apagá-la "
        "decidiria por ela, e ligá-la também."
    ),
    "integrations/arranjo_da_mesa.py::sem_entrada": (
        "29/09/2026, A-CONEXOES-DIZ-O-QUE-O-PRODUTO-JA-MEDE-01 — não é promessa "
        "ao produto: `sem_entrada` é parte da gêmea Python do motor do arranjo "
        "que nasceu em JavaScript no mockup "
        "`mockup/congelados/2026-08-24-mapa-das-portas.html`, presa a ele pelos "
        "testes de equivalência "
        "(`tests/unit/test_arranjo_da_mesa_bate_com_o_mockup.py`). A escolha "
        "entre esta régua e a do `plano_de_radio` é palavra DELA, com a "
        "divergência medida na mão "
        "(D-A-REGUA-DO-ARRANJO-SE-DECIDE-COM-A-DIVERGENCIA-NA-MAO, "
        "`tests/unit/test_as_duas_reguas_do_arranjo_divergem_onde.py`): apagá-la "
        "decidiria por ela, e ligá-la também."
    ),
    "integrations/arranjo_da_mesa.py::variante_por_id": (
        "29/09/2026, A-CONEXOES-DIZ-O-QUE-O-PRODUTO-JA-MEDE-01 — não é promessa "
        "ao produto: `variante_por_id` é parte da gêmea Python do motor do "
        "arranjo que nasceu em JavaScript no mockup "
        "`mockup/congelados/2026-08-24-mapa-das-portas.html`, presa a ele pelos "
        "testes de equivalência "
        "(`tests/unit/test_arranjo_da_mesa_bate_com_o_mockup.py`). A escolha "
        "entre esta régua e a do `plano_de_radio` é palavra DELA, com a "
        "divergência medida na mão "
        "(D-A-REGUA-DO-ARRANJO-SE-DECIDE-COM-A-DIVERGENCIA-NA-MAO, "
        "`tests/unit/test_as_duas_reguas_do_arranjo_divergem_onde.py`): apagá-la "
        "decidiria por ela, e ligá-la também."
    ),
}

_SEM_CAMINHO_HOJE: dict[str, str] = {
    # sai com: A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01
    "integrations/haptica_bt.py::bloco_de_silencio":
        "Irmã da entrada acima, mesma sprint e mesma lacuna: o bloco zerado é "
        "o que a ponte manda quando o jogo cala, e é a MORDIDA da bancada — "
        "com ele o controle parou, e foi isso que separou o voice-coil do "
        "rumble clássico em 18/09/2026.",
    # sai com: O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01
    "integrations/cura_por_estrada.py::tem_estrada":
        "O BOTÃO «Consertar» DOS CARTÕES SEM CENSO SAIU EM 10/09/2026 "
        "(LANCADOR-LOCALIZAR-01), por palavra dela — 'se tenho tudo "
        "instalado e tá pra ser identificado não tem pq ter o botão de "
        "consertar' —, e com ele o gesto "
        "`a07_lancadores.consertar_lancador` e a consulta de "
        "`desenho_dos_lancadores.medir_no_disco`. O que caiu foi o VASO, "
        "não a cura: o módulo e as 26 provas ficam. a pergunta de sim/não "
        "que decidia o botão. ONDE O CAMINHO SE PERDE, e é UM ponto: "
        "`assets/hefesto-launch.sh` só age com `SteamAppId`, e nenhum jogo "
        "do Heroic, do Lutris, do RetroArch, do Dolphin ou do mGBA tem um — "
        "este módulo é o ÚNICO código desta casa que entrega o ambiente da "
        "ponte a um lançador que não é a Steam (a carona, nas cópias de "
        "cada jogo do Heroic desde 01/10/2026; o `tem_estrada` segue sem "
        "chamador). "
        "O que FECHA: a LANCADOR-CARONA-01, que põe a cura na CARONA em vez "
        "de num botão — palavra dela de 16/08/2026 "
        "(`app/actions/carona_do_wrapper.py:7`), o mesmo lugar em que "
        "`interface/pacotes/perfil.com_a_carona()` já repõe o atalho da "
        "Steam ao Salvar e ao Aplicar. `perfil.py` e o rodapé são de outra "
        "posse, e a cura escreve em arquivo de OUTRO programa — o que "
        "merece a palavra dela sobre 'sem botão, no Salvar' antes de "
        "qualquer linha. No dia em que ela nascer, este portão cobra que "
        "estas entradas sejam APAGADAS. 10/09/2026.",


    # pintando a volta com `state_full["rumble_motores"]`". A ONDA2-05 fez as


    # `state_full["controllers"][i]["sensores"]["giroscopio_ligado"]`".

    # sai com: O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01
    "integrations/nivel_do_microfone.py::e_stream_do_medidor": (
        "A PEÇA B da LUZ-DO-MIC-01 (03/09/2026), REMEDIDA em 28/09/2026: não tem "
        "chamador, nem pelo import dinâmico. O `luz_do_mic.py` resolve por `importlib` só "
        "`NivelDoMicrofone` e `quem_ouve_agora`, e a PEÇA A reconhece o medidor com um crivo "
        "próprio (`quem_ouve_o_microfone.e_stream_do_hefesto`), sem importar a PEÇA B: são "
        "dois crivos para a mesma pergunta. FECHA quando a PEÇA A chamar este, ou quando ele "
        "sair junto com a frase do cabeçalho de `nivel_do_microfone.py` que manda usá-lo."
    ),
    # `identidade_de` SAIU DAQUI EM 03/09/2026, e fechou pela porta que a própria
    #     `data-campo="peca"` + `data-campo="via"`, e `a02_controles.pacote()`
    #     os escreve com `identidade_de(c, ctx.mesa)`. Com os dois controles
    #   aba 06 — `aba06.py` deu `data-campo="identidade"` ao nome do cartão e
    # sai com: A-TELA-PERGUNTA-AO-DONO-01
    "app/audio_saida.py::estado_do_sono": (
        "A leitura completa numa frase só, e ela BLOQUEIA — o docstring manda rodar "
        "em worker (app/audio_saida.py:678). O sono da placa de áudio é a causa "
        "histórica de o alto-falante do controle não funcionar, e a frase existe "
        "para a tela dizer isso. Nenhuma aba a mostra. Fecha quando a Conexões ou a "
        "Sistema a pedirem, em thread. MEDIDO em 01/09/2026."
    ),
    # sai com: O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01
    "core/led_control.py::apply_led_settings": (
        "Aplica settings no controle (core/led_control.py:128) — o caminho DIRETO, "
        "sem passar pelo daemon. O produto de hoje escreve pela IPC (`led.set`), "
        "que é o certo enquanto o daemon segura o hidraw. Fecha, ou some, quando a "
        "decisão sobre escrita direta for tomada; hoje é caminho vivo sem chamador. "
        "MEDIDO em 01/09/2026."
    ),
    "daemon/subsystems/gamepad.py::suspend_vpads_for_steam_input": (
        "Retira o gamepad virtual de cena pelo tempo do jogo da allowlist (JOGO-01, "
        "daemon/subsystems/gamepad.py:460). É a cura do terceiro controle — o "
        "espelho que o Steam Input faz de CADA gamepad que vê, inclusive do nosso. "
        "Nenhum caminho do daemon a chama. Fecha quando a allowlist de jogo passar "
        "a acioná-la. MEDIDO em 01/09/2026."
    ),
    # sai com: A-TELA-PERGUNTA-AO-DONO-01
    "interface/mesa_viva.py::estado_do_card": (
        "O estado de UM card da mesa — mic, volume, canal, rota "
        "(interface/mesa_viva.py:306). O único chamador é o `controles_vivos.py`, o "
        "piloto de UMA aba, que é BANCADA e sai da conta pela poda. O piloto único "
        "(`hefesto_vivo.py`) não a chama: o pacote `a02_controles` monta o estado "
        "do card por outro caminho, e são duas verdades sobre o mesmo dado. Fecha "
        "quando o pacote da aba Controles delegar a ela, como o da Sistema já "
        "delega a `gui/aba_sistema.pacote`. MEDIDO em 01/09/2026."
    ),
    # `daemon.reload` que não chega ao serviço fazia a tela dizer **"Pronto."**
    # `app/textos_de_aplicacao.py::frase_do_desfecho` SAIU daqui em 25/08/2026,
    #     por ela é o DESPACHO do daemon, não a janela.
    # sai com: O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01
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
    # sai com: O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01
    "core/physical_report_reader.py::eh_report_de_estado": (
        "MEDIDO em 29/09/2026: a porta pública do `_struct_base` (BATERIA-QUE-PULA-01) "
        "perdeu o único chamador de produção com a O-BOTAO-DO-MIC-CHEGA-NA-HORA-01. "
        "O `_consumir_lote` do `core/backend_pydualsense` usa como guarda a resposta "
        "do `_captura_status_audio`, que roda o `extract_estado_do_mic` — o MESMO "
        "`_struct_base` —, e cada report paga uma conferência de CRC, e não duas. "
        "Só as réguas a chamam (`test_bateria_que_pula_01_a_voz_dela_nao_e_a_carga.py` "
        "e `test_o_botao_do_mic_chega_na_hora.py`). O QUE A FECHA: ela sai, com as "
        "réguas passando ao dono que o laço chama (a forma que a sprint dá ao "
        "`extract_motion_window`), ou o laço volta a chamá-la."
    ),
    # "A mesa" (`app/actions/config/secao_mesa.py::_frase_do_hub_em_comum`) a
    # fica: a decisão D-COSTURA-BLUEZ (25/08) deixa o script dono do alias,
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
    # dela"*. A assinatura mudou (I1 da INÍCIO NÃO MENTE-01): o `ao_aplicar` do
    # sai com: O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01
    "daemon/subsystems/hotkey.py::HotkeySubsystem": (
        "MEDIDO em 12/08/2026: a classe existe, tem `name = 'hotkey'` e um "
        "`start` que o próprio docstring chama de `Noop`, e NÃO está no "
        "`SUBSYSTEM_REGISTRY` de daemon/subsystems/__init__.py:41. Quem sobe o "
        "hotkey de verdade é lifecycle.py:393, chamando `start_hotkey_manager` "
        "direto. A classe é uma sentinela de um registro que ninguém itera. "
        "O QUE A FECHA: ou ela entra no registro e o `lifecycle` para de subir "
        "o hotkey à mão, ou ela sai da árvore. Como o próprio "
        "`SUBSYSTEM_REGISTRY` confessa no docstring do módulo (linha 13) que "
        "`não é iterado por ninguém em produção`, fechar isto de verdade é "
        "fechar o registro inteiro — trabalho de desenho, não de uma linha."
    ),
    # sai com: OS-INTERRUPTORES-QUE-NINGUEM-LIGA-01
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
    # `trigger_set_detalhado` e `trigger_reset_detalhado` SAÍRAM daqui em
    # o `_toast_trigger` decide pelo CORPO do daemon, via `frase_do_desfecho`.
    # `led_set_detalhado` e `player_leds_set_detalhado` saíram pelo mesmo
    # motivo em 26/08/2026 (BG-01): `_aplicar_cor_no_controle`,
    # sai com: O-CODIGO-SEM-CHAMADOR-LIGA-OU-SAI-01
    # `::load_keyboard_emulation_enabled` — SAÍRAM em 26/08/2026 porque os três
    # boot do daemon, onde o `keyboard_emulation.flag` já é lido"*. O boot JÁ
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
        "`app/actions/input_actions.py:179 frase_do_teclado_na_tela` a "
        "transforma na frase da legenda — no gancho exato que a razão antiga "
        "nomeava. Pendurá-la hoje poria DUAS frases sobre o mesmo fato na "
        "mesma legenda, uma delas falsa. O QUE FECHA: a DECISÃO entre as duas "
        "— consertar o nível da chave e apagar a irmã, ou apagar esta. Enquanto "
        "não se decide, `tests/unit/test_ambiente_presumido_01_o_que_a_maquina"
        "_nao_tem.py::TestOQueEstaFraseNaoAlcancaNoStateFullDeVerdade` trava a "
        "medição e reprova em quem consertar o nível sem escolher."
    ),
    # sai com: OS-INTERRUPTORES-QUE-NINGUEM-LIGA-01
    "app/actions/ambiente_na_tela.py::descrever_steam_encontrada": (
        "ENTREGUE em 24/08/2026 (T-12, ONDA0-Z7). Lê `steam_layout_achado` — "
        "chave que NENHUMA frente desta sprint publica ainda em `state_full` "
        "(Z7-C não toca `daemon/ipc_handlers.py`, por posse declarada em §5). "
        "ONDE O CAMINHO SE PERDE: falta o publicador da chave, além do leitor "
        "de tela. O QUE FECHA: a Onda 11 · Sistema, ou quem publicar a chave "
        "primeiro (§10 da sprint). 29/09/2026: a A-TELA-PERGUNTA-AO-DONO-01 a "
        "deixou à OS-INTERRUPTORES-QUE-NINGUEM-LIGA-01, que a liga ou a tira "
        "junto com o publicador do `steam_layout_achado`."
    ),

}

#: execução — `app/ipc_bridge.py::machine_declare` e


#: anterior cinco vezes: ``getattr(pp, "lock_proton_for_all_games", None)``

_DECORADORES_DE_FRAMEWORK = frozenset(
    {"command", "callback", "hookimpl", "gesto", "registrar"})


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
    """Os corpos de heredoc que um roteiro de shell entrega ao Python."""
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
        indice += 1
        trechos.append(textwrap.dedent("\n".join(corpo)))
    return trechos


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
    """A que módulo aponta o ``from ... import`` deste nó."""
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
    """Segue a cadeia de reexportação até o módulo que DEFINE o símbolo."""
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
    """Nomes ALCANÇADOS por um trecho de código, em três coleções."""

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


def _flags_de_bancada(arvore: ast.AST) -> frozenset[str]:
    """As flags de linha de comando que o próprio arquivo declara."""
    flags: set[str] = set()
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        if not (isinstance(alvo, ast.Attribute) and alvo.attr == "add_argument"):
            continue
        for argumento in no.args:
            if (
                isinstance(argumento, ast.Constant)
                and isinstance(argumento.value, str)
                and argumento.value.startswith("--")
            ):
                flags.add(argumento.value[2:].replace("-", "_"))
    return frozenset(flags)


def _lado_de_bancada(no: ast.If, flags: frozenset[str]) -> str | None:
    """Que metade deste ``if`` só roda na BANCADA — ``body``, ``orelse``, ou nada."""
    teste: ast.expr = no.test
    negado = False
    if isinstance(teste, ast.UnaryOp) and isinstance(teste.op, ast.Not):
        teste = teste.operand
        negado = True
    nome: str | None = None
    if isinstance(teste, ast.Attribute):
        nome = teste.attr
    elif isinstance(teste, ast.Name):
        nome = teste.id
    if nome is None or nome not in flags:
        return None
    return "orelse" if negado else "body"


def _podar_a_bancada(arvore: ast.Module) -> tuple[ast.Module, list[ast.AST]]:
    """A árvore da ponte SEM os pedaços que só a bancada roda."""
    flags = _flags_de_bancada(arvore)
    podados: list[ast.AST] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.If):
            continue
        lado = _lado_de_bancada(no, flags)
        if lado == "body":
            podados.extend(no.body)
            no.body = [ast.Pass()]
        elif lado == "orelse" and no.orelse:
            podados.extend(no.orelse)
            no.orelse = []
    citados_pela_bancada: set[str] = set()
    for no in podados:
        citados_pela_bancada |= _refs(no)
    while True:
        vivos = _refs(arvore)
        alvo = next(
            (
                (corpo, indice, definicao)
                for corpo, indice, definicao in _definicoes_de_funcao(arvore)
                if definicao.name in citados_pela_bancada
                and definicao.name not in vivos
            ),
            None,
        )
        if alvo is None:
            return arvore, podados
        corpo, indice, definicao = alvo
        corpo[indice] = ast.Pass()
        podados.append(definicao)
        citados_pela_bancada |= _refs(definicao)


def _definicoes_de_funcao(
    arvore: ast.Module,
) -> list[tuple[list[ast.stmt], int, ast.FunctionDef | ast.AsyncFunctionDef]]:
    """Toda função do módulo e da classe, com o corpo e o índice que a seguram."""
    saida: list[tuple[list[ast.stmt], int, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for indice, no in enumerate(arvore.body):
        if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
            saida.append((arvore.body, indice, no))
        elif isinstance(no, ast.ClassDef):
            for posicao, membro in enumerate(no.body):
                if isinstance(membro, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    saida.append((no.body, posicao, membro))
    return saida


def pontes_vivas(raiz_do_projeto: Path | None = None) -> dict[str, Path]:
    """Os arquivos da ponte da interface nova — o fecho a partir da BOCA."""
    base = _RAIZ if raiz_do_projeto is None else raiz_do_projeto
    pasta = base / _PASTA_DA_PONTE
    boca = base / _PILOTO_DA_INTERFACE_NOVA
    if not boca.is_file():
        return {}
    vizinhos = {
        p.stem: p for p in sorted(pasta.glob("*.py")) if "__pycache__" not in p.parts
    }
    achados: dict[str, Path] = {}
    fila = [boca.stem]
    while fila:
        nome = fila.pop()
        if nome in achados or nome not in vizinhos:
            continue
        caminho = vizinhos[nome]
        try:
            arvore = _arvore(caminho)
        except (OSError, SyntaxError):  # pragma: no cover — piloto quebrado é dele
            continue
        achados[nome] = caminho
        for no in ast.walk(arvore):
            if isinstance(no, ast.Import):
                fila.extend(a.name for a in no.names if a.name in vizinhos)
            elif isinstance(no, ast.ImportFrom):
                if no.module in vizinhos:
                    fila.append(no.module)
                elif (no.module or "").startswith(_MODULO_DA_PONTE):
                    resto = (no.module or "")[len(_MODULO_DA_PONTE):].lstrip(".")
                    if resto in vizinhos:
                        fila.append(resto)
                    else:
                        fila.extend(a.name for a in no.names if a.name in vizinhos)
    return achados


def _fontes_externas(
    raiz_do_projeto: Path, *, podar_a_bancada: bool = True
) -> list[tuple[str, ast.Module]]:
    """O Python que roda de FORA do pacote: os heredocs, e a ponte da interface."""
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
    for fonte in _LANCADORES:
        caminho = raiz_do_projeto / fonte
        if not caminho.is_file():
            continue
        try:
            saida.append((fonte, _arvore(caminho)))
        except (OSError, SyntaxError):  # pragma: no cover — lançador quebrado é dele
            continue
    for nome, caminho in sorted(pontes_vivas(raiz_do_projeto).items()):
        try:
            arvore = _arvore(caminho)
        except (OSError, SyntaxError):  # pragma: no cover — piloto quebrado é dele
            continue
        if podar_a_bancada:
            arvore, _podados = _podar_a_bancada(arvore)
        saida.append((f"{_PASTA_DA_PONTE}/{nome}.py", arvore))
    return saida


def modulos_alcancados(raiz: Path | None = None) -> set[str]:
    """Os módulos que o produto de fato roda, a partir de ``_PONTOS_DE_ENTRADA``."""
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


def promessas_sem_caminho(
    raiz: Path | None = None, *, podar_a_bancada: bool = True
) -> dict[str, Promessa]:
    """Funções e classes públicas de módulo que nada em produção alcança."""
    alvo = _SRC if raiz is None else raiz
    mapa = _mapear(alvo)
    raiz_do_projeto = _RAIZ if raiz is None else raiz.parents[1]
    externas = _fontes_externas(raiz_do_projeto, podar_a_bancada=podar_a_bancada)

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
        modulo_da_ponte = ""
        if rotulo.endswith(".py") and "#heredoc" not in rotulo:
            caminho = raiz_do_projeto / rotulo
            if caminho.is_file():
                with contextlib.suppress(ValueError):
                    modulo_da_ponte = _nome_de_modulo(alvo, caminho)
        if modulo_da_ponte and modulo_da_ponte in mapa.arvores:
            contexto = _Contexto(
                mapa, modulo_da_ponte,
                _tabela_de_nomes(mapa, modulo_da_ponte, arvore),
                mapa.define[modulo_da_ponte],
            )
        else:
            contexto = _Contexto(
                mapa, rotulo, _tabela_de_nomes(mapa, rotulo, arvore, externo=True),
                frozenset(),
            )
        visitante = _Referencias(contexto)
        visitante.visit(arvore)
        refs_por_no.append((rotulo, -1, visitante.resolvidas))
        planas |= visitante.planas

    ponte_viva = pontes_vivas(raiz_do_projeto)
    bancada_do_desenho: set[str] = set()
    if ponte_viva:
        pasta_da_ponte = raiz_do_projeto / _PASTA_DA_PONTE
        if pasta_da_ponte.is_dir():
            bancada_do_desenho = {
                p.relative_to(alvo).as_posix()
                for p in pasta_da_ponte.glob("*.py")
                if p.stem not in ponte_viva
            }

    orfas: dict[str, Promessa] = {}
    for promessa, modulo, indice in _candidatas(mapa, alvo):
        if promessa.arquivo in bancada_do_desenho:
            continue
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
    """A régua de ATÉ 21/08/2026, viva só para as mordidas mostrarem a troca."""
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


_ENV = re.compile(r"""["'](HEFESTO_[A-Z0-9_]+)["']""")

_ESCRITA_DE_AMBIENTE = (
    r"(?:^|[;&|(]|\bexport\s+|\benv\s+)\s*{nome}=",
    r"^\s*Environment=\"?{nome}=",
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
    """O arquivo sem comentários, lido UMA vez por caminho."""
    try:
        return _sem_comentario(arquivo.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        return None


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
    """Quais portas ESCREVEM este interruptor. Basta uma para a promessa valer."""
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


_DATA = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")

_RAZAO_MINIMA = 120


def _razoes_mal_escritas(registro: dict[str, str], rotulo: str) -> list[str]:
    """TODA razão de um registro que não diz onde o caminho se perde."""
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
    """Os dois registros de classificação de promessa pública."""
    return (
        ("_NAO_E_PROMESSA", _NAO_E_PROMESSA),
        ("_SEM_CAMINHO_HOJE", _SEM_CAMINHO_HOJE),
    )


class TestTodoInterruptorTemMao:
    """Uma env que o produto lê promete que algo pode ser ligado."""

    def test_todo_interruptor_lido_esta_classificado(self) -> None:
        """Chave nova sem classificação reprova por ESTAR SEM CLASSIFICAÇÃO."""
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
        """Chave apagada de ``src/`` não pode deixar classificação órfã."""
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
        """Uma feature que ela pode querer, e alguma porta que a vire."""
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
        """Companheiro é escape, e todo escape precisa de guarda."""
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


class TestTodaPromessaPublicaTemCaminho:
    """O produto promete que isto faz algo — e existe por onde chegar nisto?"""

    def test_toda_promessa_solta_esta_classificada(self) -> None:
        """O caso que importa: o portão existe para pegar a PRÓXIMA."""
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
        """Registro que cita símbolo apagado é cemitério, não registro."""
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
        """O dia em que o caminho nasce é o dia de apagar a entrada."""
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
        """A lista de entradas é o chão da régua — e chão apodrece calado."""
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


_INSTRUMENTOS_DA_BANCADA = ("regua", "regua_estados", "regua_popup", "olhar", "ver")


class TestAPonteDaInterfaceNovaEProducao:
    """A janela que ela abre conta como caminho — a régua que a mede, não."""

    def test_a_cadeia_do_lancador_da_interface_nova_esta_viva(self) -> None:
        """Os TRÊS elos, conferidos contra o que cada arquivo diz hoje."""
        piloto = _RAIZ / _PILOTO_DA_INTERFACE_NOVA
        assert piloto.is_file(), (
            f"a boca declarada da interface nova não existe: {piloto}\n"
            "CORRIJA `_PILOTO_DA_INTERFACE_NOVA`, ou APAGUE a declaração se a "
            "interface passou a entrar por outro lugar — e então tudo o que só "
            "ela alcançava volta a ser dívida, que é a verdade."
        )
        quebrados = []
        for fonte, agulha, razao in _CADEIA_DA_INTERFACE_NOVA:
            arquivo = _RAIZ / fonte
            if not arquivo.is_file():
                quebrados.append(f"a fonte {fonte!r} sumiu — {razao}")
                continue
            if agulha not in arquivo.read_text(encoding="utf-8", errors="ignore"):
                quebrados.append(
                    f"{fonte!r} não diz mais {agulha!r} — {razao}"
                )
        assert not quebrados, (
            f"a cadeia que faz o piloto ser produção quebrou em "
            f"{len(quebrados)} de {len(_CADEIA_DA_INTERFACE_NOVA)} elo(s):\n"
            + "\n".join(f"  - {q}" for q in quebrados)
            + "\nCONFIRA se o elo mudou de forma (e corrija a agulha) ou se a "
            "interface deixou de ser aberta assim (e então a ponte não é mais "
            "produção, e as curas que só ela alcança voltam a ser dívida)."
        )

    def test_a_ponte_e_o_fecho_da_boca_e_nao_a_pasta_inteira(self) -> None:
        """A ponte é o que o piloto IMPORTA — não o que mora ao lado dele."""
        ponte = pontes_vivas()
        assert Path(_PILOTO_DA_INTERFACE_NOVA).stem in ponte, (
            "o fecho não contém nem a própria boca — `pontes_vivas` quebrou, e "
            "com ela a interface nova inteira sumiu da produção"
        )
        assert "mesa_viva" in ponte, (
            "o fecho não alcança `mesa_viva`, que o piloto importa e que é o "
            "dono da mesa para a Controles e para a fita — o seguimento de "
            "`import irmão` parou de funcionar"
        )
        pasta = _RAIZ / _PASTA_DA_PONTE
        assert len(ponte) < len(list(pasta.glob("*.py"))), (
            "o fecho engoliu a pasta inteira — ele deixou de ser um fecho e "
            "virou um `glob`, e a bancada entrou junto com a ponte"
        )

    def test_o_instrumento_de_bancada_nao_entra_no_fecho(self) -> None:
        """O que MEDE a tela não é a tela — e as duas moram na mesma pasta."""
        pasta = _RAIZ / _PASTA_DA_PONTE
        sumidos = [
            nome for nome in _INSTRUMENTOS_DA_BANCADA
            if not (pasta / f"{nome}.py").is_file()
        ]
        assert not sumidos, (
            f"estes instrumentos não existem mais em {_PASTA_DA_PONTE}: "
            f"{sumidos}\nATUALIZE `_INSTRUMENTOS_DA_BANCADA` — uma testemunha "
            "que sumiu deixa este caso verde sem medir nada."
        )
        ponte = pontes_vivas()
        invasores = sorted(set(_INSTRUMENTOS_DA_BANCADA) & set(ponte))
        assert not invasores, (
            f"instrumento de bancada entrou no fecho da ponte: {invasores}\n"
            "Ou o piloto passou a importar a própria régua (e aí é o piloto "
            "que está errado), ou `pontes_vivas` virou varredura de pasta. "
            "Enquanto isso valer, uma cura chamada só pela régua conta como "
            "ligada — que é a dívida que este portão existe para acusar."
        )

    def test_a_bancada_de_dentro_do_piloto_e_reconhecida(self) -> None:
        """As flags do piloto são colhidas, e o ``if not`` NÃO é podado."""
        piloto = _arvore(_RAIZ / _PILOTO_DA_INTERFACE_NOVA)
        flags = _flags_de_bancada(piloto)
        assert {"prova_no_aparelho", "prova_clique", "oculta"} <= flags, (
            f"as mordidas do piloto não foram colhidas dos `add_argument`: "
            f"{sorted(flags)}\n`_flags_de_bancada` parou de ver o idioma, e "
            "com ela toda a poda virou decoração."
        )
        positivo = ast.parse("if self.args.prova_no_aparelho:\n    x()\n").body[0]
        negativo = ast.parse("if not args.sem_cor:\n    x()\n").body[0]
        assert isinstance(positivo, ast.If) and isinstance(negativo, ast.If)
        assert _lado_de_bancada(positivo, flags) == "body", (
            "a guarda POSITIVA de uma mordida deixou de marcar o corpo como "
            "bancada — `--prova-gesto` voltou a contar como caminho"
        )
        assert _lado_de_bancada(negativo, flags) == "orelse", (
            "a guarda NEGADA foi lida como bancada: a poda vai cortar o corpo "
            "que roda SEM a flag, que é justamente a espinha viva"
        )

    def test_nenhuma_promessa_e_alcancada_so_pela_bancada(self) -> None:
        """A distância entre as duas réguas — e hoje ela é ZERO."""
        podada = set(promessas_sem_caminho())
        inteira = set(promessas_sem_caminho(podar_a_bancada=False))
        so_a_bancada = sorted(podada - inteira)
        assert not so_a_bancada, (
            "estas promessas só são alcançadas por um pedaço de MORDIDA do "
            "piloto — `--prova-gesto`, `--sem-ponte`, `--arranca-enderecos` — e "
            "por mais nada:\n"
            + "\n".join(f"  - {c}" for c in so_a_bancada)
            + "\nA régua não é caminho. FIE a cura na espinha viva do piloto "
            "(o tique, a pintura, o gesto dela), ou declare-a como dívida. "
            "Uma cura que só a própria prova exercita é uma cura desligada com "
            "teste verde."
        )


def _copia_de_src(destino: Path, *, sem_a_ponte: bool = False) -> Path:
    """Uma cópia de ``src/`` onde se pode fabricar defeito sem sujar a árvore."""
    copia = destino / "src" / "hefesto_dualsense4unix"
    copia.parent.mkdir(parents=True, exist_ok=True)
    padroes = ["__pycache__", "*.pyc"]
    if sem_a_ponte:
        padroes.append(Path(_PASTA_DA_PONTE).name)
    shutil.copytree(_SRC, copia, ignore=shutil.ignore_patterns(*padroes))
    for roteiro in (*_ROTEIROS_DE_PRODUCAO, *_LANCADORES):
        origem = _RAIZ / roteiro
        if origem.is_file():
            (destino / roteiro).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origem, destino / roteiro)
    return copia


class TestOPortaoMorde:
    """Um portão que nunca reprovou é uma decoração com nome de portão."""

    def test_a_varredura_enxerga_os_chamadores_que_existem(self) -> None:
        """A régua conferida contra contagem independente."""
        soltas = promessas_sem_caminho()
        assert len(soltas) < 150, (
            f"a varredura acusou {len(soltas)} promessas soltas — a régua "
            "quebrou. MEDIDO em 22/08/2026: 60 com a régua de alcance (eram 33 "
            "com a régua plana), e a regra ingênua ('chamador fora do próprio "
            "arquivo') dava 846.\n"
            "TETO DE 150, REMEDIDO em 07/09/2026, e o que autoriza subir NÃO é "
            "o número — é a razão dele: 135 soltas, 134 DECLARADAS, e ZERO "
            "lápide declarada que já tem caminho. Registro e varredura andam "
            "juntos, casa a casa, que é a única forma de um teto que sobe não "
            "ser um teto que desistiu.\n"
            "DE ONDE VEIO O CRESCIMENTO: a janela GTK saiu inteira em 06/09 "
            "(`D-0609-GTK-LEVA-INTEIRA`) e levou os CHAMADORES junto. Símbolo "
            "que era chamado de dentro dela virou solto sem ninguém escrever "
            "uma linha — o produto encolheu, a lista cresceu, e as duas coisas "
            "são a MESMA.\n"
            "A REGRA CONTINUA: se este número subir sem `_SEM_CAMINHO_HOJE` "
            "crescer junto, É a régua quebrando, não a casa."
        )
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
            "a varredura não vê chamada direta (gamepad.py:180) — e é ela que "
            "prova que a saída da ESCONDER-EM-VEZ-DE-SAIR-01 continua viva"
        )
        assert (
            "integrations/proton_pin.py::lock_proton_for_all_games" not in soltas
        ), (
            "a varredura não vê despacho por STRING — `getattr(pp, "
            '"lock_proton_for_all_games", None)` em '
            "app/actions/daemon_actions.py:1126 é o ÚNICO caminho deste "
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
        """O detector de ESCRITA de ambiente, contra contagem independente."""
        assert portas_que_ligam("HEFESTO_BROKER_ALLOWED_UID") == ["unit"], (
            "o detector não vê `Environment=HEFESTO_BROKER_ALLOWED_UID=` em "
            "assets/systemd/hefesto-hidraw-broker.service:37 — a régua de "
            "escrita de ambiente quebrou"
        )

    def test_o_detector_de_ambiente_nao_confunde_citacao_com_escrita(self) -> None:
        """Citar não é ligar, e é essa diferença que o portão inteiro mede."""
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
        """A prova que vale: o portão pega a PRÓXIMA, não as já escritas."""
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
        """A outra metade: o portão CALA quando a cura é entregue."""
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
        """A linha que separa a dívida solta do resto da árvore."""
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
        """A mordida sobre o produto de verdade, e não sobre um exemplo."""
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
        """A mordida do heredoc, sobre a árvore de verdade."""
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
            "COMENTÁRIO de uninstall.sh:1663 o satisfaz), ou ele parou de "
            "olhar o roteiro da CÓPIA e está medindo a árvore viva"
        )
        assert chave not in promessas_sem_caminho(), (
            "a árvore de verdade foi contaminada pela mordida"
        )

    def test_o_ponto_de_entrada_declarado_e_o_que_abre_o_alcance(
        self, tmp_path: Path
    ) -> None:
        """A mordida de ``_PONTOS_DE_ENTRADA``, sobre a árvore de verdade."""
        copia = _copia_de_src(tmp_path)
        chave = "integrations/steam_input_ponte.py::garantir_ponte"
        assert chave not in promessas_sem_caminho(copia), (
            f"com a lista inteira o portão AINDA acusa {chave!r} — o ponto de "
            "entrada declarado não abre alcance nenhum, e um módulo que a unit "
            "do guarda roda a cada saída da Steam vira dívida"
        )

        (copia / "integrations" / "steam_input_ponte.py").unlink()

        soltas = promessas_sem_caminho(copia)
        assert "integrations/apelido_do_dongle.py::costurar_a_mesa" in soltas, (
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

    def test_sem_a_boca_da_interface_nova_a_janela_do_webview_e_divida(
        self, tmp_path: Path
    ) -> None:
        """A mordida da BOCA da interface nova, nas duas pontas."""
        chave = "gui/ponte_da_tela.py::JanelaDaAba"
        assert chave not in promessas_sem_caminho(), (
            f"{chave!r} está acusada na árvore viva — a boca da interface nova "
            "parou de abrir alcance, e o portão voltou a chamar de dívida a "
            "janela que a usuária tem aberta"
        )
        copia = _copia_de_src(tmp_path, sem_a_ponte=True)
        assert not pontes_vivas(tmp_path), (
            "a cópia nasceu com ponte mesmo pedida SEM ela — o `sem_a_ponte` "
            "parou de podar `interface/`, e esta mordida deixou de medir a "
            "declaração"
        )
        assert chave in promessas_sem_caminho(copia), (
            "sem o piloto, o portão NÃO voltou a acusar a janela do WebView: a "
            "absolvição dela vem de outro lugar, e a cadeia declarada em "
            "`_CADEIA_DA_INTERFACE_NOVA` não está segurando nada"
        )

    def test_a_cura_chamada_so_pela_mordida_do_piloto_continua_acusada(
        self, tmp_path: Path
    ) -> None:
        """O ponto delicado da migração, medido em vez de afirmado."""
        copia = _copia_de_src(tmp_path, sem_a_ponte=True)
        (copia / "daemon" / "cura_recem_nascida.py").write_text(
            "def rearmar_o_gatilho_da_cor() -> bool:\n    return True\n",
            encoding="utf-8",
        )
        chave = "daemon/cura_recem_nascida.py::rearmar_o_gatilho_da_cor"

        pasta = tmp_path / _PASTA_DA_PONTE
        pasta.mkdir(parents=True, exist_ok=True)
        piloto = tmp_path / _PILOTO_DA_INTERFACE_NOVA
        cabeca = (
            "import argparse\n"
            "\n"
            "from hefesto_dualsense4unix.daemon import cura_recem_nascida\n"
            "\n\n"
            "class Janela:\n"
            "    def __init__(self, args):\n"
            "        self.args = args\n"
            "\n"
            "    def _instalar(self):\n"
        )
        rabo = (
            "\n"
            "    def _marcar_gestos_de_mentira(self):\n"
            "        return cura_recem_nascida.rearmar_o_gatilho_da_cor()\n"
            "\n\n"
            "def main():\n"
            "    p = argparse.ArgumentParser()\n"
            '    p.add_argument("--prova-gesto", action="store_true")\n'
            "    return Janela(p.parse_args())\n"
        )
        piloto.write_text(
            cabeca
            + "        if self.args.prova_gesto:\n"
            + "            self._marcar_gestos_de_mentira()\n"
            + rabo,
            encoding="utf-8",
        )
        assert pontes_vivas(tmp_path), (
            "o piloto fabricado não virou ponte — o fecho não achou a boca, e "
            "as duas medições abaixo passariam por ausência"
        )
        assert chave in promessas_sem_caminho(copia), (
            "a cura chamada SÓ de dentro de `if self.args.prova_gesto:` foi "
            "dada por ligada. A poda da bancada parou de valer, e a partir "
            "daqui basta uma linha na régua para uma cura desligada ficar "
            "verde — que é exatamente a dívida que este portão existe para ver."
        )
        assert chave not in promessas_sem_caminho(copia, podar_a_bancada=False), (
            "com a ponte INTEIRA a cura continuou acusada — então não é a poda "
            "que a está acusando, e esta mordida não mede a distinção entre "
            "espinha e bancada"
        )

        piloto.write_text(
            cabeca
            + "        self._marcar_gestos_de_mentira()\n"
            + rabo,
            encoding="utf-8",
        )
        assert chave not in promessas_sem_caminho(copia), (
            "tirada a guarda, a chamada passou a ser espinha viva e o portão "
            "continuou acusando — a poda ficou larga demais e agora cobra de "
            "quem está fiado, que é o defeito mais caro que este portão pode ter"
        )
        assert chave not in promessas_sem_caminho(), (
            "a árvore de verdade foi contaminada pela mordida"
        )

    def test_a_corrente_fechada_em_si_mesma_nao_passa_mais(
        self, tmp_path: Path
    ) -> None:
        """DEFEITO (a): ``A`` chama ``B``, ``B`` chama ``A``, e mais ninguém."""
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
        """DEFEITO (b): um nome não é um endereço."""
        copia = _copia_de_src(tmp_path)
        (copia / "daemon" / "orfa_com_nome_comum.py").write_text(
            "class LevantamentoDaMesa:\n"
            '    """A órfã de verdade — ninguém a instancia."""\n'
            "\n"
            "    def valor(self) -> int:\n"
            "        return 0\n",
            encoding="utf-8",
        )
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
        """Citar não é chamar — a mesma linha que separa o P3a inteiro."""
        embutido = "\n".join(trechos_python_embutidos(_RAIZ / "uninstall.sh"))
        assert "kc.strip_quirks_token(tok)" in embutido, (
            "o extrator não achou a chamada dentro do heredoc de "
            "uninstall.sh:1688 — o delimitador ou a linha de abertura mudaram"
        )
        assert "IDs do hefesto (strip_quirks_token do módulo puro)" not in embutido, (
            "o extrator engoliu o COMENTÁRIO de uninstall.sh:1663 junto com o "
            "heredoc — ele está pegando texto demais, e menção viraria prova"
        )

    def test_uma_chave_de_ambiente_inventada_aparece_sem_mao(self) -> None:
        """Se ``portas_que_ligam`` devolvesse algo para qualquer coisa, a"""
        assert not portas_que_ligam("HEFESTO_DUALSENSE4UNIX_CHAVE_QUE_NAO_EXISTE")

    def test_o_que_o_build_deixou_nao_e_porta(self, tmp_path: Path) -> None:
        """Um `.rlib` não liga interruptor nenhum — e reprova nos dois sentidos."""
        env = "HEFESTO_DUALSENSE4UNIX_CHAVE_QUE_NAO_EXISTE"
        applet = tmp_path / "packaging" / "cosmic-applet"
        artefato = applet / "target" / "debug"
        artefato.mkdir(parents=True)
        (artefato / "libhefesto_applet.rlib").write_text(
            f"\x7fELF\x00\x00\n{env}=1\n\x00", encoding="utf-8"
        )
        assert not portas_que_ligam(env, tmp_path), (
            "um artefato sob `target/` foi aceito como porta — o portão passou "
            "a acreditar no que o compilador deixou, e a dívida some sozinha"
        )

        (applet / "hefesto-applet.service").write_text(
            f"[Service]\nEnvironment={env}=1\n", encoding="utf-8"
        )
        assert portas_que_ligam(env, tmp_path) == ["empacotamento"], (
            "a poda cegou o detector para uma porta de VERDADE em "
            "`packaging/` — a exclusão levou junto o que ela devia preservar"
        )

    def test_a_unica_porta_real_da_arvore_sobrevive_a_poda(self) -> None:
        """A poda medida contra a árvore viva, e não contra a plausibilidade."""
        assert portas_que_ligam("HEFESTO_BROKER_ALLOWED_UID") == ["unit"], (
            "a poda de `_PASTAS_DE_ARTEFATO` levou junto a única porta de "
            "verdade da árvore — a exclusão ficou larga demais"
        )

    def test_a_razao_curta_demais_reprova(self) -> None:
        """A guarda das razões, apontada para si mesma."""
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


_LAPIDE_FABRICADA_A = "fabricado/primeiro.py::cura_alfa_que_nunca_existiu"
_LAPIDE_FABRICADA_B = "fabricado/segundo.py::cura_beta_que_nunca_existiu"

_RAZAO_FABRICADA = (
    "razão fabricada só para esta mordida, longa o bastante para passar do "
    "piso de cento e vinte caracteres, com endereço em fabricado/x.py:1, com "
    "o que a fecharia, e com data 25/08/2026."
)


class TestOPortaoNaoEscondeMetadeDoQueVe:
    """As réguas que varrem DOIS registros nomeiam os dois, não só o primeiro."""

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
        """E a guarda das razões: uma queixa em cada registro, as duas na conta."""
        with pytest.raises(AssertionError) as erro:
            _confere_razoes(
                ("_REGISTRO_FABRICADO_A", {_LAPIDE_FABRICADA_A: "porque sim"}),
                ("_REGISTRO_FABRICADO_B", {_LAPIDE_FABRICADA_B: "porque sim"}),
            )

        _os_dois_registros_saem_na_acusacao(str(erro.value), "razão mal escrita")

    def test_a_regua_da_acusacao_dupla_sabe_recusar(self) -> None:
        """O dublê que só sabe passar não é dublê."""
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


