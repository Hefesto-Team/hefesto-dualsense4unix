#!/usr/bin/env python3
"""A ABA VIBRAÇÃO fecha as quatro decisões dela de 04/09/2026.

O que esta régua mede, e nenhuma linha dela é digitada — os números vêm do
esquema, os textos vêm do produto e o desenho vem da BANCADA:

1. **AS DUAS BARRAS DE MOTOR VIRARAM AJUSTE** (decisão dela, fora  # noqa-acento: citação dela
   das três opções que eu ofereci): *"os slcers do botão esquerdo e
   direito (forte e fraco) se multiplicam"*. A barra não manda o par
   ``rumble.set`` — ela é
   POLÍTICA, e ``efetivo(motor) = degrau x barra(motor)``. Esta régua cobre as
   DUAS metades: o desenho (o ``<input type=range>`` com o lado) e o gesto (o
   ``rumble.motores.set`` com UM campo só).
2. **A FAIXA "Estado" SAIU** — decisão dela, 05/09/2026. Era a D-14 (uma linha
   de estado por coluna, com os três estados que ela nomeou), e a régua que a
   EXIGIA passou a guardar a REMOÇÃO: regra desta casa, régua que cobrava o que
   saiu se inverte, não se apaga.
3. **A LINHA DE MESA** (decisão [05]) e o "herdado" que ela torna legível: a
   coluna sem ajuste próprio deixa de acender degrau.
4. **A NOTA DO TESTAR NA TELA** (decisão [02]) — e uma vez só.

**O DUBLÊ DAQUI É FIEL, e é a razão de este arquivo existir em vez de uma linha
no ``PROVAS``.** A ``PonteDeMentira`` da régua geral responde ``True`` a
qualquer nome, e ``rumble_motores_set`` devolve ``(ok, corpo)``: um gesto
provado contra aquele dublê teria de ser afrouxado para caber nele. Esta casa
mediu esse defeito DUAS VEZES em 04/09 — *"nos dois casos o dublê do teste era
mais frouxo que a ponte real"* —, e as duas vezes o gesto passou VERDE sem
gravar um byte.

ONDE ELA MEDE: na **BANCADA** (``mockup/``), que é onde o gerador escreve. A
publicação é ato DELA, e até lá a página que o produto renderiza continua com as
duas linhas de motor como LEITURA — está em ``mockup/DIVERGENCIAS.md``.
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

from hefesto_dualsense4unix.app.telas import vibracao as _tela
from hefesto_dualsense4unix.profiles.schema import (
    MOTOR_PCT_MAX,
    MOTOR_PCT_PADRAO,
)

PAGINA = "05-vibracao.html"

#: MAC da faixa SINTÉTICA da casa — há dois portões de anonimato nesta árvore.
UNIQ = "aa:bb:cc:00:00:01"

#: A GRAFIA COM QUE O DAEMON CHAVEIA O MAPA: doze hexa, sem dois-pontos e em
#: minúscula (`gamepad._chave_da_peca`). Ela NÃO se digita aqui — sai do mesmo
#: normalizador que o produto usa, senão esta régua passaria a provar a minha
#: cópia da regra em vez da do produto.
def _chave(uniq: str) -> str:
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    return norm_mac(uniq) or ""


class PonteFiel:
    """Um dublê que devolve o que a ponte REAL devolve, forma por forma.

    ``rumble_motores_set`` devolve ``(ok, corpo)`` e o corpo traz ``status`` —
    é o contrato de `app/ipc_bridge`, e ele existe porque a recusa do daemon vem
    no CORPO, não como erro JSON-RPC. Um dublê que respondesse ``True`` deixaria
    o gesto anunciar "gravado" sobre um ``sem_perfil``.
    """

    def __init__(self, status: str = "ok", motivo: str = "") -> None:
        self.chamadas: list[tuple[str, tuple, dict]] = []
        self.status, self.motivo = status, motivo

    def rumble_motores_set(self, **kw: Any) -> tuple[bool, dict[str, Any]]:
        self.chamadas.append(("rumble_motores_set", (), kw))
        corpo: dict[str, Any] = {"status": self.status, "uniq": kw.get("uniq")}
        if self.motivo:
            corpo["motivo"] = self.motivo
        return True, corpo

    def rumble_policy_set_checked(self, policy: str) -> tuple[bool, str | None]:
        self.chamadas.append(("rumble_policy_set_checked", (policy,), {}))
        return (True, None) if self.status == "ok" else (False, self.motivo)

    def __getattr__(self, nome: str):
        def registrar(*a: Any, **kw: Any) -> bool:
            self.chamadas.append((nome, a, kw))
            return True
        return registrar


def _gesto(nome: str):
    import pacotes

    fn = pacotes.gesto_da_pagina(PAGINA, nome)
    assert fn is not None, f"{PAGINA}:{nome} não tem dono"
    return fn


def _ctx(**estado: Any):
    """Um tique de mentira com UM controle. O pacote não toca o aparelho."""
    import pacotes

    base = {"rumble_policy": "balanceado", "rumble_mult_applied": 0.7,
            "active_profile": "regua"}
    base.update(estado)
    falso = {"uniq": UNIQ, "player": 1, "connected": True, "index": 0,
             "transport": "usb", "battery_pct": 90, "is_primary": True,
             "inputs": {}}
    mesa = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
             "via": "USB", "cor": "starlight-blue", "plastico": "#123456",
             "conectado": True}]
    return pacotes.Contexto(state=base, mesa=mesa, conectados=[falso],
                            estados={})


@pytest.fixture(scope="module")
def bancada() -> str:
    import onde

    arq = onde.pagina(PAGINA)
    assert arq.exists(), f"a bancada não tem {PAGINA} — rode `python3 aba05.py`"
    return arq.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def a05():
    import pacotes.a05_vibracao as mod

    return mod


# --------------------------------------------------------------------------
# 1. A BARRA DE MOTOR — o gesto
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("lado", "campo", "outro"),
                         [("e", "forte_pct", "fraco_pct"),
                          ("d", "fraco_pct", "forte_pct")])
def test_a_barra_de_motor_grava_um_lado_so(lado: str, campo: str, outro: str) -> None:
    """Arrastar UM punho manda UM campo — e o outro fica intacto.

    É o contrato do método, e é o caso DELA: *"se so a do  # noqa-acento: citação dela
    motor fraco tiver 100 e a outrqa 50%"*. `rumble.motores.set`
    deixa intacta a barra cujo campo for
    omitido, e mandar os dois faria um arraste no punho esquerdo reescrever o
    direito com o número que a TELA mostrava — que pode estar um tique atrás.

    E O LADO CERTO NÃO SE ADIVINHA: `weak` é o motor da DIREITA, e a inversão é
    a armadilha deste assunto. A tradução tem dono
    (`app/telas/vibracao.LADO_PARA_MOTOR` e `.MOTOR_PARA_BARRA`).

    MORDIDA: em `a05_vibracao.motor`, troque `_tela.MOTOR_PARA_BARRA[...]` por
    um literal `"forte_pct"` — o caso do lado `d` reprova, porque o arraste do
    punho DIREITO passa a gravar a barra do esquerdo.
    """
    p = PonteFiel()
    _gesto("motor")(_ctx(), {"uniq": UNIQ, "lado": lado, "valor": "50"}, p)

    assert [c[0] for c in p.chamadas] == ["rumble_motores_set"], (
        f"o gesto chamou {[c[0] for c in p.chamadas]} — a barra de motor grava "
        f"pelo `rumble.motores.set`, e nada mais")
    kw = p.chamadas[0][2]
    assert kw.get(campo) == 50, (
        f"o lado {lado!r} gravou {kw!r}, e ele é o campo {campo!r}")
    assert outro not in kw, (
        f"o gesto mandou também o {outro!r} — a barra que ela NÃO arrastou tem "
        f"de ficar intacta, e é o contrato do método")
    assert kw.get("uniq") == UNIQ, (
        "o gesto gravou sem endereço — sem `uniq` o método cai no primário, e a "
        "escolha iria para o controle errado")


def test_a_barra_de_motor_aceita_o_zero() -> None:
    """`0` é ESCOLHA VÁLIDA: *"este motor não treme neste perfil"*.

    Confundir "zero" com "não sei" é o defeito que a `MIGRA-VIBRACAO-01` nomeia,
    e aqui ele teria a forma mais barata: um `if not pontos` engoliria o zero e
    o gesto voltaria calado, com a barra da tela em 0 e o perfil intacto.

    MORDIDA: em `a05_vibracao.motor`, troque `if not bruto:` por
    `if not pontos:` — este caso reprova, porque o zero deixa de gravar.
    """
    p = PonteFiel()
    _gesto("motor")(_ctx(), {"uniq": UNIQ, "lado": "e", "valor": "0"}, p)
    assert p.chamadas and p.chamadas[0][2].get("forte_pct") == 0, (
        f"o zero não chegou ao método: {p.chamadas!r}")


def test_a_barra_de_motor_diz_a_recusa_do_daemon() -> None:
    """A recusa vem no CORPO, e sobe como frase de tela.

    É a lição do NATIVO-RUMBLE-01: quem lê só o `ok` da ponte anuncia "gravado"
    sobre um `sem_perfil`. O `rumble_motores_set` devolve `(ok, corpo)` e o
    corpo traz `status` e `motivo` — a ponte devolve o corpo INTEIRO de
    propósito (*"invólucro que estreita faz a tela re-deduzir o que o daemon já
    sabia"*).

    E A FRASE TEM DE SER `RuntimeError`, não `ValueError`: o contrato do piloto
    manda `RuntimeError` ao CARTÃO dela e deixa `ValueError` no `stderr` de quem
    lançou a janela.

    MORDIDA: em `a05_vibracao.motor`, apague o bloco `if str(resposta.get
    ("status")…)` — este caso reprova, porque o gesto volta calado sobre uma
    gravação que não aconteceu.
    """
    p = PonteFiel(status="sem_perfil", motivo="não há perfil ativo agora")
    with pytest.raises(RuntimeError) as recusa:
        _gesto("motor")(_ctx(), {"uniq": UNIQ, "lado": "e", "valor": "50"}, p)
    assert "perfil" in str(recusa.value), (
        f"a frase do daemon não subiu: {recusa.value!r}")


def test_a_barra_de_motor_recusa_o_clique_sem_lado() -> None:
    """Sem punho não há qual das duas — e adivinhar gravaria a errada."""
    p = PonteFiel()
    with pytest.raises(RuntimeError):
        _gesto("motor")(_ctx(), {"uniq": UNIQ, "valor": "50"}, p)
    assert not p.chamadas, "o gesto mandou alguma coisa sem saber qual barra"


# --------------------------------------------------------------------------
# 2. A BARRA DE MOTOR — a leitura de volta
# --------------------------------------------------------------------------
def test_a_barra_le_de_volta_o_mapa_do_daemon(a05) -> None:
    """O que o `state_full` publica é o que a barra desenha.

    Sem esta metade a aba desenha a barra onde ela ESTAVA, não onde ela está: o
    gesto grava, o perfil muda, e o cursor fica onde o mockup o pôs. A fonte é
    `state_full.rumble_motores`, que a ONDA1-D2 publicou a partir do MESMO mapa
    que `apply_game_rumble` multiplica.

    MORDIDA: em `a05_vibracao._barras_dos_motores`, devolva sempre o padrão —
    este caso reprova, porque as duas barras voltam a 100 com o daemon dizendo
    outra coisa.
    """
    estado = {"rumble_motor_pct_padrao": MOTOR_PCT_PADRAO,
              "rumble_motores": {_chave(UNIQ): {"forte_pct": 50,
                                                "fraco_pct": 100}}}
    assert a05._barras_dos_motores(estado, UNIQ) == {"e": 50, "d": 100}, (
        "o mapa do daemon não chegou às duas barras — e `e` é o FORTE, que é o "
        "motor da esquerda")


def test_a_peca_sem_opiniao_vale_o_padrao_do_daemon(a05) -> None:
    """Quem não está no mapa vale o `rumble_motor_pct_padrao`, e ele NÃO se digita.

    Só quem tem opinião entra no mapa (a mesma disciplina do
    `set_rumble_scales`), e o valor de quem não tem chega ao lado, publicado
    pelo daemon. Escrever `100` na interface seria a segunda cópia do
    `MOTOR_PCT_PADRAO` do esquema.

    MORDIDA: em `_barras_dos_motores`, troque o `int` do padrão por `100` — este
    caso continua passando **hoje** (os dois valem 100) e reprova no dia em que
    o esquema mudar, que é exatamente quando importa. Por isso a régua também
    compara com o esquema, abaixo.
    """
    estado = {"rumble_motor_pct_padrao": 77, "rumble_motores": {}}
    assert a05._barras_dos_motores(estado, UNIQ) == {"e": 77, "d": 77}, (
        "a barra da peça sem opinião não veio do padrão que o daemon publicou")
    assert MOTOR_PCT_PADRAO == 100, (
        "o padrão do esquema mudou — confira quem ainda o digita")


def test_a_chave_do_mapa_casa_nas_duas_grafias(a05) -> None:
    """`aa:bb:…` e `aabb…` acham a mesma peça — senão o mapa fica MUDO em silêncio.

    O daemon chaveia pelo MAC normalizado (`gamepad._chave_da_peca`) e a mesa
    pode trazer o endereço com dois-pontos. Uma leitura que só tentasse uma
    grafia devolveria o padrão para uma peça que TEM opinião — e a barra voltaria
    sozinha para 100 no tique seguinte ao clique dela.

    MORDIDA: em `_barras_dos_motores`, apague o `or mapa.get(uniq)` — este caso
    reprova no ramo da grafia com dois-pontos.
    """
    for chave in (_chave(UNIQ), UNIQ):
        estado = {"rumble_motor_pct_padrao": MOTOR_PCT_PADRAO,
                  "rumble_motores": {chave: {"forte_pct": 30}}}
        lido = a05._barras_dos_motores(estado, UNIQ)
        assert lido["e"] == 30, f"a grafia {chave!r} não casou: {lido}"


# --------------------------------------------------------------------------
# 3. A BARRA DE MOTOR — o desenho
# --------------------------------------------------------------------------
def test_o_desenho_tem_as_duas_barras_de_motor(bancada: str) -> None:
    """Duas por coluna VIVA, com o lado, o teto do esquema e passo 1.

    QUATRO COISAS, e cada uma é um jeito de a linha voltar a mentir: sem
    `<input>` o clique chega sem número; sem `data-lado` o gesto grava a barra
    errada; com `max` acima de `MOTOR_PCT_MAX` a mesma peça ganha duas portas
    para o mesmo estouro; e com `step` maior que 1 a barra esconde valores que a
    borda aceita sem reclamar.

    MORDIDA: em `aba05._coluna`, troque `_barra_de_motor(...)` pelo `_barra(...)`
    de leitura e regere — este caso reprova por zero `<input>` de motor.
    """
    vivas = bancada.count('<div class="ctrl" data-controle=')
    assert vivas >= 1, "a bancada não tem coluna viva — a régua viraria vácuo"
    barras = [t for t in re.findall(r'<input class="trilho arrasta"[^>]*>', bancada)
              if 'data-papel="motor"' in t]
    assert len(barras) == 2 * vivas, (
        f"as barras de motor são {len(barras)} e as colunas vivas são {vivas} — "
        f"cada coluna tem UMA por punho")
    for sigla in ("e", "d"):
        do_lado = [t for t in barras if f'data-lado="{sigla}"' in t]
        assert len(do_lado) == vivas, (
            f"a barra do motor {sigla!r} não tem `data-lado` em cada coluna")
        for tag in do_lado:
            assert f'data-campo="barra-{sigla}"' in tag, (
                f"o endereço de pintura não é o novo: {tag}")
            assert 'data-hef-alvo="valor"' in tag, (
                f"o alvo não é o `valor` — num `<input>` o texto não desenha: {tag}")
    for tag in barras:
        assert f'max="{MOTOR_PCT_MAX}"' in tag, (
            f"o teto não é o `MOTOR_PCT_MAX` do esquema: {tag}")
        assert 'step="1"' in tag, (
            f"o passo esconde valores que a borda aceita: {tag}")


def test_o_endereco_velho_do_motor_continua_sendo_emitido(a05) -> None:
    """`motor-e` e `motor-e-pct` NÃO saíram do pacote — e é a ponte de publicação.

    A página que ela ABRE hoje ainda tem a linha de motor como LEITURA, com
    estes dois endereços. Tirá-los deixaria o produto dela com dois números
    congelados no que o mockup cravou — a mentira que esta aba mais persegue.
    Eles saem no dia em que a `05-vibracao` deixar a `DIVERGENCIAS.md`.

    MORDIDA: em `a05_vibracao.pacote`, apague as duas linhas `plano[f"motor-
    {lado}"...]` — este caso reprova, e o defeito seria invisível na bancada.
    """
    import pacotes

    carga = pacotes.pacote_da_pagina(PAGINA, _ctx())
    col = next(iter(carga["colunas"].values()))
    for lado in ("e", "d"):
        for chave in (f"motor-{lado}", f"motor-{lado}-pct",
                      f"barra-{lado}", f"barra-{lado}-pct"):
            assert chave in col, f"o pacote deixou de emitir {chave!r}"
        assert "%" not in str(col[f"motor-{lado}-pct"]), (
            "a largura saiu com `%` — o pintor acrescenta o dele")


# --------------------------------------------------------------------------
# 4. A FAIXA "Estado" SAIU — decisão dela, 05/09/2026
# --------------------------------------------------------------------------
def test_a_faixa_de_estado_nao_existe_mais_no_desenho(bancada: str) -> None:
    """Nem a célula, nem o rótulo da coluna de rótulos, nem a faixa da grade.

    **DECISÃO DELA, 05/09/2026, verbatim:** *"pq temos uma linha de estado se o
    estado em vibração sempre vai ser o jogo mandando os input pro controle e a
    gnt aumentando eles ou diminuindo? remove ela não faz sentido"*.

    **ELA TEM RAZÃO MEDIDA pelo caminho que ela usa**, e é por isso que esta
    régua guarda a remoção em vez de a lamentar. A faixa tinha três estados
    (`estado_da_trava`) e os dois "travada" precisam de `rumble_active` armado.
    Os DOIS gestos desta aba terminam em `rumble_passthrough(True)` —
    `a05_vibracao.testar` (passos 3 e 4) e `a05_vibracao.parar` —, que solta o
    par. Quem arma e DEIXA armado é a janela GTK (lá o "Parar" é botão separado
    do "Devolver ao jogo") ou `hef test rumble`. O próprio `?` da faixa
    confessava isso: *"Esta aba não trava — quem trava é a janela do Hefesto ou
    a linha de comando."*

    OS TRÊS ENDEREÇOS, e não só o primeiro: apagar o `<div>` e deixar o
    `data-campo="trava"` vivo noutro canto seria campo emitido para endereço que
    a página não tem — escrita em lugar nenhum, calada.

    MORDIDA: devolva o `monta_.ressalva("trava", …)` a `aba05._coluna`, ou o
    rótulo `Estado` à `.rotulos`, e este caso reprova.
    """
    for morto in ('data-campo="trava"', '<span class="sec-rot">Estado'):
        assert morto not in bancada, (
            f"{morto!r} voltou ao desenho da aba 05 — a faixa de estado saiu em "
            f"05/09/2026 por decisão dela")


def test_a_grade_da_vibracao_tem_sete_faixas(bancada: str) -> None:
    """A `grid-template-rows` perdeu a oitava, e a variável do piso foi junto.

    O CSS É A OUTRA METADE DA REMOÇÃO: uma faixa sem células continua reservando
    altura, e altura reservada para linha que não existe é rolagem paga por
    nada. MEDIDO no WebKit da janela do produto em 05/09/2026: o miolo rolava
    74 px e passou a rolar 43 — 31 px devolvidos.

    MORDIDA: devolva `minmax(var(--r-estado),auto)` à `grid-template-rows` da
    `.vib > div` — este caso reprova.
    """
    assert "--r-estado" not in bancada, (
        "a variável do piso da faixa de estado voltou à folha da aba 05")
    assert bancada.count("var(--r-motor) var(--r-motor) var(--r-acoes);") == 1, (
        "a grade da aba 05 deixou de terminar no `--r-acoes` — a oitava faixa "
        "saiu em 05/09/2026 e a `grid-template-rows` foi junto")


def test_o_pacote_nao_emite_mais_o_campo_da_trava() -> None:
    """O campo sai com o endereço — senão é escrita em lugar nenhum, calada.

    Um `plano["trava"]` sobrevivente pintaria um `data-campo="trava"` que a
    página não tem mais: o pintor procura, não acha, e não diz nada. É o defeito
    que esta casa persegue, e ele é INVISÍVEL na tela — só uma régua o vê.

    MORDIDA: devolva o `plano["trava"] = …` a `a05_vibracao.pacote` — este caso
    reprova.
    """
    import pacotes

    carga = pacotes.pacote_da_pagina(PAGINA, _ctx())
    col = next(iter(carga["colunas"].values()))
    assert "trava" not in col, (
        f"o pacote voltou a emitir o campo `trava`: {col.get('trava')!r}")


def test_as_cinco_pecas_da_trava_morreram_com_a_faixa() -> None:
    """A camada de produto da trava saiu junto — ela era desta aba e de mais
    nenhuma.

    **NÃO FUI EU QUEM MEDIU ISSO**, e é o que torna a remoção segura: assim que
    a faixa saiu, o `portao_a_casa_sabe_e_o_produto_nao_faz` reprovou nomeando
    `estado_da_trava` e `html_da_trava` como *promessas públicas sem chamador em
    produção*. A janela estável nunca as chamou — ela tem a sua própria linha
    (`app/actions/rumble_actions._update_rumble_state_label`), com as suas
    próprias palavras —, e o `SOLTAR_A_TRAVA` mandava clicar no "Parar nesta
    coluna", que só existe no HTML.

    MORDIDA: devolva qualquer uma das cinco a `app/telas/vibracao.py` sem
    chamador — este caso reprova, e o portão da casa reprova junto.
    """
    for morta in ("TRAVA_JOGO_CONTROLA", "TRAVA_EM_SILENCIO", "estado_da_trava",
                  "SOLTAR_A_TRAVA", "html_da_trava"):
        assert not hasattr(_tela, morta), (
            f"`{morta}` voltou a `app/telas/vibracao.py`. As cinco nasceram em "
            f"04/09/2026 para a faixa de estado da aba 05, que saiu em 05/09 "
            f"por decisão dela — sem ela, não há quem as chame no produto.")


# --------------------------------------------------------------------------
# 5. A LINHA DE MESA SAIU — decisão dela, 05/09/2026
# --------------------------------------------------------------------------
def test_a_linha_de_mesa_nao_existe_mais() -> None:
    """A linha de mesa e o gesto dela saíram da aba — e não voltam calados.

    **DECISÃO DELA, 05/09/2026, verbatim:** *"não é pra ter mesa em nada da
    interface. (…) segue os três modos sempre. clicou em perfil de energia
    econômico na aba sistema todos vão pra vibração manual. o resto é
    desnecessário e só polui e deixa difícil entender"*.

    ELA TEM RAZÃO MEDIDA, e é por isso que esta régua guarda a remoção em vez de
    a lamentar: a economia de bateria JÁ tem dono — o Perfil de Bateria da aba
    09 grava `orcamento.teto`, e `core.rumble._effective_mult` aplica
    `min(modo escolhido, teto)`, nunca produto (`_sob_o_teto`). O perfil
    econômico já limitava todo mundo no nível Economia. O `Auto` era um SEGUNDO
    dono do mesmo trabalho, numa aba diferente, com outra conta.

    E OS 33 PERFIS DELA NUNCA O USARAM: medido em 05/09/2026, a política global
    é `None` nos 33 e nenhum controle tem `policy: auto`.

    MORDIDA: devolva o `@gesto("05-vibracao.html", "forca-mesa")` a
    `a05_vibracao`, ou o bloco `.vib-mesa` a `aba05.MIOLO`, e este caso reprova.
    """
    import pacotes

    assert (PAGINA, "forca-mesa") not in pacotes.GESTOS, (
        "o gesto `forca-mesa` voltou. Ele saiu com a linha de mesa em "
        "05/09/2026, e a razão não caducou.")


def test_o_desenho_nao_tem_linha_de_mesa_nem_o_auto(bancada: str) -> None:
    """Nem o bloco, nem o endereço, nem o quarto botão.

    OS TRÊS ENDEREÇOS, e não só o primeiro: apagar o `<div>` e deixar o
    `data-campo="degrau-mesa"` vivo noutro canto seria campo emitido para
    endereço que a página não tem — escrita em lugar nenhum, calada. É o defeito
    que esta casa persegue, e uma régua que só olhasse a classe não o veria.
    """
    for morto in ('class="vib-mesa"', 'data-campo="degrau-mesa"',
                  'data-papel="forca-mesa"'):
        assert morto not in bancada, (
            f"{morto!r} voltou ao desenho da aba 05 — a linha de mesa saiu em "
            f"05/09/2026 por decisão dela")
    assert 'data-forca="auto"' not in bancada, (
        "o botão `Auto` voltou à aba da vibração. Ele nunca pôs peça nenhuma em "
        "Auto — o esquema o recusa por unidade, e o clique significava `limpa o "
        "meu ajuste e segue o global`. O rótulo dizia uma coisa e o ato era "
        "outra; um botão a menos é uma mentira a menos.")


def test_a_coluna_oferece_os_tres_modos(bancada: str) -> None:
    """TRÊS botões por coluna, e os três são os de `RUMBLE_POLICY_MULT`.

    A régua LÊ a tabela do produto em vez de digitar os três nomes: no dia em
    que o daemon acrescentar um degrau, ela cobra o botão em vez de dar verde
    sobre uma tela desatualizada.
    """
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT
    from hefesto_dualsense4unix.interface import aba05

    assert {c for _, c in aba05.FORCA} == set(RUMBLE_POLICY_MULT), (
        f"os degraus da aba são {sorted(c for _, c in aba05.FORCA)} e o produto "
        f"tem {sorted(RUMBLE_POLICY_MULT)}")
    for chave in RUMBLE_POLICY_MULT:
        assert f'data-forca="{chave}"' in bancada, (
            f"o degrau {chave!r} não está no desenho")


def test_a_coluna_sem_ajuste_proprio_nao_acende_degrau() -> None:
    """"Herdado" fica óbvio sem palavra nova — e é a decisão [05] dela.

    O perfil desta cena não tem override nenhum, então a coluna HERDA: o campo
    sai vazio, o alvo `classe` apaga os quatro, e o único degrau aceso na tela é
    o da linha de mesa.

    MORDIDA: em `a05_vibracao.pacote`, volte a emitir o degrau da coluna sem a
    guarda do ajuste próprio (`"degrau": <a força efetiva>`) — este
    caso reprova, e a tela volta a ter a mesma cara para "escolha dela" e para
    "o que o Hefesto está usando".
    """
    import pacotes

    carga = pacotes.pacote_da_pagina(PAGINA, _ctx())
    col = next(iter(carga["colunas"].values()))
    assert col["degrau"] == "", (
        f"a coluna acendeu {col['degrau']!r} sem ter ajuste próprio")
    # A MESA NÃO EMITE MAIS CAMPO NENHUM — 05/09/2026. Ela emitiu
    # `degrau-mesa` entre 04/09 e 05/09, enquanto a linha existiu na tela; com
    # ela fora, um campo emitido para endereço que a página não tem seria
    # escrita em lugar nenhum. O que esta régua ainda cobra é o que importava
    # desde sempre: a coluna sem ajuste próprio NÃO acende degrau.
    assert carga["mesa"] == {}, (
        f"a mesa desta aba voltou a emitir {sorted(carga['mesa'])} — a linha "
        f"que esses campos pintavam saiu em 05/09/2026")


# --------------------------------------------------------------------------
# 6. A NOTA DO TESTAR — decisão [02]
# --------------------------------------------------------------------------
def test_a_nota_do_testar_e_linha_de_tela(bancada: str) -> None:
    """Ela sobe do `?` para a tela — e aparece UMA vez.

    É a única frase desta aba que explica um resultado que a própria tela
    produz: por que um "Testar" com 220 sai fraco quando o degrau está em
    Economia. E ela é LIDA do `gui/main.glade`, nunca redigitada.

    MORDIDA: em `aba05.MIOLO`, tire o `<div class="vib-nota">` e regere — a
    régua 16 do gerador reprova antes desta.
    """
    import aba05

    assert f'class="vib-nota">{aba05.DICA_DOS_VALORES_QUE_PASSAM}' in bancada, (
        "a nota do Testar não é linha de tela")
    assert bancada.count(aba05.DICA_DOS_VALORES_QUE_PASSAM) == 1, (
        "a nota do Testar aparece duas vezes na mesma tela — o `?` e a linha")
    # A OUTRA METADE DA DECISÃO [02] ERA A DICA DOS 5 s DO AUTO, no `?`. Ela
    # saiu com o Auto em 05/09/2026: dica que explica um botão que não existe é
    # texto ensinando algo que a tela não faz.
    assert "Espera 5 segundos" not in bancada, (
        "a dica dos 5 s do Auto voltou ao desenho — o botão que ela explicava "
        "saiu em 05/09/2026")


# --------------------------------------------------------------------------
# 7. O RECADO DE SUCESSO — decisão [04] / D-01
# --------------------------------------------------------------------------
def test_o_aviso_do_que_a_coluna_mostra_e_sucesso_e_nao_recusa(a05) -> None:
    """A gravação aconteceu: o canal é o de SUCESSO, não o da recusa.

    Enquanto só existia o canal da recusa, um clique que deu certo pousava uma
    tarja LARANJA de 30 s no cartão dela — que ensina que o botão falha. A
    ONDA0-P construiu o canal de sucesso (verde, 6 s), e um gesto que devolva
    `{"recado": …}` manda a própria frase.

    MORDIDA: em `_aplicar_a_forca`, troque os três `return {"recado": …}` por
    `raise RuntimeError(…)` — este caso reprova, e o piloto volta a anotar
    `("recusou dizendo", …)` sobre um disco que mudou.
    """
    import inspect

    fonte = inspect.getsource(a05._aplicar_a_forca)
    assert 'return {"recado":' in fonte, (
        "o aviso do que a coluna mostra voltou a ser recusa — a gravação "
        "aconteceu, e a tarja laranja de 30 s ensina que o botão falha")
    assert "raise RuntimeError" not in fonte, (
        "sobrou uma recusa em `_aplicar_a_forca`: os três desfechos dele são "
        "recibos, não recusas")
