"""A 07 recebe a extensão que se usa sem manual: o que a porta mostra, recusa e pede.

Com uma extensão de mentira (só declaração, nenhum processo), o que a 07 faz por qualquer
extensão de processo que ela instale:

- ligada no registro e calada no supervisor, a chave diz «Caiu», «Voltando» ou «Recusada» na cor
  do estado, com o motivo e a última linha do diário na dica (antes, verde «Ligada» sobre nada);
- o canto do «Agora» da janela diz o mesmo quando a conexão não respondeu;
- o «Parar tudo» com ela fora da porta (``{parado: false}``) recusa dizendo, em vez de piscar verde;
- o «Atualizar» que traz permissão ou aviso novo deixa o ⋮ aberto já com a lista, e um clique na
  chave é o «sim».

MORDIDAS (23/10/2026, executadas sobre a cura e devolvidas):

- as regras ``.nj-tog.ligado.vermelho`` e ``#mod-janela .est-vermelho`` tiradas do CSS reprovam
  ``test_a_ligada_que_caiu_diz_caiu_em_vermelho_com_o_porque_na_dica``;
- o ``parado`` ignorado no gesto (o recado de sempre) reprova
  ``test_o_parar_tudo_sem_ela_na_porta_recusa_dizendo``;
- o ⋮ sem a lista depois do «Atualizar» reprova
  ``test_atualizar_com_permissao_nova_mostra_a_lista_e_um_clique_liga`` (o clique só arma);
- o estado do supervisor ignorado em ``processo_de`` (a chave verde de sempre) reprova a chave que
  caiu, as três dos estados e o canto do «Agora».
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    _a07,
    _entrada,
    _fonte,
    _instalar,
    ctx,
    lar,
)

GESTO = "ler:acessorios.gesto"
AVISO = "Ela fala com um aparelho de fora."


def _instalada_e_ligada(a07: Any, ctx: Any, tmp_path: Any, *,  # noqa: F811
                        permissoes: tuple[str, ...] = (), **extra: Any) -> None:
    """Instalada e ligada pela chave; com permissão, o primeiro clique só mostra a lista."""
    _instalar(a07, ctx, _fonte(tmp_path, permissoes=permissoes, extra=extra))
    if permissoes:
        assert a07.ligar_modificacao(ctx, {"v": "toque"}, None).get("armou") is True
    assert a07.ligar_modificacao(ctx, {"v": "toque"}, None)["recado"] == "Toque ligada."


def _supervisor_diz(a07: Any, lar: Any, **linha: Any) -> None:  # noqa: F811
    lar.estado.parent.mkdir(parents=True, exist_ok=True)
    lar.estado.write_text(json.dumps({"mods": {"toque": linha}}), encoding="utf-8")
    a07.REGISTRO.esquecer()
    a07.VIGIA.esquecer()


def _chave(a07: Any, ctx: Any) -> str:  # noqa: F811
    lista = a07._a_pintura_agora(ctx)["blocos"][".ext-lista"]
    inicio = lista.index('data-gesto="ligar-modificacao" data-v="toque"')
    fim = lista.index("</span></span>", inicio) + len("</span></span>")
    return lista[lista.rindex("<span", 0, inicio):fim]


def test_a_ligada_que_caiu_diz_caiu_em_vermelho_com_o_porque_na_dica(lar, ctx, tmp_path) -> None:  # noqa: F811
    a07 = _a07()
    _instalada_e_ligada(a07, ctx, tmp_path)
    _supervisor_diz(a07, lar, estado="parou", motivo="Caiu 4 vezes seguidas (código 1).",
                    ultima_linha="ConnectionRefusedError: [Errno 111]", quedas=4)
    chave = _chave(a07, ctx)
    assert 'class="nj-tog ligado vermelho"' in chave and ">Caiu<" in chave
    assert "Caiu 4 vezes seguidas" in chave and "ConnectionRefusedError" in chave
    assert "Desligue e ligue para tentar de novo." in chave
    css = a07.exp.CSS
    assert ".nj-tog.ligado.vermelho {" in css and ".nj-tog.ligado.amarelo {" in css, (
        "a chave vermelha sem regra no CSS se pinta de verde, a cor do «ligado»")
    assert "#mod-janela .est-vermelho {" in css


@pytest.mark.parametrize(("estado", "classe", "palavra"), [
    ("voltando", "nj-tog ligado amarelo", "Voltando"),
    ("recusada", "nj-tog ligado vermelho", "Recusada"),
    ("rodando", "nj-tog ligado", "Ligada"),
])
def test_cada_estado_do_supervisor_tem_a_sua_chave(lar, ctx, tmp_path, estado, classe,  # noqa: F811
                                                    palavra) -> None:
    a07 = _a07()
    _instalada_e_ligada(a07, ctx, tmp_path)
    _supervisor_diz(a07, lar, estado=estado, motivo="")
    chave = _chave(a07, ctx)
    assert f'class="{classe}"' in chave and f">{palavra}<" in chave


def test_desligada_segue_desligada_seja_qual_for_o_supervisor(lar, ctx, tmp_path) -> None:  # noqa: F811
    a07 = _a07()
    _instalar(a07, ctx, _fonte(tmp_path))
    _supervisor_diz(a07, lar, estado="parou", motivo="Caiu.")
    chave = _chave(a07, ctx)
    assert 'class="nj-tog"' in chave and ">Desligada<" in chave


class _Ponte:
    """O ``p`` da janela: ``mods.agora`` sem conexão e ``mods.parar_tudo`` com o ``parado`` dado."""

    def __init__(self, parado: bool) -> None:
        self.parado = parado
        self.chamadas: list[str] = []

    def resultado(self, metodo: str, **params: Any) -> Any:
        self.chamadas.append(metodo)
        if metodo == "mods.parar_tudo":
            return {"parado": self.parado}
        vazio = {"ligado": False, "conexoes": [], "aparelhos": []}  # noqa-acento: chaves
        return {"mod": params.get("mod"), **vazio}

    def chamar_com_o_corpo(self, metodo: str, **params: Any) -> tuple[bool, str | None, Any]:
        return True, None, self.resultado(metodo, **params)

    def escolher_arquivo(self, *_: Any, **__: Any) -> str | None:
        return None


def test_o_canto_do_agora_diz_que_ela_caiu(lar, ctx, tmp_path) -> None:  # noqa: F811
    a07 = _a07()
    _instalada_e_ligada(a07, ctx, tmp_path, permissoes=(GESTO,), agora=["aparelhos"],
                        parar_tudo=True)
    _supervisor_diz(a07, lar, estado="parou", motivo="Não abriu: sem o executável.")
    coluna = a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte(True))["blocos"]["#mod-agora"]
    assert 'class="ja-srv est est-vermelho"' in coluna and "Caiu" in coluna
    assert "Não abriu: sem o executável." in coluna


def test_o_parar_tudo_sem_ela_na_porta_recusa_dizendo(lar, ctx, tmp_path) -> None:  # noqa: F811
    a07 = _a07()
    _instalada_e_ligada(a07, ctx, tmp_path, permissoes=(GESTO,), agora=["aparelhos"],
                        parar_tudo=True)
    a07.configurar_modificacao(ctx, {"v": "toque"}, _Ponte(False))
    with pytest.raises(RuntimeError, match="Toque não está rodando: nada a parar"):
        a07.parar_tudo_da_modificacao(ctx, {"v": "toque"}, _Ponte(False))
    ponte = _Ponte(True)
    assert "Parar tudo" in a07.parar_tudo_da_modificacao(ctx, {"v": "toque"}, ponte)["recado"]
    assert ponte.chamadas == ["mods.parar_tudo"]


def test_a_recusa_do_servico_chega_ao_parar_tudo(lar, ctx, tmp_path, monkeypatch) -> None:  # noqa: F811
    """A frase da recusa do serviço chega ao recado, e o ``{parado: false}`` vira «não está
    rodando»: pela ponte da janela, só com o IPC dublado."""
    from hefesto_dualsense4unix.interface.pacotes import ponte

    a07 = _a07()
    _instalada_e_ligada(a07, ctx, tmp_path, permissoes=(GESTO,), agora=["aparelhos"],
                        parar_tudo=True)
    respostas: list[tuple[bool, str | None, Any]] = [
        (False, "«Toque» não declara o «Parar tudo».", None), (True, None, {"parado": False})]
    monkeypatch.setattr(ponte._b, "_call_checked_detalhado",
                        lambda metodo, params, timeout=None: respostas.pop(0))
    with pytest.raises(RuntimeError, match="não declara o «Parar tudo»"):
        a07.parar_tudo_da_modificacao(ctx, {"v": "toque"}, ponte)
    with pytest.raises(RuntimeError, match="Toque não está rodando: nada a parar"):
        a07.parar_tudo_da_modificacao(ctx, {"v": "toque"}, ponte)


@pytest.mark.parametrize("novo", [{"permissoes": [GESTO]}, {"aviso": AVISO}])  # noqa-acento: chave
def test_atualizar_com_permissao_nova_mostra_a_lista_e_um_clique_liga(lar, ctx, tmp_path,  # noqa: F811
                                                                    novo) -> None:
    a07 = _a07()
    _instalada_e_ligada(a07, ctx, tmp_path)
    _fonte(tmp_path, extra={"versao": "0.2", **novo})  # noqa-acento: a chave do manifesto
    p = SimpleNamespace()
    carga = a07.mais_da_modificacao(ctx, {"v": "toque:atualizar"}, p)
    entrada = _entrada(lar, "toque")
    assert entrada.versao == "0.2" and entrada.ligada is False, "a versão nova ligou sem o «sim»"
    lista = carga["blocos"][".ext-lista"]
    assert 'class="ext-perm"' in lista, "o ⋮ aberto não mostra o que a versão nova pede"
    if "aviso" in novo:
        assert AVISO in lista
    ligou = a07.ligar_modificacao(ctx, {"v": "toque"}, p)
    assert ligou.get("recado") == "Toque ligada.", (
        "o «sim» depois do «Atualizar» pediu dois cliques")
    entrada = _entrada(lar, "toque")
    assert entrada.ligada is True
    assert GESTO in entrada.permissoes_aceitas or entrada.aviso_aceito == AVISO
