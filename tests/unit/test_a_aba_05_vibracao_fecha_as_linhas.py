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
4. **A NOTA DO TESTAR NA DICA** (05-Q2 dela, 05/09/2026: *"As duas na dica."*)
   — e uma vez só. Ela era linha permanente de tela entre 04/09 e 05/09, por
   uma decisão do PO atribuída a ela; a régua não foi apagada nem reescrita em
   massa: o ``count == 1`` ficou byte a byte, porque ele proíbe a frase de
   existir em dois lugares **seja qual for o lugar escolhido**.

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

#: O SEGUNDO CONTROLE, e ele existe por uma régua só: com um controle na mesa,
#: `P1` sai por coincidência — qualquer contagem acerta. Com dois, só o
#: `jogador` do item de mesa dá `P2`.
OUTRO = "aa:bb:cc:00:00:02"

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


def _perfil_do_esquema(nome: str = "regua", **campos: Any):
    """Um `Profile` DE VERDADE — o esquema é metade do que esta régua mede.

    Um dublê aceitaria `policy="furrufu"` e a régua ficaria verde sobre um
    perfil que o loader recusaria no disco dela.
    """
    from hefesto_dualsense4unix.profiles.schema import Profile

    return Profile.model_validate(
        {"name": nome, "match": {"type": "criteria"}, **campos})


@pytest.fixture
def disco(monkeypatch):
    """Um disco de mentira: guarda o que o gesto mandou gravar.

    ELE PRECISOU EXISTIR NESTE ARQUIVO — 06/09/2026. As réguas da faixa CHAMAM
    o gesto e olham o que volta, em vez de ler o texto do código, e `forca`
    grava no perfil antes de dizer qualquer coisa. Sem o dublê, a régua tocaria
    o `~/.config` de verdade — que é o que o `conftest.py` desvia para um lar de
    mentira, mas gravar nele mesmo assim é escrever fora do escopo.
    """
    from hefesto_dualsense4unix.profiles import loader

    gravados: list[Any] = []
    estado: dict[str, Any] = {}
    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n],
                        raising=False)
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **_: gravados.append(prof), raising=False)
    return estado, gravados


def _ctx_dois(**estado: Any):
    """Dois controles na tela, e o SEGUNDO é o `jogador` 2.

    A MESA TEM `jogador` E `pref`, e os dois são coisas diferentes: `pref` é a
    posição (`p1`..`p4`) e `jogador` é o número que a coluna MOSTRA no rótulo.
    A régua da faixa exige o segundo.
    """
    import pacotes

    base = {"rumble_policy": "balanceado", "rumble_mult_applied": 0.7,
            "active_profile": "regua"}
    base.update(estado)
    mesa = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
             "via": "USB", "cor": "starlight-blue", "plastico": "#123456",
             "conectado": True},
            {"pref": "p2", "jogador": 2, "uniq": OUTRO, "nome": "Régua II",
             "via": "BT", "cor": "midnight-black", "plastico": "#123456",
             "conectado": True}]
    conectados = [{"uniq": UNIQ, "player": 1, "connected": True, "index": 0,
                   "transport": "usb", "battery_pct": 90, "is_primary": True,
                   "inputs": {}},
                  {"uniq": OUTRO, "player": 2, "connected": True, "index": 1,
                   "transport": "bt", "battery_pct": 80, "is_primary": False,
                   "inputs": {}}]
    return pacotes.Contexto(state=base, mesa=mesa, conectados=conectados,
                            estados={})


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
    """Duas por LUGAR da mesa, com o lado, o teto do esquema e passo 1.

    QUATRO COISAS, e cada uma é um jeito de a linha voltar a mentir: sem
    `<input>` o clique chega sem número; sem `data-lado` o gesto grava a barra
    errada; com `max` acima de `MOTOR_PCT_MAX` a mesma peça ganha duas portas
    para o mesmo estouro; e com `step` maior que 1 a barra esconde valores que a
    borda aceita sem reclamar.

    A CONTA ERA "POR COLUNA VIVA" ATÉ 07/09/2026, e a troca é cura de defeito
    medido com os quatro DualSense dela na mesa: o lugar vazio era um cartão à
    parte, sem um único `data-campo`, e as duas barras do P3 e do P4 não
    existiam — o `barra-e`/`barra-d` que o pacote emite para os quatro lugares
    chegava sem ter onde pousar. Num lugar vazio a barra é `display:none` pela
    folha, então ela não recebe clique; ela existe para o instante em que o
    controle chega, sem regerar HTML nenhum.

    MORDIDA: em `aba05._coluna`, troque `_barra_de_motor(...)` pelo `_barra(...)`
    de leitura e regere — este caso reprova por zero `<input>` de motor.
    """
    from hefesto_dualsense4unix.interface import aba05
    lugares = len(aba05.MESA)
    assert bancada.count('data-controle="p') == lugares, (
        f"a bancada não tem os {lugares} lugares — a régua viraria vácuo")
    barras = [t for t in re.findall(r'<input class="trilho arrasta"[^>]*>', bancada)
              if 'data-papel="motor"' in t]
    assert len(barras) == 2 * lugares, (
        f"as barras de motor são {len(barras)} e os lugares são {lugares} — "
        f"cada lugar tem UMA por punho")
    for sigla in ("e", "d"):
        do_lado = [t for t in barras if f'data-lado="{sigla}"' in t]
        assert len(do_lado) == lugares, (
            f"a barra do motor {sigla!r} não tem `data-lado` em cada lugar")
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
# 6. A NOTA DO TESTAR — 05-Q2
# --------------------------------------------------------------------------
def test_a_nota_do_testar_mora_na_dica(bancada: str) -> None:
    """Ela volta da tela para o `?` do "Testar agora" — e aparece UMA vez.

    **05-Q2 dela, 05/09/2026: _"As duas na dica."_** Ela leu as quatro opções
    — as duas na dica, só a nota do Testar, a do Automático quando valer, as
    duas na tela — e escolheu a primeira. Até 05/09 o produto fazia a segunda,
    e aquilo estava escrito como *"decisão [02] dela, 04/09/2026"* em quatro
    lugares: a fonte real era a `ONDA2-05-VIBRACAO-01`, que decidiu no lugar
    dela. **A palavra dela vence a atribuição.**

    O QUE NÃO MUDOU, e é a metade da razão de 04/09 que não caducou: a frase é
    LIDA do `gui/main.glade` (`DICA_DOS_VALORES_QUE_PASSAM`), nunca redigitada.
    Esta régua a compara com o que o glade diz AGORA, e por isso ela não
    sobrevive a uma segunda cópia do texto.

    O ENDEREÇO É A CÉLULA DO RÓTULO, não a página: perguntar `frase in bancada`
    daria verde com ela de volta na linha embaixo da grade.

    MORDIDA: em `aba05.MIOLO`, devolva a linha
    `<div class="vib-nota">{DICA_DOS_VALORES_QUE_PASSAM}</div>` depois da
    `.vib` e regere — a régua 16 do gerador reprova antes desta, pelo
    `count == 1`.
    """
    import aba05

    celula = bancada.split('<span class="sec-rot">Testar agora', 1)
    assert len(celula) == 2, (
        'o rótulo "Testar agora" saiu da coluna de rótulos — sem ele não há '
        "onde a dica morar")
    dica = celula[-1].split("</div>", 1)[0].split('<span class="dica"', 1)
    assert len(dica) == 2, 'o `?` do "Testar agora" sumiu da célula do rótulo'
    assert aba05.DICA_DOS_VALORES_QUE_PASSAM in dica[-1], (
        'a nota do Testar não está no `?` do "Testar agora" — a 05-Q2 dela é '
        '*"As duas na dica"*')
    assert 'class="vib-nota"' not in bancada, (
        "a linha permanente embaixo da grade voltou — ela saiu na 05-Q2, e a "
        "classe sem regra de CSS seria um dado morto na página")
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
def test_o_aviso_do_que_a_coluna_mostra_e_sucesso_e_nao_recusa(
        a05, disco) -> None:
    """A gravação aconteceu: o canal é o de SUCESSO, não o da recusa.

    Enquanto só existia o canal da recusa, um clique que deu certo pousava uma
    tarja LARANJA de 30 s no cartão dela — que ensina que o botão falha. A
    ONDA0-P construiu o canal de sucesso (verde, 6 s), e um gesto que devolva
    `{"recado": …}` manda a própria frase.

    **ELA DEIXOU DE LER O TEXTO DO CÓDIGO — 06/09/2026.** O que estava aqui era
    `inspect.getsource(_aplicar_a_forca)` procurando as strings
    `'return {"recado":'` e `"raise RuntimeError"`: a régua **mediu o FONTE**, e
    não o que o gesto devolve. É a forma de defeito que esta casa pagou onze vezes em
    26/08 — *a régua digita o que devia LER* — e ela reprovaria qualquer
    mudança de forma, inclusive a desta sprint, sem que nada na tela tivesse
    piorado. Agora ela CHAMA o gesto com o disco dublê e olha o que volta.

    MORDIDA: em `_aplicar_a_forca`, troque o `return {"recado": …}` do primeiro
    ramo por `raise RuntimeError(…)` — este caso reprova pelo `pytest.raises`,
    e o piloto volta a anotar `("recusou dizendo", …)` sobre um disco que mudou.
    """
    # O RAMO DA "ESCOLHA QUE NÃO DIVERGE", montado como o produto o produz: o
    # global do PERFIL já é `balanceado`, então `with_controller_rumble` APAGA
    # o override no clique do mesmo degrau; sem override, a coluna cai no
    # `rumble_policy` que o daemon publica — aqui `max` —, e o botão que ela
    # clicou não é o que fica aceso.
    estado, gravados = disco
    estado["regua"] = _perfil_do_esquema(
        rumble={"policy": "balanceado"},
        controllers={_chave(UNIQ): {"rumble": {"policy": "economia"}}})

    volta = _gesto("forca")(_ctx(rumble_policy="max"),
                            {"uniq": UNIQ, "forca": "balanceado"},
                            PonteFiel())

    assert isinstance(volta, dict) and volta.get("recado"), (
        f"o gesto não devolveu recado nenhum ({volta!r}) — sem ele a coluna "
        f"muda de degrau sem uma palavra")
    assert gravados, "o clique não gravou — o recibo seria sobre nada"

    # E O CANAL DA RECUSA CONTINUA SENDO OUTRO: um `RuntimeError` daqui faria o
    # piloto pintar laranja por 30 s sobre um disco que MUDOU. A asserção é
    # sobre o CAMINHO, e não sobre o texto do código: se algum dos ramos voltar
    # a levantar, o `_gesto` acima já teria estourado antes desta linha.
    assert not isinstance(volta, BaseException)


# --------------------------------------------------------------------------
# 8. A FAIXA EMBAIXO DA GRADE — 05-Q4 dela, 05/09/2026
#
#    *"Linha embaixo da grade — a frase entra na faixa que já existe sob a
#    grade, nomeando a coluna (`P2 · voltou ao ajuste geral`) e some logo
#    depois; **nada se mexe dentro das colunas**."*
# --------------------------------------------------------------------------
def test_a_frase_da_faixa_nomeia_a_coluna(a05, disco) -> None:
    """Dois controles na tela, clique no SEGUNDO, e o `P2` abre a frase.

    FORA DO CARTÃO A FRASE PERDE O ENDEREÇO. Dentro da coluna, o endereço era a
    própria coluna em que o aviso pousava; uma linha embaixo da grade fala das
    quatro ao mesmo tempo, e sem o `P2` ninguém sabe de qual. Com dois
    controles na mesa esta é a única asserção que distingue a frase do P1 da do
    P2.

    O NÚMERO NÃO SE DIGITA: ele é o `jogador` do item de mesa, o MESMO que a
    coluna já mostra no rótulo (`aba05`, `P{c["jogador"]}`). Por isso a régua
    monta a mesa com `jogador: 2` no segundo e exige o `P2` — contar a posição
    na lista daria `P2` por coincidência e `P1` no dia em que o primeiro caísse.

    MORDIDA: em `_aplicar_a_forca`, troque `_na_faixa(ctx, uniq, …)` pela frase
    crua — este caso reprova, porque o `P2` some da linha.
    """
    estado, _ = disco
    estado["regua"] = _perfil_do_esquema(
        rumble={"policy": "balanceado"},
        controllers={_chave(OUTRO): {"rumble": {"policy": "economia"}}})

    volta = _gesto("forca")(_ctx_dois(rumble_policy="max"),
                            {"uniq": OUTRO, "forca": "balanceado"},
                            PonteFiel())
    frase = str((volta or {}).get("recado") or "")
    assert frase.startswith(f"P2{a05.SEPARADOR_DA_FAIXA}"), (
        f"a linha da faixa não nomeia a coluna: {frase!r}. Ela fala das quatro "
        f"colunas ao mesmo tempo, e o `P2` é o único endereço que ela tem")
    assert "P1" not in frase, (
        f"a frase do P2 nomeou outra coluna: {frase!r}")


def test_a_frase_da_faixa_cabe_numa_linha(a05) -> None:
    """As três frases sob o teto MEDIDO — a faixa reserva UMA linha.

    O TETO NÃO É GOSTO: `a05_vibracao.TETO_DA_LINHA_DA_FAIXA` traz a medição no
    Chrome a 1920x1080, com três vocabulários (181 · 189 · 187 caracteres), e o
    número guardado fica abaixo do MENOR. A segunda linha sai CORTADA — foi o
    que a foto de 04/09/2026 mostrou com a primeira versão da
    `_ressalva_da_mesa`, de 285 caracteres.

    A CONTA É DA FRASE PRONTA, com o `P2 ·` na frente e com o nome de degrau
    MAIS LONGO no `%s`: uma régua sobre o molde cru daria verde sobre uma linha
    que a tela corta.

    MORDIDA: devolva `FRASE_DA_MESA_EM_AUTO` ao texto de 331 caracteres de
    04/09 — este caso reprova.
    """
    mais_longo = max((a05._nome_do_degrau(c) for c in ("custom", "economia",
                                                       "balanceado", "max")),
                     key=len)
    prefixo = f"P4{a05.SEPARADOR_DA_FAIXA}"
    for nome in ("FRASE_DO_AJUSTE_GERAL", "FRASE_DO_QUE_A_COLUNA_MOSTRA",
                 "FRASE_DA_MESA_EM_AUTO"):
        molde = getattr(a05, nome)
        pronta = prefixo + (molde % mais_longo if "%s" in molde else molde)
        assert len(pronta) <= a05.TETO_DA_LINHA_DA_FAIXA, (
            f"{nome} tem {len(pronta)} caracteres na linha e o teto medido é "
            f"{a05.TETO_DA_LINHA_DA_FAIXA} — a faixa corta a segunda linha, e "
            f"uma explicação que ela não consegue ler ocupa o lugar sem "
            f"informar:\n  {pronta}")


def test_a_frase_da_faixa_diz_o_que_o_produto_diz(a05) -> None:
    """A metade do FATO não é redigitada — ela vem da oração do produto.

    A janela estável diz a mesma coisa no mesmo caso desde 25/08
    (`rumble_actions.TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL`, RUM-3). O que a
    faixa mostra é a metade do FATO dela, porque o MECANISMO não cabe numa
    linha e mudou de casa (o `?` do rótulo "Força da vibração"). Escrever aqui
    uma segunda oração seria a divergência que a regra das duas cópias existe
    para matar — e esta régua **pergunta ao dono** em vez de digitar a resposta.

    MORDIDA: troque `FATO_DO_AJUSTE_GERAL` por *"voltou ao ajuste padrão"* —
    este caso reprova, porque a oração do produto não diz isso.
    """
    from hefesto_dualsense4unix.app.actions.rumble_actions import (
        TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL,
    )

    assert a05.FATO_DO_AJUSTE_GERAL in TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL, (
        f"a linha da faixa diz {a05.FATO_DO_AJUSTE_GERAL!r} e o produto diz "
        f"{TEXTO_A_PECA_VOLTOU_AO_AJUSTE_GERAL!r} — as duas telas deixaram de "
        f"contar o mesmo fato com as mesmas palavras")
    assert a05.FATO_DO_AJUSTE_GERAL in a05.FRASE_DO_AJUSTE_GERAL, (
        "a frase da faixa deixou de usar o fato que o produto nomeia")


def test_a_frase_da_faixa_e_recibo_e_nao_alerta(a05, bancada: str) -> None:
    """O tom da linha é o do RECIBO, e ele é verde.

    LARANJA SOBRE UM CLIQUE QUE GRAVOU ENSINA QUE O BOTÃO FALHA — é o defeito
    que a D-01 fechou em 04/09/2026, e o `alerta` desta faixa é laranja
    (`--orange`). Verde é a cor que esta casa usa para o que deu certo em todas
    as dez abas, e `hefesto_vivo.COR_DO_SUCESSO` lê o MESMO `--green`.

    AS DUAS METADES DESTA POSSE ESTÃO AQUI: o nome do tom (o pacote) e a regra
    que o pinta (o desenho). Sem a segunda, a linha pousa sem cor nenhuma.

    MORDIDA: em `a05_vibracao`, faça `TOM_DO_RECIBO = _tela.ALERTA`, ou pinte
    `.vib-estado .est.recibo` com `--orange` no `aba05.CSS` — este caso reprova
    nas duas.
    """
    # ERAM TRÊS TONS COM DONO ATÉ 07/09/2026. O `diz` morreu com a contagem de
    # pedidos do jogo, que era a única frase que o vestia — ver
    # `app/telas/vibracao.SEM_A_CONTAGEM_DE_PEDIDOS`. A lista é lida do módulo e
    # não digitada aqui: um quarto tom que nasça lá entra nesta guarda sozinho.
    assert a05.TOM_DO_RECIBO not in (_tela.ALERTA, _tela.INFO), (
        f"o recibo passou a usar um tom que já tem dono ({a05.TOM_DO_RECIBO!r})"
        f" — o `alerta` é laranja, e alerta sobre um clique que gravou ensina "
        f"que o botão falha")
    assert (f'data-hef-recado-classe="est {a05.TOM_DO_RECIBO}"' in bancada), (
        f"a faixa não veste o recado com o tom {a05.TOM_DO_RECIBO!r} — o "
        f"pacote e o desenho deixaram de falar do mesmo tom")
    regra = f".vib-estado .est.{a05.TOM_DO_RECIBO}"
    assert f"{regra}{{color:var(--green)}}" in bancada, (
        f"o tom do recibo não é verde na folha desta aba ({regra})")
    assert "--orange" not in bancada.split(regra, 1)[-1].split("}", 2)[0], (
        "o recibo da faixa ficou laranja")


def test_o_deu_certo_seco_nao_vira_frase(a05, disco) -> None:
    """O clique que NÃO contradiz o botão continua sem frase nenhuma.

    **É ESTA QUE GUARDA A 03-Q4 DELA**, 05/09/2026: *"nada muda de lugar e
    nenhuma palavra nova entra na tela"*. Sem ela, alguém acrescenta um
    `"Pronto."` na faixa e a decisão morre calada — o "deu certo" seco é a
    piscada verde no campo, não uma linha de texto.

    E É TAMBÉM A METADE QUE PROVA QUE A FAIXA SOME: sem frase não há depósito,
    e sem depósito não há nó na faixa. A tela parada não ganha uma linha.

    MORDIDA: em `_aplicar_a_forca`, troque o `return None` final por
    `return {"recado": _na_faixa(ctx, uniq, "Pronto.")}` — este caso reprova.
    """
    estado, gravados = disco
    estado["regua"] = _perfil_do_esquema(
        controllers={_chave(UNIQ): {"rumble": {"policy": "economia"}}})

    volta = _gesto("forca")(_ctx(rumble_policy="balanceado"),
                            {"uniq": UNIQ, "forca": "max"}, PonteFiel())
    assert gravados, "o clique não gravou — o silêncio seria sobre nada"
    assert volta is None, (
        f"o clique que deu certo e não tem notícia falou na tela: {volta!r}. "
        f"A 03-Q4 dela é a piscada verde, sem palavra nova")


def test_a_faixa_declara_que_recebe_o_recado(bancada: str) -> None:
    """O terceiro lugar do recado é a FAIXA, e quem o declara é a página.

    O PILOTO CONHECE DOIS LUGARES — o cartão do controle e a tarja de rodapé
    (`hefesto_vivo.pintar_recados`). O terceiro é este, e o endereço tem de ser
    da PÁGINA: cravar `#vib-estado` dentro do piloto seria o piloto único
    sabendo o nome de um elemento de uma aba só — a mesma dívida que o `.fita`
    de dois donos já cobra na `07-lancadores`.

    O TOM VIAJA NO ATRIBUTO porque só o SUCESSO muda de lugar: a recusa
    continua no cartão, laranja, por 30 s (§6 da sprint). Um endereço sem tom
    mudaria as duas.

    **A METADE QUE FALTA NÃO É DESTA POSSE** — `pintar_recados` ler estes dois
    atributos está relatado com a forma exata em
    `docs/process/agentes/2026-09-06/ONDA5-05-03.md`.

    MORDIDA: tire o `data-hef-recados` do `<div class="vib-estado">` em
    `aba05.MIOLO` e regere — a régua 17 do gerador reprova antes desta.
    """
    faixa = bancada.split('class="vib-estado"', 1)[-1].split(">", 1)[0]
    assert 'data-hef-recados="sucesso"' in faixa, (
        "a faixa deixou de declarar que recebe o recado de sucesso — sem isso "
        "ele volta a pousar DENTRO da coluna, cobrindo o topo do desenho do "
        "controle por 6 s a cada clique, e a 05-Q4 dela diz *nada se mexe "
        "dentro das colunas*")
    assert "recusa" not in faixa, (
        "a faixa passou a receber também a recusa — ela continua no cartão, "
        "laranja e por 30 s, e esta sprint mexe no que deu CERTO")


def test_nenhuma_linha_da_faixa_diz_mesa(a05) -> None:
    """A palavra "mesa" não entra em texto de tela — decisão dela, 06/09/2026.

    *"Falei do termo mesa que é horrível. (…) O termo sai e coloca-se termos
    simples pro user comum. feature fica."* — `docs/A-LINGUA-DESTA-CASA`. Na
    tela é **força geral**; na casa continua sendo a mesa (`ctx.mesa`,
    `mesa_viva.py`), e por isso esta régua olha só o TEXTO que sobe.

    O ESCOPO É A FAIXA, e é o que esta sprint possui: as três frases do recado
    e a ressalva que vive ao lado delas. Duas linhas na MESMA faixa, uma
    dizendo "força da mesa" e a outra "força geral", seriam dois nomes para o
    mesmo botão, um embaixo do outro.

    MORDIDA: devolva `"a força da mesa está em Auto"` à `_ressalva_da_mesa` —
    este caso reprova.
    """
    ressalva = a05._ressalva_da_mesa(
        {"rumble": {"policy": "auto"},
         "controllers": {_chave(UNIQ): {"rumble": {"policy": "max"}}}},
        [{"pref": "p1", "jogador": 1, "uniq": UNIQ}])
    assert ressalva, "a ressalva não nasceu — a régua mediria uma string vazia"
    da_faixa = [ressalva, a05.FRASE_DA_MESA_EM_AUTO, a05.FRASE_DO_AJUSTE_GERAL,
                a05.FRASE_DO_QUE_A_COLUNA_MOSTRA % a05._nome_do_degrau("custom"),
                a05.FRASE_DO_QUE_A_COLUNA_MOSTRA % a05._nome_do_degrau("furrufu")]
    for frase in da_faixa:
        assert "mesa" not in frase.lower(), (
            f"a palavra que ela baniu da tela voltou a uma linha da faixa: "
            f"{frase!r}")
