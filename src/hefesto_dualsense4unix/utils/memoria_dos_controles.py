"""A memória dos controles: onde ela mora, e como se guarda e se devolve.

ESQUECER-OS-CONTROLES-01 (25/09/2026). Pedido dela: simular a primeira vez que
uma pessoa conecta os controles, para ver se algo está amarrado à máquina dela
ou a um controle específico — *«meu medo é o programa hoje não estar preparado
como produto»*. E o alcance cresceu no mesmo dia: guardar a casa inteira,
desinstalar, conferir que a máquina está limpa, instalar de novo, testar tudo
e devolver.

ESTE MÓDULO É O DONO DO INVENTÁRIO, e é o único
-----------------------------------------------
O :data:`INVENTARIO` diz cada lugar onde o produto grava algo que identifica um
controle (alcance ``controles``) ou que é da pessoa e tem de atravessar um
uninstall (alcance ``casa``), com o dono no código. Quem move, quem copia, quem
devolve e quem pergunta «a máquina está limpa?» leem DAQUI — o comando da CLI
(``cli/cmd_esquecer.py``), o script da casa inteira
(``scripts/guardar-e-devolver-a-casa.py``) e a régua
(``tests/unit/test_esquecer_os_controles.py``). Uma lista digitada em qualquer
um dos três seria a segunda lista, e a segunda lista envelhece calada.

SÓ BIBLIOTECA PADRÃO, e é estrutural
------------------------------------
Depois do ``uninstall.sh`` o comando do Hefesto não existe mais, e o devolver
tem de rodar assim mesmo: o script da casa carrega ESTE arquivo pelo caminho,
com o ``python3`` do sistema. E a parte do root roda este mesmo arquivo como
script (``sudo -A python3 -I <este arquivo> raiz ...``), sem o pacote no
``sys.path``. Por isso nada aqui importa ``platformdirs`` nem o resto do pacote:
os caminhos XDG são resolvidos pela mesma regra que o ``platformdirs`` usa no
Linux, e a régua confere que as duas respostas são a mesma.

MOVER, NUNCA APAGAR
-------------------
Nada sai do disco. O esquecer MOVE para uma pasta datada; o devolver põe o que
estiver no lugar (o que o teste produziu) numa subpasta ``depois-do-teste`` e só
então devolve a cópia guardada. As duas voltas são reversíveis.

O PAREAMENTO NO BLUEZ, medido contra o ``RemoveDevice``
-------------------------------------------------------
O ``RemoveDevice`` do BlueZ apaga a pasta do aparelho (e tira os registros SDP do
cache): não tem volta. Mover a pasta com o ``bluetoothd`` parado tem volta DO
LADO DA MÁQUINA — e só dela. O controle guarda UMA chave de pareamento: se ele
for pareado de novo (nesta máquina, em outro adaptador, num console) ou
resetado pelo botão de trás, a chave antiga morreu nele, e devolver a pasta
antiga seria plantar uma chave que o controle recusa (o laço de autenticação que
o ``bt_bonds_autorestore.sh`` descreve). Por isso o devolver do BlueZ NÃO põe a
pasta antiga por cima de um pareamento vivo do mesmo controle, em adaptador
nenhum: o pareamento vivo é o que o controle conhece.

O ``bluetoothd`` é parado pelo MESMO roteiro do ``bt_bonds_restore.sh`` (máscara
de execução, parada irreversível, espera, e na volta o agente de pareamento
religado com ``reset-failed`` — a AGENTE-QUE-NAO-VOLTA-01 custou oito horas).
Uma parada limpa não dispara o ``bt_bonds_autorestore.sh`` (ele só age na
MORTE), e o acervo de cópias do Hefesto sai JUNTO com os pareamentos, depois
deles: nenhum instantâneo de antes do esquecer sobra para ressuscitar o que foi
esquecido.
"""
from __future__ import annotations

import configparser
import contextlib
import hashlib
import importlib
import importlib.util
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

# ══ 0. A identidade do app, do dono ═════════════════════════════════════════
#
# «O nome do app não se digita» (``utils/identidade.py``). Como pacote, o import
# normal; como script avulso (a parte do root, o script da casa), o irmão pelo
# caminho — ele é só biblioteca padrão.


def _carregar_irmao(nome: str, arquivo: Path) -> ModuleType:
    """Carrega um módulo stdlib pelo caminho, sem o pacote no ``sys.path``."""
    ja = sys.modules.get(nome)
    if ja is not None:
        return ja
    spec = importlib.util.spec_from_file_location(nome, arquivo)
    if spec is None or spec.loader is None:  # pragma: no cover - caminho quebrado
        raise ImportError(f"não consegui carregar {arquivo}")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


try:
    from hefesto_dualsense4unix.utils import identidade as _identidade
except ImportError:  # script avulso: python3 -I <este arquivo>
    _identidade = _carregar_irmao(
        "_hefesto_identidade", Path(__file__).with_name("identidade.py")
    )

_ID = _identidade.atual()
SLUG: str = _ID.slug
UNIT_DO_DAEMON: str = _ID.unit_daemon

#: A pasta do root que o install cria (``scripts/install_udev.sh``) e onde moram
#: o acervo de cópias de pareamento e o diário do root.
VARLIB_DO_PRODUTO = Path("/var/lib") / SLUG

#: O armazenamento do BlueZ.
BLUEZ_REAL = Path("/var/lib/bluetooth")

#: Onde a parte do root guarda — AO LADO do original, fora da pasta do produto:
#: o ``uninstall.sh --purge-config`` apaga ``/var/lib/<slug>`` e não pode levar a
#: cópia junto. Árvore 700, porque leva chave de pareamento.
GUARDADO_DO_ROOT_REAL = Path("/var/lib/hefesto-memoria-guardada")

#: O nome da pasta do lado dela, dentro do ``XDG_STATE_HOME``. Fora da pasta do
#: produto pelo mesmo motivo: o uninstall não a vê, e o «limpa?» não a confunde
#: com rastro.
NOME_DO_GUARDADO = "hefesto-memoria-guardada"

#: Os dois alcances.
CONTROLES = "controles"
CASA = "casa"
ALCANCES = (CONTROLES, CASA)

#: De quem é o lugar.
USUARIO = "pessoa"
ROOT = "root"

#: O que se faz com cada lugar ao guardar.
MOVER = "mover"
COPIAR = "copiar"
TIRAR_A_CHAVE = "tirar-a-chave-dos-perfis"
PAREAMENTOS = "pareamentos-do-bluez"

#: Forma do manifesto (sobe quando o formato mudar de um jeito que o devolver
#: precise saber).
FORMA_DO_MANIFESTO = 1

#: A chave dos ajustes por controle no perfil — ``profiles/schema.py``
#: (``Profile.controllers``), um mapa MAC → ajustes.
CHAVE_DOS_AJUSTES_POR_CONTROLE = "controllers"

#: Endereço como o BlueZ grava no disco (maiúsculas, com dois-pontos).
_FORMA_DO_MAC = re.compile(r"^[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}$")

#: O nome de uma pasta guardada: ``AAAAMMDD-HHMMSS-<alcance>``.
_FORMA_DA_PASTA = re.compile(r"^\d{8}-\d{6}-(?:controles|casa)$")

#: As variáveis que o produto exporta para os jogos — espelho de
#: ``daemon/launch_env.ENV_ALLOWLIST`` (a régua confere que são iguais). É por
#: elas que o «limpa?» reconhece o rastro do Hefesto no ``config.json`` do Heroic
#: e nos ``overrides`` do Flatpak, que o ``uninstall.sh`` não visita.
VARIAVEIS_DO_PRODUTO: tuple[str, ...] = (
    "SDL_GAMECONTROLLER_IGNORE_DEVICES",
    "SDL_JOYSTICK_HIDAPI",
    "SDL_GAMECONTROLLER_USE_BUTTON_LABELS",
    "PROTON_DISABLE_HIDRAW",
    "__GL_SHADER_DISK_CACHE",
    "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP",
    "SDL_ACCELEROMETER_AS_JOYSTICK",
    "PROTON_KEEP_SONY_AUDIO_ENDPOINT_VISIBLE",
    "PROTON_ENABLE_MHWILDS_USB_AUDIO",
)

#: As duas que uma pessoa costuma pôr sozinha (cache de shader da NVIDIA): no
#: «limpa?» elas contam como «pode ser sua», e não como rastro certo.
_VARIAVEIS_QUE_PODEM_SER_DELA = frozenset(
    {"__GL_SHADER_DISK_CACHE", "__GL_SHADER_DISK_CACHE_SKIP_CLEANUP"}
)

#: As pastas do Heroic — espelho de ``integrations/camadas_vulkan._CONFIG_DO_HEROIC``
#: e de ``integrations/cura_por_estrada._pasta_do_heroic`` (a régua confere).
PASTAS_DO_HEROIC: tuple[str, ...] = (
    ".var/app/com.heroicgameslauncher.hgl/config/heroic",
    ".config/heroic",
)

#: Onde o Hefesto escreve o ambiente do Flatpak de cada lançador — espelho de
#: ``integrations/cura_por_estrada.estradas_do_cartao`` e de
#: ``integrations/sandbox_dos_lancadores._raizes`` (a régua confere): o lar, e
#: não o ``XDG_DATA_HOME``, porque é assim que os dois donos escrevem e leem.
PASTA_DOS_OVERRIDES = ".local/share/flatpak/overrides"

#: Os ids de Flatpak do próprio Hefesto — os mesmos que o ``uninstall.sh``
#: desinstala (``HEFESTO_FLATPAK_APP_IDS``): o de hoje e o de antes de 25/08.
IDS_DE_FLATPAK_DO_HEFESTO: tuple[str, ...] = (
    "io.github.hefesto_team.hefesto_dualsense4unix",
    "br.andrefarias.Hefesto",
)

#: A marca que o produto grava nos prefixos Wine (``audio_ks_dualsense``).
MARCA_DO_DEVICE_KS = "HEFESTOKS"

#: A variável da guarda de ensaio: com ela, qualquer caminho que resolva para o
#: lar ou para o ``/var/lib`` de verdade faz o comando RECUSAR antes de tocar em
#: qualquer coisa.
ENV_ENSAIO = "HEFESTO_MEMORIA_ENSAIO"


# ══ 1. As raízes ═══════════════════════════════════════════════════════════


class RecusaError(RuntimeError):
    """O comando se recusou a seguir — a mensagem diz por quê e o que fazer."""


@dataclass(frozen=True)
class Raizes:
    """Onde cada coisa mora nesta máquina (ou no lar de mentira da régua)."""

    lar: Path
    config: Path
    estado: Path
    dados: Path
    cache: Path
    execucao: Path
    bluez: Path
    varlib: Path
    guardado_do_root: Path
    sistema: Path
    #: O repositório do produto, quando este arquivo roda de dentro dele — é de
    #: lá que o «limpa?» lê a lista de regras udev (``assets/``).
    repositorio: Path | None = None

    @property
    def guardado(self) -> Path:
        return self.estado / NOME_DO_GUARDADO

    @property
    def raizes_do_root_sao_as_reais(self) -> bool:
        return (
            self.bluez == BLUEZ_REAL
            and self.varlib == VARLIB_DO_PRODUTO
            and self.guardado_do_root == GUARDADO_DO_ROOT_REAL
        )

    @property
    def raizes_do_root_desviadas(self) -> bool:
        return (
            self.bluez != BLUEZ_REAL
            and self.varlib != VARLIB_DO_PRODUTO
            and self.guardado_do_root != GUARDADO_DO_ROOT_REAL
        )

    @classmethod
    def do_ambiente(cls, env: dict[str, str] | None = None) -> Raizes:
        """As raízes pela regra XDG (a do ``platformdirs`` no Linux).

        Os desvios do lado do root (``HEFESTO_MEMORIA_BLUEZ``,
        ``HEFESTO_MEMORIA_VARLIB``, ``HEFESTO_MEMORIA_GUARDADO_ROOT``,
        ``HEFESTO_MEMORIA_SISTEMA``) são ganchos de ensaio: sob root eles morrem
        (:func:`raizes_do_root`).
        """
        e = dict(os.environ if env is None else env)
        lar = Path(e.get("HOME") or pwd.getpwuid(os.getuid()).pw_dir)

        def _xdg(nome: str, padrao: Path) -> Path:
            valor = e.get(nome, "").strip()
            return Path(valor) if valor and os.path.isabs(valor) else padrao

        uid = os.getuid()
        execucao = _xdg("XDG_RUNTIME_DIR", Path(f"/run/user/{uid}"))
        repo = Path(__file__).resolve().parents[3]
        return cls(
            lar=lar,
            config=_xdg("XDG_CONFIG_HOME", lar / ".config"),
            estado=_xdg("XDG_STATE_HOME", lar / ".local/state"),
            dados=_xdg("XDG_DATA_HOME", lar / ".local/share"),
            cache=_xdg("XDG_CACHE_HOME", lar / ".cache"),
            execucao=execucao,
            bluez=Path(e.get("HEFESTO_MEMORIA_BLUEZ") or BLUEZ_REAL),
            varlib=Path(e.get("HEFESTO_MEMORIA_VARLIB") or VARLIB_DO_PRODUTO),
            guardado_do_root=Path(
                e.get("HEFESTO_MEMORIA_GUARDADO_ROOT") or GUARDADO_DO_ROOT_REAL
            ),
            sistema=Path(e.get("HEFESTO_MEMORIA_SISTEMA") or "/"),
            repositorio=repo if (repo / "assets").is_dir() else None,
        )

    def em_texto(self) -> dict[str, str]:
        return {k: str(v) for k, v in asdict(self).items() if v is not None}


def conferir_o_ensaio(raizes: Raizes, env: dict[str, str] | None = None) -> None:
    """Com ``HEFESTO_MEMORIA_ENSAIO=1``, recusa qualquer raiz de verdade.

    É a guarda que sai da régua: um lar de mentira que esquecesse de desviar UMA
    raiz escreveria no disco dela. Sem a variável, não faz nada — o comando de
    verdade aponta para as raízes de verdade, que é o trabalho dele.
    """
    e = os.environ if env is None else env
    if e.get(ENV_ENSAIO) != "1":
        return
    lar_real = Path(pwd.getpwuid(os.getuid()).pw_dir)
    proibidos = [lar_real / ".config", lar_real / ".local", lar_real / ".cache",
                 lar_real / ".steam", lar_real / ".var"]
    if raizes.lar == lar_real:
        raise RecusaError(f"ensaio com o lar de verdade ({lar_real}) — recusado")
    for nome in ("config", "estado", "dados", "cache"):
        caminho: Path = getattr(raizes, nome)
        for proibido in proibidos:
            if caminho == proibido or proibido in caminho.parents:
                raise RecusaError(f"ensaio: {nome} aponta para {caminho} — recusado")
    if not raizes.raizes_do_root_desviadas:
        raise RecusaError("ensaio: as raízes do root não estão TODAS desviadas — recusado")
    if raizes.sistema == Path("/"):
        raise RecusaError("ensaio: a raiz do sistema é a de verdade — recusado")


# ══ 2. O inventário ════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Lugar:
    """Um lugar do inventário.

    ``raiz`` é o nome de um campo de :class:`Raizes` (``config``, ``estado``,
    ``bluez``, ``varlib``, ``lar``); ``caminho`` é relativo a ela e pode ter
    curinga (``*``). ``dono`` é o endereço do código que grava ali.
    """

    chave: str
    raiz: str
    caminho: str
    dono: str
    de_quem: str
    alcance: str
    ato: str
    guarda: str
    #: No devolver da casa inteira: ``True`` = volta; ``False`` = fica só na
    #: pasta (o install ou o daemon o recriam, e devolver por cima dessincroniza
    #: o registro que o próximo uninstall lê).
    devolve: bool = True


_C = SLUG  # a pasta do app dentro de config/estado/dados/cache

#: TODO lugar que o produto grava e que importa aqui, com o dono. A ordem é a
#: ordem em que o comando os percorre.
INVENTARIO: tuple[Lugar, ...] = (
    # ── alcance CONTROLES, lado dela ──────────────────────────────────────
    Lugar(
        "fila-dos-numeros", "config", f"{_C}/controllers.json",
        "daemon/subsystems/identity.py:_CONTROLLERS_FILE e "
        "daemon/subsystems/external_identity.py:_CONTROLLERS_FILE",
        USUARIO, CONTROLES, MOVER,
        "a fila de números (quem é P1..P4) por endereço, DualSense e externos",
    ),
    Lugar(
        "mascaras-por-aparelho", "config", f"{_C}/controller_masks.json",
        "daemon/subsystems/external_mask.py:_MASKS_FILE",
        USUARIO, CONTROLES, MOVER,
        "a máscara escolhida para cada controle externo, por endereço",
    ),
    Lugar(
        "declaracao-da-mesa", "config", f"{_C}/maquina.json",
        "utils/maquina.py:_MAQUINA_FILE",
        USUARIO, CONTROLES, MOVER,
        "o que ela declarou: a cor e a chave de cada controle (por endereço), "
        "os nomes das portas, os rádios vizinhos, a antena",
    ),
    Lugar(
        "declaracao-recusada", "config", f"{_C}/maquina.json.invalido",
        "utils/maquina.py:_MAQUINA_INVALIDO_SUFIXO",
        USUARIO, CONTROLES, MOVER,
        "os bytes do maquina.json que o esquema recusou",
    ),
    Lugar(
        "ajustes-por-controle", "config", f"{_C}/profiles/*.json",
        "profiles/schema.py:Profile.controllers",
        USUARIO, CONTROLES, TIRAR_A_CHAVE,
        "os ajustes por controle dentro de cada perfil (chave = endereço); "
        "o resto do perfil fica",
    ),
    Lugar(
        "ajustes-por-controle-dos-estilos", "config",
        f"{_C}/profiles/estilos-de-jogo/*.json",
        "profiles/loader.py:ESTILOS_DE_JOGO_DIR_NAME",
        USUARIO, CONTROLES, TIRAR_A_CHAVE,
        "os mesmos ajustes nos estilos de jogo guardados",
    ),
    Lugar(
        "versoes-antigas-dos-perfis", "config", f"{_C}/profiles/.historico",
        "profiles/loader.py:HISTORICO_DIR_NAME",
        USUARIO, CONTROLES, MOVER,
        "as dez últimas versões de cada perfil, com os ajustes por controle dentro",
    ),
    Lugar(
        "lugares-dos-adaptadores", "estado", f"{_C}/lugares-dos-adaptadores.json",
        "integrations/bluez_dbus.py:_memoria_dos_lugares",
        USUARIO, CONTROLES, MOVER,
        "em qual porta USB cada adaptador Bluetooth estava",
    ),
    Lugar(
        "conexao-zumbi", "estado", f"{_C}/conexao-zumbi.json",
        "daemon/subsystems/conexoes.py:caminho_do_diario",
        USUARIO, CONTROLES, MOVER,
        "a última volta do vigia de conexões, com o endereço de cada link",
    ),
    Lugar(
        "diario-do-radio", "estado", f"{_C}/radio-diario*.jsonl*",
        "integrations/diario_do_radio.py:NOME_DO_DIARIO",
        USUARIO, CONTROLES, MOVER,
        "o diário do rádio (endereços de controle e de adaptador), com o "
        "girado (.1) e os que um uninstall anterior guardou",
    ),
    # ── alcance CONTROLES, lado do root ───────────────────────────────────
    Lugar(
        "pareamentos-dos-controles", "bluez", "<adaptador>/<controle>",
        "bluetoothd (BlueZ); lido por integrations/bluez_dbus.py",
        ROOT, CONTROLES, PAREAMENTOS,
        "o pareamento de cada controle (a chave) e o cache SDP dele, em cada "
        "adaptador. Só aparelho com classe de controle — fone e mouse ficam",
    ),
    Lugar(
        "copias-de-pareamento", "varlib", "bt-bonds",
        "scripts/bt_bonds_snapshot.sh:DST_ROOT",
        ROOT, CONTROLES, MOVER,
        "as cópias de pareamento que o Hefesto tira (com as chaves) e as lápides",
    ),
    Lugar(
        "copias-de-pareamento-de-uninstall", "varlib", "bt-bonds.pre-uninstall-*",
        "uninstall.sh (o acervo preservado sem --purge-config)",
        ROOT, CONTROLES, MOVER,
        "as cópias de pareamento que um uninstall anterior guardou (com as chaves)",
    ),
    Lugar(
        "diario-do-root", "varlib", "radio-diario.jsonl*",
        "integrations/diario_do_radio.py:DIARIO_DO_ROOT",
        ROOT, CONTROLES, MOVER,
        "o diário dos motores root do rádio",
    ),
    # ── alcance CASA: a pessoa e os lançadores (copiados; o uninstall remove) ─
    Lugar(
        "configuracao-inteira", "config", _C,
        "utils/xdg_paths.py:config_dir",
        USUARIO, CASA, COPIAR,
        "perfis, jogos, máscaras, listas, preferências, o maquina.json — tudo",
    ),
    Lugar(
        "configuracao-antiga", "config", "hefesto",
        "utils/migrate_legacy_paths.py",
        USUARIO, CASA, COPIAR,
        "a pasta de antes do nome longo (versões antigas gravavam perfis ali)",
    ),
    Lugar(
        "configuracao-do-flatpak", "lar", f".var/app/*/config/{_C}",
        "uninstall.sh:HEFESTO_FLATPAK_APP_IDS",
        USUARIO, CASA, COPIAR,
        "a configuração de quem instalou pelo Flatpak",
    ),
    Lugar(
        "camadas-vulkan", "estado", f"{_C}/camadas-vulkan.json",
        "integrations/camadas_vulkan.py:ESTADO_BASENAME",
        USUARIO, CASA, COPIAR,
        "o que o produto desligou nos prefixos, e o que ela mandou manter",
        devolve=False,
    ),
    Lugar(
        "historico-do-kernel", "estado", f"{_C}/kernel*",
        "integrations/storm_doctor.py:caminho_do_kernel_log",
        USUARIO, CASA, COPIAR,
        "o kernel.log da vigia e a marca do boot (histórico)",
        devolve=False,
    ),
    Lugar(
        "steam-opcoes-e-entrada", "lar", "<steam>/userdata/*/config/localconfig.vdf",
        "integrations/steam_launch_options.py:discover_vdfs",
        USUARIO, CASA, COPIAR,
        "as Opções de Inicialização (o atalho hefesto-launch) e o Steam Input",
    ),
    Lugar(
        "steam-proton-pinado", "lar", "<steam>/config/config.vdf",
        "integrations/proton_pin.py:default_config_vdf",
        USUARIO, CASA, COPIAR,
        "o CompatToolMapping (o Proton pinado por jogo)",
    ),
    Lugar(
        "heroic-ambiente", "lar", "<heroic>/config.json",
        "integrations/cura_por_estrada.py:_escrever_no_heroic",
        USUARIO, CASA, COPIAR,
        "o ambiente que o Hefesto põe em todo jogo do Heroic "
        "(defaultSettings.enviromentOptions)",
    ),
    Lugar(
        "flatpak-ambiente", "lar", f"{PASTA_DOS_OVERRIDES}/*",
        "integrations/cura_por_estrada.py:_escrever_no_override",
        USUARIO, CASA, COPIAR,
        "o [Environment] que o Hefesto põe no Flatpak de cada lançador "
        "(Lutris, RetroArch, Dolphin, mGBA)",
    ),
)


def lugares(alcance: str, de_quem: str | None = None) -> tuple[Lugar, ...]:
    """Os lugares de um alcance. A casa inteira INCLUI o alcance dos controles."""
    if alcance not in ALCANCES:
        raise ValueError(f"alcance desconhecido: {alcance!r}")
    escolhidos = [
        lg for lg in INVENTARIO
        if lg.alcance == alcance or (alcance == CASA and lg.alcance == CONTROLES)
    ]
    if de_quem is not None:
        escolhidos = [lg for lg in escolhidos if lg.de_quem == de_quem]
    return tuple(escolhidos)


#: O que o produto grava no lar e NÃO é memória de controle — cada nome que a
#: régua acha no código tem de estar aqui ou no inventário, com a razão. É o que
#: impede um arquivo novo de nascer fora do comando sem ninguém decidir.
#: ``casa``: da pessoa, vai na pasta da casa inteira (dentro da configuração).
#: ``install``: o install ou o daemon recriam; não se guarda.
#: ``fora``: não é arquivo do lar dela (dado do pacote, arquivo de terceiro só
#: lido, nome de exemplo).
CLASSIFICACAO: dict[str, tuple[str, str]] = {
    # memória dos controles — o inventário acima
    "controllers.json": (CONTROLES, "fila-dos-numeros"),
    "controller_masks.json": (CONTROLES, "mascaras-por-aparelho"),
    "maquina.json": (CONTROLES, "declaracao-da-mesa"),
    "lugares-dos-adaptadores.json": (CONTROLES, "lugares-dos-adaptadores"),
    "conexao-zumbi.json": (CONTROLES, "conexao-zumbi"),
    "radio-diario.jsonl": (CONTROLES, "diario-do-radio"),
    "profiles": (CONTROLES, "ajustes-por-controle (a chave controllers de cada perfil)"),
    # da pessoa, sem endereço de controle: vão na configuração inteira
    "session.json": (CASA, "o nome do último perfil ativado; não identifica controle"),
    "active_profile.txt": (CASA, "o marcador do perfil ativo; não identifica controle"),
    "paused.flag": (CASA, "o daemon pausado"),
    "autoswitch_locked.flag": (CASA, "a troca automática travada"),
    "native_mode.flag": (CASA, "o modo nativo"),
    "mouse_emulation.flag": (CASA, "a emulação de mouse"),
    "keyboard_emulation.flag": (CASA, "a emulação de teclado"),
    "gamepad_emulation.flag": (CASA, "a emulação de gamepad"),
    "gamepad_disabled.flag": (CASA, "a emulação de gamepad desligada"),
    "gamepad_caminho.flag": (CASA, "o caminho do gamepad"),
    "coop_disabled.flag": (CASA, "o co-op desligado"),
    "coop_enabled.flag": (CASA, "o co-op ligado (legado)"),
    "DESLIGADO-pela-chave.flag": (CASA, "a chave geral do produto"),
    "gui_preferences.json": (CASA, "as preferências da janela"),
    "launch_dialog_dismissed.json": (CASA, "o aviso do atalho já dispensado"),
    "hefesto-dualsense4unix/jogos_fora_do_pino.txt": (CASA, "os jogos fora do Proton pinado"),
    "hefesto-dualsense4unix/jogos_sem_wrapper.txt": (CASA, "os jogos sem o atalho"),
    "hefesto-dualsense4unix/lista_de_exclusao.json": (CASA, "a lista de exclusão"),
    "hefesto-dualsense4unix/opcoes_por_jogo.txt": (CASA, "as opções por jogo dela"),
    "hefesto-dualsense4unix/steam_input_apps.txt": (CASA, "os jogos com o Steam Input"),
    "freestyle.json": (CASA, "um perfil semeado"),
    "meu_perfil.json": (CASA, "um perfil semeado"),
    "personalizado.json": (CASA, "um perfil semeado"),
    "camadas-vulkan.json": (CASA, "camadas-vulkan: guardado, não devolvido"),
    "kernel.log": (CASA, "historico-do-kernel: guardado, não devolvido"),
    # recriados pelo install ou pelo daemon
    "gabinete.json": ("install", "o censo do gabinete: o install o grava lendo o SMBIOS"),
    "proton-pin-lock.json": ("install", "o registro do pino: o install novo grava o dele"),
    "wrapper-visto.json": ("install", "o registro da sentinela do atalho"),
    "launch_env": ("install", "o ambiente que o daemon materializa a cada transição"),
    "teclado-na-tela.json": ("install", "a sessão do teclado na tela (pasta de execução)"),
    "daemon.pid": ("install", "o pid do daemon (pasta de execução)"),
    "radio.lock": ("install", "a trava do rádio (pasta de execução)"),
    "cosmic_tray_warned.flag": ("install", "o aviso da bandeja (pasta de execução)"),
    "runtime": ("install", "a pasta de execução de reserva"),
    "51-hefesto-dualsense-no-default-source.conf": ("install", "drop-in do WirePlumber"),
    "54-hefesto-dualsense-alto-falante-nunca-dorme.conf": ("install", "drop-in do WirePlumber"),
    ".hefesto-proton-pin.json": ("install", "o manifesto do Proton que o install extrai"),
    # não são arquivos do lar dela
    "winevulkan.json": ("fora", "o driver Vulkan do Wine, lido no prefixo"),
    "PROVA-DA-FOTO.txt": ("fora", "saída da bancada de fotos (olhar.py)"),
}


# ══ 3. Pareamentos do BlueZ ════════════════════════════════════════════════


def _ler_ini(texto: str) -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str  # type: ignore[assignment,method-assign]
    with contextlib.suppress(configparser.Error):
        cp.read_string(texto)
    return cp


def e_controle_pelo_info(texto: str) -> bool:
    """O ``info`` de um aparelho do BlueZ descreve um controle de jogo?

    Pela CLASSE do aparelho (Bluetooth clássico): classe maior 0x05 (periférico),
    sem os bits de teclado/apontador, e subclasse joystick (1) ou gamepad (2) —
    é a mesma conta com que o BlueZ escolhe o ícone ``input-gaming``. O DualSense,
    o DualShock 4, o Pro Controller e o 8BitDo respondem ``0x002508``. Pela
    APARÊNCIA (só LE): ``0x03C3`` joystick e ``0x03C4`` gamepad.

    Nenhum modelo, fabricante ou endereço entra na conta: um controle que o
    produto nunca viu é reconhecido pela classe que ele mesmo anuncia.
    """
    cp = _ler_ini(texto)
    classe = cp.get("General", "Class", fallback="").strip()
    if classe:
        try:
            c = int(classe, 0)
        except ValueError:
            c = -1
        if c >= 0:
            maior = (c >> 8) & 0x1F
            sub = (c >> 2) & 0x0F
            if maior == 0x05 and (c & 0xC0) == 0 and sub in (0x01, 0x02):
                return True
    aparencia = cp.get("General", "Appearance", fallback="").strip()
    if aparencia:
        try:
            if int(aparencia, 0) in (0x03C3, 0x03C4):
                return True
        except ValueError:
            pass
    return False


def _tem_chave(pasta: Path) -> bool:
    """A pasta é um pareamento VIVO — tem ``info`` com chave? (a pergunta do
    ``_bond_com_chave`` da ponte privilegiada)."""
    info = pasta / "info"
    if not info.is_file() or info.is_symlink():
        return False
    try:
        texto = info.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    return bool(re.search(r"^\[(LinkKey|LongTermKey)\]", texto, re.M))


@dataclass(frozen=True)
class Pareamento:
    adaptador: str
    controle: str


def pareamentos_de_controle(bluez: Path) -> list[Pareamento]:
    """Todos os pareamentos de controle no armazenamento do BlueZ."""
    achados: list[Pareamento] = []
    if not bluez.is_dir():
        return achados
    for adaptador in sorted(bluez.iterdir()):
        if not _FORMA_DO_MAC.match(adaptador.name) or adaptador.is_symlink():
            continue
        if not adaptador.is_dir():
            continue
        for aparelho in sorted(adaptador.iterdir()):
            if not _FORMA_DO_MAC.match(aparelho.name) or aparelho.is_symlink():
                continue
            info = aparelho / "info"
            if not info.is_file() or info.is_symlink():
                continue
            try:
                texto = info.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if e_controle_pelo_info(texto):
                achados.append(Pareamento(adaptador.name, aparelho.name))
    return achados


# ══ 4. Mover, copiar e conferir ════════════════════════════════════════════


def sha256_de(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 16), b""):
            h.update(bloco)
    return h.hexdigest()


def retrato(caminho: Path) -> dict[str, str]:
    """``{relativo: sha256}`` de cada arquivo (e ``->alvo`` de cada link).

    É o que o manifesto guarda e o que a régua compara: devolver «exatamente
    como estava» se mede aqui, arquivo por arquivo.
    """
    saida: dict[str, str] = {}
    if caminho.is_symlink():
        return {".": "->" + os.readlink(caminho)}
    if caminho.is_file():
        return {".": sha256_de(caminho)}
    if not caminho.is_dir():
        return saida
    for raiz, pastas, arquivos in os.walk(caminho):
        pastas.sort()
        base = Path(raiz)
        for nome in sorted(arquivos) + [p for p in pastas if (base / p).is_symlink()]:
            alvo = base / nome
            rel = str(alvo.relative_to(caminho))
            if alvo.is_symlink():
                saida[rel] = "->" + os.readlink(alvo)
            elif alvo.is_file():
                saida[rel] = sha256_de(alvo)
    return saida


def _copiar_stat(origem: Path, destino: Path) -> None:
    """Modo, datas e — sob root — o dono."""
    st = origem.lstat()
    with contextlib.suppress(OSError):
        os.utime(destino, ns=(st.st_atime_ns, st.st_mtime_ns), follow_symlinks=False)
    if not destino.is_symlink():
        with contextlib.suppress(OSError):
            os.chmod(destino, st.st_mode & 0o7777)
    if os.geteuid() == 0:
        with contextlib.suppress(OSError):
            os.lchown(destino, st.st_uid, st.st_gid)


def copiar(origem: Path, destino: Path) -> None:
    """Cópia fiel (links como links, modo, datas; sob root, o dono)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if origem.is_symlink():
        os.symlink(os.readlink(origem), destino)
        return
    if origem.is_dir():
        shutil.copytree(origem, destino, symlinks=True, copy_function=shutil.copy2)
        if os.geteuid() == 0:
            for raiz, pastas, arquivos in os.walk(origem):
                for nome in pastas + arquivos:
                    o = Path(raiz) / nome
                    _copiar_stat(o, destino / o.relative_to(origem))
        _copiar_stat(origem, destino)
        return
    shutil.copy2(origem, destino, follow_symlinks=False)
    _copiar_stat(origem, destino)


def mover(origem: Path, destino: Path) -> None:
    """Move sem apagar nada antes de a cópia estar conferida.

    No mesmo disco é um ``rename`` (atômico, preserva tudo). Entre discos: copia,
    confere o retrato e só então remove a origem.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() or destino.is_symlink():
        raise RecusaError(f"o destino já existe, não sobrescrevo: {destino}")
    try:
        os.rename(origem, destino)
        return
    except OSError as erro:
        if erro.errno != 18:  # EXDEV: outro disco
            raise
    antes = retrato(origem)
    copiar(origem, destino)
    if retrato(destino) != antes:
        raise RecusaError(f"a cópia de {origem} não confere — a origem ficou onde estava")
    if origem.is_dir() and not origem.is_symlink():
        shutil.rmtree(origem)
    else:
        origem.unlink()


def _preparar_pasta(pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    with contextlib.suppress(OSError):
        os.chmod(pasta, 0o700)


# ══ 5. O manifesto ═════════════════════════════════════════════════════════


@dataclass
class Item:
    """Uma coisa guardada: de onde veio, onde está na pasta, e o retrato."""

    chave: str
    origem: str
    guardado: str
    como: str
    de_quem: str
    devolve: bool = True
    retrato: dict[str, str] = field(default_factory=dict)
    nota: str = ""


@dataclass
class Manifesto:
    alcance: str
    carimbo: str
    raizes: dict[str, str]
    itens: list[Item] = field(default_factory=list)
    root: str = ""
    devolvido_em: list[str] = field(default_factory=list)
    forma: int = FORMA_DO_MANIFESTO
    #: Os lugares do inventário que NÃO existiam no guardar (``origem``). O que
    #: o teste criar ali sai no devolver — «exatamente como estava» inclui o
    #: que não estava.
    ausentes: list[str] = field(default_factory=list)
    #: Os curingas do inventário (``{"base", "padrao", "existiam"}``): no
    #: devolver, o que casa com eles e NÃO existia no guardar nasceu no teste, e
    #: sai também. A lista do que existia é a do guardar, e não a dos itens: uma
    #: guarda que caiu no meio não pode fazer o devolver tirar o que nunca saiu.
    curingas: list[dict[str, Any]] = field(default_factory=list)

    def gravar(self, pasta: Path) -> None:
        alvo = pasta / "manifesto.json"
        tmp = alvo.with_name(alvo.name + ".novo")
        texto = json.dumps(asdict(self), ensure_ascii=False, indent=2) + "\n"
        tmp.write_text(texto, encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, alvo)

    @classmethod
    def ler(cls, pasta: Path) -> Manifesto:
        try:
            dado = json.loads((pasta / "manifesto.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as erro:
            raise RecusaError(f"a pasta {pasta} não tem um manifesto legível ({erro})") from erro
        if not isinstance(dado, dict) or dado.get("forma") != FORMA_DO_MANIFESTO:
            raise RecusaError(f"o manifesto de {pasta} é de outra forma — não mexo")
        itens = [Item(**i) for i in dado.get("itens", [])]
        return cls(
            alcance=str(dado["alcance"]),
            carimbo=str(dado["carimbo"]),
            raizes=dict(dado.get("raizes", {})),
            itens=itens,
            root=str(dado.get("root", "")),
            devolvido_em=list(dado.get("devolvido_em", [])),
            ausentes=[str(a) for a in dado.get("ausentes", [])],
            curingas=[dict(c) for c in dado.get("curingas", []) if isinstance(c, dict)],
        )


def carimbo_agora(agora: float | None = None) -> str:
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(agora))


def pastas_guardadas(raizes: Raizes) -> list[Path]:
    """As pastas guardadas, da mais velha para a mais nova."""
    if not raizes.guardado.is_dir():
        return []
    return sorted(
        p for p in raizes.guardado.iterdir()
        if p.is_dir() and _FORMA_DA_PASTA.match(p.name)
        and (p / "manifesto.json").is_file()
    )


def escolher_pasta(raizes: Raizes, pedida: str | None) -> Path:
    """A pasta pedida (nome ou caminho), ou a mais nova."""
    if pedida:
        candidata = Path(pedida)
        if not candidata.is_absolute():
            candidata = raizes.guardado / pedida
        if not (candidata / "manifesto.json").is_file():
            raise RecusaError(f"não há pasta guardada em {candidata}")
        return candidata
    todas = pastas_guardadas(raizes)
    if not todas:
        raise RecusaError(f"nenhuma pasta guardada em {raizes.guardado}")
    return todas[-1]


# ══ 6. O sistema: daemon, Steam, root ══════════════════════════════════════


class Sistema:
    """O que o comando pede à máquina. A régua troca por um de mentira.

    Nenhum método pede senha no terminal: a parte do root passa por
    ``sudo -A`` quando há ``SUDO_ASKPASS`` (o caminho do install) e por
    ``sudo -n`` quando não há — e sem nenhum dos dois ela RECUSA antes de tocar
    em qualquer coisa, dizendo o que fazer.
    """

    #: No ensaio (a régua, o lar de mentira) o sistema é INERTE: o daemon e a
    #: Steam por que ele perguntaria são os DELA, não os do lar de mentira —
    #: parar o daemon dela no meio de uma régua é o estrago que esta guarda
    #: existe para impedir.
    @property
    def ensaio(self) -> bool:
        return os.environ.get(ENV_ENSAIO) == "1"

    def _systemctl_do_usuario(self, *args: str) -> int:
        if self.ensaio:
            return 3
        try:
            r = subprocess.run(["systemctl", "--user", *args], check=False,
                               capture_output=True)
        except OSError:
            return 127
        return r.returncode

    def daemon_ativo(self) -> bool:
        return self._systemctl_do_usuario("is-active", "--quiet", UNIT_DO_DAEMON) == 0

    def parar_daemon(self) -> None:
        self._systemctl_do_usuario("stop", UNIT_DO_DAEMON)

    def subir_daemon(self) -> None:
        self._systemctl_do_usuario("start", UNIT_DO_DAEMON)

    def steam_aberta(self) -> bool:
        if self.ensaio:
            return False
        mod = _modulo_de_integracao("steam_launch_options")
        if mod is None:
            return False
        return bool(mod.steam_running())

    def rodar_parte_do_root(
        self, raizes: Raizes, verbo: str, pasta_root: Path | None, seco: bool
    ) -> dict[str, Any]:
        """Roda a parte do root; devolve o que ela relatou."""
        if raizes.raizes_do_root_desviadas:
            return executar_parte_do_root(raizes, verbo, pasta_root, seco=seco)
        if not raizes.raizes_do_root_sao_as_reais:
            raise RecusaError("as raízes do root estão meio desviadas — recuso misturar")
        argv = [
            sys.executable if os.path.isabs(sys.executable) else "/usr/bin/python3",
            "-I", str(Path(__file__).resolve()), "raiz", verbo,
        ]
        if pasta_root is not None:
            argv += ["--pasta", str(pasta_root)]
        if seco:
            argv.append("--seco")
        if os.geteuid() == 0:
            cmd = argv
        elif os.environ.get("SUDO_ASKPASS"):
            cmd = ["sudo", "-A", "--", *argv]
        else:
            cmd = ["sudo", "-n", "--", *argv]
        r = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if r.returncode != 0:
            raise RecusaError(
                "a parte do root não rodou (" + (r.stderr.strip() or f"rc={r.returncode}")
                + "). Ela precisa de privilégio sem pedir senha no meio: exporte "
                "SUDO_ASKPASS, ou rode `sudo -v` antes neste terminal, e repita."
            )
        try:
            dado = json.loads(r.stdout or "{}")
        except ValueError as erro:
            raise RecusaError(f"a parte do root respondeu fora da forma: {r.stdout!r}") from erro
        return dado if isinstance(dado, dict) else {}

    def olhar_o_bluez(self, raizes: Raizes) -> dict[str, Any] | None:
        """O que só o root lê no BlueZ, para o «limpa?». ``None`` = sem privilégio."""
        try:
            return self.rodar_parte_do_root(raizes, "olhar", None, seco=True)
        except (RecusaError, OSError):
            return None

    def root_precisa(self, raizes: Raizes) -> bool:
        """Há algo do lado do root para olhar? (sem privilégio: só o ``isdir``)."""
        return raizes.bluez.is_dir() or raizes.varlib.is_dir()


def _raiz_das_integracoes() -> Path:
    return Path(__file__).resolve().parents[1] / "integrations"


def _modulo_de_integracao(nome: str) -> ModuleType | None:
    """Um módulo stdlib de ``integrations/`` (os que o uninstall roda avulsos).

    Como pacote, o import normal; como script, pelo caminho, com a pasta das
    integrações no ``sys.path`` para o import de irmão que eles fazem.
    """
    try:
        return importlib.import_module(f"hefesto_dualsense4unix.integrations.{nome}")
    except ImportError:
        pass
    pasta = _raiz_das_integracoes()
    arquivo = pasta / f"{nome}.py"
    if not arquivo.is_file():
        return None
    if str(pasta) not in sys.path:
        sys.path.insert(0, str(pasta))
    try:
        return importlib.import_module(nome)
    except ImportError:
        return None


# ══ 7. Achar o que existe ══════════════════════════════════════════════════


def _raiz_de(raizes: Raizes, nome: str) -> Path:
    valor = getattr(raizes, nome)
    if not isinstance(valor, Path):
        raise ValueError(f"raiz desconhecida: {nome}")
    return valor


def _achar_steam(raizes: Raizes, lugar: Lugar) -> list[Path]:
    slo = _modulo_de_integracao("steam_launch_options")
    pp = _modulo_de_integracao("proton_pin")
    if lugar.chave == "steam-opcoes-e-entrada":
        if slo is None:
            return []
        return [Path(p) for p in slo.discover_vdfs(raizes.lar)]
    if pp is None:
        return []
    alvo = Path(pp.default_config_vdf(raizes.lar))
    return [alvo] if alvo.is_file() else []


def _achar_heroic(raizes: Raizes) -> list[Path]:
    return [
        raizes.lar / rel / "config.json"
        for rel in PASTAS_DO_HEROIC
        if (raizes.lar / rel / "config.json").is_file()
    ]


def variaveis_do_produto_no_override(texto: str) -> list[str]:
    """As chaves do produto no ``[Environment]`` de um override do Flatpak."""
    cp = _ler_ini(texto)
    if not cp.has_section("Environment"):
        return []
    return [k for k in cp.options("Environment") if k in VARIAVEIS_DO_PRODUTO]


def variaveis_do_produto_no_heroic(texto: str) -> list[str]:
    """As chaves do produto no ``defaultSettings.enviromentOptions`` do Heroic."""
    try:
        dado = json.loads(texto)
    except ValueError:
        return []
    padroes = dado.get("defaultSettings") if isinstance(dado, dict) else None
    lista = padroes.get("enviromentOptions") if isinstance(padroes, dict) else None
    if not isinstance(lista, list):
        return []
    return [
        str(item.get("key")) for item in lista
        if isinstance(item, dict) and item.get("key") in VARIAVEIS_DO_PRODUTO
    ]


def _achar_overrides(raizes: Raizes) -> list[Path]:
    pasta = raizes.lar / PASTA_DOS_OVERRIDES
    if not pasta.is_dir():
        return []
    achados: list[Path] = []
    for arq in sorted(pasta.iterdir()):
        if not arq.is_file() or arq.is_symlink():
            continue
        try:
            texto = arq.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if variaveis_do_produto_no_override(texto):
            achados.append(arq)
    return achados


def achar(raizes: Raizes, lugar: Lugar) -> list[Path]:
    """Os caminhos que EXISTEM agora para um lugar do lado dela."""
    if lugar.raiz == "lar" and lugar.caminho.startswith("<steam>"):
        return _achar_steam(raizes, lugar)
    if lugar.raiz == "lar" and lugar.caminho.startswith("<heroic>"):
        return _achar_heroic(raizes)
    if lugar.chave == "flatpak-ambiente":
        return _achar_overrides(raizes)
    base = _raiz_de(raizes, lugar.raiz)
    if any(c in lugar.caminho for c in "*?["):
        return sorted(p for p in base.glob(lugar.caminho) if p.exists() or p.is_symlink())
    alvo = base / lugar.caminho
    return [alvo] if (alvo.exists() or alvo.is_symlink()) else []


def _relativo_na_pasta(raizes: Raizes, caminho: Path) -> str:
    """Onde um caminho do lar mora dentro da pasta: ``pessoa/<raiz>/<rel>``."""
    for nome in ("config", "estado", "dados", "cache", "lar"):
        base = _raiz_de(raizes, nome)
        try:
            return f"pessoa/{nome}/{caminho.relative_to(base)}"
        except ValueError:
            continue
    # Uma biblioteca da Steam em outro disco (o link resolvido sai do lar).
    return "pessoa/fora/" + str(caminho).lstrip("/")


def _perfil_com_ajustes(caminho: Path) -> dict[str, Any] | None:
    """O perfil como dicionário, se ele tem ajustes por controle."""
    if not caminho.is_file() or caminho.is_symlink():
        return None
    try:
        dado = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(dado, dict) or not dado.get(CHAVE_DOS_AJUSTES_POR_CONTROLE):
        return None
    return dado


def _gravar_perfil_sem_ajustes(caminho: Path, dado: dict[str, Any]) -> None:
    """Regrava o perfil sem a chave, no formato do ``profiles/loader.py``
    (``_atomic_write_json``: indentação 2, sem escapar acento, quebra no fim)."""
    limpo = {k: v for k, v in dado.items() if k != CHAVE_DOS_AJUSTES_POR_CONTROLE}
    texto = json.dumps(limpo, indent=2, ensure_ascii=False) + "\n"
    tmp = caminho.with_name("." + caminho.name + ".esquecer")
    tmp.write_text(texto, encoding="utf-8")
    with contextlib.suppress(OSError):
        os.chmod(tmp, caminho.stat().st_mode & 0o7777)
    os.replace(tmp, caminho)


# ══ 8. O plano ═════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Passo:
    lugar: Lugar
    caminho: Path
    como: str


def montar_plano(raizes: Raizes, alcance: str) -> list[Passo]:
    """O que o guardar faria do lado dela, sem tocar em nada.

    No alcance dos controles tudo é MOVIDO (o produto passa a não ter a
    memória). Na casa inteira tudo é COPIADO: quem remove é o ``uninstall.sh``
    — e ele PRECISA dos registros no lugar para saber o que desfazer (o
    ``proton-pin-lock.json``, o ``camadas-vulkan.json``).
    """
    plano: list[Passo] = []
    vistos: set[Path] = set()
    for lugar in lugares(alcance, USUARIO):
        for caminho in achar(raizes, lugar):
            if caminho in vistos:
                continue
            if lugar.ato == TIRAR_A_CHAVE:
                # O perfil SEM ajuste por controle também leva cópia: o teste
                # pode gravar um ajuste nele (o botão do mic grava no perfil),
                # e sem os bytes de antes o devolver não o poria como estava.
                com_ajustes = _perfil_com_ajustes(caminho) is not None
                como = TIRAR_A_CHAVE if com_ajustes and alcance == CONTROLES else COPIAR
            elif alcance == CASA:
                como = COPIAR
            else:
                como = lugar.ato
            vistos.add(caminho)
            plano.append(Passo(lugar, caminho, como))
    if alcance == CASA:
        # Na casa inteira a configuração vai inteira: os passos que moram dentro
        # dela já estão na cópia, e copiá-los de novo seria o mesmo byte duas vezes.
        cfg = raizes.config / SLUG
        plano = [
            p for p in plano
            if p.lugar.chave == "configuracao-inteira" or cfg not in p.caminho.parents
        ]
    return plano


def o_que_nao_existia(
    raizes: Raizes, alcance: str
) -> tuple[list[str], list[dict[str, Any]]]:
    """Os lugares do lado dela que o devolver tem de deixar como NÃO estavam.

    ``(ausentes, curingas)``: os caminhos do inventário que não existem agora, e
    cada curinga com o que casa com ele AGORA (``existiam``). Ficam de fora os
    lugares dos lançadores (o arquivo é do lançador, não do produto), os que o
    install recria (``devolve=False``) e, na casa inteira, o que mora dentro da
    configuração — ela volta inteira.
    """
    cfg = raizes.config / SLUG
    ausentes: list[str] = []
    curingas: list[dict[str, Any]] = []
    for lugar in lugares(alcance, USUARIO):
        if not lugar.devolve or lugar.caminho.startswith("<"):
            continue
        if lugar.chave == "flatpak-ambiente":
            continue
        base = _raiz_de(raizes, lugar.raiz)
        alvo = base / lugar.caminho
        if alcance == CASA and lugar.chave != "configuracao-inteira" and cfg in alvo.parents:
            continue
        if any(c in lugar.caminho for c in "*?["):
            curingas.append({"base": str(base), "padrao": lugar.caminho,
                             "existiam": [str(p) for p in sorted(base.glob(lugar.caminho))]})
        elif not (alvo.exists() or alvo.is_symlink()):
            ausentes.append(str(alvo))
    return ausentes, curingas


# ══ 9. Guardar ═════════════════════════════════════════════════════════════


@dataclass
class Relato:
    """O que o comando fez, em linhas curtas para o terminal."""

    pasta: Path | None = None
    linhas: list[str] = field(default_factory=list)
    sobrescritos: list[str] = field(default_factory=list)
    pulados: list[str] = field(default_factory=list)
    #: O que o teste criou onde antes não havia nada (foi para depois-do-teste).
    tirados: list[str] = field(default_factory=list)
    #: O que já estava byte a byte como fora guardado (nada a fazer).
    iguais: list[str] = field(default_factory=list)

    def diz(self, texto: str) -> None:
        self.linhas.append(texto)


def guardar(
    raizes: Raizes,
    alcance: str,
    sistema: Sistema,
    *,
    seco: bool = False,
    agora: float | None = None,
    parar_o_daemon: bool = True,
) -> Relato:
    """Guarda (move ou copia) a memória do alcance numa pasta datada.

    Ordem, e cada passo tem razão:

    1. pergunta à parte do root, a SECO, se há o que fazer — e se ela não roda
       (sem privilégio), recusa ANTES de mover um byte;
    2. para o daemon (ninguém regrava o que está sendo movido);
    3. a parte do root (pareamentos com o ``bluetoothd`` parado, as cópias de
       pareamento, o diário do root);
    4. o lado dela, item por item, com o manifesto regravado a cada item — uma
       queda no meio deixa a pasta dizendo exatamente o que já saiu;
    5. sobe o daemon de novo, se ele estava de pé.
    """
    conferir_o_ensaio(raizes)
    relato = Relato()
    plano = montar_plano(raizes, alcance)
    ausentes, curingas = o_que_nao_existia(raizes, alcance)
    if alcance == CASA and sistema.steam_aberta():
        raise RecusaError("a Steam está aberta: feche-a antes de guardar (ela regrava "
                     "o localconfig.vdf ao sair, e a cópia sairia velha)")
    carimbo = f"{carimbo_agora(agora)}-{alcance}"
    pasta = raizes.guardado / carimbo
    pasta_root = raizes.guardado_do_root / carimbo
    precisa_root = sistema.root_precisa(raizes)
    root_plano: dict[str, Any] = {}
    if precisa_root:
        root_plano = sistema.rodar_parte_do_root(raizes, "esquecer", pasta_root, seco=True)

    if seco:
        relato.diz(f"(a seco) guardaria em {pasta}")
        for passo in plano:
            relato.diz(f"  {passo.como:<24} {passo.caminho}")
        for linha in root_plano.get("linhas", []):
            relato.diz(f"  root                     {linha}")
        if not precisa_root:
            relato.diz("  (nada do lado do root nesta máquina)")
        return relato

    if pasta.exists():
        raise RecusaError(f"a pasta {pasta} já existe — espere um segundo e repita")
    estava_de_pe = parar_o_daemon and sistema.daemon_ativo()
    if parar_o_daemon:
        sistema.parar_daemon()
    try:
        _preparar_pasta(raizes.guardado)
        _preparar_pasta(pasta)
        manifesto = Manifesto(alcance, carimbo, raizes.em_texto(),
                              root=str(pasta_root) if precisa_root else "",
                              ausentes=ausentes, curingas=curingas)
        manifesto.gravar(pasta)
        relato.pasta = pasta
        if precisa_root:
            feito = sistema.rodar_parte_do_root(raizes, "esquecer", pasta_root, seco=False)
            for linha in feito.get("linhas", []):
                relato.diz(f"root: {linha}")
        for passo in plano:
            _guardar_um(raizes, passo, pasta, manifesto)
            manifesto.gravar(pasta)
            relato.diz(f"{passo.como}: {passo.caminho}")
    finally:
        if estava_de_pe:
            sistema.subir_daemon()
    relato.diz(f"guardado em {pasta}")
    return relato


def _guardar_um(raizes: Raizes, passo: Passo, pasta: Path, manifesto: Manifesto) -> None:
    rel = _relativo_na_pasta(raizes, passo.caminho)
    destino = pasta / rel
    if passo.como == TIRAR_A_CHAVE:
        dado = _perfil_com_ajustes(passo.caminho)
        if dado is None:
            return
        copiar(passo.caminho, destino)
        item = Item(passo.lugar.chave, str(passo.caminho), rel, TIRAR_A_CHAVE, USUARIO,
                    devolve=True, retrato=retrato(destino),
                    nota=f"{len(dado[CHAVE_DOS_AJUSTES_POR_CONTROLE])} controle(s)")
        manifesto.itens.append(item)
        manifesto.gravar(pasta)
        _gravar_perfil_sem_ajustes(passo.caminho, dado)
        return
    antes = retrato(passo.caminho)
    if passo.como == MOVER:
        mover(passo.caminho, destino)
    else:
        copiar(passo.caminho, destino)
    depois = retrato(destino)
    if depois != antes:
        raise RecusaError(f"a cópia de {passo.caminho} não confere com o original")
    devolve = passo.lugar.devolve
    manifesto.itens.append(Item(passo.lugar.chave, str(passo.caminho), rel, passo.como,
                                USUARIO, devolve=devolve, retrato=depois))


# ══ 10. Devolver ═══════════════════════════════════════════════════════════


def devolver(
    raizes: Raizes,
    sistema: Sistema,
    pedida: str | None = None,
    *,
    seco: bool = False,
    agora: float | None = None,
) -> Relato:
    """Devolve o que uma pasta guardou, byte a byte, por cima do que houver.

    O que estiver no lugar (o que o teste produziu) vai antes para
    ``<pasta>/depois-do-teste/<carimbo>/`` — nada se perde nas duas voltas. A
    pasta guardada FICA (o devolver copia): dá para devolver de novo.
    """
    conferir_o_ensaio(raizes)
    pasta = escolher_pasta(raizes, pedida)
    manifesto = Manifesto.ler(pasta)
    relato = Relato(pasta=pasta)
    tem_steam = any(i.chave.startswith("steam-") for i in manifesto.itens if i.devolve)
    if tem_steam and sistema.steam_aberta():
        raise RecusaError("a Steam está aberta: feche-a antes de devolver (ela regrava "
                     "os arquivos dela ao sair, por cima do que eu devolver)")
    depois_do_teste = pasta / "depois-do-teste" / carimbo_agora(agora)
    pasta_root = Path(manifesto.root) if manifesto.root else None

    if seco:
        relato.diz(f"(a seco) devolveria {pasta}")
        for item in manifesto.itens:
            origem = Path(item.origem)
            existe = origem.exists() or origem.is_symlink()
            if not item.devolve:
                relato.diz(f"  fica só na pasta         {item.origem}")
            elif existe and retrato(origem) == item.retrato:
                relato.iguais.append(item.origem)
            elif existe:
                relato.diz(f"  devolver por cima        {item.origem}")
            else:
                relato.diz(f"  devolver                 {item.origem}")
        for novo in _o_que_apareceu(manifesto):
            relato.diz(f"  tirar (não existia)      {novo}")
        if relato.iguais:
            relato.diz(f"  ({len(relato.iguais)} já estão como estavam: nada a fazer)")
        if pasta_root is not None:
            dado = sistema.rodar_parte_do_root(raizes, "restaurar", pasta_root, seco=True)
            for linha in dado.get("linhas", []):
                relato.diz(f"  root                     {linha}")
        return relato

    estava_de_pe = sistema.daemon_ativo()
    sistema.parar_daemon()
    try:
        if pasta_root is not None:
            dado = sistema.rodar_parte_do_root(raizes, "restaurar", pasta_root, seco=False)
            for linha in dado.get("linhas", []):
                relato.diz(f"root: {linha}")
        for item in manifesto.itens:
            if not item.devolve:
                relato.pulados.append(item.origem)
                continue
            _devolver_um(pasta, item, depois_do_teste, relato)
        for novo in _o_que_apareceu(manifesto):
            mover(novo, depois_do_teste / _relativo_na_pasta(raizes, novo))
            relato.tirados.append(str(novo))
            relato.diz(f"tirado (não existia antes): {novo}")
        manifesto.devolvido_em.append(carimbo_agora(agora))
        manifesto.gravar(pasta)
    finally:
        if estava_de_pe:
            sistema.subir_daemon()
    if relato.iguais:
        relato.diz(f"{len(relato.iguais)} já estavam como estavam")
    if relato.sobrescritos or relato.tirados:
        relato.diz(f"o que estava no lugar foi para {depois_do_teste}")
    for caminho in relato.pulados:
        relato.diz(f"ficou só na pasta (o produto o recria): {caminho}")
    _dizer_as_escolhas_de_camada(pasta, manifesto, relato)
    relato.diz(f"devolvido de {pasta}")
    return relato


def _o_que_apareceu(manifesto: Manifesto) -> list[Path]:
    """O que existe agora num lugar do inventário que o guardar achou vazio.

    Um ausente que passou a existir, ou um casamento de curinga que não existia
    no guardar: nasceu no teste (a fila de números nova, um perfil criado, o
    ajuste que o botão do mic gravou num perfil que não tinha nenhum) — e
    «exatamente como estava» é sem ele.
    """
    achados: list[Path] = []
    for ausente in manifesto.ausentes:
        caminho = Path(ausente)
        if caminho.exists() or caminho.is_symlink():
            achados.append(caminho)
    for curinga in manifesto.curingas:
        existiam = {str(e) for e in curinga.get("existiam", [])}
        for caminho in sorted(Path(str(curinga["base"])).glob(str(curinga["padrao"]))):
            if str(caminho) in existiam or caminho in achados:
                continue
            if any(p in achados for p in caminho.parents):
                continue
            achados.append(caminho)
    return achados


def _devolver_um(pasta: Path, item: Item, depois_do_teste: Path, relato: Relato) -> None:
    guardado = pasta / item.guardado
    origem = Path(item.origem)
    if not (guardado.exists() or guardado.is_symlink()):
        raise RecusaError(f"a pasta perdeu {guardado} — não devolvo pela metade")
    if retrato(guardado) != item.retrato:
        raise RecusaError(f"{guardado} mudou dentro da pasta — não devolvo o que não confere")
    if (origem.exists() or origem.is_symlink()) and retrato(origem) == item.retrato:
        relato.iguais.append(str(origem))
        return
    if origem.exists() or origem.is_symlink():
        rel = item.guardado
        mover(origem, depois_do_teste / rel)
        relato.sobrescritos.append(str(origem))
    copiar(guardado, origem)
    if retrato(origem) != item.retrato:
        raise RecusaError(f"{origem} não ficou igual ao guardado")
    relato.diz(f"devolvido: {origem}")


def _dizer_as_escolhas_de_camada(pasta: Path, manifesto: Manifesto, relato: Relato) -> None:
    """As camadas que ela mandou MANTER não voltam sozinhas — ditas por nome."""
    for item in manifesto.itens:
        if item.chave != "camadas-vulkan":
            continue
        with contextlib.suppress(OSError, ValueError, AttributeError):
            dado = json.loads((pasta / item.guardado).read_text(encoding="utf-8"))
            for prefixo, camadas in dado.items():
                for camada, registro in camadas.items():
                    if isinstance(registro, dict) and registro.get("escolha") == "manter":
                        relato.diz(f"você tinha mandado manter a camada {camada} em "
                                   f"{prefixo}: devolva-a de novo pela aba Lançadores")


# ══ 11. A parte do root ════════════════════════════════════════════════════
#
# Roda como root (``sudo -A python3 -I <este arquivo> raiz <verbo> --pasta P``)
# ou, com as três raízes desviadas, no próprio processo da régua. Sob root os
# desvios morrem: só as raízes reais, e a pasta tem de morar dentro do
# ``/var/lib/hefesto-memoria-guardada`` com o nome na forma de um carimbo.


def raizes_do_root(env: dict[str, str] | None = None) -> Raizes:
    """As raízes que a parte do root pode usar."""
    raizes = Raizes.do_ambiente(env)
    if os.geteuid() == 0:
        raizes = Raizes(
            lar=raizes.lar, config=raizes.config, estado=raizes.estado,
            dados=raizes.dados, cache=raizes.cache, execucao=raizes.execucao,
            bluez=BLUEZ_REAL, varlib=VARLIB_DO_PRODUTO,
            guardado_do_root=GUARDADO_DO_ROOT_REAL, sistema=Path("/"),
            repositorio=raizes.repositorio,
        )
    return raizes


def _conferir_pasta_do_root(raizes: Raizes, pasta: Path) -> None:
    if pasta.parent != raizes.guardado_do_root or not _FORMA_DA_PASTA.match(pasta.name):
        raise RecusaError(f"pasta do root fora da forma: {pasta}")


class Bluetooth:
    """Parar e subir o ``bluetoothd`` pelo roteiro do ``bt_bonds_restore.sh``.

    Com as raízes desviadas não toca em serviço nenhum (a régua).
    """

    def __init__(self, raizes: Raizes) -> None:
        self.de_verdade = raizes.raizes_do_root_sao_as_reais and os.geteuid() == 0
        self.parado = False
        self.chamadas: list[str] = []

    def _systemctl(self, *args: str) -> int:
        self.chamadas.append(" ".join(args))
        if not self.de_verdade:
            return 0
        return subprocess.run(["systemctl", *args], check=False,
                              capture_output=True).returncode

    def parar(self) -> None:
        # RESTORE-MASK-01: sem a máscara, qualquer cliente do D-Bus reativa o
        # serviço e cancela a parada.
        self.parado = True
        self._systemctl("mask", "--runtime", "bluetooth.service")
        self._systemctl("stop", "--job-mode=replace-irreversibly", "bluetooth.service")
        if not self.de_verdade:
            return
        for _ in range(60):
            if self._systemctl("is-active", "--quiet", "bluetooth.service") != 0:
                return
            time.sleep(1)
        raise RecusaError("o bluetooth.service não parou em 60 s — nada foi movido")

    def subir(self) -> None:
        if not self.parado:
            return
        self._systemctl("unmask", "--runtime", "bluetooth.service")
        self._systemctl("start", "bluetooth.service")
        # AGENTE-QUE-NAO-VOLTA-01: o agente cai junto (Requires=) e não volta
        # sozinho — sem ele todo pareamento novo nasce meio-salvo.
        self._systemctl("reset-failed", "hefesto-bt-agent.service")
        self._systemctl("start", "hefesto-bt-agent.service")
        self.parado = False


@contextlib.contextmanager
def _bluetooth_parado(bt: Bluetooth, precisa: bool) -> Iterator[None]:
    if not precisa:
        yield
        return
    try:
        bt.parar()
        yield
    finally:
        bt.subir()


def _apelidos_dos_adaptadores(bluez: Path) -> dict[str, str]:
    """O ``Alias`` que cada adaptador tem gravado (``<adaptador>/settings``)."""
    apelidos: dict[str, str] = {}
    if not bluez.is_dir():
        return apelidos
    for adaptador in sorted(bluez.iterdir()):
        if not _FORMA_DO_MAC.match(adaptador.name) or adaptador.is_symlink():
            continue
        settings = adaptador / "settings"
        if not settings.is_file() or settings.is_symlink():
            continue
        try:
            texto = settings.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        alias = _ler_ini(texto).get("General", "Alias", fallback="").strip()
        if alias:
            apelidos[adaptador.name] = alias
    return apelidos


def _olhar_no_root(raizes: Raizes) -> dict[str, Any]:
    """O verbo ``olhar``: só LÊ o BlueZ — os pareamentos de controle e os nomes
    dos adaptadores. É o que o «limpa?» pergunta e a pessoa não enxerga."""
    pares = pareamentos_de_controle(raizes.bluez)
    return {
        "linhas": [f"pareamento do controle {p.controle} no adaptador {p.adaptador}"
                   for p in pares],
        "pareamentos": [[p.adaptador, p.controle] for p in pares],
        "apelidos": _apelidos_dos_adaptadores(raizes.bluez),
    }


def executar_parte_do_root(
    raizes: Raizes, verbo: str, pasta: Path | None, *, seco: bool,
    bluetooth: Bluetooth | None = None,
) -> dict[str, Any]:
    """O verbo do root: ``esquecer``, ``restaurar`` ou ``olhar`` (só lê).

    Devolve ``{"linhas": [...]}``; o ``olhar`` não tem pasta e não escreve nada.
    """
    if verbo == "olhar":
        return {**_olhar_no_root(raizes), "bluetooth": []}
    if pasta is None:
        raise RecusaError(f"o verbo do root {verbo} precisa da pasta")
    _conferir_pasta_do_root(raizes, pasta)
    bt = bluetooth if bluetooth is not None else Bluetooth(raizes)
    if verbo == "esquecer":
        linhas = _esquecer_no_root(raizes, pasta, seco=seco, bt=bt)
    elif verbo == "restaurar":
        linhas = _restaurar_no_root(raizes, pasta, seco=seco, bt=bt)
    else:
        raise RecusaError(f"verbo do root desconhecido: {verbo}")
    return {"linhas": linhas, "bluetooth": bt.chamadas}


def _caminhos_do_root(raizes: Raizes) -> list[tuple[Lugar, Path]]:
    saida: list[tuple[Lugar, Path]] = []
    for lugar in lugares(CONTROLES, ROOT):
        if lugar.ato == PAREAMENTOS:
            continue
        base = _raiz_de(raizes, lugar.raiz)
        if "*" in lugar.caminho:
            saida.extend((lugar, p) for p in sorted(base.glob(lugar.caminho)))
        elif (base / lugar.caminho).exists():
            saida.append((lugar, base / lugar.caminho))
    return saida


def _esquecer_no_root(raizes: Raizes, pasta: Path, *, seco: bool, bt: Bluetooth) -> list[str]:
    pares = pareamentos_de_controle(raizes.bluez)
    controles = sorted({p.controle for p in pares})
    caches: list[Path] = []
    if raizes.bluez.is_dir():
        for adaptador in sorted(raizes.bluez.iterdir()):
            if not _FORMA_DO_MAC.match(adaptador.name):
                continue
            for controle in controles:
                c = adaptador / "cache" / controle
                if c.is_file() and not c.is_symlink():
                    caches.append(c)
    outros = _caminhos_do_root(raizes)
    linhas: list[str] = []
    for p in pares:
        linhas.append(f"pareamento do controle {p.controle} no adaptador {p.adaptador}")
    for c in caches:
        linhas.append(f"cache SDP {c.relative_to(raizes.bluez)}")
    for _lugar, caminho in outros:
        linhas.append(str(caminho))
    if seco:
        return linhas
    _preparar_pasta(raizes.guardado_do_root)
    if pasta.exists():
        raise RecusaError(f"a pasta do root {pasta} já existe")
    _preparar_pasta(pasta)
    # O manifesto nasce ANTES do primeiro mover e é regravado a cada item, como
    # o do lado dela: uma queda no meio (o bluetoothd que não para, um disco
    # cheio) deixa a pasta dizendo exatamente o que já saiu — e o devolver da
    # outra metade não tropeça numa pasta do root sem manifesto.
    manifesto = Manifesto(CONTROLES, pasta.name, raizes.em_texto())
    manifesto.gravar(pasta)

    def _mover_e_anotar(chave: str, origem: Path, rel: str, nota: str = "") -> None:
        antes = retrato(origem)
        mover(origem, pasta / rel)
        manifesto.itens.append(Item(chave, str(origem), rel, MOVER, ROOT,
                                    retrato=antes, nota=nota))
        manifesto.gravar(pasta)

    # 1. Os pareamentos, com o bluetoothd parado.
    with _bluetooth_parado(bt, bool(pares or caches)):
        for p in pares:
            _mover_e_anotar("pareamentos-dos-controles", raizes.bluez / p.adaptador / p.controle,
                            f"bluez/{p.adaptador}/{p.controle}", p.controle)
        for c in caches:
            _mover_e_anotar("pareamentos-dos-controles", c,
                            f"bluez/{c.relative_to(raizes.bluez)}", c.name)
        # 2. As cópias de pareamento e o diário do root, DEPOIS dos pareamentos:
        #    nenhum instantâneo de antes sobra para o autorestore ressuscitar.
        for lugar, caminho in outros:
            _mover_e_anotar(lugar.chave, caminho,
                            f"varlib/{caminho.relative_to(raizes.varlib)}")
    return linhas


def _pareamento_vivo(bluez: Path, controle: str) -> str | None:
    """O adaptador em que este controle tem pareamento VIVO agora, ou None."""
    if not bluez.is_dir():
        return None
    for adaptador in sorted(bluez.iterdir()):
        if _FORMA_DO_MAC.match(adaptador.name) and _tem_chave(adaptador / controle):
            return adaptador.name
    return None


def _restaurar_no_root(raizes: Raizes, pasta: Path, *, seco: bool, bt: Bluetooth) -> list[str]:
    manifesto = Manifesto.ler(pasta)
    depois = pasta / "depois-do-teste" / carimbo_agora()
    linhas: list[str] = []
    pular: set[str] = set()
    #: (adaptador antigo, controle) de cada pareamento que NÃO volta.
    enterrar: list[tuple[str, str]] = []
    plano: list[Item] = []
    for item in manifesto.itens:
        if item.chave == "pareamentos-dos-controles" and "/cache/" not in item.guardado:
            controle = Path(item.guardado).name
            vivo = _pareamento_vivo(raizes.bluez, controle)
            if vivo is not None:
                pular.add(controle)
                enterrar.append((Path(item.guardado).parent.name, controle))
                linhas.append(f"o controle {controle} já está pareado de novo (adaptador "
                              f"{vivo}): o pareamento vivo fica, o antigo fica na pasta")
                continue
        if (item.chave == "pareamentos-dos-controles" and "/cache/" in item.guardado
                and Path(item.guardado).name in pular):
            continue
        plano.append(item)
    tocar_o_bluez = any(i.chave == "pareamentos-dos-controles" for i in plano)
    for item in plano:
        linhas.append(f"devolveria {item.origem}" if seco else f"devolvido {item.origem}")
    lapides = raizes.varlib / "bt-bonds" / ".lapides"
    for adaptador, controle in enterrar:
        linhas.append(f"{'gravaria' if seco else 'gravada'} a lápide de {controle} em "
                      f"{adaptador}: o autorestore não o ressuscita")
    if seco:
        return linhas
    with _bluetooth_parado(bt, tocar_o_bluez):
        for item in plano:
            guardado = pasta / item.guardado
            origem = Path(item.origem)
            if retrato(guardado) != item.retrato:
                raise RecusaError(f"{guardado} mudou dentro da pasta — não devolvo")
            if origem.exists() or origem.is_symlink():
                mover(origem, depois / item.guardado)
            copiar(guardado, origem)
        _gravar_lapides(lapides, enterrar)
    manifesto.devolvido_em.append(carimbo_agora())
    manifesto.gravar(pasta)
    return linhas


def _gravar_lapides(lapides: Path, enterrar: list[tuple[str, str]]) -> None:
    """A lápide do pareamento que o devolver deixou de fora — a MESMA do verbo
    ``esquecer`` da ponte privilegiada: ``<epoch> <adaptador> <controle>`` em
    ``bt-bonds/.lapides``.

    Sem ela, o acervo de cópias que acabou de voltar traz a chave VELHA desse
    controle, e o ``bt_bonds_autorestore.sh`` a plantaria no adaptador antigo
    na próxima morte do ``bluetoothd`` (ele só confere o mesmo adaptador) — o
    controle, que só conhece a chave nova, ficaria com casa em dois
    adaptadores. É a regra do devolver («chave velha nunca por cima de um
    pareamento vivo, em adaptador nenhum») valendo também para quem restaura
    depois dele. A lápide só enterra cópia de ANTES dela: o pareamento vivo,
    copiado dali em diante, volta como qualquer outro.
    """
    if not enterrar or not lapides.parent.is_dir() or lapides.parent.is_symlink():
        return
    if lapides.is_symlink():
        raise RecusaError(f"recusando a lápide: {lapides} é link simbólico")
    agora = int(time.time())
    with lapides.open("a", encoding="utf-8") as fh:
        for adaptador, controle in enterrar:
            fh.write(f"{agora} {adaptador} {controle}\n")
    with contextlib.suppress(OSError):
        os.chmod(lapides, 0o600)


# ══ 12. «A máquina está limpa?» ════════════════════════════════════════════


@dataclass(frozen=True)
class Rastro:
    """Uma sobra do Hefesto depois do uninstall."""

    onde: str
    o_que: str
    #: ``True`` quando o próprio uninstall deixa de propósito (um backup, o
    #: Proton extraído que é dado dela) — dito, mas não é defeito.
    de_proposito: bool = False
    #: ``True`` quando o lugar não pôde ser olhado (só o root o lê, e não havia
    #: privilégio). «Não sei» não é «sobrou» nem «limpo»: é dito à parte, com o
    #: que fazer, e não conta como defeito do uninstall.
    nao_sei: bool = False


_REGRAS_HISTORICAS = (
    "70-ps5-controller.rules",
    "73-ps5-controller-hotplug.rules",
    "74-ps5-controller-hotplug-bt.rules",
)


def _regras_udev(raizes: Raizes) -> list[str]:
    nomes = list(_REGRAS_HISTORICAS)
    if raizes.repositorio is not None:
        nomes.extend(p.name for p in (raizes.repositorio / "assets").glob("[0-9][0-9]-*.rules"))
    return sorted(set(nomes))


def _globs_do_sistema(raizes: Raizes) -> list[tuple[str, str]]:
    """``(glob relativo à raiz do sistema, o que é)`` — o que o install escreve."""
    globs = [(f"etc/udev/rules.d/{n}", "regra udev") for n in _regras_udev(raizes)]
    globs += [
        ("etc/modprobe.d/hefesto-*", "opção de módulo"),
        ("etc/modules-load.d/hefesto*", "módulo carregado no boot"),
        ("etc/systemd/system/hefesto-*", "unit do sistema"),
        ("etc/systemd/system/*.d/*hefesto*", "drop-in de unit do sistema"),
        ("etc/tmpfiles.d/hefesto*", "tmpfiles"),
        ("etc/sysctl.d/*hefesto*", "sysctl"),
        ("etc/NetworkManager/conf.d/hefesto*", "configuração do NetworkManager"),
        ("etc/NetworkManager/dispatcher.d/*hefesto*", "gancho do NetworkManager"),
        ("etc/bluetooth/main.conf.d/*hefesto*", "configuração do BlueZ"),
        ("usr/local/lib/hefesto*", "scripts do root"),
        ("usr/local/share/hefesto*", "dados do root"),
        ("usr/local/bin/hefesto*", "binário"),
        ("usr/local/sbin/hefesto*", "binário do root"),
        ("usr/share/alsa/ucm2/USB-Audio/Hefesto", "perfil UCM do DualSense"),
        ("usr/src/hefesto-*", "fonte DKMS"),
        ("run/hefesto-*", "pasta de execução do root"),
    ]
    return globs


#: O prefixo que o Hefesto põe no nome de um adaptador (``bt_active_mode.sh`` e
#: ``integrations/apelido_do_dongle.py``). O ``uninstall.sh`` o tira de TODO
#: adaptador — um nome que ainda começa assim depois dele é rastro.
PREFIXO_DO_ADAPTADOR = "Nintendo "

_O_QUE_FAZER_SEM_ROOT = (
    "exporte SUDO_ASKPASS (ou rode `sudo -v` neste terminal) e pergunte de novo"
)


def _rastros_do_bluez(raizes: Raizes, sistema: Sistema | None) -> list[Rastro]:
    """Os pareamentos de controle e os nomes dos adaptadores — que só o root lê.

    O armazenamento do BlueZ é ``700`` do root: como pessoa, a pergunta não tem
    resposta. Ela vai à parte do root (o mesmo ``sudo -A``/``sudo -n`` do
    guardar); sem privilégio, a resposta é «não sei», dita com o que fazer —
    nunca «sobrou», que faria toda máquina de verdade reprovar, e nunca
    «limpa», que esconderia um controle ainda pareado.
    """
    try:
        olhado: dict[str, Any] | None = _olhar_no_root(raizes)
    except PermissionError:
        olhado = sistema.olhar_o_bluez(raizes) if sistema is not None else None
    if olhado is None:
        return [Rastro(str(raizes.bluez), "não sei se sobrou controle pareado ou nome de "
                       f"adaptador do Hefesto: só o root lê — {_O_QUE_FAZER_SEM_ROOT}",
                       nao_sei=True)]
    rastros: list[Rastro] = []
    for adaptador, controle in olhado.get("pareamentos", []):
        rastros.append(Rastro(str(raizes.bluez / str(adaptador) / str(controle)),
                              "um controle ainda pareado: a primeira vez não será a primeira"))
    for adaptador, alias in sorted(dict(olhado.get("apelidos", {})).items()):
        if str(alias).startswith(PREFIXO_DO_ADAPTADOR):
            rastros.append(Rastro(str(raizes.bluez / str(adaptador) / "settings"),
                                  f"o nome do adaptador ainda leva o prefixo do Hefesto "
                                  f"({alias})"))
    return rastros


def _rastros_do_sistema(raizes: Raizes, sistema: Sistema | None = None) -> list[Rastro]:
    rastros: list[Rastro] = []
    base = raizes.sistema
    if raizes.varlib.exists():
        rastros.append(Rastro(str(raizes.varlib), "pasta do root do produto (cópias de "
                              "pareamento, diário do root)"))
    rastros.extend(_rastros_do_bluez(raizes, sistema))
    for padrao, o_que in _globs_do_sistema(raizes):
        for achado in sorted(base.glob(padrao)):
            rastros.append(Rastro(str(achado), o_que))
    sudoers = base / "etc/sudoers.d/49-hefesto-bt-ponte"
    try:
        if sudoers.exists():
            rastros.append(Rastro(str(sudoers), "a ponte privilegiada (sudoers)"))
    except PermissionError:
        rastros.append(Rastro(str(sudoers), f"não sei: só o root lê — {_O_QUE_FAZER_SEM_ROOT}",
                              nao_sei=True))
    main_conf = base / "etc/bluetooth/main.conf"
    with contextlib.suppress(OSError):
        if "hefesto" in main_conf.read_text(encoding="utf-8", errors="replace").lower():
            rastros.append(Rastro(str(main_conf), "bloco do Hefesto no main.conf"))
    grupo = base / "etc/group"
    with contextlib.suppress(OSError):
        for linha in grupo.read_text(encoding="utf-8", errors="replace").splitlines():
            if linha.split(":", 1)[0] == "hefesto":
                rastros.append(Rastro(str(grupo), "o grupo hefesto"))
    for cmdline in (base / "etc/kernelstub/configuration", base / "etc/default/grub"):
        with contextlib.suppress(OSError):
            texto = cmdline.read_text(encoding="utf-8", errors="replace").lower()
            if "054c:0ce6:gn" in texto or "054c:0df2:gn" in texto:
                rastros.append(Rastro(
                    str(cmdline), "o quirk usbcore do DualSense na linha do kernel "
                    "(o uninstall o preserva sem --remove-usb-quirk)", de_proposito=True))
    return rastros


def _rastros_do_lar(raizes: Raizes) -> list[Rastro]:
    rastros: list[Rastro] = []
    for base, nomes in (
        (raizes.config, (SLUG, "hefesto")),
        (raizes.estado, (SLUG,)),
        (raizes.dados, (SLUG, "hefesto")),
        (raizes.cache, (SLUG, "hefesto")),
        (raizes.execucao, (SLUG,)),
    ):
        for nome in nomes:
            alvo = base / nome
            if alvo.exists():
                rastros.append(Rastro(str(alvo), "pasta do produto"))
    for backup in sorted(raizes.config.glob(f"{SLUG}.backup-*")):
        rastros.append(Rastro(str(backup), "o backup que o uninstall faz", de_proposito=True))
    padroes = [
        (raizes.config / "systemd/user", "hefesto*", "unit do usuário"),
        (raizes.config / "systemd/user", "*/hefesto*", "unit do usuário (habilitada)"),
        (raizes.config / "autostart", "*hefesto*", "abrir com a sessão"),
        (raizes.lar / ".local/bin", "hefesto*", "comando no PATH"),
        (raizes.dados / "applications", "*hefesto*", "atalho do menu"),
        (raizes.dados / "icons/hicolor", f"*/apps/{_ID.icone}.*", "ícone"),
        (raizes.dados / "pixmaps", f"{_ID.app_id}*", "ícone"),
        (raizes.dados / "locale", f"*/LC_MESSAGES/{SLUG}.mo", "tradução"),
        (raizes.config / "environment.d", "*hefesto*", "ambiente da sessão"),
        (raizes.lar / ".var/app", "*", ""),
    ]
    for pasta, padrao, o_que in padroes:
        if not pasta.is_dir():
            continue
        for achado in sorted(pasta.glob(padrao)):
            if o_que == "":
                if achado.name in IDS_DE_FLATPAK_DO_HEFESTO:
                    rastros.append(Rastro(str(achado), "a casa do Flatpak do Hefesto"))
                continue
            rastros.append(Rastro(str(achado), o_que))
    wp = raizes.config / "wireplumber/wireplumber.conf.d"
    if wp.is_dir():
        for achado in sorted(wp.glob("*hefesto*")):
            try:
                marcado = "recriado manualmente" in achado.read_text(
                    encoding="utf-8", errors="replace")
            except OSError:
                marcado = False
            rastros.append(Rastro(str(achado), "drop-in do WirePlumber"
                                  + (" (marcado para ficar)" if marcado else ""),
                                  de_proposito=marcado))
    return rastros


def _rastros_nos_lancadores(raizes: Raizes) -> list[Rastro]:
    rastros: list[Rastro] = []
    lugar_vdf = next(lg for lg in INVENTARIO if lg.chave == "steam-opcoes-e-entrada")
    for vdf in _achar_steam(raizes, lugar_vdf):
        with contextlib.suppress(OSError):
            n = sum(
                1 for linha in vdf.read_text(encoding="utf-8", errors="replace").splitlines()
                if '"LaunchOptions"' in linha and "hefesto" in linha.lower()
            )
            if n:
                rastros.append(Rastro(str(vdf), f"{n} jogo(s) com o atalho do Hefesto "
                                      "nas Opções de Inicialização"))
        # As cópias que o install e o uninstall tiram ao lado de cada vdf antes de
        # mexer nele (``steam_launch_options``: ``.bak.hefesto-launch-<ts>``;
        # ``disable_steam_input.sh``: ``.bak.steam-input-<ts>``). Ficam de
        # propósito — são o desfazer dela —, e o «limpa?» diz que estão lá.
        for sufixo in ("hefesto-launch", "steam-input"):
            for copia in sorted(vdf.parent.glob(f"{vdf.name}.bak.{sufixo}-*")):
                rastros.append(Rastro(str(copia), "a cópia do vdf de antes de o Hefesto "
                                      "mexer nele (fica: é o seu desfazer)",
                                      de_proposito=True))
    pp = _modulo_de_integracao("proton_pin")
    if pp is not None:
        with contextlib.suppress(OSError, ValueError, AttributeError):
            cfg = Path(pp.default_config_vdf(raizes.lar))
            conf_path = pp.default_pin_conf_path()
            if cfg.is_file() and conf_path is not None:
                nome = pp.parse_pin_conf(Path(conf_path).read_text(encoding="utf-8"))["name"]
                mapa = pp.extract_compat_tool_mapping(cfg.read_text(encoding="utf-8"))
                n = sum(1 for v in mapa.values() if v == nome)
                if n:
                    rastros.append(Rastro(str(cfg), f"{n} jogo(s) ainda no Proton pinado "
                                          f"({nome}) — pode ser escolha sua"))
            compat = Path(pp.default_compat_dir(raizes.lar))
            if compat.is_dir():
                for manifesto in sorted(compat.glob(f"*/{pp.MANIFEST_BASENAME}")):
                    rastros.append(Rastro(str(manifesto.parent),
                                          "o Proton que o Hefesto extraiu (fica: é seu)",
                                          de_proposito=True))
    for heroic in _achar_heroic(raizes):
        with contextlib.suppress(OSError):
            chaves = variaveis_do_produto_no_heroic(heroic.read_text(encoding="utf-8"))
            certas = [k for k in chaves if k not in _VARIAVEIS_QUE_PODEM_SER_DELA]
            if certas:
                rastros.append(Rastro(str(heroic), "o ambiente do Hefesto em todo jogo do "
                                      "Heroic: " + ", ".join(certas)))
    for override in _achar_overrides(raizes):
        with contextlib.suppress(OSError):
            chaves = variaveis_do_produto_no_override(override.read_text(encoding="utf-8"))
            certas = [k for k in chaves if k not in _VARIAVEIS_QUE_PODEM_SER_DELA]
            if certas:
                rastros.append(Rastro(str(override), "o ambiente do Hefesto no Flatpak "
                                      "deste lançador: " + ", ".join(certas)))
    cv = _modulo_de_integracao("camadas_vulkan")
    if cv is not None:
        with contextlib.suppress(OSError, AttributeError):
            for prefixo in cv.raizes_de_prefixo(raizes.lar):
                reg = Path(prefixo) / "pfx" / "system.reg"
                with contextlib.suppress(OSError):
                    if MARCA_DO_DEVICE_KS in reg.read_text(encoding="utf-8", errors="replace"):
                        rastros.append(Rastro(str(reg), "o device de áudio KS do Hefesto "
                                              "no registro do jogo"))
    return rastros


def conferir_a_casa(raizes: Raizes, sistema: Sistema | None = None) -> list[Rastro]:
    """Depois do uninstall: o que sobrou do Hefesto, lugar por lugar.

    É também a prova de que o uninstall é honesto — o que sobra e não é de
    propósito é defeito dele. O ``sistema`` é por onde a pergunta chega ao que
    só o root lê (o BlueZ); sem ele, esse pedaço volta «não sei».
    """
    return (_rastros_do_lar(raizes) + _rastros_nos_lancadores(raizes)
            + _rastros_do_sistema(raizes, sistema))


# ══ 13. Linha de comando da parte do root ═════════════════════════════════


def _principal_do_root(argv: Sequence[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="memoria_dos_controles raiz")
    p.add_argument("verbo", choices=("esquecer", "restaurar", "olhar"))
    p.add_argument("--pasta", default=None)
    p.add_argument("--seco", action="store_true")
    a = p.parse_args(list(argv))
    raizes = raizes_do_root()
    try:
        pasta = Path(a.pasta) if a.pasta else None
        dado = executar_parte_do_root(raizes, a.verbo, pasta, seco=a.seco)
    except RecusaError as erro:
        print(str(erro), file=sys.stderr)
        return 2
    print(json.dumps(dado, ensure_ascii=False))
    return 0


def principal(argv: Iterable[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] == ["raiz"]:
        return _principal_do_root(args[1:])
    print("uso: memoria_dos_controles.py raiz {esquecer,restaurar} --pasta P [--seco]"
          " | raiz olhar", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(principal())
