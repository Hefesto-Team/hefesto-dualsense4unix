"""A coluna das conexões da extensão se escolhe no clique.

A-LOVENSE-PELO-BLUETOOTH-E-A-CONEXAO-QUE-SE-ESCOLHE-01 (01/11/2026). O manifesto ganha
o mapa das conexões (o id de cada uma para ``{liga, escolha?}``): a coluna passa a se chamar
«Conexão», cada linha declarada é a chave da própria conexão (o clique grava a opção ``liga``
ao contrário, e a ligada fica marcada), e a linha com ``escolha`` oferece os nomes que a
extensão publica (os adaptadores do computador), um botão cada, que gravam a opção ``escolha``.
A porta é genérica: nada aqui é de uma extensão só.

MORDIDAS (01/11/2026, executadas sobre a cura e devolvidas):

- a linha sem o ``data-gesto`` reprova a coluna e o clique;
- o gesto que ignora o clique do botão da escolha reprova o adaptador escolhido;
- o ``_validada`` sem o nome da conexão recusa o adaptador fora das ``escolhas`` declaradas.
"""

from __future__ import annotations

import copy
import re
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.interface.desenho_da_experimental import janela_pintada
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import ctx, lar  # noqa: F401
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    _manifesto,
    _Ponte,
    janela,
)

AUTO = "Automático"
CX = "conexoes"  # (noqa-acento)
OPCOES: list[dict[str, Any]] = [
    {"id": "ligada", "rotulo": "Ligada", "tipo": "ligado", "padrao": True},  # (noqa-acento)
    {"id": "usar_o_celular", "rotulo": "Celular", "tipo": "ligado",
     "padrao": False},  # (noqa-acento)
    {"id": "usar_o_radio", "rotulo": "Bluetooth", "tipo": "ligado",
     "padrao": True},  # (noqa-acento)
    {"id": "radio", "rotulo": "Adaptador", "tipo": "escolha", "escolhas": [AUTO],
     "padrao": AUTO, "grupo": "Ligação"},  # (noqa-acento)
    {"id": "volume", "rotulo": "Volume", "tipo": "deslizante",
     "minimo": 0, "maximo": 10, "passo": 1, "padrao": 5},  # (noqa-acento)
]
LIGAS: dict[str, Any] = {"celular": {"liga": "usar_o_celular"},
                         "bluetooth": {"liga": "usar_o_radio", "escolha": "radio"}}
ESTADO_VIVO: dict[str, Any] = {"ligado": True, "serie": 1, "conexoes": [  # (noqa-acento)
    {"id": "celular", "tipo": "Celular", "transporte": "rede", "estado": "desligado",
     "motivo": "Pelo app do celular"},
    {"id": "bluetooth", "tipo": "Bluetooth", "transporte": "bluetooth", "estado": "ligado",
     "escolhas": [AUTO, "Pendrive preto", "Pendrive azul"], "escolha": AUTO},
    {"id": "jogo", "tipo": "Game Mode", "transporte": "rede", "estado": "desligado"},
]}


def _pecas(**troca: Any) -> dict[str, Any]:
    return {"opcoes": copy.deepcopy(OPCOES), "agora": [CX], "chave": "ligada",  # (noqa-acento)
            CX: copy.deepcopy(LIGAS), **troca}


def _declarado(**troca: Any) -> dict[str, Any]:
    return _manifesto(**_pecas(**troca))


def test_o_manifesto_aceita_o_conexoes() -> None:
    m = Manifesto.model_validate(_declarado())
    assert {c: (x.liga, x.escolha) for c, x in m.conexoes.items()} == {  # (noqa-acento)
        "celular": ("usar_o_celular", None), "bluetooth": ("usar_o_radio", "radio")}


@pytest.mark.parametrize(("troca", "frase"), [
    ({"agora": ["nivel"]}, f"{CX} pede o pedaço {CX} em agora"),
    ({CX: {"Celular!": {"liga": "usar_o_celular"}}}, "fora da forma de chave"),
    ({CX: {"celular": {"liga": "sumiu"}}}, "liga 'sumiu', que não é uma opção ligado"),
    ({CX: {"celular": {"liga": "volume"}}}, "liga 'volume', que não é uma opção ligado"),
    ({CX: {"celular": {"liga": "ligada"}}}, "liga 'ligada', que não é uma opção ligado"),
    ({CX: {"bluetooth": {"liga": "usar_o_radio", "escolha": "volume"}}},
     "escolhe 'volume', que não é uma opção escolha"),
], ids=["sem-o-pedaco", "id-fora-da-forma", "liga-que-nao-existe", "liga-de-outro-tipo",
        "liga-a-chave", "escolha-de-outro-tipo"])
def test_o_manifesto_recusa(troca: dict[str, Any], frase: str) -> None:
    with pytest.raises(ValidationError, match=re.escape(frase)):
        Manifesto.model_validate(_declarado(**troca))


def test_o_estado_leva_as_escolhas_da_conexao_e_recusa_a_escolha_de_fora() -> None:
    from hefesto_dualsense4unix.mods import porta

    linha = porta._conexao_do_estado(ESTADO_VIVO["conexoes"][1])  # (noqa-acento)
    assert linha["escolhas"] == [AUTO, "Pendrive preto", "Pendrive azul"]
    assert linha["escolha"] == AUTO
    assert "escolhas" not in porta._conexao_do_estado(ESTADO_VIVO["conexoes"][0])  # (noqa-acento)
    fora = {**ESTADO_VIVO["conexoes"][1], "escolha": "Outro"}  # (noqa-acento)
    with pytest.raises(porta.RecusaError, match="uma das escolhas publicadas"):
        porta._conexao_do_estado(fora)


def _linhas(html: str) -> dict[str, str]:
    """As linhas clicáveis da coluna: ``data-v`` → a classe."""
    return {v: c for c, v in re.findall(
        r'<div class="(cx-linha[^"]*)"[^>]*data-gesto="guardar-opcao-da-modificacao" '
        r'data-v="toque:([^"]+)"', html)}


def _escolhas(html: str) -> dict[str, bool]:
    return {v: "marcada" in c for c, v in re.findall(
        r'<button class="(cx-escolha[^"]*)" value="([^"]+)"', html)}


def _clicar(a07: Any, ctx: Any, ponte: _Ponte, opcao: str, **mais: Any) -> str:  # noqa: F811
    carga = a07.guardar_opcao_da_modificacao(
        ctx, {"v": f"toque:{opcao}", "evento": "click", "tipo": "div", **mais}, ponte)
    return janela_pintada(carga["blocos"]) if carga else ""


def test_a_coluna_se_chama_conexao_e_cada_linha_declarada_tem_o_gesto(
        janela: Any, ctx: Any) -> None:  # noqa: F811
    _a07, instalar, abrir = janela
    instalar(**_pecas())
    html = janela_pintada(abrir(_Ponte(ESTADO_VIVO))["blocos"])
    assert '<span class="pc-sub">Conexão</span>' in html, "a coluna não se chama Conexão"
    assert _linhas(html) == {"usar_o_celular": "cx-linha cx-liga",
                             "usar_o_radio": "cx-linha cx-liga marcada"}, (
        "cada linha declarada leva o gesto da própria opção, e só a ligada fica marcada")
    assert "Game Mode" in html and 'data-v="toque:jogo"' not in html, (
        "a linha que o manifesto não declara segue só mostrando")
    assert _escolhas(html) == {AUTO: True, "Pendrive preto": False, "Pendrive azul": False}


def test_o_clique_na_linha_grava_a_opcao_declarada(janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(ESTADO_VIVO)
    abrir(ponte)
    depois = _clicar(a07, ctx, ponte, "usar_o_celular")
    assert _linhas(depois)["usar_o_celular"].endswith("marcada"), "o clique não marcou a linha"
    _clicar(a07, ctx, ponte, "usar_o_radio")
    guardados: Any = opcoes.ler(manifesto_instalado("toque", lugares=lar), lar)
    assert guardados["usar_o_celular"] is True and guardados["usar_o_radio"] is False
    a07._MEXIDA.limpar()
    reaberta = janela_pintada(abrir(ponte)["blocos"])
    assert _linhas(reaberta) == {"usar_o_celular": "cx-linha cx-liga marcada",
                                 "usar_o_radio": "cx-linha cx-liga"}
    assert not _escolhas(reaberta), "a conexão desligada não oferece os adaptadores"


def test_o_adaptador_se_escolhe_pelo_nome_no_clique(janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(ESTADO_VIVO)
    abrir(ponte)
    assert _clicar(a07, ctx, ponte, "radio", tipo="select") == "", (
        "o clique na caixa da escolha não grava: só o change da caixa")
    html = _clicar(a07, ctx, ponte, "radio", tipo="button", valor="Pendrive azul")
    assert _escolhas(html) == {AUTO: False, "Pendrive preto": False, "Pendrive azul": True}
    m = manifesto_instalado("toque", lugares=lar)
    assert opcoes.ler(m, lar)["radio"] == "Pendrive azul", "o nome escolhido não ficou gravado"
    caixa = re.search(r'<select[^>]*data-v="toque:radio".*?</select>', html, re.S)
    assert caixa, "a aba Ligação perdeu a caixa do adaptador"
    assert re.findall(r"<option[^>]*>([^<]+)</option>", caixa.group(0)) == [
        AUTO, "Pendrive preto", "Pendrive azul"], "a caixa não oferece os nomes da coluna"


def test_o_nome_de_conexao_vale_so_na_escolha_declarada() -> None:
    from hefesto_dualsense4unix.mods import opcoes

    m = Manifesto.model_validate(_declarado())
    radio = next(o for o in m.opcoes if o.id == "radio")
    assert opcoes.escolha_de_conexao(m, radio)
    assert opcoes.aceitas_de(m, radio, {}, "Pendrive azul") == ("Pendrive azul",)
    assert opcoes.aceitas_de(m, radio, {}, "x" * 41) == ()
    assert opcoes.aceitas_de(m, radio, {}, "linha\nquebrada") == ()
    sem = Manifesto.model_validate(_declarado(conexoes={"celular": {"liga": "usar_o_celular"}}))
    assert not opcoes.escolha_de_conexao(sem, next(o for o in sem.opcoes if o.id == "radio"))
