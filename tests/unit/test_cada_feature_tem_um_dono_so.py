"""Cada feature tem um dono só na interface (CADA-FEATURE-TEM-UM-DONO-SO-NA-INTERFACE-01).

A fala de 12/10/2026: «Temos que evitar features se repetindo em abas diferentes.»

O mapa `FEATURES` diz, para cada feature, QUEM A ESCREVE: a aba dona e os gestos de escrita dela.
Dois olhares, e os dois reprovam o mesmo defeito, por caminhos diferentes:

1. **as páginas** (a bancada e a publicada): nenhuma página fora da dona emite um desses gestos
   como botão. Selo, dica e texto passam: só `data-gesto` e `data-hef-gesto` contam;
2. **o registro dos pacotes**: nenhuma página fora da dona atende um desses gestos. Um botão
   escondido, ou um gesto herdado de outra tela, reprova aqui mesmo que a página não o mostre.

E um terceiro, contra a régua cega: a dona emite ou atende ao menos um gesto de cada papel.

A perna «publicada» da Calibrar fica vermelha até o `--publicar` do fecho (a bancada já está
curada): é por desenho, como nas outras réguas de tela.

MORDIDA: devolver o `analogico-lado` ao pacote da Calibrar (`@gesto("calibrar-sensores.html",
"analogico-lado")`), ou o botão `data-gesto="analogico-lado"` ao gerador dela, reprova.
"""

from __future__ import annotations

import html.parser
import sys
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BANCADA = RAIZ / "mockup"
PUBLICADAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"

#: (feature, papel) -> (aba dona, gestos de escrita). O papel separa quem define, quem escolhe e
#: quem ativa: a MESMA feature pode ter donos diferentes por papel, nunca dois donos no mesmo.
FEATURES: dict[tuple[str, str], tuple[str, frozenset[str]]] = {
    ("point and click", "definir o estilo"): (
        "06-navegacao.html", frozenset({"point-and-click-perfil"})),
    ("point and click", "escolher o estilo do perfil"): (
        "10-perfis.html", frozenset({"editor.estilo"})),
    ("point and click", "ativar"): (
        "01-jogar.html", frozenset({"modo-point-and-click"})),
    ("máscara", "escolher"): (
        "01-jogar.html", frozenset({"mascara"})),
    ("analógico virtual", "ligar e escolher o lado"): (
        "02-controles.html", frozenset({"analogico-lado", "analogico-virtual", "mira"})),
    ("velocidade do cursor", "ajustar"): (
        "06-navegacao.html", frozenset({"vel-cursor"})),
    ("atalho do jogo", "aplicar nos lançadores, política global"): (
        "09-sistema.html", frozenset({"correcoes-automaticas"})),
}

PAGINAS = sorted(p.name for p in BANCADA.glob("*.html"))
ARQUIVOS = [pytest.param(pasta, nome, id=f"{rotulo}-{nome}")
            for rotulo, pasta in (("bancada", BANCADA), ("publicada", PUBLICADAS))
            for nome in PAGINAS]


class _Gestos(html.parser.HTMLParser):
    """Os gestos que uma página emite como botão: fora de `<script>`, `<style>` e comentário."""

    def __init__(self) -> None:
        super().__init__()
        self.gestos: set[str] = set()
        self._fora = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._fora += 1
            return
        if self._fora:
            return
        for chave, valor in attrs:
            if chave in ("data-gesto", "data-hef-gesto") and valor:
                self.gestos.add(valor)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._fora:
            self._fora -= 1


def gestos_da_pagina(texto: str) -> set[str]:
    leitor = _Gestos()
    leitor.feed(texto)
    return leitor.gestos


def _donos_do_gesto() -> dict[str, set[str]]:
    """Cada gesto de escrita do mapa -> as abas que o mapa deixa emiti-lo."""
    donos: dict[str, set[str]] = {}
    for dona, gestos in FEATURES.values():
        for gesto in gestos:
            donos.setdefault(gesto, set()).add(dona)
    return donos


def _pacotes() -> Any:
    interface = str(RAIZ / "src" / "hefesto_dualsense4unix" / "interface")
    if interface not in sys.path:
        sys.path.insert(0, interface)
    import pacotes

    pacotes._carregar_tudo()
    return pacotes


# --- o mapa ------------------------------------------------------------------------------------

def test_o_mapa_tem_um_dono_por_gesto() -> None:
    """Um gesto de escrita com duas donas é o defeito que a régua existe para matar."""
    repetidos = {g: d for g, d in _donos_do_gesto().items() if len(d) != 1}
    assert not repetidos, f"gesto com mais de uma dona no mapa: {repetidos}"
    assert {dona for dona, _ in FEATURES.values()} <= set(PAGINAS), (
        "o mapa cita uma aba que a bancada não tem")


# --- as páginas --------------------------------------------------------------------------------

@pytest.mark.parametrize(("pasta", "nome"), ARQUIVOS)
def test_nenhuma_pagina_emite_o_gesto_de_escrita_de_outra_aba(pasta: Path, nome: str) -> None:
    """Gesto de escrita fora da aba dona reprova; selo, dica e texto passam."""
    emitidos = gestos_da_pagina((pasta / nome).read_text(encoding="utf-8"))
    fora = {g: sorted(d) for g, d in _donos_do_gesto().items()
            if g in emitidos and nome not in d}
    assert not fora, f"{nome} emite gesto de escrita que é de outra aba (gesto -> dona): {fora}"


def test_a_bancada_da_dona_emite_o_que_o_mapa_diz() -> None:
    """Contra a régua cega: a dona emite ou atende ao menos um gesto de cada papel."""
    achados = {nome: gestos_da_pagina((BANCADA / nome).read_text(encoding="utf-8"))
               for nome in PAGINAS}
    assert len(achados) >= 11 and any(achados.values()), "a bancada sumiu — régua cega"
    sem_nenhum = []
    pacotes = _pacotes()
    for (feature, papel), (dona, gestos) in FEATURES.items():
        na_pagina = gestos & achados.get(dona, set())
        no_registro = {g for g in gestos if (dona, g) in pacotes.GESTOS}
        if not (na_pagina or no_registro):
            sem_nenhum.append((feature, papel, dona))
    assert not sem_nenhum, f"a dona não emite nem atende o gesto do papel: {sem_nenhum}"


# --- o registro dos pacotes ----------------------------------------------------------------------

def test_nenhum_pacote_atende_o_gesto_de_escrita_de_outra_aba() -> None:
    pacotes = _pacotes()
    donos = _donos_do_gesto()
    fora = sorted(f"{pagina}:{gesto}" for (pagina, gesto) in pacotes.GESTOS
                  if gesto in donos and pagina not in donos[gesto])
    assert not fora, f"gesto de escrita atendido por outra aba: {fora}"


# --- a própria régua morde ---------------------------------------------------------------------

def test_o_detector_ve_o_botao_e_ignora_o_selo_a_dica_e_o_estilo() -> None:
    """O botão conta; o selo com a mesma palavra, a dica, o comentário e o CSS não."""
    botao = '<button data-gesto="analogico-lado" data-lado="x">Esquerdo</button>'
    so_leitura = (
        '<!-- data-gesto="analogico-lado" -->'
        '<style>.sw[data-gesto="analogico-lado"]{color:red}</style>'
        '<span class="selo" data-dica="Para trocar o lado, vá à aba Controles">Mira virtual</span>'
        "<script>var x = 'data-gesto=\"analogico-lado\"';</script>")
    assert "analogico-lado" in gestos_da_pagina(botao)
    assert gestos_da_pagina(so_leitura) == set()


def test_a_regua_reprova_o_botao_que_volta_para_a_calibrar() -> None:
    """A mordida em miniatura: a mesma conta da régua das páginas, com o botão de volta."""
    # Prova da D-1510-O-ANALOGICO-VIRTUAL-SO-NA-ABA-CONTROLES.
    emitidos = gestos_da_pagina(
        '<button data-gesto="analogico-lado" data-lado="analogico_esquerdo">Esquerdo</button>')
    fora = {g: d for g, d in _donos_do_gesto().items()
            if g in emitidos and "calibrar-sensores.html" not in d}
    assert fora, "a régua não reprovou o analogico-lado na Calibrar"
