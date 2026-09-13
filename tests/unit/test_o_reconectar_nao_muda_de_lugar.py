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
VIVO_XBOX: dict[str, Any] = {
    "connected": True, "native_mode": False, "paused": False,
    "gamepad_emulation": {"enabled": True, "flavor": "xbox", "backend": "uinput"},
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
    """§3.2, primeiro elo: sem `manual` o daemon leria reconciliação e poderia recusar."""
    plano = aba._plano_do_chip("xbox")
    pedidos = [p for m, p in plano if m == "gamepad.emulation.set"]
    assert pedidos == [{"enabled": True, "origin": "manual", "flavor": "xbox"}], plano


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
    """§3.2, terceiro elo: o chip lê o `flavor`, e a pendência some quando ele chega."""
    assert aba._estado_da_tela(VIVO_DUALSENSE)["modo-aceso"] == "dualsense"
    assert aba._estado_da_tela(VIVO_XBOX)["modo-aceso"] == "xbox"
    aba.modo_xbox(_ctx(VIVO_DUALSENSE), {"texto": "Xbox"}, PonteDeMentira())
    assert aba._faixa_do_pendente(VIVO_XBOX) == ("", "")
