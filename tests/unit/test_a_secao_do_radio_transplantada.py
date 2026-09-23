#!/usr/bin/env python3
"""A seção «Rádio e Adaptadores» é o desenho aprovado — e cada fio dela tem dono.

**23/09/2026 — TRANSPLANTE-DA-SECAO-01.** O `mockup/mapa-do-radio.html` que ela
aprovou virou a seção `cx8-3` da aba Conexões. A regra da casa vale inteira: o
Python PINTA (`a08_conexoes.campos_da_secao`), a página só abre e fecha o que
veio pintado. Esta régua cobra o que costuma se perder numa transplantação —
e cada caso diz a mordida que o derruba.

1. **§P4 — âncora não é gesto.** `#mapear-entradas` e `#mapear-entrada-a-entrada`
   abrem por `:target`; um `data-gesto` nelas seria um segundo nome para o
   mesmo ato, e um gesto com o nome de uma âncora confunde os dois.
2. **Todo campo tem dono, e todo dono tem campo** — na página publicada, contra
   o que o pacote emite. Campo sem dono é pintura que cai no vazio; dono sem
   campo escreve para ninguém. Os dois dão verde calado.
3. **Todo gesto tem dono** — inclusive os que moram dentro de `<template>`
   (as janelas que a página abre), ou declarado em `SEM_GESTO` com a razão.
4. **A paridade com o desenho**: `PONTES_POR_ADAPTADOR` e `MARGINAL_DA_PONTE`
   do desenho são os do dono (`radio_da_mesa`).
5. **«fatia» não chega à tela** — nem no texto, nem em `title`, nem em classe.
6. **A sala é estável entre tiques** (os Hz moram em listas próprias) **e as
   listas caem nos elementos certos** (a ordem do DOM é a ordem da lista).
7. **O dublê do `radio.mover` é o daemon de verdade**: o gesto passa pelo
   tratador real, com a central e o governador de mentira atrás dele.
8. **«Além do limite» é laranja, nunca vermelho.**
9. **O sino lê o diário pela palavra dela**, pela hora, e nada cru.
10. **A porta sem nome se chama pelo `devpath`** («Entrada 4.1.4»).

A mesa é DECLARADA — BlueZ, `maquina.json`, `/sys` e o histórico entram por
dublê —, e a faixa de endereços é a sintética da casa.
"""
from __future__ import annotations

import asyncio
import pathlib
import re
import sys
import time
from html.parser import HTMLParser
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "08-conexoes.html"
DESENHO = RAIZ / "mockup" / "mapa-do-radio.html"

#: A faixa sintética da casa — há dois portões de anonimato nesta árvore.
A1 = "aa:bb:cc:00:00:09"
A2 = "aa:bb:cc:00:00:15"
U1 = "aabbcc000011"
U2 = "aabbcc000022"
U3 = "aabbcc000033"
PCI = "0000:00:14.0"
LUGAR_1 = f"pci-{PCI}-usb-0:1.2"
LUGAR_2 = f"pci-{PCI}-usb-0:4.1.4"

#: O id de um adaptador na cena é o endereço sem pontuação, em maiúsculas
#: (`a08_conexoes._mac`) — é o que vai no `data-alvo` e volta no clique.
I1 = A1.replace(":", "").upper()
I2 = A2.replace(":", "").upper()

#: As âncoras da cerimônia — abrem por `:target`, e só por ele.
ANCORAS = ("mapear-entradas", "mapear-entrada-a-entrada")

_VAZIOS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
           "meta", "source", "track", "wbr"}


class _Arvore(HTMLParser):
    """Os elementos (tag, atributos) e o texto de um trecho — ou só da subárvore
    do elemento `id=raiz`, contando a profundidade para saber onde ela fecha."""

    def __init__(self, raiz: str | None = None) -> None:
        super().__init__(convert_charrefs=True)
        self.raiz = raiz
        self.fundo = 0 if raiz else 1
        self.elementos: list[tuple[str, dict[str, str]]] = []
        self.texto: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if self.raiz and not self.fundo:
            if a.get("id") == self.raiz:
                self.fundo = 1
                self.elementos.append((tag, a))
            return
        if not self.fundo:
            return
        self.elementos.append((tag, a))
        if tag not in _VAZIOS:
            self.fundo += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.fundo:
            self.elementos.append((tag, {k: v or "" for k, v in attrs}))

    def handle_endtag(self, tag: str) -> None:
        if self.raiz and self.fundo:
            self.fundo -= 1
            if self.fundo == 0:
                self.fundo = -1  # a subárvore fechou: nada mais entra

    def handle_data(self, data: str) -> None:
        if self.fundo and self.fundo > 0:
            self.texto.append(data)


def _ler(html: str, raiz: str | None = None) -> _Arvore:
    arvore = _Arvore(raiz)
    arvore.feed(html)
    arvore.fundo = max(arvore.fundo, 0)
    return arvore


def _pagina() -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(PAGINA).read_text(encoding="utf-8")


def _secao_da_pagina() -> _Arvore:
    arvore = _ler(_pagina(), "rd-secao")
    assert arvore.elementos, "a página publicada perdeu o `#rd-secao`"
    return arvore


@pytest.fixture
def a08() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


# ---------------------------------------------------------------------------
# A MESA DECLARADA — dois adaptadores, três controles, uma caixa, um vizinho
# ---------------------------------------------------------------------------
@pytest.fixture
def mesa(a08: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    from hefesto_dualsense4unix.integrations.bluez_dbus import (
        AdaptadorDoBluez,
        AparelhoDoBluez,
    )
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa, RadioUsb
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    monkeypatch.setattr(a08, "LER_NA_HORA", True)
    monkeypatch.setattr(a08, "_FUNDO", {})
    monkeypatch.setattr(a08, "_ABERTO", {})
    monkeypatch.setattr(a08, "_CENA_NA_TELA", {})
    vizinho = RadioUsb(no="/bancada/usb/3-5", vid="046d", pid="08e5", busnum=3,
                       devpath="5", controlador_pci=PCI)
    monkeypatch.setattr(a08, "_mesa_do_radio",
                        lambda recarregar=False: Mesa(radios=(vizinho,)))
    adaptadores = (
        AdaptadorDoBluez("/org/bluez/hci0", "hci0", A1.upper(), lugar=LUGAR_1,
                         varrendo=False),
        AdaptadorDoBluez("/org/bluez/hci1", "hci1", A2.upper(), lugar=LUGAR_2,
                         varrendo=False),
    )
    aparelhos = (
        AparelhoDoBluez("/org/bluez/hci0/dev_AA_BB_CC_00_00_44", "/org/bluez/hci0",
                        "AA:BB:CC:00:00:44", nome="Caixa", conectado=True, classe=0x240414),
    )
    monkeypatch.setattr(a08, "_ler_o_bluez", lambda: (adaptadores, aparelhos))
    maquina = MaquinaConfig(lugares={LUGAR_1: {"nome": "Sala"}})
    monkeypatch.setattr(a08, "_ler_a_maquina", lambda: (maquina, {3: PCI}))
    monkeypatch.setattr(a08, "_ler_o_historico", lambda: {})
    return a08


def _estado(*, hz: tuple[float, float, float] = (250.0, 98.0, 200.0),
            movimentos: list[dict[str, Any]] | None = None,
            pedido: bool = True) -> dict[str, Any]:
    governador: dict[str, Any] = {A1: {"n_max": 2, "pontes": [
        {"uniq": U1, "tipo": "som", "alem_do_limite": True}]}}
    if pedido:
        governador[A1]["pedidos"] = [{"uniq": U2, "tipo": "som", "vagas": [A2]}]
    return {
        "controllers": [
            {"uniq": U1, "transport": "bt", "adaptador": A1, "hz_movimento": hz[0],
             "hz_voz": 16.2, "ponte_do_radio": "som", "audio": {"mic_mudo": False}},
            {"uniq": U2, "transport": "bt", "adaptador": A1, "hz_movimento": hz[1],
             "hz_voz": 0.0, "ponte_do_radio": None, "audio": {"mic_mudo": True}},
            {"uniq": U3, "transport": "bt", "adaptador": A2, "hz_movimento": hz[2],
             "hz_voz": 0.0, "ponte_do_radio": None, "audio": {"mic_mudo": True}},
        ],
        "radio_ar": {A1: {"pontes": [{"uniq": U1, "modo": "som"}], "n_max": 2,
                          "canais_evitados": [20, 21, 22, 40]},
                     A2: {"pontes": [], "n_max": 2, "canais_evitados": None}},
        "radio_governador": governador,
        "radio_central": {"movimentos": movimentos or [], "proposta": None},
    }


def _ctx(estado: dict[str, Any]) -> Any:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    return Contexto(state=estado, conectados=list(estado["controllers"]), mesa=[
        {"uniq": U1, "cor": "cosmic-red", "jogador": 1, "nome": "Cosmic Red"},
        {"uniq": U2, "cor": "white", "jogador": 2, "nome": "White"},
        {"uniq": U3, "cor": "", "jogador": 3, "nome": ""},
    ])


def _campos(mesa: Any, **kw: Any) -> dict[str, Any]:
    return mesa.campos_do_radio(_ctx(_estado(**kw)))


# ---------------------------------------------------------------------------
# 1. §P4 — âncora não é gesto
# ---------------------------------------------------------------------------
def test_as_ancoras_da_secao_nao_carregam_gesto() -> None:
    """MORDIDA: ponha `data-gesto` no `<a href="#mapear-entradas">` do gerador."""
    achadas = {a["href"][1:]: a for tag, a in _secao_da_pagina().elementos
               if tag == "a" and a.get("href", "").startswith("#")
               and a["href"][1:] in ANCORAS}
    assert set(achadas) == set(ANCORAS), f"a seção perdeu uma porta: {sorted(achadas)}"
    for alvo, a in achadas.items():
        assert "data-gesto" not in a, (
            f"a âncora #{alvo} ganhou `data-gesto={a['data-gesto']!r}` — ela abre "
            f"por `:target`, e o gesto seria um segundo nome para o mesmo ato")


def test_nenhum_gesto_se_chama_como_uma_ancora() -> None:
    """MORDIDA: registre `@gesto("08-conexoes.html", "mapear-entradas")`."""
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    ids = set(re.findall(r'\bid="([^"]+)"', _pagina()))
    nomes = {n for p, n in GESTOS if p == PAGINA}
    assert not (nomes & set(ANCORAS)), sorted(nomes & set(ANCORAS))
    telas = {i for i in ids if i.startswith("mapear-")}
    assert not (nomes & telas), f"gesto com nome de tela: {sorted(nomes & telas)}"


# ---------------------------------------------------------------------------
# 2 e 3. Os fios — campo com dono, dono com campo, gesto com dono
# ---------------------------------------------------------------------------
def test_todo_campo_da_secao_tem_dono_e_todo_dono_tem_campo(mesa: Any) -> None:
    """MORDIDA: tire o `data-campo="radio-moldes"` do gerador e publique — o
    pacote passa a escrever para ninguém, e a segunda asserção nomeia o campo."""
    na_pagina = {a["data-campo"] for _t, a in _secao_da_pagina().elementos
                 if "data-campo" in a}
    emitidos = set(_campos(mesa))
    assert na_pagina - emitidos == set(), (
        f"campo na seção sem dono no pacote: {sorted(na_pagina - emitidos)}")
    # O contador e o «quem» da cerimônia moram nas três telas, FORA da seção.
    em_toda_a_pagina = set(re.findall(r'data-campo="([^"]+)"', _pagina()))
    assert emitidos - em_toda_a_pagina == set(), (
        f"o pacote escreve para campo que a página não tem: "
        f"{sorted(emitidos - em_toda_a_pagina)}")
    assert set(mesa.campos_da_secao(mesa._CENA_NA_TELA)) <= na_pagina


def _gestos_de(html: str) -> set[str]:
    return {a["data-gesto"] for _t, a in _ler(html).elementos if "data-gesto" in a}


def test_todo_gesto_da_secao_tem_dono(mesa: Any) -> None:
    """Na página publicada E no que o produto pinta (sala, janelas, balão).

    MORDIDA: troque o `data-gesto` do botão do balão por um nome sem `@gesto`.
    """
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    campos = _campos(mesa)
    pintados = _gestos_de(campos["radio-sala"]) | _gestos_de(campos["radio-moldes"])
    na_pagina = {a["data-gesto"] for _t, a in _secao_da_pagina().elementos
                 if "data-gesto" in a}
    donos = {n for p, n in GESTOS if p == PAGINA}
    sem = {k for k, v in mesa.SEM_GESTO.items() if str(v).strip()}
    orfaos = (pintados | na_pagina) - donos - sem
    assert not orfaos, f"gesto sem dono e sem razão declarada: {sorted(orfaos)}"
    assert {"confirmar-mudanca", "ligar-mesmo-assim", "aceitar-sugestao",
            "adaptador-renomear", "abrir-adaptador"} <= (pintados | na_pagina)


# ---------------------------------------------------------------------------
# 4. A paridade com o desenho aprovado
# ---------------------------------------------------------------------------
def test_as_constantes_do_desenho_sao_as_do_dono(a08: Any) -> None:
    """MORDIDA: mude `radio_da_mesa.N_MAX_PONTES` para 3."""
    from hefesto_dualsense4unix.integrations import radio_da_mesa as dono

    assert a08.PONTES_POR_ADAPTADOR == dono.N_MAX_PONTES
    assert a08.MARGINAL_DA_PONTE == (dono.FATIAS_DA_PONTE - 1) * dono.HZ_DA_PONTE
    desenho = DESENHO.read_text(encoding="utf-8")
    pontes = re.search(r"const PONTES_POR_ADAPTADOR = ([\d.]+);", desenho)
    marginal = re.search(r"const MARGINAL_DA_PONTE = ([\d.]+);", desenho)
    assert pontes and marginal, "o desenho aprovado perdeu as duas constantes"
    assert float(pontes.group(1)) == a08.PONTES_POR_ADAPTADOR
    assert float(marginal.group(1)) == a08.MARGINAL_DA_PONTE


# ---------------------------------------------------------------------------
# 5. «fatia» não chega à tela
# ---------------------------------------------------------------------------
_ATRIBUTOS_QUE_SE_LEEM = ("title", "aria-label", "placeholder", "class", "value")


def _fala_fatia(arvore: _Arvore) -> list[str]:
    achados = [t for t in arvore.texto if re.search(r"fatia", t, re.I)]
    for _t, a in arvore.elementos:
        achados += [f"{k}={a[k]!r}" for k in _ATRIBUTOS_QUE_SE_LEEM
                    if re.search(r"fatia", a.get(k, ""), re.I)]
    return achados


def test_fatia_nao_chega_a_tela(mesa: Any) -> None:
    """MORDIDA: devolva `class="fatias"` à `conta-da-vaga` do pacote."""
    assert not _fala_fatia(_secao_da_pagina())
    campos = _campos(mesa)
    for chave in ("radio-sala", "radio-moldes", "espectro-canais", "meus-no-ar"):
        assert not _fala_fatia(_ler(str(campos[chave]))), chave


# ---------------------------------------------------------------------------
# 6. A sala estável e as listas no lugar certo
# ---------------------------------------------------------------------------
def test_a_sala_nao_muda_quando_so_os_hz_mudam(mesa: Any) -> None:
    """O piloto troca a sala inteira quando o texto muda: com os Hz dentro, ela
    seria reescrita a cada tique, com o nome que ela está digitando junto.

    MORDIDA: chame `html_da_sala(cena, com_hz=True)` em `campos_da_secao`.
    """
    antes = _campos(mesa, hz=(250.0, 98.0, 200.0))
    depois = _campos(mesa, hz=(249.1, 97.3, 201.8))
    assert antes["radio-sala"] == depois["radio-sala"]
    assert antes["hz-movimento"] != depois["hz-movimento"]


def test_as_listas_de_hz_caem_nos_elementos_certos(mesa: Any) -> None:
    """A lista vai pela ordem do DOM: ela tem de ser a ordem das linhas na sala.

    MORDIDA: ordene os `controles` de `campos_da_secao` por outra chave.
    """
    campos = _campos(mesa, hz=(250.0, 98.0, 200.0))
    ordem = [a["data-alvo"] for _t, a in _ler(campos["radio-sala"]).elementos
             if a.get("data-campo") == "hz-movimento"]
    esperado = {U1: "250", U2: "98", U3: "200"}
    assert len(ordem) == len(campos["hz-movimento"]) == 3, (ordem, campos["hz-movimento"])
    for alvo, valor in zip(ordem, campos["hz-movimento"], strict=True):
        assert valor.startswith(esperado[alvo]), (
            f"o Hz de {alvo} caiu no elemento de outro: {valor!r}")
    pouco = [a["data-alvo"] for _t, a in _ler(campos["radio-sala"]).elementos
             if a.get("data-campo") == "hz-pouco"]
    assert pouco == ordem
    assert campos["hz-pouco"] == ["", "sim", ""], campos["hz-pouco"]
    voz = [a["data-alvo"] for _t, a in _ler(campos["radio-sala"]).elementos
           if a.get("data-campo") == "hz-voz"]
    assert voz == [U1] and len(campos["hz-voz"]) == 1


# ---------------------------------------------------------------------------
# 7. O dublê do `radio.mover` é o tratador de verdade
# ---------------------------------------------------------------------------
class _CentralDeMentira:
    def __init__(self, ocupada: bool = False) -> None:
        self.ocupada = ocupada
        self.pedidos: list[tuple[str, str | None]] = []

    def _movimento(self, aparelho: str, destino: str | None) -> Any:
        from hefesto_dualsense4unix.integrations import central_do_radio as c

        if self.ocupada:
            return c.Movimento(aparelho, destino or "", c.NAO_CHEGOU, c.PASSO_FIM,
                               c.MOTIVO_OCUPADO)
        return c.Movimento(aparelho, destino or "", c.ESPERANDO, c.PASSO_PREPARANDO)

    def comecar_a_mover(self, aparelho: str, destino: str | None = None) -> Any:
        self.pedidos.append((aparelho, destino))
        return self._movimento(aparelho, destino)

    def comecar_a_conectar(self, destino: str | None = None) -> Any:
        self.pedidos.append(("", destino))
        return self._movimento("", destino)


class _GovernadorDeMentira:
    def __init__(self) -> None:
        self.ligados: list[str] = []

    def ligar_aqui(self, uniq: str) -> bool:
        self.ligados.append(uniq)
        return True


class _PonteQueVaiAoDaemon:
    """O `ponte.resultado` com o TRATADOR REAL do daemon atrás — a validação de
    parâmetro e a tradução de `ocupado` são as dele, nunca mais frouxas."""

    def __init__(self, central: Any, governador: Any) -> None:
        from types import SimpleNamespace

        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        class _Daemon(IpcHandlersMixin):
            pass

        self.eu = _Daemon()
        self.eu.daemon = SimpleNamespace(  # type: ignore[attr-defined]
            _central_do_radio=central,
            _alto_falante_subsystem=SimpleNamespace(governador=governador))
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        tratador = {"radio.mover": self.eu._handle_radio_mover,
                    "radio.ponte.ligar_aqui": self.eu._handle_radio_ponte_ligar_aqui}
        assert metodo in tratador, f"método que o daemon não atende: {metodo}"
        self.chamadas.append((metodo, dict(params)))
        return asyncio.run(tratador[metodo](params))


def test_os_metodos_existem_no_servidor() -> None:
    fonte = (RAIZ / "src/hefesto_dualsense4unix/daemon/ipc_server.py").read_text(
        encoding="utf-8")
    assert '"radio.mover": self._handle_radio_mover' in fonte
    assert '"radio.ponte.ligar_aqui": self._handle_radio_ponte_ligar_aqui' in fonte


def _gesto(nome: str) -> Any:
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    return GESTOS[(PAGINA, nome)]


def test_mover_manda_o_destino_que_a_tela_mostrou(mesa: Any) -> None:
    """MORDIDA: tire `"destino"` dos parâmetros de `_mover` — a central decide
    sozinha, e a ordem da tela diverge da dela no empate."""
    _campos(mesa)
    central = _CentralDeMentira()
    ponte = _PonteQueVaiAoDaemon(central, _GovernadorDeMentira())
    assert _gesto("confirmar-mudanca")(None, {"alvo": U3, "destino": I1}, ponte) == {
        "armou": True}
    assert central.pedidos == [(U3, I1)]
    assert ponte.chamadas == [("radio.mover", {"destino": I1, "aparelho": U3})]


def test_ocupado_treme_o_botao_e_nao_passa_calado(mesa: Any) -> None:
    """A recusa da central vira `RuntimeError` — é o que faz o botão tremer."""
    _campos(mesa)
    ponte = _PonteQueVaiAoDaemon(_CentralDeMentira(ocupada=True), _GovernadorDeMentira())
    with pytest.raises(RuntimeError, match="ocupado"):
        _gesto("confirmar-mudanca")(None, {"alvo": U3, "destino": I1}, ponte)


def test_com_um_movimento_esperando_a_tela_nem_pede(mesa: Any) -> None:
    """Item 6: um movimento esperando PS + Create segura todo «Mover».

    MORDIDA: tire a guarda do `_CENA_NA_TELA["ocupado"]` de `_mover`.
    """
    esperando = [{"estado": "esperando", "quando": time.time(), "destino": A2,
                  "aparelho": U3}]
    campos = _campos(mesa, movimentos=esperando)
    assert campos["radio-ocupado"] == "sim"
    assert "pergunta-molde" not in campos["radio-moldes"]
    central = _CentralDeMentira()
    ponte = _PonteQueVaiAoDaemon(central, _GovernadorDeMentira())
    with pytest.raises(RuntimeError):
        _gesto("confirmar-mudanca")(None, {"alvo": U1, "destino": I2}, ponte)
    assert central.pedidos == [] and ponte.chamadas == []


def test_conectar_sem_alvo_abre_a_janela_no_destino_da_tela(mesa: Any) -> None:
    _campos(mesa)
    central = _CentralDeMentira()
    ponte = _PonteQueVaiAoDaemon(central, _GovernadorDeMentira())
    _gesto("escolher-adaptador")(None, {"alvo": I2}, ponte)
    _gesto("conectar-aparelho")(None, {}, ponte)
    assert central.pedidos == [("", I2)]


def test_ligar_aqui_sobe_a_ponte_pelo_governador(mesa: Any) -> None:
    governador = _GovernadorDeMentira()
    ponte = _PonteQueVaiAoDaemon(_CentralDeMentira(), governador)
    _gesto("ligar-mesmo-assim")(None, {"alvo": U2}, ponte)
    assert governador.ligados == [U2]


def test_o_pedido_do_governador_vira_a_janela_de_duas_saidas(mesa: Any) -> None:
    """R3: «Mover e ligar» para a vaga, ou «Ligar aqui» além do limite."""
    moldes = _campos(mesa)["radio-moldes"]
    pedido = [a for t, a in _ler(moldes).elementos
              if t == "template" and a.get("data-pedido")]
    assert len(pedido) == 1, moldes[:400]
    assert pedido[0]["data-sim"] == "Mover e ligar"
    assert pedido[0]["data-outro"] == "Ligar aqui"
    assert pedido[0]["data-alvo"] == U2 and pedido[0]["data-destino"] == I2


# ---------------------------------------------------------------------------
# 8. «Além do limite» é laranja, nunca vermelho
# ---------------------------------------------------------------------------
def test_alem_do_limite_e_laranja_nunca_vermelho(mesa: Any) -> None:
    """MORDIDA: troque `var(--orange)` por `var(--red)` numa regra `.alem`."""
    regras = re.findall(r"(\.radio [^{}]*)\{([^}]*)\}", _pagina())
    assert regras, "a folha da seção sumiu da página"
    for seletor, corpo in regras:
        assert "var(--red)" not in corpo, f"vermelho na seção: {seletor}"
        if ".alem" in seletor:
            assert "var(--orange)" in corpo, f"`.alem` sem o laranja: {seletor}"
    sala = _campos(mesa)["radio-sala"]
    assert re.search(r'class="vaga som alem"', sala), (
        "a ponte além do limite não ganhou a marca na linha")


def test_quem_passou_do_limite_e_quem_o_governador_marcou(mesa: Any) -> None:
    """A «N de 2» de cada linha é a ordem em que as pontes CHEGARAM, e a que
    passou do limite é a que o governador marcou — um dono só.

    O governador tira a marca das `n_max` primeiras vagas na ordem de chegada
    (`_recalcular_o_limite`); a tela numerava pela ordem de `controllers`. Com
    o Cosmic Red na frente da lista e marcado, a linha dele dizia «1 de 2» com
    o botão de som laranja, e a de OUTRO controle dizia «Passou do limite».

    MORDIDA: devolva `_pontes` à ordem da cena (tire o `sorted`), ou ordene só
    pela marca e esqueça a ordem de chegada (`ordem_da_vaga`).
    """
    estado = _estado(pedido=False)
    for c in estado["controllers"]:
        c.update(adaptador=A1, ponte_do_radio="som")
    # Chegaram o P3, o P2 e, por «Ligar aqui», o P1 — a lista da cena é P1, P2, P3.
    estado["radio_governador"] = {A1: {"n_max": 2, "pontes": [
        {"uniq": U3, "tipo": "som", "alem_do_limite": False},
        {"uniq": U2, "tipo": "som", "alem_do_limite": False},
        {"uniq": U1, "tipo": "som", "alem_do_limite": True}]}}
    sala = mesa.html_da_sala(mesa.cena_do_radio(_ctx(estado)))
    contas = {alvo: (bool(alem), texto) for alem, alvo, texto in re.findall(
        r'<span class="conta-da-vaga( alem)?" data-alvo="([^"]+)" title="[^"]*">([^<]*)</span>',
        sala) if alvo in (U1, U2, U3)}
    assert contas == {U3: (False, "1 de 2"), U2: (False, "2 de 2"), U1: (True, "3 de 2")}, (
        f"a vaga de cada linha não é a do governador: {contas}")
    laranjas = re.findall(r'class="vaga som alem"[^>]*data-alvo="([^"]+)"', sala)
    assert laranjas == [U1], f"o som laranja está em outra linha: {laranjas}"


# ---------------------------------------------------------------------------
# 9. O sino — pela palavra dela, pela hora, nada cru
# ---------------------------------------------------------------------------
def test_o_sino_diz_so_o_que_a_tela_sabe_dizer_e_pela_hora(a08: Any) -> None:
    """MORDIDA: pouse o `motivo` da linha do diário em vez da frase."""
    agora = time.time()
    diario = [
        {"o_que": "adaptador cheio", "carimbo": agora - 300, "adaptador": A1,
         "motivo": "EAGAIN na fila de saída do hci0"},
        {"o_que": "fila parada", "carimbo": agora - 60, "adaptador": A1},
        {"o_que": "ponte subiu", "carimbo": agora - 30, "adaptador": A1},
        {"o_que": "ponte subiu", "carimbo": agora - 10, "adaptador": A1,
         "alem_do_limite": True},
        {"o_que": "reset do controlador hci0", "carimbo": agora - 5, "adaptador": A1},
    ]
    sino = a08._quedas_por_adaptador({"diario": diario}, {}, None, {})[I1]
    assert [q["porque"] for q in sino] == [
        a08.FRASE_DO_DIARIO["ponte subiu"], a08.FRASE_DO_DIARIO["fila parada"],
        a08.FRASE_DO_DIARIO["adaptador cheio"]]
    assert [q["carimbo"] for q in sino] == sorted((q["carimbo"] for q in sino), reverse=True)
    for q in sino:
        assert "EAGAIN" not in q["porque"] and "hci" not in q["porque"]


def test_o_sino_diz_desde_quando_se_mede(mesa: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O «desde» vem do `medida_desde` do dono, no dia e mês dela."""
    monkeypatch.setattr(mesa, "_ler_o_historico", lambda: {
        "desde": "2026-09-21T08:00:00", "quedas": [],
        "diario": [{"o_que": "fila parada", "carimbo": time.time(), "adaptador": A1}]})
    mesa._FUNDO.clear()
    cena = mesa.cena_do_radio(_ctx(_estado()))
    lug = next(lg for lg in cena["lugares"] if lg["id"] == I1)
    assert lug["quedas_desde"] == "21/09"
    assert 'data-gesto="adaptador-historico"' in mesa.html_da_sala(cena)


# ---------------------------------------------------------------------------
# 10. A porta sem nome, e o nome que ela digita
# ---------------------------------------------------------------------------
def test_a_porta_sem_numero_se_chama_pelo_devpath() -> None:
    """MORDIDA: devolva `None` no fim de `rotulo_da_entrada`."""
    from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    vazia = MaquinaConfig()
    assert ee.rotulo_da_entrada(LUGAR_2, maquina=vazia, controladores={3: PCI}) == (
        "Entrada 4.1.4")
    assert ee.face_do_lugar(LUGAR_2, maquina=vazia, controladores={3: PCI}) is None
    assert ee.rotulo_da_entrada("", maquina=vazia, controladores={}) is None
    assert ee.rotulo_do_numero("3") == "Entrada 3"
    assert ee.rotulo_do_numero("") is None


def test_o_nome_que_ela_digita_nao_vira_marcacao(mesa: Any, monkeypatch: pytest.MonkeyPatch,
                                                  ) -> None:
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    maquina = MaquinaConfig(lugares={LUGAR_1: {"nome": "<b>Sala</b>"}})
    monkeypatch.setattr(mesa, "_ler_a_maquina", lambda: (maquina, {3: PCI}))
    campos = _campos(mesa)
    for chave in ("radio-sala", "radio-moldes"):
        assert "<b>Sala</b>" not in campos[chave], chave
    assert "&lt;b&gt;Sala&lt;/b&gt;" in campos["radio-sala"]


def test_o_microfone_da_linha_e_o_gesto_da_aba_02(mesa: Any,
                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    """D-12: o 🎙 é UM ato. O da linha do controle é o `mudo` da 02, chamado —
    o que ela grava no perfil, confessa e recusa vale igual aqui.

    MORDIDA: volte a pedir `mic_canal_set_detalhado` direto no `custo_mic` — o
    perfil deixa de lembrar o microfone ligado por esta aba, e a identidade cai.
    """
    from hefesto_dualsense4unix.interface.pacotes import a02_controles

    assert mesa._o_mudo_da_aba_02 is a02_controles.mudo
    pedidos: list[dict[str, Any]] = []
    monkeypatch.setattr(mesa, "_o_mudo_da_aba_02", lambda ctx, o, p: pedidos.append(o))
    ctx = _ctx(_estado())
    _gesto("custo-mic")(ctx, {"alvo": U1, "evento": "click"}, None)
    assert pedidos == [{"uniq": U1, "mudo": "microfone"}]
    with pytest.raises(ValueError):
        _gesto("custo-mic")(ctx, {"alvo": "aabbcc0000ff"}, None)
