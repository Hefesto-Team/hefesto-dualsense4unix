"""aba_conexoes — os valores e os gestos da aba 08, com endereço, sem GTK.

A aba **Conexões** no motor novo: o mockup aprovado (`08-conexoes.html`) rodando
num ``WebKit2.WebView``, e este módulo é o lado Python dela — o que pinta e o que
ouve. A janela, as duas pontes e a guarda de carga **não estão aqui**: são de
:mod:`hefesto_dualsense4unix.gui.ponte_da_tela`, que nasceu para as dez abas.

POR QUE ELE NÃO IMPORTA GTK, NEM LÊ ``/sys``, NEM FALA COM O DAEMON
-------------------------------------------------------------------
Tudo aqui é função pura sobre dado já lido. Quem lê é quem chama — o piloto, a
GUI ou a régua —, e passa o resultado por argumento. São três consequências
medidas, não gosto:

1. **A régua mede este código, não uma cópia dele.** A régua da aba Controles
   herda o piloto justamente para isso; aqui ela nem precisa herdar: chama a
   mesma função que a interface chama.
2. **Os portões alcançam.** Os comandos exatos do CI são ``ruff check src/
   tests/`` e ``mypy src/hefesto_dualsense4unix``, e nenhum dos dois alcança
   ``scripts/`` ou ``novo-layout/`` (que é ``.gitignore:108`` e não viaja em
   worktree nenhum).
3. **O dublê é o caso normal, não um modo de teste.** Os três quadros desta aba
   são alimentáveis por injeção — ``mesa_de_radio.ler_a_mesa`` recebe os
   leitores, ``radio_da_mesa.ocupacao_por_adaptador`` também, e o exame recebe os
   :class:`~hefesto_dualsense4unix.integrations.exame_da_mesa.Item` prontos. Foi
   assim que esta aba se ligou inteira com o daemon dela DESLIGADO.

A GRAMÁTICA DOS ENDEREÇOS
-------------------------
Proposta na ``MIGRA-CONEXOES-03`` e adotada aqui sem mudança, porque duas
gramáticas de endereço seriam a segunda verdade que a regra do fato errado existe
para matar:

* ``data-v="<família>.<campo>"`` — o que o Python **pinta**;
* ``data-g="<gesto>"`` — o que o Python **recebe**;
* a chave de um controle é o ``uniq``, **nunca** o ``p1``/``p2`` do mockup. O
  ``p1..p4`` é posição na mesa de exemplo, e endereço por posição é o "jogador 3
  fantasma" voltando pela porta dos atributos. :func:`endereco_por_posicao`
  existe para uma régua poder reprovar isso.

**O endereço nasce na mesma f-string do valor** (:func:`html_das_linhas` e
irmãs), e é por isso que ele não pode divergir dele: não há uma tabela de
endereços de um lado e uma pintura do outro.

O QUE ESTA ABA MOSTRA E O PRODUTO NÃO SABE
------------------------------------------
Está em :data:`SEM_FONTE`, com o motivo de cada um. **Um número plausível e falso
é pior que um traço honesto**, porque ela confia nele: o que não tem fonte é
pintado como :data:`TRACO` e a régua exige que continue assim.
"""
from __future__ import annotations

import html
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

#: O que se escreve onde não há dado. Um traço é uma resposta; um número
#: inventado é uma mentira que ninguém audita depois.
TRACO = "—"

#: As famílias de endereço desta aba. Uma família por bloco da tela, e o
#: conjunto é FECHADO: endereço fora dele é endereço órfão — alguém o escreveu e
#: ninguém o pinta —, e :func:`familia_de` o recusa.
FAMILIAS: frozenset[str] = frozenset(
    {"mesa", "controle", "exame", "ordem", "adaptador", "vizinho", "pista", "rodape"}
)

#: Os gestos que esta aba oferece, e o conjunto também é fechado. Um botão que a
#: tela desenha e o Python não conhece é o "botão morto" que custou a esta casa
#: uma leva inteira em 29/08: tinha ``cursor:pointer``, era pintado, e não tinha
#: ouvinte nenhum.
GESTOS: frozenset[str] = frozenset(
    {
        "controle.mic.existe",
        "controle.mic.escopo",
        "controle.vibracao.teto",
        "controle.luz.nao-acende",
        "controle.abrir",
        "exame.reexaminar",
        "exame.ja-movi",
        "exame.ignorar",
        "exame.ignoradas",
        "adaptador.renomear",
        "vizinho.oque",
        "mesa.mapear-entradas",
        "mesa.mapear-entrada-a-entrada",
        "rodape.aplicar",
        "rodape.salvar",
        "rodape.importar",
        "rodape.exportar",
    }
)

#: O QUE A TELA MOSTRA E O PRODUTO NÃO TEM DE ONDE TIRAR — declarado, nunca
#: inventado. Cada linha é ``(endereço, o que falta, quem fecha)``.
#:
#: Isto não é lápide calada: as três primeiras têm sprint com dono, e as duas
#: últimas são contradições entre dois documentos que ela aprovou — quem as fecha
#: é uma frase dela, não um agente.
SEM_FONTE: tuple[tuple[str, str, str], ...] = (
    (
        "exame.quando",
        'A tela diz "Examinado há 3 minutos". O exame não guarda quando correu: '
        "`exame_da_mesa` devolve os cinco `Item` e nenhum carimbo de tempo.",
        "MIGRA-CONEXOES-07 — quem der o carimbo dá o texto.",
    ),
    (
        "controle.*.mascara",
        "A tela mostra uma máscara POR CONTROLE (o mockup pinta quatro "
        "diferentes). O produto guarda UMA por máquina, em "
        "`state['gamepad_emulation']['flavor']` — o item de `controllers` não "
        "tem o campo.",
        "Contradição NOVA, sem sprint: não está no §0 do índice desta onda.",
    ),
    (
        "controle.*.mic.escopo",
        "A tela oferece a escolha por controle. O produto guarda um valor por "
        "máquina, em `state['mic_button_toggles_system']`.",
        "MIGRA-CONEXOES-06 — §0.7 do índice, e é palavra dela.",
    ),
    (
        "controle.*.vibracao.teto",
        "A tela oferece 'Segue o global / Sem teto / 30%' por controle. O "
        "produto aplica `min` (`core/rumble.py`), e o `min` é o que impede um "
        "'teto' de AUMENTAR a força — sobrepor mudaria o daemon, não a tela.",
        "MIGRA-CONEXOES-11 — §0.5 do índice, e é palavra dela.",
    ),
    (
        "vizinho.*.qual",
        "O que cada rádio vizinho É ('Wi-Fi', 'Teclado'...) é declaração dela, "
        "guardada em `maquina.json`. Sem declaração o produto sabe o "
        "vid:pid e mais nada — e adivinhar pelo vid:pid seria inventar.",
        "Já responde: `ordens_da_mesa.Leitura.nomes_declarados` quando existe.",
    ),
)


class EnderecoInvalido(ValueError):  # noqa: N818 — o projeto é em português
    """Endereço fora da gramática. É erro de programação, não de dado."""


def familia_de(endereco: str) -> str:
    """A família de um ``data-v``, recusando o que está fora do conjunto fechado.

    Recusar aqui, e não na régua, é o que impede um endereço órfão de nascer:
    quem escrever ``data-v="controles.p1"`` (plural, e por posição) descobre no
    ato, não três abas depois.
    """
    familia = endereco.split(".", 1)[0]
    if familia not in FAMILIAS:
        raise EnderecoInvalido(
            f"{endereco!r}: família {familia!r} não é uma das {sorted(FAMILIAS)}"
        )
    return familia


def endereco_por_posicao(endereco: str) -> bool:
    """O endereço fala de POSIÇÃO na mesa em vez de identidade?

    ``controle.p1.bateria`` é o jogador fantasma voltando: o ``p1..p4`` do mockup
    é a ordem da mesa de exemplo, e a mesa de verdade muda de ordem quando um
    controle sai. A chave tem de ser o ``uniq``.
    """
    return any(
        pedaco[:1] == "p" and pedaco[1:].isdigit() for pedaco in endereco.split(".")
    )


def v(*partes: str) -> str:
    """Monta um ``data-v`` e o valida na hora. ``v("controle", uniq, "bateria")``."""
    endereco = ".".join(str(p) for p in partes)
    familia_de(endereco)
    if endereco_por_posicao(endereco):
        raise EnderecoInvalido(
            f"{endereco!r}: endereço por POSIÇÃO. A chave de um controle é o "
            "uniq — p1..p4 é a mesa de exemplo do mockup."
        )
    return endereco


def g(gesto: str) -> str:
    """Valida um ``data-g`` contra :data:`GESTOS`. Gesto novo entra na lista."""
    if gesto not in GESTOS:
        raise EnderecoInvalido(f"{gesto!r} não está em GESTOS — declare-o antes de usá-lo")
    return gesto


def _e(texto: object) -> str:
    """Escapa para HTML. Todo texto que vem de fora passa por aqui.

    Um adaptador chamado ``Sala <do fundo>`` não pode virar tag, e um apelido com
    aspas não pode fechar o atributo em que ele está.
    """
    return html.escape(str(texto), quote=True)


# ---------------------------------------------------------------------------
# Quadro 1 — Gestão Controles
# ---------------------------------------------------------------------------
#: Como a tela chama cada transporte. O produto diz ``usb``/``bt``.
NOME_DO_TRANSPORTE = {"usb": "USB", "bt": "BT", "bluetooth": "BT"}

#: Como a tela chama cada máscara. É o ``flavor`` do produto, e ele é GLOBAL —
#: veja :data:`SEM_FONTE`.
NOME_DA_MASCARA = {"dualsense": "DualSense", "xbox": "Xbox 360", "nintendo": "Nintendo Pro"}


@dataclass(frozen=True)
class Controle:
    """Uma linha do quadro "Gestão Controles" — só o que ESTA aba mostra.

    ``plastico`` é a cor lida do aparelho, ``""`` quando ninguém a leu. A borda
    fica neutra nesse caso, e é a regra da tela: *uma borda colorida seria uma
    cor que ninguém leu*.
    """

    uniq: str
    jogador: int
    via: str
    bateria: int | None
    plastico: str = ""
    cor_nome: str = ""
    fabricante: str = "Sony"
    mic_ligado: bool = True

    @property
    def nome(self) -> str:
        """``Sony • Player 1 • Cosmic Red • USB`` — a linha de identidade."""
        pedacos = [self.fabricante, f"Player {self.jogador}"]
        if self.cor_nome:
            pedacos.append(self.cor_nome)
        pedacos.append(NOME_DO_TRANSPORTE.get(self.via, self.via.upper()))
        return " • ".join(pedacos)

    @property
    def texto_da_bateria(self) -> str:
        return TRACO if self.bateria is None else f"{self.bateria}%"

    @property
    def pelo_radio(self) -> bool:
        return self.via not in ("usb", "cabo")

    @property
    def texto_do_microfone(self) -> str:
        """*Ligado, pelo rádio • Pela ponte* — e o "por onde" NÃO é escolha.

        Pelo cabo o microfone chega pela placa de áudio do próprio aparelho;
        pelo rádio, pela ponte do Hefesto, porque o DualSense não tem A2DP nem
        HFP. Quem decide é o transporte, e por isso esta frase é derivada, nunca
        perguntada.
        """
        estado = "Ligado" if self.mic_ligado else "Desligado"
        if self.pelo_radio:
            return f"{estado}, pelo rádio • Pela ponte"
        return f"{estado}, pelo cabo • Placa do controle"


def controles_do_estado(
    estado: Mapping[str, Any],
    cores: Mapping[str, tuple[str, str]] | None = None,
) -> list[Controle]:
    """Os controles LIGADOS do ``daemon.state_full``, na ordem em que a tela os põe.

    ``cores`` é ``{uniq: (hexa, nome)}`` — o que o leitor de cor já respondeu.
    Ausência é resposta: sem entrada, a borda fica neutra e o nome sai sem a cor.
    """
    conhecidas = dict(cores or {})
    linhas: list[Controle] = []
    for bruto in estado.get("controllers") or []:
        if not isinstance(bruto, Mapping) or not bruto.get("connected"):
            continue
        uniq = str(bruto.get("uniq") or "")
        if not uniq:
            # Sem uniq não há endereço, e um endereço por índice seria o
            # jogador fantasma. Uma linha a menos é melhor que uma linha que
            # troca de dono quando a mesa muda de ordem.
            continue
        hexa, nome = conhecidas.get(uniq, ("", ""))
        bateria = bruto.get("battery_pct")
        linhas.append(
            Controle(
                uniq=uniq,
                jogador=int(bruto.get("player") or bruto.get("index", 0) + 1),
                via=str(bruto.get("transport") or ""),
                bateria=int(bateria) if isinstance(bateria, int | float) else None,
                plastico=hexa,
                cor_nome=nome,
            )
        )
    return linhas


def texto_da_contagem(controles: Sequence[Controle]) -> str:
    """``4 na mesa • 2 no cabo • 2 no rádio`` — o canto do quadro 1."""
    radio = sum(1 for c in controles if c.pelo_radio)
    cabo = len(controles) - radio
    return f"{len(controles)} na mesa • {cabo} no cabo • {radio} no rádio"


def mascara_da_maquina(estado: Mapping[str, Any]) -> str:
    """A máscara que o jogo vê — UMA, da máquina inteira.

    A tela mostra uma por controle e o produto tem uma só: está em
    :data:`SEM_FONTE`. Enquanto a contradição não se fecha, as quatro linhas
    dizem a MESMA verdade — que é o que o produto sabe — em vez de quatro
    máscaras diferentes que ninguém guarda.
    """
    emulacao = estado.get("gamepad_emulation")
    sabor = ""
    if isinstance(emulacao, Mapping):
        sabor = str(emulacao.get("flavor") or "")
    return NOME_DA_MASCARA.get(sabor, TRACO)


def html_das_linhas(controles: Sequence[Controle], mascara: str) -> str:
    """As linhas do quadro 1, com o endereço nascendo na f-string do valor.

    A remontagem é a mesma disciplina do produto e do piloto: o corpo se
    reconstrói quando a CHAVE da mesa muda (quem está, com que cor, por onde), e
    no resto do tempo a pintura faz diff. Sem isso a cor que chega três segundos
    depois — é uma pergunta ao aparelho, em thread — nunca apareceria.
    """
    return "".join(
        _html_de_uma_linha(c, mascara, posicao) for posicao, c in enumerate(controles, 1)
    )


#: Quantas fatias o acordeão do mockup tem. A CSS dela nomeia `gc-p1..gc-p4` uma
#: a uma, então a quinta linha não teria como abrir: a mesa mostra as quatro
#: primeiras e :func:`sobraram` diz quantas ficaram de fora, em voz alta.
FATIAS_DO_ACORDEAO = 4


def _html_de_uma_linha(c: Controle, mascara: str, posicao: int) -> str:
    """Uma linha do acordeão. **A CLASSE É POSIÇÃO; O ENDEREÇO É IDENTIDADE.**

    As duas convivem de propósito, e a distinção é o coração da gramática:

    * ``class="gc-item gc-p2"`` e ``<label for="gc-p2">`` são o gancho da CSS
      DELA — o acordeão do mockup é CSS pura (``#gc-p2:checked ~ .gc .gc-p2``), e
      "a segunda fatia do acordeão" é posicional por natureza. Trocar isso por
      JavaScript seria reescrever o desenho aprovado para não mudar nada que se
      veja.
    * ``data-controle``, ``data-v`` e ``data-g`` são o ``uniq``, sempre. É por
      eles que o Python pinta e ouve, e é o que impede o "jogador 3 fantasma":
      quando um controle sai da mesa, a fatia 2 passa a ser outro aparelho e
      **nenhum endereço muda de dono**, porque nenhum endereço fala de fatia.
    """
    borda = f"--plastico:{_e(c.plastico)}" if c.plastico else ""
    fatia = f"gc-p{posicao}"
    return (
        f'<div class="gc-item {fatia}" data-controle="{_e(c.uniq)}" style="{borda}">'
        f'<div class="gc-cabeca">'
        f'<label class="gc-abre" for="{fatia}" data-g="{g("controle.abrir")}" '
        f'data-alvo="{_e(c.uniq)}">'
        f'<span class="gc-nome" data-v="{v("controle", c.uniq, "nome")}">{_e(c.nome)}</span>'
        f'<span class="gc-resumo">'
        f'<span>Vê como <b data-v="{v("controle", c.uniq, "mascara")}">{_e(mascara)}</b></span>'
        f'<span data-v="{v("controle", c.uniq, "mic")}">{_e(c.texto_do_microfone)}</span>'
        f'<span>Bateria <b data-v="{v("controle", c.uniq, "bateria")}">'
        f"{_e(c.texto_da_bateria)}</b></span>"
        f"</span></label>"
        f'<label class="gc-seta abre" for="{fatia}">▾</label>'
        f'<label class="gc-seta so" for="{fatia}">só este</label>'
        f'<label class="gc-seta fecha" for="gc-todos">▴</label></div>'
        f'<div class="gc-corpo">'
        f'<span class="gc-bloco">'
        f'<select class="pronto" data-g="{g("controle.mic.existe")}" '
        f'data-alvo="{_e(c.uniq)}">'
        f'<option{" selected" if c.mic_ligado else ""}>Ligado</option>'
        f'<option{"" if c.mic_ligado else " selected"}>Desligado</option></select>'
        f'<select class="pronto" data-g="{g("controle.mic.escopo")}" '
        f'data-alvo="{_e(c.uniq)}">'
        f"<option selected>Só este controle</option>"
        f"<option>O computador inteiro</option></select></span>"
        f'<span class="gc-bloco barra">'
        f'<select class="pronto" data-g="{g("controle.vibracao.teto")}" '
        f'data-alvo="{_e(c.uniq)}">'
        f"<option selected>Segue o global</option><option>Sem teto</option>"
        f"<option>30% da força</option></select></span>"
        f'<button class="btn apagado" data-g="{g("controle.luz.nao-acende")}" '
        f'data-trava="{v("controle", c.uniq, "luz")}" '
        f'data-alvo="{_e(c.uniq)}"{"" if c.pelo_radio else " disabled"}>'
        f"A luz não acende</button>"
        f"</div></div>"
    )


# ---------------------------------------------------------------------------
# Quadro 2 — Está tudo certo?
# ---------------------------------------------------------------------------
#: O selo de cada estado do exame. As chaves são as de
#: `integrations/exame_da_mesa`, e a tradução mora aqui porque é palavra de TELA:
#: o módulo do exame responde por máquina, não por vocabulário.
SELO_DO_ESTADO = {
    "certo": ("ok", "CERTO"),
    "atencao": ("warn", "AJUSTAR"),
    "problema": ("warn", "AJUSTAR"),
    "nao_sei": ("info", "NOTA"),
}


def html_do_exame(itens: Iterable[Any]) -> str:
    """As linhas conferidas, uma por :class:`Item` do ``exame_da_mesa``.

    O texto é o ``porque`` — a MEDIÇÃO em uma frase —, nunca o rótulo: a tela
    aprovada mostra o que se achou, não o nome do que se conferiu.
    """
    linhas = []
    for item in itens:
        classe, palavra = SELO_DO_ESTADO.get(str(item.estado), ("info", "NOTA"))
        chave = str(item.chave)
        linhas.append(
            f'<div class="exame">'
            f'<span class="selo {classe}" data-v="{v("exame", chave, "selo")}">{_e(palavra)}</span>'
            f'<span class="txt" data-v="{v("exame", chave, "txt")}">{_e(item.porque)}</span>'
            f"</div>"
        )
    return "".join(linhas)


def html_da_ordem(ordem: Any | None) -> str:
    """A ordem de serviço — o imperativo, o de→para e o ganho.

    ``None`` é uma resposta e tem texto próprio: "nenhuma ordem pendente" é o que
    a pessoa precisa ler, e um quadro vazio a deixaria sem saber se o exame não
    achou nada ou se ele não correu.
    """
    if ordem is None:
        return (
            f'<div class="ordem"><div class="faca" data-v="{v("ordem", "acao")}">'
            f"Nenhuma mudança recomendada agora.</div></div>"
        )
    return (
        f'<div class="ordem">'
        f'<div class="faca" data-v="{v("ordem", "acao")}">{_e(ordem.acao)}</div>'
        f'<div class="receita">'
        f'<span class="caixa" data-v="{v("ordem", "de")}">{_e(ordem.alvo.onde or TRACO)}</span>'
        f'<span class="seta">→</span>'
        f'<span class="caixa alvo" data-v="{v("ordem", "para")}">'
        f"{_e(ordem.destino or TRACO)}</span></div>"
        f'<div class="ganho"><span>Ganho esperado:</span> '
        f'<span data-v="{v("ordem", "ganho")}">{_e(ordem.ganho_esperado.texto)}</span></div>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Quadro 3 — Rádio e adaptadores
# ---------------------------------------------------------------------------
def html_dos_adaptadores(
    adaptadores: Sequence[Any], apelidos: Mapping[str, str] | None = None
) -> str:
    """A tabela dos adaptadores Bluetooth: nome, modelo, onde está.

    **O ``hciN`` nunca entra.** Ele inverte entre boots, e a decisão M1 desta
    casa o proíbe na tela; o que endereça a linha é o ``caminho`` de barramento
    (``3-1.1.4``), que é a palavra comum entre este módulo, o censo e o mapa.
    """
    nomes = dict(apelidos or {})
    linhas = []
    for a in adaptadores:
        caminho = str(a.caminho) or str(a.interface)
        apelido = nomes.get(caminho, "")
        onde = f"Entrada {a.painel}" if a.painel else ("Interno" if not a.caminho else TRACO)
        modelo = f"{a.vid}:{a.pid}" if a.vid else TRACO
        mudo = "" if apelido else ' class="mudo"'
        linhas.append(
            f'<tr data-adaptador="{_e(caminho)}">'
            f'<td data-v="{v("adaptador", caminho, "nome")}"{mudo}>'
            f'{_e(apelido or "Sem nome")}</td>'
            f'<td class="mudo" data-v="{v("adaptador", caminho, "modelo")}">{_e(modelo)}</td>'
            f'<td data-v="{v("adaptador", caminho, "onde")}">{_e(onde)}</td>'
            f'<td style="text-align:right"><span class="acao" '
            f'data-g="{g("adaptador.renomear")}" data-alvo="{_e(caminho)}">Renomear</span></td>'
            f"</tr>"
        )
    return "".join(linhas)


#: As respostas do "— O que é? —". A primeira é a pergunta em si: enquanto ela
#: estiver escolhida, o produto NÃO sabe, e a tela diz isso em vez de chutar.
RESPOSTAS_DO_VIZINHO = (
    "— O que é? —",
    "Wi-Fi",
    "Teclado",
    "Mouse",
    "Webcam",
    "Caixa de som",
    "Outro",
    "Não sei",
)


def html_dos_vizinhos(radios: Sequence[Any], declarados: Mapping[str, str] | None = None) -> str:
    """Os outros rádios na faixa de 2,4 GHz, com o que ela declarou de cada um.

    Sem declaração o ``<select>`` fica na pergunta — e é honesto: o produto sabe
    o ``vid:pid`` e mais nada. Adivinhar "Wi-Fi" a partir de um vid seria
    exatamente o número plausível e falso que esta aba não escreve.
    """
    conhecidos = dict(declarados or {})
    blocos = []
    for r in radios:
        caminho = str(r.caminho)
        chave = f"{r.vid}:{r.pid}"
        qual = conhecidos.get(chave, "")
        escolhida = qual or RESPOSTAS_DO_VIZINHO[0]
        opcoes = "".join(
            f'<option{" selected" if o == escolhida else ""}>{_e(o)}</option>'
            for o in RESPOSTAS_DO_VIZINHO
        )
        blocos.append(
            f'<div class="viz" data-vizinho="{_e(caminho)}">'
            f'<span class="qual" data-v="{v("vizinho", caminho, "qual")}">{_e(chave)}</span>'
            f'<select class="pronto{"" if qual else " pergunta"}" '
            f'data-g="{g("vizinho.oque")}" data-alvo="{_e(caminho)}">{opcoes}</select></div>'
        )
    return "".join(blocos)


def html_das_pistas(
    adaptadores: Sequence[Any],
    ocupacoes: Mapping[str, Any],
    apelidos: Mapping[str, str] | None = None,
) -> str:
    """A régua de Desempenho: o rádio de cada adaptador, em turnos.

    O teto e os turnos vêm de ``integrations/radio_da_mesa`` — ``SLOTS_POR_SEGUNDO``
    e as frações CRUAS. Passar de 1,0 é resultado legítimo e a barra precisa
    saber dizê-lo, então nada aqui satura a largura em 100%.
    """
    nomes = dict(apelidos or {})
    linhas = []
    for a in adaptadores:
        caminho = str(a.caminho) or str(a.interface)
        quem = nomes.get(caminho, "") or "Sem nome"
        oc = ocupacoes.get(caminho)
        if oc is None or not oc.controles:
            trilho = '<span class="vazio">Nenhum controle neste rádio</span>'
            numero = f"0 <i>de {_turnos(None)}</i>"
        else:
            largura = oc.fracao_input * 100
            trilho = (
                f'<span class="bloco usa" style="width:{largura:.2f}%">'
                f"{oc.controles} de {oc.slots_input / max(oc.controles, 1):.1f}</span>"
            )
            if oc.slots_audio:
                trilho += (
                    f'<span class="bloco mic" style="width:{oc.fracao_audio * 100:.2f}%"></span>'
                )
            numero = f"{oc.slots_total:.1f} <i>de {_turnos(oc)}</i>"
        linhas.append(
            f'<div class="pista" data-pista="{_e(caminho)}">'
            f'<span class="quem" data-v="{v("pista", caminho, "quem")}">{_e(quem)}</span>'
            f'<span class="trilho" data-v="{v("pista", caminho, "trilho")}">{trilho}</span>'
            f'<span class="num" data-v="{v("pista", caminho, "num")}">{numero}</span></div>'
        )
    return "".join(linhas)


def _turnos(ocupacao: Any | None) -> str:
    """O teto, sempre lido do produto — nunca digitado aqui."""
    from hefesto_dualsense4unix.integrations.radio_da_mesa import SLOTS_POR_SEGUNDO

    teto = SLOTS_POR_SEGUNDO if ocupacao is None else ocupacao.slots_teto
    return f"{teto:,}".replace(",", ".")


# ---------------------------------------------------------------------------
# O pacote de um tique
# ---------------------------------------------------------------------------
@dataclass
class Pintura:
    """O que UMA pintura escreve. É o argumento de ``HEF.pinta``.

    ``remonta`` traz o HTML dos blocos cuja LISTA mudou (quem está na mesa, quais
    adaptadores, quais vizinhos); ``valores`` traz o resto, por endereço. A
    separação é o que faz a pintura custar um diff em vez de um ``innerHTML`` a
    cada 100 ms.
    """

    valores: dict[str, str] = field(default_factory=dict)
    remonta: dict[str, str] = field(default_factory=dict)
    travas: dict[str, bool] = field(default_factory=dict)

    def como_dicionario(self) -> dict[str, Any]:
        return {"valores": self.valores, "remonta": self.remonta, "travas": self.travas}

    def __len__(self) -> int:
        """Quantos valores esta pintura escreve — a régua do orçamento do tique."""
        return len(self.valores) + len(self.remonta) + len(self.travas)


def pintura(
    estado: Mapping[str, Any],
    *,
    controles: Sequence[Controle] | None = None,
    itens_do_exame: Sequence[Any] = (),
    ordem: Any | None = None,
    adaptadores: Sequence[Any] = (),
    radios: Sequence[Any] = (),
    ocupacoes: Mapping[str, Any] | None = None,
    apelidos: Mapping[str, str] | None = None,
    declarados: Mapping[str, str] | None = None,
    remontar: bool = True,
) -> Pintura:
    """Um ``state_full`` e as leituras da mesa viram UMA pintura.

    **Uma chamada por TIQUE, não por valor.** Com 50 valores e quatro controles,
    uma chamada por valor seriam centenas de travessias de fronteira por segundo;
    quem monta o pacote é aqui e quem o distribui é a página.
    """
    linhas = list(controles) if controles is not None else controles_do_estado(estado)
    mascara = mascara_da_maquina(estado)
    p = Pintura()

    p.valores[v("mesa", "conta")] = texto_da_contagem(linhas)
    p.valores[v("rodape", "recibo")] = str(estado.get("active_profile") or TRACO)
    p.valores[v("exame", "quando")] = TRACO  # SEM_FONTE: o exame não se carimba

    for c in linhas:
        p.valores[v("controle", c.uniq, "nome")] = c.nome
        p.valores[v("controle", c.uniq, "mascara")] = mascara
        p.valores[v("controle", c.uniq, "mic")] = c.texto_do_microfone
        p.valores[v("controle", c.uniq, "bateria")] = c.texto_da_bateria
        # TRAVAR É ESCRITA, e por isso conta: um botão que a tela oferece e o
        # produto recusa é mentira. "A luz não acende" só existe no rádio — a
        # cura dele é derrubar a conexão Bluetooth para ela apertar PS.
        p.travas[v("controle", c.uniq, "luz")] = not c.pelo_radio

    if remontar:
        # AS CHAVES SÃO NOMES, NÃO SELETORES CSS. Quem sabe onde cada bloco mora
        # é a página (`HEF.remonta`), e a razão é de dono: o seletor é da folha
        # DELA, e um Python que os escrevesse passaria a ser o segundo dono do
        # desenho — a cada classe renomeada no mockup, uma pintura muda calada.
        # Com nomes, renomear uma classe quebra em UM lugar, e ruidosamente.
        p.remonta["controles"] = html_das_linhas(linhas[:FATIAS_DO_ACORDEAO], mascara)
        p.remonta["exame"] = html_do_exame(itens_do_exame)
        p.remonta["ordem"] = html_da_ordem(ordem)
        p.remonta["adaptadores"] = html_dos_adaptadores(adaptadores, apelidos)
        p.remonta["vizinhos"] = html_dos_vizinhos(radios, declarados)
        p.remonta["pistas"] = html_das_pistas(adaptadores, ocupacoes or {}, apelidos)
    return p


def sobraram(controles: Sequence[Controle]) -> int:
    """Quantos controles a mesa tem além das :data:`FATIAS_DO_ACORDEAO`.

    Zero é o caso normal — a mesa dela tem quatro. Um número maior é uma tela
    que está ESCONDENDO controle ligado, e quem chama tem de dizê-lo: calar
    seria o defeito de 22/08, a ausência de notícia lida como sucesso.
    """
    return max(0, len(controles) - FATIAS_DO_ACORDEAO)


def chave_da_mesa(
    controles: Sequence[Controle],
    adaptadores: Sequence[Any] = (),
    radios: Sequence[Any] = (),
) -> tuple[Any, ...]:
    """A assinatura que decide REMONTAR ou fazer diff.

    Entram a cor, o nome, o transporte e o jogador porque os quatro estão
    ASSADOS no HTML da linha: sem eles, a cor que chega depois — é uma pergunta
    ao aparelho, em thread — nunca apareceria na tela.
    """
    return (
        tuple((c.uniq, c.plastico, c.cor_nome, c.via, c.jogador) for c in controles),
        tuple(str(a.caminho) for a in adaptadores),
        tuple(str(r.caminho) for r in radios),
    )


def gesto_valido(objeto: Mapping[str, Any]) -> bool:
    """O gesto que chegou da tela é um dos declarados?

    A ponte já recusa o que não é objeto JSON; o que falta é o nome. Despachar
    por nome vindo de fora sem esta peneira é o buraco que esta casa não abre.
    """
    return str(objeto.get("gesto", "")) in GESTOS
