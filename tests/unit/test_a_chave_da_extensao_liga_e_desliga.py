"""A chave Ligado/Desligado do topo da janela da extensão, no lugar do «Parar tudo».

A-CHAVE-LIGADO-DESLIGADO-NO-LUGAR-DO-PARAR-TUDO-01 (28/10/2026). O usuário disse: «Deveríamos
deixar um slider de ligado e desligado ao invés do parar tudo. O parar tudo é meio
contraintuitivo.» O manifesto declara ``"chave": "<opção ligado>"``; a janela põe a chave no
topo, sem texto, grava na hora e, desligada, apaga as ações e pede o gesto ``para``. O
``parar_tudo`` de antes segue valendo.

E os controles do aparelho no cartão dele quando a aba deles é a dos aparelhos (O-CONTROLE-DO-
APARELHO-MORA-NO-CARTAO-DELE-01): uma linha por aparelho, sem rótulo, e nenhum cartão à parte.

MORDIDAS (28/10/2026, executadas sobre a cura e devolvidas):

- o ``opcoes.guardar`` da chave tirado do ``_handle_mods_parar_tudo`` reprova
  ``test_o_ipc_do_parar_grava_a_chave_desligada_e_publica_o_para``;
- o ``desligada`` tirado do ``acao_html`` reprova
  ``test_a_chave_no_topo_grava_na_hora_e_desligada_apaga_as_acoes``;
- o ``not (gestao and gestao.controles)`` tirado de ``_abas_com_as_pecas`` reprova
  ``test_os_controles_do_aparelho_moram_no_cartao_quando_dividem_a_aba``.
"""

from __future__ import annotations

import asyncio
import json
import re
from types import SimpleNamespace
from typing import Any

import pytest
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.interface.desenho_da_experimental import janela_pintada
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import _servico
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    ACOES_DOS_APARELHOS,
    VIVO,
    _Ponte,
    janela,
)

ESTADO = "publicar:acessorios.estado"
LIGADA = {"id": "ligada", "rotulo": "Ligada", "tipo": "ligado", "padrao": True}  # (noqa-acento)
FORCA = {"id": "forca", "rotulo": "Força", "tipo": "deslizante", "grupo": "Toques",
         "padrao": 50, "minimo": 0, "maximo": 100, "passo": 5}  # (noqa-acento)
PAREAR = {"id": "parear", "rotulo": "Parear", "grupo": "Aparelhos", "icone": "procurar"}
LUZ = [{"id": "acesa", "tipo": "chave", "rotulo": "Luz", "icone": "lampada", "valor": True},
       {"id": "cor", "tipo": "paleta", "valor": "a",
        "opcoes": [{"id": "a", "rotulo": "A", "cor": "#ff0000"},  # (noqa-acento)
                   {"id": "b", "rotulo": "B", "cor": ["#00ff00", "#0000ff"]}]}]


BOTAO_DA_ACAO = r'<button[^>]*data-gesto="acao-da-modificacao"'
GERIDOS = {"grupo": "Aparelhos", "acoes": ACOES_DOS_APARELHOS}  # (noqa-acento)


def _base(**extra: Any) -> dict[str, Any]:
    return {"id": "toque", "nome": "Toque", "versao": "0.1", "api": ">=1,<3",  # (noqa-acento)
            "licenca": "MIT", "tipos": ["tema"], "tema": {},
            "permissoes": [ESTADO], **extra}  # (noqa-acento)


def test_o_manifesto_confere_a_chave() -> None:
    manifesto = Manifesto.model_validate(_base(opcoes=[LIGADA], chave="ligada"))  # (noqa-acento)
    assert manifesto.chave == "ligada"
    casos = {
        "não existe": _base(opcoes=[LIGADA], chave="outra"),  # (noqa-acento)
        "tipo ligado": _base(opcoes=[{**LIGADA, "tipo": "escolha", "escolhas": ["a"],
                                      "padrao": "a"}], chave="ligada"),  # (noqa-acento)
        "sem aparece_com": _base(opcoes=[LIGADA, {**LIGADA, "id": "x"},
                                         {**LIGADA, "id": "y", "aparece_com": {"x": True}}],
                                 chave="y"),
        "permissão": {**_base(opcoes=[LIGADA], chave="ligada"), "permissoes": []},  # (noqa-acento)
    }
    for trecho, bruto in casos.items():
        with pytest.raises(ValueError, match=trecho):
            Manifesto.model_validate(bruto)


def _instalada_com_a_chave(lugares: Any) -> None:
    pasta = lugares.codigo / "acessorios"
    pasta.mkdir(parents=True)
    manifesto = {**_base(opcoes=[LIGADA], chave="ligada"), "id": "acessorios",  # (noqa-acento)
                 "nome": "Acessórios"}
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")


def test_o_ipc_do_parar_grava_a_chave_desligada_e_publica_o_para(lar: Any) -> None:  # noqa: F811
    """Prova da D-2810-A-CHAVE-DA-EXTENSAO-NO-LUGAR-DO-PARAR-TUDO."""
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    _instalada_com_a_chave(lar)
    publicados: list[str] = []
    sup = SimpleNamespace(lugares=lar,
                          porta=SimpleNamespace(parar_tudo=lambda m: publicados.append(m) or True))
    corpo = asyncio.run(IpcHandlersMixin._handle_mods_parar_tudo(_servico(sup),
                                                                 {"mod": "acessorios"}))
    assert corpo == {"parado": True} and publicados == ["acessorios"]
    manifesto = manifesto_instalado("acessorios", lugares=lar)
    assert manifesto is not None and opcoes.ler(manifesto, lar)["ligada"] is False


def _topo(html: str) -> str:
    achado = re.search(r'<span class="mj-chave ja-chave[^"]*"[^>]*>', html)
    assert achado, "a chave do topo"
    return achado.group(0)


def test_a_chave_no_topo_grava_na_hora_e_desligada_apaga_as_acoes(
        janela: Any, ctx: Any) -> None:  # noqa: F811
    """Prova da D-2810-A-CHAVE-DA-EXTENSAO-NO-LUGAR-DO-PARAR-TUDO."""
    a07, instalar, abrir = janela
    instalar(opcoes=[LIGADA, FORCA], chave="ligada", acoes=[PAREAR],
             aparelhos_acoes=GERIDOS)
    ponte = _Ponte(VIVO)
    html = janela_pintada(abrir(ponte)["blocos"])
    topo = _topo(html)
    assert ' on"' in topo and 'aria-checked="true"' in topo and "Parar tudo" not in html
    assert 'data-v="toque:ligada"' not in html, "a opção da chave não vira linha"
    assert re.search(r'<button class="btn mj-acao[^"]*" data-gesto="acao-da-modificacao"', html)

    carga = a07.chave_da_modificacao(ctx, {"v": "toque"}, ponte)
    from hefesto_dualsense4unix.mods import opcoes

    assert opcoes.ler(a07._a_instalada("toque").manifesto, a07._lugares())["ligada"] is False
    assert [m for m, _ in ponte.chamadas if m == "mods.parar_tudo"] == ["mods.parar_tudo"]
    assert "Desligada" in carga["recado"]
    html = janela_pintada(abrir(ponte)["blocos"])
    assert 'aria-checked="false"' in _topo(html)
    assert not re.search(BOTAO_DA_ACAO, html), "nenhum botão de ação clicável desligada"
    assert 'data-v="toque:ligar:ap-1"' in html, "a chave de cada aparelho segue escolhendo"
    assert html.count("mj-acao apagado") >= 2, "o Parear e o Testar seguem à vista, apagados"

    ponte.chamadas.clear()
    a07.chave_da_modificacao(ctx, {"v": "toque"}, ponte)
    assert opcoes.ler(a07._a_instalada("toque").manifesto, a07._lugares())["ligada"] is True
    assert ponte.chamadas == [], "ligar só grava"
    assert re.search(BOTAO_DA_ACAO, janela_pintada(abrir(ponte)["blocos"]))


def _cartoes(html: str) -> dict[str, str]:
    partes = re.split(r'(?=<div class="mj-ap[ "][^>]*data-alvo=")', html)
    return {re.search(r'data-alvo="([^"]+)"', p).group(1): p  # type: ignore[union-attr]
            for p in partes if 'data-alvo="' in p[:200]}


@pytest.mark.parametrize("aba", ["Aparelhos", "Luz"])
def test_os_controles_do_aparelho_moram_no_cartao_quando_dividem_a_aba(
        janela: Any, ctx: Any, aba: str) -> None:  # noqa: F811
    """Prova da D-2810-O-CONTROLE-DO-APARELHO-MORA-NO-CARTAO-DELE."""
    a07, instalar, abrir = janela
    instalar(aparelhos_acoes=GERIDOS,
             aparelhos_controles={"grupo": aba})
    aparelhos = [dict(VIVO["aparelhos"][0], controles=LUZ), VIVO["aparelhos"][1]]
    ponte = _Ponte({**VIVO, "aparelhos": aparelhos})
    blocos = abrir(ponte)["blocos"]
    html = janela_pintada(blocos)
    tique = a07._com_os_aparelhos({"blocos": {}})["blocos"]
    juntos = aba == "Aparelhos"
    assert (">Luz</label>" in html) is not juntos
    assert ('id="mod-controles"' in html) is not juntos
    assert ("#mod-controles" in tique) is not juntos
    for pintado in (html, tique["#mod-aparelhos"]):
        cartao = _cartoes(pintado)
        assert ('class="mj-ap-cc"' in cartao["ap-1"]) is juntos, cartao["ap-1"]
        assert 'class="mj-ap-cc"' not in cartao["ap-2"], "sem controles, sem a linha"
        if juntos:
            linha = cartao["ap-1"].split('class="mj-ap-cc"')[1].split('class="mj-ap-pe"')[0]
            assert 'data-v="toque:acesa:ap-1"' in linha and 'data-v="toque:cor:ap-1"' in linha
            assert "mj-cc-rot" not in linha and ">Cor<" not in linha, "mostra e não diz"
