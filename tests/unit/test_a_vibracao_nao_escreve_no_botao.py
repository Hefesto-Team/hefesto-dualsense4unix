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
#: OS ALVOS QUE NÃO ENCOSTAM NO TEXTO. `texto` (o padrão) e `html` reescrevem o
#: conteúdo do elemento; `classe`, `largura`, `fundo`, `valor` e `cor` mexem numa
#: classe, num estilo ou no `value`, e o rótulo do botão sobrevive intacto.
#:
#: A DISTINÇÃO ENTROU EM 02/09/2026, com o endereço do degrau aceso. Sem ela
#: esta régua reprovava a cura: os quatro degraus passaram a levar
#: `data-campo="degrau" data-hef-alvo="classe"`, que é justamente o alvo que
#: NÃO apaga "Economia"/"Balanceado"/"Máximo"/"Auto" — a prova está no
#: `test_o_degrau_aceso_nao_apaga_o_rotulo`, que roda o `escrever()` de verdade.
#: Medir "tem endereço num botão" em vez de "escreve TEXTO num botão" seria a
#: régua confundindo o endereço com o ato, que é o vício desta casa.
ALVOS_QUE_ESCREVEM_TEXTO = ("texto", "html")


def test_nenhuma_chave_do_pacote_escreve_num_botao(arvore, emitidos):
    """Escrever um valor num `<button>` APAGA o rótulo dele.

    Foi assim que "Economia", "Balanceado", "Máximo" e "Auto" viraram os quatro
    a palavra "balanceado", e ela deixou de poder escolher o degrau.
    """
    _, chaves = emitidos
    culpados = {
        chave: [n["attrs"].get("data-forca") or n["attrs"].get("data-lado") or "?"
                for n in _achar(arvore, chave)
                if n["tag"] == "button"
                and (n["attrs"].get("data-hef-alvo") or "texto")
                in ALVOS_QUE_ESCREVEM_TEXTO]
        for chave in sorted(chaves)
    }
    culpados = {k: v for k, v in culpados.items() if v}
    assert not culpados, (
        f"o pacote emite chave que cai DENTRO de um botão: {culpados}. "
        f"O pintor escreve `textContent`, então o rótulo do botão some.")


def test_nenhuma_chave_do_pacote_apaga_outra(arvore, emitidos):
    """Pintar um elemento que CONTÉM outro endereço apaga o de dentro.

    `textContent` substitui a subárvore inteira. A linha do "Personalizado"
    guardava o trilho (`forca-pct`) e o número (`mult`) dentro de um elemento que
    também era endereço — e a pintura seguinte já não achava nem um nem outro.
    """
    _, chaves = emitidos
    por_chave = {chave: _achar(arvore, chave) for chave in chaves}
    dentro = {n["attrs"].get(e) for ns in por_chave.values() for n in ns
              for e in ENDERECOS if n["attrs"].get(e)}
    falhas = []
    for chave, nos in sorted(por_chave.items()):
        for no in nos:
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
    """
    mudos = [(n["attrs"]["data-papel"], _dono(n)) for n in _todos(arvore)
             if n["attrs"].get("data-papel") in ("testar", "parar")]
    assert len(mudos) == 4, f"são dois botões em duas colunas, e achei {len(mudos)}"
    assert all(dono for _, dono in mudos), (
        f"clique sem dono, e o gesto vai recusar: {mudos}")


# --------------------------------------------------------------------------
# 3. o que o pacote escreve é o que a caixa pede
# --------------------------------------------------------------------------
def test_o_multiplicador_e_o_numero_e_nao_o_degrau(emitidos):
    """A caixa do "Personalizado" pede o NÚMERO, e o desenho escreve `150%`.

    O pacote mandava ali o nome do degrau (`balanceado`). O número sai do
    produto — `app/telas/vibracao._barra` sobre `rumble_mult_applied` — e com
    0,7 aplicado ele é `70%`.
    """
    pacote, _ = emitidos
    col = next(iter(pacote["colunas"].values()))
    assert col["mult"] == "70%", f"o multiplicador saiu {col['mult']!r}"
    assert col["forca-pct"] == "46.7", (
        f"a largura da barra saiu {col['forca-pct']!r} — 70 de um teto de 150")
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


def test_a_mesa_desta_aba_nao_emite_valor(emitidos):
    """Nada da MESA tem endereço nesta página — e emitir sem endereço custou caro.

    `rumble_policy` e `rumble_passthrough` não têm `data-campo` nenhum: o degrau
    aceso é uma CLASSE, e o pintor não mexe em classe. O que a chave `forca`
    fazia era só destruição.
    """
    pacote, _ = emitidos
    assert pacote["mesa"] == {}, f"a mesa voltou a emitir: {pacote['mesa']}"


def test_o_que_falta_esta_declarado(emitidos):
    """O que a tela mostra e este pacote não pinta tem NOME e DONO da cura.

    `SEM_DONO` estava `{}` — o vazio dizia "nada falta" numa aba onde quatro
    coisas faltavam, e é a forma mais barata de mentir.
    """
    pacote, _ = emitidos
    assert set(pacote["sem_dono"]) == {"degrau-aceso", "mult-teto",
                                       "lado:ligado", "barra:motor"}
    for chave, razao in pacote["sem_dono"].items():
        assert len(razao) > 80, f"{chave} declara sem dizer por quê"
