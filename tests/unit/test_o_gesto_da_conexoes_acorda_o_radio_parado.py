"""O gesto da Conexões acorda o rádio parado (07/11/2026).

Depois de a leitura parar de ativar o ``org.bluez``, «Conectar» e «Procurar» ficaram mudos com o
Bluetooth parado: sem adaptador não havia molde, a gaveta não abria e ninguém pedia a ativação. O
clique é o gesto que autoriza acordar; o tique nunca.

Dois andares. No de baixo, um ``dbus-daemon`` particular com o ``org.bluez`` ativável de verdade e
o ``busctl`` real preso a ele: a ativação é a do barramento, e o ativador conta. No de cima, o
``Ensaio`` da tela com o ``DonoVivo`` real e a central real sobre o rádio de mentira, que parte
sem o nome no barramento.

MORDIDA: tirar o ``_acordar_o_radio`` do «Conectar», do «Procurar», do ``_mover`` ou do
``_ligar_a_busca``, o molde da gaveta sem adaptador, a linha da falha, ou fazer a leitura acordar
reprova.

Faixa sintética da casa: ``aa:bb:cc``.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, SALA, VERDE, VERMELHO
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    Ensaio,
    id_da_tela,
    preparar_a_tela,
    preparar_o_diario,
)
from tests.unit.test_o_radio_parado_nao_acorda_com_uma_pergunta import Banca, _ha_o_barramento

RAIZ = Path(__file__).resolve().parents[2]
TETO_S = 5.0

_O_BLUETOOTHD = """import os, sys
sys.path.insert(0, {raiz!r})
from tests.unit.test_o_radio_parado_nao_acorda_com_uma_pergunta import BluezDePe
BluezDePe(os.environ["DBUS_STARTER_ADDRESS"])._fio.join()
"""

MESAS = {
    "quatro-cabos": ("usb", "usb", "usb", "usb"),
    "tres-cabos-um-radio": ("usb", "bt", "usb", "usb"),
    "dois-e-dois": ("bt", "usb", "usb", "bt"),
    "um-cabo-tres-radios": ("bt", "bt", "usb", "bt"),
    "quatro-radios": ("bt", "bt", "bt", "bt"),
}


def _ate(condicao: Callable[[], Any], teto: float = TETO_S) -> None:
    fim = time.monotonic() + teto
    while time.monotonic() < fim:
        if condicao():
            return
        time.sleep(0.01)
    raise AssertionError("a condição não chegou no prazo")


class MundoParado(rm.RadioDeMentira):
    """O rádio com o ``bluetoothd`` parado: o ``org.bluez`` só volta pelo ``StartServiceByName``,
    e a recusa do systemd é a da unit que não existe."""

    def __init__(self, *, quebrado: bool = False, **extra: Any) -> None:
        super().__init__(**extra)
        self.bluez_de_pe = False
        self.quebrado = quebrado
        self.pedidos = 0
        self.ativacoes = 0

    def chamar(self, destino: str, caminho: str, interface: str, metodo: str, assinatura: str,
               argumentos: Sequence[Any], *, espera: float) -> bd.Escrita:
        if destino != bd.BARRAMENTO_DBUS or metodo != bd.ACORDAR:
            return super().chamar(destino, caminho, interface, metodo, assinatura, argumentos,
                                  espera=espera)
        assert tuple(argumentos) == (bd.SERVICO, 0)
        self.pedidos += 1
        if self.bluez_de_pe:
            return bd.Escrita(True, resposta=(2,))
        self.ativacoes += 1
        if self.quebrado:
            return bd.Escrita(False, "org.freedesktop.systemd1.NoSuchUnit", "sem a unit")
        self.bluez_de_pe = True
        self._emitir(bd.Sinal("dono", dono_novo=self.DONO_DO_BLUEZ))
        return bd.Escrita(True, resposta=(1,))


class EnsaioParado(Ensaio):
    """O ensaio da tela com uma mesa de controles e a leitura real do dono, sem a guarda da
    suíte (a guarda é para o dono de verdade, e o daqui é o de mentira)."""

    def __init__(self, a08: Any, monkeypatch: pytest.MonkeyPatch, mundo: MundoParado,
                 relogio: rm.Relogio, transportes: tuple[str, ...] = ()) -> None:
        super().__init__(a08, monkeypatch, mundo, relogio)
        self.parado = mundo
        self.transportes = transportes
        self.ar: dict[str, Any] = {}
        monkeypatch.setattr(bd, "dono", lambda: self.dono)
        monkeypatch.setattr(a08, "_ler_se_o_radio_parou", lambda: not self.dono.responde())

    def estado(self) -> dict[str, Any]:
        estado = super().estado()
        estado["controllers"] = [
            {"uniq": f"aa:bb:cc:00:00:0{n}", "transport": transporte, "connected": True,
             "hz_movimento": 150.0, "hz_voz": 0.0, "audio": {"mic_mudo": True}}
            for n, transporte in enumerate(self.transportes, 1)]
        if self.ar:
            estado["radio_ar"] = self.ar
        return estado

    def tique(self) -> dict[str, Any]:
        from hefesto_dualsense4unix.interface.pacotes import em_fundo

        em_fundo.esquecer("bluez-parado")
        return super().tique()

    def moldes(self) -> str:
        return str(self.tique()["radio-moldes"])

    def chips(self) -> int:
        return self.moldes().count('data-gesto="escolher-adaptador"')


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    tela = preparar_a_tela(monkeypatch)
    monkeypatch.setattr(tela, "_O_ACORDAR", {"falhou": False, "ligou_em": None})
    return tela


@pytest.fixture()
def montar(diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch
           ) -> Iterator[Callable[..., EnsaioParado]]:
    vivos: list[EnsaioParado] = []

    def fazer(transportes: tuple[str, ...] = (), *, quebrado: bool = False,
              com_adaptador: bool = True) -> EnsaioParado:
        relogio = rm.Relogio()
        mundo = MundoParado(quebrado=quebrado)
        if not com_adaptador:
            mundo.mesa = {caminho: dado for caminho, dado in mundo.mesa.items()
                          if bd.ADAPTADOR not in dado}
        mundo.fisicos[VERDE] = rm.Fisico(VERDE, rm.CLASSE_DE_CONTROLE)
        ensaio = EnsaioParado(a08, monkeypatch, mundo, relogio, transportes)
        vivos.append(ensaio)
        return ensaio

    try:
        yield fazer
    finally:
        for ensaio in vivos:
            ensaio.parado.bluez_de_pe = True
            ensaio.fechar()


@pytest.mark.parametrize("transportes", MESAS.values(), ids=MESAS.keys())
def test_a_volta_da_tela_sem_clique_nao_acorda_nada(
    montar: Callable[..., EnsaioParado], transportes: tuple[str, ...]
) -> None:
    ensaio = montar(transportes)
    for _ in range(5):
        ensaio.tique()
    assert ensaio.parado.pedidos == 0


@pytest.mark.parametrize("transportes", MESAS.values(), ids=MESAS.keys())
def test_o_conectar_pede_a_ativacao_uma_vez_e_a_gaveta_abre_com_a_resposta(
    montar: Callable[..., EnsaioParado], transportes: tuple[str, ...]
) -> None:
    ensaio = montar(transportes)
    antes = ensaio.moldes()
    assert 'data-painel="conectar"' in antes, "sem o molde, o clique não abre a gaveta"
    assert 'data-pulso="1"' in antes
    assert "escolher-adaptador" not in antes
    assert ensaio.gesto("conectar-aparelho") == {"armou": True}
    assert ensaio.parado.ativacoes == 1
    _ate(ensaio.dono.responde)
    assert ensaio.chips() == len(rm.HCIS)
    assert ensaio.gesto("conectar-aparelho") == {"armou": True}
    assert ensaio.parado.pedidos == 1, "o rádio de pé não se ativa de novo"


def test_a_ativacao_fica_no_diario_do_radio(
    montar: Callable[..., EnsaioParado], diario: Path
) -> None:
    ensaio = montar()
    ensaio.tique()
    ensaio.gesto("conectar-aparelho")
    linhas = [json.loads(linha) for linha in diario.read_text(encoding="utf-8").splitlines()]
    assert [(linha.get("chamada"), linha.get("quem")) for linha in linhas
            if linha.get("chamada") == bd.ACORDAR] == [(bd.ACORDAR, "tela")]


@pytest.mark.parametrize("transportes", MESAS.values(), ids=MESAS.keys())
def test_o_procurar_acorda_e_liga_a_busca_no_adaptador_que_chegou(
    montar: Callable[..., EnsaioParado], a08: Any, monkeypatch: pytest.MonkeyPatch,
    transportes: tuple[str, ...]
) -> None:
    monkeypatch.setattr(a08, "PRAZO_DOS_ADAPTADORES_S", TETO_S * 3)
    ensaio = montar(transportes)
    ensaio.tique()
    assert ensaio.a08._CENA_NA_TELA["destino_do_conectar"] == ""
    parar = threading.Event()

    def voltas_da_tela() -> None:
        while not parar.wait(0.02):
            ensaio.tique()

    tela = threading.Thread(target=voltas_da_tela, daemon=True)
    tela.start()
    comeco = time.monotonic()
    try:
        assert ensaio.gesto("radio-procurar") == {"armou": True}
    finally:
        parar.set()
        tela.join(5.0)
    assert time.monotonic() - comeco < TETO_S, "a volta da tela não avisou o gesto"
    assert ensaio.parado.ativacoes == 1
    pedidos = [p for m, p in ensaio.ponte.chamadas if m == "radio.busca.set"]
    assert len(pedidos) == 1
    assert pedidos[0]["ligada"] is True
    assert pedidos[0]["destino"] in {id_da_tela(e) for e in rm.HCIS}


def test_desligar_a_busca_nao_acorda(montar: Callable[..., EnsaioParado], a08: Any) -> None:
    ensaio = montar()
    ensaio.tique()
    a08._CENA_NA_TELA["procurando"] = a08.PROCURAR_LIGADO
    assert ensaio.gesto("radio-procurar") == {"armou": True}
    assert ensaio.parado.pedidos == 0
    assert [p["ligada"] for m, p in ensaio.ponte.chamadas if m == "radio.busca.set"] == [False]


@pytest.mark.parametrize("gesto", ["conectar-aparelho", "radio-procurar"])
@pytest.mark.parametrize("transportes", MESAS.values(), ids=MESAS.keys())
def test_a_ativacao_que_falha_diz_na_linha_e_o_clique_tenta_de_novo(
    montar: Callable[..., EnsaioParado], a08: Any, gesto: str, transportes: tuple[str, ...]
) -> None:
    ensaio = montar(transportes, quebrado=True)
    ensaio.tique()
    with pytest.raises(RuntimeError, match=a08.BLUETOOTH_NAO_LIGOU):
        ensaio.gesto(gesto)
    assert ensaio.parado.ativacoes == 1
    moldes = ensaio.moldes()
    assert a08.BLUETOOTH_NAO_LIGOU in moldes
    assert 'data-pulso="1"' not in moldes
    with pytest.raises(RuntimeError, match=a08.BLUETOOTH_NAO_LIGOU):
        ensaio.gesto(gesto)
    assert ensaio.parado.ativacoes == 2


def test_o_radio_que_volta_por_fora_limpa_a_linha(
    montar: Callable[..., EnsaioParado], a08: Any
) -> None:
    ensaio = montar(quebrado=True)
    ensaio.tique()
    with pytest.raises(RuntimeError):
        ensaio.gesto("conectar-aparelho")
    ensaio.parado.quebrado = False
    ensaio.parado.chamar(bd.BARRAMENTO_DBUS, "", "", bd.ACORDAR, "su", (bd.SERVICO, 0), espera=1.0)
    _ate(ensaio.dono.responde)
    assert a08.BLUETOOTH_NAO_LIGOU not in ensaio.moldes()


def test_ligou_sem_adaptador_a_gaveta_espera_e_depois_diz(
    montar: Callable[..., EnsaioParado], a08: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    ensaio = montar(com_adaptador=False)
    ensaio.tique()
    ensaio.gesto("conectar-aparelho")
    _ate(ensaio.dono.responde)
    assert 'data-pulso="1"' in ensaio.moldes(), "a gaveta não afirma a falta antes do prazo"
    monkeypatch.setattr(a08, "PRAZO_DOS_ADAPTADORES_S", 0.0)
    moldes = ensaio.moldes()
    assert a08.NENHUM_ADAPTADOR in moldes
    assert 'data-pulso="1"' not in moldes


@pytest.mark.parametrize("com_o_kernel", [False, True], ids=["sem-adaptador", "com-o-do-kernel"])
def test_o_bluetooth_que_ligou_e_caiu_nao_deixa_o_pulso_para_sempre(
    montar: Callable[..., EnsaioParado], a08: Any, monkeypatch: pytest.MonkeyPatch,
    com_o_kernel: bool
) -> None:
    ensaio = montar(("usb", "bt"), com_adaptador=False)
    ensaio.ar = {SALA: {"canais_evitados": []}} if com_o_kernel else {}
    ensaio.tique()
    ensaio.gesto("conectar-aparelho")
    monkeypatch.setattr(a08, "_ler_se_o_radio_parou", lambda: True)
    assert 'data-pulso="1"' in ensaio.moldes(), "dentro do prazo, a gaveta espera"
    monkeypatch.setattr(a08, "PRAZO_DOS_ADAPTADORES_S", 0.0)
    moldes = ensaio.moldes()
    assert a08.BLUETOOTH_NAO_LIGOU in moldes
    assert 'data-pulso="1"' not in moldes


def test_o_clique_que_acorda_manda_a_proxima_volta_reler(
    montar: Callable[..., EnsaioParado]
) -> None:
    """Sem isso, a resposta do rádio esperaria a leitura de 3 s vencer."""
    from hefesto_dualsense4unix.interface.pacotes import em_fundo

    ensaio = montar()
    for chave in ("bluez", "bluez-parado"):
        em_fundo.em_fundo(chave, lambda: "antes", 999.0)
    ensaio.gesto("conectar-aparelho")
    for chave in ("bluez", "bluez-parado"):
        assert em_fundo.em_fundo(chave, lambda: "depois", 999.0) == "depois"


def test_o_clique_novo_troca_a_frase_da_falha_pelo_pulso(
    montar: Callable[..., EnsaioParado], a08: Any
) -> None:
    ensaio = montar(quebrado=True)
    ensaio.tique()
    with pytest.raises(RuntimeError):
        ensaio.gesto("conectar-aparelho")
    assert a08._a_resposta_do_acordar(True, False) == {"frase": a08.BLUETOOTH_NAO_LIGOU}
    ensaio.parado.quebrado = False
    ensaio.gesto("conectar-aparelho")
    assert a08._a_resposta_do_acordar(True, False) == {"pulso": True}


def test_o_adaptador_que_chegou_encerra_a_espera_do_clique(
    montar: Callable[..., EnsaioParado], a08: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Horas depois, o Bluetooth parado de novo não herda a resposta daquele clique."""
    ensaio = montar()
    ensaio.tique()
    ensaio.gesto("conectar-aparelho")
    _ate(ensaio.dono.responde)
    assert ensaio.chips() == len(rm.HCIS)
    monkeypatch.setattr(a08, "PRAZO_DOS_ADAPTADORES_S", 0.0)
    monkeypatch.setattr(a08, "_ler_se_o_radio_parou", lambda: True)
    assert a08.BLUETOOTH_NAO_LIGOU not in ensaio.moldes()


def test_sem_o_servico_na_tela_o_procurar_recusa_sem_acordar(
    montar: Callable[..., EnsaioParado], a08: Any
) -> None:
    ensaio = montar()
    ensaio.tique()
    a08._CENA_NA_TELA["procurando"] = a08.TRAVESSAO_DO_PROCURAR
    with pytest.raises(RuntimeError, match=a08.PROCURAR_RECUSA):
        ensaio.gesto("radio-procurar")
    assert ensaio.parado.pedidos == 0


def test_com_o_adaptador_do_kernel_na_tela_o_clique_acorda_do_mesmo_jeito(
    montar: Callable[..., EnsaioParado], a08: Any
) -> None:
    ensaio = montar(("usb", "bt"))
    ensaio.ar = {SALA: {"canais_evitados": []}}
    ensaio.tique()
    assert a08._CENA_NA_TELA["lugares"], "o daemon publica o adaptador com o BlueZ parado"
    ensaio.gesto("conectar-aparelho")
    assert ensaio.parado.ativacoes == 1


@pytest.mark.parametrize("pedido", [
    lambda a08, p: a08._mover(p, VERMELHO, id_da_tela(SALA)),
    lambda a08, p: a08._ligar_a_busca(p, True, id_da_tela(SALA)),
], ids=["mover", "busca"])
def test_todo_caminho_ate_o_radio_acorda_antes_de_pedir(
    montar: Callable[..., EnsaioParado], a08: Any, pedido: Any
) -> None:
    ensaio = montar()
    ensaio.tique()
    ordem: list[str] = []

    class Ponte:
        def resultado(self, metodo: str, **_params: Any) -> dict[str, Any]:
            ordem.append(f"{metodo}, ativações: {ensaio.parado.ativacoes}")
            return {"status": "recusado"}

    with pytest.raises(RuntimeError):
        pedido(a08, Ponte())
    assert ordem and ordem[0].endswith("ativações: 1")


def test_com_o_bluez_de_pe_o_clique_nao_pede_nada(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    relogio = rm.Relogio()
    mundo = MundoParado()
    mundo.bluez_de_pe = True
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(SALA, AZUL)
    ensaio = EnsaioParado(a08, monkeypatch, mundo, relogio)
    try:
        ensaio.tique()
        assert ensaio.gesto("conectar-aparelho") == {"armou": True}
        assert mundo.pedidos == 0
    finally:
        ensaio.fechar()


@pytest.fixture
def banca(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Banca]:
    preparar_o_diario(tmp_path, monkeypatch)
    viva = Banca(tmp_path)
    monkeypatch.setenv("PATH", f"{viva.binarios}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(bd, "a_suite_esta_rodando", lambda: False)
    try:
        yield viva
    finally:
        viva.fechar()


def _o_ativador_toma_o_nome(banca: Banca) -> None:
    script = banca.pasta / "bluetoothd.py"
    script.write_text(_O_BLUETOOTHD.format(raiz=str(RAIZ)), encoding="utf-8")
    (banca.pasta / "ativador.sh").write_text(
        f'#!/bin/sh\necho ativado >> "{banca.marca}"\nexec "{sys.executable}" "{script}"\n',
        encoding="utf-8")


def _gio(banca: Banca) -> tuple[bd.DonoVivo, bd.BarramentoGio]:
    barramento = bd.BarramentoGio(banca.endereco)
    assert barramento.abrir()
    dono = bd.DonoVivo(barramento)
    assert dono.ligar()
    return dono, barramento


@_ha_o_barramento
def test_pelo_busctl_a_pergunta_nao_ativa_e_o_acordar_ativa_uma_vez(banca: Banca) -> None:
    _o_ativador_toma_o_nome(banca)
    leitor = bd.PeloBusctl()
    assert not leitor.responde()
    assert banca.ativacoes() == 0
    assert leitor.acordar(quem="tela").feita
    assert banca.ativacoes() == 1
    assert leitor.responde()
    assert leitor.acordar(quem="tela").feita
    assert banca.ativacoes() == 1, "com o dono de pé, o pedido não sobe outro"


@_ha_o_barramento
def test_pelo_gio_o_acordar_vai_sem_tocar_no_org_bluez_e_o_dono_percebe(banca: Banca) -> None:
    pytest.importorskip("gi")
    _o_ativador_toma_o_nome(banca)
    dono, barramento = _gio(banca)
    try:
        assert not dono.responde()
        assert banca.ativacoes() == 0
        assert dono.acordar(quem="tela").feita
        assert banca.ativacoes() == 1
        _ate(lambda: barramento.dono_do_nome(bd.SERVICO))
    finally:
        barramento.fechar()


@_ha_o_barramento
@pytest.mark.parametrize("pelo", ["busctl", "gio"])
def test_a_ativacao_que_o_sistema_recusa_volta_como_nao_feita(banca: Banca, pelo: str) -> None:
    if pelo == "busctl":
        assert not bd.PeloBusctl().acordar(quem="tela", espera=TETO_S).feita
    else:
        pytest.importorskip("gi")
        dono, barramento = _gio(banca)
        try:
            assert not dono.acordar(quem="tela", espera=TETO_S).feita
        finally:
            barramento.fechar()
    assert banca.ativacoes() == 1


@_ha_o_barramento
def test_a_leitura_da_tela_ve_o_radio_parado_sem_o_ativar(
    banca: Banca, monkeypatch: pytest.MonkeyPatch, a08: Any
) -> None:
    _o_ativador_toma_o_nome(banca)
    leitor = bd.PeloBusctl()
    monkeypatch.setattr(bd, "dono", lambda: leitor)
    for _ in range(3):
        assert a08._ler_se_o_radio_parou() is True
    assert banca.ativacoes() == 0
    assert leitor.acordar(quem="tela").feita
    assert a08._ler_se_o_radio_parou() is False


def test_sob_a_suite_a_leitura_da_tela_nao_olha_o_sistema(a08: Any) -> None:
    assert a08._ler_se_o_radio_parou() is None
    assert a08._acordar_o_radio() is False


def test_a_suite_nao_acorda_o_bluez_da_maquina(tmp_path: Path) -> None:
    feito = bd.PeloBusctl().acordar(quem="tela")
    assert not feito.feita
    assert feito.erro == bd.RECUSA_DA_SUITE
