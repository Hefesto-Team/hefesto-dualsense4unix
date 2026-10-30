"""A janela de uma extensão de tema importa, tira e diz a recusa do destaque na linha dele
(O-GERENCIADOR-DE-TEMA-E-A-EXTENSAO-DE-FABRICA-01).

A opção ``importar`` vira «Importar» sem arquivo e «Trocar» e «Tirar» com ele; o nome do arquivo
mora só na dica, nunca como texto embaixo. A opção ``css`` ganha «Importar» ao lado de «Editar».
A janela da extensão que pinta o tema (bloco ``tema`` preenchido) leva os grupos em abas, como
a da Lovense, e a chave do grupo vira a bolinha da aba; a das outras continua nos cartões.
Extensões FALSAS num lar de mentira; o seletor de arquivo é o da ponte de mentira.

MORDIDAS (30/10/2026, executadas sobre a cura e devolvidas):

- o ramo ``importar`` arrancado de ``_controle_da_opcao`` (cai no número) reprova
  ``test_o_importar_sem_arquivo_e_um_botao_so`` e
  ``test_com_arquivo_trocar_e_tirar_e_o_nome_na_dica``;
- o ``_notas_do_tema`` devolvendo vazio reprova ``test_o_destaque_ilegivel_aparece_na_linha_dele``;
- o ``escolher_arquivo`` ignorado (o gesto importa sempre o mesmo caminho) reprova
  ``test_o_gesto_importa_o_escolhido_e_cancelar_nao_fala``;
- o ``em_abas`` arrancado da chamada do ``_montar_a_janela_da_extensao`` reprova
  ``test_a_janela_do_tema_vai_em_abas_como_a_da_lovense``.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from hefesto_dualsense4unix.mods import importados, opcoes
from hefesto_dualsense4unix.mods.instalador import Lugares
from tests.unit.test_o_tema_por_escolha_importa_e_personaliza import (
    NOVA,
    _arquivo,
    _ligada,
    _manifesto,
    _pasta,
    _png,
)

INTERFACE = Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix" / "interface"


def _linha(o: exp.OpcaoDaJanela) -> str:
    return exp._linha_da_opcao(o)


def _sem_tags(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def test_o_importar_sem_arquivo_e_um_botao_so() -> None:
    html = _linha(exp.OpcaoDaJanela("m", "logo", "Logo", "importar", ""))
    assert f'data-gesto="{exp.GESTO_DE_IMPORTAR}" data-v="m:logo"' in html
    assert exp.GESTO_DE_TIRAR not in html
    assert _sem_tags(html) == "Logo Importar"


def test_com_arquivo_trocar_e_tirar_e_o_nome_na_dica() -> None:
    html = _linha(exp.OpcaoDaJanela("m", "logo", "Logo", "importar", "minha-logo.png"))
    assert _sem_tags(html) == "Logo Trocar Tirar", "o nome do arquivo virou texto na linha"
    assert f'data-gesto="{exp.GESTO_DE_TIRAR}" data-v="m:logo" data-dica="minha-logo.png"' in html
    assert html.count('data-dica="minha-logo.png"') == 2


def test_o_css_ganha_o_importar_ao_lado_do_editar() -> None:
    html = _linha(exp.OpcaoDaJanela("m", "meu_css", "Meu CSS", "css", False))
    assert f'data-gesto="{exp.GESTO_DE_IMPORTAR}" data-v="m:meu_css"' in html
    assert html.index(exp.GESTO_DE_IMPORTAR) < html.index(exp.GESTO_DO_CSS)


@pytest.fixture
def lg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lugares:
    lugares = Lugares(codigo=tmp_path / "codigo", dados=tmp_path / "dados",  # (noqa-acento)
                      registro=tmp_path / "config" / "mods.json",
                      estado=tmp_path / "run" / "mods-estado.json")
    monkeypatch.setattr(Lugares, "do_xdg", classmethod(lambda cls: lugares))
    return lugares


@pytest.fixture
def a07(lg: Lugares, monkeypatch: pytest.MonkeyPatch) -> Any:
    sys.path.insert(0, str(INTERFACE))
    from hefesto_dualsense4unix.interface.pacotes import a07_lancadores

    monkeypatch.setattr(a07_lancadores.VIGIA, "_disparar", lambda: None)
    a07_lancadores.REGISTRO.esquecer()
    a07_lancadores._MEXIDA.limpar()
    yield a07_lancadores
    a07_lancadores.REGISTRO.esquecer()
    a07_lancadores._MEXIDA.limpar()


@pytest.fixture
def ctx() -> Any:
    sys.path.insert(0, str(INTERFACE))
    import pacotes

    return pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})


class _Ponte:
    def __init__(self, escolhido: Path | None) -> None:
        self.escolhido = escolhido
        self.pedidos: list[tuple[str, str]] = []

    def escolher_arquivo(self, titulo: str, padrao: str = "*", **_: Any) -> str | None:
        self.pedidos.append((titulo, padrao))
        return str(self.escolhido) if self.escolhido else None


def test_o_gesto_importa_o_escolhido_e_cancelar_nao_fala(a07: Any, ctx: Any, lg: Lugares,
                                                          tmp_path: Path) -> None:
    manifesto = _ligada(lg, _pasta(tmp_path, _manifesto()))
    logo = _arquivo(tmp_path, "minha-logo.png", _png())
    assert a07.importar_na_modificacao(ctx, {"v": f"{NOVA}:logo"}, _Ponte(None)) is None
    assert opcoes.ler(manifesto, lg)["logo"] == ""
    ponte = _Ponte(logo)
    resposta = a07.importar_na_modificacao(ctx, {"v": f"{NOVA}:logo"}, ponte)
    assert resposta["recado"] == "Importado: minha-logo.png."
    assert ponte.pedidos == [("Escolha a logo para importar", "*")]
    assert importados.caminho(NOVA, "logo", lg).read_bytes() == logo.read_bytes()
    assert 'data-dica="minha-logo.png"' in a07._MEXIDA.html_mod
    a07.tirar_da_modificacao(ctx, {"v": f"{NOVA}:logo"}, ponte)
    assert not importados.caminho(NOVA, "logo", lg).exists()
    assert opcoes.ler(manifesto, lg)["logo"] == ""


def test_o_arquivo_recusado_vira_a_frase_e_nada_se_grava(a07: Any, ctx: Any, lg: Lugares,
                                                         tmp_path: Path) -> None:
    manifesto = _ligada(lg, _pasta(tmp_path, _manifesto()))
    falsa = _arquivo(tmp_path, "logo.png", b"<svg onload=alert(1)>")
    with pytest.raises(RuntimeError, match="PNG, JPEG ou WebP"):
        a07.importar_na_modificacao(ctx, {"v": f"{NOVA}:logo"}, _Ponte(falsa))
    assert opcoes.ler(manifesto, lg)["logo"] == ""
    with pytest.raises(RuntimeError, match="não importa"):
        a07.importar_na_modificacao(ctx, {"v": f"{NOVA}:botoes"}, _Ponte(falsa))


def test_o_destaque_ilegivel_aparece_na_linha_dele(a07: Any, lg: Lugares,
                                                   tmp_path: Path) -> None:
    manifesto = _ligada(lg, _pasta(tmp_path, _manifesto()))
    opcoes.guardar(manifesto, "destaque", True, lg)
    opcoes.guardar(manifesto, "cor_de_destaque", "#1e1f29", lg)
    a07._montar_a_janela_da_extensao(NOVA)
    linha = re.search(r'<div class="ky-linha" id="mod-op-cor_de_destaque".*?</div></div>',
                      a07._MEXIDA.html_mod)
    assert linha and "ky-recusa" in linha.group(0) and "ilegível" in linha.group(0)
    opcoes.guardar(manifesto, "cor_de_destaque", "#50fa7b", lg)
    a07._montar_a_janela_da_extensao(NOVA)
    assert "ky-recusa" not in a07._MEXIDA.html_mod


def test_a_janela_do_tema_vai_em_abas_como_a_da_lovense(a07: Any, lg: Lugares,
                                                        tmp_path: Path) -> None:
    _ligada(lg, _pasta(tmp_path, _manifesto()))
    a07._montar_a_janela_da_extensao(NOVA)
    html = a07._MEXIDA.html_mod
    assert 'class="ac-card mj-abas" style="--n:4"' in html and "ky-grade" not in html
    rotulos = re.findall(r'<label for="mj-aba-\d">([^<]+)', html)
    assert rotulos == ["Cores", "Destaque", "Janela", "CSS"]
    assert f'data-v="{NOVA}:destaque"' in html and 'id="mod-chave-da-aba-1"' in html


def test_a_extensao_que_nao_e_tema_segue_nos_cartoes() -> None:
    opcoes = [exp.OpcaoDaJanela("m", "a", "A", "ligado", False, grupo="Um"),
              exp.OpcaoDaJanela("m", "b", "B", "ligado", False, grupo="Dois")]
    assert "mj-abas" not in exp.modificacao_miolo_html("M", opcoes, mod="m")
    assert "mj-abas" in exp.modificacao_miolo_html("M", opcoes, mod="m", em_abas=True)
    um = exp.modificacao_miolo_html("M", opcoes[:1], mod="m", em_abas=True)
    assert "mj-abas" not in um and "ac-card" in um
