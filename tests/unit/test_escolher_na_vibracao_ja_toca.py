"""Escolher na aba Vibração já toca (ESCOLHER-NA-VIBRACAO-JA-TOCA-01, 23/10/2026).

Como o gatilho e a luz aplicam na hora, a escolha nas duas listas da coluna toca uma vez no
controle daquela coluna: o padrão dos motores pelo `rumble_set_checked` (e devolve ao jogo), a
forma háptica pelo `haptica_testar` ligado e desligado. «Sem efeito» e a gravação recusada não
tocam. D-2310-ESCOLHER-NA-VIBRACAO-JA-TOCA.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as padroes
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

AZUL = "aa:bb:cc:00:00:01"
BRANCO = "aa:bb:cc:00:00:02"


def _item(uniq: str, pref: str, jogador: int) -> dict[str, Any]:
    return {"uniq": uniq, "pref": pref, "jogador": jogador, "nome": "Prova", "cor": "",
            "transporte": "usb", "via": "cabo", "alvo": True, "mascara": "dualsense"}


def _ctx() -> pacotes.Contexto:
    controles = [{"uniq": u, "connected": True, "player": n, "transport": "usb"}
                 for n, u in ((1, AZUL), (2, BRANCO))]
    state = {"controllers": controles, "rumble_policy": "max", "active_profile": ""}
    return pacotes.Contexto(state=state, mesa=[_item(AZUL, "p1", 1), _item(BRANCO, "p2", 2)],
                            conectados=controles, estados={}, externos=[])


class _Ponte:
    """A ponte do app: grava com `ok` (ou recusa) e anota todo pedido em ordem."""

    def __init__(self, grava: str = "ok", haptica: str = "ok") -> None:
        self.grava = grava
        self.haptica = haptica
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def rumble_motores_set(self, **k: Any) -> tuple[bool, dict[str, Any]]:
        self.chamadas.append(("rumble_motores_set", (), k))
        return True, {"status": self.grava, "motivo": "recusado de prova"}

    def haptica_testar(self, uniq: str, ligado: bool) -> tuple[bool, dict[str, Any]]:
        self.chamadas.append(("haptica_testar", (uniq, ligado), {}))
        return True, {"status": self.haptica if ligado else "ok"}

    def __getattr__(self, nome: str) -> Any:
        def registrar(*a: Any, **k: Any) -> Any:
            self.chamadas.append((nome, a, k))
            return (True, None) if nome.endswith("_checked") else True
        return registrar

    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]

    def de(self, nome: str) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
        return [(a, k) for n, a, k in self.chamadas if n == nome]


@pytest.fixture(autouse=True)
def _sem_espera_nem_marca(monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setattr(a05, "_segurar", lambda _s: None)
    monkeypatch.setattr(a05, "_perfil_ativo", lambda _ctx: {})
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()
    yield
    a05.parar_o_teste()
    a05.parar_o_teste_da_haptica()


def _escolher(gesto: str, uniq: str, valor: str, ponte: _Ponte) -> None:
    feito = pacotes.gesto_da_pagina("05-vibracao.html", gesto)
    assert feito is not None
    feito(_ctx(), {"uniq": uniq, "valor": valor}, ponte)


class TestOPadraoDosMotores:
    def test_escolher_o_ressoar_toca_a_sequencia_no_controle_da_coluna(self) -> None:
        """MORDIDA: arrancar o toque do `efeito_imersao` deixa a lista de sets vazia.

        Prova da D-2310-ESCOLHER-NA-VIBRACAO-JA-TOCA.
        """
        ponte = _Ponte()
        _escolher(a05.GESTO_DO_EFEITO_IMERSAO, BRANCO, "ressoar", ponte)
        sets = ponte.de("rumble_set_checked")
        esperados = len(padroes.sequencia("ressoar", padroes.AMBOS))
        assert len(sets) == esperados and esperados > 0
        assert all(k == {"uniq": BRANCO} for _a, k in sets)
        assert ponte.nomes()[0] == "rumble_motores_set", "tocou antes de gravar"
        assert ponte.de("rumble_passthrough") == [((True, BRANCO), {})], "não devolveu ao jogo"
        assert BRANCO not in a05.em_teste(), "a escolha ficou repetindo como o Testar"

    def test_sem_efeito_grava_e_nao_toca(self) -> None:
        ponte = _Ponte()
        _escolher(a05.GESTO_DO_EFEITO_IMERSAO, AZUL, "sem_efeito", ponte)
        assert ponte.nomes() == ["rumble_motores_set"]

    def test_do_estilo_toca_o_padrao_do_estilo_e_nada_sem_ele(
            self, monkeypatch: pytest.MonkeyPatch) -> None:
        estilo, padrao = next(iter(padroes.POR_ESTILO.items()))
        monkeypatch.setattr(a05, "_perfil_ativo", lambda _ctx: {"estilo": estilo})
        ponte = _Ponte()
        _escolher(a05.GESTO_DO_EFEITO_IMERSAO, AZUL, "do_estilo", ponte)
        assert len(ponte.de("rumble_set_checked")) == len(padroes.sequencia(padrao)), padrao
        monkeypatch.setattr(a05, "_perfil_ativo", lambda _ctx: {})
        sem = _Ponte()
        _escolher(a05.GESTO_DO_EFEITO_IMERSAO, AZUL, "do_estilo", sem)
        assert sem.nomes() == ["rumble_motores_set"]

    def test_a_escolha_substitui_a_haptica_ligada_no_mesmo_controle(self) -> None:
        a05.testar_haptica(_ctx(), {"uniq": AZUL}, _Ponte())
        assert AZUL in a05.em_teste_da_haptica()
        ponte = _Ponte()
        _escolher(a05.GESTO_DO_EFEITO_IMERSAO, AZUL, "batida", ponte)
        assert AZUL not in a05.em_teste_da_haptica()
        assert ponte.de("haptica_testar") == [((AZUL, False), {})]


class TestAFormaHaptica:
    def test_escolher_o_eco_toca_uma_vez_e_cala(self) -> None:
        """MORDIDA: arrancar o toque do `efeito_haptico` deixa o tocador sem pedido."""
        ponte = _Ponte()
        _escolher(a05.GESTO_DO_EFEITO_HAPTICO, BRANCO, "eco", ponte)
        assert ponte.de("haptica_testar") == [((BRANCO, True), {}), ((BRANCO, False), {})]
        assert BRANCO not in a05.em_teste_da_haptica(), "o coração rebateria até o «Parar»"

    def test_o_daemon_sem_efeito_nao_deixa_recusa_nem_desliga(self) -> None:
        ponte = _Ponte(haptica="sem_efeito")
        _escolher(a05.GESTO_DO_EFEITO_HAPTICO, AZUL, "sem_efeito", ponte)
        assert ponte.de("haptica_testar") == [((AZUL, True), {})]

    def test_a_escolha_substitui_o_testar_ligado(self) -> None:
        a05.testar(_ctx(), {"uniq": AZUL}, _Ponte())
        assert AZUL in a05.em_teste()
        ponte = _Ponte()
        _escolher(a05.GESTO_DO_EFEITO_HAPTICO, AZUL, "estalo", ponte)
        assert AZUL not in a05.em_teste()
        assert ponte.nomes().index("rumble_passthrough") < ponte.nomes().index("haptica_testar")


class TestARecusaECadaColuna:
    @pytest.mark.parametrize(("gesto", "valor"), [
        (a05.GESTO_DO_EFEITO_IMERSAO, "ressoar"), (a05.GESTO_DO_EFEITO_HAPTICO, "eco")])
    def test_gravacao_recusada_nao_toca(self, gesto: str, valor: str) -> None:
        ponte = _Ponte(grava="recusado")
        with pytest.raises(RuntimeError, match="recusado de prova"):
            _escolher(gesto, AZUL, valor, ponte)
        assert ponte.nomes() == ["rumble_motores_set"]

    @pytest.mark.parametrize("uniq", [AZUL, BRANCO])
    def test_cada_coluna_toca_no_controle_dela(self, uniq: str) -> None:
        ponte = _Ponte()
        _escolher(a05.GESTO_DO_EFEITO_IMERSAO, uniq, "batida", ponte)
        _escolher(a05.GESTO_DO_EFEITO_HAPTICO, uniq, "toque", ponte)
        alvos = {k.get("uniq") for _a, k in ponte.de("rumble_set_checked")}
        alvos |= {a[0] for a, _k in ponte.de("haptica_testar")}
        assert alvos == {uniq}
