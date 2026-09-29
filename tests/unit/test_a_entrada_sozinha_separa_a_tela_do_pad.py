"""A-ENTRADA-SOZINHA-SEPARA-A-TELA-DO-PAD-01 — o instrumento que dava alarme falso.

Em 29/09/2026, quatro pads parados na mesa por um minuto, e o
`scripts/ensaios/a_entrada_que_nasce_sozinha.py` imprimiu «8875 evento(s) NO
QUE MEXE NA TELA» com `rc 0`, sem nada se mexer na tela. Seis defeitos do
instrumento, e as réguas abaixo prendem a cura de cada um:

1. a classe do nó vem do udev, pelas marcas de CLASSE, e nunca do nome;
2. a conta é por nó (o caminho), e quatro pads iguais dão quatro linhas;
3. o eco da vibração (`EV_FF`) é saída, e sai com o tipo e o efeito;
4. o pad pergunta ao dono da zona (`quem_mexe.teve_entrada`), e o chiado de
   1 LSB fica dentro dela;
5. o fantasma de 10/09 (eixo que salta, botão num pad parado) continua pego;
6. o zero de quem não foi lido sai com a frase do dono, e o grab do nó aberto
   pelo broker se pergunta no fd dele;
7. os donos são os objetos da casa, e não cópias com o mesmo nome;
8. o veredito zero diz «ZERO no que mexe na tela», que a folha da bancada lê;
9. o cabeçalho diz de onde veio a biblioteca, porque o `import` vem antes.

Todas puras: nada de `/dev/input`, de `/run/udev` ou de broker de verdade. O
leitor de propriedades, o de eventos e o do grab entram injetados.
"""

from __future__ import annotations

import errno
import importlib.util
import os
import stat
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INSTRUMENTO = RAIZ / "scripts" / "ensaios" / "a_entrada_que_nasce_sozinha.py"

ec = pytest.importorskip("evdev").ecodes

_NOME_DO_PAD = "Microsoft X-Box 360 pad (Hefesto)"

#: As propriedades do udev medidas às 02h20 de 29/09 (só leitura), por nó.
_GAMEPAD_FISICO = {
    "ID_INPUT": "1",
    "ID_INPUT_JOYSTICK": "1",
    "ID_INPUT_JOYSTICK_INTEGRATION": "external",
}
_GAMEPAD_DO_PAD = {"ID_INPUT": "1", "ID_INPUT_JOYSTICK": "1"}
_SENSOR = {
    "ID_INPUT": "1",
    "ID_INPUT_ACCELEROMETER": "1",
    "ID_INPUT_WIDTH_MM": "8",
    "ID_INPUT_HEIGHT_MM": "8",
}
_TOUCHPAD_FISICO = {
    "ID_INPUT": "1",
    "ID_INPUT_TOUCHPAD": "1",
    "ID_INPUT_TOUCHPAD_INTEGRATION": "external",
}
_TOUCHPAD_DO_PAD = {"ID_INPUT": "1", "ID_INPUT_TOUCHPAD": "1"}
_HEADSET_JACK = {"ID_INPUT": "1", "ID_INPUT_SWITCH": "1"}
_TECLADO_VIRTUAL = {"ID_INPUT": "1", "ID_INPUT_KEY": "1"}


@pytest.fixture(scope="module")
def mod() -> Any:
    """Importa o instrumento pelo caminho, como a casa já faz com os scripts."""
    sys.path.insert(0, str(INSTRUMENTO.parent))
    sys.path.insert(0, str(RAIZ / "scripts"))
    spec = importlib.util.spec_from_file_location("a_entrada_que_nasce_sozinha", INSTRUMENTO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def comum(mod: Any) -> Any:
    return sys.modules["comum"]


# ---------------------------------------------------------------------------
# Os dublês: um aparelho que publica o que o nó publica
# ---------------------------------------------------------------------------


class _Aparelho:
    """O `InputDevice` de mentira: fd, `absinfo` do repouso, `capabilities`."""

    def __init__(self, fd: int, repouso: dict[int, int] | None = None) -> None:
        self.fd = fd
        self._repouso = repouso or {}

    def capabilities(self) -> dict[int, Any]:
        return {}

    def absinfo(self, codigo: int) -> Any:
        if codigo not in self._repouso:
            raise OSError(errno.EINVAL, "sem absinfo")
        return SimpleNamespace(value=self._repouso[codigo])

    def close(self) -> None:
        pass


def _ev(tipo: int, codigo: int, valor: int = 0) -> Any:
    return SimpleNamespace(type=tipo, code=codigo, value=valor)


def _syn() -> Any:
    return _ev(ec.EV_SYN, ec.SYN_REPORT, 0)


def _repouso(**eixos: int) -> dict[int, int]:
    base = {"ABS_X": 128, "ABS_Y": 128, "ABS_RX": 128, "ABS_RY": 128, "ABS_Z": 0, "ABS_RZ": 0}
    base.update(eixos)
    return {int(getattr(ec, nome)): valor for nome, valor in base.items()}


def _pad(mod: Any, comum: Any, caminho: str, **repouso: int) -> Any:
    no = mod.NoVigiado(
        caminho, _NOME_DO_PAD, "—", mod.PAD, porta=comum.PORTA_DIRETA, grab=comum.GRAB_LIVRE
    )
    no.semear(_Aparelho(3, _repouso(**repouso)), ec)
    return no


def _no(mod: Any, comum: Any, caminho: str, classe: str, nome: str = "nó") -> Any:
    return mod.NoVigiado(
        caminho, nome, "—", classe, porta=comum.PORTA_DIRETA, grab=comum.GRAB_LIVRE
    )


def _alimentar(mod: Any, no: Any, eventos: list[Any]) -> None:
    for evento in eventos:
        no.registrar(evento, ec)
    no.fechar_quadro()


def _chiado(eixo: str, a: int, b: int, trocas: int) -> list[Any]:
    """Um eixo trocando entre dois valores vizinhos, um quadro por troca."""
    codigo = int(getattr(ec, eixo))
    eventos: list[Any] = []
    for i in range(trocas):
        eventos += [_ev(ec.EV_ABS, codigo, b if i % 2 == 0 else a), _syn()]
    return eventos


def _eco(quantos: int) -> list[Any]:
    return [_ev(ec.EV_FF, 0, 1) for _ in range(quantos)]


# ---------------------------------------------------------------------------
# 1. A classe vem do udev
# ---------------------------------------------------------------------------


def _montar(mod: Any, alvos: list[tuple[str, str, dict[str, str] | None]]) -> list[Any]:
    """Monta os nós com as propriedades injetadas e nenhum nó aberto."""
    props = {caminho: p for caminho, _n, p in alvos}

    def _recusa(caminho: str) -> Any:
        raise PermissionError(errno.EACCES, "sem permissão", caminho)

    return list(mod.montar_os_nos(
        [(caminho, nome, "—") for caminho, nome, _p in alvos],
        ec,
        abrir=_recusa,
        propriedades=props.get,
        acesso=lambda _c, _m: False,
    ))


def test_a_classe_vem_do_udev_e_nao_do_nome(mod: Any) -> None:
    """Mordida (a): a IMU volta a sair pelo nome («Motion Sensors» no nome
    vira IMU), e o nó com a marca de touchpad deixa de ser tela."""
    nos = _montar(mod, [
        ("/x/event900", "DualSense Wireless Controller Motion Sensors",
         {"ID_INPUT": "1", "ID_INPUT_TOUCHPAD": "1"}),
        ("/x/event901", "Hefesto - Dualsense4Unix Virtual Keyboard", _GAMEPAD_DO_PAD),
    ])
    assert [no.classe for no in nos] == [mod.TELA, mod.PAD]


@pytest.mark.parametrize(
    ("propriedades", "classe"),
    [
        (_GAMEPAD_FISICO, "pad"),
        (_GAMEPAD_DO_PAD, "pad"),
        (_SENSOR, "IMU"),
        (_TOUCHPAD_FISICO, "tela"),
        (_TOUCHPAD_DO_PAD, "tela"),
        (_HEADSET_JACK, "chave"),
        (_TECLADO_VIRTUAL, "tela"),
        ({"ID_INPUT": "1", "ID_INPUT_JOYSTICK": "1", "ID_INPUT_KEY": "1"}, "tela"),
        ({"ID_INPUT": "1", "ID_INPUT_MOUSE": "1"}, "tela"),
        (None, "não sei"),
        ({}, "não sei"),
        ({"ID_INPUT": "1"}, "não sei"),
    ],
)
def test_as_propriedades_medidas_dao_a_classe_certa(
    mod: Any, propriedades: dict[str, str] | None, classe: str
) -> None:
    """Mordida (b): leia «qualquer outra `ID_INPUT_*`» como tela, e o gamepad
    físico (`ID_INPUT_JOYSTICK_INTEGRATION=external`) vira tela."""
    assert mod.classe_do_no(propriedades) == classe


def test_o_banco_do_udev_se_le_pelo_st_rdev(mod: Any, tmp_path: Path) -> None:
    """O `event263` é `c13:263`; a conta 64 + N daria `c13:327`, outro nó."""
    (tmp_path / "c13:263").write_text(
        "I:123\nE:ID_INPUT=1\nE:ID_INPUT_SWITCH=1\nG:seat\n", encoding="utf-8"
    )
    (tmp_path / "c13:327").write_text("E:ID_INPUT=1\nE:ID_INPUT_TOUCHPAD=1\n", encoding="utf-8")

    def _estat(_caminho: str) -> Any:
        return SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_rdev=os.makedev(13, 263))

    props = mod.propriedades_do_udev("/x/event263", raiz=str(tmp_path), estat=_estat)
    assert props == {"ID_INPUT": "1", "ID_INPUT_SWITCH": "1"}
    assert mod.classe_do_no(props) == mod.CHAVE


def test_sem_o_banco_do_udev_a_classe_e_nao_sei(mod: Any, tmp_path: Path) -> None:
    """Numa caixa sem o banco à vista, a resposta honesta é «não sei»."""

    def _estat(_caminho: str) -> Any:
        return SimpleNamespace(st_mode=stat.S_IFCHR | 0o600, st_rdev=os.makedev(13, 70))

    assert mod.propriedades_do_udev("/x/event70", raiz=str(tmp_path), estat=_estat) is None
    arquivo_comum = tmp_path / "event70"
    arquivo_comum.write_bytes(b"")
    assert mod.propriedades_do_udev(str(arquivo_comum), raiz=str(tmp_path)) is None


# ---------------------------------------------------------------------------
# 2. A conta é por nó
# ---------------------------------------------------------------------------


def test_quatro_nos_com_o_mesmo_nome_dao_quatro_linhas(mod: Any, comum: Any) -> None:
    """Mordida: conte por nome, e as quatro linhas repetem a soma (8.875 em
    cada uma, em 29/09)."""
    nos = [_no(mod, comum, f"/x/event{n}", mod.TELA, _NOME_DO_PAD) for n in range(20, 24)]
    _alimentar(mod, nos[0], [_ev(ec.EV_KEY, ec.BTN_SOUTH, 1), _syn()] * 3)
    _alimentar(mod, nos[1], [_ev(ec.EV_KEY, ec.BTN_EAST, 1), _syn()] * 5)
    linhas = {
        linha.split()[0]: linha
        for linha in mod.relatorio(nos, 60)
        if linha.startswith("  /x/event")
    }
    assert len(linhas) == 4
    assert " 3  " in linhas["/x/event20"]
    assert " 5  " in linhas["/x/event21"]
    zero = comum.leitura_de_zero(comum.GRAB_LIVRE)
    assert zero in linhas["/x/event22"] and zero in linhas["/x/event23"]
    assert [no.entradas for no in nos] == [3, 5, 0, 0]


# ---------------------------------------------------------------------------
# 3. O eco da vibração é saída
# ---------------------------------------------------------------------------


def test_o_eco_da_vibracao_nao_e_entrada(mod: Any, comum: Any) -> None:
    """1.199 `EV_FF` de efeito 0 em cada pad (4.796 no total, a medida de
    29/09): zero na tela, zero com mão, e uma linha de eco por pad.

    Mordida: conte `EV_FF` como entrada, e o alarme de 29/09 volta."""
    pads = [_pad(mod, comum, f"/x/event{n}") for n in range(20, 24)]
    for pad in pads:
        _alimentar(mod, pad, _eco(1199))
    rc, frase = mod.veredito(pads)
    assert rc == 0, frase
    assert "ZERO no que mexe na tela" in frase
    assert all(pad.entradas == 0 and pad.quadros_com_mao == 0 for pad in pads)
    texto = "\n".join(mod.relatorio(pads, 60))
    assert texto.count("EV_FF efeito 0: 1.199") == 4
    assert "4.796 de saída ecoada" in frase


def test_o_rotulo_leva_o_tipo(mod: Any) -> None:
    """O `0` puro de 29/09 era `EV_FF` do efeito 0 sem o tipo."""
    assert mod.rotulo_do_evento(ec, ec.EV_FF, 0) == "EV_FF efeito 0"
    assert mod.rotulo_do_evento(ec, ec.EV_ABS, ec.ABS_RX) == "EV_ABS ABS_RX"


# ---------------------------------------------------------------------------
# 4. O chiado pergunta ao dono da zona
# ---------------------------------------------------------------------------


def _a_corrida_de_29_09(mod: Any, comum: Any) -> list[Any]:
    """Os quatro pads com os eixos e as trocas medidos, ±1 em torno de 124..132."""
    p1 = _pad(mod, comum, "/x/event21", ABS_X=127, ABS_RX=131)
    p2 = _pad(mod, comum, "/x/event22", ABS_X=125)
    p3 = _pad(mod, comum, "/x/event23", ABS_RX=128)
    p4 = _pad(mod, comum, "/x/event24", ABS_X=126, ABS_RY=124)
    _alimentar(mod, p1, _chiado("ABS_X", 127, 128, 500) + _chiado("ABS_RX", 131, 132, 458)
               + _eco(1199))
    _alimentar(mod, p2, _chiado("ABS_X", 125, 126, 506) + _eco(1199))
    _alimentar(mod, p3, _chiado("ABS_RX", 128, 129, 2) + _eco(1199))
    _alimentar(mod, p4, _chiado("ABS_X", 126, 127, 506) + _chiado("ABS_RY", 124, 125, 1649)
               + _eco(1199))
    return [p1, p2, p3, p4]


def test_o_chiado_do_aparelho_fica_dentro_da_zona(mod: Any, comum: Any) -> None:
    """A corrida de 29/09 reproduzida dá ZERO e rc 0, com o chiado por pad.

    Mordida (a): conte todo `EV_ABS` de pad como candidato, e o rc vira 1."""
    pads = _a_corrida_de_29_09(mod, comum)
    rc, frase = mod.veredito(pads)
    assert rc == 0, frase
    assert "ZERO no que mexe na tela" in frase
    assert [pad.quadros_com_mao for pad in pads] == [0, 0, 0, 0]
    assert [pad.dentro_da_zona for pad in pads] == [958, 506, 2, 2155]
    assert pads[0].amplitude() == "lx 1, rx 1"
    assert pads[2].amplitude() == "rx 1"
    assert pads[3].amplitude() == "lx 1, ry 1"
    texto = "\n".join(mod.relatorio(pads, 60))
    assert "dentro da zona (o chiado do aparelho): 2 evento(s); amplitude: rx 1" in texto


def test_a_zona_e_a_do_dono_e_nao_uma_copia(
    mod: Any, comum: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mordida (b): com `quem_mexe.ZONA_MORTA = 0`, o chiado vira «com mão».
    Prova que o instrumento pergunta ao dono: se ele mudar, o veredito muda."""
    from hefesto_dualsense4unix.daemon.subsystems import quem_mexe

    monkeypatch.setattr(quem_mexe, "ZONA_MORTA", 0)
    pads = _a_corrida_de_29_09(mod, comum)
    rc, frase = mod.veredito(pads)
    assert rc == 1, frase
    assert all(pad.quadros_com_mao for pad in pads)


# ---------------------------------------------------------------------------
# 5. O fantasma continua pego
# ---------------------------------------------------------------------------


def test_o_eixo_que_salta_e_pego(mod: Any, comum: Any) -> None:
    """O caso de 10/09: um eixo que salta para 250 num pad parado.

    Mordida: tire o pad da pergunta, e o fantasma passa com rc 0."""
    pad = _pad(mod, comum, "/x/event30", ABS_RX=131)
    _alimentar(mod, pad, [*_chiado("ABS_RX", 131, 132, 10),
                          _ev(ec.EV_ABS, ec.ABS_RX, 250), _syn()])
    rc, frase = mod.veredito([pad])
    assert rc == 1, frase
    assert "/x/event30" in frase
    assert pad.quadros_com_mao == 1
    assert "ABS_RX=250" in pad.primeiro_com_mao


def test_o_botao_num_pad_parado_e_pego(mod: Any, comum: Any) -> None:
    pad = _pad(mod, comum, "/x/event31")
    _alimentar(mod, pad, [_ev(ec.EV_KEY, ec.BTN_SOUTH, 1), _syn(),
                          _ev(ec.EV_KEY, ec.BTN_SOUTH, 0), _syn()])
    rc, frase = mod.veredito([pad])
    assert rc == 1, frase
    assert "/x/event31" in frase and "pad" in frase


def test_o_que_mexe_na_tela_e_culpado(mod: Any, comum: Any) -> None:
    """O teclado virtual que emite uma tecla é o culpado, com o caminho."""
    teclado = _no(mod, comum, "/x/event22", mod.TELA, "Hefesto - Dualsense4Unix Virtual Keyboard")
    sensor = _no(mod, comum, "/x/event23", mod.IMU, "Motion Sensors")
    _alimentar(mod, sensor, [_ev(ec.EV_ABS, ec.ABS_RX, 7), _syn()] * 40)
    _alimentar(mod, teclado, [_ev(ec.EV_KEY, ec.KEY_A, 1), _syn()])
    rc, frase = mod.veredito([teclado, sensor])
    assert rc == 1, frase
    assert "/x/event22" in frase and "/x/event23" not in frase


def test_a_imu_e_a_chave_sao_contexto(mod: Any, comum: Any) -> None:
    sensor = _no(mod, comum, "/x/event23", mod.IMU)
    jack = _no(mod, comum, "/x/event24", mod.CHAVE)
    _alimentar(mod, sensor, [_ev(ec.EV_ABS, ec.ABS_RX, 7), _syn()] * 40)
    _alimentar(mod, jack, [_ev(ec.EV_SW, ec.SW_HEADPHONE_INSERT, 1), _syn()])
    rc, frase = mod.veredito([sensor, jack])
    assert rc == 0, frase
    assert "40 de IMU, 1 de chave" in frase


# ---------------------------------------------------------------------------
# 6. O zero de quem não se leu
# ---------------------------------------------------------------------------


def _sem_permissao(tmp_path: Path, nome: str) -> Path:
    """Um arquivo `0000` no lugar do nó escondido: `os.open` dá `EACCES`."""
    if os.geteuid() == 0:  # pragma: no cover - a raiz abre tudo
        pytest.skip("a raiz não recebe EACCES")
    no = tmp_path / nome
    no.write_bytes(b"")
    no.chmod(0)
    return no


def _ioctl_que_pega(_fd: int, _pedido: int, _arg: int) -> None:
    return None


def _ioctl_de_terceiro(_fd: int, _pedido: int, _arg: int) -> None:
    raise OSError(errno.EBUSY, "outro processo segura o nó")


def test_o_touchpad_sem_permissao_sai_com_a_frase_do_dono(
    mod: Any, comum: Any, tmp_path: Path
) -> None:
    """Mordida (a): imprima 0, e a corrida dá rc 0 sobre um touchpad que
    ninguém leu."""
    caminho = str(_sem_permissao(tmp_path, "event256"))

    def _recusa(c: str) -> Any:
        raise PermissionError(errno.EACCES, "sem permissão", c)

    (no,) = mod.montar_os_nos(
        [(caminho, "DualSense Wireless Controller Touchpad", "—")], ec,
        abrir=_recusa, propriedades=lambda _c: _TOUCHPAD_FISICO,
        acesso=lambda _c, _m: False, ioctl=_ioctl_que_pega,
    )
    assert no.porta is None
    assert no.celula() == comum.leitura_de_zero(comum.GRAB_SEM_PERMISSAO)
    rc, frase = mod.veredito([no])
    assert rc == 3, frase
    assert caminho in frase


def test_o_no_preso_por_terceiro_nao_segura_o_veredito(
    mod: Any, comum: Any, tmp_path: Path
) -> None:
    no_do_disco = tmp_path / "event257"
    no_do_disco.write_bytes(b"")

    def _recusa(c: str) -> Any:
        raise PermissionError(errno.EACCES, "sem permissão", c)

    (no,) = mod.montar_os_nos(
        [(str(no_do_disco), "DualSense Wireless Controller", "—")], ec,
        abrir=_recusa, propriedades=lambda _c: _GAMEPAD_FISICO,
        acesso=lambda _c, _m: False, ioctl=_ioctl_de_terceiro,
    )
    assert no.celula() == comum.leitura_de_zero(comum.GRAB_DE_TERCEIRO)
    rc, frase = mod.veredito([no])
    assert rc == 0, frase


def test_o_touchpad_lido_pelo_broker_tem_o_grab_perguntado_no_fd(
    mod: Any, comum: Any, tmp_path: Path
) -> None:
    """O nó é `0600 root`: o `os.open` dá `EACCES`, e o broker serviu o fd.

    Mordida (b): chame `estado_do_grab(caminho)` sem o `abrir`, e o touchpad
    lido pelo broker sai «sem permissão»."""
    caminho = str(_sem_permissao(tmp_path, "event259"))
    servido = tmp_path / "o-fd-do-broker"
    servido.write_bytes(b"")
    fd = os.open(servido, os.O_RDONLY)
    try:
        (no,) = mod.montar_os_nos(
            [(caminho, "DualSense Wireless Controller Touchpad", "—")], ec,
            abrir=lambda _c: _Aparelho(fd), propriedades=lambda _c: _TOUCHPAD_FISICO,
            acesso=lambda _c, _m: False, ioctl=_ioctl_que_pega,
        )
    finally:
        os.close(fd)
    assert no.porta == mod.PORTA_BROKER
    assert no.grab == comum.GRAB_LIVRE
    assert no.lido
    rc, frase = mod.veredito([no])
    assert rc == 0, frase
    assert no.celula() == comum.leitura_de_zero(comum.GRAB_LIVRE)


def test_o_no_aberto_pelo_caminho_diz_a_porta_direta(mod: Any, comum: Any, tmp_path: Path) -> None:
    servido = tmp_path / "event21"
    servido.write_bytes(b"")
    fd = os.open(servido, os.O_RDONLY)
    try:
        (no,) = mod.montar_os_nos(
            [(str(servido), _NOME_DO_PAD, "—")], ec,
            abrir=lambda _c: _Aparelho(fd, _repouso(ABS_X=127)),
            propriedades=lambda _c: _GAMEPAD_DO_PAD,
            acesso=lambda _c, _m: True, ioctl=_ioctl_que_pega,
        )
    finally:
        os.close(fd)
    assert no.porta == comum.PORTA_DIRETA
    assert no.eixos["lx"] == 127, "o estado do pad nasce do absinfo na abertura"


def test_a_classe_ilegivel_e_o_no_que_nasceu_no_meio_dao_nao_sei(mod: Any, comum: Any) -> None:
    desconhecido = _no(mod, comum, "/x/event40", mod.NAO_SEI)
    rc, frase = mod.veredito([desconhecido])
    assert rc == 3, frase
    pad = _pad(mod, comum, "/x/event41")
    nasceram = mod.classes_dos_que_nasceram(
        ["/x/event50", "/x/event51"],
        {"/x/event50": _TOUCHPAD_DO_PAD, "/x/event51": _SENSOR}.get,
    )
    assert nasceram == ["/x/event50"]
    rc, frase = mod.veredito([pad], nasceram_sem_leitura=nasceram)
    assert rc == 3, frase
    assert "/x/event50" in frase


def test_o_no_que_saiu_no_meio_invalida_a_medicao(mod: Any, comum: Any) -> None:
    rc, frase = mod.veredito([_pad(mod, comum, "/x/event21")], sumiram=["P2"])
    assert rc == 2
    assert frase.startswith("MEDIÇÃO INVÁLIDA")


# ---------------------------------------------------------------------------
# 7. Os donos são os objetos da casa
# ---------------------------------------------------------------------------


def test_os_donos_sao_os_objetos_da_casa(mod: Any, comum: Any) -> None:
    """É a régua de dono, e não a da palavra: uma cópia local com o mesmo
    nome passaria numa busca pelo texto `estado_do_grab(`.

    Mordida: copie a função para dentro do instrumento, e a identidade reprova."""
    from hefesto_dualsense4unix.core import evdev_reader
    from hefesto_dualsense4unix.daemon.subsystems import quem_mexe
    from hefesto_dualsense4unix.integrations import hidraw_broker_client

    assert mod.estado_do_grab is comum.estado_do_grab is hidraw_broker_client.estado_do_grab
    assert mod.leitura_de_zero is hidraw_broker_client.leitura_de_zero
    assert mod.teve_entrada is quem_mexe.teve_entrada
    assert mod.abrir_input_device is evdev_reader.abrir_input_device
    assert mod.EvdevReader is evdev_reader.EvdevReader
    assert mod.normalizar_eixo is evdev_reader.normalizar_eixo


def test_a_porta_padrao_e_o_dono_da_porta(mod: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem `abrir` injetado, o nó abre pelo `abrir_input_device` da casa."""
    chamados: list[str] = []

    def _dono(caminho: str) -> Any:
        chamados.append(caminho)
        raise PermissionError(errno.EACCES, "sem permissão", caminho)

    monkeypatch.setattr(mod, "abrir_input_device", _dono)
    monkeypatch.setattr(mod, "ler_o_grab", lambda *_a, **_k: "livre")
    mod.montar_os_nos([("/x/event60", "nó", "—")], ec, propriedades=lambda _c: None)
    assert chamados == ["/x/event60"]


# ---------------------------------------------------------------------------
# 8 e 9. A frase do zero e a biblioteca do cabeçalho
# ---------------------------------------------------------------------------


def test_a_frase_do_zero_e_a_que_a_folha_le(mod: Any, comum: Any) -> None:
    rc, frase = mod.veredito([_pad(mod, comum, "/x/event21")])
    assert rc == 0
    assert "ZERO no que mexe na tela" in frase
    assert "RESUMO: ZERO no que mexe na tela" in comum.resumo(frase)


def test_o_cabecalho_diz_de_onde_veio_o_evdev(
    mod: Any, comum: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Com um `evdev` falso no caminho de import, a linha da biblioteca traz o
    `__file__` dele, e não «NÃO IMPORTADO».

    Mordida: imprima o cabeçalho antes do `import evdev`."""
    pacote = tmp_path / "evdev"
    pacote.mkdir()
    (pacote / "__init__.py").write_text("ecodes = None\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "evdev", raising=False)
    monkeypatch.setattr(comum, "estado_do_daemon", lambda: comum.EstadoDoDaemon())
    monkeypatch.setattr(comum, "porta_provavel", lambda *_a, **_k: (comum.PORTA_DIRETA, "dublê"))
    monkeypatch.setattr(mod, "nos_de_entrada", list)

    rc = mod.main(["--listar"])

    saida = capsys.readouterr().out
    linha = next(li for li in saida.splitlines() if "biblioteca ......." in li)
    assert str(pacote / "__init__.py") in linha, linha
    assert "NÃO IMPORTADO" not in linha
    assert rc == 3, "sem nó nenhum a vigiar, a resposta é «não sei»"


def test_sem_nenhum_no_o_rc_e_nao_sei(
    mod: Any, comum: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(comum, "estado_do_daemon", lambda: comum.EstadoDoDaemon())
    monkeypatch.setattr(comum, "porta_provavel", lambda *_a, **_k: (comum.PORTA_DIRETA, "dublê"))
    monkeypatch.setattr(mod, "nos_de_entrada", list)
    assert mod.main(["--segundos", "0"]) == 3
    assert "RESUMO: NÃO SEI" in capsys.readouterr().out


def test_o_modulo_evdev_falso_nao_vaza(mod: Any) -> None:
    """O teste do cabeçalho devolve o `evdev` de verdade ao terminar."""
    evdev = sys.modules.get("evdev")
    assert isinstance(evdev, types.ModuleType)
    assert getattr(evdev, "ecodes", None) is not None
