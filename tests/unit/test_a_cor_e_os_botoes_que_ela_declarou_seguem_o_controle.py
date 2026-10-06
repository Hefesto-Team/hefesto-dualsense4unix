"""AS-ISENCOES-QUE-ESPERAM-A-PALAVRA-DELA-01: a cor e os botões declarados seguem o controle.

As respostas dela de 06/10/2026: os glifos das outras abas seguem o `controles.modo` e o
`controles.botoes`, e a `controles.cor` aparece em tudo, como a do DualSense. Os três campos
existiam no `maquina.json` e nenhuma tela os lia: só a seção da janela GTK, que saiu.

O fio é UM, na mesa que as dez abas leem (`mesa_viva.mesa_do_estado`):

* a cor que ela declarou entra quando o aparelho não deu a dele (a lida vence sempre);
* a família dos botões (`xbox`, `nintendo` ou vazia) sai no item da mesa e chega ao desenho da
  02 pelo alvo `atributo`, que escreve o `data-botoes` na grade dos glifos.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.integrations.cor_do_plastico import (
    CorDoPlastico,
    cor_do_nome,
)
from hefesto_dualsense4unix.utils.maquina import (
    MaquinaConfig,
    gravar_maquina,
)

UNIQ = "aa:bb:cc:00:00:07"
CHAVE = "aabbcc000007"
OUTRO = "aa:bb:cc:00:00:08"


def _maquina(**campos: Any) -> MaquinaConfig:
    return MaquinaConfig.model_validate({"controles": {CHAVE: campos}})


def _estado(*uniqs: str) -> dict[str, Any]:
    return {"controllers": [
        {"uniq": u, "connected": True, "transport": "usb", "player_slot": i}
        for i, u in enumerate(uniqs, start=1)
    ]}


def _mesa(mv: Any, uniq: str = UNIQ, cores: dict | None = None, **kw: Any) -> dict[str, Any]:
    (item,) = mv.mesa_do_estado(_estado(uniq), cores or {}, **kw)
    return item


@pytest.fixture(scope="module")
def mv():
    import mesa_viva

    return mesa_viva


# 1. A COR


def test_a_cor_declarada_pinta_o_controle_que_o_aparelho_nao_respondeu(mv) -> None:
    item = _mesa(mv, declaracao=_maquina(cor="Cosmic Red"))
    esperado = cor_do_nome("Cosmic Red")
    assert esperado is not None
    assert item["cor"] == esperado.id and item["nome"] == esperado.nome


def test_a_cor_lida_do_aparelho_vence_a_declarada(mv) -> None:
    lida = cor_do_nome("Starlight Blue")
    assert lida is not None
    item = _mesa(mv, cores={UNIQ: lida}, declaracao=_maquina(cor="Cosmic Red"))
    assert item["cor"] == lida.id, "a declarada passou por cima da que o aparelho disse"


def test_so_o_nome_do_modelo_nao_e_cor_lida(mv) -> None:
    """O `LeitorDeCor` entrega o modelo como uma cor SEM código: a declarada ainda vale."""
    so_o_modelo = CorDoPlastico(codigo="", nome="DualSense")
    item = _mesa(mv, cores={UNIQ: so_o_modelo}, declaracao=_maquina(cor="Cosmic Red"))
    assert item["cor"] == cor_do_nome("Cosmic Red").id


def test_nome_que_o_mapa_nao_conhece_nao_pinta_nada(mv) -> None:
    """O campo «Outra»: texto livre, sem hexa — o desenho fica no neutro."""
    item = _mesa(mv, declaracao=_maquina(cor="Rosa choque da minha tia"))
    assert item["cor"] == ""


def test_a_cor_e_do_controle_dela_e_nao_do_vizinho(mv) -> None:
    itens = mv.mesa_do_estado(_estado(UNIQ, OUTRO), {}, declaracao=_maquina(cor="Cosmic Red"))
    por_uniq = {i["uniq"]: i for i in itens}
    assert por_uniq[UNIQ]["cor"] != "" and por_uniq[OUTRO]["cor"] == ""


# 2. A FAMÍLIA DOS BOTÕES


@pytest.mark.parametrize(("campos", "familia"), [
    ({"botoes": "xbox"}, "xbox"),
    ({"botoes": "nintendo"}, "nintendo"),
    ({"modo": "xinput"}, "xbox"),
    ({"modo": "switch"}, "nintendo"),
    ({"modo": "dinput"}, ""),
    ({"botoes": "nintendo", "modo": "xinput"}, "nintendo"),
    ({}, ""),
])
def test_a_familia_dos_botoes_sai_no_item_da_mesa(mv, campos: dict, familia: str) -> None:
    assert _mesa(mv, declaracao=_maquina(**campos))["botoes"] == familia


def test_sem_declaracao_nenhuma_o_desenho_e_o_do_dualsense(mv) -> None:
    assert _mesa(mv, declaracao=MaquinaConfig())["botoes"] == ""


def test_as_letras_da_face_cobrem_os_quatro_botoes_de_cada_familia(mv) -> None:
    for familia, letras in mv.LETRAS_DA_FACE.items():
        assert set(letras) == {"cross", "circle", "square", "triangle"}, familia
        assert len(set(letras.values())) == 4, f"{familia}: duas posições com a mesma letra"
    assert set(mv.FAMILIA_DO_MODO.values()) <= set(mv.LETRAS_DA_FACE)


# 3. O DISCO (o caminho sem a declaração injetada)


def test_o_disco_e_relido_quando_o_arquivo_muda(mv) -> None:
    """A mesa lê o `maquina.json` do lar (o `conftest` o desvia) e o relê no gesto dela."""
    assert gravar_maquina({"controles": {CHAVE: {"botoes": "xbox"}}})
    assert _mesa(mv)["botoes"] == "xbox"
    assert gravar_maquina({"controles": {CHAVE: {"botoes": "nintendo", "cor": "Cosmic Red"}}})
    item = _mesa(mv)
    assert item["botoes"] == "nintendo" and item["cor"] == cor_do_nome("Cosmic Red").id


# 4. O DESENHO DA 02


def _pagina() -> str:
    return (RAIZ / "mockup/02-controles.html").read_text(encoding="utf-8")


def test_a_grade_de_cada_lugar_tem_o_endereco_da_familia() -> None:
    import monta

    doc = _pagina()
    enderecos = doc.count('data-campo="botoes" data-hef-alvo="atributo" '
                          'data-hef-atributo="data-botoes"')
    assert enderecos == len(monta.MESA), (
        f"{enderecos} grades com endereço para {len(monta.MESA)} lugares")


def test_a_folha_troca_o_rotulo_dos_quatro_botoes_de_cada_familia(mv) -> None:
    folha = "".join(re.findall(r"<style[^>]*>(.*?)</style>", _pagina(), re.S))
    for familia, letras in mv.LETRAS_DA_FACE.items():
        for botao, letra in letras.items():
            alvo = f'.glifos[data-botoes="{familia}"] .gb[data-glifo="{botao}"]'
            assert f'{alvo}::before{{content:"{letra}"}}' in folha, (familia, botao)
            assert f"{alvo} svg{{display:none}}" in folha, (familia, botao)


def test_o_desenho_nasce_sem_familia() -> None:
    """O mockup é o do DualSense: o atributo só aparece quando o produto o escreve."""
    assert not re.search(r'class="glifos"[^>]*\sdata-botoes="', _pagina())


def test_o_pacote_leva_a_familia_ao_endereco_do_card(monkeypatch) -> None:
    import pacotes
    from pacotes import a02_controles as a02

    monkeypatch.setattr(a02, "_ENDERECOS", frozenset({"botoes"}), raising=False)
    entrada = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
               "battery_pct": 95, "is_primary": True, "inputs": {}, "audio": {}}
    for familia in ("xbox", ""):
        mesa = [{"uniq": UNIQ, "pref": "p1", "nome": "White", "via": "USB",
                 "cor": "white", "botoes": familia}]
        ctx = pacotes.Contexto(state={}, mesa=mesa, conectados=[entrada], estados={})
        assert a02.pacote(ctx)["cards"][UNIQ]["botoes"] == familia


def test_pagina_sem_o_endereco_nao_recebe_o_campo(monkeypatch) -> None:
    """Enquanto o desenho não é publicado, o pacote não emite o que a página não tem."""
    import pacotes
    from pacotes import a02_controles as a02

    monkeypatch.setattr(a02, "_ENDERECOS", frozenset(), raising=False)
    ctx = pacotes.Contexto(
        state={}, mesa=[{"uniq": UNIQ, "pref": "p1", "nome": "White", "via": "USB",
                         "cor": "white", "botoes": "xbox"}],
        conectados=[{"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
                     "battery_pct": 95, "is_primary": True, "inputs": {}, "audio": {}}],
        estados={})
    assert "botoes" not in a02.pacote(ctx)["cards"][UNIQ]


# 5. A RÉGUA DO CADERNO


def test_o_consumidor_de_cada_campo_e_chamado_em_algum_lugar() -> None:
    """Um `def` sem chamador não é consumidor: a citação tem de apontar para quem É lido."""
    from tests.unit.test_todo_campo_do_caderno_tem_consumidor import (
        CONSUMIDOR_DE_PRODUCAO,
        SRC,
    )

    for campo, citacao in CONSUMIDOR_DE_PRODUCAO.items():
        arquivo, _, alvo = citacao.partition(":")
        nome = alvo.removeprefix("def ").strip()
        chamadas = 0
        for caminho in SRC.rglob("*.py"):
            texto = caminho.read_text(encoding="utf-8", errors="replace")
            achados = len(re.findall(rf"\b{re.escape(nome)}\b", texto))
            chamadas += achados - (1 if caminho == SRC / arquivo else 0)
        assert chamadas > 0, f"{campo}: `{nome}` é definido e ninguém o chama"


def test_nenhum_campo_do_caderno_fica_isento() -> None:
    from tests.unit.test_todo_campo_do_caderno_tem_consumidor import ISENTOS

    assert ISENTOS == {}, (
        "as isenções saíram em 06/10/2026 com as respostas dela; campo novo sem leitor "
        "ganha consumidor ou sai do esquema")
