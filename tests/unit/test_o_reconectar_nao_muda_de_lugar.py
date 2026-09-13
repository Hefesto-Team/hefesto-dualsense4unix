#!/usr/bin/env python3
"""O «Reconectar controles» fica onde está — JOGAR-A-FAIXA-QUE-PULA-01.

13/09/2026, 02:48. Duas fotos dela da aba Jogar, no mesmo minuto:

    *"botoes que mudam de lugar direto."*  # noqa-acento: citação literal dela

O QUE O PILOTO MEDIU ANTES DA CURA (WebKit, oculto, 1212/1228/1282/1300 de
largura): parado por 60 s o botão não se move, e acender ou apagar a pendência
também não. O que o movia era o recibo do Reconectar pousando na `.faixa-final`
vestido de `.pendente` — 223 px para a esquerda com a frase curta, 301 com a
longa, e até a outra ponta com três frases —, e INVISÍVEL, porque a faixa sem
`.ha` esconde tudo o que veste `.pendente`.

AS TRÊS METADES, e cada uma morde sozinha:

1. **A página** — a faixa não declara lugar de recado. Era o nó que empurrava.
2. **O layout** — no Chrome headless, nas larguras das duas fotos, o botão não
   sai do lugar em nenhuma cena que o piloto produz nem quando um vizinho de
   texto longo entra na fileira: uma linha, colado à direita, x e y iguais.
   Quem prova no motor dela (WebKit) é o piloto, e a tabela está na entrega.
3. **O pacote** — as duas frases desta aba não chegam à tela: a ressalva da
   máscara e a pendência saem vazias, e a pendência vai ao diário da janela.

E O §3.2 DA SPRINT, medido em dublê e no código (não no aparelho): o chip Xbox
pede com `origin="manual"`, a trava de jogo aberto não segura essa origem, e o
chip acende o `flavor` que o daemon grava. É o que autoriza a faixa a apagar.

AS MORDIDAS, aplicadas e com a saída na entrega:

* devolva o `recibo-do-reconectar` com `data-hef-recados="sucesso"` ao MIOLO de
  `aba01.py`, regere e publique — a metade 1 reprova;
* tire as três regras `.faixa-final …` que a sprint escreveu no CSS de
  `aba01.py` — a cena «um vizinho longo entra na fileira» reprova;
* devolva `return RESSALVA_DA_MASCARA` em `_ressalva_da_mascara`, ou a `frase`
  no `"pendente"` do `pacote()` — a metade 3 reprova.

E O PULO VERTICAL — RECONECTAR-SAMBA-02, 13/09/2026. A queixa voltou no índice
da terceira lista dela:

    *"reconectar c ontroles segue dando pau,. falo do posicionamento e formato
    dele. ele segue sambando."*

Com a fileira à prova de vizinho, o que ainda movia o botão era o ESTADO. No
piloto oculto (WebKit, vista de 1212x809), antes da cura:

* **o tique em que o serviço não responde a tempo** pintava `{}`: os quatro
  lugares apagavam, o chip do lugar vazio saía do fluxo, o cartão caía de 128
  para 67 px e o botão subia 61 px (y 463 → 402), voltando no tique seguinte;
* **a lista de controles vazia** acendia a frase da mesa NO FLUXO, acima dos
  cartões, e o saldo era de 34 px para cima (463 → 429).

AS TRÊS CURAS, e cada uma morde sozinha:

4. **o chip do lugar vazio guarda o vão** — volte a regra dele em `aba01.py`
   para `display:none`, regere e publique: as cenas dos lugares apagados e o
   clique no chip escondido reprovam;
5. **a frase da mesa pousa por cima dos lugares apagados**, fora do fluxo — tire o
   `position:absolute` de `.mesa-notas`: a cena da lista vazia reprova, com o
   botão 26 px abaixo e a frase fora da fileira;
6. **o tique mudo repinta o último estado bom por uma folga medida**
   (`hefesto_vivo.FolgaDoServicoMudo`) — troque `st = self._folga.mudo(e)` por
   `st = {}` no `_tique`: a régua do WebKit reprova com os lugares apagados
   dentro da folga;
7. **por cima SÓ dos lugares apagados** — achado da validação: tire o
   `:not(:has(…))` das duas regras de `.mesa-notas` em `aba01.py`, regere e
   publique: a frase do quinto controle cobre o chip da máscara de dois cartões
   cheios, e a régua dela reprova.
"""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

CHROME = pathlib.Path("/usr/bin/google-chrome")

#: As larguras das duas fotos dela: ≈1228 e ≈1300 com a moldura do COSMIC.
LARGURAS = (1228, 1300)

#: Três frases REAIS do produto coladas — um dublê de COMPRIMENTO, e não uma
#: frase de tela: é o tamanho que levou o botão à outra ponta no piloto.
TRES_FRASES = ("Os controles foram renumerados: P1, P2, P3 e P4. "
               "Não consegui conferir a numeração dos controles. "
               "Não consegui ajustar a numeração dos controles.")

VIVO_DUALSENSE: dict[str, Any] = {
    "connected": True, "native_mode": False, "paused": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense", "backend": "uhid"},
}
#: AJUSTADO À REGRA DELA — MODO-DE-CONEXAO-01, 13/09/2026: o daemon publica o
#: CAMINHO, e é por ele que o chip de modo acende. O `backend` `uhid` do estado
#: DualSense já responde por si; o `uinput` sozinho não separa o Xbox escolhido
#: do DualSense degradado, e por isso o estado Xbox traz o campo.
VIVO_XBOX: dict[str, Any] = {
    "connected": True, "native_mode": False, "paused": False,
    "gamepad_emulation": {"enabled": True, "flavor": "xbox", "backend": "uinput",
                          "caminho": "xbox"},
}
VIVO_NATIVO: dict[str, Any] = {
    "connected": True, "native_mode": True, "paused": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
}
VIVO_NAVEGACAO: dict[str, Any] = {
    "connected": True, "native_mode": False, "paused": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
}


class PonteDeMentira:
    """Aceita qualquer método e guarda o que foi pedido. Não abre socket."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def chamar(self, metodo: str, **params: Any) -> bool:
        self.chamadas.append((metodo, params))
        return True


@pytest.fixture(autouse=True)
def _memoria_limpa(monkeypatch: pytest.MonkeyPatch) -> Any:
    """A escolha e o último relato são de MÓDULO — sem isto um teste suja o outro."""
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()
    monkeypatch.setattr(aba, "_PENDENCIA_RELATADA", "")
    yield
    aba._ESCOLHA.clear()
    aba._ROTULO.clear()


def _ctx(state: dict[str, Any]) -> Contexto:
    return Contexto(state=state, mesa=[], conectados=[], estados={})


# ---------------------------------------------------------------------------
# 1. A PÁGINA — a faixa não tem onde pousar recado
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("publicado", [False, True], ids=["bancada", "publicado"])
def test_a_faixa_final_nao_declara_lugar_de_recado(publicado: bool) -> None:
    """O nó que empurrava o botão, nos DOIS lados.

    O piloto pousa o recado de sucesso no primeiro `[data-hef-recados~=…]` que
    a página declara (`hefesto_vivo.BOOTSTRAP`, `pintar_recados`). Na 01 esse
    lugar era um irmão do botão dentro da `.faixa-final`, e crescia com a frase.
    Olhar só a bancada daria verde com o produto dela ainda empurrando.
    """
    corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(encoding="utf-8")
    assert "data-hef-recados=" not in corpo, (
        "a 01 voltou a declarar um lugar de recado: o recibo volta a entrar na "
        "fileira do Reconectar e a empurrá-lo")
    assert 'class="recibo-do-reconectar"' not in corpo


# ---------------------------------------------------------------------------
# 2. O LAYOUT — o botão não muda de lugar em cena nenhuma
# ---------------------------------------------------------------------------
#: A MEDIDA. `direita` é o que sobra entre a borda direita do botão e a do
#: conteúdo da faixa; `linhas` conta as caixas de linha do texto do botão.
MEDIR = """() => {
  const f = document.querySelector('.faixa-final');
  const b = document.querySelector('[data-gesto="reconectar"]');
  if (!f || !b) return {erro: 'sem .faixa-final ou sem o botão'};
  const cf = getComputedStyle(f);
  const rf = f.getBoundingClientRect(), rb = b.getBoundingClientRect();
  const borda = rf.right - parseFloat(cf.paddingRight) - parseFloat(cf.borderRightWidth);
  const rg = document.createRange();
  rg.selectNodeContents(b);
  const tops = new Set(Array.from(rg.getClientRects()).map(r => Math.round(r.top)));
  return {x: rb.left, y: rb.top, direita: borda - rb.right, linhas: tops.size};
}"""

#: AS CENAS — cada uma é o que o piloto ou a folha da casa fazem com a fileira.
#: O argumento chega como `a` e só as que precisam o leem.
CENAS: tuple[tuple[str, str], ...] = (
    ("a página como nasce", "(a) => 0"),
    ("a faixa apaga (sai o .ha)",
     "(a) => { document.querySelector('.faixa-final').classList.remove('ha'); return 0; }"),
    ("o piloto escreve o travessão na pendência",
     "(a) => { document.querySelector('[data-campo=\"pendente\"]').textContent = '\\u2014';"
     " document.querySelector('.faixa-final').classList.remove('ha'); return 0; }"),
    ("a frase do produto acende",
     "(a) => { document.querySelector('[data-campo=\"pendente\"]').textContent = a.frase;"
     " document.querySelector('.faixa-final').classList.add('ha'); return 0; }"),
    # O MESMO CAMINHO DO `pintar_recados`: o recado entra DENTRO do lugar que a
    # página declara, vestido das classes que ela pede.
    ("o piloto pousa o recibo de sucesso",
     "(a) => { const f = document.querySelector('[data-hef-recados~=\"sucesso\"]');"
     " if (!f) return 0; const el = document.createElement('div');"
     " el.className = 'hef-recado ' + (f.dataset.hefRecadoClasse || '');"
     " el.style.cssText = 'pointer-events:none;'; el.textContent = a.longa;"
     " f.appendChild(el); return 1; }"),
    ("um vizinho de texto longo entra na fileira",
     "(a) => { const d = document.createElement('div'); d.textContent = a.longa;"
     " document.querySelector('.faixa-final').appendChild(d); return 1; }"),
    ("o botão voa e pousa verde",
     "(a) => { const b = document.querySelector('[data-gesto=\"reconectar\"]');"
     " b.classList.add('hef-em-voo'); b.classList.add('hef-deu-certo'); return 0; }"),
)


@pytest.mark.parametrize("largura", LARGURAS)
def test_o_botao_nao_muda_de_lugar_em_cena_nenhuma(largura: int) -> None:
    """Uma linha, colado à direita, e x e y iguais (±1 px) nas sete cenas.

    NO CHROME, e é declarado: o motor dela é o WebKit, e quem mede lá é o
    piloto (a tabela da entrega). O Chrome headless é o que a suíte alcança sem
    abrir janela nenhuma — a mesma escolha de `olhar.py`.
    """
    if not CHROME.exists():
        pytest.skip("sem /usr/bin/google-chrome: o layout não se mede sem motor")
    sync_api = pytest.importorskip("playwright.sync_api")
    from hefesto_dualsense4unix.app.actions.relancar import texto_do_pendente
    from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA

    frase = texto_do_pendente(mascara="Xbox")
    argumento = {"frase": frase[:2] + frase[2:3].upper() + frase[3:], "longa": TRES_FRASES}
    pagina = onde.pagina("01-jogar.html", publicado=True).as_uri()

    medidas: list[tuple[str, dict[str, Any]]] = []
    with sync_api.sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            for nome, cena in CENAS:
                pg = nav.new_page(viewport={"width": largura, "height": 900},
                                  device_scale_factor=1)
                try:
                    pg.goto(pagina)
                    pg.wait_for_load_state("networkidle")
                    # A FOLHA DO PILOTO, que é o que o produto põe por cima.
                    pg.add_style_tag(content=FOLHA_DA_CASA)
                    pg.evaluate(cena, argumento)
                    pg.wait_for_timeout(50)
                    m = pg.evaluate(MEDIR)
                finally:
                    pg.close()
                assert "erro" not in m, f"{largura}px · {nome}: {m.get('erro')}"
                medidas.append((nome, m))
        finally:
            nav.close()

    _, base = medidas[0]
    for nome, m in medidas:
        onde_ = f"{largura}px · {nome}"
        assert m["linhas"] == 1, f"{onde_}: o botão quebrou em {m['linhas']} linhas"
        assert abs(m["direita"]) <= 1, (
            f"{onde_}: o botão não está colado à direita — sobram "
            f"{m['direita']:.1f} px entre ele e a borda da faixa")
        assert abs(m["x"] - base["x"]) <= 1 and abs(m["y"] - base["y"]) <= 1, (
            f"{onde_}: o botão mudou de lugar — x {base['x']:.1f} → {m['x']:.1f}, "
            f"y {base['y']:.1f} → {m['y']:.1f}")


# ---------------------------------------------------------------------------
# 4. O ESTADO — os lugares apagam e o botão fica (RECONECTAR-SAMBA-02)
# ---------------------------------------------------------------------------
#: O VALOR DO ATRIBUTO que o piloto escreve num lugar sem controle (o passo `1b`
#: do BOOTSTRAP). Vai às cenas como argumento, para nenhuma o digitar.
LUGAR_VAZIO = "nao"  # noqa-acento: valor do atributo `data-conectado`, não a palavra

#: O QUE O PILOTO FAZ COM A FILEIRA quando o tique pinta `{}` (os quatro lugares
#: viram vazios) e quando a lista de controles chega vazia (o mesmo, e a frase
#: da mesa acende).
APAGAR_OS_QUATRO = ("for (const el of document.querySelectorAll('[data-controle]'))"
                    " { el.dataset.conectado = a.vazio; el.classList.add('off'); }")
ACENDER_A_FRASE = ("document.querySelector('.mesa-notas[data-campo=\"mesa-frase\"]')"
                   ".classList.add('ha');")
CENAS_DO_ESTADO: tuple[tuple[str, str], ...] = (
    ("o serviço não respondeu: os quatro lugares apagam",
     "(a) => { " + APAGAR_OS_QUATRO + " return 0; }"),
    ("a lista vem vazia: os lugares apagam e a frase da mesa acende",
     "(a) => { " + APAGAR_OS_QUATRO + " " + ACENDER_A_FRASE + " return 0; }"),
)

#: A TOLERÂNCIA DAS CENAS DO ESTADO, declarada: com os quatro lugares vazios o
#: cartão mede 1 px a menos (128 em vez de 129 no Chrome). Não é o botão
#: andando — com a cura arrancada ele anda 61.
TOLERANCIA_DO_ESTADO = 2

#: A MEDIDA DAS CENAS DO ESTADO: a do botão, mais a caixa da frase da mesa e a
#: da fileira. Sem as duas, esconder a frase passaria por pousá-la por cima.
MEDIR_O_ESTADO = """() => {
  const f = document.querySelector('.faixa-final');
  const b = document.querySelector('[data-gesto="reconectar"]');
  const n = document.querySelector('.mesa-notas[data-campo="mesa-frase"]');
  const p = document.querySelector('.pecas');
  if (!f || !b || !n || !p) return {erro: 'sem .faixa-final, botão, frase da mesa ou .pecas'};
  const cf = getComputedStyle(f);
  const rf = f.getBoundingClientRect(), rb = b.getBoundingClientRect();
  const rn = n.getBoundingClientRect(), rp = p.getBoundingClientRect();
  const borda = rf.right - parseFloat(cf.paddingRight) - parseFloat(cf.borderRightWidth);
  const rg = document.createRange();
  rg.selectNodeContents(b);
  const tops = new Set(Array.from(rg.getClientRects()).map(r => Math.round(r.top)));
  return {x: rb.left, y: rb.top, direita: borda - rb.right, linhas: tops.size,
          frase: {altura: rn.height, meio: rn.top + rn.height / 2},
          fileira: {topo: rp.top, base: rp.bottom}};
}"""

#: O CLIQUE NO CHIP ESCONDIDO: quem recebe um clique no centro de cada chip dos
#: lugares apagados. É o ponto que um clique de verdade alcança, e a caixa vem
#: junto — um chip sem altura não tem centro a clicar, e a régua mediria nada.
CLIQUE_NO_CHIP_ESCONDIDO = "(a) => { " + APAGAR_OS_QUATRO + """
  const saida = [];
  for (const chip of document.querySelectorAll('[data-controle] .mascara .chip')) {
    const r = chip.getBoundingClientRect();
    const em = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    saida.push({lugar: chip.closest('[data-controle]').dataset.controle,
                rotulo: chip.textContent.trim(), altura: r.height,
                pega: !!em && (em === chip || chip.contains(em)),
                no_ponto: em ? em.tagName + '.' + em.className : ''});
  }
  return saida;
}"""

#: A MESMA LINHA COM MAIS CONTROLES QUE LUGARES: os quatro cheios e a frase do
#: quinto acesa, com o texto que o pacote escreve. Devolve o que ela cobre de
#: clicável e visível num cartão cheio.
O_QUE_A_FRASE_DO_QUINTO_COBRE = "(a) => { " + (
    "for (const el of document.querySelectorAll('.pecas [data-controle]'))"
    " { el.dataset.conectado = 'sim'; el.classList.remove('off'); } "
) + ACENDER_A_FRASE + """
  const s = document.querySelector('.mesa-notas[data-campo="mesa-frase"] .mesa-nota');
  s.textContent = a.frase;
  const r = s.getBoundingClientRect();
  const cobre = [];
  for (const g of document.querySelectorAll('.pecas [data-controle] [data-gesto]')) {
    const rg = g.getBoundingClientRect();
    if (getComputedStyle(g).visibility === 'hidden' || !rg.width || !rg.height) continue;
    if (rg.left < r.right && r.left < rg.right && rg.top < r.bottom && r.top < rg.bottom)
      cobre.push(g.closest('[data-controle]').dataset.controle + ' · `' + g.dataset.gesto
                 + '` ("' + g.textContent.trim().slice(0, 20) + '")');
  }
  return {altura: r.height, cobre: cobre};
}"""


def _medir_no_chrome(largura: int, cenas: tuple[tuple[str, str], ...],
                     argumento: dict[str, Any], medir: str) -> list[tuple[str, Any]]:
    """Uma página publicada por cena, com a folha do piloto por cima, e a medida."""
    if not CHROME.exists():
        pytest.skip("sem /usr/bin/google-chrome: o layout não se mede sem motor")
    sync_api = pytest.importorskip("playwright.sync_api")
    from hefesto_dualsense4unix.interface.folha_da_casa import FOLHA_DA_CASA

    pagina = onde.pagina("01-jogar.html", publicado=True).as_uri()
    medidas: list[tuple[str, Any]] = []
    with sync_api.sync_playwright() as pw:
        nav = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            for nome, cena in cenas:
                pg = nav.new_page(viewport={"width": largura, "height": 900},
                                  device_scale_factor=1)
                try:
                    pg.goto(pagina)
                    pg.wait_for_load_state("networkidle")
                    pg.add_style_tag(content=FOLHA_DA_CASA)
                    pg.evaluate(cena, argumento)
                    pg.wait_for_timeout(50)
                    medidas.append((nome, pg.evaluate(medir, argumento)))
                finally:
                    pg.close()
        finally:
            nav.close()
    return medidas


@pytest.mark.parametrize("largura", LARGURAS)
def test_o_botao_nao_muda_de_lugar_quando_o_estado_apaga_os_lugares(largura: int) -> None:
    """As duas cenas do estado contra a página como nasce.

    NO CHROME, ANTES DA CURA, na página publicada: com os quatro lugares
    apagados o botão subia 61 px (o chip do lugar vazio saía do fluxo e o
    cartão caía de 129 para 68 px); com a lista vazia a frase entrava acima dos
    cartões, e o saldo era de 34 px para cima. Com a cura, 1 px nas duas.

    A FRASE TEM DE ESTAR LÁ, e sobre a fileira: sem esta metade, sumir com ela
    passaria nesta régua como se fosse a cura.
    """
    medidas = _medir_no_chrome(
        largura, (("a página como nasce", "(a) => 0"), *CENAS_DO_ESTADO),
        {"vazio": LUGAR_VAZIO}, MEDIR_O_ESTADO)
    _, base = medidas[0]
    assert "erro" not in base, f"{largura}px: {base.get('erro')}"
    for nome, m in medidas[1:]:
        onde_ = f"{largura}px · {nome}"
        assert "erro" not in m, f"{onde_}: {m.get('erro')}"
        assert m["linhas"] == 1, f"{onde_}: o botão quebrou em {m['linhas']} linhas"
        assert abs(m["direita"]) <= 1, (
            f"{onde_}: o botão descolou da direita — sobram {m['direita']:.1f} px")
        dy = m["y"] - base["y"]
        assert abs(m["x"] - base["x"]) <= 1 and abs(dy) <= TOLERANCIA_DO_ESTADO, (
            f"{onde_}: o botão {'subiu' if dy < 0 else 'desceu'} {abs(dy):.0f} px — "
            f"y {base['y']:.1f} → {m['y']:.1f}, x {base['x']:.1f} → {m['x']:.1f}")

    _, acesa = medidas[2]
    assert acesa["frase"]["altura"] > 0, (
        f"{largura}px: a frase da mesa acendeu sem caixa — sumir com ela não é "
        f"pousá-la por cima dos lugares")
    fileira, meio = acesa["fileira"], acesa["frase"]["meio"]
    assert fileira["topo"] <= meio <= fileira["base"], (
        f"{largura}px: a frase da mesa não está por cima dos lugares — o meio "
        f"dela em y {meio:.1f}, a fileira de {fileira['topo']:.1f} a "
        f"{fileira['base']:.1f}")


def test_o_clique_no_chip_escondido_nao_devolve_o_chip() -> None:
    """O lugar apagado guarda o vão do chip, e o clique no centro dele cai fora.

    AS DUAS METADES, e cada uma pega uma cura torta diferente: o chip TEM altura
    (sem ela a fileira volta a cair, e o `elementFromPoint` num ponto sem caixa
    não mede nada), e o ponto NÃO É o chip (senão o lugar sem controle voltou a
    oferecer a escolha — a decisão de 31/08 citada em `aba01.py`).
    """
    [(_, chips)] = _medir_no_chrome(
        LARGURAS[0], (("os quatro lugares apagam", "(a) => 0"),),
        {"vazio": LUGAR_VAZIO}, CLIQUE_NO_CHIP_ESCONDIDO)
    assert {c["lugar"] for c in chips} == {"p1", "p2", "p3", "p4"}, chips
    sem_vao = [f'{c["lugar"]} · {c["rotulo"]}' for c in chips if c["altura"] <= 0]
    assert not sem_vao, (
        "o chip do lugar vazio saiu do fluxo de novo — a fileira volta a cair e "
        "o botão sobe: " + ", ".join(sem_vao))
    pegam = [f'{c["lugar"]} · {c["rotulo"]} ({c["no_ponto"]})' for c in chips if c["pega"]]
    assert not pegam, (
        "o clique no centro do chip escondido DEVOLVE o chip — um lugar sem "
        "controle voltou a oferecer a escolha: " + ", ".join(pegam))


@pytest.mark.parametrize("largura", LARGURAS)
def test_a_frase_do_quinto_controle_nao_cobre_cartao_cheio(largura: int) -> None:
    """Com mais controles que lugares a frase acende sobre quatro cartões CHEIOS.

    POR CIMA DELES, ELA COBRIA A MÁSCARA — achado da validação desta sprint, em
    13/09/2026: no Chrome a 1228 e 1300, e no piloto oculto, a frase do quinto
    controle pousava sobre o chip «DualSense» do P2 e do P3, e o clique nela
    caía nesse chip. Por cima só dos lugares apagados; com um lugar cheio, a
    linha fica acima da fileira.

    A FRASE É A DO DONO (`a01_jogar._frase_da_mesa`, com cinco controles): um
    texto digitado aqui mediria a caixa de outra frase.
    """
    cinco = [{"uniq": f"aa:bb:cc:00:00:0{n}", "connected": True} for n in range(1, 6)]
    frase = aba._frase_da_mesa(Contexto(state={**VIVO_DUALSENSE, "controllers": cinco},
                                        mesa=[], conectados=cinco, estados={}))
    assert frase, "com cinco controles o pacote não escreveu a frase — a régua mediria nada"
    [(_, m)] = _medir_no_chrome(
        largura, (("os quatro cheios e a frase do quinto", "(a) => 0"),),
        {"frase": frase}, O_QUE_A_FRASE_DO_QUINTO_COBRE)
    assert m["altura"] > 0, f"{largura}px: a frase do quinto não acendeu — a régua mediria nada"
    assert not m["cobre"], (
        f"{largura}px: a frase do quinto controle cobre o que se clica num cartão "
        f"cheio — " + ", ".join(m["cobre"]))


# ---------------------------------------------------------------------------
# 3. O PACOTE — as duas frases desta aba não chegam à tela
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("estado", [VIVO_NATIVO, VIVO_NAVEGACAO, VIVO_DUALSENSE, {}],
                         ids=["nativo", "navegacao", "jogo", "sem-daemon"])
def test_a_ressalva_da_mascara_nao_chega_a_tela(estado: dict[str, Any]) -> None:
    """§3.1: em modo nenhum — e era no Nativo e na Navegação que ela era pintada."""
    assert aba.pacote(_ctx(estado))["mascara-ressalva"] == ""


def test_a_pendencia_nao_acende_a_faixa_e_vai_ao_diario(
        capsys: pytest.CaptureFixture[str]) -> None:
    """§3.2: o daemon ainda não alcançou o Xbox — a dona sabe, a tela não fala.

    AS TRÊS METADES, e cada uma pega uma cura torta diferente: os três
    endereços vazios (a faixa não acende); a dona ainda medindo (sem ela a
    pendência some do diário também); e UMA linha no diário por mudança, não
    dez por segundo.
    """
    aba.modo_xbox(_ctx(VIVO_DUALSENSE), {"texto": "Xbox"}, PonteDeMentira())
    capsys.readouterr()

    fora = aba.pacote(_ctx(VIVO_DUALSENSE))
    for campo in ("pendente", "pendente-alvo", "pendente-ha"):
        assert fora[campo] == "", f"a faixa voltou a falar: {campo}={fora[campo]!r}"
    assert aba._faixa_do_pendente(VIVO_DUALSENSE)[1] == "Xbox", (
        "a dona da pendência parou de medir — o diário ficaria mudo junto")

    primeira = capsys.readouterr().err
    assert primeira.count("[relato] 01-jogar.html · pendente:") == 1
    assert "Xbox" in primeira
    aba.pacote(_ctx(VIVO_DUALSENSE))
    assert "[relato]" not in capsys.readouterr().err, (
        "o diário repetiu a mesma pendência no tique seguinte")


def test_o_chip_xbox_pede_com_origem_manual() -> None:
    """§3.2, primeiro elo: sem `manual` o daemon leria reconciliação e poderia recusar.

    AJUSTADA À REGRA DELA — MODO-DE-CONEXAO-01, 13/09/2026. ANTES conferia que o
    chip pedia `flavor: "xbox"` — a MÁSCARA, que o cartão do controle vencia e
    o daemon respondia `ja_estava`. AGORA confere que ele pede o `caminho`, e a
    origem `manual` continua sendo o elo que esta régua trava.
    """
    plano = aba._plano_do_chip("xbox")
    pedidos = [p for m, p in plano if m == "gamepad.emulation.set"]
    assert pedidos == [{"enabled": True, "origin": "manual", "caminho": "xbox"}], plano


def test_a_trava_do_jogo_aberto_nao_segura_o_gesto_dela() -> None:
    """§3.2, segundo elo: com o jogo na autoridade, só a AUTOMAÇÃO é segurada.

    O dublê sabe recusar — é a mesma trava devolvendo `True` para `profile` — e
    é por isso que o `False` do `manual` diz alguma coisa.
    """
    from hefesto_dualsense4unix.daemon.subsystems import gamepad

    com_jogo = SimpleNamespace(display_authority="game", store=None)
    motivo = "troca_de_mascara:dualsense->xbox"
    assert gamepad._recriacao_bloqueada_por_jogo(
        com_jogo, origin="manual", motivo=motivo) is False
    assert gamepad._recriacao_bloqueada_por_jogo(
        com_jogo, origin="profile", motivo=motivo) is True


def test_o_chip_acende_o_flavor_que_o_daemon_grava() -> None:
    """§3.2, terceiro elo: o chip lê o que o daemon publica, e a pendência some quando chega.

    AJUSTADA À REGRA DELA — MODO-DE-CONEXAO-01, 13/09/2026. ANTES o chip lia o
    `flavor` — a máscara —, e o nome do teste ficou dessa época; AGORA ele lê o
    `caminho` publicado (`painel.caminho_vivo`), e é o estado Xbox com o campo
    que apaga a pendência do clique «Xbox».
    """
    assert aba._estado_da_tela(VIVO_DUALSENSE)["modo-aceso"] == "dualsense"
    assert aba._estado_da_tela(VIVO_XBOX)["modo-aceso"] == "xbox"
    aba.modo_xbox(_ctx(VIVO_DUALSENSE), {"texto": "Xbox"}, PonteDeMentira())
    assert aba._faixa_do_pendente(VIVO_XBOX) == ("", "")


# ---------------------------------------------------------------------------
# 5. O TIQUE MUDO — a folga, sozinha e no piloto de verdade (RECONECTAR-SAMBA-02)
# ---------------------------------------------------------------------------
UNIQ_P1 = "aa:bb:cc:00:00:01"
UNIQ_P2 = "aa:bb:cc:00:00:02"


def _controle(uniq: str, transporte: str, jogador: int) -> dict[str, Any]:
    return {"uniq": uniq, "connected": True, "transport": transporte,
            "player": jogador, "battery": 64, "audio": {"mic_mudo": False}}


ESTADO_COM_DOIS: dict[str, Any] = {
    **VIVO_DUALSENSE, "active_profile": "regua",
    "controllers": [_controle(UNIQ_P1, "usb", 1), _controle(UNIQ_P2, "bt", 2)],
}


def _mudo_por(causa: BaseException) -> Exception:
    """O `DaemonMudo` na forma exata em que `mesa_viva.estado_do_daemon` o levanta."""
    import hefesto_vivo as hv

    try:
        try:
            raise causa
        except BaseException as erro:
            raise hv.mesa_viva.DaemonMudo(str(erro)) from erro
    except hv.mesa_viva.DaemonMudo as mudo:
        return mudo


def test_a_folga_repinta_o_ultimo_estado_bom_e_depois_diz_a_verdade() -> None:
    """Os mudos da folga devolvem o último bom; o seguinte, `{}`, e ele não volta.

    A TERCEIRA METADE é a que impede a cura de virar mentira: depois de a tela
    dizer que o serviço calou, um mudo a mais não ressuscita o estado velho.
    Só uma resposta nova o traz.
    """
    import hefesto_vivo as hv

    folga = hv.FolgaDoServicoMudo()
    assert folga.folga == hv.MUDOS_SEGUIDOS_QUE_VOLTARAM >= 1
    folga.respondeu(ESTADO_COM_DOIS)
    for vez in range(1, folga.folga + 1):
        assert folga.mudo(_mudo_por(TimeoutError("timed out"))) is ESTADO_COM_DOIS, (
            f"o {vez}º tique mudo seguido já apagou os lugares — a folga não segurou")
    assert folga.mudo(_mudo_por(TimeoutError("timed out"))) == {}, (
        "passou da folga e a tela continuou afirmando os controles de antes")
    assert folga.mudo(_mudo_por(TimeoutError("timed out"))) == {}, (
        "a tela já tinha dito que o serviço calou, e o estado velho voltou")
    folga.respondeu(ESTADO_COM_DOIS)
    assert folga.mudo(TimeoutError("timed out")) is ESTADO_COM_DOIS, (
        "o `TimeoutError` direto, que é como um dublê o levanta, ficou sem folga")


@pytest.mark.parametrize("causa", [
    FileNotFoundError(2, "Arquivo ou diretório inexistente"),
    ConnectionResetError(104, "Conexão fechada pela outra ponta"),
    ConnectionRefusedError(111, "Conexão recusada"),
], ids=["sem-socket", "fechada", "recusada"])
def test_o_servico_fora_do_ar_nao_tem_folga(causa: OSError) -> None:
    """Fora do ar não é demora: a verdade se pinta no primeiro tique."""
    import hefesto_vivo as hv

    folga = hv.FolgaDoServicoMudo()
    folga.respondeu(ESTADO_COM_DOIS)
    assert folga.mudo(_mudo_por(causa)) == {}, (
        f"{type(causa).__name__} ganhou folga — o serviço fora do ar ficaria "
        f"escondido atrás dos controles de antes")


def test_sem_resposta_boa_nao_ha_o_que_repintar() -> None:
    """A janela que abre com o serviço mudo pinta a verdade desde o começo."""
    import hefesto_vivo as hv

    assert hv.FolgaDoServicoMudo().mudo(_mudo_por(TimeoutError("timed out"))) == {}


#: O QUE A RÉGUA DO WEBKIT LÊ a cada amostra: o topo do botão, a marca do P1 e
#: se a frase da mesa está acesa.
LER_A_FILEIRA = r"""(() => {
  const b = document.querySelector('[data-gesto="reconectar"]');
  const p1 = document.querySelector('[data-controle="p1"]');
  const n = document.querySelector('.mesa-notas[data-campo="mesa-frase"]');
  if (!b || !p1 || !n) return JSON.stringify({erro: 'sem o botão, o P1 ou a frase da mesa'});
  return JSON.stringify({y: b.getBoundingClientRect().top, p1: p1.dataset.conectado || '',
                         frase: n.classList.contains('ha')});
})()"""


@pytest.fixture(scope="module")
def tique_mudo() -> dict[str, Any]:
    """O piloto de verdade, oculto, na página publicada: bom → mudo → lista vazia.

    O SERVIÇO É DUBLÊ, e o mudo tem a forma do produto: `DaemonMudo` com
    `TimeoutError` na causa. A ponte também, para nenhuma leitura sair deste
    processo. Os dois voltam no fim — `mesa_viva` e `pacotes.ponte` são módulos
    compartilhados, e um dublê esquecido entrega mesa de mentira ao vizinho.
    """
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse
    import json
    import time

    import hefesto_vivo as hv

    fase: dict[str, Any] = {"como": "bom", "mudos": 0}

    def estado(*_a: Any, **_k: Any) -> dict[str, Any]:
        if fase["como"] == "mudo":
            fase["mudos"] += 1
            try:
                raise TimeoutError("timed out")
            except TimeoutError as causa:
                raise hv.mesa_viva.DaemonMudo("timed out") from causa
        if fase["como"] == "vazia":
            return {**ESTADO_COM_DOIS, "controllers": []}
        return ESTADO_COM_DOIS

    def sem_daemon(metodo: str, *_a: Any, **_k: Any) -> Any:
        raise RuntimeError(f"régua: sem daemon para {metodo}")

    folga = int(hv.MUDOS_SEGUIDOS_QUE_VOLTARAM)
    fora: dict[str, Any] = {"amostras": [], "folga": folga}
    guardado = (hv.mesa_viva.estado_do_daemon, hv.ponte.resultado)
    hv.mesa_viva.estado_do_daemon = estado  # type: ignore[assignment]
    hv.ponte.resultado = sem_daemon  # type: ignore[assignment]
    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre="", prova_no_aparelho=False, entre=2500, espera=1200,
        incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False, conta_mutacoes=0,
    )
    piloto = hv.Piloto(args)

    def de_pe() -> bool:
        return bool(piloto.pronto and piloto.tela.na_aba
                    and piloto.pagina == "01-jogar.html")

    def amostrar() -> bool:
        if fora.get("parar"):
            return False
        if not de_pe():
            return True
        como, mudos = fase["como"], fase["mudos"]

        def leu(valor: Any, erro: Any) -> None:
            if erro is not None:
                fora["amostras"].append({"erro": str(erro), "fase": como})
                return
            lido = json.loads(str(valor))
            lido.update(fase=como, mudos=mudos)
            fora["amostras"].append(lido)

        piloto.ponte.perguntar(LER_A_FILEIRA, leu)
        return True

    def roteiro() -> bool:
        if fora.get("parar"):
            return False
        amostras = fora["amostras"]
        if fase["como"] == "bom":
            if sum(1 for a in amostras if a.get("p1") == "sim") >= 5:
                fase["como"] = "mudo"
        elif fase["como"] == "mudo":
            if fase["mudos"] >= folga + 6:
                fase["como"] = "vazia"
        elif sum(1 for a in amostras if a.get("fase") == "vazia" and a.get("frase")) >= 5:
            fora["completou"] = True
            fora["parar"] = True
            Gtk.main_quit()
            return False
        return True

    GLib.timeout_add(40, amostrar)
    GLib.timeout_add(50, roteiro)
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        limite = time.monotonic() + 60.0
        while not fora.get("completou") and time.monotonic() < limite:
            Gtk.main()
    finally:
        # OS DOIS TIMERS SE DESARMAM SOZINHOS no próximo disparo: um relógio que
        # sobra da fixture dispara dentro do laço do PRÓXIMO teste de GUI.
        fora["parar"] = True
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        (hv.mesa_viva.estado_do_daemon,
         hv.ponte.resultado) = guardado  # type: ignore[assignment]
    assert fora.get("completou"), (
        f"o roteiro não chegou ao fim (fase {fase['como']}, {fase['mudos']} mudos, "
        f"{len(fora['amostras'])} amostras) — a régua mediria pela metade")
    erros = [a for a in fora["amostras"] if "erro" in a]
    assert not erros, f"a leitura da fileira falhou: {erros[:3]}"
    return fora


def test_no_webkit_o_tique_mudo_repinta_o_ultimo_estado_bom(tique_mudo: dict[str, Any]) -> None:
    """Dentro da folga os lugares continuam cheios — no motor dela.

    A MORDIDA: troque `st = self._folga.mudo(e)` por `st = {}` no `_tique` e o
    P1 apaga já no primeiro tique mudo.
    """
    folga = tique_mudo["folga"]
    dentro = [a for a in tique_mudo["amostras"]
              if a["fase"] == "mudo" and 1 <= a["mudos"] <= folga]
    assert dentro, "nenhuma amostra caiu dentro da folga — a régua não mediu o que promete"
    apagou = [a for a in dentro if a["p1"] != "sim"]
    assert not apagou, (
        f"o serviço demorou {apagou[0]['mudos']} tique(s) e os lugares já apagaram "
        f"— a folga de {folga} não segurou: {apagou[:3]}")


def test_no_webkit_depois_da_folga_a_tela_diz_que_o_servico_calou(
        tique_mudo: dict[str, Any]) -> None:
    """E a folga ACABA: passado o último mudo que ela segura, o P1 apaga."""
    folga = tique_mudo["folga"]
    depois = [a for a in tique_mudo["amostras"]
              if a["fase"] == "mudo" and a["mudos"] >= folga + 2]
    assert depois, "nenhuma amostra depois da folga — a régua não viu a verdade chegar"
    assert any(a["p1"] == LUGAR_VAZIO for a in depois), (
        "passou da folga e a tela continuou afirmando o P1 — estado velho pintado "
        "como se fosse de agora")


def test_no_webkit_o_botao_nao_anda_com_os_lugares_apagados(
        tique_mudo: dict[str, Any]) -> None:
    """O y do botão no repouso, com os lugares apagados e com a frase acesa.

    ANTES DA CURA, no piloto: 463 → 402 com os lugares apagados, 463 → 429 com a
    lista vazia. Com a cura, 462 nas duas.
    """
    amostras = tique_mudo["amostras"]
    repouso = [a["y"] for a in amostras if a["fase"] == "bom" and a["p1"] == "sim"]
    apagados = [a for a in amostras if a["p1"] == LUGAR_VAZIO and not a["frase"]]
    acesa = [a for a in amostras if a["frase"]]
    assert repouso and apagados and acesa, (
        "a régua não viu o repouso, os lugares apagados ou a frase acesa — "
        "ficaria verde sobre nada")
    base = repouso[-1]
    for rotulo, grupo in (("com os lugares apagados", apagados),
                          ("com a lista vazia e a frase acesa", acesa)):
        pior = max(grupo, key=lambda a: abs(a["y"] - base))
        dy = pior["y"] - base
        assert abs(dy) <= TOLERANCIA_DO_ESTADO, (
            f"no WebKit, {rotulo}, o botão {'subiu' if dy < 0 else 'desceu'} "
            f"{abs(dy):.0f} px — y {base:.1f} → {pior['y']:.1f}")
