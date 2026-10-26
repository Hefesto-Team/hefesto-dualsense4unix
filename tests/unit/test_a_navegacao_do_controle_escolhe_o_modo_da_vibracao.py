"""A navegação do controle escolhe o modo da vibração.

A-NAVEGACAO-DO-CONTROLE-ESCOLHE-O-MODO-DA-VIBRACAO-01.

A queixa (22/10/2026): «o modo de vibração eu não consigo selecionar usando a navegação interna
do controle». Medido no piloto, em lar de mentira, com os quatro controles: sentado na lista, o X,
o ↓ e o X trocam a opção e ela fica depois dos tiques (o gesto chega ao daemon e a pintura não a
devolve). O que falhava era CHEGAR à lista: descendo a coluna dos interruptores, o ↓ do interruptor
da háptica ia ao do motor esquerdo, e o do motor direito ia ao «Testar», pulando as duas listas
que moram logo abaixo deles. A lista começa na mesma borda que o interruptor e é larga; o centro
dela fica longe do dele, e o `vizinho` contava o desvio de centro a centro.

Dois contratos, medidos no Chrome sobre os DESENHOS (`mockup/`):

1. Na 05, de cada um dos quatro controles: do interruptor logo acima, o ↓ chega à lista, e o X,
   o ↓ e o X trocam a opção do «Padrão dos motores» e do «Efeito háptico» DAQUELE controle, com o
   `change` dizendo o assento e o valor (a porta pela qual o gesto vai ao daemon).
2. Em toda página, para todo controle: o direcional nunca pula uma caixa que está na frente, na
   faixa de quem está selecionado (uma caixa entre a de agora e a escolhida, que a cobre no outro
   eixo).

MORDIDA: o `vizinho` de antes (o desvio de centro a centro) reprova os dois.
"""

from __future__ import annotations

import json
import pathlib
import sys
from collections.abc import Iterator
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
for _caminho in (str(RAIZ / "src"), str(RAIZ / "scripts")):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import chrome_sem_rede

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as padroes
from hefesto_dualsense4unix.interface import hefesto_vivo
from hefesto_dualsense4unix.interface import navegacao_interna as nav

CHROME = pathlib.Path("/usr/bin/google-chrome")
MOCKUP = RAIZ / "mockup"
LARGURA, ALTURA = 1212, 809
ASSENTOS = ("p1", "p2", "p3", "p4")
UNIQ = {p: f"aa:bb:cc:00:00:0{n}" for n, p in enumerate(ASSENTOS, start=1)}
LISTAS = (
    ("imersao-escolha", "lado-d", "efeito-imersao"),
    ("haptico-escolha", "lado-h", "efeito-haptico"),
)

QUATRO_NA_MESA = r"""() => {
  for (const p of ['p1','p2','p3','p4']) {
    for (const el of document.querySelectorAll('[data-controle="' + p + '"]')) {
      el.dataset.conectado = 'sim';
      el.classList.remove('off');
    }
  }
}"""

DONO = '[data-controle="p1"],[data-controle="p2"],[data-controle="p3"],[data-controle="p4"]'

OUVIR_O_CHANGE = r"""() => {
  window.__mudancas = [];
  document.addEventListener('change', function(ev){
    const el = ev.target;
    const dono = el.closest('DONO');
    window.__mudancas.push({controle: dono ? dono.dataset.controle : '',
                            gesto: el.dataset.gesto || '', valor: el.value});
  }, true);
}""".replace("DONO", DONO)

LER_AS_LISTAS = r"""() => {
  const fora = {};
  for (const s of document.querySelectorAll('select[data-gesto]')) {
    const dono = s.closest('DONO');
    if (dono) fora[dono.dataset.controle + '|' + s.dataset.gesto] = s.value;
    if (dono) fora[dono.dataset.controle + '|' + s.dataset.gesto + '|seguinte'] =
      (s.options[s.selectedIndex + 1] || {}).value || '';
  }
  return fora;
}""".replace("DONO", DONO)


@pytest.fixture(scope="module")
def navegador() -> Iterator[Any]:
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as pw:
        motor = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            yield motor
        finally:
            motor.close()


def _abrir(navegador: Any, arquivo: pathlib.Path) -> Any:
    pg, _ = chrome_sem_rede.abrir_sem_rede(
        navegador, arquivo.as_uri(), largura=LARGURA, altura=ALTURA)
    pg.evaluate(hefesto_vivo.NAV_INSTALAR)
    return pg


def _leiaute(pg: Any) -> dict[str, Any]:
    return dict(json.loads(pg.evaluate("window.__hefNav.ler()")))


def _endereco(caixas: list[nav.Caixa], pref: str, campo: str) -> nav.Caixa:
    achadas = [c for c in caixas if c.endereco.startswith(pref + "|")
               and c.endereco.split("|")[2] == campo]
    assert achadas, f"{pref}: a caixa de campo {campo!r} não está entre as que ele seleciona"
    return achadas[0]


def _toques(**contas: int) -> dict[str, int]:
    nomes = ("x", "o", "cima", "baixo", "esquerda", "direita")
    return {nome: contas.get(nome, 0) for nome in nomes}


def test_na_05_cada_controle_chega_a_lista_e_troca_a_opcao(navegador: Any) -> None:
    pg = _abrir(navegador, MOCKUP / "05-vibracao.html")
    try:
        pg.evaluate(QUATRO_NA_MESA)
        pg.evaluate(OUVIR_O_CHANGE)
        antes = pg.evaluate(LER_AS_LISTAS)
        pref_de = {UNIQ[p]: p for p in ASSENTOS}
        falhas: list[str] = []
        for pref in ASSENTOS:
            uniq = UNIQ[pref]
            for campo, interruptor, gesto in LISTAS:
                leiaute = _leiaute(pg)

                def caixas_de(u: str, lei: dict[str, Any] = leiaute) -> list[nav.Caixa]:
                    return nav.caixas_do_leiaute(lei, pref_de.get(u, ""))

                caixas = caixas_de(uniq)
                lista = _endereco(caixas, pref, campo)
                de_cima = _endereco(caixas, pref, interruptor)
                selecoes = nav.Selecoes()
                navegador_ = nav.Navegador(relogio=lambda: 0.0)
                navegador_.atos(pagina="05-vibracao.html", dez=["05-vibracao.html"],
                                toques={uniq: _toques()}, ativa=True)
                selecoes.aplicar([nav.Ato("dedo", uniq=uniq, ponto=de_cima.centro)], caixas_de,
                                 pref_de=pref_de, popup=False)
                ops: list[dict[str, Any]] = []
                contas = _toques()
                for tecla in ("baixo", "x", "baixo", "x"):
                    contas = {**contas, tecla: contas[tecla] + 1}
                    atos = navegador_.atos(pagina="05-vibracao.html",
                                           dez=["05-vibracao.html"],
                                           toques={uniq: contas}, ativa=True)
                    ops += selecoes.aplicar(atos, caixas_de, pref_de=pref_de, popup=False)
                    if tecla == "baixo" and not selecoes.dentro(uniq) and \
                            selecoes.de(uniq) != lista.endereco:
                        falhas.append(f"{pref}: o ↓ do interruptor {interruptor} foi a "
                                      f"{selecoes.de(uniq)!r}, pulando a lista {lista.endereco!r}")
                        break
                pg.evaluate("(ops) => window.__hefNav.aplicar(ops, [])", ops)
                valor = pg.evaluate(LER_AS_LISTAS).get(f"{pref}|{gesto}")
                if valor == antes.get(f"{pref}|{gesto}"):
                    falhas.append(f"{pref}: o X, o ↓ e o X não trocaram a lista {gesto} "
                                  f"(ficou {valor!r}; ops {ops})")
        assert not falhas, "\n".join(falhas)
        depois = pg.evaluate(LER_AS_LISTAS)
        mudancas = pg.evaluate("() => window.__mudancas")
    finally:
        pg.close()
    esperadas = sorted((p, g, antes[f"{p}|{g}|seguinte"]) for p in ASSENTOS for _c, _i, g in LISTAS)
    assert all(v for *_r, v in esperadas), f"lista sem opção seguinte: {esperadas}"
    assert {antes["p1|efeito-imersao|seguinte"]} <= set(padroes.ESCOLHAS)
    assert sorted((m["controle"], m["gesto"], m["valor"]) for m in mudancas) == esperadas, (
        f"o `change` não disse o assento e o valor de cada lista: {mudancas}")
    for chave, valor in depois.items():
        if chave.split("|")[1] not in {g for _c, _i, g in LISTAS} and "|seguinte" not in chave:
            assert valor == antes[chave], f"{chave} mudou sem ninguém escolher"


def _frente_e_faixa(a: nav.Caixa, b: nav.Caixa, direcao: str) -> tuple[float, bool]:
    """Quanto ``b`` está à frente de ``a`` (de centro a centro) e se cobre a faixa de ``a``."""
    (ax, ay), (bx, by) = a.centro, b.centro
    if direcao in ("cima", "baixo"):
        frente = (by - ay) if direcao == "baixo" else (ay - by)
        cobre = b.x < a.x + a.largura and a.x < b.x + b.largura
    else:
        frente = (bx - ax) if direcao == "direita" else (ax - bx)
        cobre = b.y < a.y + a.altura and a.y < b.y + b.altura
    return frente, cobre


def _paginas() -> list[pathlib.Path]:
    return sorted(p for p in MOCKUP.glob("*.html")
                  if 'id="base-comum"' in p.read_text(encoding="utf-8"))


def test_o_direcional_nunca_pula_a_caixa_da_frente(navegador: Any) -> None:
    """Prova da D-2210-O-DIRECIONAL-NAO-PULA-A-CAIXA-DA-FRENTE."""
    pulos: list[str] = []
    for pagina in _paginas():
        pg = _abrir(navegador, pagina)
        try:
            leiaute = _leiaute(pg)
        finally:
            pg.close()
        for pref in ("", *ASSENTOS):
            caixas = nav.caixas_do_leiaute(leiaute, pref)
            for i, a in enumerate(caixas):
                for direcao in nav.DIRECOES:
                    j = nav.vizinho(caixas, i, direcao)
                    if j is None:
                        continue
                    frente_escolhida, _ = _frente_e_faixa(a, caixas[j], direcao)
                    for k, b in enumerate(caixas):
                        frente, cobre = _frente_e_faixa(a, b, direcao)
                        if k not in (i, j) and cobre and 0.5 < frente < frente_escolhida - 0.5:
                            pulos.append(f"{pagina.name} [{pref or '-'}] {a.endereco} "
                                         f"{direcao} → {caixas[j].endereco}, pulando "
                                         f"{b.endereco}")
                            break
    assert not pulos, f"{len(pulos)} pulos:\n" + "\n".join(sorted(set(pulos))[:40])
