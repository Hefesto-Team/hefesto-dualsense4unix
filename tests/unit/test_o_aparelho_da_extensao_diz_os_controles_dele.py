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
    _servico,
    janela,
)

ABA = "Luz"
CORES: list[dict[str, Any]] = [{"id": "vermelho", "cor": "#ff5555", "rotulo": "Vermelho"},  # noqa-acento: contrato
         {"id": "verde", "cor": "#50fa7b", "rotulo": "Verde"},  # noqa-acento: contrato
         {"id": "azul", "cor": "#6c8cff", "rotulo": "Azul"},  # noqa-acento: contrato
         {"id": "brasa", "cor": ["#bd93f9", "#ffb86c", "#ff5555"], "rotulo": "Brasa"}]  # noqa-acento: contrato
ESCOLHA = [{"id": "fixa", "rotulo": "Fixa"}, {"id": "pisca", "rotulo": "Pisca"}]  # noqa-acento: contrato


def _aparelhos() -> list[dict[str, Any]]:
    """Três aparelhos: chave e paleta (e uma escolha), só a chave, e nenhum controle."""
    return [
        {"id": "ap-1", "nome": "Aparelho 1", "estado": "ligado", "ligado": True, "controles": [
            {"id": "luz", "tipo": "chave", "valor": True, "dica": "Acesa"},
            {"id": "cor", "tipo": "paleta", "valor": "verde", "opcoes": copy.deepcopy(CORES)},  # noqa-acento: contrato
            {"id": "jeito", "tipo": "escolha", "valor": "fixa", "rotulo": "Jeito",  # noqa-acento: contrato
             "opcoes": copy.deepcopy(ESCOLHA)}]},  # noqa-acento: contrato
        {"id": "ap-2", "nome": "Aparelho 2", "estado": "ligado", "ligado": True, "controles": [
            {"id": "luz", "tipo": "chave", "valor": False}]},
        {"id": "ap-3", "nome": "Aparelho 3", "estado": "ligado", "ligado": True},
    ]


def _estado(aparelhos: list[dict[str, Any]] | None = None, serie: int = 1) -> dict[str, Any]:
    """O estado como a porta o guarda: validado, com a ``serie`` que a janela espera."""
    bruto = {"ligado": True, "aparelhos": _aparelhos() if aparelhos is None else aparelhos}
    return {**estado_dos_acessorios("toque", bruto), "serie": serie}


def _pecas() -> dict[str, Any]:
    return {"aparelhos_controles": {"grupo": ABA}}  # noqa-acento: contrato


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
    assert feitas == [{"mod": "toque", "acao": controle, "alvo": alvo, "valor": valor}], feitas  # noqa-acento: contrato


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
            assert chegou["params"]["dados"] == {"mod": "acessorios", "acao": "cor",  # noqa-acento: contrato
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
    pytest.param(lambda a: a[0]["controles"][1]["opcoes"][0].update(cor="vermelho"),  # noqa-acento: contrato
                 "a cor de uma paleta é #rrggbb", id="cor-torta"),
    pytest.param(lambda a: a[0]["controles"][1]["opcoes"][3].update(  # noqa-acento: contrato
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
    assert certo["aparelhos"][0]["controles"][1]["opcoes"][3]["cor"] == ["#bd93f9", "#ffb86c",  # noqa-acento: contrato
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
    assert enviadas == [("toque", "cor", "ap-1", "azul"), ("toque", "luz", "ap-2", True)]


def test_sem_aparelhos_controles_no_manifesto_o_controle_nao_passa(lar: Any) -> None:  # noqa: F811
    pasta = lar.codigo / "toque"
    pasta.mkdir(parents=True)
    (pasta / "hefesto-mod.json").write_text(json.dumps(_manifesto()), encoding="utf-8")
    porta = SimpleNamespace(acao=lambda *a, **k: True, agora_de=lambda mod: _estado())
    servico = _servico(SimpleNamespace(lugares=lar, porta=porta))
    with pytest.raises(ValueError, match="não declara a ação «cor» nos aparelhos"):
        asyncio.run(IpcHandlersMixin._handle_mods_acao(
            servico, {"mod": "toque", "acao": "cor", "alvo": "ap-1", "valor": "azul"}))  # noqa-acento: contrato


@pytest.mark.parametrize(("mexer", "frase"), [
    (lambda d: d.update(permissoes=[]),  # noqa-acento: chave do manifesto
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
