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
        "controle.*.vibracao.sem-teto",
        "'Sem teto' é a única das TRÊS opções sem representação possível: "
        "`ControllerRumbleOverride` (`profiles/schema.py:887`) só diz QUAL "
        "política a peça usa, nunca 'esta peça ignora o teto do orçamento'; e o "
        "`min` que imporia um teto de verdade vive em "
        "`core.rumble._effective_mult`, que não conhece `uniq` e roda antes de a "
        "peça ser endereçada. Traduzi-la por 'balanceado' deixaria a peça mais "
        "FRACA que as outras sob um global 'max'; por 'max', mais FORTE que o "
        "global sob 'balanceado' — um campo chamado teto AUMENTANDO a força. "
        "A CONTA ESTÁ EM `politica_do_rotulo`, derivada do `RUMBLE_POLICY_MULT` "
        "e não digitada: ela estava escrita à mão aqui e em mais dois lugares, e "
        "os três diziam 0,667 com o degrau mordido para outra coisa. "
        "As outras duas ganharam fonte em 01/09/2026.",
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
    """``4 controles • 2 no cabo • 2 no rádio`` — o canto do quadro 1.

    A PALAVRA "mesa" SAIU EM 05/09/2026, ordem dela: *"não é pra ter mesa em
    nada da interface"*. O número já dizia o que ela precisava; a palavra só
    acrescentava um jargão desta casa à tela de quem joga.
    """
    radio = sum(1 for c in controles if c.pelo_radio)
    cabo = len(controles) - radio
    return f"{len(controles)} controles • {cabo} no cabo • {radio} no rádio"


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

#: A opção que NÃO grava nada. O merge do perfil é POR CAMPO
#: (`profiles/manager._controllers_to_rumble_scales:1864-1866` pula quem não tem
#: `policy` em `model_fields_set`), então "seguir o global" é a ausência da
#: chave — não um valor a escrever.
SEGUE_O_GLOBAL = "Segue o global"

#: A CLÁUSULA DE QUANDO A FORÇA NÃO É CALCULÁVEL, e ela nunca é "Sem teto".
#: Acontece em três casos, todos honestos: o serviço não publicou o
#: `rumble_policy`, ele está em `auto` (degrau que muda com a bateria a cada
#: tique), ou o `maquina.json` não deu para ler. Antes de 01/09/2026 os três
#: viravam a afirmação em negrito **"Sem teto"** — a ausência de notícia lida
#: como sucesso, no campo que ela clica.
NAO_SEI_A_FORCA = "e não dá para dizer quanta força chega ao motor agora"


def por_cento(fracao: float) -> str:
    """`0.3` → `"30% da força"`. A ÚNICA grafia desta frase nesta casa.

    Ela existia em QUATRO — `secao_orcamento.celula_do_teto:379`,
    `secao_orcamento._dica_da_bateria_longa:240`, `gui.aba_sistema
    .forca_do_perfil:417` e a que este arquivo digitou em 01/09/2026 —, e a
    quarta era a única que não passava pelo dono do NÚMERO. Aqui só a FORMA é
    própria; o número vem sempre de quem o calcula.
    """
    return f"{round(fracao * 100)}% da força"


def fala_do_teto(chave: str | None) -> str:
    """A frase de tela do teto que uma chave de ORÇAMENTO DA MESA impõe.

    **ELA RESPONDE PELO ORÇAMENTO, E NÃO PELO "GLOBAL"** — a distinção custou os
    quatro bloqueantes de 01/09/2026. O orçamento é o `maquina.json`, e o único
    valor dele que impõe teto é o `economia`; a política de vibração que o
    daemon está APLICANDO é outra coisa (`state['rumble_policy']`), e é ela que
    multiplica o que chega ao motor. Chamar esta função de "o global" fez o `?`
    da aba escrever *"o global vale Sem teto"* com o daemon cortando a 0,3.
    Quem quer saber o que o global entrega hoje chama
    :func:`~hefesto_dualsense4unix.core.rumble.forca_do_global`.

    O NÚMERO NÃO SE CALCULA AQUI — 01/09/2026, segunda correção. Esta função
    fazia `if chave != _ORCAMENTO_COM_TETO` e ia direto ao `RUMBLE_POLICY_MULT`,
    que é a QUARTA grafia de um desvio que `core.rumble.teto_do_orcamento` já é
    dono. Medido: com o dono mordido para 0,5, a aba Sistema dizia "50% da
    força" e esta dizia "30%" — duas abas do mesmo produto, dois números para o
    mesmo fato.

    O IMPORT É TARDIO pela mesma razão dos outros dois desta casa
    (:func:`_turnos` e o `ROTULO_SEM_FACE`): o topo deste arquivo é
    `import html` e mais nada de produto. **Ele não puxa mais GTK**: o
    `SEM_TETO` mudou-se para `core.rumble` justamente porque
    `app.actions.config.secao_orcamento` arrasta `gi.repository.Gtk` no import,
    e o docstring da linha 1 promete *"sem GTK"*.
    """
    from hefesto_dualsense4unix.core.rumble import SEM_TETO, teto_do_orcamento

    teto = teto_do_orcamento(chave)
    return str(SEM_TETO) if teto is None else por_cento(teto)


def opcoes_do_teto() -> tuple[str, str, str]:
    """As três opções do campo, NA ORDEM DA TELA — o desenho que ela aprovou.

    A ordem é a do mockup (`mockup/08-conexoes.html`), e ela não é alfabética:
    primeiro a que não grava nada, depois as duas que sobrepõem. Quem confere um
    clique confere contra esta lista, nunca contra três literais soltos — foi
    assim que o `mic-existe` se protegeu de um rótulo traduzido.
    """
    from hefesto_dualsense4unix.core.rumble import _ORCAMENTO_COM_TETO

    return (SEGUE_O_GLOBAL, fala_do_teto(""), fala_do_teto(_ORCAMENTO_COM_TETO))


#: ONDE O TETO GLOBAL SE MUDA — e não é nesta aba. Decisão dela, 28/08/2026:
#: *"Teto da Vibração, que na verdade é Perfil de Bateria"*. O dropdown dos três
#: perfis do produto (`app/actions/config/secao_orcamento.py`) mora na aba
#: **Sistema**; esta aba é LEITORA do global e sobrepõe-no por controle.
CASA_DO_TETO_GLOBAL = "Perfil de Bateria"
ABA_DO_TETO_GLOBAL = "Sistema"


def politica_do_rotulo(rotulo: str) -> str | None:
    """A ``policy`` de disco que uma opção do campo grava. ``None`` = não grava.

    DUAS DAS TRÊS TÊM TRADUÇÃO, e a terceira não tem — está em :data:`SEM_FONTE`,
    linha ``controle.*.vibracao.sem-teto``. Esta função **levanta** para ela em
    vez de escolher uma tradução: cada escolha possível faz o rótulo mentir num
    dos casos, e a frase que falta é dela.

    O 0,667 DA RECUSA É DERIVADO, e não digitado — corrigido em 01/09/2026. Ele
    estava escrito à mão em TRÊS lugares (aqui, no :data:`SEM_FONTE` acima e num
    ``assert`` da régua), e a régua guardava o número DIGITADO: com o degrau
    ``max`` mordido para 2,0 — quando a conta verdadeira vira 0,5 — os 18 casos
    ficavam verdes e a frase mentia na tela dela. É a mesma forma do defeito que
    :func:`fala_do_teto` cita como lição.

    :raises ValueError: para "Sem teto" e para qualquer coisa fora da lista.
    """
    from hefesto_dualsense4unix.core.rumble import _ORCAMENTO_COM_TETO
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    segue, sem_teto, economia = opcoes_do_teto()
    if rotulo == segue:
        return None
    if rotulo == economia:
        return str(_ORCAMENTO_COM_TETO)
    if rotulo == sem_teto:
        base, alto = RUMBLE_POLICY_MULT["balanceado"], RUMBLE_POLICY_MULT["max"]
        conta = f"{base:g}/{alto:g} = {base / alto:.3f}".replace(".", ",")
        raise ValueError(
            f"{sem_teto!r} é a única das três opções sem tradução para o "
            f"perfil. `ControllerRumbleOverride` só diz QUAL política esta peça "
            f"usa, nunca 'esta peça ignora o teto do orçamento': gravar "
            f"'balanceado' a deixaria mais FRACA que as outras quando o global "
            f"for 'max' ({conta}), e gravar 'max' a deixaria mais FORTE "
            f"que o global quando ele for 'balanceado' — um campo chamado teto "
            f"aumentando a força. A frase que falta é dela "
            f"(MIGRA-CONEXOES-11).")
    raise ValueError(f"{rotulo!r} não é resposta desta lista: {list(opcoes_do_teto())}")


def rotulo_da_politica(policy: str | None) -> str | None:
    """O que o CAMPO mostra para uma ``policy`` guardada. ``None`` = não sabe.

    ``None`` de entrada é "sem override" e vira :data:`SEGUE_O_GLOBAL`. ``None``
    de SAÍDA é outra coisa: o perfil guarda uma política que este campo não sabe
    mostrar, e quem chama tem de DECLARAR isso em vez de escolher uma das três.

    POR QUE NÃO SERVE A :func:`fala_do_teto` AQUI, e a diferença custou um
    defeito nesta mesma leva: ela responde pelo ORÇAMENTO DA MESA, onde só o
    `economia` impõe teto e todo o resto é "Sem teto". Aplicada a um override
    por controle, ela traduziria `balanceado` e `max` — os dois — como "Sem
    teto", que é justamente a opção sem tradução. Aqui a pergunta é outra: das
    quatro políticas que `ControllerRumbleOverride` aceita
    (`profiles/schema.py:887`), **uma só** tem opção no campo.
    """
    from hefesto_dualsense4unix.core.rumble import _ORCAMENTO_COM_TETO

    if not policy:
        return SEGUE_O_GLOBAL
    if policy == _ORCAMENTO_COM_TETO:
        return fala_do_teto(_ORCAMENTO_COM_TETO)
    return None


@dataclass(frozen=True)
class Vibracao:
    """AS QUATRO COISAS QUE DECIDEM A FORÇA NO MOTOR DE UM CONTROLE.

    TRÊS DELAS SE CHAMAVAM "O GLOBAL" ATÉ 01/09/2026, e a tela reportava a
    errada — foi o defeito que segurou esta leva. A conta inteira, do disco ao
    motor, é::

        no motor = forca_do_global(a_viva, orcamento) * MULT[do_controle]/MULT[do_perfil]
                   └────── core.rumble ───────┘   └── profiles.manager.fator_da_unidade ──┘

    :param do_controle: ``controllers[uniq].rumble.policy`` do perfil — o
        override desta peça, ``None`` quando ela não sobrepõe nada.
    :param do_perfil: ``Profile.rumble.policy`` — **o DENOMINADOR**. O fator por
        peça é RELATIVO a ele (`profiles/manager.py:1857`), e não à política que
        multiplica. Sem opinião, o produto assume ``balanceado``.
    :param a_viva: ``state['rumble_policy']`` — **o que MULTIPLICA**, e é o único
        "global" que o motor sente (`daemon/ipc_handlers.py:2923` publica o
        ``DaemonConfig.rumble_policy`` que `core.rumble._effective_mult` lê).
        ``None`` = o serviço não disse, e aí a tela não afirma número nenhum.
    :param orcamento: a chave do ``maquina.json`` — o teto por CIMA da viva,
        aplicado com ``min``. ``None`` = ninguém declarou, que não impõe teto.
    :param a_mesa_respondeu: ``False`` quando não deu para LER o ``maquina.json``.
        Sem isto, "não consegui ler" e "ninguém declarou" viravam o mesmo
        ``None``, e a tela publicava a ausência de notícia como uma afirmação —
        exatamente o que o dono da fonte proíbe (`secao_orcamento
        .orcamento_em_vigor`: *"None aqui significa 'não sei', nunca 'sem teto'"*).

    OS CAMPOS SÃO NOMEADOS E A CLASSE É CONGELADA de propósito: os quatro são
    ``str | None`` e uma troca de posição entre ``do_perfil`` e ``a_viva`` é
    silenciosa, verde em toda régua e errada no motor. Foi como o defeito
    nasceu.
    """

    do_controle: str | None = None
    do_perfil: str | None = None
    a_viva: str | None = None
    orcamento: str | None = None
    a_mesa_respondeu: bool = True


def forca_no_motor(v: Vibracao) -> float | None:
    """A fração do que o JOGO pediu que chega ao motor DESTE controle.

    ``None`` = não dá para afirmar, e a tela tem de dizer isso em vez de
    escolher um número plausível.

    **NENHUMA ARITMÉTICA NASCE AQUI.** Os dois fatores vêm dos donos que o
    produto já usa — `core.rumble.forca_do_global` (o mesmo corpo que
    `_effective_mult` roda no funil) e `profiles.manager.fator_da_unidade` (o
    mesmo que `_controllers_to_rumble_scales` publica no backend). É o que faz a
    régua da tela poder ser a régua do motor: morda um dos dois e as duas
    reprovam juntas.
    """
    from hefesto_dualsense4unix.core.rumble import forca_do_global
    from hefesto_dualsense4unix.profiles.manager import fator_da_unidade

    if not v.a_mesa_respondeu:
        return None
    global_ = forca_do_global(v.a_viva, v.orcamento)
    if global_ is None:
        return None
    if not v.do_controle:
        return global_
    fator = fator_da_unidade(v.do_controle, v.do_perfil)
    return None if fator is None else global_ * fator


def teto_que_vale(v: Vibracao) -> tuple[str | None, str]:
    """``(o que o CAMPO mostra, a frase de quem manda neste controle)``.

    O QUE ELA DIZ É O QUE CHEGA AO MOTOR, e não o degrau nominal do rótulo —
    corrigido em 01/09/2026, e é a diferença inteira. Com um override
    ``economia`` (rótulo "30% da força"), o motor recebe **9%** se a política
    viva for ``economia`` e **45%** se for ``max``: o fator da peça é RELATIVO
    ao global do perfil e o global VIVO multiplica por cima. Medido, com a
    cadeia inteira até ``_escalar_rumble``. A frase que dizia só o rótulo era um
    campo chamado teto entregando acima do teto que promete.

    O PRIMEIRO ITEM É ``None`` quando o campo não sabe mostrar a política
    guardada. Quem pinta NÃO escreve nada no ``<select>`` nesse caso, e a razão
    é medida: escrever num ``<select>`` um valor que não é opção nenhuma deixa
    ``selectedIndex = -1``, e o ``escrever()`` do piloto contaria uma pintura
    NOVA a cada tique para sempre — um contador que mente é pior que um campo
    parado. A frase do ``?``, essa, diz o que há.

    UMA FRASE POR CASO, não três pedaços costurados. Costurada, o texto saía
    *"vale Sem teto, do global, na aba Sistema. O global hoje é Sem teto…"* —
    "Sem teto" duas vezes na mesma dica.
    """
    no_motor = forca_no_motor(v)
    entrega = (NAO_SEI_A_FORCA if no_motor is None
               else f"e o motor recebe <b>{por_cento(no_motor)}</b>")
    if not v.do_controle:
        return SEGUE_O_GLOBAL, f"este controle <b>segue o global</b>, {entrega}"
    meu = rotulo_da_politica(v.do_controle)
    if meu is None:
        return None, (
            f"o perfil guarda <code>{_e(v.do_controle)}</code> para este "
            f"controle, e este campo não sabe mostrar essa política — o perfil "
            f"manda, a caixa fica como está, {entrega}")
    # O DEGRAU DA CAIXA SÓ APARECE QUANDO DIVERGE do que chega ao motor, e é aí
    # que ele precisa ser explicado: repeti-lo quando os dois coincidem seria
    # "30% da força" duas vezes na mesma frase, que é o defeito de costura que
    # esta função já tinha corrigido uma vez.
    if no_motor is not None and meu == por_cento(no_motor):
        return meu, f"este controle <b>sobrepõe</b> o global, {entrega}"
    return meu, (f"este controle <b>sobrepõe</b> o global com <b>{meu}</b>, que é "
                 f"RELATIVO ao global — hoje {entrega.removeprefix('e ')}")


def dica_do_teto(v: Vibracao) -> str:
    """A frase inteira do ``?`` do campo, com marcação — dono único das duas telas.

    Ela nasceu no gerador do mockup (`interface/aba08.teto_dica`) e mudou-se
    para cá em 01/09/2026, quando o `?` ganhou endereço de pintura
    (``data-campo="teto-explica"``). Enquanto a frase vivesse só lá, o pacote
    da interface nova teria de escrevê-la de novo — e a segunda grafia é a que
    fica para trás no dia em que a primeira mudar.

    TRAZ `<b>` E `<code>`, de propósito: quem a pinta usa o alvo ``html`` do
    `hefesto_vivo.BOOTSTRAP`, e não o ``texto`` padrão.
    """
    return (f"O teto da vibração <b>deste controle</b>. O global manda e o do controle "
            f"sobrepõe: hoje {teto_que_vale(v)[1]}. Quem muda o global é o "
            f"<b>{CASA_DO_TETO_GLOBAL}</b>, na aba <b>{ABA_DO_TETO_GLOBAL}</b> — ele decide "
            f"o que custa bateria, e esta aba mede o rádio. O degrau vem de "
            f"<code>RUMBLE_POLICY_MULT</code>, que é o dono dele — a vibração é o único "
            f"recurso com teto real hoje.")


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
    # A PRIMEIRA É A ESCOLHIDA porque é a que não grava nada: sem override no
    # perfil, este controle segue o global. Quem pinta o estado de disco por
    # cima é o pacote da interface nova (`a08_conexoes.pacote`); esta janela
    # ainda não lê o perfil aqui, e mostrar o padrão é o honesto até que leia.
    opcoes_teto = "".join(
        f'<option{" selected" if i == 0 else ""}>{_e(o)}</option>'
        for i, o in enumerate(opcoes_do_teto())
    )
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
        f'data-alvo="{_e(c.uniq)}">{opcoes_teto}</select></span>'
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
    "atencao": ("warn", "AJUSTAR"),  # (noqa-acento): chave de máquina, ASCII por contrato
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

    A chave dos dois ``data-v`` é ENDEREÇO DE DADO, não texto de tela: ela vai
    crua para o atributo e o JS a compara byte a byte. Acentuá-la trocaria o
    endereço — daí o ``noqa-acento`` nas duas linhas.
    """
    if ordem is None:
        return (
            f'<div class="ordem">'
            f'<div class="faca" data-v="{v("ordem", "acao")}">'  # (noqa-acento): endereço
            f"Nenhuma mudança recomendada agora.</div></div>"
        )
    return (
        f'<div class="ordem">'
        f'<div class="faca" data-v="{v("ordem", "acao")}">'  # (noqa-acento): endereço
        f"{_e(ordem.acao)}</div>"
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


# ---------------------------------------------------------------------------
# O MAPA DO GABINETE — o desenho ÚNICO, 01/09/2026
# ---------------------------------------------------------------------------
# POR QUE ELE MUDOU DE CASA: o desenho das faces e dos quadrados vivia no
# GERADOR (`interface/aba08.py`), e junto com ele vivia uma SEGUNDA CÓPIA do
# motor — uma função `veredito()` que reescrevia à mão o
# `arranjo_da_mesa.julgar`, com os mesmos cinco vereditos ("ocupada", "vale
# evitar", "melhor lugar"…) digitados como constantes.
#
# O PREÇO DISSO ERA DUPLO, e os dois lados foram medidos em 01/09/2026:
#
#   1. O JUÍZO DA TELA NÃO ERA O DO PRODUTO. A cópia julgava por uma tabela de
#      vizinhos do mockup; o motor julga pela mesa real, sabe de entrada azul,
#      de folga na fileira e de extensor, e ainda CONFESSA o que não sabe
#      (`confissao_do_desenho`). A tela mostrava menos e podia mostrar diferente.
#   2. O GABINETE DESENHADO NÃO ERA O DELA. `FACES`, `QUEM_ESTA` e `EXTENSAO`
#      eram constantes de bancada — duas faces e dez entradas de exemplo —, e o
#      `maquina.json` dela **não existe**: o mapa declarado está vazio. A aba
#      mostrava um gabinete que não é o dela, e por isso os seis botões que
#      mexem no mapa não podiam ser ligados: clicar declararia no disco DELA o
#      desenho de uma bancada de exemplo.
#
# AQUI O DESENHO É UM SÓ e recebe DADO: o gerador o chama com a cena do mockup,
# o piloto com o que ela declarou. É a mesma disciplina dos outros `html_*`
# deste módulo — função pura sobre dado já lido, sem GTK, sem `/sys`, sem IPC.


#: AS DUAS DICAS DOS BOTÕES DO MAPA. Elas são da tela WEB — a janela GTK põe os
#: mesmos gestos em botões sem tooltip —, e por isso moram aqui, no lado Python
#: dela, e não em `mapa_da_mesa.py`. O gerador do mockup e o piloto leem daqui:
#: eram duas grafias até 01/09/2026.
DICA_NOVA_ENTRADA = (
    "Acrescenta a esta face o menor número que ainda não existe em face "
    "nenhuma — os números são do GABINETE, e dois buracos diferentes não podem "
    "levar o mesmo."
)
#: A PALAVRA "mesa" SAIU DA TELA em 05/09/2026, ordem dela. Aqui ela dizia ONDE
#: o hub entra, e o lugar certo não é o móvel: é o MAPA — o que este botão
#: acrescenta é uma linha no desenho, não um objeto na sala.
DICA_NOVO_HUB = (
    "Acrescenta um hub ou uma extensão ao mapa e pergunta em que entrada ele "
    "está ligado. Cabo passivo não tem descritor USB: nenhuma leitura do "
    "sistema o enxerga, e por isso quem o declara é você."
)


def html_do_mapa(
    faces: Sequence[Mapping[str, Any]],
    *,
    quem_esta: Mapping[str, tuple[str, str]],
    extensoes: Mapping[str, str],
    veredito_de: Any,
    rotulos: Mapping[str, str],
    dicas: Mapping[str, str],
) -> str:
    """As faces do gabinete, com um quadrado por entrada.

    `faces` é `[{"nome": …, "portas": [numero, …]}, …]` — a forma do
    `MapaDaMesa`, para que o chamador não precise traduzir nada.

    `quem_esta` é `numero -> (espécie, nome do kernel)`. A espécie é o que o
    quadrado mostra; o nome do kernel é o que a dica diz, porque é ele que
    distingue dois aparelhos iguais.

    `veredito_de(numero, esticada)` devolve `(classe, texto, porque)`. Ele é
    INJETADO e não importado: o motor de verdade (`arranjo_da_mesa.julgar`,
    pelo `mapa_da_mesa.veredito_do_quadrado`) precisa de uma `Bancada`, que
    precisa do censo do barramento — e este módulo não lê `/sys` por decisão,
    escrita no cabeçalho dele. Quem lê é quem chama.

    O `data-v` E O `data-gesto` CONVIVEM no quadrado, e não se trocam: a CSS
    pinta por `data-v` (`.mm-sq[data-v="cheia"]`) e o piloto ouve o
    `data-gesto`. Trocar um pelo outro apagaria a cor.
    """
    def quadrado(numero: str, esticada: bool = False) -> str:
        classe, texto, porque = veredito_de(numero, esticada)
        dentro = quem_esta.get(numero)
        corpo = dentro[0] if dentro else rotulos["vazia"]
        dizeres = []
        if esticada:
            dizeres.append(dicas["esticada"])
        elif dentro:
            dizeres.append(dicas["enumera"].format(c=dentro[1]))
        dizeres.append(porque)
        linhas = [f'<span class="mm-n">{_e(numero)}</span>',
                  f'<span class="mm-c{"" if dentro else " mm-vazia"}">{_e(corpo)}</span>']
        if esticada:
            linhas.append(f'<span class="mm-ext">{_e(rotulos["por_extensao"])}</span>')
        linhas.append(f'<span class="mm-v">{_e(texto)}</span>')
        return (f'<button class="mm-sq" data-v="{_e(classe)}" '
                f'data-gesto="escolher-entrada" data-entrada="{_e(numero)}" '
                f'title="{_e(" ".join(dizeres))}">' + "".join(linhas) + "</button>")

    #: DE QUAL FACE É CADA ENTRADA — para o hub poder dizer onde está ligado.
    #: Sai das próprias faces, nunca digitado.
    face_da_entrada = {n: str(f.get("nome", "")) for f in faces for n in f.get("portas", [])}

    if not faces:
        # O ESTADO VAZIO TEM FRASE, e ela é do produto: `ROTULO_SEM_FACE`. Sem
        # ela o mapa de quem nunca desenhou o gabinete seria uma caixa em
        # branco — e "não há nada aqui" é indistinguível de "isto quebrou".
        from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import ROTULO_SEM_FACE

        return f'            <div class="tn-frase">{_e(ROTULO_SEM_FACE)}</div>'

    blocos = []
    for indice, face in enumerate(faces):
        grade = "".join(f'<div class="mm-cel">{quadrado(str(n))}</div>'
                        for n in face.get("portas", []))
        blocos.append(
            f'''            <div class="mm-face" data-face="{indice}">
              <div class="mm-face-cab"><span class="mm-face-nome">{_e(face.get("nome", ""))}</span>
                <button class="btn mini" data-gesto="nova-entrada" data-face="{indice}" '''
            f'''title="{_e(dicas["nova_entrada"])}">{_e(rotulos["nova_entrada"])}</button></div>
              <div class="mm-grade">{grade}</div>
            </div>''')

    if extensoes:
        celulas = "".join(
            f'<div class="mm-cel">{quadrado(filha, esticada=True)}'
            f'<span class="mm-ligado">ligado na entrada <b>{_e(mae)}</b>'
            f' <span class="mudo">· {_e(face_da_entrada.get(mae, ""))}</span></span></div>'
            for mae, filha in extensoes.items())
        blocos.append(
            f'''            <div class="mm-face" data-face="hubs">
              <div class="mm-face-cab"><span class="mm-face-nome">Hubs e extensões</span>
                <button class="btn mini" data-gesto="novo-hub" '''
            f'''title="{_e(dicas["novo_hub"])}">Acrescentar hub</button></div>
              <div class="mm-grade mm-grade-hubs">{celulas}</div>
            </div>''')
    return "\n".join(blocos)
