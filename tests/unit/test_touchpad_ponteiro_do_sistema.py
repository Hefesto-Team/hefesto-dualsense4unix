"""TOUCHPAD-DO-SISTEMA-01 — o touchpad volta a ser touchpad, em todos os modos.

O PEDIDO, 09/08/2026, textual: ** E, quando o assunto
desviou para a emulação de mouse pelo analógico: ** — o pedido é sobre o TOUCHPAD como ponteiro do
sistema.

A CAUSA, medida no controle do usuário (``/run/udev/data/c13:68``, DualSense por USB,
09/08/2026): ``E:ID_INPUT_TOUCHPAD=1`` **e** ``E:LIBINPUT_IGNORE_DEVICE=1``. Uma
linha só, com curinga, em ``assets/76-dualsense-touchpad-libinput-ignore.rules``
apagava o touchpad de TODO aparelho em TODO modo::

    ATTRS{name}=="*DualSense*Touchpad"

AS DUAS BRIGAS QUE O CURINGA CUROU, e por que nenhuma volta:

- **cursor engasgado** (FEAT-DUALSENSE-TOUCHPAD-IGNORE-01, 26/06): o hefesto e
  o libinput movendo o MESMO cursor com o MESMO dedo. Agora quem separa é o
  runtime: o ``TouchpadReader`` lê ``LIBINPUT_IGNORE_DEVICE`` no nó que abriu e,
  se o sistema é o ponteiro, não acumula movimento nem entrega região de clique;
- **toque em dobro dentro do jogo** (TOUCHPAD-76-BT-VPAD-01, 21/07): eram DOIS
  ponteiros do libinput alimentados por UM dedo — o nó do touchpad físico e o do
  VPAD, que recebe os touch points copiados do report cru (bytes 32..39, dentro
  da janela de motion 15..39 de ``core/physical_report_reader.py``). A regra
  continua tirando o nó do VPAD, para sempre; sobra exatamente um ponteiro.

AS MORDIDAS (cada uma foi arrancada e vista reprovar):

- devolver o curinga ``*DualSense*Touchpad`` à regra ->
  ``test_o_touchpad_fisico_nao_e_mais_ignorado`` reprova nos quatro nomes
  físicos medidos (USB, BT, Edge, DualShock4);
- apagar a linha do vpad da regra -> ``test_o_touchpad_do_vpad_continua_fora``
  reprova, e com ela o toque em dobro estaria de volta;
- renomear o vpad sem mexer na regra ->
  ``test_a_regra_casa_o_nome_que_o_vpad_publica_hoje`` reprova (foi exatamente
  uma renomeação que furou o match exato de 26/06);
- tirar ``not self._ponteiro_do_sistema`` do ``_acumula_agora`` ->
  ``test_nao_acumula_movimento_quando_o_sistema_e_o_ponteiro`` reprova;
- tirar o ``if getattr(reader, "ponteiro_do_sistema", False)`` do
  ``_combine_with_touchpad`` -> ``test_o_clique_nao_vira_tecla_quando_o_sistema_
  e_o_ponteiro`` reprova, e um clique só passaria a disparar o botão do mouse
  do usuário mais um ``KEY_BACKSPACE``.

Nenhum controle real, nenhum ``/dev``, nenhum ``udevadm control`` é tocado: a
regra é lida como texto e a base do udev é um diretório temporário.
"""
from __future__ import annotations

import fnmatch
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.evdev_reader import (
    TouchpadReader,
    libinput_ignora_device,
)
from hefesto_dualsense4unix.daemon.subsystems.keyboard import _combine_with_touchpad
from hefesto_dualsense4unix.integrations.uhid_gamepad import UhidDualSense, player_mac

REPO_ROOT = Path(__file__).resolve().parents[2]
REGRA = REPO_ROOT / "assets" / "76-dualsense-touchpad-libinput-ignore.rules"

#: DualSense plugado; o segundo é como o BlueZ nomeia o mesmo aparelho (sem o
NOMES_FISICOS = (
    "Sony Interactive Entertainment DualSense Wireless Controller Touchpad",
    "DualSense Wireless Controller Touchpad",
    "Sony Interactive Entertainment DualSense Edge Wireless Controller Touchpad",
    "Sony Interactive Entertainment Wireless Controller Touchpad",
)

MAC_FISICO = "aa:bb:cc:00:11:f0"


def _linhas_de_codigo(path: Path) -> list[str]:
    """Só linha de CÓDIGO: o comentário que EXPLICA a regra não prova nada."""
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.lstrip().startswith("#")
    ]


def _casa(linha: str, *, name: str, uniq: str) -> bool:
    """Simula o casamento de UMA linha de regra udev contra um nó de entrada."""
    atributos = dict(re.findall(r'ATTRS\{(\w+)\}=="([^"]*)"', linha))
    if not atributos:
        return False
    valores = {"name": name, "uniq": uniq}
    return all(
        fnmatch.fnmatchcase(valores.get(attr, ""), padrao)
        for attr, padrao in atributos.items()
    )


def _ignora(linhas: list[str], *, name: str, uniq: str = "") -> bool:
    """True se ALGUMA linha da regra marca este nó com LIBINPUT_IGNORE_DEVICE."""
    return any(
        'ENV{LIBINPUT_IGNORE_DEVICE}="1"' in ln and _casa(ln, name=name, uniq=uniq)
        for ln in linhas
    )


@pytest.fixture(scope="module")
def linhas() -> list[str]:
    if not REGRA.is_file():
        pytest.fail(f"regra ausente: {REGRA}")
    return _linhas_de_codigo(REGRA)


def test_o_touchpad_fisico_nao_e_mais_ignorado(linhas: list[str]) -> None:
    """O pedido, em uma asserção: o touchpad físico é do SISTEMA.

    Vale por USB e por Bluetooth, e para os quatro nomes que o mesmo touchpad
    assume. Devolver o curinga `*DualSense*Touchpad` reprova aqui.
    """
    for nome in NOMES_FISICOS:
        assert not _ignora(linhas, name=nome, uniq=MAC_FISICO), (
            f"a regra ainda apaga o touchpad FÍSICO '{nome}' do libinput — é "
            "exatamente o defeito que ela relatou: o dedo anda e o cursor não."
        )


def test_o_touchpad_do_vpad_continua_fora(linhas: list[str]) -> None:
    """O toque em DOBRO (21/07) morava aqui, e não pode voltar."""
    nomes_vpad = (
        "DualSense Wireless Controller (Hefesto P1) Touchpad",
        "DualSense Wireless Controller (Hefesto P4) Touchpad",
        "Hefesto Virtual DualSense P1 Touchpad",
    )
    for nome in nomes_vpad:
        assert _ignora(linhas, name=nome, uniq=player_mac(1)), (
            f"o nó do vpad '{nome}' voltou a ser ponteiro do libinput — cada "
            "toque move o cursor EM DOBRO dentro do jogo (medido em 21/07)."
        )


def test_o_vpad_e_pego_pelo_mac_forjado_mesmo_sem_o_nome(linhas: list[str]) -> None:
    """A segunda âncora existe porque a primeira já furou uma vez."""
    for jogador in (1, 2, 3, 4):
        assert _ignora(
            linhas,
            name="Qualquer Nome Que O Vpad Venha A Ter Touchpad",
            uniq=player_mac(jogador),
        ), f"o vpad do P{jogador} escapa quando o nome muda: falta a âncora do MAC"


def test_a_regra_casa_o_nome_que_o_vpad_publica_hoje(linhas: list[str]) -> None:
    """Trava a regra no CÓDIGO: renomear o vpad sem mexer aqui reprova."""
    pad = UhidDualSense(player=1, blueprint={"descriptor": b"", "features": {}})
    assert _ignora(linhas, name=f"{pad.name} Touchpad", uniq=pad.mac), (
        f"o vpad publica '{pad.name}' e a regra não o pega: o toque em dobro "
        "volta em silêncio na próxima renomeação."
    )


def test_nenhuma_linha_usa_attrs_phys(linhas: list[str]) -> None:
    """``phys`` sai VAZIO nos nós do hid_playstation — âncora que não ancora."""
    for ln in linhas:
        assert "ATTRS{phys}" not in ln, (
            f"âncora em atributo VAZIO nos nós do hid_playstation: {ln}"
        )


def test_udevadm_verify_aprova() -> None:
    """Sintaxe: uma regra que o udev recusa não protege ninguém."""
    udevadm = shutil.which("udevadm")
    if udevadm is None:
        pytest.skip("udevadm ausente neste ambiente")
    proc = subprocess.run(
        [udevadm, "verify", str(REGRA)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"udevadm verify reprovou:\n{proc.stdout}{proc.stderr}"


def test_a_regra_e_instalada_por_todos_os_formatos() -> None:
    """Paridade nominal: a regra que não viaja é a regra que não existe."""
    alvos = (
        "scripts/install_udev.sh",
        "scripts/install-host-udev.sh",
        "uninstall.sh",
        "packaging/arch/PKGBUILD",
        "packaging/fedora/hefesto-dualsense4unix.spec",
        "packaging/nix/package.nix",
        "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml",
    )
    faltando = [
        rel
        for rel in alvos
        if (REPO_ROOT / rel).is_file()
        and REGRA.name not in (REPO_ROOT / rel).read_text(encoding="utf-8")
    ]
    assert not faltando, f"{REGRA.name} não é instalada por: {faltando}"


class TestLibinputIgnoraDevice:
    """A leitura da base do udev — o único fato que o gate consulta."""

    @staticmethod
    def _montar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, corpo: str | None):
        """Um "nó" e a entrada dele na base do udev, em diretório temporário."""
        from hefesto_dualsense4unix.core import evdev_reader

        monkeypatch.setattr(evdev_reader, "UDEV_DB_DIR", tmp_path)
        no = tmp_path / "event0"
        no.write_text("", encoding="utf-8")
        if corpo is not None:
            (tmp_path / "c0:0").write_text(corpo, encoding="utf-8")
        return no

    def test_marcado_com_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        no = self._montar(
            tmp_path,
            monkeypatch,
            "E:ID_INPUT=1\nE:ID_INPUT_TOUCHPAD=1\nE:LIBINPUT_IGNORE_DEVICE=1\nG:uaccess\n",
        )
        assert libinput_ignora_device(no) is True

    def test_sem_a_propriedade(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        no = self._montar(tmp_path, monkeypatch, "E:ID_INPUT=1\nE:ID_INPUT_TOUCHPAD=1\n")
        assert libinput_ignora_device(no) is False

    def test_marcado_com_zero_nao_conta(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        no = self._montar(tmp_path, monkeypatch, "E:LIBINPUT_IGNORE_DEVICE=0\n")
        assert libinput_ignora_device(no) is False

    def test_sem_base_do_udev_o_sistema_e_o_dono(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem base, nenhuma regra foi aplicada ao nó — o libinput o enxerga."""
        no = self._montar(tmp_path, monkeypatch, None)
        assert libinput_ignora_device(no) is False

    def test_caminho_ausente(self) -> None:
        assert libinput_ignora_device(None) is False
        assert libinput_ignora_device("/dev/input/event-que-nao-existe") is False


class _DevFalso:
    """O mínimo que o `_on_device_opened` consulta de um InputDevice."""

    def __init__(self, path: str) -> None:
        self.path = path


class TestTouchpadReaderDonoDoCursor:
    """O reader só move o cursor quando o cursor é dele."""

    @staticmethod
    def _reader() -> TouchpadReader:
        return TouchpadReader(device_path=Path("/dev/input/event-fake"))

    @staticmethod
    def _dedo(reader: TouchpadReader, x: int) -> None:
        """Um frame de dedo apoiado em X (o mesmo caminho do `_handle_event`)."""
        with reader._lock:
            reader._touching = True
            reader._accumulate_axis_x(x)

    def test_acumula_movimento_quando_o_hefesto_e_o_dono(self) -> None:
        reader = self._reader()
        reader._ponteiro_do_sistema = False
        self._dedo(reader, 100)
        self._dedo(reader, 150)
        assert reader.consume_motion() == (50, 0)

    def test_nao_acumula_movimento_quando_o_sistema_e_o_ponteiro(self) -> None:
        """O dente do "cursor engasgado" (26/06), agora em runtime."""
        reader = self._reader()
        reader._ponteiro_do_sistema = True
        self._dedo(reader, 100)
        self._dedo(reader, 150)
        assert reader.consume_motion() == (0, 0)

    def test_o_observador_continua_sem_acumular(self) -> None:
        """As duas negativas são independentes: o painel de Status nunca acumula."""
        reader = TouchpadReader(
            device_path=Path("/dev/input/event-fake"), acumular_movimento=False
        )
        reader._ponteiro_do_sistema = False
        self._dedo(reader, 100)
        self._dedo(reader, 150)
        assert reader.consume_motion() == (0, 0)

    def test_o_open_decide_o_dono_pela_base_do_udev(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.core import evdev_reader

        monkeypatch.setattr(evdev_reader, "UDEV_DB_DIR", tmp_path)
        no = tmp_path / "event0"
        no.write_text("", encoding="utf-8")

        reader = self._reader()
        reader._on_device_opened(_DevFalso(str(no)))
        assert reader.ponteiro_do_sistema is True

        (tmp_path / "c0:0").write_text("E:LIBINPUT_IGNORE_DEVICE=1\n", encoding="utf-8")
        reader._on_device_opened(_DevFalso(str(no)))
        assert reader.ponteiro_do_sistema is False

    def test_trocar_de_dono_zera_o_acumulado(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O delta do dono anterior viraria um salto de cursor no novo."""
        from hefesto_dualsense4unix.core import evdev_reader

        monkeypatch.setattr(evdev_reader, "UDEV_DB_DIR", tmp_path)
        no = tmp_path / "event0"
        no.write_text("", encoding="utf-8")
        (tmp_path / "c0:0").write_text("E:LIBINPUT_IGNORE_DEVICE=1\n", encoding="utf-8")

        reader = self._reader()
        reader._on_device_opened(_DevFalso(str(no)))
        self._dedo(reader, 100)
        self._dedo(reader, 400)
        assert reader._accum_dx == 300

        (tmp_path / "c0:0").write_text("E:ID_INPUT=1\n", encoding="utf-8")
        reader._on_device_opened(_DevFalso(str(no)))
        assert reader.consume_motion() == (0, 0)


class _DaemonFalso:
    def __init__(self, reader: Any) -> None:
        self._touchpad_reader = reader


class _ReaderFalso:
    def __init__(self, *, ponteiro_do_sistema: bool) -> None:
        self.ponteiro_do_sistema = ponteiro_do_sistema

    def regions_pressed(self) -> frozenset[str]:
        return frozenset({"touchpad_left_press"})


class TestCliqueDoTouchpad:
    """O clique é um só: ou é o botão do sistema, ou é a tecla do hefesto."""

    def test_o_clique_vira_tecla_quando_o_hefesto_e_o_dono(self) -> None:
        daemon = _DaemonFalso(_ReaderFalso(ponteiro_do_sistema=False))
        combinado = _combine_with_touchpad(daemon, frozenset({"cross"}))
        assert combinado == frozenset({"cross", "touchpad_left_press"})

    def test_o_clique_nao_vira_tecla_quando_o_sistema_e_o_ponteiro(self) -> None:
        """Sem este dente, um clique dispara o botão do mouse E um KEY_BACKSPACE."""
        daemon = _DaemonFalso(_ReaderFalso(ponteiro_do_sistema=True))
        combinado = _combine_with_touchpad(daemon, frozenset({"cross"}))
        assert combinado == frozenset({"cross"})

    def test_reader_sem_a_propriedade_mantem_o_comportamento_historico(self) -> None:
        """Dublê antigo/objeto sem a propriedade: o hefesto é o dono."""

        class _Antigo:
            def regions_pressed(self) -> frozenset[str]:
                return frozenset({"touchpad_right_press"})

        daemon = _DaemonFalso(_Antigo())
        assert _combine_with_touchpad(daemon, frozenset()) == frozenset(
            {"touchpad_right_press"}
        )
