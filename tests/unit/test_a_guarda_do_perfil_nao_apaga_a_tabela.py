"""A aba Perfis não pode escrever num endereço que CONTÉM a página."""
from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import Contexto, a10_perfis

VAZIAS = frozenset({
    "br", "img", "input", "meta", "link", "hr", "source", "area", "base",
    "col", "embed", "track", "wbr",
})

#: variável ``--plastico``. Só o alvo padrão — o texto — apaga filhos.
#: ela existe para pegar: pôr ``data-hef-alvo="classe"`` num ``<span>`` com glifo
ALVOS_SEGUROS = frozenset({"largura", "altura", "fundo", "valor", "html",
                           "classe", "cor", "plastico", "atributo"})


class _Leitor(HTMLParser):
    """Para cada ``data-hef`` da página: a tag, quantos filhos-elemento tem,"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.pilha: list[list[Any]] = []
        self.achados: list[dict[str, Any]] = []

    def _contar_no_pai(self, tag: str, d: dict[str, str | None]) -> None:
        """Um filho a mais no pai — e o que ele é, que é o que decide tudo."""
        if not self.pilha:
            return
        self.pilha[-1][2] += 1
        if tag == "svg":
            self.pilha[-1][3] = True
        if not (tag == "span" and (d.get("class") or "") == "pt"
                and not d.get("data-hef")):
            self.pilha[-1][5] += 1

    def _fechar(self) -> None:
        tag, endereco, filhos, tem_svg, alvo, estruturais = self.pilha.pop()
        if endereco:
            self.achados.append({"endereco": endereco, "tag": tag,
                                 "filhos": filhos, "svg": tem_svg, "alvo": alvo,
                                 "estruturais": estruturais})

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        d = dict(attrs)
        self._contar_no_pai(tag, d)
        if tag in VAZIAS:
            return
        self.pilha.append(
            [tag, d.get("data-hef"), 0, False, d.get("data-hef-alvo"), 0]
        )

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        d = dict(attrs)
        self._contar_no_pai(tag, d)
        if d.get("data-hef"):
            self.achados.append({"endereco": d["data-hef"], "tag": tag,
                                 "filhos": 0, "svg": False,
                                 "alvo": d.get("data-hef-alvo"),
                                 "estruturais": 0})

    def handle_endtag(self, tag: str) -> None:
        if tag in VAZIAS:
            return
        for i in range(len(self.pilha) - 1, -1, -1):
            if self.pilha[i][0] == tag:
                while len(self.pilha) > i:
                    self._fechar()
                return


def _pagina_publicada() -> list[dict[str, Any]]:
    """Os elementos endereçados do ``10-perfis.html`` que o produto RENDERIZA."""
    leitor = _Leitor()
    leitor.feed(
        onde.pagina("10-perfis.html", publicado=True).read_text(encoding="utf-8")
    )
    return leitor.achados


MESA = [
    {"pref": "p1", "uniq": "aabbcc000001", "jogador": 1,
     "cor": "cosmic-red", "nome": "Cosmic Red", "via": "BT",
     "transporte": "bt", "alvo": True, "mascara": "DualSense"},
    {"pref": "p2", "uniq": "aabbcc000002", "jogador": 2,
     "cor": "starlight-blue", "nome": "Starlight Blue", "via": "USB",
     "transporte": "usb", "alvo": False, "mascara": "DualSense"},
]


def _perfil_de_regua() -> Any:
    """Um perfil com ajuste próprio SÓ do primeiro controle.

    O DISCO NÃO SERVE, e a medição é de 02/09/2026: no lar de mentira do
    `conftest.py`, `load_all_profiles()` devolve **zero** perfis nesta suíte —
    a semeadura dos presets não roda aqui. (A nota em `a10_perfis.PROVAS`
    afirma nove; ela vale no processo em que a semeadura já correu, não neste.)
    Uma régua que dependesse disso daria verde por vacuidade: sem perfil,
    `pacote_da_aba` devolve `guarda=[]` e a tabela nunca é medida.
    """
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        MatchAny,
        Profile,
    )

    return Profile(
        name="régua", match=MatchAny(),
        controllers={MESA[0]["uniq"]: ControllerOverrides(
            rumble={"policy": "economia"})},
    )


def _emitidos(monkeypatch: Any = None) -> dict[str, Any]:
    """O que ``a10_perfis.pacote()`` manda pintar, com uma mesa de dois."""
    ctx = Contexto(state={"active_profile": "régua"}, mesa=list(MESA),
                   conectados=list(MESA), estados={})
    return a10_perfis.pacote(ctx)


@pytest.fixture(autouse=True)
def _perfil_no_lugar_do_disco(monkeypatch: pytest.MonkeyPatch) -> None:
    """O perfil da régua no lugar da pasta do usuário — e o `_ESCOLHIDO` limpo."""
    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(a10_perfis, "_ESCOLHIDO", "", raising=False)
    monkeypatch.setattr(loader, "load_all_profiles", lambda *a, **k: [_perfil_de_regua()])


def test_nenhum_endereco_emitido_apaga_a_pagina() -> None:
    """A régua-mãe: pintar um endereço não pode custar outro pedaço da tela."""
    por_endereco: dict[str, list[dict[str, Any]]] = {}
    for item in _pagina_publicada():
        por_endereco.setdefault(item["endereco"], []).append(item)

    estragos = []
    for chave, valor in _emitidos().items():
        if isinstance(valor, dict):
            continue
        for elemento in por_endereco.get(chave, []):
            if (elemento["alvo"] or "") in ALVOS_SEGUROS:
                continue
            if elemento["estruturais"]:
                estragos.append(
                    f"{chave}: <{elemento['tag']}> tem {elemento['estruturais']} "
                    f"filho(s) de ESTRUTURA — pintar como texto apaga "
                    f"{'o glifo SVG' if elemento['svg'] else 'a marcação'} "
                    f"dentro dele"
                )
    assert not estragos, (
        "endereços que o pacote emite e a página publicada não sabe receber:\n  "
        + "\n  ".join(sorted(estragos))
    )


def test_nenhuma_porcentagem_vai_para_um_elemento_sem_largura() -> None:
    """Um `"37%"` só é BARRA onde o HTML declara `data-hef-alvo="largura"`.

    Sem o alvo o pintor cai no ramo padrão e escreve a porcentagem como TEXTO
    dentro da barra, deixando a LARGURA no valor do desenho. Foi o segundo
    defeito da Prioridade: `"0%"` escrito dentro de um `<span class="cheio">`
    de 5px que continuava com `style="width:90%"` — quase cheio, para um
    perfil em 1 de 200.
    """
    import re

    por_endereco: dict[str, list[dict[str, Any]]] = {}
    for item in _pagina_publicada():
        por_endereco.setdefault(item["endereco"], []).append(item)

    fora_do_alvo = [
        f"{chave} = {valor!r} — <{elemento['tag']}> sem data-hef-alvo='largura'"
        for chave, valor in _emitidos().items()
        if isinstance(valor, str) and re.fullmatch(r"\d+(\.\d+)?%", valor)
        for elemento in por_endereco.get(chave, [])
        if (elemento["alvo"] or "") != "largura"
    ]
    assert not fora_do_alvo, (
        "porcentagem escrita como texto em vez de virar largura:\n  "
        + "\n  ".join(fora_do_alvo)
    )


@pytest.mark.parametrize("endereco", a10_perfis.NAO_PINTAVEIS)
def test_os_que_nao_saem_continuam_na_pagina(endereco: str) -> None:
    """Eles NÃO são endereços mortos: a página os tem, e o dia em que o HTML"""
    existe = {item["endereco"] for item in _pagina_publicada()}
    assert endereco in existe, (
        f"“{endereco}” saiu da página publicada e continua em "
        f"`a10_perfis.NAO_PINTAVEIS` — a lista virou fóssil"
    )


def test_a_tabela_da_guarda_nomeia_os_controles_da_mesa() -> None:
    """`guarda.nome` saía `["", ""]`: o `perfis_web` pede `rotulo` e a
    `mesa_do_estado` não devolve nenhum. É a cura de `_mesa_com_rotulo`."""
    fora = _emitidos()
    assert fora["guarda.nome"] == ["P1 • Cosmic Red • BT",
                                   "P2 • Starlight Blue • USB",
                                   "P3 • Desconectado",
                                   "P4 • Desconectado"]
    assert len(fora["guarda.id"]) == 4
    assert fora["guarda.id"][2:] == ["", ""], (
        "o lugar sem controle ganhou um ID — sem peça ali, não há o que mostrar")
    assert fora["guarda.vazio"] == ["", "", "sim", "sim"], (
        "a marca do lugar vazio não acende nos dois últimos: os glifos do "
        "mockup voltam à tela de um lugar sem controle")
    assert fora["perfis.com-ajuste"] == (
        "1 de 2 controles com ajuste próprio")


def test_o_rotulo_da_guarda_e_o_mesmo_do_monta() -> None:
    """A ordem do rótulo tem UM dono — `monta.rotulo`, decisão de 26/08."""
    monta = pytest.importorskip(
        "hefesto_dualsense4unix.interface.monta",
        reason="o gerador lê o repositório no import; num pacote instalado não há",
    )
    controle = {"jogador": 2, "nome": "Starlight Blue", "via": "USB"}
    do_gerador = monta.rotulo(controle, "curta").replace(
        monta.SEPARADOR, a10_perfis.SEPARADOR_EM_TEXTO
    )
    assert a10_perfis._rotulo_curto(controle) == do_gerador
