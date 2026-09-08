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

**A MORDIDA DA SEGUNDA É A QUE IMPORTA**, e ela mede uma AUSÊNCIA: ponha um
`<button data-gesto="luzes">` dentro da `.cel-leds` de `aba04.coluna` e a régua
do gesto reprova — a receita inteira, com os dois degraus e o que devolver
depois, está em `test_a_celula_de_leds_nao_oferece_gesto_nenhum`. Uma régua de
ausência que ninguém arranca é uma régua que dá verde sobre a botoeira de volta.

O LAR É DE MENTIRA. O `conftest` desvia `HOME` e os quatro `XDG_*`; os casos que
gravam escrevem perfil de verdade, com `save_profile`, dentro dele — que é a
única forma de provar que o disco recebeu, em vez de provar que a função foi
chamada.
"""
from __future__ import annotations

import json
import re
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

def test_o_gesto_de_escopo_global_saiu_do_pacote(pac, a04):
    """Ela mandou tirar os três cantos que falavam de automático — 07/09/2026.

        *"Olha na real sai todos. Deixa só lá o de cima mesmo o tongle. E aí vai
         servir pra dizer. O jogo é que escolhe quais serão as cores de todos os
         controles."*

    OS DOIS TESTES QUE MORAVAM AQUI mediam o gesto de escopo GLOBAL da faixa do
    título, campo a campo contra o gêmeo da janela estável, e o `profile_switch`
    que ele disparava. Eles nasceram em 06/09 e morreram em 07/09, um dia
    depois — não porque estivessem errados, mas porque a peça que mediam saiu.
    **Um teste que continua exigindo o gesto reprovaria a ordem dela**, e é essa
    a forma de defeito que esta régua substitui.

    O QUE ELE FAZIA fica escrito no pacote, na nota da poda, com a medição que
    ele carregava: limpava `lightbar` e `lightbar_brightness` de TODOS os
    overrides por controle e religava `auto_player_colors`, preservando o
    desenho das cinco luzes.

    A MORDIDA: registre de novo qualquer gesto de escopo global nesta página
    com `@gesto` e a primeira asserção reprova.
    """
    vivos = {nome for (pagina, nome) in pac.GESTOS if pagina == PAGINA}
    for morto in ("auto-todos", "auto"):
        assert morto not in vivos, (
            f"o gesto `{morto}` voltou ao pacote sem o widget que o oferecia — "
            f"ela mandou tirar os dois em 07/09/2026, e a poda acompanha a peça")
    # E OS AJUDANTES ÓRFÃOS SAÍRAM JUNTO. Os dois só tinham aquele chamador; um
    # ajudante privado que ninguém chama é código morto que portão nenhum vê, e
    # a próxima pessoa o lê como caminho vivo.
    for orfao in ("_leds_sem", "_perfil_ativo_ou_recusa"):
        assert not hasattr(a04, orfao), (
            f"`{orfao}` ficou no pacote sem chamador — ele só existia para o "
            f"gesto de escopo global, que saiu em 07/09/2026")
    # E O MÉTODO DE PONTE QUE SÓ AQUELE BOTÃO CHAMAVA saiu da declaração: uma
    # `METODOS` que lista o que ninguém chama é a régua verde sobre uma ponte
    # que a tela não atravessa.
    assert sorted(a04.METODOS) == ["coop.sync"], (
        f"a declaração de métodos desta aba é {sorted(a04.METODOS)} — só o "
        f"`coop.sync` sobrevive à poda de 07/09/2026")


def test_a_faixa_do_titulo_tem_um_morador_so():
    """Ficou o interruptor, e só ele — ordem dela de 07/09/2026.

    A RÉGUA MEDE O RÓTULO, e não só o endereço, porque o `data-gesto` some no
    instante em que o `<button>` sai — mas um `<span>` com o mesmo texto
    passaria calado, e é a forma exata que a próxima pessoa usaria para "só
    deixar a informação". O que ela mandou tirar foi o CANTO da tela que fala de
    automático, não o atributo.

    E OS DOIS LADOS, porque a bancada e o publicado divergem em silêncio: um
    conserto que fica só no `mockup/` não chega à tela dela, e a página que o
    `WebKit2.WebView` lê é a de `paginas/`.

    A MORDIDA: devolva o `<button>` ao `quadro-topo` de `aba04.MIOLO`, regere e
    publique — esta linha reprova, e o `_conferir` do gerador reprova antes.
    """
    from hefesto_dualsense4unix.interface import onde

    for caminho in (onde.pagina(PAGINA), onde.PUBLICADO / PAGINA):
        texto = caminho.read_text(encoding="utf-8")
        topo = texto.split('<div class="quadro-topo">', 1)[-1].split("</div>", 1)[0]
        assert "Todos no automático" not in topo, (
            f"o botão de escopo global voltou à faixa do título em "
            f"{caminho.name} — ela mandou tirar os três cantos que falavam de "
            f"automático em 07/09/2026")
        assert 'data-gesto="auto-cores"' in topo, (
            f"o interruptor saiu da faixa em {caminho.name} — ele é o ÚNICO "
            f"que ela mandou deixar")


def test_o_botao_por_controle_saiu_e_o_desligar_ficou():
    """*"sai todos"* alcançou a célula Opções de cada coluna — e só ela.

    O `Desligar` FICA, e a razão é MEDIDA, não zelo: os dois botões faziam
    coisas diferentes. O que saiu largava o claim da barra ao jogo e pintava a
    cor do número por cima; este escreve preto no aparelho e mais nada. Ela não
    citou este — e é a diferença de ato que autoriza deixá-lo até ela dizer.

    A MORDIDA: devolva o botão à célula Opções de `aba04.coluna`, regere e
    publique.
    """
    from hefesto_dualsense4unix.interface import onde

    for caminho in (onde.pagina(PAGINA), onde.PUBLICADO / PAGINA):
        corpo = caminho.read_text(encoding="utf-8")
        grade = corpo.split('<div class="luz-grade">', 1)[-1]
        grade = grade.split('<div class="rodape"', 1)[0]
        assert ">Automático</button>" not in grade, (
            f"o botão `Automático` voltou à célula Opções em {caminho.name}")
        # O NÚMERO SAI DA PÁGINA, e não do `MESA` deste arquivo: a mesa
        # daqui tem dois lugares (é o dublê dos gestos) e a página tem os
        # quatro do gerador. Comparar as duas dava 4 contra 2 e reprovava o
        # desenho certo — é a armadilha de medir contra a fonte errada.
        lugares = len(re.findall(r'<div class="ctrl(?:"| vazia")', grade))
        assert lugares >= 2, "a régua não achou as colunas — não mediria nada"
        assert grade.count(">Desligar</button>") == lugares, (
            f"a célula Opções de {caminho.name} não tem um `Desligar` por "
            f"lugar ({grade.count('>Desligar</button>')} para {lugares}) — "
            f"ela NÃO citou este botão")


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

    A MORDIDA (medida em 07/09/2026, e ela tem DOIS degraus): acrescente uma
    tecla dentro da `.cel-leds` de `aba04.coluna` — literalmente
    `<button class="btn" data-gesto="luzes">Desenho</button>` acima da
    `<div class="aceso" …>` — e rode `aba04.py`.

    O GERADOR RECUSA PRIMEIRO, `rc=1`, nomeando a célula duas vezes: o item 10
    de `aba04._conferir` mede a mesma ausência, e é o degrau de cima. Para ver
    ESTA régua vermelha é preciso passar por ele — escreva o `<button>` direto
    em `mockup/04-iluminacao.html` e rode o pytest: as duas asserções reprovam,
    uma por `data-gesto=`, outra por `<button`.

    **DEVOLVA A PÁGINA DEPOIS** (`git checkout -- mockup/04-iluminacao.html`).
    A guarda do `__main__` de `aba04.py` já devolve o desenho aprovado quando o
    gerador recusa, mas uma mordida escrita à mão no HTML é sua para desfazer —
    e `--publicar` copia `mockup/` para `paginas/`, que é o que ela vê.

    A RECEITA ANTIGA MORREU COM A FUNÇÃO QUE MORDIA. Ela mandava devolver
    `bits=_pacote04.desenho_de_agora(None, "", j)` a `desenho_da_luz`, e as duas
    metades saíram nesta mesma leva: `desenho_de_agora` foi deletada e
    `desenho_da_luz` não tem mais parâmetro `bits`. Quem a seguisse receberia
    `AttributeError`/`TypeError` — um erro de digitação, não uma asserção
    vermelha —, e leria isso como "a régua não morde".
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
    assert vivos == {"cor", "apagar", "brilho", "player",
                     "reenviar", "auto-cores"}, (
        f"a poda da botoeira levou junto um gesto que FICA: {sorted(vivos)}")


def test_o_piso_da_aba_desceu_com_a_ordem_dela(a04):
    """A ÚNICA vez em que o piso desce, e ela tem nome, razão e data.

    A regra ("o piso só sobe") existe porque uma queda não aparece na tela: o
    clique simplesmente deixa de fazer alguma coisa, calado. Aqui não há queda
    calada — há uma ordem dela, e os três que saem são exatamente os três que a
    LUZES-01 trouxe. Ver a nota datada em `a04_iluminacao.PISO_DA_ABA`.
    """
    assert a04.PISO_DA_ABA == 6, (
        f"o piso da aba é {a04.PISO_DA_ABA}. Ele desceu DUAS vezes em "
        f"07/09/2026, nas duas ordens dela — 11 para 8 com a botoeira das "
        f"lâmpadas, 8 para 6 com os dois botões do automático. Cada degrau de "
        f"volta é repor um botão que ela mandou tirar, e isso pede a palavra "
        f"dela")


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
