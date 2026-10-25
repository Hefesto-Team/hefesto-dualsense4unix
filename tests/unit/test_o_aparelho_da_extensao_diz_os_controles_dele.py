"""Cada aparelho de uma extensão diz na janela os controles que ele tem.

O-APARELHO-DA-EXTENSAO-DIZ-OS-CONTROLES-DELE-NA-JANELA-01 (24/10/2026). O aparelho do
``acessorios.estado`` declara ``controles`` (uma chave, uma paleta, uma escolha), o manifesto diz a
aba (``aparelhos_controles.grupo``), a janela desenha um cartão por aparelho que os tem e o clique
volta como ``extensao.acao`` com o ``alvo`` do aparelho, só à extensão dona. O cartão mostra o
valor do estado, e o clique fica «em curso» até o estado seguinte o confirmar.

MORDIDAS (24/10/2026, executadas sobre a cura e devolvidas):

- o ``alvo`` tirado do ``data-v`` do controle reprova
  ``test_a_paleta_clicada_no_terceiro_ponto_chega_so_a_extensao_dona`` e
  ``test_cada_tipo_de_controle_pede_o_valor_do_tipo_dele``;
- o cartão desenhado para o aparelho sem ``controles`` reprova
  ``test_tres_aparelhos_dao_dois_cartoes_cada_um_com_os_seus``;
- o teto de seis controles tirado da porta reprova
  ``test_o_estado_torto_e_recusado_com_a_frase[sete-controles]``;
- o ponto aceso pelo clique (e não pelo estado) reprova
  ``test_o_cartao_mostra_o_valor_do_estado_e_espera_em_curso``.
- (25/10/2026, no desenho regerado) o grupo sem quebrar a fileira (``nowrap``), a coluna do
  rótulo de volta aos 40px, e os dois juntos como eram, reprovam
  ``test_toda_opcao_do_contrato_fica_inteira_e_o_rotulo_nao_invade`` nas duas vistas.
"""

from __future__ import annotations

import asyncio
import copy
import json
import pathlib
import re
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.mods.manifesto import ManifestoRecusadoError, ler_manifesto
from hefesto_dualsense4unix.mods.porta import RecusaError, estado_dos_acessorios
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import (  # noqa: F401
    _entrar,
    _porta,
    curto,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    _manifesto,
    _Ponte,
    _pecas as _pecas_geridas,
    _servico,
    janela,
)

ABA = "Luz"
CORES: list[dict[str, Any]] = [
    {"id": "vermelho", "cor": "#ff5555", "rotulo": "Vermelho"},  # (noqa-acento) contrato
    {"id": "verde", "cor": "#50fa7b", "rotulo": "Verde"},  # (noqa-acento) contrato
    {"id": "azul", "cor": "#6c8cff", "rotulo": "Azul"},  # (noqa-acento) contrato
    {"id": "brasa", "cor": ["#bd93f9", "#ffb86c", "#ff5555"],
     "rotulo": "Brasa"}]  # (noqa-acento) contrato
ESCOLHA = [{"id": "fixa", "rotulo": "Fixa"},  # (noqa-acento) contrato
           {"id": "pisca", "rotulo": "Pisca"}]


def _aparelhos() -> list[dict[str, Any]]:
    """Três aparelhos: chave e paleta (e uma escolha), só a chave, e nenhum controle."""
    return [
        {"id": "ap-1", "nome": "Aparelho 1", "estado": "ligado", "ligado": True, "controles": [
            {"id": "luz", "tipo": "chave", "valor": True, "dica": "Acesa"},
            {"id": "cor", "tipo": "paleta", "valor": "verde",
             "opcoes": copy.deepcopy(CORES)},  # (noqa-acento) contrato
            {"id": "jeito", "tipo": "escolha", "valor": "fixa",  # (noqa-acento) contrato
             "rotulo": "Jeito",
             "opcoes": copy.deepcopy(ESCOLHA)}]},  # (noqa-acento) contrato
        {"id": "ap-2", "nome": "Aparelho 2", "estado": "ligado", "ligado": True, "controles": [
            {"id": "luz", "tipo": "chave", "valor": False}]},
        {"id": "ap-3", "nome": "Aparelho 3", "estado": "ligado", "ligado": True},
    ]


def _estado(aparelhos: list[dict[str, Any]] | None = None, serie: int = 1) -> dict[str, Any]:
    """O estado como a porta o guarda: validado, com a ``serie`` que a janela espera."""
    bruto = {"ligado": True, "aparelhos": _aparelhos() if aparelhos is None else aparelhos}
    return {**estado_dos_acessorios("toque", bruto), "serie": serie}


def _pecas() -> dict[str, Any]:
    return {"aparelhos_controles": {"grupo": ABA}}  # (noqa-acento) contrato


def _cartoes(html: str) -> dict[str, str]:
    """Os cartões dos controles, pelo ``alvo``: o bloco ``#mod-controles`` partido por cartão."""
    inicio = html.find('id="mod-controles">')
    miolo = html[inicio:] if inicio >= 0 else html
    fins = [n for n in (miolo.find('<input type="radio"'), miolo.find('class="tn-rod"')) if n > 0]
    miolo = miolo[:min(fins)] if fins else miolo
    partes = re.split(r'(?=<div class="mj-ap mj-cc[^"]*" data-alvo=")', miolo)
    cartoes = {}
    for parte in partes:
        alvo = re.match(r'<div class="mj-ap mj-cc[^"]*" data-alvo="([^"]+)"', parte)
        if alvo:
            cartoes[alvo.group(1)] = parte
    return cartoes


def _pedido(cartao: str, controle: str, quer: str) -> dict[str, str]:
    """O clique que o elemento desenhado manda: ``data-v`` e ``data-quer``, lidos do HTML."""
    achado = re.search(
        rf'data-gesto="acao-da-modificacao" data-v="([^"]*:{controle}(?::[^"]*)?)" '
        rf'data-quer="{quer}"', cartao)
    assert achado, f"o controle {controle} não desenhou o pedido {quer}"
    return {"v": achado.group(1), "quer": quer}


# -- 1. os cartões --------------------------------------------------------------------------


def test_tres_aparelhos_dao_dois_cartoes_cada_um_com_os_seus(janela: Any, ctx: Any) -> None:  # noqa: F811
    # D-2510-OS-CONTROLES-DO-APARELHO-NA-JANELA
    _a07, instalar, abrir = janela
    instalar(**_pecas())
    html = abrir(_Ponte(_estado()))["blocos"]["#mod-janela"]
    assert f">{ABA}</label>" in html, "a aba dos controles não apareceu"
    cartoes = _cartoes(html)
    assert set(cartoes) == {"ap-1", "ap-2"}, "o aparelho sem controles ganhou cartão, ou faltou um"
    um, dois = cartoes["ap-1"], cartoes["ap-2"]
    assert um.count('role="switch"') == 1 and dois.count('role="switch"') == 1
    assert um.count('data-v="toque:cor:ap-1"') == len(CORES), "a paleta não tem um ponto por cor"
    assert um.count('data-v="toque:jeito:ap-1"') == len(ESCOLHA)
    assert ">Cor<" in um and ">Jeito<" in um, "a linha não diz o que é"
    assert 'class="mj-cores mj-pontos"' in um and "conic-gradient(" in um, (
        "a cor de três não virou fatias")
    assert "data-v=\"toque:cor" not in dois and "jeito" not in dois, (
        "o vizinho ganhou o que não tem")
    assert 'aria-checked="true"' in um and 'aria-checked="false"' in dois


def test_sem_aparelho_com_controles_a_aba_some_e_volta_com_o_primeiro(
        janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(**_pecas())
    sem = [{k: v for k, v in ap.items() if k != "controles"} for ap in _aparelhos()]
    ponte = _Ponte(_estado(sem))
    html = abrir(ponte)["blocos"]["#mod-janela"]
    assert f">{ABA}</label>" not in html and "mod-controles" not in html, "a aba vazia apareceu"
    ponte.estado = _estado(serie=2)
    a07._AGORA.ler("toque", ponte)
    blocos = a07._com_os_aparelhos({"blocos": {}})["blocos"]
    assert f">{ABA}</label>" in blocos.get("#mod-janela", ""), "o tique não trouxe a aba nova"
    assert set(_cartoes(blocos["#mod-janela"])) == {"ap-1", "ap-2"}
    blocos = a07._com_os_aparelhos({"blocos": {}})["blocos"]
    assert "#mod-janela" not in blocos
    assert set(_cartoes(blocos["#mod-controles"])) == {"ap-1", "ap-2"}
    ponte.estado = _estado(sem, serie=3)
    a07._AGORA.ler("toque", ponte)
    blocos = a07._com_os_aparelhos({"blocos": {}})["blocos"]
    assert f">{ABA}</label>" not in blocos.get("#mod-janela", "-"), "a aba ficou sem controle"


@pytest.mark.parametrize(("grupo", "abas"), [
    ("Luz", ["Aparelhos", "Toques", "Luz"]),
    ("Toques", ["Aparelhos", "Toques"]),
])
def test_a_aba_dos_controles_vem_por_ultimo_ou_no_lugar_da_opcao(
        janela: Any, ctx: Any, grupo: str, abas: list[str]) -> None:  # noqa: F811
    """A aba nova fica depois das opções, como a Luz no arranjo C; a de uma opção fica onde ela
    está, e a ordem das abas escolhida em 19/10 não muda."""
    _a07, instalar, abrir = janela
    instalar(**{**_pecas_geridas(), "aparelhos_controles": {"grupo": grupo}})
    html = abrir(_Ponte(_estado()))["blocos"]["#mod-janela"]
    assert re.findall(r'<label for="mj-aba-\d+">([^<]*)</label>', html) == abas
    assert set(_cartoes(html)) == {"ap-1", "ap-2"}


# -- 2. o clique ----------------------------------------------------------------------------


@pytest.mark.parametrize(("alvo", "controle", "quer", "valor"), [
    ("ap-1", "luz", "0", False),
    ("ap-2", "luz", "1", True),
    ("ap-1", "cor", "brasa", "brasa"),
    ("ap-1", "jeito", "pisca", "pisca"),
])
def test_cada_tipo_de_controle_pede_o_valor_do_tipo_dele(
        janela: Any, ctx: Any, alvo: str, controle: str, quer: str, valor: Any) -> None:  # noqa: F811
    """A matriz: a chave ligada pede desligar, a desligada pede ligar, e a paleta e a escolha pedem
    o ``id`` da opção, cada uma com o ``alvo`` do aparelho do usuário."""
    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(_estado())
    cartao = _cartoes(abrir(ponte)["blocos"]["#mod-janela"])[alvo]
    a07.acao_da_modificacao(ctx, _pedido(cartao, controle, quer), ponte)
    feitas = [p for m, p in ponte.chamadas if m == "mods.acao"]
    assert feitas == [{"mod": "toque", "acao": controle, "alvo": alvo,  # (noqa-acento) contrato
                       "valor": valor}], feitas


def _instalada_como(lugares: Any, mod_id: str) -> None:
    pasta = lugares.codigo / mod_id
    pasta.mkdir(parents=True)
    manifesto = {**_manifesto(**_pecas()), "id": mod_id}
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")


def test_a_paleta_clicada_no_terceiro_ponto_chega_so_a_extensao_dona(
        janela: Any, ctx: Any, lar: Any, curto: pathlib.Path) -> None:  # noqa: F811
    # D-2410-A-EXTENSAO-DECLARA-ACOES-E-O-CLIQUE-VAI-SO-A-ELA
    """A cadeia inteira: a extensão publica o estado pela porta, a janela desenha, o terceiro ponto
    da paleta do primeiro aparelho é clicado, o serviço confere e a porta entrega só à dona."""
    a07, instalar, abrir = janela
    instalar("acessorios", **_pecas())

    async def corrida() -> None:
        porta = await _porta(curto, EventBus())
        bruto = {"ligado": True, "aparelhos": _aparelhos()}
        a = await _entrar(curto, "ficha-a", bruto)
        b = await _entrar(curto, "ficha-b", bruto)
        try:
            ponte = _Ponte({**porta.agora_de("acessorios"), "serie": 1})
            cartao = _cartoes(abrir(ponte, "acessorios")["blocos"]["#mod-janela"])["ap-1"]
            terceira = CORES[2]["id"]
            await asyncio.to_thread(a07.acao_da_modificacao, ctx,
                                    _pedido(cartao, "cor", terceira), ponte)
            pedido = next(p for m, p in ponte.chamadas if m == "mods.acao")
            servico = _servico(SimpleNamespace(lugares=lar, porta=porta))
            assert await IpcHandlersMixin._handle_mods_acao(servico, pedido) == {"enviada": True}
            chegou = await asyncio.to_thread(a.esperar_evento, 2.0)
            assert chegou is not None, "a extensão dona não recebeu o clique"
            assert chegou["params"]["nome"] == "extensao.acao"
            assert chegou["params"]["dados"] == {"mod": "acessorios",
                                                 "acao": "cor",  # (noqa-acento) contrato
                                                 "alvo": "ap-1", "valor": terceira}
            vazou = await asyncio.to_thread(b.esperar_evento, 0.4)
            assert vazou is None, f"a outra extensão recebeu o clique: {vazou}"
        finally:
            a.fechar()
            b.fechar()
            await porta.parar()

    asyncio.run(corrida())


def test_o_cartao_mostra_o_valor_do_estado_e_espera_em_curso(janela: Any, ctx: Any) -> None:  # noqa: F811
    # D-2410-O-BOTAO-DA-ACAO-DIZ-EM-CURSO-ATE-A-SERIE-SUBIR
    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(_estado())
    cartao = _cartoes(abrir(ponte)["blocos"]["#mod-janela"])["ap-1"]
    a07.acao_da_modificacao(ctx, _pedido(cartao, "cor", "azul"), ponte)
    a07._AGORA.ler("toque", ponte)
    um = _cartoes(a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-controles"])["ap-1"]
    assert 'class="mj-cores mj-pontos em-curso"' in um, "a paleta clicada não diz que espera"
    assert re.search(r'class="on" aria-pressed="true"[^>]*data-quer="verde"', um), (
        "o ponto aceso mudou antes de a extensão confirmar")
    novo = _aparelhos()
    novo[0]["controles"][1]["valor"] = "azul"
    ponte.estado = _estado(novo, serie=2)
    a07._AGORA.ler("toque", ponte)
    um = _cartoes(a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-controles"])["ap-1"]
    assert "em-curso" not in um, "o estado novo não tirou o «em curso»"
    assert re.search(r'class="on" aria-pressed="true"[^>]*data-quer="azul"', um)
    assert not re.search(r'class="on"[^>]*data-quer="verde"', um)


# -- 3. o que se recusa ---------------------------------------------------------------------


def _com(mexer: Callable[[list[dict[str, Any]]], Any]) -> dict[str, Any]:
    aparelhos = _aparelhos()
    mexer(aparelhos)
    return {"ligado": True, "aparelhos": aparelhos}


@pytest.mark.parametrize(("mexer", "frase"), [
    pytest.param(lambda a: a[1]["controles"].extend(
        {"id": f"c{n}", "tipo": "chave", "valor": False} for n in range(6)),
        "uma lista de até 6", id="sete-controles"),
    pytest.param(lambda a: a[1]["controles"][0].update(tipo="deslizante"),
                 "o tipo de um controle é um de chave, paleta, escolha", id="tipo-desconhecido"),
    pytest.param(
        lambda a: a[0]["controles"][1]["opcoes"][0].update(cor="vermelho"),  # (noqa-acento) chave
                 "a cor de uma paleta é #rrggbb", id="cor-torta"),
    pytest.param(lambda a: a[0]["controles"][1]["opcoes"][3].update(  # (noqa-acento) contrato
        cor=["#000000", "#111111", "#222222", "#333333"]),
        "lista de até 3", id="quatro-cores"),
    pytest.param(lambda a: a[0]["controles"][1].update(valor="roxo"),
                 "o valor da paleta é o id de uma das opções dela", id="valor-fora"),
    pytest.param(lambda a: a[1]["controles"][0].update(valor="sim"),
                 "o valor da chave é verdadeiro ou falso", id="chave-sem-bool"),
    pytest.param(lambda a: a[1].pop("id"), "o aparelho com controles tem id", id="sem-id"),
    pytest.param(lambda a: a[1]["controles"].append({"id": "luz", "tipo": "chave", "valor": True}),
                 "controle repetido", id="repetido"),
])
def test_o_estado_torto_e_recusado_com_a_frase(mexer: Any, frase: str) -> None:
    with pytest.raises(RecusaError) as recusa:
        estado_dos_acessorios("toque", _com(mexer))
    assert frase in str(recusa.value), str(recusa.value)
    assert str(recusa.value).count("acessorios.estado:") == 1


def test_seis_controles_e_tres_cores_ainda_passam() -> None:
    def seis(a: list[dict[str, Any]]) -> None:
        a[1]["controles"].extend({"id": f"c{n}", "tipo": "chave", "valor": False} for n in range(5))

    certo = estado_dos_acessorios("toque", _com(seis))
    assert len(certo["aparelhos"][1]["controles"]) == 6
    assert certo["aparelhos"][0]["controles"][1]["opcoes"][3]["cor"] == [  # (noqa-acento) contrato
        "#bd93f9", "#ffb86c",
                                                                         "#ff5555"]
    assert "controles" not in certo["aparelhos"][2], "o aparelho sem controles ganhou a chave"


def test_o_servico_so_leva_o_controle_que_o_aparelho_publicou(lar: Any) -> None:  # noqa: F811
    _instalada_como(lar, "toque")
    enviadas: list[tuple[Any, ...]] = []

    def acao(mod: str, acao: str, *, alvo: str | None = None, valor: Any = None) -> bool:
        enviadas.append((mod, acao, alvo, valor))
        return True

    porta = SimpleNamespace(acao=acao, agora_de=lambda mod: _estado())
    servico = _servico(SimpleNamespace(lugares=lar, porta=porta))

    def pedir(**params: Any) -> Any:
        return asyncio.run(IpcHandlersMixin._handle_mods_acao(servico, {"mod": "toque", **params}))

    assert pedir(acao="cor", alvo="ap-1", valor="azul") == {"enviada": True}
    assert pedir(acao="luz", alvo="ap-2", valor=True) == {"enviada": True}
    with pytest.raises(ValueError, match="não declara a ação «cor» nos aparelhos"):
        pedir(acao="cor", alvo="ap-2", valor="azul")
    with pytest.raises(ValueError, match="não declara a ação «luz» nos aparelhos"):
        pedir(acao="luz", alvo="ap-3", valor=True)
    with pytest.raises(ValueError, match="uma de: vermelho, verde, azul, brasa"):
        pedir(acao="cor", alvo="ap-1", valor="roxo")
    with pytest.raises(ValueError, match="o valor da chave é verdadeiro ou falso"):
        pedir(acao="luz", alvo="ap-1", valor="1")
    with pytest.raises(ValueError, match="na janela"):
        pedir(acao="cor", valor="azul")
    with pytest.raises(ValueError, match="verdadeiro, falso ou o id de uma opção"):
        pedir(acao="cor", alvo="ap-1", valor=3)
    assert enviadas == [("toque", "cor", "ap-1", "azul"), ("toque", "luz", "ap-2", True)]


def test_sem_aparelhos_controles_no_manifesto_o_controle_nao_passa(lar: Any) -> None:  # noqa: F811
    pasta = lar.codigo / "toque"
    pasta.mkdir(parents=True)
    (pasta / "hefesto-mod.json").write_text(json.dumps(_manifesto()), encoding="utf-8")
    porta = SimpleNamespace(acao=lambda *a, **k: True, agora_de=lambda mod: _estado())
    servico = _servico(SimpleNamespace(lugares=lar, porta=porta))
    with pytest.raises(ValueError, match="não declara a ação «cor» nos aparelhos"):
        asyncio.run(IpcHandlersMixin._handle_mods_acao(
            servico, {"mod": "toque", "acao": "cor", "alvo": "ap-1",  # (noqa-acento) contrato
                      "valor": "azul"}))


@pytest.mark.parametrize(("mexer", "frase"), [
    (lambda d: d.update(permissoes=[]),  # (noqa-acento) chave do manifesto
     "aparelhos_controles pede a permissão publicar:acessorios.estado"),
    (lambda d: d["aparelhos_controles"].pop("grupo"), "aparelhos_controles.grupo"),
    (lambda d: d["aparelhos_controles"].update(cor="#fff"), "aparelhos_controles.cor"),
])
def test_o_manifesto_dos_controles_torto_e_recusado(
        tmp_path: pathlib.Path, mexer: Any, frase: str) -> None:
    bruto = _manifesto(**_pecas())
    mexer(bruto)
    (tmp_path / "hefesto-mod.json").write_text(json.dumps(bruto), encoding="utf-8")
    with pytest.raises(ManifestoRecusadoError) as recusa:
        ler_manifesto(tmp_path)
    assert frase in recusa.value.frase, recusa.value.frase


# -- 5. o cartão inteiro no WebKit ------------------------------------------------------------

DESENHO = pathlib.Path(__file__).resolve().parents[2] / "mockup" / "07-lancadores.html"
#: A janela maximizada no monitor do usuário e o piso da janela.
VISTAS = ((1918, 840), (1212, 809))

#: A sonda abre o desenho num WebKit de verdade, sob a tela de mentira, e roda os passos de cada
#: caso: ``["js", código]`` devolve o que o código devolve, ``["espera", segundos]`` deixa o laço
#: do GTK andar (os ``setInterval`` da página andam junto).
SONDA = r"""
import json, pathlib, sys
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from hefesto_dualsense4unix.interface.janela import PonteDaTela

PAGINA = pathlib.Path(sys.argv[1])
CASOS = json.loads(sys.stdin.read())

def esperar(caixa, segundos):
    fim = GLib.get_monotonic_time() + int(segundos * 1_000_000)
    while "v" not in caixa and GLib.get_monotonic_time() < fim:
        Gtk.main_iteration_do(False)

saida = {}
for chave, (largura, altura, passos) in CASOS.items():
    ponte = PonteDaTela(folha=None)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(largura, altura)
    janela.add(ponte.view)
    janela.show_all()
    ponte.view.load_uri(PAGINA.as_uri())
    esperar({}, 4)
    lidos = []
    for tipo, corpo in passos:
        if tipo == "espera":
            esperar({}, corpo)
            continue
        caixa = {}
        ponte.perguntar(corpo, lambda v, e: caixa.update(v=v, e=repr(e) if e else ""))
        esperar(caixa, 8)
        lidos.append(caixa.get("v") if not caixa.get("e") else {"erro": caixa["e"]})
    saida[chave] = lidos
    janela.destroy()
print(json.dumps(saida))
"""


def rodar_no_webkit(casos: dict[str, tuple[int, int, list[list[Any]]]]) -> dict[str, list[Any]]:
    """Os passos de cada caso no desenho, num WebKit de verdade; sem WebKit, o teste é pulado."""
    import os
    import subprocess
    import sys

    ambiente = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    filho = subprocess.run([sys.executable, "-c", SONDA, str(DESENHO)], input=json.dumps(casos),
                           env=ambiente, capture_output=True, text=True, timeout=300)
    if filho.returncode != 0:
        pytest.skip(f"o WebKit não subiu na tela de mentira: {filho.stderr.strip()[-300:]}")
    return dict(json.loads(filho.stdout.strip().splitlines()[-1]))


#: O cartão na borda do contrato: dezesseis pontos (treze de uma cor e três de três), uma escolha
#: de seis opções compridas e um rótulo de 28 letras (o teto é 30).
_PONTOS = [{"id": f"c{n}", "cor": f"#{40 + n * 12:02x}{200 - n * 9:02x}{90 + n * 10:02x}",
            "rotulo": f"Cor {n + 1}"} for n in range(13)] + [  # (noqa-acento) contrato
    {"id": f"t{n}", "cor": ["#ff5555", "#50fa7b", "#6c8cff"][n:] + ["#ff5555", "#50fa7b"][:n],
     "rotulo": f"Mistura {n + 1}"} for n in range(3)]  # (noqa-acento) contrato
_JEITOS = [{"id": f"j{n}", "rotulo": r} for n, r in enumerate(  # (noqa-acento) contrato
    ("Fixa", "Pisca devagar", "Pisca depressa", "Respira", "Onda de cores", "Segue o jogo"))]
_ROTULO_LONGO = "Como a luz se comporta agora"


def _cartoes_na_borda() -> str:
    from hefesto_dualsense4unix.interface import desenho_da_experimental as exp

    aparelhos = [
        {"id": "ap-1", "nome": "Aparelho 1", "estado": "ligado", "ligado": True, "controles": [
            {"id": "luz", "tipo": "chave", "valor": True},
            {"id": "cor", "tipo": "paleta", "valor": "c2",
             "opcoes": _PONTOS},  # (noqa-acento) contrato
            {"id": "jeito", "tipo": "escolha", "valor": "j0",  # (noqa-acento) contrato
             "rotulo": _ROTULO_LONGO,
             "opcoes": _JEITOS}]},  # (noqa-acento) contrato
        {"id": "ap-2", "nome": "Aparelho 2", "estado": "ligado", "ligado": True, "controles": [
            {"id": "luz", "tipo": "chave", "valor": False}]}]
    return str(exp.controles_dos_aparelhos_html("toque", _estado(aparelhos)))


_ABRIR = """(function(h){
  const cc = document.getElementById('mod-controles');
  location.hash = '#' + cc.closest('.tela-nova').id;
  cc.innerHTML = h;
  const tela = cc.closest('.mj-tela'), aba = tela.previousElementSibling.previousElementSibling;
  aba.checked = true;
  return 'ok';
})(%s)"""
_MEDIR = """(function(){
  const r = e => { const x = e.getBoundingClientRect();
    return [x.left, x.top, x.right, x.bottom]; };
  const cc = document.getElementById('mod-controles'), tela = cc.closest('.mj-tela');
  return JSON.stringify({
    grupos: [...cc.querySelectorAll('.mj-cores')].map(g => ({caixa: r(g),
      botoes: [...g.querySelectorAll('button')].map(b => [b.textContent.trim(), r(b)])})),
    linhas: [...cc.querySelectorAll('.mj-cc-linha')].map(l => {
      const rot = l.querySelector('.mj-cc-rot');
      return {rotulo: rot.textContent, caixa: r(rot), largo: [rot.scrollWidth, rot.clientWidth],
              letra: parseFloat(getComputedStyle(rot).fontSize),
              controle: r(l.querySelector('.mj-cc-ctrl')), cartao: r(l.closest('.mj-cc'))};
    }),
    tela: [tela.scrollHeight, tela.clientHeight], visivel: getComputedStyle(tela).visibility});
})()"""


@pytest.fixture(scope="module")
def na_borda() -> dict[str, dict[str, Any]]:
    html = _cartoes_na_borda()
    casos: dict[str, tuple[int, int, list[list[Any]]]] = {
        f"{w}x{h}": (w, h, [["js", _ABRIR % json.dumps(html)], ["espera", 0.5], ["js", _MEDIR]])
        for w, h in VISTAS}
    return {k: json.loads(v[1]) for k, v in rodar_no_webkit(casos).items()}


@pytest.mark.parametrize("vista", [f"{w}x{h}" for w, h in VISTAS])
def test_toda_opcao_do_contrato_fica_inteira_e_o_rotulo_nao_invade(
        na_borda: dict[str, dict[str, Any]], vista: str) -> None:
    # D-2410-A-EXTENSAO-DECLARA-ACOES-E-O-CLIQUE-VAI-SO-A-ELA
    """Na borda do contrato, cada ponto e cada opção ficam inteiros dentro do grupo (nenhum some
    atrás da borda), o rótulo longo cabe em duas linhas sem invadir o controle, e a aba não rola."""
    m = na_borda[vista]
    assert m["visivel"] == "visible" and m["grupos"], f"a aba dos controles não abriu: {m}"
    botoes = sum(len(g["botoes"]) for g in m["grupos"])
    assert botoes == len(_PONTOS) + len(_JEITOS), f"faltou opção no cartão: {m}"
    for g in m["grupos"]:
        e, t, d, b = g["caixa"]
        for nome, (be, bt, bd, bb) in g["botoes"]:
            assert be >= e - 0.5 and bd <= d + 0.5 and bt >= t - 0.5 and bb <= b + 0.5, (
                f"a opção «{nome}» ficou cortada pelo grupo {g['caixa']}: {(be, bt, bd, bb)}")
    for linha in m["linhas"]:
        rot, ctrl, cartao = linha["caixa"], linha["controle"], linha["cartao"]
        assert linha["largo"][0] <= linha["largo"][1] + 1, f"o rótulo transborda: {linha}"
        assert rot[2] <= ctrl[0] + 0.5, f"o rótulo invade o controle: {linha}"
        assert rot[3] - rot[1] <= 2 * 1.5 * linha["letra"], (
            f"o rótulo virou uma coluna de pedaços de palavra (mais de duas linhas): {linha}")
        assert ctrl[2] <= cartao[2] + 0.5, f"o controle sai do cartão: {linha}"
    assert m["tela"][0] <= m["tela"][1] + 1, f"a aba dos controles rola: {m['tela']}"
