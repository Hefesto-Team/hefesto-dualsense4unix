"""O mudo do Hefesto chega ao nó que os apps ouvem, e só a MUDANÇA o escreve."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.daemon.subsystems.bt_mic import (
    BtMicSubsystem,
    RegistroDePedidosDeCanal,
)
from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
from hefesto_dualsense4unix.integrations import eleicao_de_microfone as elm

A = "aabbcc000011"

B = "aabbcc000022"

C = "aabbcc000033"


class _Source:
    """O nó, sem PipeWire: só o nome e o rótulo."""

    def __init__(self, *, nome: str, descricao: str, **_: object) -> None:
        self.nome = nome
        self.descricao = descricao

    def iniciar(self) -> bool:
        return True

    def parar(self) -> None:
        pass


class _Pactl:
    """O `pactl` de mentira: guarda cada argv e o mudo de cada nó."""

    def __init__(self) -> None:
        self.argvs: list[list[str]] = []
        self.mudo_do_no: dict[str, str] = {}

    def __call__(self, argv: list[str]) -> bool:
        self.argvs.append(list(argv))
        if argv[:2] == ["pactl", "set-source-mute"]:
            self.mudo_do_no[argv[2]] = argv[3]
        return True

    def escritas(self) -> list[tuple[str, str]]:
        return [(a[2], a[3]) for a in self.argvs if a[:2] == ["pactl", "set-source-mute"]]

    def zerar(self) -> None:
        self.argvs.clear()


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch):
    """O registro e o subsystem de VERDADE atrás dos ganchos; só o `pactl` é dublê."""

    class Mesa:
        def __init__(self) -> None:
            self.pactl = _Pactl()
            self.registro = RegistroDePedidosDeCanal()
            self.sub = BtMicSubsystem(registro=self.registro)

        def abrir(self, uniq: str) -> Any:
            return canal.abrir(uniq, "Microfone do Controle", fabrica=_Source)

        def no_de(self, uniq: str) -> str:
            return canal.nome_do_canal(uniq)

    m = Mesa()
    monkeypatch.setattr(canal, "_rodar_pactl", m.pactl)
    for uniq in list(canal.de_pe()):
        canal.fechar(uniq)
    anteriores = elm.registrar_dizedor_do_no_ar(
        m.sub.no_ar, m.sub.esquecer_a_palavra, m.sub.palavra_no_ar
    )
    try:
        yield m
    finally:
        elm.registrar_dizedor_do_no_ar(*anteriores)
        for uniq in list(canal.de_pe()):
            canal.fechar(uniq)


def test_o_ato_chega_ao_no_e_so_ao_no_dele(mesa) -> None:
    """Calar A escreve `1` no nó de A; ligar escreve `0`; esquecer volta a `0`. B não é tocado."""
    mesa.abrir(A)
    mesa.abrir(B)
    mesa.pactl.zerar()

    mesa.sub.no_ar(A, False)
    assert mesa.pactl.escritas() == [(mesa.no_de(A), "1")]

    mesa.pactl.zerar()
    mesa.sub.no_ar(A, True)
    assert mesa.pactl.escritas() == [(mesa.no_de(A), "0")]

    mesa.sub.no_ar(A, False)
    mesa.pactl.zerar()
    mesa.sub.esquecer_a_palavra(A)
    assert mesa.pactl.escritas() == [(mesa.no_de(A), "0")]
    assert mesa.no_de(B) not in {no for no, _ in mesa.pactl.escritas()}


def test_o_nascimento_herda_a_palavra(mesa) -> None:
    """Com a palavra de A em `False`, o canal nasce mudo e nunca desmutado."""
    mesa.sub.no_ar(A, False)
    mesa.pactl.zerar()

    mesa.abrir(A)

    assert mesa.pactl.escritas() == [(mesa.no_de(A), "1")]


def test_o_nascimento_sem_palavra_nasce_aberto(mesa) -> None:
    """Sem palavra nenhuma o nó nasce `0`, escrito, e não herdado do mudo de fábrica."""
    mesa.abrir(A)

    assert mesa.pactl.escritas() == [(mesa.no_de(A), "0")]


def test_o_renascimento_por_rotulo_herda(mesa) -> None:
    """O rótulo que envelhece derruba e reabre o canal, e o novo nasce mudo se A está calado."""
    mesa.abrir(A)
    mesa.sub.no_ar(A, False)
    mesa.pactl.zerar()

    canal.renomear(A, "Microfone do Controle 2", fabrica=_Source)

    escritas = mesa.pactl.escritas()
    assert escritas, "o canal renasceu sem escrever o mudo"
    assert escritas[-1] == (mesa.no_de(A), "1")
    assert (mesa.no_de(A), "0") not in escritas


def _nasce(monkeypatch: pytest.MonkeyPatch, *, saida: str) -> None:
    """Arma uma das três saídas caladas de `_nascer_no_ar_na_vez`."""

    async def pede_silencio(_daemon: Any, _uniq: str) -> bool:
        return saida == "controle"

    monkeypatch.setattr(hotkey, "_ela_desligou_este_microfone", lambda _d, _u: saida == "recusa")
    monkeypatch.setattr(hotkey, "_o_controle_pede_silencio", pede_silencio)
    monkeypatch.setattr(hotkey, "_o_firmware_esta_mudo", lambda _d, _u: saida == "gesto")


@pytest.mark.parametrize("saida", ["recusa", "controle", "gesto"])
def test_o_nascimento_calado_diz_a_palavra(mesa, monkeypatch, saida: str) -> None:
    """As três saídas caladas deixam a palavra `False`, e o nó (já de pé) fecha na volta."""
    mesa.abrir(A)
    _nasce(monkeypatch, saida=saida)
    mesa.pactl.zerar()
    assert mesa.sub.palavra_no_ar(A) is None

    feito = asyncio.run(hotkey._nascer_no_ar_na_vez(object(), A))  # type: ignore[arg-type]

    assert feito is False
    assert mesa.sub.palavra_no_ar(A) is False
    assert mesa.pactl.mudo_do_no[mesa.no_de(A)] == "1"


def test_so_a_mudanca_escreve_e_o_mudo_de_fora_fica(mesa) -> None:
    """Três voltas sem mudança de palavra não escrevem; o mudo posto de fora em B segue."""
    mesa.abrir(A)
    mesa.abrir(B)
    mesa.sub.no_ar(A, False)
    mesa.pactl.mudo_do_no[mesa.no_de(B)] = "1"
    mesa.pactl.zerar()

    for _ in range(3):
        mesa.sub._aplicar_a_palavra_dela()

    assert mesa.pactl.escritas() == []
    assert mesa.pactl.mudo_do_no[mesa.no_de(B)] == "1"


def test_o_cabo_entra_sem_ponte_nenhuma(mesa) -> None:
    """O canal do cabo não passa pelo laço das pontes: o mudo chega por fora dele."""
    assert mesa.sub._gerenciador is None
    mesa.abrir(C)
    mesa.pactl.zerar()

    mesa.sub.no_ar(C, False)

    assert mesa.pactl.escritas() == [(mesa.no_de(C), "1")]


def test_o_que_ja_funcionava_continua(mesa, monkeypatch) -> None:
    """No ar termina em `0`; o jogo calando termina em `1` só no jogador dele; a volta, em `0`."""
    mesa.abrir(A)
    mesa.abrir(B)
    mesa.sub.no_ar(A, False)
    mesa.pactl.zerar()

    class _NoAr:
        def esta(self, _u: str) -> bool:
            return True

    monkeypatch.setattr(hotkey, "_ela_desligou_este_microfone", lambda _d, _u: False)
    monkeypatch.setattr(hotkey, "_o_firmware_esta_mudo", lambda _d, _u: False)

    async def livre(_d: Any, _u: str) -> bool:
        return False

    monkeypatch.setattr(hotkey, "_o_controle_pede_silencio", livre)
    monkeypatch.setattr(hotkey, "_no_ar_da_sessao", lambda _d: _NoAr())
    monkeypatch.setattr(hotkey, "_eleitor", lambda _d: type("E", (), {"eleito": "outro"})())

    assert asyncio.run(hotkey._nascer_no_ar_na_vez(object(), A)) is True  # type: ignore[arg-type]
    assert mesa.pactl.mudo_do_no[mesa.no_de(A)] == "0"

    async def firmware(*_a: Any, **_k: Any) -> Any:
        return hotkey.MetadeDoAto(True, "")

    monkeypatch.setattr(hotkey, "_metade_do_firmware", firmware)
    mesa.pactl.zerar()
    asyncio.run(hotkey.o_jogo_pede_o_mudo(object(), B, True, 1.0))  # type: ignore[arg-type]
    assert mesa.pactl.escritas() == [(mesa.no_de(B), "1")]

    mesa.pactl.zerar()
    asyncio.run(hotkey.o_jogo_pede_o_mudo(object(), B, False, 2.0))  # type: ignore[arg-type]
    assert mesa.pactl.escritas() == [(mesa.no_de(B), "0")]
