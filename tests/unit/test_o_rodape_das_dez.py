#!/usr/bin/env python3
"""O RODAPÉ: Aplicar · Salvar Perfil · Importar · Exportar, nas dez abas.

ELE NÃO É DE ABA NENHUMA — mora no `topo.html`, o esqueleto compartilhado — e é
por isso que seus gestos são registrados em `("*", nome)`.

O QUE ELE É NO PRODUTO ESTÁVEL, medido em 01/09/2026 a pedido dela (*"salvar
exportar importar. dividir e ver se a feature do botão tá condizendo com o
output seu"*):

    Aplicar   footer_actions.on_apply_draft    → profile.apply_draft     ✓ existe
    Salvar    footer_actions.on_save_profile   → save_profile            ✓ existe
    Importar  footer_actions.on_import_profile → FileChooser + validação ✓ existe
    Exportar  ——                                                          NÃO EXISTE

**"Exportar" é um botão que o desenho criou e o produto nunca teve.** Não há
handler no `src/`, e o `main.glade` traz `btn_footer_apply`, `btn_footer_import`
e `btn_footer_save_profile` — mais nenhum. Ele foi CONSTRUÍDO nesta leva, por
ordem dela: *"o que tiver em falta ou vc constrói ou manda agente ir
construindo"*.

O QUE ESTA RÉGUA COBRA, e as três primeiras são sobre estrago:

1. **Importar não sobrescreve perfil dela.** Nome repetido vira `nome-2`.
2. **Importar recusa o que não é perfil** ANTES de tocar a pasta.
3. **Cancelar não é erro** — e não escreve nada.
4. Aplicar e Salvar recusam sem perfil ativo, dizendo o quê fazer.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PERFIL = {
    "name": "Importado", "version": 1, "priority": 42,
    "match": {"type": "criteria", "process_name": ["x.exe"]},
    "triggers": {"left": {"mode": "Rigid", "params": [0, 180]},
                 "right": {"mode": "Off", "params": []}},
    "leds": {"lightbar": [10, 20, 30], "player_leds": [True] * 5,
             "lightbar_brightness": 1.0},
}


class PonteDeMentira:
    """Dublê da ponte, com o seletor de arquivo PROGRAMÁVEL.

    O seletor é o que separa este rodapé do resto: ele não é IPC, é do SISTEMA.
    Programá-lo aqui é o que deixa a régua cobrir os três caminhos que importam
    — ela escolhe, ela cancela, e ela escolhe um arquivo que não presta.
    """

    def __init__(self, escolhe=None, salva=None) -> None:
        self.chamadas: list[tuple] = []
        self._escolhe, self._salva = escolhe, salva

    def escolher_arquivo(self, titulo, padrao="*", **_):
        self.chamadas.append(("escolher_arquivo", titulo))
        return self._escolhe

    def salvar_arquivo(self, titulo, sugestao="", **_):
        self.chamadas.append(("salvar_arquivo", titulo))
        return self._salva

    def __getattr__(self, nome):
        def registrar(*a, **kw):
            self.chamadas.append((nome, a, kw))
            return True
        return registrar


@pytest.fixture
def casa(tmp_path, monkeypatch):
    """Uma pasta de perfis de mentira, e o leitor apontado para ela."""
    from pacotes import perfil

    pasta = tmp_path / "profiles"
    pasta.mkdir(parents=True)
    monkeypatch.setattr(perfil, "pasta", lambda: pasta)
    return pasta


@pytest.fixture
def ctx():
    from pacotes import Contexto

    return Contexto(state={"active_profile": ""}, mesa=[], conectados=[], estados={})


def _g(nome):
    import pacotes

    fn = pacotes.gesto_da_pagina("01-jogar.html", nome)
    assert fn is not None, f"o rodapé não registrou {nome!r} — ele vale nas DEZ abas"
    return fn


def test_os_quatro_do_rodape_valem_em_qualquer_aba():
    """Registrados em `("*", …)`, e o despachante os acha de qualquer página."""
    import pacotes

    for pagina in ("01-jogar.html", "05-vibracao.html", "10-perfis.html"):
        for nome in ("aplicar", "salvar", "importar", "exportar"):
            assert pacotes.gesto_da_pagina(pagina, nome) is not None, (
                f"{nome} não foi achado a partir de {pagina} — o rodapé é o "
                f"mesmo nas dez, e um `('*', …)` que não resolve deixa quatro "
                f"botões mudos em todas elas.")


def test_importar_nao_sobrescreve_perfil_dela(casa, ctx, tmp_path):
    """Nome repetido vira `nome-2`.

    Perder um perfil dela por um clique de importação é o estrago que esta
    linha impede — e a janela estável faz o mesmo ("resolve conflito de nome se
    necessário", `on_import_profile`).
    """
    (casa / "importado.json").write_text('{"ja": "estava aqui"}', encoding="utf-8")
    vindo = tmp_path / "de-fora.json"
    vindo.write_text(json.dumps(PERFIL), encoding="utf-8")

    _g("importar")(ctx, {}, PonteDeMentira(escolhe=str(vindo)))

    assert (casa / "importado.json").read_text(encoding="utf-8") == '{"ja": "estava aqui"}', (
        "o perfil que já estava lá foi SOBRESCRITO")
    assert (casa / "importado-2.json").exists(), "o novo devia entrar como -2"
    assert json.loads((casa / "importado-2.json").read_text())["priority"] == 42


def test_importar_recusa_o_que_nao_e_perfil(casa, ctx, tmp_path):
    """Um JSON qualquer é recusado ANTES de tocar a pasta dela."""
    ruim = tmp_path / "qualquer.json"
    ruim.write_text('{"oi": 1}', encoding="utf-8")

    p = PonteDeMentira(escolhe=str(ruim))
    with pytest.raises(ValueError, match="não é um perfil"):
        _g("importar")(ctx, {}, p)
    assert list(casa.glob("*.json")) == [], (
        "recusou e escreveu na pasta dela assim mesmo — a validação tem de vir "
        "ANTES de qualquer escrita")


def test_cancelar_o_seletor_nao_e_erro(casa, ctx):
    """Ela clicou e desistiu. Não levanta, não escreve."""
    p = PonteDeMentira(escolhe=None)
    _g("importar")(ctx, {}, p)            # não levanta
    assert list(casa.glob("*.json")) == []
    assert p.chamadas[0][0] == "escolher_arquivo"


def test_aplicar_e_salvar_recusam_sem_perfil_ativo(ctx):
    """E recusam DIZENDO o que fazer — a frase é parte do contrato."""
    for nome in ("aplicar", "salvar"):
        p = PonteDeMentira()
        with pytest.raises(ValueError, match=r"[Pp]erfil"):
            _g(nome)(ctx, {}, p)
        assert not any(c[0] == "apply_draft_detalhado" for c in p.chamadas), (
            f"{nome} recusou e chamou o daemon assim mesmo")
