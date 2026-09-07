#!/usr/bin/env python3
"""A célula `LEDs` é ESPELHO da linha `Jogador` — 07/09/2026, ordem dela.

**ESTE ARQUIVO ERA A RÉGUA DA BOTOEIRA (LUZES-01, 06/09/2026), e a botoeira
saiu.** Ele se chamava `test_a_04_as_cinco_lampadas_sem_o_numero.py` e provava
as cinco linhas `FALTA_NO_HTML` que aquela sprint fechou: marcar cada lâmpada,
os presets "Desenho do P1".."P4", "Todas acesas"/"Todas apagadas", o reenvio, e
"Voltar todos ao automático".

**A ORDEM DELA, olhando a aba com os quatro DualSense na mesa:**

    "pq tá surgindo os leds no lado da iluminação se acima já tem o canto dos
     players? pode remover?"

e, corrigindo o que eu tinha entendido a mais:

    "para. os leds. barra de luz ficam. é o desenho original. o que eu não
     quero é frase da steam ou outras e p1,P2..."

e a forma final, que é o contrato:

    "só olhar a linha de cima da seleção de player e replicar o que tem lá."

**O QUE SAIU E O QUE FICOU:**

    as CINCO lâmpadas       ficam — e passam a MOSTRAR o número, sem escolha
    as DUAS tiras           ficam — são o desenho original
    `P1 P2 P3 P4 ··· ·`     saíram (gesto `desenho-de`)
    o clique nas lâmpadas   saiu   (gesto `luzes`)
    a moldura de reenvio    saiu   (gesto `reenviar-desenho`)
    a linha de ressalva     saiu   (`data-campo="luz-ressalva"`)

**AS QUATRO LINHAS DE PARIDADE REABREM COMO DECISÃO DELA, e a distinção é o
ponto:** o produto não as perdeu por descuido — ela dispensou o controle manual
do desenho. A quinta (`csv:148`, "Voltar todos ao automático") FICA, e é o que
os três primeiros testes deste arquivo continuam provando: o `auto-todos` veio
na mesma sprint e não foi tocado pela ordem.

**O QUE ESTE ARQUIVO PROVA AGORA** são as duas metades da réplica:

1. a célula acende o padrão do NÚMERO daquela coluna, perguntado ao dono
   (`monta.luzinhas` ← `core/led_control.player_led_pattern`);
2. ela não oferece gesto nenhum — nem na coluna cheia, nem na vazia.

**A MORDIDA DA SEGUNDA É A QUE IMPORTA**, e ela mede uma AUSÊNCIA: devolva
`bits=` à chamada de `desenho_da_luz` em `aba04.coluna`, rode o gerador, e a
régua do gesto reprova. Uma régua de ausência que ninguém arranca é uma régua
que dá verde sobre a botoeira de volta.

O LAR É DE MENTIRA. O `conftest` desvia `HOME` e os quatro `XDG_*`; os casos que
gravam escrevem perfil de verdade, com `save_profile`, dentro dele — que é a
única forma de provar que o disco recebeu, em vez de provar que a função foi
chamada.
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

#: MACs da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UM = "aa:bb:cc:00:00:01"
DOIS = "aa:bb:cc:00:00:02"
CHAVE_UM, CHAVE_DOIS = "aabbcc000001", "aabbcc000002"

MESA = [
    {"pref": "p1", "uniq": UM, "jogador": 1, "cor": "white",
     "nome": "White", "via": "USB"},
    {"pref": "p2", "uniq": DOIS, "jogador": 2, "cor": "galactic-purple",
     "nome": "Galactic Purple", "via": "BT"},
]

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
    """Um dublê da ponte que guarda o que foi chamado e devolve o caminho feliz.

    **ELE SABE RECUSAR** — com `corpo=None` o `player_leds_set_detalhado` volta
    sem corpo e os gestos levantam a frase do produto. Um dublê que só sabe
    passar não é dublê, e esta casa já mediu o preço disso três vezes.
    """

    def __init__(self, corpo: object = ...):
        self.corpo = ({"status": "ok", "aplicado_em": [UM, DOIS],
                       "guardado_em": []} if corpo is ... else corpo)
        self.chamadas: list[tuple[str, tuple, dict]] = []

    def __getattr__(self, nome: str):
        def registrar(*args, **kwargs):
            self.chamadas.append((nome, args, kwargs))
            return True if nome in ("chamar", "profile_switch") else self.corpo

        return registrar

    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]

    def so(self, nome: str) -> list[tuple[tuple, dict]]:
        return [(a, k) for n, a, k in self.chamadas if n == nome]


def _semear(nome: str = "regua", *, automatico: bool = True,
            overrides: dict | None = None):
    """Escreve um perfil no lar de mentira, PELO DONO da escrita."""
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
        leds=LedsConfig(lightbar=(40, 80, 180), lightbar_brightness=1.0,
                        auto_player_colors=automatico),
        controllers={
            chave: ControllerOverrides(leds=LedsConfig(**campos))
            for chave, campos in (overrides or {}).items()
        },
    )
    return save_profile(prof, origem="regua")


def _do_disco(caminho) -> dict:
    return json.loads(pathlib.Path(caminho).read_text(encoding="utf-8"))


def _leds_de(caminho, chave: str) -> dict:
    """A seção `leds` do override daquele controle — `{}` quando não há."""
    dele = (_do_disco(caminho).get("controllers") or {}).get(chave) or {}
    return dele.get("leds") or {}


def _clique(**extra) -> dict:
    return {"controle": "p1", "uniq": UM, **extra}

def test_todos_no_automatico_limpa_as_cores_de_todos_e_religa_o_campo(pac, a04):
    """Campo a campo, o que o gêmeo da GTK faz (`on_lightbar_auto_reset_all`)."""
    caminho = _semear(
        automatico=False,
        overrides={CHAVE_UM: {"lightbar": (255, 0, 0), "lightbar_brightness": 0.5},
                   CHAVE_DOIS: {"lightbar": (0, 255, 0),
                                "player_leds": [True] * 5}})
    fora = a04.automatico_de_todos(_ctx(pac), _clique(), PonteDeMentira())

    disco = _do_disco(caminho)
    assert disco["leds"]["auto_player_colors"] is True, (
        "o automático não voltou a valer")
    for chave in (CHAVE_UM, CHAVE_DOIS):
        leds = _leds_de(caminho, chave)
        assert "lightbar" not in leds, f"a cor própria de {chave} ficou"
        assert "lightbar_brightness" not in leds, f"o brilho de {chave} ficou"
    # O DESENHO FICA — é o que a GTK preserva, e mexer nele aqui faria as duas
    # telas do mesmo produto responderem coisas diferentes ao mesmo botão.
    assert _leds_de(caminho, CHAVE_DOIS).get("player_leds") == [True] * 5, (
        "o `Todos no automático` apagou o desenho das luzes de jogador — o "
        "gêmeo da janela estável limpa a COR, e só ela")
    assert isinstance(fora, dict) and fora.get("recado")


def test_todos_no_automatico_reaplica_o_perfil(pac, a04):
    _semear(automatico=False,
            overrides={CHAVE_UM: {"lightbar": (255, 0, 0)}})
    ponte = PonteDeMentira()
    a04.automatico_de_todos(_ctx(pac), _clique(), ponte)
    assert ponte.so("profile_switch"), (
        "o perfil não foi reaplicado — as cores sairiam do disco e ficariam no "
        "aparelho até a próxima troca de perfil")

def test_o_escopo_global_mora_na_faixa_do_titulo():
    """Dentro de uma coluna ele mentiria sobre o alcance — e custaria linha."""
    from hefesto_dualsense4unix.interface import onde
    from pacotes import a04_iluminacao as a04

    texto = onde.pagina(PAGINA).read_text(encoding="utf-8")
    topo = texto.split('<div class="quadro-topo">', 1)[-1].split("</div>", 1)[0]
    assert f'data-gesto="{a04.GESTO_DO_AUTOMATICO_DE_TODOS}"' in topo
    assert ">Todos no automático</button>" in topo


# ---------------------------------------------------------------------------
# A RÉPLICA — a célula LEDs acende o padrão do NÚMERO daquela coluna
# ---------------------------------------------------------------------------
def _grade() -> str:
    """A grade das colunas da página da BANCADA — o desenho de hoje.

    **OS COMENTÁRIOS SAEM ANTES**, e não é asseio: é a mesma primeira linha do
    `aba04._conferir`, e ela existe porque a prosa desta aba CITA os endereços
    que as réguas procuram. O comentário que explica por que a linha de ressalva
    saiu escreve `data-campo="luz-ressalva"` por extenso; o que explica a poda da
    botoeira nomeia os três gestos. Uma régua que lesse a prosa junto com a
    marcação acusaria o AVISO como se fosse o defeito que ele descreve — que é a
    armadilha que esta casa pagou três vezes em três dias, a última em 05/09,
    quando um comentário sobre o `BOOTSTRAP` virou a primeira ocorrência do
    padrão proibido e derrubou treze testes.
    """
    import re

    from hefesto_dualsense4unix.interface import onde

    texto = onde.pagina(PAGINA).read_text(encoding="utf-8")
    texto = re.sub(r"<!--.*?-->", "", texto, flags=re.S)
    return texto.split('<div class="luz-grade">', 1)[-1] \
                .split('<div class="rodape"', 1)[0]


def _celulas_de_leds(grade: str) -> list[tuple[int, str]]:
    """`(número do jogador, HTML da célula LEDs)` de cada coluna CONECTADA.

    O RECORTE PASSA PELA COLUNA, e não pelo miolo inteiro: os quatro lugares
    emitem a `.cel-leds` desde 07/09/2026, e casar `<div class="cel-leds">` no
    documento todo devolveria as duas vazias junto com as duas cheias.
    """
    import re

    fora = []
    for coluna in re.findall(
            r'<div class="ctrl(?! vazia)"(.*?)(?=<div class="ctrl[" ]|\Z)',
            grade, re.S):
        n = re.search(r'data-campo="identidade">P(\d)', coluna)
        leds = re.search(r'<div class="cel-leds">(.*?)</div>\s*</div>',
                         coluna, re.S)
        if n and leds:
            fora.append((int(n.group(1)), leds.group(1)))
    return fora


def test_as_cinco_lampadas_desenham_o_padrao_do_numero_da_coluna():
    """A réplica que ela pediu, medida coluna a coluna.

    O PADRÃO NÃO SE DIGITA AQUI: ele é perguntado a `monta.luzinhas`, que sai de
    `core/led_control.player_led_pattern` — o MESMO que o daemon acende. Escrever
    `<i class="on">` na posição que eu achasse certa faria esta régua medir a
    minha memória em vez do produto, que é o defeito que esta casa nomeia como
    *a régua digita o que devia LER*.

    A MORDIDA: faça `aba04.coluna` passar um número fixo a `desenho_da_luz` — o
    `1`, por exemplo — e a coluna do P2 reprova.
    """
    import monta

    celulas = _celulas_de_leds(_grade())
    assert len(celulas) == len(monta.CONECTADOS), (
        f"a grade tem {len(celulas)} colunas conectadas com célula LEDs e a "
        f"mesa tem {len(monta.CONECTADOS)}")
    for n, bloco in celulas:
        assert monta.luzinhas(n) in bloco, (
            f"a célula LEDs do P{n} não desenha o padrão do número {n} — ela "
            f"deixou de replicar a linha `Jogador`, que é o que ela mandou em "
            f"07/09/2026")


def test_a_celula_de_leds_nao_oferece_gesto_nenhum():
    """As lâmpadas MOSTRAM o número; quem o escolhe é a linha `Jogador`.

    ESTA RÉGUA MEDE UMA AUSÊNCIA, e por isso nomeia os três gestos que não podem
    voltar. Um `data-gesto` nesta faixa é a botoeira de volta — a segunda maneira
    de mexer nas mesmas luzes, que é exatamente o que ela mandou tirar.

    A MORDIDA: devolva `bits=_pacote04.desenho_de_agora(None, "", j)` à chamada
    de `desenho_da_luz` em `aba04.coluna`, rode o gerador, e as duas asserções
    reprovam.
    """
    for n, bloco in _celulas_de_leds(_grade()):
        assert "data-gesto=" not in bloco, (
            f"a célula LEDs do P{n} voltou a oferecer gesto — ela é desenho de "
            f"leitura desde 07/09/2026")
        assert "<button" not in bloco, (
            f"a célula LEDs do P{n} ganhou um `<button>` — mesmo sem gesto, um "
            f"botão convida a um clique que o pacote não atende")


def test_nenhum_lugar_vazio_oferece_tecla_de_luz():
    """Sem aparelho não há desenho a mandar — a mesma regra das outras células.

    ELA CONTINUA VALENDO DEPOIS DA REMOÇÃO, e por isso fica: a coluna vazia
    nunca teve estes gestos, e a régua é a que garante que a poda não os deixou
    cair de volta só ali — onde ninguém olha.
    """
    import re

    for bloco in re.findall(
            r'<div class="ctrl vazia"(.*?)(?=<div class="ctrl[" ]|\Z)',
            _grade(), re.S):
        for gesto in ("luzes", "desenho-de", "reenviar-desenho"):
            assert f'data-gesto="{gesto}"' not in bloco, (
                f"um lugar vazio oferece `{gesto}` — o gesto saiu do pacote em "
                f"07/09/2026 e o clique não teria quem o atendesse")


def test_os_tres_gestos_da_botoeira_sairam_do_pacote(pac, a04):
    """O widget e o gesto saíram no MESMO commit — e é o que fecha o `casa-sabe`.

    A ALTERNATIVA ERA DECLARÁ-LOS EM `_SEM_CAMINHO_HOJE`, e ela estaria errada:
    aquela lista é para PROMESSA cujo caminho ainda não existe. Um gesto cujo
    widget ela mandou remover não é promessa por cumprir — é código morto, e a
    regra desta casa manda que a poda acompanhe a peça.

    A MORDIDA: registre de novo qualquer um dos três com `@gesto` e a primeira
    asserção reprova.
    """
    vivos = {nome for (pagina, nome) in pac.GESTOS if pagina == PAGINA}
    for morto in ("luzes", "desenho-de", "reenviar-desenho"):
        assert morto not in vivos, (
            f"o gesto `{morto}` voltou ao pacote sem o widget que o oferecia — "
            f"um gesto que a tela não alcança é código morto, e ela mandou "
            f"remover a botoeira inteira em 07/09/2026")
    assert vivos >= {"cor", "apagar", "auto", "brilho", "player",
                     "reenviar", "auto-cores", "auto-todos"}, (
        f"a poda da botoeira levou junto um gesto que FICA: {sorted(vivos)}")


def test_o_piso_da_aba_desceu_com_a_ordem_dela(a04):
    """A ÚNICA vez em que o piso desce, e ela tem nome, razão e data.

    A regra ("o piso só sobe") existe porque uma queda não aparece na tela: o
    clique simplesmente deixa de fazer alguma coisa, calado. Aqui não há queda
    calada — há uma ordem dela, e os três que saem são exatamente os três que a
    LUZES-01 trouxe. Ver a nota datada em `a04_iluminacao.PISO_DA_ABA`.
    """
    assert a04.PISO_DA_ABA == 8, (
        f"o piso da aba é {a04.PISO_DA_ABA}. Ele foi de 11 para 8 em "
        f"07/09/2026, com a botoeira; subi-lo de volta a 11 é repor a botoeira "
        f"que ela mandou tirar, e isso pede a palavra dela")


def test_a_linha_de_ressalva_saiu_da_celula_de_leds():
    """*"o que eu não quero é frase da steam ou outras"* — 07/09/2026.

    AS DUAS METADES ANDAM JUNTAS, e é isso que esta régua guarda: o widget saiu
    do gerador E o campo saiu do pacote. Um campo que o pacote emite e a página
    não tem é ÓRFÃO calado no piloto — escreve-se em nada, tique após tique, sem
    erro nenhum.

    A MORDIDA: devolva o `monta_.ressalva(...)` ao `.cel-leds` de `aba04.coluna`
    e a primeira asserção reprova; devolva a chave ao pacote e a segunda reprova.

    E OS COMENTÁRIOS SAEM ANTES, pela razão que `_grade` documenta: o comentário
    que EXPLICA a remoção escreve `luz-ressalva` por extenso, quatro vezes na
    página. Lê-lo como marcação faria o aviso reprovar como se fosse o defeito
    que ele descreve.
    """
    import re

    from hefesto_dualsense4unix.interface import onde
    from pacotes import a04_iluminacao as a04

    texto = re.sub(r"<!--.*?-->", "",
                   onde.pagina(PAGINA).read_text(encoding="utf-8"), flags=re.S)
    assert "luz-ressalva" not in texto, (
        "a linha de ressalva voltou à página — a razão de a barra apagar "
        "continua no `title` das duas tiras, escrita pela `dica_da_luz`")
    assert not hasattr(a04, "ENDERECO_DA_RESSALVA"), (
        "o endereço da ressalva voltou ao pacote — sem o widget na página, "
        "todo tique escreveria num campo que não existe")
