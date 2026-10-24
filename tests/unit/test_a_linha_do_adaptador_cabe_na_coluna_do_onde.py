"""A linha do adaptador cabe na coluna do «onde», e o sino não cobre nada.

Sprint: A-LINHA-DO-ADAPTADOR-NAO-CABE-NA-COLUNA-DO-ONDE-01.

Medido em 24/10/2026, no lar de mentira (P1 no cabo, os outros três no rádio): a coluna do «onde» da
linha do adaptador tinha 116 px fixos, e a marca da USB 3.0, a espera «Segure PS + Create» e o
«Onde fica?» passavam dela; a espera ficava sob o sino, o «Onde fica?» quebrava em duas linhas e o
«Dentro da máquina» em três. A cura é a grade UMA, a da sala, herdada por cada caixa (`subgrid`): a
coluna do «onde» cresce até o que ela leva, para todos os adaptadores, e as barras continuam na
mesma reta.

A régua pinta a sala no WebKit (o pintor do piloto, `radio-sala`) com a cena do desenho mudada para
a mesa mista e confere, em cada linha: nenhum filho do «onde» passa da borda dele, nenhum filho da
linha cruza outro (o sino incluído), o «Onde fica?» e a espera ocupam uma linha, as barras começam
e acabam na mesma reta, e nada rola de lado.

TUDO É DE MENTIRA: a página num WebKit fora da tela; nada chega a daemon.

MORDIDA (24/10/2026): devolver a coluna de 116 px (`24px auto 116px 26px …` na linha, sem a grade
da sala) reprova a régua no transbordo e no sino.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from tests.conftest import skip_sem_gi_real
from tests.unit.test_a_conexoes_cabe_na_tela import (  # noqa: F401 -- a fixture de módulo vem junto
    _clicar,
    _no_webkit,
    um_webview_por_modulo,
)

RAIZ = Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "mockup" / "08-conexoes.html"
PUBLICADA = onde.pagina("08-conexoes.html", publicado=True)
#: a marca da cura no CSS da página; o publicado a ganha no `--publicar` da costura
MARCA_DA_CURA = "minmax(116px,max-content)"
TAMANHOS = ((1212, 809), (1280, 860), (1920, 1000))
QUEDA = {"carimbo": 0.0, "quando": "18:47", "porque": "Som além do limite"}


def _cena_base() -> dict[str, Any]:
    """A cena do desenho na mesa mista: o Cosmic Red no cabo (fora do rádio), os outros três no
    rádio, um por adaptador."""
    from hefesto_dualsense4unix.interface import aba08

    cena = copy.deepcopy(aba08.CENA_DO_RADIO)
    cena["aparelhos"] = [a for a in cena["aparelhos"]
                         if a["id"] != "P1" and not str(a["id"]).startswith("nao-conectou")]
    for ap, lugar in (("P2", "L1"), ("P3", "L2"), ("P4", "L3")):
        next(a for a in cena["aparelhos"] if a["id"] == ap)["lugar"] = lugar
    for lug in cena["lugares"]:
        lug["nao_conectou"] = False
    cena["aberto"] = None
    return cena


def _com_a_foto_dela(cena: dict[str, Any], lid: str, quem: tuple[str, ...]) -> dict[str, Any]:
    """O lugar da foto: sem face (o «Onde fica?»), na USB 3.0, perto de um vizinho, com o sino e
    com quem está em `quem` esperando PS + Create."""
    lug = next(lg for lg in cena["lugares"] if lg["id"] == lid)
    lug.update(face="", hub=False, usb3=True, junto="encostado em outro rádio", quedas=[QUEDA])
    for ap in cena["aparelhos"]:
        if ap["id"] in quem:
            ap["lugar"] = lid
            ap["esperando"] = True
    return cena


def _cena_da_foto() -> dict[str, Any]:
    return _com_a_foto_dela(_cena_base(), "L1", ("P2",))


def _cena_dentro_da_maquina() -> dict[str, Any]:
    """O lugar sem entrada sabida diz «Dentro da máquina»; a espera vai ao lado."""
    cena = _com_a_foto_dela(_cena_base(), "L2", ("P3",))
    next(lg for lg in cena["lugares"] if lg["id"] == "L2").update(lugar="", entrada="")
    return cena


def _cena_de_dois_esperando() -> dict[str, Any]:
    return _com_a_foto_dela(_cena_base(), "L3", ("P3", "P4"))


def _cena_de_um_so() -> dict[str, Any]:
    """Um adaptador só: a linha não tem a seta, e a coluna dela fica vazia."""
    cena = _com_a_foto_dela(_cena_base(), "L1", ("P2",))
    cena["lugares"] = cena["lugares"][:1]
    cena["aparelhos"] = [a for a in cena["aparelhos"] if a["lugar"] == "L1"]
    return cena


CENAS = {"a-foto-dela": _cena_da_foto, "dentro-da-maquina": _cena_dentro_da_maquina,
         "dois-esperando": _cena_de_dois_esperando, "um-so": _cena_de_um_so}


def _pintar_a_sala(cena: dict[str, Any]) -> str:
    html = a08.html_da_sala(cena, com_hz=True)
    return f"String(window.__hef.pintar({json.dumps({'mesa': {'radio-sala': html}})}))"


#: Mede cada linha de adaptador e devolve os defeitos, com o que foi visto para o recado.
_MEDIR = r"""(function(){
const vis = e => e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden';
const R = e => e.getBoundingClientRect();
const cruza = (a, b) => a.left < b.right - 0.5 && a.right > b.left + 0.5
                     && a.top < b.bottom - 0.5 && a.bottom > b.top + 0.5;
const defeitos = [], visto = {esperas: 0, ensinas: 0, sinos: 0, linhas: 0};
const topos = [...document.querySelectorAll('.radio .sala .lugar > .lugar-topo')].filter(vis);
for (const [i, topo] of topos.entries()) {
  visto.linhas++;
  const ond = topo.querySelector(':scope > .onde');
  const ro = R(ond);
  if (ond.scrollWidth > ond.clientWidth + 1)
    defeitos.push(`linha ${i}: o onde rola de lado (${ond.scrollWidth} em ${ond.clientWidth})`);
  for (const f of [...ond.children].filter(vis)) {
    const rf = R(f);
    if (rf.right > ro.right + 0.5 || rf.left < ro.left - 0.5)
      defeitos.push(`linha ${i}: «${(f.textContent || f.className).trim()}» passa da coluna ` +
                    `do onde (${Math.round(rf.left)} a ${Math.round(rf.right)} em ` +
                    `${Math.round(ro.left)} a ${Math.round(ro.right)})`);
    if (f.matches('.espera,.ensina') && f.getClientRects().length !== 1)
      defeitos.push(`linha ${i}: «${f.textContent.trim()}» quebra em ` +
                    `${f.getClientRects().length} linhas`);
    if (f.matches('.espera')) visto.esperas++;
    if (f.matches('.ensina')) visto.ensinas++;
  }
  const textos = [...ond.children].filter(e => vis(e) && e.tagName === 'SPAN' && !e.className);
  for (const t of textos)
    if (t.getClientRects().length !== 1 || R(t).height > 20)
      defeitos.push(`linha ${i}: «${t.textContent.trim()}» quebra a linha ` +
                    `(${Math.round(R(t).height)} px)`);
  const pecas = [...topo.children].filter(vis);
  visto.sinos += pecas.filter(e => e.matches('.sino')).length;
  const miudas = [ond, ...[...ond.children].filter(vis)];
  for (const a of pecas.concat(miudas.slice(1)))
    for (const b of pecas)
      if (a !== b && !b.contains(a) && !a.contains(b) && cruza(R(a), R(b)))
        defeitos.push(`linha ${i}: «${(a.textContent || a.className).trim()}» cruza ` +
                      `«${(b.textContent || b.className).trim()}»`);
}
const barras = topos.map(t => t.querySelector(':scope > .barra-do-lugar')).filter(Boolean)
  .map(b => [Math.round(R(b).left), Math.round(R(b).right)]);
if (new Set(barras.map(b => b.join())).size > 1)
  defeitos.push('as barras não começam e acabam na mesma reta: ' + JSON.stringify(barras));
const sala = document.querySelector('.radio .sala');
if (sala.scrollWidth > sala.clientWidth + 1)
  defeitos.push(`a sala rola de lado (${sala.scrollWidth} em ${sala.clientWidth})`);
const doc = document.scrollingElement;
if (doc.scrollWidth > innerWidth + 1)
  defeitos.push(`a página rola de lado (${doc.scrollWidth} em ${innerWidth})`);
return JSON.stringify({defeitos, visto, barras});
})()"""


def _medir_a_sala(pagina: Path, tamanho: tuple[int, int], cena: dict[str, Any]) -> dict[str, Any]:
    lidas = _no_webkit(pagina, tamanho, [_clicar('label[for="cx8-3"]'), _pintar_a_sala(cena),
                                         _MEDIR])
    assert lidas[0] == "clicou", lidas[0]
    medida = lidas[-1]
    assert isinstance(medida, dict), medida
    return medida


def _conferir(pagina: Path, tamanho: tuple[int, int], nome: str) -> None:
    cena = CENAS[nome]()
    medida = _medir_a_sala(pagina, tamanho, cena)
    visto = medida["visto"]
    esperando = sum(1 for a in cena["aparelhos"] if a.get("esperando"))
    # a régua não passa por vazio: as peças da foto estão na linha
    assert visto["linhas"] == len(cena["lugares"]), visto
    assert visto["esperas"] == esperando and visto["sinos"] >= 1, visto
    assert visto["ensinas"] >= (0 if nome == "dentro-da-maquina" else 1), visto
    assert medida["defeitos"] == [], f"{nome} a {tamanho[0]} px: {medida['defeitos']}"


@skip_sem_gi_real
@pytest.mark.parametrize("tamanho", TAMANHOS, ids=lambda t: f"{t[0]}px")
@pytest.mark.parametrize("nome", sorted(CENAS))
def test_a_linha_do_adaptador_cabe_no_desenho(nome: str, tamanho: tuple[int, int]) -> None:
    _conferir(DESENHO, tamanho, nome)


@skip_sem_gi_real
@pytest.mark.parametrize("tamanho", TAMANHOS, ids=lambda t: f"{t[0]}px")
def test_a_linha_do_adaptador_cabe_na_pagina_publicada(tamanho: tuple[int, int]) -> None:
    if MARCA_DA_CURA not in PUBLICADA.read_text(encoding="utf-8"):
        pytest.skip("o publicado da 08 ainda é o de antes; o `--publicar` é da costura")
    _conferir(PUBLICADA, tamanho, "a-foto-dela")


@skip_sem_gi_real
def test_o_onde_fica_abre_o_mapear_entrada_a_entrada() -> None:
    lidas = _no_webkit(DESENHO, TAMANHOS[0], [
        _clicar('label[for="cx8-3"]'), _pintar_a_sala(_cena_da_foto()),
        _clicar(".radio .sala .lugar-topo .ensina"), "location.hash"])
    assert lidas[2] == "clicou", lidas
    assert lidas[-1] == "#mapear-entrada-a-entrada", lidas


def _grade_da_sala(texto: str, prefixo: str) -> str:
    import re

    achou = re.search(prefixo + r"\.sala\{[^}]*?grid-template-columns:([^;}]+)", texto)
    assert achou, f"sem a grade da sala ({prefixo or 'sem prefixo'})"
    return " ".join(achou.group(1).split())


def test_o_desenho_do_radio_tem_a_mesma_grade_da_08() -> None:
    """O `mapa-do-radio` é o desenho de onde a 08 tira a sala: a grade dos dois é a mesma."""
    gerador = (RAIZ / "src/hefesto_dualsense4unix/interface/aba08.py").read_text(encoding="utf-8")
    radio = (RAIZ / "mockup" / "mapa-do-radio.html").read_text(encoding="utf-8")
    assert MARCA_DA_CURA in _grade_da_sala(gerador, r"\.radio ")
    assert _grade_da_sala(radio, r"\n") == _grade_da_sala(gerador, r"\.radio ")
    assert "grid-template-columns:subgrid" in radio, "a caixa do adaptador não herda a grade"
