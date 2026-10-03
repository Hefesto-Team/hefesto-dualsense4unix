"""O nome que ela dá volta na reconexão — O-RADIO-CONECTA-ONDE-ELA-MANDA-01, item 4."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.utils import maquina
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, FONE, QUARTO, ROXO, SALA, VARANDA, VERMELHO
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    Bancada,
    id_da_tela,
    preparar_a_tela,
    preparar_o_diario,
)

ADAPTADORES = (SALA, QUARTO, VARANDA)

FABRICA = rm.NOME_DE_FABRICA[rm.CLASSE_DE_CONTROLE]


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


@pytest.fixture()
def casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O ``maquina.json`` numa pasta de teste — o de verdade, pelo dono dele."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    caminho = maquina.caminho_da_maquina()
    assert str(caminho).startswith(str(tmp_path)), "o maquina.json não é o da régua"
    return caminho


def _guardado(casa: Path, aparelho: str) -> str | None:
    """O nome no DISCO, lido do arquivo — não da memória de ninguém."""
    if not casa.exists():
        return None
    documento = json.loads(casa.read_text(encoding="utf-8"))
    return (documento.get("controles", {}).get(rm.uniq(aparelho)) or {}).get("nome")


def _renomear_na_tela(bancada: Bancada, monkeypatch: pytest.MonkeyPatch,
                      aparelho: str, nome: str) -> None:
    """O gesto da tela, o de verdade: o ``Alias`` vai a todo objeto dele no BlueZ."""
    monkeypatch.setattr(bd, "dono", lambda: bancada.dono)
    cena = bancada.cena()
    linha = next(a for a in cena["aparelhos"]
                 if str(a["id"]).replace(":", "").lower() == rm.uniq(aparelho))
    bancada.gesto("aparelho-renomear", alvo=linha["id"], valor=nome)


def _esquecer_em_todos(bancada: Bancada) -> None:
    """O X em cada linha do vermelho, em cada adaptador — ligado ou desligado."""
    for _ in range(len(ADAPTADORES)):
        cena = bancada.cena()
        linhas = [a for a in cena["aparelhos"]
                  if str(a["id"]).replace(":", "").lower() == rm.uniq(VERMELHO)
                  and not a.get("nao_conectou")]
        if not linhas:
            return
        clique = {"alvo": linhas[0]["id"], "lugar": linhas[0]["lugar"]}
        bancada.gesto("esquecer-aparelho", **clique)
        bancada.gesto("confirmar-esquecer", **clique)


def _conectar_em(bancada: Bancada, destino: str, quem: str) -> cr.Movimento:
    """Ela abre ``destino``, clica «Conectar», segura PS + Create em ``quem`` e"""
    bancada.cena()
    if bancada.cena().get("aberto") != id_da_tela(destino):
        bancada.gesto("abrir-adaptador", alvo=id_da_tela(destino))
    bancada.cena()
    rm.ela_pareia(bancada.relogio, bancada.mundo, bancada.central, quem)
    bancada.gesto("radio-procurar")
    bancada.esperar_a_central()
    return next(m for m in bancada.central.movimentos() if m.destino == destino)


PARES = [(o, d) for o in (SALA, QUARTO, VARANDA) for d in (SALA, QUARTO, VARANDA) if o != d]


@pytest.mark.parametrize(("origem", "destino"), PARES)
def test_o_conectar_noutro_adaptador_leva_o_nome_dela(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, origem: str, destino: str,
) -> None:
    """O vermelho se chama «André» na origem. Ela o desliga, abre outro adaptador"""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(origem, VERMELHO, nome="André")
    mundo.pareado(origem, AZUL, nome="Vitória")
    mundo.desligar(VERMELHO)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        feito = _conectar_em(bancada, destino, VERMELHO)
        assert (feito.estado, feito.aparelho) == (cr.CHEGOU, VERMELHO)
        assert mundo.objeto(destino, VERMELHO)["Alias"] == "André"
        assert mundo.objeto(origem, AZUL)["Alias"] == "Vitória", "o nome foi para outro"
        cena = bancada.cena()
        (linha,) = [a for a in cena["aparelhos"] if str(a["id"]).lower() == rm.uniq(VERMELHO)
                    and a.get("lugar") == id_da_tela(destino)]
        assert linha["nome"] == "André"
    finally:
        bancada.fechar()


def test_sem_nome_dela_o_objeto_novo_fica_com_o_de_fabrica(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O nome de fábrica não é nome: o controle que ela nunca renomeou chega"""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO)
    mundo.desligar(VERMELHO)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _conectar_em(bancada, VARANDA, VERMELHO)
        assert mundo.objeto(VARANDA, VERMELHO)["Alias"] == FABRICA
        assert [e for e in mundo.escritas if e[2] == "Alias"] == []
    finally:
        bancada.fechar()


def test_a_tela_mostra_o_nome_dela_em_toda_chave_do_controle(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O roxo se chama «Vitória» só no objeto da varanda; desligado, ele tem"""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(VARANDA, ROXO, conectado=False, nome="Vitória")
    mundo.pareado(SALA, ROXO, host=False)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        cena = bancada.cena()
        linhas = {a["lugar"]: a for a in cena["aparelhos"] if a.get("desligado")}
        assert set(linhas) == {id_da_tela(VARANDA), id_da_tela(SALA)}
        assert {a["nome"] for a in linhas.values()} == {"Vitória"}
    finally:
        bancada.fechar()


@pytest.mark.parametrize(("origem", "destino"), PARES + [(a, a) for a in ADAPTADORES])
def test_renomear_esquecer_em_todos_e_parear_de_novo_o_nome_volta(
    diario: Path, a08: Any, casa: Path, monkeypatch: pytest.MonkeyPatch,
    origem: str, destino: str,
) -> None:
    """E2 da O-RADIO-CONECTA-ONDE-ELA-MANDA-02, pela mão dela e de ponta a ponta."""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(origem, VERMELHO)
    outro = next(a for a in ADAPTADORES if a != origem)
    mundo.pareado(outro, VERMELHO, host=False)
    mundo.pareado(origem, AZUL, nome="Vitória")
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _renomear_na_tela(bancada, monkeypatch, VERMELHO, "André")
        assert {mundo.objeto(a, VERMELHO)["Alias"] for a in (origem, outro)} == {"André"}
        bancada.central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"
        assert _guardado(casa, AZUL) == "Vitória"

        _esquecer_em_todos(bancada)
        assert all(mundo.objeto(a, VERMELHO) is None for a in ADAPTADORES), "sobrou chave"
        bancada.central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André", "esquecer a chave apagou o nome"

        feito = _conectar_em(bancada, destino, VERMELHO)
        assert (feito.estado, feito.aparelho) == (cr.CHEGOU, VERMELHO)
        assert mundo.objeto(destino, VERMELHO)["Alias"] == "André"
        (linha,) = [a for a in bancada.cena()["aparelhos"]
                    if str(a["id"]).lower() == rm.uniq(VERMELHO)]
        assert linha["nome"] == "André" and linha["lugar"] == id_da_tela(destino)
        assert mundo.objeto(origem, AZUL)["Alias"] == "Vitória", "o nome foi para outro"
    finally:
        bancada.fechar()


def _central_da_casa(mundo: rm.RadioDeMentira, relogio: rm.Relogio) -> tuple[
        cr.CentralDoRadio, bd.DonoVivo]:
    dono = bd.DonoVivo(mundo)
    assert dono.ligar()
    central = cr.CentralDoRadio(
        dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte, relogio=relogio, dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})
    return central, dono


@pytest.mark.parametrize("destino", ADAPTADORES)
def test_o_controle_que_conecta_por_fora_da_central_recebe_o_nome(
    diario: Path, casa: Path, destino: str,
) -> None:
    """«Reaplicado em toda conexão, em qualquer adaptador»: o nome está no"""
    assert maquina.gravar_o_nome_do_controle(VERMELHO, "André")
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA if destino != SALA else QUARTO, AZUL)
    mundo.pareado(destino, VERMELHO)
    central, dono = _central_da_casa(mundo, relogio)
    try:
        assert mundo.objeto(destino, VERMELHO)["Alias"] == FABRICA
        feitos = central.cuidar_dos_nomes()
        assert feitos == ((VERMELHO, "André"),)
        assert mundo.objeto(destino, VERMELHO)["Alias"] == "André"
        assert [e for e in mundo.escritas if e[2] == "Alias"] == [
            (rm.no_de(destino, VERMELHO), bd.APARELHO, "Alias", "André")]
        assert central.cuidar_dos_nomes() == (), "a volta escreveu de novo o que já estava"
    finally:
        central.fechar()
        dono.fechar()


def test_ela_apaga_o_nome_e_ele_nao_volta(
    diario: Path, a08: Any, casa: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Apagar o nome na tela volta ao de fábrica (e a tela ao «Player N»): o"""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(QUARTO, VERMELHO, host=False)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _renomear_na_tela(bancada, monkeypatch, VERMELHO, "André")
        bancada.central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"

        _renomear_na_tela(bancada, monkeypatch, VERMELHO, "")
        bancada.central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) is None, "o nome apagado ficou guardado"
        bancada.central.cuidar_dos_nomes()
        assert all(not bancada.central._nome_dado(bancada.dono, o)
                   for o in bancada.dono.aparelhos() or () if o.endereco == VERMELHO)

        _esquecer_em_todos(bancada)
        _conectar_em(bancada, VARANDA, VERMELHO)
        assert mundo.objeto(VARANDA, VERMELHO)["Alias"] == FABRICA
    finally:
        bancada.fechar()


def test_o_nome_dado_por_fora_do_produto_tambem_fica(diario: Path, casa: Path) -> None:
    """O produto é para qualquer computador: o nome que ela dá pelo"""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(VARANDA, VERMELHO, host=False)
    central, dono = _central_da_casa(mundo, relogio)
    try:
        assert central.cuidar_dos_nomes() == ()
        mundo.escrever(rm.no_de(SALA, VERMELHO), bd.APARELHO, "Alias", "s", "Bia", espera=1.0)
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "Bia"
        assert mundo.objeto(VARANDA, VERMELHO)["Alias"] == "Bia"
    finally:
        central.fechar()
        dono.fechar()


def test_so_o_controle_tem_o_nome_guardado(diario: Path, casa: Path) -> None:
    """DECISÃO desta sprint: o campo é ``ControleDeclarado.nome``, e só controle"""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, FONE, classe=rm.CLASSE_DE_FONE, nome="Caixa da Sala")
    mundo.pareado(SALA, VERMELHO, nome="André")
    central, dono = _central_da_casa(mundo, relogio)
    try:
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"
        assert _guardado(casa, FONE) is None
        assert mundo.objeto(SALA, FONE)["Alias"] == "Caixa da Sala"
    finally:
        central.fechar()
        dono.fechar()


def test_o_objeto_recriado_no_mesmo_adaptador_nao_e_ela_apagando(
    diario: Path, a08: Any, casa: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O X e o «Conectar» no MESMO adaptador, sem volta dos nomes no meio, e o"""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO)
    bancada = Bancada(a08, monkeypatch, mundo, relogio)
    try:
        _renomear_na_tela(bancada, monkeypatch, VERMELHO, "André")
        bancada.central.cuidar_dos_nomes()
        bancada.central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"

        monkeypatch.setattr(bancada.central, "_dar_o_nome", lambda *_a: None)
        _esquecer_em_todos(bancada)
        _conectar_em(bancada, SALA, VERMELHO)
        assert mundo.objeto(SALA, VERMELHO)["Alias"] == FABRICA

        bancada.central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André", "o objeto novo apagou o nome dela"
        assert mundo.objeto(SALA, VERMELHO)["Alias"] == "André"
    finally:
        bancada.fechar()


def test_o_adaptador_que_volta_com_o_nome_velho_recebe_o_dela(diario: Path, casa: Path) -> None:
    """A varanda estava fora da porta quando ela renomeou o vermelho de «André»"""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO, nome="André")
    central, dono = _central_da_casa(mundo, relogio)
    try:
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"
        mundo.escrever(rm.no_de(SALA, VERMELHO), bd.APARELHO, "Alias", "s", "Bia", espera=1.0)
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "Bia"

        mundo.pareado(VARANDA, VERMELHO, host=False, nome="André")
        dono._fotografar()
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "Bia", "o adaptador que voltou trouxe o nome velho"
        assert mundo.objeto(VARANDA, VERMELHO)["Alias"] == "Bia"
        assert mundo.objeto(SALA, VERMELHO)["Alias"] == "Bia"
    finally:
        central.fechar()
        dono.fechar()


def test_o_nome_apagado_sai_tambem_do_objeto_que_ficou_com_ele(diario: Path, casa: Path) -> None:
    """Ela apaga o nome, e a escrita não alcança um dos objetos (o BlueZ recusou"""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO, nome="André")
    mundo.pareado(VARANDA, VERMELHO, host=False, nome="André")
    central, dono = _central_da_casa(mundo, relogio)
    try:
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"
        mundo.escrever(rm.no_de(SALA, VERMELHO), bd.APARELHO, "Alias", "s", "", espera=1.0)
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) is None
        assert mundo.objeto(VARANDA, VERMELHO)["Alias"] == ""
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) is None, "o nome apagado voltou"
    finally:
        central.fechar()
        dono.fechar()


def test_o_fio_da_faxina_cuida_do_nome(diario: Path, casa: Path) -> None:
    """Ninguém chama a volta à mão no produto: é o fio da faxina, que o daemon"""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, VERMELHO, nome="André")
    dono = bd.DonoVivo(mundo)
    assert dono.ligar()
    central = cr.CentralDoRadio(
        dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})
    try:
        central.comecar_a_faxina(intervalo_s=0.05)
        fim = time.monotonic() + 5.0
        while _guardado(casa, VERMELHO) is None and time.monotonic() < fim:
            time.sleep(0.02)
        assert _guardado(casa, VERMELHO) == "André"
    finally:
        central.fechar(espera=2.0)
        dono.fechar()


@pytest.mark.parametrize("adaptador", ADAPTADORES)
def test_o_objeto_sem_chave_no_mesmo_caminho_nao_e_ela_apagando(
    diario: Path, casa: Path, adaptador: str,
) -> None:
    """O DEFEITO QUE A CONFERÊNCIA ACHOU. O vermelho se chama «André», com"""
    outro = next(a for a in ADAPTADORES if a != adaptador)
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(adaptador, VERMELHO, nome="André")
    mundo.pareado(outro, VERMELHO, host=False, nome="André")
    central, dono = _central_da_casa(mundo, relogio)
    try:
        central.cuidar_dos_nomes()
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"

        mundo.esquecer_na_ponte(adaptador, VERMELHO)
        mundo.desligar(VERMELHO)
        mundo.mesa[rm.HCIS[adaptador]][bd.ADAPTADOR]["Discovering"] = True
        mundo.segurar_ps_create(VERMELHO)
        novo = mundo.objeto(adaptador, VERMELHO)
        assert novo is not None and novo["Paired"] is False
        assert novo["Alias"] == FABRICA

        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André", "o achado sem chave apagou o nome dela"
        assert mundo.objeto(outro, VERMELHO)["Alias"] == "André"
    finally:
        central.fechar()
        dono.fechar()


class _DiscoQueRecusa:
    """O ``maquina.json`` de verdade (:class:`cr.NomesNaMaquina`), que recusa"""

    def __init__(self) -> None:
        self.real = cr.NomesNaMaquina()
        self.recusar = 0

    def ler(self) -> Any:
        return self.real.ler()

    def gravar(self, aparelho: str, nome: str | None) -> bool:
        if self.recusar:
            self.recusar -= 1
            return False
        return self.real.gravar(aparelho, nome)


@pytest.mark.parametrize("adaptador", ADAPTADORES)
def test_a_gravacao_recusada_nao_desfaz_o_nome_que_ela_deu(
    diario: Path, casa: Path, adaptador: str,
) -> None:
    """O vermelho se chama «André». Ela o renomeia para «Bia» (por fora do"""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(adaptador, VERMELHO, nome="André")
    disco = _DiscoQueRecusa()
    dono = bd.DonoVivo(mundo)
    assert dono.ligar()
    central = cr.CentralDoRadio(
        dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte, nomes=disco, relogio=relogio,
        dormir=relogio.dormir, sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})
    try:
        central.cuidar_dos_nomes()
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "André"

        no = rm.no_de(adaptador, VERMELHO)
        mundo.escrever(no, bd.APARELHO, "Alias", "s", "Bia", espera=1.0)
        disco.recusar = 1
        assert central.cuidar_dos_nomes() == ()
        assert _guardado(casa, VERMELHO) == "André"
        assert mundo.objeto(adaptador, VERMELHO)["Alias"] == "Bia"

        central.cuidar_dos_nomes()
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) == "Bia", "o nome dela não chegou ao disco"
        assert mundo.objeto(adaptador, VERMELHO)["Alias"] == "Bia", "o nome velho voltou"
    finally:
        central.fechar()
        dono.fechar()


def test_o_endereco_no_lugar_do_nome_nao_e_nome_dela(diario: Path, casa: Path) -> None:
    """Sem ``Name`` (o aparelho ainda não disse como se chama), o BlueZ põe o"""
    mundo, relogio = rm.RadioDeMentira(), rm.Relogio()
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(QUARTO, VERMELHO, host=False)
    objeto = mundo.objeto(SALA, VERMELHO)
    del objeto["Name"]
    objeto["Alias"] = VERMELHO.upper().replace(":", "-")
    central, dono = _central_da_casa(mundo, relogio)
    try:
        central.cuidar_dos_nomes()
        central.cuidar_dos_nomes()
        assert _guardado(casa, VERMELHO) is None
        assert mundo.objeto(QUARTO, VERMELHO)["Alias"] == FABRICA
        assert [e for e in mundo.escritas if e[2] == "Alias"] == []
    finally:
        central.fechar()
        dono.fechar()


def test_com_o_dono_vivo_a_volta_dos_nomes_nao_espera_a_faxina(diario: Path, casa: Path) -> None:
    """A faxina anda a cada 30 s; o nome, com o dono lendo da memória, a cada"""
    mundo = rm.RadioDeMentira()
    mundo.pareado(VARANDA, VERMELHO, nome="André")
    dono = bd.DonoVivo(mundo)
    assert dono.ligar()
    central = cr.CentralDoRadio(
        dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})
    try:
        assert central.ligar()
        central.comecar_a_faxina()
        fim = time.monotonic() + cr.INTERVALO_DOS_NOMES_S + 3.0
        while _guardado(casa, VERMELHO) is None and time.monotonic() < fim:
            time.sleep(0.05)
        assert _guardado(casa, VERMELHO) == "André"
    finally:
        central.fechar(espera=2.0)
        dono.fechar()


def test_o_nome_no_maquina_json_e_do_controle_e_nao_apaga_o_resto(casa: Path) -> None:
    """O nome entra pela fusão: o microfone e a economia do mesmo controle"""
    assert maquina.gravar_maquina({"controles": {rm.uniq(VERMELHO): {
        "microfone": False, "economia": True}}})
    assert maquina.gravar_o_nome_do_controle(VERMELHO.upper(), "  André  ")
    lido = maquina.carregar_maquina().controles[rm.uniq(VERMELHO)]
    assert (lido.nome, lido.microfone, lido.economia) == ("André", False, True)
    assert maquina.nomes_dos_controles(maquina.carregar_maquina()) == {
        rm.uniq(VERMELHO): "André"}

    assert maquina.gravar_o_nome_do_controle(rm.uniq(VERMELHO), "")
    documento = json.loads(casa.read_text(encoding="utf-8"))
    assert documento["controles"][rm.uniq(VERMELHO)] == {"microfone": False, "economia": True}

    assert maquina.gravar_o_nome_do_controle("02:00:1a:00:00:01", "Clone") is False
    assert maquina.gravar_o_nome_do_controle("isto não é endereço", "X") is False
    assert maquina.gravar_o_nome_do_controle(VERMELHO, "é" * 125) is False
    assert maquina.chave_do_controle("AA:BB:CC:00:00:01") == rm.uniq(VERMELHO)
    with pytest.raises(ValueError):
        maquina.ControleDeclarado(nome="x" * 249)
    assert maquina.ControleDeclarado(nome="   ").nome is None
