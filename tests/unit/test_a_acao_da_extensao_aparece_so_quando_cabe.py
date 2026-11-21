"""A ação da extensão aparece só quando cabe, com o texto ao lado, e a conexão diz que espera.

A-ACAO-DA-EXTENSAO-APARECE-SO-QUANDO-CABE-E-A-CONEXAO-DIZ-QUE-ESPERA-01 (20/11/2026). A ação
``pedida`` do manifesto só é desenhada quando o estado que a extensão publica a pede,
com o texto que o estado dá ao lado do botão (escapado, até 120 letras), na abertura da janela e no
tique; a conexão ``esperando`` passa pela porta e se pinta laranja, «Esperando o aceite». O
manifesto sem os campos novos desenha igual.

MORDIDAS (20/11/2026, executadas sobre a cura e devolvidas, md5 conferido):

- ``acoes_que_aparecem`` devolvendo todas reprova
  ``test_a_acao_pedida_so_aparece_quando_o_estado_a_nomeia``, e o mesmo teste reprova com o
  ``estado`` tirado da barra repintada no tique (``_com_os_aparelhos``), com a ação ``pedida``
  tirada do ``_estado_da_janela`` (a abertura sem o estado) e com o ``pedida`` que o
  ``_acao_da_janela`` não passa;
- o ``_e`` tirado do ``texto_ao_lado_html`` reprova
  ``test_o_texto_ao_lado_e_texto_cortado_e_nunca_marcacao``;
- o ``esperando`` tirado do ``ESTADOS_DA_CONEXAO`` da porta reprova
  ``test_a_porta_aceita_a_conexao_que_espera_e_corta_o_texto_da_acao``;
- o ``esperando`` tirado do ``PALAVRA_DO_ESTADO`` reprova
  ``test_a_conexao_que_espera_diz_a_palavra_laranja_e_o_motivo_na_dica``;
- a recusa da ``pedida`` com ``cartao`` tirada do manifesto reprova
  ``test_a_acao_pedida_torta_recusa_o_manifesto``.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.mods import porta
from hefesto_dualsense4unix.mods.manifesto import ManifestoRecusadoError, ler_manifesto
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    _manifesto,
    _Ponte,
    janela,
)

PAREAR = {"id": "parear", "rotulo": "Parear", "grupo": "Aparelhos", "icone": "procurar"}
DICA = "Esta página passa a comandar os brinquedos"
ACEITAR = {"id": "aceitar", "rotulo": "Aceitar o site", "grupo": "Aparelhos", "pedida": True,
           "dica": DICA}
ESPERA = {"id": "jogo", "tipo": "Jogo", "transporte": "local", "estado": "esperando",
          "motivo": "Uma página pediu para comandar: null"}
BOTAO = 'data-v="toque:aceitar"'
PEDIDAS = exp.CHAVE_DAS_ACOES
TESTAR_PEDIDA = {"id": "testar", "rotulo": "Testar", "pedida": True}


def test_a_acao_pedida_so_aparece_quando_o_estado_a_nomeia(janela: Any, ctx: Any) -> None:  # noqa: F811
    """D-2011-A-ACAO-DA-EXTENSAO-APARECE-QUANDO-CABE-E-A-CONEXAO-ESPERA"""
    a07, instalar, abrir = janela
    instalar(acoes=[PAREAR, ACEITAR])
    ponte = _Ponte({"ligado": True, "serie": 1})
    html = abrir(ponte)["blocos"]["#mod-janela"]
    assert 'data-v="toque:parear"' in html and BOTAO not in html, "sem pedido, só o Parear"

    def tique(serie: int, **estado: Any) -> str:
        ponte.estado = {"ligado": True, "serie": serie, **estado}
        a07._AGORA.ler("toque", ponte)
        return str(a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-acoes-0"])

    barra = tique(2, acoes={"aceitar": "null"})
    assert BOTAO in barra, "o estado pediu e o tique não desenhou a ação"
    assert f'data-dica="{DICA}"' in barra
    assert barra.index("toque:parear") < barra.index(BOTAO) < barra.index(">null</span>")
    assert BOTAO not in tique(3, acoes={}), "o pedido saiu e o botão ficou"
    tique(4, acoes={"aceitar": "https://jogo.exemplo"})
    aberta = abrir(ponte)["blocos"]["#mod-janela"]
    assert BOTAO in aberta and ">https://jogo.exemplo</span>" in aberta, (
        "a janela aberta com o pedido não desenhou a ação com o texto")


def test_o_texto_ao_lado_e_texto_cortado_e_nunca_marcacao() -> None:
    acoes = [exp.AcaoDaJanela("aceitar", "Aceitar o site", pedida=True)]

    def barra(texto: Any) -> str:
        return exp.barra_de_acoes_html("toque", acoes, estado={PEDIDAS: {"aceitar": texto}})

    perigo = barra('<img src=x onerror="x()">')
    assert "<img" not in perigo and '>&lt;img src=x onerror="x()"&gt;</span>' in perigo
    assert f">{'a' * exp.TEXTO_AO_LADO}</span>" in barra("a" * 300)
    assert exp.barra_de_acoes_html("toque", acoes, estado={PEDIDAS: ["torto"]}).count(
        "<button") == 1, "as pedidas tortas caem no de antes: a ação desenhada"


def test_o_manifesto_sem_os_campos_novos_desenha_igual() -> None:
    parear = exp.AcaoDaJanela("parear", "Parear", "Aparelhos", "procurar")
    esperado = (f'<button class="btn mj-acao forte" data-gesto="acao-da-modificacao" '
                f'data-v="toque:parear"><svg {exp._TRACO_DA_ACAO}>'
                f'{exp.ICONE_DA_ACAO["procurar"]}</svg><span>Parear</span></button>')
    assert exp.barra_de_acoes_html("toque", [parear]) == esperado
    assert exp.barra_de_acoes_html("toque", [parear], estado={PEDIDAS: {}}) == esperado


def test_a_conexao_que_espera_diz_a_palavra_laranja_e_o_motivo_na_dica() -> None:
    linha = exp._conexao_html(ESPERA)
    assert '<span class="est est-laranja"><i></i>Esperando o aceite</span>' in linha
    assert f'data-dica="{ESPERA["motivo"]}"' in linha
    assert '<span class="est est-mudo"><i></i>—</span>' in exp._conexao_html(
        {**ESPERA, "estado": "outro"}), "o estado desconhecido cai no de antes"


def test_a_porta_aceita_a_conexao_que_espera_e_corta_o_texto_da_acao() -> None:
    longo = "https://" + "x" * 200
    estado = porta.estado_dos_acessorios(
        "toque", {"conexoes": [ESPERA], PEDIDAS: {"aceitar": longo, "outra": ""}})  # (noqa-acento)
    assert estado["conexoes"][0]["estado"] == "esperando"  # (noqa-acento)
    assert estado[PEDIDAS] == {"aceitar": longo[:porta.TEXTO_DA_ACAO], "outra": ""}
    assert PEDIDAS not in porta.estado_dos_acessorios("toque", {})
    with pytest.raises(porta.RecusaError, match="as ações do estado"):
        porta.estado_dos_acessorios("toque", {PEDIDAS: {"aceitar": 1}})
    with pytest.raises(porta.RecusaError, match="o estado de um aparelho"):
        porta.estado_dos_acessorios(
            "toque", {"aparelhos": [{"nome": "A", "estado": "esperando"}]})


@pytest.mark.parametrize(("mexer", "frase"), [
    (lambda d: d["acoes"].append({**ACEITAR, "cartao": "Toques"}),  # (noqa-acento)
     "é pedida e mora na barra da aba"),
    (lambda d: d.update(aparelhos_acoes={"acoes": [TESTAR_PEDIDA]},  # (noqa-acento)
                        agora=["aparelhos"]),
     "não declara pedida"),
    (lambda d: d["acoes"].append({**ACEITAR, "dica": "x" * 121}),  # (noqa-acento)
     "acoes.1.dica"),
])
def test_a_acao_pedida_torta_recusa_o_manifesto(
        tmp_path: pathlib.Path, mexer: Any, frase: str) -> None:
    bruto = _manifesto(acoes=[PAREAR],
                       opcoes=[{"id": "um", "rotulo": "Um", "tipo": "ligado",
                                "cartao": "Toques"}])
    mexer(bruto)
    (tmp_path / "hefesto-mod.json").write_text(json.dumps(bruto), encoding="utf-8")
    with pytest.raises(ManifestoRecusadoError) as recusa:
        ler_manifesto(tmp_path)
    assert frase in recusa.value.frase, recusa.value.frase
