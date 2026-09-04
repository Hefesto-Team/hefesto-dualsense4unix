#!/usr/bin/env python3
"""A RÉGUA DA FORÇA DA VIBRAÇÃO **POR CONTROLE** — aba Vibração, 03/09/2026.

DUAS DECISÕES DELA, no mesmo dia, e esta régua mede as duas:

1. **"Construir por controle."** O clique num degrau da coluna deixou de mandar
   `rumble.policy_set` (que é da MESA e não aceita `uniq`) e passou a gravar
   `controllers[uniq].rumble` no PERFIL ativo — de onde
   `profiles/manager._controllers_to_rumble_scales` o transforma em fator
   relativo, o `ProfileManager.apply` o publica com `set_rumble_scales` e o
   `core/backend_pydualsense._escalar_rumble` o aplica no motor daquele handle.
2. **"0 a 200%, e grava na hora."** A barra "Personalizado" era LEITURA — um
   `<div>` sem `value`, cujo clique o gesto recusava com um `ValueError` que
   **não chega à tela** — e virou um `<input type=range>` que grava
   `policy="custom"` com o `custom_mult` que ela arrastou.

POR QUE ELA PRECISA DE ARQUIVO PRÓPRIO, e não de linhas em
`a05_vibracao.PROVAS`: aquela régua passa um dublê de ponte e cobra QUAL função
dela foi chamada. Estes dois gestos exigem **perfil ativo** — que o `ctx` dela
não tem — e o que eles mudam PRIMEIRO é o disco; o `profile.switch` vem depois.
Uma prova que só olhasse a ponte diria que eles funcionam mesmo com o que foi
para o arquivo errado. É a mesma razão que tirou o `teto-da-vibracao` das provas
da aba Conexões.

A PONTE É DUBLÊ E O DISCO É DE MENTIRA, SEMPRE. `perfil.gravar_e_reaplicar`
chama `p.profile_switch(...)` quando o nome casa o ativo, e uma ponte real
mandaria isso ao daemon DELA, que está vivo com um DualSense no cabo. Todo
`uniq` daqui vem da faixa sintética `aa:bb:cc:00:00:01` — há dois portões de
anonimato que reprovam o contrário.

O QUE ELA COBRA, e cada item é um jeito diferente de a tela ou o disco mentir:

 1. o degrau clicado vira override SÓ daquele controle;
 2. a chave gravada é a NORMALIZADA — a mesma com que o backend casa o fator;
 3. `Auto` LIMPA o override, e nunca o grava (o esquema o recusa por unidade);
 4. degrau igual ao global não vira override;
 5. o segundo clique igual não regrava — nem dispara `profile.switch`;
 6. a barra arrastada grava `custom` com o multiplicador em 0-2;
 7. o teto é o do esquema, e passar dele RECUSA DIZENDO;
 8. sem perfil ativo, e sem controle, a recusa é `RuntimeError` — a única que
    chega ao cartão dela;
 9. o teto da barra tem UM dono, e o gerador lê o mesmo;
10. a PINTURA mostra o que está no disco, e não o degrau da mesa;
11. o `mult-pos` é o número cru, e não a largura do trilho;
12. o desenho publica um `<input type=range>` por coluna viva, com o teto e o
    passo derivados;
13. os dois gestos estão em `PERIGOSOS` — a prova automática não escreve no
    perfil dela;
14. o fator que chega ao motor é o da conta do produto, ponta a ponta.

AS MORDIDAS ESTÃO NO DOCSTRING DE CADA CASO, uma a uma, com o que reprova.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: O ENDEREÇO DA BANCADA — faixa sintética, nunca um MAC de aparelho real.
UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"
#: O VIZINHO, para provar que o clique de uma coluna não mexe na outra.
UNIQ_B = "aa:bb:cc:00:00:02"
CHAVE_B = "aabbcc000002"


class PonteDeMentira:
    """Guarda o que foi pedido ao daemon, na ordem. NUNCA fala com o de verdade."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...]]] = []

    def profile_switch(self, nome: str) -> bool:
        self.chamadas.append(("profile_switch", (nome,)))
        return True

    def chamar(self, metodo: str, **_: Any) -> bool:
        self.chamadas.append(("chamar", (metodo,)))
        return True


def _perfil_de_verdade(nome: str = "Bancada", **campos: Any) -> Any:
    """Um `Profile` DE VERDADE — o esquema é metade do que esta régua mede.

    Um dublê aceitaria `policy="furrufu"` e a régua ficaria verde sobre um
    perfil que o loader recusaria no disco dela.
    """
    from hefesto_dualsense4unix.profiles.schema import Profile

    return Profile.model_validate(
        {"name": nome, "match": {"type": "criteria"}, **campos})


@pytest.fixture
def pac():
    import pacotes

    return pacotes


@pytest.fixture
def a05():
    from pacotes import a05_vibracao

    return a05_vibracao


@pytest.fixture
def clique_no_degrau(pac):
    fn = pac.gesto_da_pagina("05-vibracao.html", "forca")
    assert fn is not None, (
        "05-vibracao.html:forca perdeu o dono — os quatro degraus de cada "
        "coluna voltam a não fazer nada.")
    return fn


@pytest.fixture
def arraste(pac):
    fn = pac.gesto_da_pagina("05-vibracao.html", "intensidade")
    assert fn is not None, (
        "05-vibracao.html:intensidade perdeu o dono — a barra 'Personalizado' "
        "volta a ser desenho.")
    return fn


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira: guarda o que o gesto mandou gravar."""
    from hefesto_dualsense4unix.profiles import loader

    gravados: list[Any] = []
    estado: dict[str, Any] = {}

    def falso_load(nome: str) -> Any:
        return estado[nome]

    def falso_save(prof: Any, **_: Any) -> None:
        gravados.append(prof)

    monkeypatch.setattr(loader, "load_profile", falso_load, raising=False)
    monkeypatch.setattr(loader, "save_profile", falso_save, raising=False)
    return estado, gravados


def _ctx(pac, ativo: str = "Bancada"):
    return pac.Contexto(
        state={"active_profile": ativo, "rumble_policy": "balanceado"},
        mesa=[],
        conectados=[{"uniq": UNIQ, "connected": True, "transport": "usb", "index": 0},
                    {"uniq": UNIQ_B, "connected": True, "transport": "bt", "index": 1}],
        estados={})


# ---------------------------------------------------------------------------
# 1. o degrau vira override — e SÓ daquele controle
# ---------------------------------------------------------------------------
def test_o_degrau_clicado_vira_override_so_daquele_controle(
        pac, clique_no_degrau, disco) -> None:
    """Clicar "Economia" na coluna do P1 não toca no P2 nem no global.

    É A DECISÃO DELA INTEIRA numa asserção: até 02/09 este clique chamava
    `rumble.policy_set`, que é da MESA, e mudava os quatro de uma vez.

    MORDIDA: em `a05_vibracao.forca`, troque `_gravar_a_forca(ctx, p, uniq,
    degrau)` por uma chamada a `p.rumble_policy_set_checked(degrau)` — este caso
    reprova, porque nada é gravado no perfil e o override do P1 não existe.
    """
    estado, gravados = disco
    estado["Bancada"] = _perfil_de_verdade(rumble={"policy": "balanceado"})
    p = PonteDeMentira()

    clique_no_degrau(_ctx(pac), {"uniq": UNIQ, "forca": "economia"}, p)

    assert len(gravados) == 1, f"gravou {len(gravados)} vez(es), esperava uma"
    prof = gravados[0]
    dele = (prof.controllers or {}).get(CHAVE)
    assert dele is not None and dele.rumble is not None, (
        f"não há override de vibração para {CHAVE!r}: as chaves gravadas são "
        f"{sorted((prof.controllers or {}).keys())}")
    assert dele.rumble.policy == "economia", f"gravou {dele.rumble!r}"
    assert CHAVE_B not in (prof.controllers or {}), (
        "o clique numa coluna escreveu no controle da OUTRA — é exatamente o "
        "defeito que a decisão dela existe para curar")
    assert prof.rumble.policy == "balanceado", (
        f"o clique da coluna mudou o degrau da MESA para "
        f"{prof.rumble.policy!r} — os quatro controles voltariam a andar juntos")


def test_a_chave_gravada_e_a_que_o_motor_casa(pac, clique_no_degrau, disco) -> None:
    """Doze hexa minúsculos, sem separador — a grafia do `norm_mac`.

    O mapa que chega ao backend é chaveado pelo `uniq` normalizado
    (`set_rumble_scales`); gravar sob `aa:bb:…` criaria uma SEGUNDA chave para o
    mesmo aparelho, e a borda do esquema rejeita o perfil INTEIRO com "chaves
    duplicadas após normalização". A escolha dela sumiria, e o arquivo junto.

    MORDIDA: em `a05_vibracao._chave_no_perfil`, devolva `uniq` cru em vez do
    `norm_mac` — este caso reprova com a chave `aa:bb:cc:00:00:01`.
    """
    estado, gravados = disco
    estado["Bancada"] = _perfil_de_verdade()
    clique_no_degrau(_ctx(pac), {"uniq": UNIQ, "forca": "max"}, PonteDeMentira())

    chaves = sorted((gravados[0].controllers or {}).keys())
    assert chaves == [CHAVE], f"gravou sob {chaves}, e o backend casa por {CHAVE!r}"


# ---------------------------------------------------------------------------
# 2. o `Auto`, que o esquema recusa por unidade
# ---------------------------------------------------------------------------
def test_o_auto_limpa_o_override_e_nunca_o_grava(
        pac, clique_no_degrau, disco) -> None:
    """"Auto" devolve a coluna ao global — a leitura que o PRODUTO escolheu.

    `ControllerRumbleOverride` RECUSA `auto` por unidade, com validador e razão
    próprios: ele escala pela bateria do controle PRIMÁRIO, e guardá-lo por peça
    faria duas escalarem pela bateria da mesma. `with_controller_rumble` traduz
    o clique em *"limpa o override dela e devolve a peça ao global — que é a
    leitura honesta do gesto, e não um erro silencioso"*.

    **E ELE PASSOU A DIZER ISSO — 04/09/2026.** Até 03/09 o gesto limpava e
    voltava CALADO: a coluna caía no degrau da mesa um tique depois, e o botão
    que ela clicou não era o que ficava aceso. A janela estável conta o mesmo
    desfecho desde 25/08 (RUM-3), e a frase é dela —
    `rumble_actions.TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL`, lida daqui em vez de
    redigitada, porque duas cópias de um texto de tela divergem na primeira
    edição.

    MORDIDA: em `a05_vibracao.forca`, contorne o produto gravando
    `ControllerRumbleOverride(policy="auto")` à mão — o esquema levanta e este
    caso reprova com a recusa dele em vez do perfil limpo.
    """
    from hefesto_dualsense4unix.app.actions.rumble_actions import (
        TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL,
    )

    estado, gravados = disco
    estado["Bancada"] = _perfil_de_verdade(
        rumble={"policy": "balanceado"},
        controllers={CHAVE: {"rumble": {"policy": "economia"}}})

    with pytest.raises(RuntimeError) as recusa:
        clique_no_degrau(_ctx(pac), {"uniq": UNIQ, "forca": "auto"},
                         PonteDeMentira())
    assert TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL.strip(" —") in str(recusa.value), (
        f"o Auto voltou a limpar o override em silêncio: {recusa.value}")

    assert len(gravados) == 1, "o Auto não gravou — a coluna ficaria em Economia"
    dele = (gravados[0].controllers or {}).get(CHAVE)
    assert dele is None or dele.rumble is None, (
        f"o Auto deixou um override de vibração para trás: {dele!r}")


def test_degrau_igual_ao_global_nao_vira_override(
        pac, clique_no_degrau, disco) -> None:
    """Escolher o que já vale na mesa não deixa opinião no disco.

    A razão é aritmética e é do produto: `_controllers_to_rumble_scales` calcula
    `mult / base` e DESCARTA o fator 1,0. Guardar o override só deixaria no
    arquivo dela uma opinião que o motor ignora — e que a próxima ativação teria
    de reaplicar.

    MORDIDA: em `_gravar_a_forca`, troque `draft.with_controller_rumble(...)`
    por uma escrita direta do override — este caso reprova, porque o perfil
    passa a guardar `balanceado` sob a chave do P1.
    """
    estado, gravados = disco
    estado["Bancada"] = _perfil_de_verdade(rumble={"policy": "balanceado"})

    clique_no_degrau(_ctx(pac), {"uniq": UNIQ, "forca": "balanceado"},
                     PonteDeMentira())

    assert not gravados, (
        f"gravou {len(gravados)} vez(es) um override igual ao global — o motor "
        f"o ignora, e o arquivo dela fica com lixo")


def test_o_segundo_clique_igual_nao_regrava(pac, clique_no_degrau, disco) -> None:
    """Regravar o mesmo perfil dispara `profile.switch` no meio da partida.

    É a guarda que também torna inócuo o clique DOBRADO da barra arrastável: o
    ouvinte do piloto escuta `change` **e** `click`, e soltar o polegar de um
    `<input type=range>` dispara os dois com o mesmo valor.

    MORDIDA: em `_gravar_a_forca`, tire o `if novo.source_controllers ==
    draft.source_controllers: return` — este caso reprova com duas gravações e
    dois `profile_switch`.
    """
    estado, gravados = disco
    estado["Bancada"] = _perfil_de_verdade(
        rumble={"policy": "balanceado"},
        controllers={CHAVE: {"rumble": {"policy": "economia"}}})
    p = PonteDeMentira()

    clique_no_degrau(_ctx(pac), {"uniq": UNIQ, "forca": "economia"}, p)

    assert not gravados, "regravou um perfil que já dizia exatamente isso"
    assert not p.chamadas, (
        f"falou com o daemon sem ter o que dizer: {p.chamadas}")


# ---------------------------------------------------------------------------
# 3. a barra arrastável — a segunda decisão dela
# ---------------------------------------------------------------------------
def test_a_barra_arrastada_grava_o_multiplicador(pac, arraste, disco) -> None:
    """175% na barra vira `policy="custom"` com `custom_mult=1.75`.

    A DIVISÃO POR 100 É DE UNIDADE: a tela fala em pontos percentuais e o perfil
    guarda o multiplicador (`custom_mult`, 0 a 2).

    MORDIDA: em `a05_vibracao.intensidade`, passe `custom=pontos` em vez de
    `pontos / 100` — a borda do esquema recusa `175.0` e este caso reprova com a
    frase dela em vez do valor gravado.
    """
    estado, gravados = disco
    estado["Bancada"] = _perfil_de_verdade(rumble={"policy": "balanceado"})

    arraste(_ctx(pac), {"uniq": UNIQ, "valor": "175"}, PonteDeMentira())

    dele = (gravados[0].controllers or {}).get(CHAVE)
    assert dele is not None and dele.rumble is not None, "nada foi gravado"
    assert dele.rumble.policy == "custom", f"gravou {dele.rumble.policy!r}"
    assert dele.rumble.custom_mult == pytest.approx(1.75), (
        f"gravou {dele.rumble.custom_mult!r} — a tela dizia 175%")


def test_o_teto_da_barra_e_o_do_esquema(a05) -> None:
    """200 — e o número tem UM dono, que é quem recusa o que passa dele.

    O `150` que a aba usava até ontem era a segunda cópia de
    `RUMBLE_POLICY_MULT["max"]`, e o teto do que ela pode ARRASTAR não é o do
    degrau mais alto: é o do multiplicador personalizado.

    MORDIDA: escreva `return 200` em `a05_vibracao.teto_da_barra` — este caso
    continua verde HOJE e reprova no dia em que o esquema mudar, que é
    exatamente o dia em que a barra passaria a mentir. Por isso a asserção é
    contra o dono, e não contra o número.
    """
    from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX

    assert a05.teto_da_barra() == round(RUMBLE_CUSTOM_MULT_MAX * 100)


def test_o_teto_recusa_dizendo_em_vez_de_gravar(pac, arraste, disco) -> None:
    """210% não entra no disco, e a recusa chega ao CARTÃO dela.

    Quem recusa é a BORDA do esquema (`RumbleDraft`, `le=RUMBLE_CUSTOM_MULT_MAX`)
    — não uma checagem escrita no gesto, que envelheceria na primeira mudança do
    produto. O que o gesto faz é vestir a recusa de `RuntimeError`, que é o
    único tipo que `hefesto_vivo._recusou_dizendo` leva à tela.

    MORDIDA: em `_gravar_a_forca`, tire o `try/except` que veste a recusa —
    este caso reprova, porque o `ValidationError` do pydantic sobe cru. Ele é
    subclasse de `ValueError`, e `ValueError` é justamente o tipo que
    `hefesto_vivo._recusou_dizendo` NÃO leva ao cartão: a recusa iria para o
    `stderr` de quem lançou a janela, e para ela o arraste não faria nada.

    MEDIDO, E A NOTA IMPORTA: trocar o `RumbleDraft.model_validate` por
    `model_copy` **não** reprova este caso — a borda de baixo
    (`ControllerRumbleOverride`) pega o 2,1 do mesmo jeito. O `model_validate`
    não é a única trava; ele é a trava mais PERTO do número, e o que ganha é a
    frase (ela nomeia `custom_mult` em vez de um campo de `Profile`).
    """
    estado, gravados = disco
    estado["Bancada"] = _perfil_de_verdade()

    with pytest.raises(RuntimeError):
        arraste(_ctx(pac), {"uniq": UNIQ, "valor": "210"}, PonteDeMentira())
    assert not gravados, "gravou um multiplicador que o produto recusa"


# ---------------------------------------------------------------------------
# 4. as recusas que TÊM de chegar à tela
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("clique", [  # (noqa-acento) nome do argumento
    {"uniq": UNIQ, "forca": ""},
    {"uniq": "", "forca": "max"},
])
def test_a_recusa_do_degrau_e_runtime_error(pac, clique_no_degrau, clique) -> None:
    """`ValueError` fica no `stderr` de quem lançou a janela; ela não o lê.

    O contrato do piloto é explícito: `RuntimeError` quer dizer *"o produto
    recusou, e a frase VAI PARA A TELA"*. As duas recusas deste gesto falam com
    quem está com o controle na mão.

    MORDIDA: devolva `ValueError` a qualquer uma das duas em `a05_vibracao.forca`
    — este caso reprova.
    """
    with pytest.raises(RuntimeError):
        clique_no_degrau(_ctx(pac), clique, PonteDeMentira())


def test_sem_perfil_ativo_a_recusa_diz_onde_escolher(pac, clique_no_degrau) -> None:
    """A força de um controle é do PERFIL — sem um, não há onde guardar.

    MORDIDA: em `_gravar_a_forca`, tire a guarda do `active_profile` — o
    `load_profile("")` levanta um erro de arquivo, e a frase que chega ao cartão
    dela passa a ser um caminho de disco.
    """
    with pytest.raises(RuntimeError, match=r"[Pp]erfil"):
        clique_no_degrau(_ctx(pac, ativo=""), {"uniq": UNIQ, "forca": "max"},
                         PonteDeMentira())


def test_a_recusa_do_arraste_sem_numero_e_runtime_error(pac, arraste) -> None:
    """Um arraste sem `valor` é o estado de ONTEM, e ele tem de falar.

    Era assim que a linha "Personalizado" respondia: `valor: alvo.value ?? ''`
    num `<div>` que não tem `value`, e a recusa saía num `ValueError` que a tela
    não mostra.

    MORDIDA: devolva `ValueError` em `a05_vibracao.intensidade` — este reprova.
    """
    with pytest.raises(RuntimeError):
        arraste(_ctx(pac), {"uniq": UNIQ, "valor": ""}, PonteDeMentira())


# ---------------------------------------------------------------------------
# 5. a PINTURA — a metade sem a qual a tela mente um tique depois
# ---------------------------------------------------------------------------
def test_a_coluna_mostra_o_override_do_disco_e_nao_o_degrau_da_mesa(a05) -> None:
    """O `state_full` não publica override nenhum — a fonte é o perfil.

    Sem esta metade, a tela voltaria a acender o mesmo degrau nas quatro colunas
    um tique depois de ela escolher quatro diferentes.

    MORDIDA: em `a05_vibracao._forca_da_coluna`, devolva sempre o global — este
    caso reprova, porque o P1 passa a dizer `balanceado` com `economia` no disco.
    """
    overrides = {CHAVE: {"rumble": {"policy": "economia"}}}
    state = {"rumble_policy": "balanceado", "rumble_mult_applied": None}

    assert a05._forca_da_coluna(overrides, UNIQ, state)[0] == "economia"
    # O VIZINHO SEM OPINIÃO HERDA A MESA, que é a precedência do produto.
    assert a05._forca_da_coluna(overrides, UNIQ_B, state)[0] == "balanceado"


def test_a_coluna_le_a_chave_normalizada_e_a_crua(a05) -> None:
    """`perfil.ativo` lê o JSON SEM o pydantic — um arquivo editado à mão pode
    trazer `aa:bb:…`, que o loader só canoniza quando alguém o CARREGA.

    MORDIDA: tire o `or overrides.get(uniq)` de `_forca_da_coluna` — este caso
    reprova na segunda asserção, e na tela dela um perfil editado à mão mostraria
    "segue o global" para sempre.
    """
    state = {"rumble_policy": "balanceado"}
    assert a05._forca_da_coluna(
        {CHAVE: {"rumble": {"policy": "max"}}}, UNIQ, state)[0] == "max"
    assert a05._forca_da_coluna(
        {UNIQ: {"rumble": {"policy": "max"}}}, UNIQ, state)[0] == "max"


def test_o_mult_pos_e_o_numero_cru_e_nao_a_largura(a05) -> None:
    """O `<input type=range>` posiciona o polegar pelo `value`, não pela largura.

    O `pct["w"]` do produto é `100 * valor / teto` — a FRAÇÃO da barra. Escrevê-lo
    no `value` de um range que vai a 200 poria o cursor em 75 quando o pedido é
    150.

    MORDIDA: em `a05_vibracao.pacote`, emita `pct["w"]` em `mult-pos` — este
    caso reprova.
    """
    pct = a05._pct_da_coluna("max", None)
    assert pct["n"] == "150%" and pct["sabe"] == "1"
    # a largura é a fração (150/200 = 75%); o `value` do range é 150.
    assert pct["w"] == "75.0%"


# ---------------------------------------------------------------------------
# 6. o DESENHO — a barra existe, e o teto e o passo são derivados
# ---------------------------------------------------------------------------
def test_o_desenho_tem_a_barra_arrastavel_com_o_teto_do_esquema() -> None:
    """Uma por coluna VIVA, com `max` do esquema e `step` que casa os degraus.

    TRÊS COISAS, e cada uma é um jeito diferente de a barra mentir: um `<div>`
    não tem `value` (o clique chega sem número), um `max` errado esconde ou
    inventa posições, e um `step` que não divide os degraus faz o botão
    "Máximo" escrever 150% num lugar onde a barra não consegue parar.

    MORDIDA: em `aba05._coluna`, tire o `arrasta=True` da linha do
    "Personalizado" e regere — este caso reprova por zero `<input>`.
    """
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT
    from hefesto_dualsense4unix.profiles.schema import RUMBLE_CUSTOM_MULT_MAX

    pagina = (RAIZ / "mockup/05-vibracao.html").read_text(encoding="utf-8")
    barras = re.findall(r'<input class="trilho arrasta"[^>]*>', pagina)
    assert barras, (
        "a barra 'Personalizado' voltou a ser um `<div>` — o ouvinte manda "
        "`valor: alvo.value ?? ''`, e um `<div>` não tem `value`")
    teto = round(RUMBLE_CUSTOM_MULT_MAX * 100)
    for tag in barras:
        assert f'max="{teto}"' in tag, f"o teto da barra não é o do esquema: {tag}"
        assert 'data-hef-alvo="valor"' in tag, (
            f"o alvo de pintura não é o `valor`: {tag}")
    passos = {int(m) for m in re.findall(r'step="(\d+)"', " ".join(barras))}
    assert len(passos) == 1, f"as barras têm passos diferentes: {sorted(passos)}"
    passo = passos.pop()
    for chave, mult in RUMBLE_POLICY_MULT.items():
        degrau = round(mult * 100)
        assert degrau % passo == 0 and degrau <= teto, (
            f"o degrau {chave!r} vale {degrau}% e a barra não para nele "
            f"(passo {passo}, teto {teto})")


# ---------------------------------------------------------------------------
# 7. a prova automática não escreve no perfil DELA
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("nome", ["forca", "intensidade"])  # (noqa-acento) id
def test_os_dois_gestos_que_gravam_ficam_de_fora_da_prova(nome: str) -> None:
    """Quem escreve no disco dela não entra na prova botão a botão.

    Em 03/09 a leva que clicou as dez abas deixou dez gravações no
    `meu_perfil.json` dela porque um gesto que grava não estava nesta lista.
    Estes dois passaram a gravar HOJE, e por decisão dela — a isenção é a outra
    metade da mesma decisão.

    MORDIDA: tire qualquer um dos dois de `hefesto_vivo.PERIGOSOS` — este caso
    reprova, e a próxima `--prova-gesto` escolhe uma vibração que ela não pediu
    em cada controle da mesa.
    """
    from hefesto_dualsense4unix.interface import hefesto_vivo, regua_do_mockup

    class _Gesto:
        def __init__(self, n: str) -> None:
            self.nome = n

    vistos, pulados = regua_do_mockup._alvos_a_clicar(
        [_Gesto(nome)], {nome}, "05-vibracao.html", hefesto_vivo.PERIGOSOS)
    assert nome in pulados and nome not in vistos, (
        f"a prova clicaria `{nome}` na Vibração — e esse clique grava no perfil "
        f"dela, sem diálogo e sem perguntar")


# ---------------------------------------------------------------------------
# 8. a cadeia inteira, do disco ao motor
# ---------------------------------------------------------------------------
def test_o_fator_que_chega_ao_motor_e_o_da_conta_do_produto(
        pac, clique_no_degrau, disco) -> None:
    """Do clique ao `_escalar_rumble`, sem nenhuma conta escrita por esta aba.

    Com a mesa em `balanceado` (1,0) e o P1 em `economia` (0,3), o fator
    RELATIVO é 0,3 — e é ele que o backend multiplica na saída daquele handle.
    O denominador é a política do PRÓPRIO perfil, e é por isso que o produto
    manda o relativo: o valor que chega ao `set_rumble` já vem escalado pela
    global, e um fator absoluto escalaria duas vezes.

    MORDIDA: grave `policy="max"` em vez do degrau clicado — este caso reprova
    com 1,5 no lugar de 0,3.
    """
    from hefesto_dualsense4unix.profiles.manager import _controllers_to_rumble_scales

    estado, gravados = disco
    estado["Bancada"] = _perfil_de_verdade(rumble={"policy": "balanceado"})
    clique_no_degrau(_ctx(pac), {"uniq": UNIQ, "forca": "economia"},
                     PonteDeMentira())

    prof = gravados[0]
    escalas = _controllers_to_rumble_scales(prof.controllers, prof.rumble)
    assert escalas == pytest.approx({CHAVE: 0.3}), (
        f"o motor receberia {escalas} — a escolha dela é 30% da força")
