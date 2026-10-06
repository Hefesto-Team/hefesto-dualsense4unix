#!/usr/bin/env python3
"""As QUATRO decisões de produto na aba Iluminação, medidas uma a uma — 04/09/2026.

A fonte é o registro «O-PO-DECIDE-as-54-e-os-sete-conflitos» de 04/09/2026,
§2, aba `04-iluminacao`, e a sprint
`2026-09-04-ONDA2-04-ILUMINACAO-01-o-interruptor-de-verdade-e-a-cor-que-se-grava-ao-desligar`:

    [01] a razão do tracejado    uma linha só quando há ressalva          (D-02)
         ↑ CADUCOU EM 07/09/2026, por  A linha saiu da célula `LEDs`, e as cinco
           réguas que a mediam saíram com ela — ver
           `test_a_04_as_lampadas_espelham_o_numero`, que guarda a AUSÊNCIA.
           A razão do tracejado continua no `title` das duas tiras.
    [02] o automático do perfil  interruptor DE VERDADE na aba            (D-13)
    [03] reenviar uma cor        a caixa do hexadecimal vira o botão
    [04] o brilho guardado       uma frase curta

**A DE PESO É A [02], E ELA VEIO CONTRA A RECOMENDAÇÃO ESCRITA.** A lista desta
aba propunha que o botão só MOSTRASSE o estado do automático, e que mudá-lo
continuasse na aba Perfis (conflito C-4). O usuário escolheu o interruptor, aceitou o
custo declarado (~30 px) e aceitou a consequência que ele abre — com estas
palavras: *"ok aceito o caminho"*. **Desligar GRAVA a cor de cada controle no
ato**, para cumprir a regra de 03/09 (*"nenhuma cor dos controles nunca
pode ser a mesma"*) sem o produto nunca dizer não a ela.

O QUE ESTE ARQUIVO MEDE, com a mordida escrita em cada caso:

1. o interruptor tem dono, mora no TOPO da aba, e a página o oferece com os
   três atributos que o piloto precisa para lê-lo e escrevê-lo;
2. **desligar grava a cor de cada CONECTADO no override dele**, com o
   `auto_player_colors` indo a `false` no MESMO arquivo — é a D-13 inteira;
3. ligar de volta não apaga cor nenhuma, e o perfil é REAPLICADO nas duas
   direções (sem isso o campo só entra em vigor na próxima troca de perfil, e o
   interruptor seria o botão que aceita o toque e não age);
4. o `click` que o navegador manda junto do `change` não inverte duas vezes;
5. o reenvio lê o TEXTO da caixa, e **ignora o `data-hex`** — que é a metade
   que morde: o `data-hex` é escrito pelo gerador e fica congelado no que o
   mockup sabia;
6. a faixa dos LEDs mantém a tira CENTRADA e a aba não rola por dentro —
   medido no Chrome, na página. (Esta linha olhava a ressalva até 07/09/2026;
   com a linha fora, o que sobra a medir é o pixel da faixa, que é o que a
   asserção sempre olhou de verdade — ver `_medida`.);
7. a frase do brilho guardado é curta e **não é uma recusa**.

O LAR É DE MENTIRA. O `conftest` desvia `HOME` e os quatro `XDG_*`; os casos que
gravam escrevem perfil de verdade, com `save_profile`, dentro dele — que é a
única forma de provar que o disco recebeu, em vez de provar que a função foi
chamada. É o mesmo desenho de `test_a_04_o_trilho_de_brilho_grava.py`.

**RELATADO, e é de outra posse:** `("04-iluminacao.html", "auto-cores")` tem de
entrar em `hefesto_vivo.PERIGOSOS` — o gesto chama `gravar_e_reaplicar`, e a
régua de clique acionaria o interruptor sozinha, desligando o automático no
perfil do usuário para provar que sabe clicar. `interface/hefesto_vivo.py` é da ONDA 0
e esta frente não o toca; quem já reprova por isso é
`tests/unit/test_todo_gesto_que_grava_esta_protegido.py`, com o nome do gesto na
mensagem.
"""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _p in (str(RAIZ / "src"), str(INTERFACE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PAGINA = "04-iluminacao.html"

UM = "aa:bb:cc:00:00:01"
DOIS = "aa:bb:cc:00:00:02"
CHAVE_UM, CHAVE_DOIS = "aabbcc000001", "aabbcc000002"

MESA = [
    {"pref": "p1", "uniq": UM, "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB"},
    {"pref": "p2", "uniq": DOIS, "jogador": 2, "cor": "galactic-purple",
     "nome": "Galactic Purple", "via": "BT"},
]

#: P2, que são `player_slot_color(1)` e `(2)`.
P1 = {"uniq": UM, "index": 0, "transport": "usb", "connected": True,
      "player": 1, "player_slot": 1, "is_primary": True,
      "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
      "lightbar_source": "sysfs"}
P2 = {"uniq": DOIS, "index": 1, "transport": "bluetooth", "connected": True,
      "player": 2, "player_slot": 2, "is_primary": False,
      "lightbar_rgb": [255, 0, 0], "lightbar_on": True,
      "lightbar_source": "sysfs"}


@pytest.fixture
def a04():
    from pacotes import a04_iluminacao

    return a04_iluminacao


@pytest.fixture
def pac():
    import pacotes

    return pacotes


def _ctx(pac, *, perfil="regua", conectados=None, state=None):
    return pac.Contexto(state={"active_profile": perfil, **(state or {})},
                        mesa=[dict(m) for m in MESA],
                        conectados=[dict(c) for c in (conectados or [P1, P2])],
                        estados={})


class PonteDeMentira:
    """Um dublê da ponte que guarda o que foi chamado e devolve o caminho feliz."""

    def __init__(self, corpo: object = ...):
        self.corpo = ({"aplicado_em": [UM, DOIS], "guardado_em": []}
                      if corpo is ... else corpo)
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return True if nome in ("chamar", "profile_switch") else self.corpo

        return registrar

    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]


def _semear(nome: str = "regua", *, automatico: bool = True,
            overrides: dict | None = None, brilho: float = 1.0):
    """Escreve um perfil no lar de mentira e devolve o caminho do arquivo."""
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        LedsConfig,
        MatchAny,
        Profile,
    )

    prof = Profile(
        name=nome,
        match=MatchAny(),
        leds=LedsConfig(lightbar=(40, 80, 180), lightbar_brightness=brilho,
                        auto_player_colors=automatico),
        controllers={
            chave: ControllerOverrides(leds=LedsConfig(**campos))
            for chave, campos in (overrides or {}).items()
        },
    )
    return save_profile(prof, origem="regua")


def _do_disco(caminho) -> dict:
    return json.loads(pathlib.Path(caminho).read_text(encoding="utf-8"))


def _mudanca(**extra) -> dict:
    """O clique que o piloto manda quando ela MEXE num `<input>`: o `change`.

    Os dois campos são do BOOTSTRAP e chegam em todo clique — `tipo` é o
    `tagName` do alvo e `evento` é o `ev.type`. Escrevê-los aqui é o que separa
    o ato da abertura; ver `a04_iluminacao._so_abriu_o_seletor`.
    """
    return {"controle": "p1", "uniq": UM, "tipo": "input",
            "evento": "change", "valor": "on", "texto": "", **extra}


def test_o_interruptor_tem_dono(pac, a04):
    """Um `data-gesto` sem função é uma chave que engole o clique."""
    assert pac.gesto_da_pagina(PAGINA, "auto-cores") is not None
    vivos = {nome for (pagina, nome) in pac.GESTOS if pagina == PAGINA}
    assert len(vivos) == a04.PISO_DA_ABA, (
        f"o pacote registra {len(vivos)} gestos e o piso declarado é "
        f"{a04.PISO_DA_ABA} — os dois têm de dizer o mesmo, e a nota datada do "
        f"`PISO_DA_ABA` é quem explica cada degrau")
    assert {"auto-cores", "reenviar"} <= vivos, (
        "o interruptor ou o reenvio do hexadecimal saíram do pacote — os dois "
        "são decisão dela de 04/09/2026, e nenhuma ordem posterior os tocou")


def test_a_pagina_oferece_o_interruptor_no_topo_da_aba():
    """*"Um interruptor no topo da aba Iluminação."* — e o topo é a faixa do título."""
    from hefesto_dualsense4unix.interface import onde
    from pacotes import a04_iluminacao as a04

    texto = onde.pagina(PAGINA).read_text(encoding="utf-8")
    topo = texto.split('<div class="quadro-topo">', 1)[-1].split("</div>", 1)[0]
    assert 'class="chave-auto"' in topo, (
        "o interruptor não está na faixa do título — fora dela ele custa uma "
        "linha da grade, e a coluna já está a 4px do teto medido")
    for atributo in (f'data-gesto="{a04.ENDERECO_DO_AUTOMATICO}"',
                     f'data-campo="{a04.ENDERECO_DO_AUTOMATICO}"',
                     'data-hef-alvo="marcado"'):
        assert atributo in topo, f"o interruptor perdeu {atributo!r}"


def test_o_pacote_diz_o_estado_do_automatico(a04, pac):
    """A tela lê o PERFIL, e as duas respostas são exercitadas."""
    _semear(automatico=True)
    assert a04.pacote(_ctx(pac))[a04.ENDERECO_DO_AUTOMATICO] == "sim"
    _semear(automatico=False)
    assert a04.pacote(_ctx(pac))[a04.ENDERECO_DO_AUTOMATICO] == ""


def test_o_estado_do_automatico_chega_a_tela(a04, pac):
    """E ele atravessa o `normalizar`, que é o que a tela consome."""
    _semear(automatico=True)
    fora = pac.normalizar(a04.pacote(_ctx(pac)))
    assert fora["mesa"].get(a04.ENDERECO_DO_AUTOMATICO) == "sim", (
        "o estado do automático não chegou à `mesa` — o piloto só escreve o "
        f"que está lá, e o `{a04.ENDERECO_DO_AUTOMATICO}` sumiu no caminho")


def test_desligar_grava_a_cor_de_cada_controle(pac, a04):
    """**A D-13 INTEIRA, e é o caso que o usuário aceitou por escrito.**"""
    caminho = _semear(automatico=True)
    p = PonteDeMentira()
    a04.auto_cores(_ctx(pac), _mudanca(), p)

    disco = _do_disco(caminho)
    assert disco["leds"]["auto_player_colors"] is False, (
        "o interruptor não desligou o automático no perfil")
    cores = {}
    for chave in (CHAVE_UM, CHAVE_DOIS):
        dele = disco.get("controllers", {}).get(chave, {})
        assert "leds" in dele and "lightbar" in dele["leds"], (
            f"o controle {chave} ficou SEM cor gravada — com o automático fora "
            f"ele cai na cor global, e o vizinho também: as duas iguais")
        cores[chave] = tuple(dele["leds"]["lightbar"])
    assert cores[CHAVE_UM] != cores[CHAVE_DOIS], (
        f"os dois controles ficaram com a MESMA cor ({cores}) — é exatamente a "
        f"regra dela que a gravação existe para cumprir")


def test_a_cor_gravada_e_a_que_estava_acesa(pac, a04):
    """E ela é a PEDIDA, não a publicada — a diferença é o brilho."""
    from hefesto_dualsense4unix.core.led_control import LedSettings

    caminho = _semear(automatico=True, brilho=0.5)
    meio = dict(P1, lightbar_rgb=list(
        LedSettings(lightbar=(0, 255, 0)).apply_brightness(0.5).lightbar))
    a04.auto_cores(_ctx(pac, conectados=[meio]), _mudanca(), PonteDeMentira())

    gravada = _do_disco(caminho)["controllers"][CHAVE_UM]["leds"]["lightbar"]
    assert tuple(gravada) == (0, 255, 0), (
        f"gravou {tuple(gravada)} — a cor guardada é a PEDIDA, e a 50% de "
        f"brilho o daemon publica a metade dela")


def test_sem_cor_conhecida_grava_a_do_numero(pac, a04):
    """A queda não é preto, e não é um remendo: é a cor que o automático dava.

    Nos estados em que o motor não afirma cor (a Steam com o `fd`, Nativo, cor
    desconhecida) o que o automático estava dando àquele controle é exatamente
    `player_slot_color(numero)` — é essa a paleta que ele governa. Um preto aqui
    apagaria a barra dela por um clique num interruptor.

    A MORDIDA: troque a queda por `(0, 0, 0)` e esta linha reprova.
    """
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    caminho = _semear(automatico=True)
    cego = dict(P1, lightbar_source="desconhecida", lightbar_rgb=None)
    a04.auto_cores(_ctx(pac, conectados=[cego]), _mudanca(), PonteDeMentira())

    gravada = tuple(_do_disco(caminho)["controllers"][CHAVE_UM]["leds"]["lightbar"])
    assert gravada == player_slot_color(1), (
        f"gravou {gravada} — sem cor conhecida a resposta é a do número, que é "
        f"o que o automático estava dando")


def test_ligar_de_volta_nao_apaga_cor_nenhuma(pac, a04):
    """O caminho de volta, e ele não tem consequência a confessar."""
    caminho = _semear(automatico=False,
                      overrides={CHAVE_UM: {"lightbar": (7, 8, 9)}})
    a04.auto_cores(_ctx(pac), _mudanca(), PonteDeMentira())

    disco = _do_disco(caminho)
    assert disco["leds"]["auto_player_colors"] is True
    assert tuple(disco["controllers"][CHAVE_UM]["leds"]["lightbar"]) == (7, 8, 9), (
        "ligar o automático apagou a cor que ela tinha escolhido para o "
        "controle — override e camada automática convivem no merge por campo")


def test_o_interruptor_reaplica_o_perfil(pac, a04):
    """Metade do gesto, e sem ela ele é o botão que aceita o toque e não age."""
    _semear(automatico=True)
    p = PonteDeMentira()
    a04.auto_cores(_ctx(pac), _mudanca(), p)
    assert "profile_reaplicar" in p.nomes(), (
        f"o gesto não mandou o daemon reaplicar o perfil: {p.nomes()}")


def test_o_click_que_vem_junto_do_change_nao_inverte_duas_vezes(pac, a04):
    """Um clique do usuário é UM ato — e o navegador manda dois eventos por ele.

    Um `<input type="checkbox">` dispara `click` E `change` no mesmo ato, e o
    BOOTSTRAP escuta os dois. Sem o guarda, um clique viraria DUAS inversões: o
    interruptor voltaria sozinho ao lugar, com duas gravações no perfil do usuário
    pelo caminho.

    A MORDIDA: tire o `if _so_abriu_o_seletor(o): return None` do gesto e esta
    linha reprova — o `auto_player_colors` volta a `True` e o arquivo ganha uma
    segunda gravação.
    """
    caminho = _semear(automatico=True)
    ctx = _ctx(pac)
    p = PonteDeMentira()
    a04.auto_cores(ctx, _mudanca(evento="click"), p)
    assert _do_disco(caminho)["leds"]["auto_player_colors"] is True, (
        "o `click` sozinho já inverteu — com o `change` que vem junto, um "
        "clique dela viraria duas gravações")
    assert p.chamadas == [], f"o `click` chegou a falar com o daemon: {p.nomes()}"


def test_sem_perfil_ativo_o_interruptor_grava_no_computador(pac, a04):
    """As cores automáticas são do COMPUTADOR desde 01/10/2026."""
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador

    a04.auto_cores(_ctx(pac, perfil=""), _mudanca(), PonteDeMentira())
    leds = o_computador().global_.leds
    assert leds is not None and "auto_player_colors" in leds.model_fields_set


def test_o_recado_do_interruptor_conta_a_consequencia(pac, a04):
    """O cartão diz as DUAS metades do que aconteceu ao desligar."""
    _semear(automatico=True)
    saiu = a04.auto_cores(_ctx(pac), _mudanca(), PonteDeMentira())
    assert isinstance(saiu, dict) and "recado" in saiu, (
        "o gesto voltou calado — o canal de sucesso da D-01 existe justamente "
        "para o clique que muda o perfil dizer o que fez")
    assert "cor" in saiu["recado"].lower(), (
        f"o recado não conta a gravação da cor: {saiu['recado']!r}")


def test_o_reenvio_manda_a_cor_escrita_na_caixa(pac, a04):
    """O gesto existe, e o que ele manda é o texto que está na tela."""
    assert pac.gesto_da_pagina(PAGINA, "reenviar") is not None
    p = PonteDeMentira()
    a04.reenviar(_ctx(pac), {"controle": "p1", "uniq": UM, "texto": "#12AB34"}, p)
    assert p.chamadas and p.chamadas[0][0] == "led_set_detalhado"
    assert p.chamadas[0][1] == ((18, 171, 52),), (
        f"o reenvio mandou {p.chamadas[0][1]!r}")


def test_o_reenvio_ignora_o_data_hex(pac, a04):
    """**A metade que morde**, e ela é a razão inteira de o gesto ser novo."""
    p = PonteDeMentira()
    a04.reenviar(_ctx(pac),
                 {"controle": "p1", "uniq": UM,
                  "hex": "#FF0000", "texto": "#12AB34"}, p)
    assert p.chamadas[0][1] == ((18, 171, 52),), (
        f"o reenvio leu o `data-hex` congelado: {p.chamadas[0][1]!r}")


def test_a_caixa_do_hexadecimal_nao_leva_data_hex():
    """E a página não oferece a porta errada — a régua olha o ARQUIVO."""
    from hefesto_dualsense4unix.interface import onde

    texto = onde.pagina(PAGINA).read_text(encoding="utf-8")
    caixas = [linha for linha in texto.splitlines() if 'class="hex reenvia"' in linha]
    assert caixas, "a caixa do hexadecimal deixou de ser botão"
    for caixa in caixas:
        assert 'data-gesto="reenviar"' in caixa
        assert "data-hex=" not in caixa, (
            "a caixa ganhou `data-hex` — o reenvio passaria a mandar a cor "
            "cravada no desenho, e não a que está na tela")


def test_o_travessao_de_um_lugar_vazio_nao_reenvia(pac, a04):
    """Numa coluna que esvaziou, a caixa mostra `—`, e `—` não é cor."""
    from pacotes import TRAVESSAO

    p = PonteDeMentira()
    with pytest.raises(ValueError, match="sem controle"):
        a04.reenviar(_ctx(pac), {"controle": "p3", "uniq": UM,
                                 "texto": TRAVESSAO}, p)
    assert p.chamadas == [], "a recusa ainda assim falou com o daemon"


CHROME = pathlib.Path("/usr/bin/google-chrome")


@pytest.fixture(scope="module")
def pagina_no_chrome():
    """A aba aberta num Chrome de verdade, com a `.nota` escondida."""
    if not CHROME.exists():
        pytest.skip("Chrome do sistema ausente — esta régua mede pixel de verdade")
    playwright = pytest.importorskip("playwright.sync_api")
    from hefesto_dualsense4unix.interface import onde

    with playwright.sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"],
                               ignore_default_args=["--hide-scrollbars"])
        pg = b.new_page(viewport={"width": 1920, "height": 1080},
                        device_scale_factor=1)
        pg.goto(f"file://{onde.pagina(PAGINA)}")
        pg.wait_for_load_state("networkidle")
        pg.add_style_tag(content=".nota{display:none}")
        pg.wait_for_timeout(300)
        yield pg
        b.close()


def _medida(pg) -> dict:
    """O que a tela mostra — e o VÃO DO PAI, que é onde o pixel se paga."""
    return pg.evaluate("""() => {
      const m = document.querySelector('.miolo');
      const q = document.querySelector('.quadro.luzes');
      const vaos = Array.from(document.querySelectorAll('.cel-leds')).map(cel => {
        const c = cel.getBoundingClientRect();
        const t = cel.querySelector('.aceso').getBoundingClientRect();
        const b = (cel.querySelector('.brilhos') || cel.querySelector('.aceso'))
          .getBoundingClientRect();
        return [+(t.top - c.top).toFixed(2), +(c.bottom - b.bottom).toFixed(2)];
      });
      return {rola: m.scrollHeight > m.clientHeight,
              quadro: Math.round(q.getBoundingClientRect().height),
              colunas: Array.from(document.querySelectorAll('.ctrl'))
                .map(c => Math.round(c.getBoundingClientRect().height)),
              ressalvas: Array.from(document.querySelectorAll('.ressalva'))
                .map(e => Math.round(e.getBoundingClientRect().height)),
              vaos: vaos};
    }""")


def test_no_repouso_a_linha_nao_cobra_pixel_e_a_aba_nao_rola(pagina_no_chrome):
    """A régua da D-02, aplicada a esta aba: zero no repouso."""
    m = pagina_no_chrome and _medida(pagina_no_chrome)
    assert m["vaos"], "nenhuma `.cel-leds` na página — a tira perdeu a célula"
    for acima, abaixo in m["vaos"]:
        assert abs(acima - abaixo) <= 0.6, (
            f"a tira ficou descentrada na faixa dos LEDs ({acima} acima, "
            f"{abaixo} abaixo) — alguma coisa entrou no fluxo da célula "
            f"debaixo da tira e cobra pixel em toda tela")
        assert acima >= -0.6 and abaixo >= -0.6, (
            f"a faixa dos LEDs transbordou ({acima} acima, {abaixo} abaixo) — "
            f"alguma coisa entrou no fluxo da célula além da tira e das pílulas")
    assert not m["rola"], (
        f"a aba passou a rolar por dentro — o quadro mede {m['quadro']}px")


def test_o_brilho_guardado_diz_uma_frase_curta_e_nao_recusa(pac, a04):
    """Decisão [04] dela, entre a frase inteira, a curta e o silêncio."""
    caminho = _semear()
    disputado = dict(P1, lightbar_disputada=True)
    ctx = _ctx(pac, conectados=[disputado])
    p = PonteDeMentira()

    saiu = a04.brilho(ctx, {"controle": "p1", "uniq": UM, "tipo": "input",
                            "evento": "change", "valor": "60"}, p)

    assert isinstance(saiu, dict) and saiu.get("recado"), (
        "o gesto não devolveu recado — ou levantou, e um brilho GUARDADO não é "
        "uma recusa")
    frase = saiu["recado"]
    guardado = _do_disco(caminho)["controllers"][CHAVE_UM]["leds"]
    assert guardado["lightbar_brightness"] == pytest.approx(0.6), (
        f"a frase saiu e o disco não recebeu: {guardado}")
    assert "reacender" not in frase and len(frase) <= 110, (
        f"a frase não encolheu ({len(frase)} caracteres): {frase!r}")
    assert p.nomes() == ["led_set_detalhado"], (
        f"o brilho escolhido não chegou ao aparelho: {p.nomes()}")
    _, _, argumentos = p.chamadas[0]
    assert argumentos.get("brightness") == pytest.approx(0.6), (
        f"chegou ao aparelho com outro brilho: {argumentos}")


def test_a_frase_curta_carrega_a_causa_do_motor(pac, a04):
    """Encolher não é perder o porquê: a causa continua vindo do dono."""
    from hefesto_dualsense4unix.interface.cartao_do_controle import rotulo_lightbar

    _semear()
    disputado = dict(P1, lightbar_disputada=True)
    ctx = _ctx(pac, conectados=[disputado])
    causa, _ = rotulo_lightbar(disputado, ctx.state)

    saiu = a04.brilho(ctx, {"controle": "p1", "uniq": UM, "tipo": "input",
                            "evento": "change", "valor": "60"}, PonteDeMentira())
    assert causa in saiu["recado"], (
        f"a frase não traz a causa do motor ({causa!r}): {saiu['recado']!r}")


def test_a_pasta_de_perfis_desta_regua_e_de_mentira():
    """A guarda de vacuidade, e ela é a mais importante deste arquivo."""
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    conftest = next(m for nome, m in sys.modules.items()
                    if nome.endswith("conftest") and hasattr(m, "lar_real"))
    onde_grava = pathlib.Path(profiles_dir()).resolve()
    real = pathlib.Path(conftest.lar_real()).resolve()
    assert not onde_grava.is_relative_to(real), (
        f"a régua escreveria em {onde_grava}, que está dentro do $HOME REAL "
        f"({real}) — sete casos deste arquivo chamam `save_profile`")
