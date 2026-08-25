"""`mic bt` não vira o SEGUNDO dono do report 0x32 — QUATRO-MICROFONES-01/E3.

O DEFEITO, medido em 25/08/2026 no fonte da árvore de hoje: a ponte de
microfone por Bluetooth tem **duas portas de produção** que a sobem, e nenhuma
sabia da outra.

    cli/cmd_mic.py::_mic_bt                     -> GerenciadorMicBluetooth()
    daemon/subsystems/bt_mic.py::BtMicSubsystem -> GerenciadorMicBluetooth()

São dois PROCESSOS. Cada `PonteMicBluetooth` carrega o próprio contador de
sequência do `0x32`, então as duas portas no mesmo controle produzem
exatamente o quadro que o estudo `2026-08-16-O-PS-PRESO-*.md` nomeou como causa
provável de um DualSense travado: **dois donos da sequência do 0x32** — e desta
vez sem kernel nenhum no meio, feito pelo próprio produto.

A CURA é a arbitragem NA PORTA, e ela não inventa dado nenhum: usa o que o
`daemon.state_full` já publica desde 23/08 (`bt_mic.uniqs`, os `uniq` cuja
ponte SUBIU — a entrega E2 desta mesma sprint). `mic bt` lê essa lista e não
sobe ponte em cima de quem já tem uma.

O LIMITE, DECLARADO: fecha o sentido CLI -> daemon, e só ele. O outro sentido é
a arbitragem do NÓ, no broker — o portão 5.a, que não existe, e cuja dívida é
vigiada por `test_portao_a_ponte_do_mic_espera_a_arbitragem.py`.

COMO MORDE (exercido em 25/08/2026)
------------------------------------
Arranque, por LINHA, o bloco da arbitragem em `cli/cmd_mic.py::_mic_bt` (o
teste contra `_DAEMON_VELHO` e o `_livres(...)`/`if not livres:` logo abaixo) e
devolva o `gerenciador.reconciliar(alvos)` ao `reconciliar()` sem argumento.
Reprovam:

* `test_recusa_quando_o_daemon_nao_diz_de_quem_sao_as_pontes`
* `test_recusa_quando_todo_controle_ja_tem_ponte_do_daemon`
* `test_sobe_so_no_controle_que_o_daemon_nao_segura`

Endereços sintéticos da faixa `e8:47:3a` com a máscara da casa (octetos 4 e 5
zerados) — fora da faixa `aabbcc`, que é a que já vazou para a mesa dela.
"""
from __future__ import annotations

import signal
from dataclasses import dataclass
from typing import Any

import pytest

from hefesto_dualsense4unix.cli import cmd_mic

UNIQ_A = "e8:47:3a:00:00:11"
UNIQ_B = "e8:47:3a:00:00:22"


@dataclass
class _No:
    """Dublê de `NoDualSenseBT` — só os dois campos que a arbitragem lê."""

    caminho: str
    uniq: str


@dataclass
class _Diag:
    """Dublê de `Diagnostico`. Ele sabe dizer PRONTO e sabe dizer NÃO."""

    controles: list[_No]
    libopus: str | None = "libopus.so.0"
    pactl: bool = True
    pipe_source: bool = True
    broker: bool = True
    pronto_: bool = True

    @property
    def pronto(self) -> bool:
        return self.pronto_

    @property
    def impedimentos(self) -> list[str]:
        return [] if self.pronto_ else ["libopus ausente"]


class _GerenciadorFalso:
    """Dublê do gerenciador: registra os alvos e encerra o laço na 1ª volta.

    `dormir` devolvendo True é o mesmo sinal que o Ctrl-C manda — assim o laço
    de `_mic_bt` roda exatamente UMA reconciliação e volta, sem relógio.
    """

    def __init__(self) -> None:
        self.alvos: list[list[str]] = []
        self.parou = False

    def reconciliar(self, nos: list[Any] | None = None) -> None:
        self.alvos.append([getattr(n, "uniq", "") for n in (nos or [])])

    @property
    def pontes(self) -> dict[str, Any]:
        return {}

    def dormir(self, _s: float) -> bool:
        return True

    def parar(self) -> None:
        self.parou = True


@pytest.fixture
def sinais_intactos():
    """Restaura SIGINT/SIGTERM: `_mic_bt` os instala no caminho de subir."""
    antes = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    yield
    for sig, handler in antes.items():
        signal.signal(sig, handler)


def _montar(monkeypatch, *, controles: list[_No], daemon: tuple[frozenset[str], str]):
    """Fia os dublês: o diagnóstico, o gerenciador e a resposta do daemon."""
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as ponte

    gerenciador = _GerenciadorFalso()
    monkeypatch.setattr(ponte, "diagnosticar", lambda: _Diag(controles=controles))
    monkeypatch.setattr(ponte, "GerenciadorMicBluetooth", lambda: gerenciador)
    monkeypatch.setattr(ponte, "nos_dualsense_bluetooth", lambda: list(controles))
    monkeypatch.setattr(cmd_mic, "_pontes_ja_de_pe", lambda: daemon)
    return gerenciador


# ---------------------------------------------------------------------------
# A régua que lê o daemon — e ela sabe dar as TRÊS respostas (armadilha A2)
# ---------------------------------------------------------------------------


def test_a_regua_sabe_dizer_quem_ja_tem_ponte():
    uniqs, situacao = cmd_mic._ler_bloco_bt_mic(
        {"bt_mic": {"enabled": True, "running": True, "uniqs": [UNIQ_A]}}
    )
    assert situacao == cmd_mic._DAEMON_RESPONDE
    assert uniqs == frozenset({"e8473a000011"}), "o uniq chega normalizado"


def test_a_regua_sabe_dizer_ninguem():
    uniqs, situacao = cmd_mic._ler_bloco_bt_mic(
        {"bt_mic": {"enabled": False, "running": False}}
    )
    assert (uniqs, situacao) == (frozenset(), cmd_mic._DAEMON_RESPONDE)


def test_a_regua_sabe_dizer_nao_sei():
    """Ausência de notícia NÃO é notícia boa: `running` sem `uniqs` é `velho`.

    É o daemon de 22/08, que publicava duas chaves. Ele diz que há ponte de pé
    e não diz de quem — a única resposta honesta é "não sei".
    """
    assert cmd_mic._ler_bloco_bt_mic({"bt_mic": {"running": True}})[1] == (
        cmd_mic._DAEMON_VELHO
    )
    assert cmd_mic._ler_bloco_bt_mic({})[1] == cmd_mic._DAEMON_VELHO


def test_a_reparticao_separa_livre_de_tomado():
    livres, tomados = _livres_de([_No("/dev/hidraw3", UNIQ_A), _No("/dev/hidraw4", UNIQ_B)])
    assert [n.uniq for n in livres] == [UNIQ_B]
    assert [n.uniq for n in tomados] == [UNIQ_A]


def _livres_de(nos: list[_No]):
    return cmd_mic._livres(nos, frozenset({"e8473a000011"}))


# ---------------------------------------------------------------------------
# A arbitragem da porta
# ---------------------------------------------------------------------------


def test_recusa_quando_o_daemon_nao_diz_de_quem_sao_as_pontes(monkeypatch, capsys):
    gerenciador = _montar(
        monkeypatch,
        controles=[_No("/dev/hidraw3", UNIQ_A)],
        daemon=(frozenset(), cmd_mic._DAEMON_VELHO),
    )
    rc = cmd_mic._mic_bt(status_apenas=False)
    saida = capsys.readouterr().out
    assert rc == 1, "não sei quem segura o nó -> não subo"
    assert gerenciador.alvos == [], "nenhuma ponte foi tentada"
    assert "0x32" in saida and "daemon restart" in saida, "o quê, por quê e o que fazer"


def test_recusa_quando_todo_controle_ja_tem_ponte_do_daemon(monkeypatch, capsys):
    gerenciador = _montar(
        monkeypatch,
        controles=[_No("/dev/hidraw3", UNIQ_A)],
        daemon=(frozenset({"e8473a000011"}), cmd_mic._DAEMON_RESPONDE),
    )
    rc = cmd_mic._mic_bt(status_apenas=False)
    saida = capsys.readouterr().out
    assert rc == 0, "não é erro da usuária: está tudo ligado, só não por nós"
    assert gerenciador.alvos == []
    assert "Configurações" in saida, "quem subiu é quem derruba"


def test_sobe_so_no_controle_que_o_daemon_nao_segura(
    monkeypatch, capsys, sinais_intactos
):
    gerenciador = _montar(
        monkeypatch,
        controles=[_No("/dev/hidraw3", UNIQ_A), _No("/dev/hidraw4", UNIQ_B)],
        daemon=(frozenset({"e8473a000011"}), cmd_mic._DAEMON_RESPONDE),
    )
    rc = cmd_mic._mic_bt(status_apenas=False)
    saida = capsys.readouterr().out
    assert rc == 0
    assert gerenciador.alvos == [[UNIQ_B]], "o A é do daemon; só o B é nosso"
    assert UNIQ_A in saida and "pulo" in saida, "a tela diz quem ficou de fora"
    assert gerenciador.parou, "o `finally` desliga o que subimos"


def test_sem_daemon_o_caminho_a_mao_continua_livre(
    monkeypatch, capsys, sinais_intactos
):
    """Sem daemon não há subsystem, logo não há ponte do produto de pé.

    É a única ausência que se pode LER como "o caminho está livre", e é por
    isso que ela é uma situação própria e não cai no `velho`.
    """
    gerenciador = _montar(
        monkeypatch,
        controles=[_No("/dev/hidraw3", UNIQ_A), _No("/dev/hidraw4", UNIQ_B)],
        daemon=(frozenset(), cmd_mic._SEM_DAEMON),
    )
    rc = cmd_mic._mic_bt(status_apenas=False)
    assert rc == 0
    assert gerenciador.alvos == [[UNIQ_A, UNIQ_B]], "os dois, como sempre foi"
    assert "pontes do daemon ... nenhuma" in capsys.readouterr().out


def test_bt_status_mostra_quem_ja_segura_e_nao_mexe_em_nada(monkeypatch, capsys):
    gerenciador = _montar(
        monkeypatch,
        controles=[_No("/dev/hidraw3", UNIQ_A)],
        daemon=(frozenset({"e8473a000011"}), cmd_mic._DAEMON_RESPONDE),
    )
    rc = cmd_mic._mic_bt(status_apenas=True)
    assert rc == 0
    assert gerenciador.alvos == [], "`bt-status` diagnostica, nunca sobe"
    assert "e8473a000011" in capsys.readouterr().out
