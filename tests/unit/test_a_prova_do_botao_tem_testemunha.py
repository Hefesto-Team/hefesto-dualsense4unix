"""A PROVA DO BOTÃO TEM TESTEMUNHA — A-PROVA-DO-BOTAO-TEM-TESTEMUNHA-01, 29/09/2026.

Na bancada de 29/09, um laço de 0,1 s leu 1.767 vezes o `state_full` com os
botões vazios nos quatro cartões, e o vazio foi lido como «a tela não viu».
Não havia aperto dentro do laço: a aba Controles estava fora da tela e o
primeiro da ordem não apertou nada. O defeito era da PROVA — um zero sem aperto
testemunhado —, e a cura é o `scripts/ensaios/quem_e_quem.py --apertar`: o pad
que o jogo lê é a testemunha, e a tela é o `state_full` pela conta da aba 02.

As réguas rodam o ensaio de produção com duas fontes de mentira independentes:
o pad (eventos com a hora do kernel, num relógio de mentira que o seletor anda)
e o `state_full` (o que `mesa_viva.estado_do_daemon` devolveria naquela hora).
O `leitura_viva` e o `TIQUE_MS` são os de produção. Nenhum nó de verdade é
aberto: a porta da casa (`evdev_reader.abrir_input_device`) e o dono do grab
(`hidraw_broker_client.estado_do_grab`) são trocados em TODO teste, e o `/sys`
do pad uinput é uma pasta temporária.

As mordidas estão nas docstrings; as que se fazem trocando o dado (o cartão de
outro jogador, dois cartões, o aperto curto) estão também dentro do arquivo.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
ENSAIOS = RAIZ / "scripts" / "ensaios"
ENSAIO = ENSAIOS / "quem_e_quem.py"

INICIO = 1000.0
JANELA_S = 4.0

#: Faixa forjada (a máscara preserva o OUI; fixture não usa endereço real).
UNIQS = tuple(f"aa:bb:cc:00:00:0{n}" for n in range(1, 5))


def _carregar() -> ModuleType:
    if str(ENSAIOS) not in sys.path:
        sys.path.insert(0, str(ENSAIOS))
    spec = importlib.util.spec_from_file_location("quem_e_quem_da_testemunha", ENSAIO)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    # as dataclasses do ensaio procuram o próprio módulo em `sys.modules`
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def qq() -> ModuleType:
    return _carregar()


@pytest.fixture(scope="module")
def tela(qq: ModuleType) -> tuple[Any, Any, Any, int]:
    return qq._a_tela()  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# O pad de mentira: eventos com a hora do kernel, e um seletor que anda o relógio
# ---------------------------------------------------------------------------


class Relogio:
    def __init__(self) -> None:
        self.agora = INICIO

    def __call__(self) -> float:
        return self.agora


@dataclass
class Evento:
    type: int
    code: int
    value: int
    hora: float

    def timestamp(self) -> float:
        return self.hora


@dataclass
class PadDeMentira:
    caminho: str
    relogio: Relogio
    eventos: list[Evento] = field(default_factory=list)
    fechado: bool = False

    def pendentes(self) -> list[Evento]:
        return [e for e in self.eventos if e.hora <= self.relogio.agora]

    def proximo(self) -> float | None:
        return min((e.hora for e in self.eventos), default=None)

    def read(self) -> list[Evento]:
        saem = self.pendentes()
        self.eventos = [e for e in self.eventos if e not in saem]
        return saem

    def close(self) -> None:
        self.fechado = True


@dataclass
class _Chave:
    fileobj: Any


class SeletorDeMentira:
    """O `select` anda o relógio até o próximo evento, ou até o tempo pedido."""

    def __init__(self, relogio: Relogio) -> None:
        self.relogio = relogio
        self.registrados: list[PadDeMentira] = []

    def register(self, pad: PadDeMentira, _eventos: int) -> None:
        self.registrados.append(pad)

    def select(self, timeout: float) -> list[tuple[_Chave, int]]:
        alvo = self.relogio.agora + timeout
        proximos = [t for p in self.registrados if (t := p.proximo()) is not None]
        if proximos and min(proximos) <= alvo:
            self.relogio.agora = max(self.relogio.agora, min(proximos))
        else:
            self.relogio.agora = alvo
        return [(_Chave(p), 1) for p in self.registrados if p.pendentes()]

    def get_map(self) -> dict[int, _Chave]:
        return {i: _Chave(p) for i, p in enumerate(self.registrados)}

    def close(self) -> None:
        pass


def aperto(pad: PadDeMentira, botao: str, descida: float, duracao: float) -> None:
    from evdev import ecodes

    codigo = ecodes.ecodes[botao]
    pad.eventos += [Evento(ecodes.EV_KEY, codigo, 1, descida),
                    Evento(ecodes.EV_SYN, 0, 0, descida),
                    Evento(ecodes.EV_KEY, codigo, 0, descida + duracao),
                    Evento(ecodes.EV_SYN, 0, 0, descida + duracao)]


# ---------------------------------------------------------------------------
# O `state_full` de mentira: os cartões, e o que cada um tem apertado em cada hora
# ---------------------------------------------------------------------------


@dataclass
class Cena:
    relogio: Relogio
    jogadores: tuple[int, ...] = (1, 2, 3, 4)
    #: (jogador, botão, de, até)
    apertados: list[tuple[int, str, float, float]] = field(default_factory=list)
    mudo: bool = False
    perguntas: int = 0

    def estado_do_daemon(self, *, timeout: float = 2.0) -> dict[str, Any]:
        from hefesto_dualsense4unix.interface import mesa_viva

        self.perguntas += 1
        if self.mudo:
            raise mesa_viva.DaemonMudo("sem socket")
        agora = self.relogio.agora
        controles = []
        for n in self.jogadores:
            botoes = [b for j, b, de, ate in self.apertados if j == n and de <= agora <= ate]
            controles.append({
                "uniq": UNIQS[n - 1], "connected": True, "player_slot": n, "player": n,
                "transport": "bt", "index": n - 1,
                "inputs": {"buttons": botoes, "l2_raw": 0, "r2_raw": 0},
            })
        return {"controllers": controles}


# ---------------------------------------------------------------------------
# A mesa de mentira no disco: os vpads uhid, os pads uinput e os físicos
# ---------------------------------------------------------------------------


def _no_de_entrada(dir_device: Path, input_n: int, event_n: int, nome: str) -> str:
    pasta = dir_device / "input" / f"input{input_n}"
    (pasta / f"event{event_n}").mkdir(parents=True)
    (pasta / "name").write_text(nome + "\n", encoding="utf-8")
    return f"/dev/input/event{event_n}"


def vpad_uhid(qq: ModuleType, raiz: Path, jogador: int) -> tuple[Any, str]:
    dir_device = raiz / f"vpad{jogador}"
    caminho = _no_de_entrada(dir_device, 40 + jogador, 40 + jogador,
                             f"DualSense Edge (Hefesto P{jogador})")
    aparelho = qq.Aparelho(
        hidraw=f"hidraw{20 + jogador}", caminho_hidraw=f"/dev/hidraw{20 + jogador}",
        dir_device=str(dir_device), mac=f"02:fe:00:00:00:0{jogador}",
        nome=f"DualSense Edge (Hefesto P{jogador})", transporte=sys.modules["comum"].VPAD,
        e_vpad=True, rotulo=f"P{jogador}")
    return aparelho, caminho


def controle_fisico(qq: ModuleType, raiz: Path, jogador: int, led: str = "") -> tuple[Any, str]:
    dir_device = raiz / f"controle{jogador}"
    caminho = _no_de_entrada(dir_device, 10 + jogador, 10 + jogador,
                             "Sony Interactive Entertainment DualSense Wireless Controller")
    if led:
        for i, aceso in enumerate(led, start=1):
            pasta = dir_device / "leds" / f"input{10 + jogador}:white:player-{i}"
            pasta.mkdir(parents=True)
            (pasta / "brightness").write_text(aceso + "\n", encoding="utf-8")
    aparelho = qq.Aparelho(
        hidraw=f"hidraw{jogador}", caminho_hidraw=f"/dev/hidraw{jogador}",
        dir_device=str(dir_device), mac=UNIQS[jogador - 1],
        nome="Sony Interactive Entertainment DualSense Wireless Controller",
        transporte="rádio", e_vpad=False, rotulo="")
    return aparelho, caminho


def pads_uinput(raiz_sys: Path, quantos: int, nome: str) -> list[str]:
    caminhos = []
    for i in range(quantos):
        input_n, event_n = 70 + i, 90 + i
        morada = raiz_sys / "devices" / "virtual" / "input" / f"input{input_n}"
        morada.mkdir(parents=True)
        (morada / "name").write_text(nome + "\n", encoding="utf-8")
        classe = raiz_sys / "class" / "input" / f"event{event_n}"
        classe.mkdir(parents=True)
        (classe / "device").symlink_to(morada, target_is_directory=True)
        caminhos.append(f"/dev/input/event{event_n}")
    return caminhos


def _nome_do_pad_xbox() -> str:
    from hefesto_dualsense4unix.integrations.uinput_gamepad import FLAVORS, XBOX360_NAME

    nomes = {str(d["name"]) for d in FLAVORS.values()}
    assert XBOX360_NAME in nomes
    return str(XBOX360_NAME)


# ---------------------------------------------------------------------------
# O mundo: a porta da casa, o dono do grab e o daemon, trocados em TODO teste
# ---------------------------------------------------------------------------


@dataclass
class Mundo:
    relogio: Relogio
    cena: Cena
    pads: dict[str, PadDeMentira]
    raiz_sys: Path
    abertos: list[str] = field(default_factory=list)
    grab: dict[str, str] = field(default_factory=dict)
    grabs_perguntados: list[str] = field(default_factory=list)

    def pad(self, caminho: str) -> PadDeMentira:
        return self.pads.setdefault(caminho, PadDeMentira(caminho, self.relogio))


@pytest.fixture
def mundo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, tela: Any) -> Mundo:
    from hefesto_dualsense4unix.core import evdev_reader
    from hefesto_dualsense4unix.integrations import hidraw_broker_client
    from hefesto_dualsense4unix.interface import mesa_viva

    relogio = Relogio()
    raiz_sys = tmp_path / "sys"
    raiz_sys.mkdir()
    m = Mundo(relogio, Cena(relogio), {}, raiz_sys)

    def abrir(caminho: Any, **_: Any) -> PadDeMentira:
        m.abertos.append(str(caminho))
        return m.pad(str(caminho))

    def grab(caminho: str, **_: Any) -> str:
        m.grabs_perguntados.append(caminho)
        return str(m.grab.get(caminho, hidraw_broker_client.GRAB_LIVRE))

    monkeypatch.setattr(evdev_reader, "abrir_input_device", abrir)
    monkeypatch.setattr(hidraw_broker_client, "estado_do_grab", grab)
    monkeypatch.setattr(mesa_viva, "estado_do_daemon", m.cena.estado_do_daemon)
    return m


def rodar(qq: ModuleType, m: Mundo, aparelhos: list[Any]) -> int | None:
    return qq.ensaio_de_aperto(  # type: ignore[no-any-return]
        aparelhos, JANELA_S, raiz_sys=str(m.raiz_sys), relogio=m.relogio,
        novo_seletor=lambda: SeletorDeMentira(m.relogio))


def quatro_vpads(qq: ModuleType, tmp_path: Path) -> tuple[list[Any], list[str]]:
    pares = [vpad_uhid(qq, tmp_path, n) for n in range(1, 5)]
    return [a for a, _ in pares], [c for _, c in pares]


def linhas_do(saida: str, marca: str) -> list[str]:
    return [linha for linha in saida.splitlines() if marca in linha]


# ---------------------------------------------------------------------------
# As réguas
# ---------------------------------------------------------------------------


def test_regua_1_sem_aperto_nada_medido(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                         capsys: pytest.CaptureFixture[str]) -> None:
    """Pad calado e estado vazio nos quatro: «nada medido», rc 3.

    MORDIDA: sem a guarda da testemunha (julgar pela tela vazia), o ensaio diz
    que a tela não acendeu, e o rc sai 2.
    """
    aparelhos, _ = quatro_vpads(qq, tmp_path)
    rc = rodar(qq, mundo, aparelhos)
    saida = capsys.readouterr().out
    assert rc == qq.RC_NADA_MEDIDO == 3
    assert "Nenhum aperto medido na janela — nada medido" in saida
    assert "não acendeu" not in saida
    tiques = int(JANELA_S * 1000 / 100)
    assert mundo.cena.perguntas >= tiques - 1, "a tela não foi lida a cada tique"


def test_regua_1_o_daemon_mudo_nao_e_estado_vazio(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    """A tela que levanta `DaemonMudo` e um X de 300 ms: «a tela não respondeu», rc 3.

    MORDIDA: tratar o daemon mudo como estado vazio dá FALHA (rc 2).
    """
    aparelhos, caminhos = quatro_vpads(qq, tmp_path)
    mundo.cena.mudo = True
    aperto(mundo.pad(caminhos[1]), "BTN_SOUTH", INICIO + 1.0, 0.3)
    rc = rodar(qq, mundo, aparelhos)
    saida = capsys.readouterr().out
    assert rc == 3
    assert "A tela não respondeu — nada medido" in saida
    assert "FALHA" not in saida


def test_regua_2_a_testemunha_nao_sai_do_estado(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    """Um X de 300 ms no pad do P2 e o estado vazio nos quatro: FALHA, rc 2.

    MORDIDA: uma testemunha derivada do próprio estado (os apertos lidos do
    `state_full`) não vê aperto nenhum e diz «nada medido» — a trava contra a
    própria saída.
    """
    aparelhos, caminhos = quatro_vpads(qq, tmp_path)
    aperto(mundo.pad(caminhos[1]), "BTN_SOUTH", INICIO + 1.0, 0.3)
    rc = rodar(qq, mundo, aparelhos)
    saida = capsys.readouterr().out
    assert rc == qq.RC_FALHA == 2
    (linha,) = linhas_do(saida, "no pad uhid P2")
    assert "FALHA — não acendeu cartão nenhum" in linha
    assert linha.strip().startswith("cross ")


def _o_x_do_p2(qq: ModuleType, m: Mundo, tmp_path: Path, acende: tuple[int, ...]) -> list[Any]:
    aparelhos, caminhos = quatro_vpads(qq, tmp_path)
    descida = INICIO + 1.02
    aperto(m.pad(caminhos[1]), "BTN_SOUTH", descida, 0.3)
    for jogador in acende:
        # a tela acende no tique seguinte à descida e apaga um tique depois da subida
        m.cena.apertados.append((jogador, "cross", descida + 0.05, descida + 0.35))
    return aparelhos


def test_regua_3_acendeu_o_cartao_dele(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                        capsys: pytest.CaptureFixture[str]) -> None:
    """X de 300 ms no pad do P2, `cross` no cartão do P2 em três tiques: acendeu, sem rc próprio.

    `None` é «vale o rc da tabela» (o aviso do LED fica; ver a régua 10).
    """
    aparelhos = _o_x_do_p2(qq, mundo, tmp_path, acende=(2,))
    rc = rodar(qq, mundo, aparelhos)
    saida = capsys.readouterr().out
    assert rc is None
    (linha,) = linhas_do(saida, "no pad uhid P2")
    assert "acendeu só o cartão P2" in linha and "FALHA" not in linha
    assert "1 aperto(s) medido(s), cada um com o cartão dele" in saida


def test_regua_3_a_mordida_o_cartao_de_outro_jogador(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                                      capsys: pytest.CaptureFixture[str]) -> None:
    """O mesmo aperto com o `cross` só no P3: o nó diz P2, e é FALHA."""
    aparelhos = _o_x_do_p2(qq, mundo, tmp_path, acende=(3,))
    rc = rodar(qq, mundo, aparelhos)
    saida = capsys.readouterr().out
    assert rc == 2
    (linha,) = linhas_do(saida, "no pad uhid P2")
    assert "FALHA — acendeu o cartão P3, que é de outro jogador (o nó é do P2)" in linha


def test_regua_4_um_cartao_so(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                               capsys: pytest.CaptureFixture[str]) -> None:
    """O mesmo aperto com `cross` no P2 e no P3: FALHA.

    MORDIDA: um veredito que aceita «algum cartão acendeu» passa com rc 0.
    """
    aparelhos = _o_x_do_p2(qq, mundo, tmp_path, acende=(2, 3))
    rc = rodar(qq, mundo, aparelhos)
    saida = capsys.readouterr().out
    assert rc == 2
    (linha,) = linhas_do(saida, "no pad uhid P2")
    assert "FALHA — acendeu mais de um cartão: P2 (cross), P3 (cross)" in linha


def test_regua_5_o_aperto_curto_nao_e_medido(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                              capsys: pytest.CaptureFixture[str]) -> None:
    """Um X de 60 ms entre dois tiques, sem nada aceso: «curto demais» e «nada medido», rc 3.

    MORDIDA: tratar o curto como FALHA dá rc 2; contá-lo como medido dá rc 0.
    """
    aparelhos, caminhos = quatro_vpads(qq, tmp_path)
    aperto(mundo.pad(caminhos[0]), "BTN_SOUTH", INICIO + 1.02, 0.06)
    rc = rodar(qq, mundo, aparelhos)
    saida = capsys.readouterr().out
    assert rc == 3
    (linha,) = linhas_do(saida, "no pad uhid P1")
    assert "curto demais para o tique da tela" in linha and "FALHA" not in linha
    assert "nada medido" in saida


def test_regua_5_o_curto_com_um_aperto_medido(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                               capsys: pytest.CaptureFixture[str]) -> None:
    """O X curto e um segundo X, de 300 ms, que acende o cartão dele: sem rc próprio."""
    aparelhos, caminhos = quatro_vpads(qq, tmp_path)
    aperto(mundo.pad(caminhos[0]), "BTN_SOUTH", INICIO + 1.02, 0.06)
    aperto(mundo.pad(caminhos[0]), "BTN_SOUTH", INICIO + 2.02, 0.3)
    mundo.cena.apertados.append((1, "cross", INICIO + 2.05, INICIO + 2.35))
    rc = rodar(qq, mundo, aparelhos)
    saida = capsys.readouterr().out
    assert rc is None
    curto, medido = linhas_do(saida, "no pad uhid P1")
    assert "curto demais" in curto
    assert "acendeu só o cartão P1" in medido


def test_regua_6_o_modo_xbox_abre_os_pads_uinput(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                                  capsys: pytest.CaptureFixture[str]) -> None:
    """Quatro nós uinput com o nome do `FLAVORS` e a morada do uinput: o ensaio abre os quatro.

    O nó uinput não diz o jogador: a linha diz o cartão que acendeu.
    MORDIDA: com a descoberta só por `/sys/class/hidraw`, nenhum nó abre e a
    régua reprova; e os físicos não são testemunha quando há pad.
    """
    caminhos = pads_uinput(mundo.raiz_sys, 4, _nome_do_pad_xbox())
    fisicos = [controle_fisico(qq, tmp_path, n)[0] for n in range(1, 5)]
    aperto(mundo.pad(caminhos[2]), "BTN_SOUTH", INICIO + 1.02, 0.3)
    mundo.cena.apertados.append((3, "cross", INICIO + 1.05, INICIO + 1.35))
    rc = rodar(qq, mundo, fisicos)
    saida = capsys.readouterr().out
    assert sorted(mundo.abertos) == sorted(caminhos)
    assert rc is None
    (linha,) = linhas_do(saida, f"no pad uinput {caminhos[2]}")
    assert "acendeu só o cartão P3" in linha


def test_regua_6_o_espelho_de_outro_nome_nao_e_pad(qq: ModuleType, mundo: Mundo) -> None:
    """A morada do uinput com outro nome (o espelho do Steam Input) fica de fora: o dono decide."""
    pads_uinput(mundo.raiz_sys, 1, "Microsoft X-Box 360 pad 0")
    assert qq.testemunhas_da_mesa([], str(mundo.raiz_sys)) == []


def test_regua_7_o_dono_do_aceso_e_o_da_tela(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                              capsys: pytest.CaptureFixture[str]) -> None:
    """O estado traz `create` no P1 e o pad um `BTN_SELECT`: a tela acendeu `share`.

    MORDIDA: comparar com o `inputs.buttons` cru dá `create` no lado da tela.
    """
    aparelhos, caminhos = quatro_vpads(qq, tmp_path)
    aperto(mundo.pad(caminhos[0]), "BTN_SELECT", INICIO + 1.02, 0.3)
    mundo.cena.apertados.append((1, "create", INICIO + 1.05, INICIO + 1.35))
    rc = rodar(qq, mundo, aparelhos)
    saida = capsys.readouterr().out
    assert rc is None
    (linha,) = linhas_do(saida, "no pad uhid P1")
    assert linha.strip().startswith("create no pad uhid P1")
    assert linha.endswith("a tela acendeu share")


def test_regua_8_a_troca_de_botao(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                   capsys: pytest.CaptureFixture[str]) -> None:
    """O pad vê `BTN_EAST` e o estado traz `cross` no mesmo cartão: acendeu, e a linha diz os dois.

    MORDIDA: exigir o mesmo nome nos dois lados dá FALHA.
    """
    aparelhos, caminhos = quatro_vpads(qq, tmp_path)
    aperto(mundo.pad(caminhos[3]), "BTN_EAST", INICIO + 1.02, 0.3)
    mundo.cena.apertados.append((4, "cross", INICIO + 1.05, INICIO + 1.35))
    rc = rodar(qq, mundo, aparelhos)
    saida = capsys.readouterr().out
    assert rc is None
    (linha,) = linhas_do(saida, "no pad uhid P4")
    assert linha.strip().startswith("circle no pad uhid P4")
    assert "acendeu só o cartão P4; a tela acendeu cross" in linha


def test_regua_9_o_nativo_segurado_por_outro(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                              capsys: pytest.CaptureFixture[str]) -> None:
    """Sem pad, a testemunha é o físico pela porta da casa, e o nó calado sai pelo dono do zero.

    MORDIDA: com `evdev.InputDevice` direto no lugar de `abrir_input_device`,
    a porta de mentira não é chamada; com um texto próprio no lugar de
    `leitura_de_zero`, a frase não bate com a do dono.
    """
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as dono

    par = [controle_fisico(qq, tmp_path, n) for n in (1, 3)]
    mundo.cena.jogadores = (1, 3)
    for _, caminho in par:
        mundo.grab[caminho] = dono.GRAB_DE_TERCEIRO
    rc = rodar(qq, mundo, [a for a, _ in par])
    saida = capsys.readouterr().out
    assert mundo.abertos == [c for _, c in par]
    assert rc == 3
    for _, caminho in par:
        (linha,) = linhas_do(saida, f"({caminho}):")
        assert linha.endswith(dono.leitura_de_zero(dono.GRAB_DE_TERCEIRO))


def test_regua_9_o_nativo_confere_o_cartao_pelo_endereco(
    qq: ModuleType, mundo: Mundo, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """O físico do P3 que acende o cartão do P1: o endereço diz de quem é o cartão, e é FALHA."""
    par = [controle_fisico(qq, tmp_path, n) for n in (1, 3)]
    mundo.cena.jogadores = (1, 3)
    aperto(mundo.pad(par[1][1]), "BTN_SOUTH", INICIO + 1.02, 0.3)
    mundo.cena.apertados.append((1, "cross", INICIO + 1.05, INICIO + 1.35))
    rc = rodar(qq, mundo, [a for a, _ in par])
    saida = capsys.readouterr().out
    assert rc == 2
    (linha,) = linhas_do(saida, f"no físico {UNIQS[2]}")
    assert "acendeu o cartão P1, que é de outro jogador (o nó é do P3)" in linha
    # e o P1, que não apertou nada, sai pelo dono do zero, livre
    (calado,) = linhas_do(saida, f"({par[0][1]}):")
    assert calado.endswith("0 (o controle não emitiu)")


def test_regua_12_o_botao_sem_glifo_nao_e_falha(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    """O L3 não tem glifo na grade: sem nada aceso, não é FALHA, e também não é medida.

    Quem diz que não há glifo é o `leitura_viva`, perguntado com o nome.
    MORDIDA: tratar o botão sem glifo como FALHA dá rc 2.
    """
    aparelhos, caminhos = quatro_vpads(qq, tmp_path)
    aperto(mundo.pad(caminhos[0]), "BTN_THUMBL", INICIO + 1.02, 0.3)
    rc = rodar(qq, mundo, aparelhos)
    saida = capsys.readouterr().out
    assert rc == 3
    (linha,) = linhas_do(saida, "no pad uhid P1")
    assert "a grade não tem glifo para l3 — nada medido" in linha


# ---------------------------------------------------------------------------
# O rc inteiro: a régua 10 roda o `main`, com a tabela e o aperto
# ---------------------------------------------------------------------------


def _main_com_led_repetido(qq: ModuleType, m: Mundo, tmp_path: Path,
                           monkeypatch: pytest.MonkeyPatch, acende: int) -> int:
    import functools

    dois = [controle_fisico(qq, tmp_path, n, led="00100")[0] for n in (1, 2)]  # os dois dizem P1
    vpad2, caminho2 = vpad_uhid(qq, tmp_path, 2)
    aperto(m.pad(caminho2), "BTN_SOUTH", INICIO + 1.02, 0.3)
    m.cena.apertados.append((acende, "cross", INICIO + 1.05, INICIO + 1.35))
    monkeypatch.setattr(qq, "descobrir_aparelhos", lambda: [*dois, vpad2])
    monkeypatch.setattr(qq, "cabecalho_do_instrumento", lambda *a, **k: "")
    monkeypatch.setattr(qq, "ensaio_de_aperto", functools.partial(
        qq.ensaio_de_aperto, raiz_sys=str(m.raiz_sys), relogio=m.relogio,
        novo_seletor=lambda: SeletorDeMentira(m.relogio)))
    monkeypatch.setattr(qq, "CONHECIDOS", [])
    return int(qq.main(["--apertar", "--segundos", str(JANELA_S)]))


def test_regua_10_o_aviso_do_led_nao_some(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch,
                                           capsys: pytest.CaptureFixture[str]) -> None:
    """O aperto certo com o LED de jogador repetido na tabela: rc 1.

    MORDIDA: um rc 0 fixo quando o aperto passa esconde a divergência.
    """
    rc = _main_com_led_repetido(qq, mundo, tmp_path, monkeypatch, acende=2)
    saida = capsys.readouterr().out
    assert "P1 está aceso em 2 controles" in saida
    assert "acendeu só o cartão P2" in saida
    assert rc == 1


def test_regua_10_a_falha_vence_o_led(qq: ModuleType, mundo: Mundo, tmp_path: Path,
                                       monkeypatch: pytest.MonkeyPatch,
                                       capsys: pytest.CaptureFixture[str]) -> None:
    """A FALHA do aperto vence o aviso do LED: rc 2."""
    assert _main_com_led_repetido(qq, mundo, tmp_path, monkeypatch, acende=3) == 2
    capsys.readouterr()


# ---------------------------------------------------------------------------
# A régua 11: a tabela e o `--json` não dependem da tela
# ---------------------------------------------------------------------------

_SEM_GI = textwrap.dedent('''
    import importlib.util, json, sys
    sys.modules["gi"] = None  # o `import gi` levanta ImportError
    ensaios, aparelhos, argv = sys.argv[1], json.loads(sys.argv[2]), sys.argv[3:]
    sys.path.insert(0, ensaios)
    spec = importlib.util.spec_from_file_location("quem_e_quem", ensaios + "/quem_e_quem.py")
    qq = importlib.util.module_from_spec(spec)
    sys.modules["quem_e_quem"] = qq
    spec.loader.exec_module(qq)
    qq.descobrir_aparelhos = lambda: [qq.Aparelho(**a) for a in aparelhos]
    qq.cabecalho_do_instrumento = lambda *a, **k: ""
    rc = qq.main(argv)
    print("RC=" + str(rc))
''')


def _sem_gi(tmp_path: Path, argv: list[str]) -> subprocess.CompletedProcess[str]:
    import dataclasses

    qq = _carregar()
    aparelhos = [dataclasses.asdict(controle_fisico(qq, tmp_path, n, led=led)[0])
                 for n, led in ((1, "00100"), (2, "01010"))]
    ambiente = dict(os.environ)
    ambiente["PYTHONPATH"] = str(RAIZ / "src")
    # o lar de mentira: nada do que este processo importa acha a pasta dela
    ambiente["HOME"] = str(tmp_path / "lar")
    for chave in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        ambiente[chave] = str(tmp_path / "lar" / chave.lower())
    return subprocess.run(
        [sys.executable, "-c", _SEM_GI, str(ENSAIOS), json.dumps(aparelhos), *argv],
        capture_output=True, text=True, timeout=120, env=ambiente, check=False, cwd=str(tmp_path))


def _chaves_que_o_o_basico_le() -> tuple[set[str], set[str]]:
    """As chaves do `--json` que o `o_basico.py` lê, tiradas do contrato dele (outro dono)."""
    contrato = RAIZ / "tests" / "unit" / "test_o_basico_o_contrato.py"
    spec = importlib.util.spec_from_file_location("contrato_do_o_basico", contrato)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    forma = json.loads(modulo.quem_e_quem_json(None, modulo.estado_da_mesa()))
    return set(forma), set(forma["fisicos"][0])


def test_regua_11_o_json_nao_depende_da_tela(tmp_path: Path) -> None:
    """Com o `import gi` levantando, o `--json` termina e traz as chaves que o `o_basico.py` lê.

    MORDIDA: com o import do `hefesto_vivo` no topo do módulo, o `--json`
    quebra no import, e a régua reprova.
    """
    feito = _sem_gi(tmp_path, ["--json"])
    assert "Traceback" not in feito.stderr, feito.stderr
    corpo, _, fim = feito.stdout.rpartition("RC=")
    assert fim.strip() == "0", feito.stdout
    dado = json.loads(corpo)
    de_cima, do_fisico = _chaves_que_o_o_basico_le()
    assert de_cima <= set(dado)
    assert len(dado["fisicos"]) == 2
    assert all(do_fisico <= set(f) for f in dado["fisicos"])
    assert [f["led_jogador"] for f in dado["fisicos"]] == [1, 2]


def test_regua_11_sem_a_tela_o_apertar_diz_nada_medido(tmp_path: Path) -> None:
    """Sem o pacote da interface, o `--apertar` diz «a tela não se lê aqui — nada medido», rc 3.

    Nenhum nó é aberto: a tela é importada antes da testemunha.
    """
    feito = _sem_gi(tmp_path, ["--apertar", "--segundos", "0.1"])
    assert "Traceback" not in feito.stderr, feito.stderr
    assert "A tela não se lê aqui" in feito.stdout and "nada medido" in feito.stdout
    assert feito.stdout.rstrip().endswith("RC=3")


def test_o_modulo_nao_importa_a_interface_no_topo() -> None:
    """O import da tela mora dentro do `_a_tela`, e só ali (o `--json` vai no pacote)."""
    import ast

    arvore = ast.parse(ENSAIO.read_text(encoding="utf-8"))
    no_topo: list[str] = []
    for no in arvore.body:
        if isinstance(no, ast.ImportFrom) and no.module:
            no_topo.append(no.module)
        elif isinstance(no, ast.Import):
            no_topo.extend(a.name for a in no.names)
    assert not [m for m in no_topo if m == "gi" or ".interface" in m], no_topo


def test_o_tique_e_o_leitor_sao_os_da_tela(qq: ModuleType, tela: Any) -> None:
    """O ensaio lê pelo `mesa_viva`, acende pelo `leitura_viva` e anda no `TIQUE_MS` do piloto."""
    from hefesto_dualsense4unix.interface import hefesto_vivo, mesa_viva
    from hefesto_dualsense4unix.interface.pacotes import a02_controles

    modulo, leitura_viva, mesa_do_estado, tique = tela
    assert modulo is mesa_viva
    assert leitura_viva is a02_controles.leitura_viva
    assert mesa_do_estado is mesa_viva.mesa_do_estado
    assert tique == hefesto_vivo.TIQUE_MS
