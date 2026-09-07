#!/usr/bin/env python3
"""A ABA VIBRAÇÃO: o valor cai no lugar do valor, e o clique tem dono.

POR QUE ELA EXISTE, e as duas metades foram fotografadas em 02/09/2026 com o
daemon dela vivo:

1. **A PINTURA ESCREVIA DENTRO DOS BOTÕES.** O pintor procura um valor por
   ``[data-campo=X],[data-papel=X],[data-hef=X]`` (``hefesto_vivo.py:183``) e o
   ouvinte de clique lê ``data-papel`` como o NOME do gesto
   (``hefesto_vivo.py:288``). Nesta página ``forca`` era os dois: o
   ``data-campo`` do número do multiplicador **e** o ``data-papel`` dos quatro
   degraus. O pacote emitia a chave ``forca`` e cada tique escrevia
   ``"balanceado"`` em dez elementos — os quatro rótulos viravam a mesma
   palavra, e a linha do "Personalizado" (um ``<div>`` com filhos) perdia o
   trilho, o número e o "Máx", porque ``textContent`` apaga os filhos. A foto
   ``/tmp/antes-05.png`` mostra os quatro degraus lendo "balanceado".

2. **"TESTAR" E "PARAR" RECUSAVAM SEMPRE.** O ouvinte sobe com
   ``closest('[data-controle],[data-uniq]')`` e lê
   ``dataset.controle || dataset.uniq``. A coluna desta aba só tinha
   ``data-uniq=""`` — vazio na cena estática, por anonimato —, então o gesto
   chegava sem controle e ``a05_vibracao._mirar`` levantava. Medido no DOM:

       publicado:  testar controle='' -> RECUSA · parar controle='' -> RECUSA
       bancada:    testar controle='p1' · parar controle='p1' · idem p2

   A régua ``test_os_botoes_tem_dono`` passava porque ela INJETA o ``uniq`` no
   clique de mentira: verde sobre quatro botões mortos. É a mesma forma do
   ``--prova-gesto`` que dava verde sobre o botão do microfone.

A MORDIDA: devolva ``campo="mult"`` para ``campo="forca"`` em
``aba05._coluna``, rode o gerador, e ``test_nenhuma_chave_do_pacote_escreve_num_botao``
reprova nomeando os quatro degraus. Tire o ``data-controle`` da coluna e
``test_testar_e_parar_sabem_de_quem_foi_o_clique`` reprova nomeando os dois.

ONDE ELA MEDE: na **BANCADA**, que é onde o gerador escreve. Apontá-la para o
publicado a faria dar verde sobre a página congelada — a armadilha que o
``onde.pagina()`` documenta e que reincidiu quatro vezes só em 31/08.
"""
from __future__ import annotations

import html.parser
import pathlib
import sys
from typing import ClassVar

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "05-vibracao.html"

#: Um controle de mentira. MAC da faixa sintética da casa — há dois portões de
#: anonimato nesta árvore e eles não perdoam.
UNIQ = "aa:bb:cc:00:00:01"

#: Os endereços que o pintor entende como "aqui vai um valor".
ENDERECOS = ("data-campo", "data-papel", "data-hef")

#: O que o ouvinte de clique sobe procurando para saber DE QUEM foi o clique.
DONOS = ("data-controle", "data-uniq")


class _Arvore(html.parser.HTMLParser):
    """A página como uma árvore de nós, com pai e filhos.

    Um `html.parser` cru só dá eventos; o que estas réguas perguntam é
    ESTRUTURAL — *este elemento contém aquele?*, *qual o ancestral que carrega
    endereço de coluna?* —, e as duas respostas precisam da árvore.

    As tags vazias do HTML são fechadas na hora: um `<br>` ou um `<img>` sem
    barra deixaria a pilha desalinhada e todo elemento seguinte viraria filho
    dele. O `<svg>` desta aba traz `<path>`, `<rect>` e `<circle>` aos montes.
    """

    VAZIAS: ClassVar[set[str]] = {
        "area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.raiz: dict = {"tag": "#raiz", "attrs": {}, "filhos": [], "pai": None}
        self._pilha = [self.raiz]

    def handle_starttag(self, tag, attrs):
        no = {"tag": tag, "attrs": dict(attrs), "filhos": [], "pai": self._pilha[-1]}
        self._pilha[-1]["filhos"].append(no)
        if tag not in self.VAZIAS:
            self._pilha.append(no)

    def handle_startendtag(self, tag, attrs):
        no = {"tag": tag, "attrs": dict(attrs), "filhos": [], "pai": self._pilha[-1]}
        self._pilha[-1]["filhos"].append(no)

    def handle_endtag(self, tag):
        for i in range(len(self._pilha) - 1, 0, -1):
            if self._pilha[i]["tag"] == tag:
                del self._pilha[i:]
                return


def _todos(no: dict):
    for f in no["filhos"]:
        yield f
        yield from _todos(f)


@pytest.fixture(scope="module")
def arvore():
    import onde

    arq = onde.pagina(PAGINA)
    assert arq.exists(), f"a bancada não tem {PAGINA} — rode `python3 aba05.py`"
    p = _Arvore()
    p.feed(arq.read_text())
    return p.raiz


def _achar(raiz: dict, chave: str) -> list[dict]:
    """O `achar()` do pintor, em Python: os três endereços, o mesmo nome."""
    return [n for n in _todos(raiz)
            if any(n["attrs"].get(e) == chave for e in ENDERECOS)]


@pytest.fixture(scope="module")
def emitidos():
    """As chaves que o pacote da aba manda pintar, num tique de mentira.

    Ela vem do PACOTE e não de uma lista digitada aqui — uma chave nova entra
    na régua sozinha, que é a diferença entre medir e repetir.
    """
    import pacotes

    falso = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
             "battery_pct": 95, "is_primary": True, "inputs": {}}
    mesa = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
             "via": "USB", "cor": "starlight-blue", "plastico": "#123456",
             "conectado": True}]
    ctx = pacotes.Contexto(state={"rumble_policy": "balanceado",
                                  "rumble_mult_applied": 0.7,
                                  "active_profile": "regua"},
                           mesa=mesa, conectados=[falso], estados={})
    pacote = pacotes.pacote_da_pagina(PAGINA, ctx)
    chaves = set(pacote.get("mesa") or {})
    for col in (pacote.get("colunas") or {}).values():
        chaves |= set(col)
    return pacote, chaves


# --------------------------------------------------------------------------
# 1. o valor não entra no botão
# --------------------------------------------------------------------------
def test_nenhuma_chave_do_pacote_escreve_num_botao(arvore, emitidos):
    """Escrever um valor num `<button>` pelo alvo `texto` APAGA o rótulo dele.

    Foi assim que "Economia", "Balanceado", "Máximo" e "Auto" viraram os quatro
    a palavra "balanceado", e ela deixou de poder escolher o degrau.

    A RÉGUA PASSOU A PERGUNTAR PELO ALVO — 03/09/2026, e a distinção é o ponto
    inteiro: quem destrói o rótulo é o `el.textContent = t` do ramo PADRÃO
    (`hefesto_vivo.py:284`). Um botão com `data-hef-alvo="classe"` recebe um
    `classList.toggle` e o texto dele não é tocado — é assim que os quatro
    degraus passaram a dizer QUAL está aceso sem perder o nome.

    Sem esta distinção a régua reprovaria a cura em vez do defeito, que é a
    forma de instrumento falso que mais custou nesta casa.
    """
    _, chaves = emitidos
    culpados = {
        chave: [n["attrs"].get("data-forca") or n["attrs"].get("data-lado") or "?"
                for n in _achar(arvore, chave)
                if n["tag"] == "button"
                and (n["attrs"].get("data-hef-alvo") or "texto") == "texto"]
        for chave in sorted(chaves)
    }
    culpados = {k: v for k, v in culpados.items() if v}
    assert not culpados, (
        f"o pacote emite chave que cai DENTRO de um botão pelo alvo `texto`: "
        f"{culpados}. O pintor escreve `textContent`, então o rótulo some.")


def test_o_degrau_cai_nos_quatro_botoes_pelo_alvo_classe(arvore, emitidos):
    """E o contrário: `degrau` TEM de alcançar os quatro botões — pela classe.

    Sem isto o teste acima passaria por vacuidade no dia em que alguém tirasse
    o `data-campo="degrau"` do desenho: nenhuma chave cairia em botão nenhum, e
    a régua daria verde sobre a tela que voltou a mostrar o degrau do mockup.
    """
    _, chaves = emitidos
    assert "degrau" in chaves, "o pacote parou de emitir `degrau`"
    botoes = [n for n in _achar(arvore, "degrau") if n["tag"] == "button"]
    from hefesto_dualsense4unix.interface import aba05
    # POR LUGAR, E NÃO POR COLUNA VIVA — 07/09/2026. O lugar vazio deixou de ser
    # um cartão sem `data-campo` (ver `aba05._coluna`), e uma régua que
    # continuasse contando `* 2` daria verde sobre a metade da mesa que não
    # recebe pintura nenhuma — que era exatamente o defeito.
    assert len(botoes) == len(aba05.FORCA) * len(aba05.MESA), (
        f"são {len(aba05.FORCA)} degraus em {len(aba05.MESA)} lugares, e achei "
        f"{len(botoes)}")
    for n in botoes:
        assert n["attrs"].get("data-hef-alvo") == "classe", n["attrs"]
        assert n["attrs"].get("data-hef-quando"), (
            "um degrau sem `data-hef-quando` acenderia por 'não vazio' — os "
            "quatro ficariam acesos ao mesmo tempo")


#: OS ALVOS QUE SUBSTITUEM O MIOLO DO ELEMENTO, e só eles apagam o de dentro.
#:
#: **A LISTA ENTROU EM 03/09/2026, e sem ela a régua acusava o inocente.** O que
#: apaga filhos é o `textContent` do ramo PADRÃO do `escrever()` e o `innerHTML`
#: do alvo `html` (`hefesto_vivo.py`). Os outros escrevem no PRÓPRIO elemento e
#: não tocam a subárvore: `classe` liga uma classe, `largura`/`cor` mexem no
#: `style`, `plastico` põe uma variável de CSS, `valor` é o `value` de um campo.
#:
#: O CASO QUE A OBRIGOU: a moldura de cada coluna é `data-campo="plastico"` com
#: alvo `plastico` — a cor do aparelho como variável, que a borda e o halo do
#: punho herdam — e os dois grupos de motor do SVG, que ganharam endereço no
#: mesmo dia (`treme-e`/`treme-d`, alvo `classe`), moram DENTRO dela. Sem esta
#: distinção a régua reprovava uma pintura que não apaga um pixel, e a única
#: saída seria tirar a cor da moldura — desfazendo a lei da identidade dela.
#:
#: ELA NÃO AFROUXA O QUE A RÉGUA NASCEU PARA PEGAR: a linha do "Personalizado"
#: com `data-campo="forca"` era o ramo PADRÃO, sem `data-hef-alvo` nenhum, e
#: continua reprovando.
ALVOS_QUE_APAGAM_OS_FILHOS = ("", "html")


def test_nenhuma_chave_do_pacote_apaga_outra(arvore, emitidos):
    """Pintar um elemento que CONTÉM outro endereço apaga o de dentro.

    `textContent` substitui a subárvore inteira. A linha do "Personalizado"
    guardava o trilho (`forca-pct`) e o número (`mult`) dentro de um elemento que
    também era endereço — e a pintura seguinte já não achava nem um nem outro.

    SÓ VALE PARA QUEM ESCREVE MIOLO — ver :data:`ALVOS_QUE_APAGAM_OS_FILHOS`.
    """
    _, chaves = emitidos
    por_chave = {chave: _achar(arvore, chave) for chave in chaves}
    dentro = {n["attrs"].get(e) for ns in por_chave.values() for n in ns
              for e in ENDERECOS if n["attrs"].get(e)}
    falhas = []
    for chave, nos in sorted(por_chave.items()):
        for no in nos:
            if no["attrs"].get("data-hef-alvo", "") not in ALVOS_QUE_APAGAM_OS_FILHOS:
                continue
            for neto in _todos(no):
                for e in ENDERECOS:
                    alvo = neto["attrs"].get(e)
                    if alvo and alvo != chave and alvo in chaves and alvo in dentro:
                        falhas.append(f"{chave} contém {alvo}")
    assert not falhas, (
        f"uma chave pintada apaga outra: {sorted(set(falhas))}. "
        f"Separe os endereços — o de dentro nunca mais é achado.")


# --------------------------------------------------------------------------
# 2. o clique tem dono
# --------------------------------------------------------------------------
def _dono(no: dict) -> str:
    """A subida do ouvinte: `closest('[data-controle],[data-uniq]')`."""
    atual = no["pai"]
    while atual is not None:
        for e in DONOS:
            if e in atual["attrs"]:
                return atual["attrs"].get("data-controle") or atual["attrs"].get("data-uniq") or ""
        atual = atual["pai"]
    return ""


def test_toda_coluna_tem_endereco_de_coluna(arvore):
    """Sem `data-controle` o pintor não acha onde pôr o valor daquele controle.

    E o lugar VAZIO também precisa dele: é por ele que `hefesto_vivo.py:229`
    marca `conectado="nao"` quando um controle sai da mesa. Sem o atributo, uma
    mesa de um controle deixava a coluna do P2 com os números do desenho.
    """
    colunas = [n for n in _todos(arvore)
               if "ctrl" in (n["attrs"].get("class") or "").split()]
    assert len(colunas) == 4, f"a mesa desta aba tem quatro colunas, e achei {len(colunas)}"
    sem = [c["attrs"].get("class") for c in colunas
           if not (c["attrs"].get("data-controle") or "").startswith("p")]
    assert not sem, f"coluna sem `data-controle`: {sem}"


def test_testar_e_parar_sabem_de_quem_foi_o_clique(arvore):
    """Os dois botões que MEXEM no aparelho, e sem dono os dois recusam.

    `a05_vibracao._mirar` levanta *"o clique não disse em qual controle — e sem
    alvo a mesa inteira treme"*, e a recusa é correta: `rumble.set` sem alvo faz
    BROADCAST. O defeito não era a recusa; era a página não dizer de quem foi.

    SÃO DOIS BOTÕES POR LUGAR desde 07/09/2026 — os quatro lugares saem do mesmo
    molde (`aba05._coluna`). Num lugar vazio eles são `display:none` pela folha
    (`.ctrl[data-conectado="nao"] .acoes-col > *`), e `display:none` não recebe
    clique: o par existe para o instante em que o controle chega, sem regerar
    HTML nenhum. O que esta régua guarda continua sendo o DONO — um botão que
    chegue ao pacote sem controle recusa sempre.
    """
    from hefesto_dualsense4unix.interface import aba05
    esperado = 2 * len(aba05.MESA)
    mudos = [(n["attrs"]["data-papel"], _dono(n)) for n in _todos(arvore)
             if n["attrs"].get("data-papel") in ("testar", "parar")]
    assert len(mudos) == esperado, (
        f"são dois botões em {len(aba05.MESA)} lugares, e achei {len(mudos)}")
    assert all(dono for _, dono in mudos), (
        f"clique sem dono, e o gesto vai recusar: {mudos}")


# --------------------------------------------------------------------------
# 3. o que o pacote escreve é o que a caixa pede
# --------------------------------------------------------------------------
def test_o_multiplicador_e_o_numero_e_nao_o_degrau(emitidos):
    """A caixa do "Personalizado" pede o NÚMERO, e ele é o PEDIDO do degrau.

    O pacote mandava ali o nome do degrau (`balanceado`), e essa metade continua
    valendo — a chave `forca` não pode voltar.

    **CORRIGIDO EM 03/09/2026, e a régua CIMENTAVA a divergência.** Ela exigia
    `70%` e `46.7`, os números de `rumble_mult_applied` — um campo que o daemon
    dela deixa **preso no default 0,7** em passthrough ocioso
    (`daemon/lifecycle.py:3459-3468`, com todas as letras). Medido no mesmo dia,
    clicando os quatro degraus pela porta do produto: a política mudou as quatro
    vezes e o número **não se moveu**. Com o degrau em "Balanceado" — cujo
    multiplicador é 1,0 — a tela escrevia `70%`, ao lado de uma dica dela que
    promete *"Balanceado 100%, como o jogo pediu"*.

    É a mesma forma de defeito de `f6c6745b`: a régua guardando o número errado
    e, com ele, o defeito. O esperado passou a sair de
    `app/telas/vibracao._escada()` — a única cópia autorizada em `app/` —, de
    modo que ela não pode mais ficar verde sobre um número digitado aqui.
    """
    from hefesto_dualsense4unix.app.telas import vibracao as _tela

    pacote, _ = emitidos
    col = next(iter(pacote["colunas"].values()))
    pedido = round(_tela._escada()["balanceado"] * 100)
    assert col["mult"] == f"{pedido}%", f"o multiplicador saiu {col['mult']!r}"
    # O CURSOR, e não mais a LARGURA — 03/09/2026, decisão dela: a linha do
    # multiplicador virou um `<input type=range>`, e o que o pintor escreve nela
    # é o `value` (o número de 0 ao teto), não a fração do trilho.
    assert col["mult-pos"] == f"{pedido}", (
        f"o cursor da barra saiu {col['mult-pos']!r}, e o número ao lado diz "
        f"{col['mult']!r} — a mesma linha contando duas histórias")
    assert "forca" not in col, (
        "a chave `forca` voltou ao pacote: ela é `data-papel` dos quatro degraus")


def test_a_identidade_sai_com_um_ponto_so():
    """`P1 · Não sei · BT`, e não `P1 ·•· Não sei ·•· BT`.

    A camada do produto separa com `<span class="pt">•</span>` — DUAS tags e um
    `•` no meio. Trocar cada tag por `·` produzia três pontos por separador.
    """
    from pacotes.a05_vibracao import _sem_marcacao

    do_produto = ('P1 <span class="pt">•</span> Cosmic Red '
                  '<span class="pt">•</span> USB')
    assert _sem_marcacao(do_produto) == "P1 · Cosmic Red · USB"
    assert "<" not in _sem_marcacao(do_produto)


def test_a_mesa_desta_aba_so_emite_o_degrau_geral(emitidos):
    """A MESA emite UM campo, e ele tem endereço — 04/09/2026, decisão [05] dela.

    **FATO SUBSTITUÍDO**, e a régua anterior dizia *"nada da MESA tem endereço
    nesta página"*. Era verdade e deixou de ser: a linha de MESA (`.vib-mesa`)
    nasceu com os quatro degraus do ajuste geral, e o `degrau-mesa` é o campo
    que os acende. A razão de então continua valendo, virada do avesso — o
    degrau aceso é uma CLASSE, e é o alvo `classe` que este campo alimenta.

    O QUE CONTINUA PROIBIDO é emitir um campo SEM endereço na página: era o que
    a chave `forca` fazia, e o que ela fazia era só destruição. Por isso a régua
    passou de "a mesa não emite" para "a mesa emite exatamente o que a página
    sabe receber".
    """
    import onde

    pacote, _ = emitidos
    assert set(pacote["mesa"]) == set(), (
        f"a mesa emite {sorted(pacote['mesa'])} — e a página só tem endereço "
        f"para o degrau geral")
    bancada = onde.pagina(PAGINA).read_text(encoding="utf-8")
    assert 'data-campo="degrau-mesa"' not in bancada, (
        "o `degrau-mesa` voltou ao desenho — campo sem endereço é "
        "pintura que não acontece, e ela é silenciosa dos dois lados")
    assert not pacote["mesa"], (
        "o degrau da mesa saiu vazio com o daemon dizendo a política")


def test_o_que_falta_esta_declarado(emitidos):
    """O que a tela mostra e este pacote não pinta tem NOME e DONO da cura.

    `SEM_DONO` estava `{}` — o vazio dizia "nada falta" numa aba onde quatro
    coisas faltavam, e é a forma mais barata de mentir.

    ERAM QUATRO, VIRARAM DOIS E HOJE SÃO QUATRO DE NOVO — e as duas contas são
    a mesma regra. `degrau-aceso` e `mult-teto` fecharam pela manhã de 03/09;
    ficar na lista depois de pintados seria a mentira SIMÉTRICA — dívida
    fantasma, que faz a próxima pessoa esperar por uma cura que já chegou.

    À TARDE ENTRARAM DUAS, e as duas nasceram da decisão dela de construir a
    política POR CONTROLE: `forca:auto-da-mesa` (pôr a MESA em `Auto` perdeu o
    botão, porque o esquema recusa `auto` por unidade) e `forca:global-em-auto`
    (com o global em `Auto` o produto PULA o override, e a tela ainda não
    avisa).

    **E `forca:global-em-auto` SAIU EM 04/09/2026** — pela mesma regra que fez
    `degrau-aceso` e `mult-teto` saírem: a cura chegou. Ele dizia *"o que falta
    é a tela AVISAR"*, e a tela avisa agora em DOIS tempos, que é o que a
    condição pede: `a05_vibracao._aplicar_a_forca` leva a frase ao cartão no
    instante do clique, e `a05_vibracao._ressalva_da_mesa` põe a linha no
    `#vib-estado` **enquanto a condição existir** — inclusive para quem abrir a
    aba amanhã sem ter clicado nada. A prova das duas metades está em
    `test_a05_a_vibracao_aplica_e_fala.py`, com a mordida dos dois lados.

    A `barra:forca` SAIU no dia anterior — a barra virou arrastável e grava.

    **E AS DUAS ÚLTIMAS SAÍRAM EM 04/09/2026, pela mesma regra e no mesmo dia
    em que ela decidiu as duas:**

    * `barra:motor` esperava *a palavra dela* sobre o par `weak`/`strong`. Ela
      veio, e desfez a premissa: a barra **não manda o par** — ela é POLÍTICA
      que MULTIPLICA o degrau, e as duas são independentes. O método existe
      (`rumble.motores.set`), o gesto é `a05_vibracao.motor`;
    * `forca:auto-da-mesa` dizia que pôr a MESA em `Auto` perdera o botão e que
      o desenho era decisão dela. Ela escolheu a **linha de mesa embaixo da
      grade** (decisão [05]), e o gesto é `a05_vibracao.forca_da_mesa`.

    `lado:ligado` é o que sobra, e continua sem existir em linha nenhuma do
    produto — nem campo no esquema, nem método de IPC, nem chave no `state_full`.
    """
    pacote, _ = emitidos
    assert set(pacote["sem_dono"]) == {"lado:ligado"}
    for chave, razao in pacote["sem_dono"].items():
        assert len(razao) > 80, f"{chave} declara sem dizer por quê"
    # E O QUE FECHOU É PINTADO — sem isto, apagar da lista seria indistinguível
    # de esconder a dívida debaixo do tapete.
    col = next(iter(pacote["colunas"].values()))
    assert "mult-teto" in col, "o `Máx` voltou a ser texto cravado no desenho"
    assert pacote["mesa"].get("degrau-mesa") is None, (
        "a linha de mesa não pinta o degrau geral — e era ela que a "
        "`forca:auto-da-mesa` esperava")
    for lado in ("e", "d"):
        assert f"barra-{lado}" in col, (
            f"a barra do motor {lado!r} não é pintada — era ela que a "
            f"`barra:motor` esperava")
