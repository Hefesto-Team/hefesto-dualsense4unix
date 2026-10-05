"""Esquecer e limpar as conexões — ESQUECER-E-LIMPAR-AS-CONEXOES-01.

O que ela disse em 30/09/2026, ~01h30, com os quatro DualSense no rádio:
*«opção esquecer ali. Esse dualsense fantasma ali não faz sentido.»*
<!-- noqa-acento: citação literal dela -->
E às ~03h, sobre o «Limpar Conexões»:
*«limpar com frequencia a cada troca <!-- noqa-acento: citação literal dela -->
ou ao desligar os controles, algo nessa linha»*.

MEDIDO antes da cura (02/10, sobre ``2fd24c009``, o mesmo instrumento antes e
depois): o «Conectar» anônimo que acabou fazia a linha «DualSense · Não
Conectou» sem aparelho, com a caixa laranja; a linha de quem não chegou ficava
com ele já no ar noutro adaptador; o X que a tirava morava na janela e ela
voltava ao reabrir; o teclado no ar não tinha como ser esquecido e o fone fora
do ar nem aparecia; a dobra do controle que desligou ficava; e a chave tirada
por outro programa, com o serviço vivo, ficava sem lápide.

As decisões (quem coordena, 30/09/2026, a validar por ela):
D-3009-A-LINHA-TEM-APARELHO, D-3009-O-ESQUECER-TEM-NOME,
D-3009-A-CASA-SE-LIMPA-SOZINHA (pela resposta dela; os momentos e as guardas de
quem coordena) e D-3009-TODO-ESQUECER-TEM-LAPIDE.

A central é a ``CentralDoRadio`` de verdade, com o ``DonoVivo`` de verdade por
cima do rádio de mentira com física, e todo pedido da tela atravessa o
tratador real do daemon. **A pergunta é sempre ao mundo e à central** — as
chamadas ao BlueZ, as lápides da ponte de mentira, os movimentos publicados —;
quando uma régua precisa de um botão, ela o acha no HTML da cena e o clica.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import re
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import gesto_de_pareamento as gp
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, FONE, QUARTO, ROXO, SALA, VARANDA, VERDE, VERMELHO
from tests.unit.test_o_conectar_pareia_no_adaptador_escolhido import (
    Bancada,
    id_da_tela,
    preparar_a_tela,
    preparar_o_diario,
)

RAIZ = Path(__file__).resolve().parents[2]
PAGINA = "08-conexoes.html"
TECLADO = "aa:bb:cc:00:00:e1"
JOHNATHAN, ANDRE = VERMELHO, AZUL


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return preparar_o_diario(tmp_path, monkeypatch)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    return preparar_a_tela(monkeypatch)


class PonteDeTudo:
    """O ``ponte.resultado`` com o tratador REAL do daemon, para qualquer método"""

    def __init__(self, central: cr.CentralDoRadio) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        class _Daemon(IpcHandlersMixin):
            pass

        self.eu = _Daemon()
        self.eu.daemon = SimpleNamespace(_central_do_radio=central)  # type: ignore[attr-defined]
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        tratador = getattr(self.eu, "_handle_" + metodo.replace(".", "_"), None)
        assert tratador is not None, f"método que o daemon não atende: {metodo}"
        self.chamadas.append((metodo, dict(params)))
        return asyncio.run(tratador(params))


class Casa(Bancada):
    """A bancada da 08 com a ponte inteira, o cabo, e só CONTROLE na lista do"""

    def __init__(self, a08: Any, monkeypatch: pytest.MonkeyPatch, mundo: rm.RadioDeMentira,
                 relogio: rm.Relogio | None = None) -> None:
        super().__init__(a08, monkeypatch, mundo, relogio or rm.Relogio())
        self.monkeypatch = monkeypatch
        self.ponte = PonteDeTudo(self.central)  # type: ignore[assignment]
        self.cabo: set[str] = set()
        monkeypatch.setattr(a08, "_ler_os_zumbis", lambda: {})

    def estado(self) -> dict[str, Any]:
        controles = [
            {"uniq": rm.uniq(f.endereco), "transport": "bt", "connected": True,
             "adaptador": f.conectado_em, "hz_movimento": 150.0, "hz_voz": 0.0,
             "ponte_do_radio": "som", "audio": {"mic_mudo": True}}
            for f in self.mundo.fisicos.values()
            if f.conectado_em and f.classe == rm.CLASSE_DE_CONTROLE]
        controles += [{"uniq": rm.uniq(ap), "transport": "usb", "connected": True,
                       "adaptador": "", "hz_movimento": 250.0, "hz_voz": 0.0,
                       "audio": {"mic_mudo": True}} for ap in sorted(self.cabo)]
        return {"controllers": controles, "radio_central": self.central.publicar(controles)}

    def janela_nova(self) -> Any:
        """Ela fecha e abre o Hefesto: o módulo da 08 é RECARREGADO (tudo o que a"""
        from hefesto_dualsense4unix.interface import pacotes

        nome = self.a08.__name__
        for registro in (pacotes.GESTOS, pacotes.GESTOS_QUE_MEXEM, pacotes.PACOTES):
            for chave in [k for k, v in registro.items()
                          if getattr(v, "__module__", "") == nome
                          or (registro is pacotes.GESTOS_QUE_MEXEM
                              and getattr(pacotes.GESTOS.get(k), "__module__", "") == nome)]:
                self.monkeypatch.delitem(registro, chave)
        novo = importlib.reload(self.a08)
        preparar_a_tela(self.monkeypatch)
        dono, ordem = self.dono, [id_da_tela(e) for e in (SALA, QUARTO, VARANDA)]
        self.monkeypatch.setattr(novo, "_ler_o_bluez", lambda: (
            tuple(dono.adaptadores() or ()), tuple(dono.aparelhos() or ())))
        self.monkeypatch.setattr(novo, "_ordem_gravada", lambda: ordem)
        self.monkeypatch.setattr(novo, "_ler_os_zumbis", lambda: {})
        self.a08 = novo
        return novo


def esperar(condicao: Any, teto: float = 5.0) -> bool:
    """Espera, no relógio de verdade, a condição valer. Não levanta."""
    fim = time.monotonic() + teto
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.01)
    return bool(condicao())


def nao_conectou(cena: dict[str, Any]) -> list[dict[str, Any]]:
    return [a for a in cena["aparelhos"] if a.get("nao_conectou")]


def do_diario(caminho: Path, o_que: str) -> list[dict[str, Any]]:
    if not caminho.exists():
        return []
    linhas = [json.loads(x) for x in caminho.read_text(encoding="utf-8").splitlines() if x]
    return [x for x in linhas if x.get("o_que") == o_que]


def remocoes(mundo: rm.RadioDeMentira) -> list[tuple[str, str]]:
    """Os ``RemoveDevice`` que chegaram ao BlueZ: ``(adaptador, aparelho)``."""
    por_hci = {hci: e for e, hci in rm.HCIS.items()}
    saida = []
    for caminho, argumentos in mundo.metodos("RemoveDevice"):
        no = str(argumentos[0])
        saida.append((por_hci.get(caminho, caminho),
                      no.rsplit("dev_", 1)[-1].replace("_", ":").lower()))
    return saida


def os_quatro_no_ar() -> rm.RadioDeMentira:
    """João e Johnathan na Direita (sala), André no Meio (quarto), Vitória na"""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, JOHNATHAN, nome="Johnathan")
    mundo.pareado(SALA, VERDE, nome="João")
    mundo.pareado(QUARTO, ANDRE, nome="André")
    mundo.pareado(VARANDA, ROXO, nome="Vitória")
    return mundo


def movimento(aparelho: str, destino: str, estado: str = cr.NAO_CHEGOU, *,
              motivo: str = cr.MOTIVO_SEM_GESTO, idade: float = 5.0) -> cr.Movimento:
    return cr.Movimento(aparelho, destino, estado, cr.PASSO_FIM if estado != cr.ESPERANDO
                        else cr.PASSO_GESTO, motivo=motivo, quando=time.time() - idade)


def o_mover_que_nao_chega(casa: Casa, quem: str, destino: str) -> cr.Movimento:
    """O «Mover» sem o gesto dela: a central esquece a origem, abre a janela"""
    feito = casa.central.mover(quem, destino)
    assert (feito.estado, feito.aparelho) == (cr.NAO_CHEGOU, quem), feito
    return feito


def test_o_conectar_anonimo_que_acaba_sem_ninguem_nao_vira_linha(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com os quatro no ar, o «Conectar» sem alvo na Direita (o ``radio.mover``"""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    try:
        casa.cena()
        casa.gesto("abrir-adaptador", alvo=id_da_tela(QUARTO))
        casa.cena()
        resposta = casa.ponte.resultado("radio.mover", destino=id_da_tela(SALA))
        assert isinstance(resposta, dict) and resposta.get("status") == "ok", resposta
        casa.esperar_a_central()
        (fim,) = casa.central.movimentos()
        assert (fim.aparelho, fim.estado, fim.destino) == ("", cr.NAO_CHEGOU, SALA), fim

        cena = casa.cena()
        assert nao_conectou(cena) == [], "a busca sem ninguém virou linha"
        assert not [lug["id"] for lug in cena["lugares"] if lug.get("nao_conectou")]
        assert cena["aberto"] == id_da_tela(QUARTO), "a busca sem ninguém abriu outra caixa"
    finally:
        casa.fechar()


@pytest.mark.parametrize("motivo", [cr.MOTIVO_SEM_JANELA, cr.MOTIVO_NAO_PAREOU,
                                    cr.MOTIVO_SEM_GESTO, cr.MOTIVO_PRAZO])
def test_nenhum_motivo_faz_linha_sem_aparelho(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, motivo: str,
) -> None:
    """A regra é pelo APARELHO, e vale para todo motivo — a janela que não abriu"""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    try:
        casa.central._guardar(movimento("", VARANDA, motivo=motivo))
        cena = casa.cena()
        assert nao_conectou(cena) == []
        assert not [lug["id"] for lug in cena["lugares"] if lug.get("nao_conectou")]
    finally:
        casa.fechar()


@pytest.mark.parametrize("volta", ["no rádio, noutro adaptador", "no cabo"])
def test_a_linha_some_quando_ele_aparece_no_ar(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, volta: str,
) -> None:
    """O «Mover» de Johnathan para a Esquerda não chega: a linha «Não Conectou»"""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    try:
        o_mover_que_nao_chega(casa, JOHNATHAN, VARANDA)
        (linha,) = nao_conectou(casa.cena())
        assert (linha["aparelho"], linha["lugar"]) == (id_da_tela(JOHNATHAN), id_da_tela(VARANDA))
        assert linha["nome"] == "Johnathan"

        if volta == "no cabo":
            casa.cabo.add(JOHNATHAN)
        else:
            casa.mundo.parear_por_fora(QUARTO, JOHNATHAN)
        cena = casa.cena()
        assert nao_conectou(cena) == [], f"a linha ficou com ele no ar {volta}"
        assert not [lug["id"] for lug in cena["lugares"] if lug.get("nao_conectou")]
    finally:
        casa.fechar()


def test_o_conectar_anonimo_depois_nao_apaga_a_linha_dele(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A linha é por APARELHO, como a central guarda: o «Conectar» sem ninguém"""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    try:
        o_mover_que_nao_chega(casa, JOHNATHAN, VARANDA)
        assert len(nao_conectou(casa.cena())) == 1
        resposta = casa.ponte.resultado("radio.mover", destino=id_da_tela(VARANDA))
        assert isinstance(resposta, dict) and resposta.get("status") == "ok", resposta
        casa.esperar_a_central()
        (anonimo,) = [m for m in casa.central.movimentos() if m.aparelho == cr.CONECTANDO]
        assert (anonimo.estado, anonimo.destino) == (cr.NAO_CHEGOU, VARANDA), anonimo

        linhas = nao_conectou(casa.cena())
        assert [(x["aparelho"], x["lugar"]) for x in linhas] == [
            (id_da_tela(JOHNATHAN), id_da_tela(VARANDA))], linhas
    finally:
        casa.fechar()


def test_o_x_dispensado_nao_volta_numa_janela_nova(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O X da linha de Johnathan tira a linha NA CENTRAL (``radio.dispensar``):"""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    try:
        o_mover_que_nao_chega(casa, JOHNATHAN, VARANDA)
        # o X virou item do «⋮» (desenho aprovado de 05/10/2026): mora no molde do menu
        moldes = casa.tique()["radio-moldes"]
        x = re.search(r'data-gesto="dispensar-linha" data-alvo="([^"]+)" '
                      r'data-lugar="([^"]+)"', moldes)
        assert x is not None, "o menu da linha «Não conectou» não tem o «Tirar esta linha»"
        assert casa.gesto("dispensar-linha", alvo=x.group(1), lugar=x.group(2)) == {
            "armou": True}
        assert nao_conectou(casa.cena()) == []
        assert casa.mundo.lapides == [(SALA, JOHNATHAN)], "o X esqueceu alguma coisa"

        casa.janela_nova()
        assert nao_conectou(casa.cena()) == [], "a linha dispensada voltou na janela nova"
        assert not [m for m in casa.central.publicar()["movimentos"]
                    if m["aparelho"] == JOHNATHAN], "a central ainda publica o dispensado"
    finally:
        casa.fechar()


def test_o_dispensar_nunca_tira_um_esperando(diario: Path) -> None:
    """O ``radio.dispensar`` só tira movimento ACABADO: o «esperando» fica, e"""
    mundo, relogio = os_quatro_no_ar(), rm.Relogio()
    dono = bd.DonoVivo(mundo)
    assert dono.ligar()
    central = cr.CentralDoRadio(
        dono=dono, onde_esta=mundo.onde_esta, movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte, relogio=relogio, dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"})
    try:
        central._guardar(movimento(JOHNATHAN, VARANDA, cr.ESPERANDO))
        resposta = PonteDeTudo(central).resultado("radio.dispensar",
                                                  aparelho=id_da_tela(JOHNATHAN))
        assert resposta == {"status": "ocupado", "dispensado": False}, resposta
        assert central.movimento_de(JOHNATHAN) is not None
    finally:
        central.fechar(espera=5.0)
        dono.fechar()


def _a_caixa_cheia() -> rm.RadioDeMentira:
    """Na sala: um controle no ar, um «Desligado», um no cabo com a chave BT"""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, VERMELHO, nome="Johnathan")
    mundo.pareado(SALA, ROXO, conectado=False, nome="Vitória")
    mundo.pareado(SALA, AZUL, conectado=False, nome="André")
    mundo.pareado(SALA, TECLADO, classe=rm.CLASSE_DE_TECLADO)
    mundo.pareado(SALA, FONE, classe=rm.CLASSE_DE_FONE, conectado=False)
    mundo.fisicos[VERDE] = rm.Fisico(VERDE, rm.CLASSE_DE_CONTROLE)
    return mundo


def _o_menu_de(campos: dict[str, Any], aparelho: str) -> tuple[str, str] | None:
    """O ``(alvo, lugar)`` do «⋮» da linha de ``aparelho`` na sala, achado no HTML."""
    for alvo, lugar in re.findall(r'data-gesto="aparelho-menu" data-alvo="([^"]+)" '
                                  r'data-lugar="([^"]+)"', campos["radio-sala"]):
        if alvo.replace(":", "").upper() == id_da_tela(aparelho):
            return alvo, lugar
    return None


@pytest.mark.parametrize("quem", [VERMELHO, ROXO, AZUL, TECLADO, FONE],
                         ids=["no ar", "desligado", "no cabo", "teclado", "fone"])
def test_todo_pareado_tem_o_esquecer_e_ele_tira_aquele_par(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, quem: str,
) -> None:
    """O «⋮» da linha abre o menu, o «Esquecer» de lá abre a pergunta, e o"""
    casa = Casa(a08, monkeypatch, _a_caixa_cheia())
    casa.cabo.add(AZUL)
    try:
        campos = casa.tique()
        cena = dict(casa.a08._CENA_NA_TELA)
        linha = next((a for a in cena["aparelhos"]
                      if str(a["id"]).replace(":", "").upper() == id_da_tela(quem)
                      and a["lugar"] == id_da_tela(SALA)), None)
        assert linha is not None, f"{quem} não tem linha na sala"
        if quem == FONE:
            assert (linha["tipo"], linha.get("desligado")) == ("fone", True), linha
        if quem == AZUL:
            assert linha.get("usb") is True, linha

        menu = _o_menu_de(campos, quem)
        assert menu is not None, f"a linha de {quem} não tem o «⋮»"
        alvo, lugar = menu
        assert casa.gesto("aparelho-menu", alvo=alvo, lugar=lugar) == {"armou": True}
        painel = re.search(r'<template class="painel-molde" data-painel="menu" data-alvo="'
                           + re.escape(f"{alvo}|{lugar}") + r'"[^>]*>(.*?)</template>',
                           campos["radio-moldes"])
        assert painel is not None, "o «⋮» não abre menu nenhum"
        assert (f'data-gesto="esquecer-aparelho" data-alvo="{alvo}" '
                f'data-lugar="{lugar}"') in painel.group(1)
        assert casa.gesto("esquecer-aparelho", alvo=alvo, lugar=lugar) == {"armou": True}
        assert remocoes(casa.mundo) == [] and casa.mundo.lapides == [], "esqueceu sem ela"
        assert (f'data-esquecer="1" data-alvo="{alvo}" data-destino="{lugar}" '
                f'data-sim="Esquecer" data-gesto="confirmar-esquecer"') in campos["radio-moldes"]

        casa.gesto("confirmar-esquecer", alvo=alvo, lugar=lugar)
        assert remocoes(casa.mundo) == [(SALA, quem)]
        assert casa.mundo.lapides == [(SALA, quem)]
        assert casa.mundo.objeto(SALA, quem) is None
        for outro in {VERMELHO, ROXO, AZUL, TECLADO, FONE} - {quem}:
            assert casa.mundo.objeto(SALA, outro) is not None, f"{outro} saiu junto"
    finally:
        casa.fechar()


def test_a_linha_nao_conectou_nao_tem_esquecer(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O verde que não chegou à sala tem o «⋮» só com o «Tirar esta linha», e nem o"""
    casa = Casa(a08, monkeypatch, _a_caixa_cheia())
    try:
        casa.central._guardar(movimento(VERDE, SALA, motivo=cr.MOTIVO_NAO_PAREOU))
        campos = casa.tique()
        (linha,) = nao_conectou(dict(casa.a08._CENA_NA_TELA))
        assert linha["aparelho"] == id_da_tela(VERDE)
        par = f'data-alvo="{linha["id"]}" data-lugar="{linha["lugar"]}"'
        assert f'data-gesto="aparelho-menu" {par}' in campos["radio-sala"]
        assert f'data-gesto="dispensar-linha" {par}' in campos["radio-moldes"]
        assert f'data-gesto="esquecer-aparelho" {par}' not in campos["radio-moldes"]
        with pytest.raises(ValueError):
            casa.gesto("esquecer-aparelho", alvo=linha["id"], lugar=linha["lugar"])
    finally:
        casa.fechar()


@pytest.mark.parametrize("descrito", [True, False], ids=["descrito", "sem_o_bluez"])
def test_todo_menu_abre_ou_treme(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, descrito: bool,
) -> None:
    """O «⋮» de cada linha abre o menu dele, ou treme: nunca um clique que não"""
    casa = Casa(a08, monkeypatch, _a_caixa_cheia())
    try:
        campos = casa.tique()
        menus = re.findall(r'data-gesto="aparelho-menu" data-alvo="([^"]+)" '
                           r'data-lugar="([^"]*)"', campos["radio-sala"])
        assert menus, "a sala não tem «⋮» nenhum"
        cena = dict(casa.a08._CENA_NA_TELA)
        cena["lugares"] = [{**lug, "sabido": descrito} for lug in cena["lugares"]]
        monkeypatch.setattr(casa.a08, "_CENA_NA_TELA", cena)
        moldes = casa.a08.html_dos_moldes(cena)
        for alvo, lugar in menus:
            tem_molde = f'data-painel="menu" data-alvo="{alvo}|{lugar}"' in moldes
            assert tem_molde is descrito, (alvo, lugar)
            if tem_molde:
                assert casa.gesto("aparelho-menu", alvo=alvo, lugar=lugar) == {"armou": True}
            else:
                with pytest.raises(RuntimeError):
                    casa.gesto("aparelho-menu", alvo=alvo, lugar=lugar)
    finally:
        casa.fechar()


def _faxina(casa: Casa) -> None:
    """O fio da faxina, com o passo curto e a volta de 30 s longe: o que limpar"""
    casa.central.comecar_a_faxina(intervalo_s=3600.0, passo_s=0.02)


def _sobras_no_diario(diario: Path, aparelho: str) -> list[dict[str, Any]]:
    return [x for x in do_diario(diario, cr.ESQUECEU_A_SOBRA) if x.get("controle") == aparelho]


def _visto_no_ar(casa: Casa, aparelho: str) -> None:
    """Espera o passo do fio guardar onde ``aparelho`` está no ar. Não reprova"""
    esperar(lambda: aparelho in casa.central._lembrancas, teto=2.0)


def test_depois_de_uma_troca_a_dobra_sai_antes_da_volta(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """André no Meio, com a chave velha dele também na Esquerda (o autorestore"""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    mundo = casa.mundo
    try:
        mundo.chave_que_volta(VARANDA, ANDRE)
        _faxina(casa)
        casa.relogio.agendar(2.0, lambda: mundo.segurar_ps_create(JOHNATHAN))
        feito = casa.central.mover(JOHNATHAN, VARANDA)
        assert feito.estado == cr.CHEGOU, feito
        acabou = casa.relogio()

        assert esperar(lambda: (VARANDA, ANDRE) in mundo.lapides), (
            f"a dobra do André ficou depois da troca: lápides {mundo.lapides}")
        assert casa.relogio() - acabou < cr.INTERVALO_DA_FAXINA_S
        assert mundo.objeto(VARANDA, ANDRE) is None
        assert mundo.objeto(QUARTO, ANDRE) is not None, "a chave de onde ele está saiu"
        assert (QUARTO, ANDRE) not in mundo.lapides
        assert esperar(lambda: _sobras_no_diario(diario, ANDRE))
        (linha,) = _sobras_no_diario(diario, ANDRE)
        assert linha["adaptador"] == VARANDA
    finally:
        casa.fechar()


@pytest.mark.parametrize("como", ["desliga", "vai para o cabo"])
def test_quando_desliga_a_dobra_sai_e_a_casa_dele_fica(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, como: str,
) -> None:
    """A mesma dobra, e o André desliga (ou passa ao cabo) logo depois de ser"""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    mundo = casa.mundo
    try:
        mundo.chave_que_volta(VARANDA, ANDRE)
        _faxina(casa)
        _visto_no_ar(casa, ANDRE)
        assert mundo.lapides == [], "a dobra saiu sem momento nenhum"
        if como == "vai para o cabo":
            casa.cabo.add(ANDRE)
            mundo.para_o_cabo(ANDRE)
        else:
            mundo.desligar(ANDRE)

        assert esperar(lambda: (VARANDA, ANDRE) in mundo.lapides), (
            f"a dobra ficou quando ele {como}: lápides {mundo.lapides}")
        assert mundo.lapides == [(VARANDA, ANDRE)]
        objeto = mundo.objeto(QUARTO, ANDRE)
        assert objeto is not None and objeto["Paired"] is True, "a casa dele saiu"
        assert esperar(lambda: _sobras_no_diario(diario, ANDRE))
        (linha,) = _sobras_no_diario(diario, ANDRE)
        assert linha["por_que"] == cr.QUANDO_O_CONTROLE_DESLIGOU
    finally:
        casa.fechar()


def test_a_chave_que_nasceu_depois_fica(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """André é visto no ar no Meio, com a dobra da Esquerda, e desliga. Antes"""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    mundo = casa.mundo
    try:
        mundo.chave_que_volta(VARANDA, ANDRE)
        casa.central._lembrar_onde_estao()
        mundo.desligar(ANDRE)
        mundo.parear_por_fora(VARANDA, ANDRE)
        mundo.desligar(ANDRE)
        casa.central.limpar(cr.QUANDO_O_CONTROLE_DESLIGOU)
        assert mundo.objeto(VARANDA, ANDRE) is not None, "a chave nova saiu"
        assert mundo.lapides == [] and remocoes(mundo) == []
    finally:
        casa.fechar()


def _quatro_desligados(casa: Casa) -> None:
    casa.central._lembrar_onde_estao()
    for quem in (JOHNATHAN, VERDE, ANDRE, ROXO):
        casa.mundo.desligar(quem)


def _teclado_em_dois(casa: Casa) -> None:
    casa.mundo.pareado(SALA, TECLADO, classe=rm.CLASSE_DE_TECLADO)
    casa.mundo.pareado(QUARTO, TECLADO, classe=rm.CLASSE_DE_TECLADO, host=False)
    casa.central._lembrar_onde_estao()
    casa.central.limpar()
    casa.mundo.desligar(TECLADO)


def _adaptador_desplugado(casa: Casa) -> None:
    casa.mundo.chave_que_volta(VARANDA, ANDRE)
    casa.central._lembrar_onde_estao()
    casa.mundo.desplugar(VARANDA)
    casa.central.limpar()
    casa.mundo.desligar(ANDRE)


def _dobra_com_esperando(casa: Casa) -> None:
    casa.mundo.chave_que_volta(VARANDA, ANDRE)
    casa.central._guardar(movimento(FONE, SALA, cr.ESPERANDO, idade=1.0))


def _uma_chave_so(casa: Casa) -> None:
    casa.central._lembrar_onde_estao()
    casa.mundo.desligar(ANDRE)


@pytest.mark.parametrize("cena", [_uma_chave_so, _quatro_desligados, _teclado_em_dois,
                                  _adaptador_desplugado, _dobra_com_esperando],
                         ids=lambda f: f.__name__.strip("_"))
def test_o_que_nunca_sai(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, cena: Any,
) -> None:
    """No mesmo mundo, nada sai — nenhum ``RemoveDevice``, nenhuma lápide: o"""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    try:
        cena(casa)
        casa.central.limpar(cr.QUANDO_O_CONTROLE_DESLIGOU)
        casa.central.limpar()
        assert remocoes(casa.mundo) == [], remocoes(casa.mundo)
        assert casa.mundo.lapides == []
    finally:
        casa.fechar()


def test_sem_lapide_nada_sai_e_o_diario_diz_uma_vez(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com a ponte recusando, a dobra do André fica: nenhum ``RemoveDevice``,"""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    mundo = casa.mundo
    try:
        mundo.ponte_recusa = True
        mundo.chave_que_volta(VARANDA, ANDRE)
        for _ in range(3):
            assert casa.central.limpar(cr.NA_VOLTA_DA_FAXINA) == ()
        assert mundo.objeto(VARANDA, ANDRE) is not None, "a dobra saiu sem lápide"
        assert remocoes(mundo) == [] and mundo.lapides == []
        (linha,) = do_diario(diario, cr.NAO_LIMPOU_SEM_LAPIDE)
        assert (linha["controle"], linha["adaptador"]) == (ANDRE, VARANDA)

        mundo.ponte_recusa = False
        assert casa.central.limpar() == ((VARANDA, ANDRE),)
        assert mundo.lapides == [(VARANDA, ANDRE)]
    finally:
        casa.fechar()


def test_a_limpeza_tira_da_publicacao_o_que_nao_diz_mais_nada(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O «não chegou» de Johnathan sai da publicação na volta em que ele está"""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    central = casa.central
    try:
        central._guardar(movimento(JOHNATHAN, VARANDA))
        central._guardar(movimento(ROXO, VARANDA, cr.CHEGOU, motivo=""))
        central._guardar(movimento("", QUARTO, idade=cr.LEMBRA_O_NAO_CONECTOU_S - 30))

        def publicados() -> set[str]:
            return {m["aparelho"] for m in central.publicar()["movimentos"]}

        assert publicados() == {JOHNATHAN, ROXO, ""}
        central.limpar()
        assert publicados() == {ROXO, ""}, "o «não chegou» de quem está no ar ficou"
        central._guardar(movimento("", QUARTO, idade=cr.LEMBRA_O_NAO_CONECTOU_S + 1))
        central.limpar()
        assert publicados() == {ROXO}, "o anônimo de mais de 600 s ficou"
    finally:
        casa.fechar()


@pytest.mark.parametrize("pair", ["deu", "não deu"])
def test_a_chave_morta_da_origem_sai_so_quando_o_pair_deu(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, pair: str,
) -> None:
    """O verde guarda o Meio (desligado, com a chave lá). Ela liga o"""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, VERMELHO)
    mundo.pareado(QUARTO, VERDE, conectado=False)
    if pair == "deu":
        mundo.pair_mente = True
    else:
        mundo.pair_falha = True
    casa = Casa(a08, monkeypatch, mundo)
    try:
        casa.cena()
        casa.gesto("abrir-adaptador", alvo=id_da_tela(VARANDA))
        casa.cena()
        rm.ela_pareia(casa.relogio, mundo, casa.central, VERDE)
        casa.gesto("radio-procurar")
        casa.esperar_a_central()
        (feito,) = [m for m in casa.central.movimentos() if m.aparelho == VERDE]
        assert feito.estado == cr.NAO_CHEGOU, feito
        if pair == "deu":
            assert sorted(mundo.lapides) == sorted([(VARANDA, VERDE), (QUARTO, VERDE)])
            assert mundo.objeto(QUARTO, VERDE) is None, "a chave morta da origem ficou"
        else:
            assert (QUARTO, VERDE) not in mundo.lapides
            assert mundo.objeto(QUARTO, VERDE) is not None, "a casa dele saiu sem Pair"
    finally:
        casa.fechar()


def _desligado_na_varanda(casa: Casa) -> None:
    """Vitória desligada, com a chave na Esquerda."""
    casa.mundo.desligar(ROXO)


def test_a_chave_tirada_por_fora_ganha_lapide_depois_de_sessenta_segundos(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outro programa tira a chave da Vitória na Esquerda, com o serviço vivo."""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    central, mundo = casa.central, casa.mundo
    try:
        _desligado_na_varanda(casa)
        mundo.remover_por_fora(VARANDA, ROXO)
        comeco = casa.relogio.agora
        casa.relogio.agora = comeco + 59.0
        assert central.gravar_as_lapides_de_fora() == ()
        assert mundo.lapides == []
        casa.relogio.agora = comeco + 60.0
        assert central.gravar_as_lapides_de_fora() == ((VARANDA, ROXO),)
        assert mundo.lapides == [(VARANDA, ROXO)]
        assert central.gravar_as_lapides_de_fora() == ()
        (linha,) = do_diario(diario, cr.ENTERROU_O_QUE_SAIU_POR_FORA)
        assert (linha["controle"], linha["adaptador"]) == (ROXO, VARANDA)
    finally:
        casa.fechar()


def _desplugue(casa: Casa) -> list[tuple[str, str]]:
    casa.mundo.desplugar(VARANDA)
    return []


def _bluetoothd_reiniciado(casa: Casa) -> list[tuple[str, str]]:
    casa.mundo.remover_por_fora(VARANDA, ROXO)
    casa.relogio.agora += 5.0
    casa.central.gravar_as_lapides_de_fora()
    casa.relogio.agora += 5.0
    casa.mundo.reiniciar_o_bluetoothd()
    return []


def _o_proprio_hefesto(casa: Casa) -> list[tuple[str, str]]:
    """O «Esquecer» da tela: o ``RemoveDevice`` sob a trava, e a lápide DELE."""
    feito = gp.esquecer_o_pareamento(VARANDA, ROXO, dono=casa.dono,
                                     esquecer_na_ponte=casa.mundo.esquecer_na_ponte,
                                     quem="tela")
    assert feito.estado == gp.ESTADO_ESQUECEU, feito
    return [(VARANDA, ROXO)]


@pytest.mark.parametrize("cena", [_desplugue, _bluetoothd_reiniciado, _o_proprio_hefesto],
                         ids=lambda f: f.__name__.strip("_"))
def test_as_contraprovas_da_lapide_de_fora(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch, cena: Any,
) -> None:
    """Nenhuma lápide de fora: o adaptador desplugado (sai o ``Adapter1``), o"""
    casa = Casa(a08, monkeypatch, os_quatro_no_ar())
    central, mundo = casa.central, casa.mundo
    try:
        _desligado_na_varanda(casa)
        dele = cena(casa)
        casa.relogio.agora += cr.ESPERA_DA_LAPIDE_DE_FORA_S + 1.0
        assert central.gravar_as_lapides_de_fora() == ()
        assert mundo.lapides == dele, f"lápide de fora indevida: {mundo.lapides}"
        assert do_diario(diario, cr.ENTERROU_O_QUE_SAIU_POR_FORA) == []
    finally:
        casa.fechar()


def test_o_dono_da_janela_nunca_grava_lapide(
    diario: Path, a08: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A janela tem o dono dela, sem central: o mesmo sinal, visto por ele, não"""
    mundo, relogio = os_quatro_no_ar(), rm.Relogio()
    dono = bd.DonoVivo(mundo)
    assert dono.ligar()
    monkeypatch.setattr(a08, "_ler_o_bluez", lambda: (
        tuple(dono.adaptadores() or ()), tuple(dono.aparelhos() or ())))
    monkeypatch.setattr(a08, "_ordem_gravada",
                        lambda: [id_da_tela(e) for e in (SALA, QUARTO, VARANDA)])
    monkeypatch.setattr(a08, "_ler_os_zumbis", lambda: {})
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    ctx = Contexto(state={"controllers": [], "radio_central": {}}, conectados=[], mesa=[])
    try:
        a08._esquecer("bluez")
        a08.campos_do_radio(ctx)
        mundo.desligar(ROXO)
        mundo.remover_por_fora(VARANDA, ROXO)
        relogio.agora += cr.ESPERA_DA_LAPIDE_DE_FORA_S + 1.0
        for _ in range(3):
            a08._esquecer("bluez")
            a08.campos_do_radio(ctx)
        assert mundo.lapides == [] and dono._ouvintes == []
    finally:
        dono.fechar()


def test_o_desenho_nao_tem_linha_sem_aparelho() -> None:
    """A cena do desenho (a mesma que gera o mockup) mostra um «Não Conectou»"""
    from hefesto_dualsense4unix.interface import aba08

    linhas = [a for a in aba08.CENA_DO_RADIO["aparelhos"] if a.get("nao_conectou")]
    assert linhas, "o desenho perdeu o «Não Conectou»"
    assert [a["id"] for a in linhas if not a.get("aparelho")] == []
    assert all(a.get("nome") and a.get("cor") for a in linhas), linhas
    mockup = (RAIZ / "mockup" / "08-conexoes.html").read_text(encoding="utf-8")
    assert "Não Conectou" in mockup
