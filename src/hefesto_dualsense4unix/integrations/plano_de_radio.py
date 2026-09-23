"""plano_de_radio.py — a conta de fatias POR ADAPTADOR, com nome de jogador.

O QUE ESTE MÓDULO ACRESCENTA AO ``radio_da_mesa``
------------------------------------------------

``radio_da_mesa`` responde *"quanto do rádio deste adaptador já foi
comprometido"*. Ele é o dono das constantes, da :class:`Ocupacao` e das três
palavras. **Nada disso se recalcula aqui**, e é regra: dois donos do mesmo
número divergem na primeira remedição.

O que faltava, e é o que decide o produto, são três perguntas que a
:class:`Ocupacao` sozinha não responde:

1. **quem** está naquele adaptador — o número do jogador, para a tela poder
   dizer "Jogadores 1 e 2" em vez de "2 controles";
2. **cabe mais um?** — a pergunta do planejamento, que a barra de ocupação de
   hoje não responde porque ela só sabe falar do agora;
3. **se não cabe, para onde vai?** — a ordem de redistribuição, como DADO PURO.
   Quem a desenha é a seção Conexões; o contrato entre as duas é a
   :class:`Redistribuicao`, e trocar o renderizador não muda uma linha do dado.

AS TRÊS REGRAS DE HONESTIDADE QUE ESTE MÓDULO CARREGA
-----------------------------------------------------

**1. ``agora`` e ``planejada`` são DUAS contas, não uma.** ``agora`` é
alimentada por ``bt_mic.uniqs`` — os ``uniq`` cuja ponte de microfone
**subiu** —, e ``planejada`` pelo que ela DECLAROU no ``maquina.json``. Quando
as duas divergem, a tela diz as duas. Alimentar as duas com a declaração seria
o produto respondendo pelo pedido em vez de pelo efeito, que é o padrão que a
queixa do Sackboy revelou (22/08/2026).

**2. Nenhuma palavra de culpa.** A desigualdade de quase o dobro entre dois
controles do MESMO adaptador continua ABERTA (``radio_da_mesa.py:49-55``), e
ocupação não é qualidade. :data:`radio_da_mesa.PALAVRAS_DE_CULPA` é varrida
contra tudo que este módulo produz.

**3. Nenhum número é digitado.** Toda frase deste módulo deriva das constantes
do ``radio_da_mesa``. Um número digitado sobrevive à remedição que o derrubou,
e aí a tela passa a afirmar o que a bancada já negou.

O SELO TEM TRÊS PARTES, E A TERCEIRA CONFESSA
----------------------------------------------

O selo de hoje na seção Conexões é uma frase só — ``derivado da
especificação`` — e ela defende as 1600 fatias enquanto cala sobre o resto.
Aqui ele tem três partes, que é a coluna ``de_onde_sei`` do mapa de canais
chegando à tela:

* as **1600 fatias por segundo**: especificação de terceiro (Bluetooth
  Classic, 625 µs por fatia) — nunca medidas nesta máquina;
* os **260,4 sem microfone / 276,7 com**: medido aqui, A/B de 25/07/2026, e é
  medição de **UM** controle;
* a **soma de N controles**: derivado da conta, e **nunca medido**. O maior
  ensaio desta casa no rádio foi de DOIS controles, e ele não mediu isto
  (``D-CONTA-ADITIVA-DO-RADIO``, aberta).

Isso não é modéstia. O cabeçalho de ``radio_da_mesa.py:76-81`` registra que a
medição de 23/08/2026 releu o denominador: *"~800 relatórios/s é orçamento do
ADAPTADOR, repartido entre os controles que ele hospeda — não uma taxa por
controle."* Se aquela leitura estiver certa, o modelo aditivo **superestima** a
ocupação. Superestimar é o lado seguro — a barra fica laranja antes da hora,
nunca depois —, mas divergência conhecida e sem selo vira medição aos olhos de
quem lê.

ONDE MORA O PADRÃO DE NASCIMENTO DO MICROFONE
----------------------------------------------

:func:`microfone_nasce_ligado` **não decide nada**: ela LÊ o dono único do
padrão, que é o campo ``ControleDeclarado.microfone`` do esquema
(``utils/maquina.py``). Hoje ele nasce ``None`` — "ninguém declarou", que
deixa a ponte no chão.

A ``D-O-MIC-LIGADO-VALE-NO-RADIO`` (aberta em 25/08/2026) é a decisão DELA
sobre se esse padrão muda no rádio, e ela contradiz a ``D-PERFIL-DE-DESEMPENHO``
de 24/08. Este módulo **não a resolve**: ele mostra o preço dos dois lados
(:func:`frase_do_preco_por_controle`) para que a conta esteja na mesa quando
ela escolher. Quando a escolha vier, quem muda é o ``default`` daquele campo —
e a frase desta tela acompanha sozinha, porque deriva dele.

O «EQUILIBRAR» PESA PONTES, DESDE 23/09/2026 — MOVER-UM-POR-VEZ-01
------------------------------------------------------------------

A R12 dela manda o «Equilibrar» continuar nesta régua (:func:`ordem_de_redistribuicao`,
dona desde 20/09), e a medição de 23/09 trocou o que ela pesa. A entrada do
controle é ELÁSTICA (~750 relatórios/s sozinho, ~400 dividindo): somá-la como
demanda fixa contra 1.600 era o erro. O que transborda um adaptador são as
PONTES de som e de vibração, de ritmo fixo — e o limite é
``radio_da_mesa.N_MAX_PONTES`` (dois, medido em 22/09: a terceira derrubou em
11, 15 e 89 s). Então a régua passou a ler o ``OrcamentoDoAdaptador`` do dono
(``radio_da_mesa.orcamento_por_adaptador``) e a palavra de
``palavra_das_pontes``: nasce ordem quando um adaptador passa de ``n_max``
pontes, e o destino é o da D8 (:func:`ordem_dos_destinos`).

A vista aditiva (``agora``, ``planejada``, :func:`cabe_mais_um`, as linhas e o
selo) FICA, e não é descuido: ela tem dois leitores de tela — a seção
Desempenho (``secao_orcamento``) e a seção de rádio de hoje da aba 08 — e sai
com eles, na TRANSPLANTE-DA-SECAO-01. Ela não decide mais movimento nenhum.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from hefesto_dualsense4unix.app.fala_do_mapa import formata_pt_br
from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.integrations.conexao_zumbi import mac_limpo
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    HZ_AUDIO_COM_MIC,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
    N_MAX_PONTES,
    SEM_ADAPTADOR,
    SLOTS_POR_RELATORIO,
    SLOTS_POR_SEGUNDO,
    Ocupacao,
    OrcamentoDoAdaptador,
    adaptador_por_uniq,
    orcamento_por_adaptador,
    palavra_da_ocupacao,
    palavra_das_pontes,
)

#: O maior ensaio desta casa no rádio, em número de controles simultâneos
#: (15/08/2026, ``docs/data/ensaios-brutos/2026-08-15-E2-taxa-dos-oito-nos.csv``).
#: Daqui para cima a conta é EXTRAPOLAÇÃO, e o selo diz isso. Não é palpite:
#: é o número de linhas do maior ensaio que existe.
ENSAIO_MAXIMO_DESTA_CASA = 2

#: A mesa cheia desta casa — o co-op de quatro que o produto existe para
#: servir. É o cenário da frase de capacidade do microfone, e o único número
#: deste módulo que não sai de uma medição: sai do produto.
MESA_CHEIA_DESTA_CASA = 4

#: O que a tela diz de um controle sem número de jogador. É a MESMA frase de
#: ``secao_controles.TITULO_SEM_NUMERO`` — repetida aqui, e não importada,
#: porque ``secao_controles`` **importa GTK**: puxá-lo daqui traria a biblioteca
#: de janelas para dentro de ``integrations/``. Se as duas divergirem, o teste
#: ``test_o_sem_numero_e_a_mesma_frase_do_card`` reprova.
#:
#: (26/08/2026: esta razão era escrita como *"para que `integrations/` não passe
#: a depender de `app/`"*, e o ``_numero`` logo abaixo passou a importar
#: ``app/fala_do_mapa.py``. Não é contradição — é a razão dita com precisão:
#: ``fala_do_mapa`` é zero-dependência por contrato, só stdlib, e
#: ``secao_controles`` não é.)
SEM_NUMERO = "Sem número ainda"

#: O que a tela diz de um adaptador que o produto não soube nomear. ``hciN``
#: NUNCA aparece: o índice é a VAGA, não o aparelho, e ele inverte entre boots
#: (medido em 24/08/2026 — o serial que a ``D-HCI1-BLOQUEADO`` chamava de
#: ``hci1`` é o ``hci0`` de hoje).
ADAPTADOR_SEM_NOME = "Adaptador sem nome"

#: O balde de quem o produto não conseguiu amarrar a adaptador nenhum.
ADAPTADOR_DESCONHECIDO = "Adaptador que não sei qual é"


@dataclass(frozen=True)
class PlanoDoAdaptador:
    """O que está num adaptador, o que custa agora, e o que custaria declarado.

    ``endereco`` é o BD Address minúsculo do adaptador como o ``HID_PHYS`` do
    uevent o publica, ou :data:`radio_da_mesa.SEM_ADAPTADOR` (string vazia)
    para o balde do "não sei de quem é".

    ``jogadores`` traz o ``player_slot`` de cada controle NA ORDEM em que
    chegaram, com ``None`` para quem ainda não tem número — nunca chutado por
    posição. A conta ``índice + 1`` já deu "Jogador 4" a dois cards da mesma
    mesa (22/08/2026), e null honesto vale mais que número errado.
    """

    endereco: str
    apelido: str = ""
    jogadores: tuple[int | None, ...] = ()
    com_mic_de_pe: frozenset[str] = field(default_factory=frozenset)
    com_mic_declarado: frozenset[str] = field(default_factory=frozenset)
    agora: Ocupacao = field(default_factory=Ocupacao)
    planejada: Ocupacao = field(default_factory=Ocupacao)
    #: O ar deste adaptador pelo DONO (``radio_da_mesa.orcamento_por_adaptador``):
    #: quem está nele, quais pontes estão de pé e o ``n_max``. É o que o
    #: «Equilibrar» pesa desde 23/09 (MOVER-UM-POR-VEZ-01). ``None`` só em plano
    #: montado à mão; :func:`plano_por_adaptador` sempre o preenche.
    orcamento: OrcamentoDoAdaptador | None = None

    @property
    def pontes(self) -> int:
        """Quantas pontes de som e vibração estão de pé neste adaptador."""
        return len(self.orcamento.pontes) if self.orcamento is not None else 0

    @property
    def n_max(self) -> int:
        """Quantas pontes o adaptador comporta — o do dono, nunca um digitado."""
        return self.orcamento.n_max if self.orcamento is not None else N_MAX_PONTES

    @property
    def vaga_de_ponte(self) -> int:
        """Quantas pontes ainda cabem aqui. Negativo quando já passou do limite."""
        return self.n_max - self.pontes

    @property
    def no_ar(self) -> int:
        """Quantos controles estão no rádio deste adaptador."""
        if self.orcamento is not None:
            return len(self.orcamento.controles)
        return self.agora.controles

    @property
    def rotulo_das_pontes(self) -> str:
        """Folgada, Apertada ou Cheia — pelas pontes, pela palavra do dono."""
        return palavra_das_pontes(self.pontes, self.n_max)

    @property
    def nome_na_tela(self) -> str:
        """O nome DELA, nunca ``hciN`` — ver :data:`ADAPTADOR_SEM_NOME`."""
        if self.apelido:
            return self.apelido
        if not self.endereco:
            return ADAPTADOR_DESCONHECIDO
        return ADAPTADOR_SEM_NOME

    @property
    def declarado_que_nao_subiu(self) -> frozenset[str]:
        """Os ``uniq`` que ela marcou e cuja ponte não está de pé.

        Ausência de notícia lida como notícia de sucesso é o padrão que a
        queixa do Sackboy revelou: sem esta lista, a tela mostraria "está tudo
        certo" sobre uma ponte no chão.
        """
        return frozenset(self.com_mic_declarado - self.com_mic_de_pe)


@dataclass(frozen=True)
class Redistribuicao:
    """A ordem de serviço, como DADO PURO — sem uma linha de ``gi``.

    Quem desenha a caixinha é a seção Conexões (Frente B); enquanto o desenho
    dela não existir, a seção Desempenho renderiza as três linhas com
    ``rotulo_de_apoio``. A troca do renderizador não muda nada aqui.

    **UM movimento, e ela diz QUAL controle** (R12, 23/09/2026): ``controle`` é
    o ``uniq`` (12 hex) do que carrega a ponte, e ``modo`` é a ponte dele
    (``som``/``haptica``). A central move exatamente esse, com o PS + Create
    dela, e só depois do «chegou» a régua propõe o próximo.

    FATO SUBSTITUÍDO (23/09): aqui moravam ``origem_depois``/``destino_depois``
    como :class:`Ocupacao` e ``move_com_microfone`` — a conta aditiva, que o
    estudo de 23/09 mediu como errada para o ar. Agora a ordem diz as PONTES
    antes e depois, contra ``n_max``.
    """

    origem: str
    destino: str
    origem_na_tela: str
    destino_na_tela: str
    o_que_eu_vi: str
    por_que_importa: str
    ganho_esperado: str
    controle: str
    modo: str
    pontes_na_origem_depois: int
    pontes_no_destino_depois: int
    n_max: int

    def publicar(self) -> dict[str, Any]:
        """O que viaja no ``state_full`` — só tipos de JSON."""
        return {
            "origem": self.origem,
            "destino": self.destino,
            "controle": self.controle,
            "modo": self.modo,
            "pontes_na_origem_depois": self.pontes_na_origem_depois,
            "pontes_no_destino_depois": self.pontes_no_destino_depois,
            "n_max": self.n_max,
        }


#: O que a tela diz quando o adaptador está apertado e NÃO há para onde mover.
#: Mandar mover para lugar nenhum seria pior que calar.
FRASE_DO_ADAPTADOR_UNICO = (
    "Todos os controles estão no mesmo adaptador, e é o único que você tem. "
    "Um segundo adaptador dividiria a fila."
)

#: A parte do "por que importa" da ordem de serviço. É MEDIÇÃO (22/09/2026: a
#: terceira ponte num adaptador derrubou em 11, 15 e 89 s), e a frase não afirma
#: nada sobre a qualidade de controle nenhum.
#:
#: FATO SUBSTITUÍDO (23/09): dizia *"o rádio de um adaptador é uma fila só.
#: Passando do teto, os relatórios do controle atrasam"* — o teto aditivo, que o
#: estudo de 23/09 derrubou: a entrada ocupa o ar que sobra, e quem transborda
#: são as pontes.
POR_QUE_IMPORTA = (
    "cada ponte de som ou vibração ocupa o rádio sem parar, e acima do limite "
    "o adaptador não comporta todas."
)


def _numero(valor: float) -> str:
    """Uma casa decimal, com vírgula — é assim que ela lê número nesta casa.

    Delega ao DONO ÚNICO (``app/fala_do_mapa.formata_pt_br``) desde 26/08/2026.

    **FATO ERRADO, SUBSTITUÍDO:** estas linhas diziam *"repetida aqui, e não
    importada, porque `integrations/` não pode passar a depender de `app/`"* — e
    mesmo assim prometiam, no comentário, a *"mesma forma"* que as outras duas.
    Comentário não é régua: era a terceira implementação independente da mesma
    conta, e as três divergiriam na primeira mudança de arredondamento.

    **O preço da importação, medido em 26/08/2026, e por que ele é zero aqui:**
    ``app/fala_do_mapa.py`` é zero-dependência de propósito — só stdlib, sem
    GTK, sem nada do pacote (o ``scripts/validar-fala-de-tela.py`` depende
    disso: ele carrega o arquivo por CAMINHO, sem passar pelo ``__init__``
    de ``app/``, exatamente para não transformar ``ImportError`` em "zero
    ``Fala`` encontradas"). E este módulo já é consumido só pela tela: o único
    importador dele em ``src/`` é
    ``app/actions/config/secao_orcamento.py``. Nada headless ganha dependência
    de ``app/`` por causa desta linha, e não há ciclo — ``fala_do_mapa`` não
    importa nada do projeto.
    """
    return formata_pt_br(valor)


def _hex(valor: str) -> str:
    """Só os dígitos hex minúsculos — o mesmo normalizador do ``radio_da_mesa``."""
    return norm_mac(valor) or ""


def _somar(
    base: Ocupacao, *, com_mic: bool = False, quantos: int = 1
) -> Ocupacao:
    """``base`` mais ``quantos`` controles — a ÚNICA aritmética deste módulo.

    Nenhuma constante nova e nenhum corte novo: as parcelas são as do
    ``radio_da_mesa``, e a palavra continua saindo de
    :func:`radio_da_mesa.palavra_da_ocupacao` pela propriedade ``rotulo``.

    Um só lugar somando é o que impede que :func:`plano_por_adaptador` e
    :func:`cabe_mais_um` respondam números diferentes sobre o mesmo controle.
    """
    if quantos <= 0:
        return base
    if com_mic:
        entrada = HZ_INPUT_COM_MIC * SLOTS_POR_RELATORIO * quantos
        audio = HZ_AUDIO_COM_MIC * SLOTS_POR_RELATORIO * quantos
    else:
        entrada = HZ_INPUT_SEM_MIC * SLOTS_POR_RELATORIO * quantos
        audio = 0.0
    return Ocupacao(
        slots_input=base.slots_input + entrada,
        slots_audio=base.slots_audio + audio,
        slots_teto=base.slots_teto,
        controles=base.controles + quantos,
        com_microfone=base.com_microfone + (quantos if com_mic else 0),
    )


def apelido_por_endereco(dongles: Sequence[Any]) -> dict[str, str]:
    """``endereço minúsculo -> nome DELA``, só para quem tem nome.

    A junção nome↔endereço já existia dentro da seção Conexões
    (``secao_mesa._apelido_por_endereco``), e por isso ela mora AQUI a partir
    de agora: duas junções para o mesmo fato divergiriam na primeira vez que
    uma delas aprendesse um caso novo. A seção Conexões passa a importar
    daqui — a costura dessa ponta está declarada na entrega desta frente.

    A chave sai MINÚSCULA porque é assim que o ``HID_PHYS`` do uevent chega
    (``radio_da_mesa.adaptador_por_uniq`` já faz ``.lower()``), e comparar
    ``AA:BB`` com ``aa:bb`` não casa nunca.
    """
    achados: dict[str, str] = {}
    for dongle in dongles:
        endereco = str(getattr(dongle, "endereco", "") or "").lower()
        nome = str(getattr(dongle, "nome", "") or "")
        if endereco and nome:
            achados[endereco] = nome
    return achados


def plano_por_adaptador(
    controles: Iterable[Mapping[str, Any]],
    *,
    com_ponte_de_mic: Iterable[str] = (),
    mic_declarado: Iterable[str] = (),
    apelidos: Mapping[str, str] | None = None,
    ar: Mapping[str, Any] | None = None,
    n_max: int = N_MAX_PONTES,
    adaptadores: Iterable[str] = (),
    raiz: str = "/sys/class/hidraw",
    listar: Callable[[str], list[str]] = os.listdir,
    ler: Callable[[str], str] | None = None,
) -> dict[str, PlanoDoAdaptador]:
    """``{endereço: PlanoDoAdaptador}`` a partir do estado do daemon.

    ``controles`` é ``state["controllers"]`` como já chega. ``com_ponte_de_mic``
    é ``bt_mic.uniqs`` — a ponte que SUBIU; ``mic_declarado`` são as chaves de
    ``maquina.json`` que ELA marcou. As duas alimentam contas diferentes, e é
    a regra 1 do cabeçalho.

    As três regras de descarte são as mesmas de
    ``radio_da_mesa.ocupacao_por_adaptador``, e por isso não se reescrevem: quem
    não está em ``bt`` não toca o rádio, quem não tem endereço legível vai para
    o balde do "não sei", e a fração passa de 1,0 quando passa.

    DESDE 23/09/2026 (MOVER-UM-POR-VEZ-01) cada plano leva o
    ``OrcamentoDoAdaptador`` do dono — ``ar`` e ``n_max`` vão direto para
    ``radio_da_mesa.orcamento_por_adaptador``. E o adaptador VAZIO passa a
    existir: todo endereço que o ``ar`` mede ou que vem em ``adaptadores`` (o
    que o BlueZ conhece) ganha plano, com zero controles. Era o ACHADO 2 da
    medição das duas réguas (``test_as_duas_reguas_do_arranjo_divergem_onde``):
    o dongle livre não existia para a régua, e ela mandava a frase do adaptador
    único com um adaptador vazio na mesa.

    O ``adaptador`` que o daemon já publica por controle (``_merge_radio``, do
    ``HID_PHYS``) vale sem reler o sysfs; só quem chega sem ele é resolvido aqui
    — a mesma regra do ``orcamento_por_adaptador``, e é ela que deixa esta conta
    rodar no tique do ``state_full`` sem varrer ``/sys`` a cada volta.
    """
    conectados = [
        controle
        for controle in controles
        if controle.get("transport") == "bt" and controle.get("connected", True)
    ]
    conhecidos = {_mac_minusculo(e) for e in adaptadores} - {""}
    if not conectados and not conhecidos and not ar:
        return {}

    uniqs = [_hex(str(c.get("uniq") or "")) for c in conectados]
    publicados = {
        uniq: str(c.get("adaptador") or "").lower()
        for c, uniq in zip(conectados, uniqs, strict=True)
        if uniq and _mac_minusculo(str(c.get("adaptador") or ""))
    }
    faltam = [u for u in uniqs if u and u not in publicados]
    enderecos = dict(publicados)
    if faltam:
        enderecos.update(adaptador_por_uniq(faltam, raiz=raiz, listar=listar, ler=ler))
    de_pe = {_hex(u) for u in com_ponte_de_mic if _hex(u)}
    declarados = {_hex(u) for u in mic_declarado if _hex(u)}
    nomes = {k.lower(): v for k, v in (apelidos or {}).items()}
    orcamentos = orcamento_por_adaptador(
        conectados, ar=ar, n_max=n_max, raiz=raiz, listar=listar, ler=ler
    )

    juntos: dict[str, dict[str, Any]] = {}

    def _vazio() -> dict[str, Any]:
        return {
            "jogadores": [],
            "de_pe": set(),
            "declarados": set(),
            "agora": Ocupacao(),
            "planejada": Ocupacao(),
        }

    for endereco in sorted(conhecidos | {e for e in orcamentos if e}):
        juntos.setdefault(endereco, _vazio())
    for controle, uniq in zip(conectados, uniqs, strict=True):
        endereco = enderecos.get(uniq, SEM_ADAPTADOR) if uniq else SEM_ADAPTADOR
        alvo = juntos.setdefault(endereco, _vazio())
        alvo["jogadores"].append(_inteiro(controle.get("player_slot")))
        com_mic_agora = bool(uniq) and uniq in de_pe
        com_mic_plano = bool(uniq) and uniq in declarados
        if com_mic_agora:
            alvo["de_pe"].add(uniq)
        if com_mic_plano:
            alvo["declarados"].add(uniq)
        alvo["agora"] = _somar(alvo["agora"], com_mic=com_mic_agora)
        alvo["planejada"] = _somar(alvo["planejada"], com_mic=com_mic_plano)

    return {
        endereco: PlanoDoAdaptador(
            endereco=endereco,
            apelido=nomes.get(endereco, ""),
            jogadores=tuple(dados["jogadores"]),
            com_mic_de_pe=frozenset(dados["de_pe"]),
            com_mic_declarado=frozenset(dados["declarados"]),
            agora=dados["agora"],
            planejada=dados["planejada"],
            orcamento=orcamentos.get(endereco)
            or OrcamentoDoAdaptador(adaptador=endereco, n_max=n_max),
        )
        for endereco, dados in juntos.items()
    }


def _mac_minusculo(valor: str) -> str:
    """``aa:bb:…`` minúsculo, ou ``""`` — pela régua ESTRITA de ``conexao_zumbi``."""
    return mac_limpo(str(valor or "")) or ""


def cabe_mais_um(ocupacao: Ocupacao, *, com_mic: bool) -> tuple[bool, Ocupacao]:
    """``(cabe?, como ficaria)`` — a pergunta do planejamento.

    "Cabe" quer dizer **não passa do corte da "Cheia"**: até "Apertada" a mesa
    funciona e a pessoa decide; de "Cheia" para cima a fila estoura. O corte é
    o do ``radio_da_mesa`` e a palavra sai de ``palavra_da_ocupacao`` — um
    corte próprio aqui seria a segunda régua sobre o mesmo número.
    """
    depois = _somar(ocupacao, com_mic=com_mic)
    from hefesto_dualsense4unix.integrations.radio_da_mesa import PALAVRA_CHEIA

    return palavra_da_ocupacao(depois.fracao_total) != PALAVRA_CHEIA, depois


def ordem_dos_destinos(
    planos: Mapping[str, PlanoDoAdaptador],
    *,
    varrendo: Iterable[str] | None = None,
    exceto: str = "",
) -> list[PlanoDoAdaptador]:
    """A ordem dos destinos — a D8 dela, em UMA função.

    **Mais vaga de ponte primeiro; no empate, o de menos controles; o que está
    varrendo, por último.** É a regra de «onde parear» (D8: o adaptador só se
    escolhe no PAREAR, porque o host não liga o controle) e é a mesma que o
    «Equilibrar» usa para o destino de cada movimento: duas grafias da mesma
    escolha divergiriam na primeira remedição.

    Quem varre vai para o FIM, não para FORA — a razão é a de 20/09, escrita em
    :func:`ordem_de_redistribuicao`: excluir mataria a máquina de um adaptador
    só. ``varrendo`` ``None`` é *"não perguntei"*, e não penaliza ninguém.

    O balde :data:`radio_da_mesa.SEM_ADAPTADOR` nunca é destino, e ``exceto``
    (a origem) também não. O desempate final é o endereço, para a mesma mesa dar
    sempre a mesma resposta.
    """
    em_busca = {_hex(e) for e in (varrendo or ()) if _hex(e)}
    alvo_fora = _hex(exceto)
    candidatos = [
        p
        for endereco, p in planos.items()
        if endereco != SEM_ADAPTADOR and (not alvo_fora or _hex(endereco) != alvo_fora)
    ]
    return sorted(
        candidatos,
        # `False < True`: quem varre desce para o fim da fila, e continua NA fila.
        key=lambda p: (_hex(p.endereco) in em_busca, -p.vaga_de_ponte, p.no_ar, p.endereco),
    )


def _quem_move(origem: PlanoDoAdaptador) -> tuple[str, str] | None:
    """``(uniq, modo)`` do controle que sai da origem: o ÚLTIMO a chegar com ponte.

    Só controle COM ponte alivia o adaptador — é a ponte que transborda, e mover
    um sem ponte não muda a conta. Entre os que têm, o último da lista do dono:
    quem já estava fica, e a mesma mesa dá sempre a mesma resposta.
    """
    if origem.orcamento is None:
        return None
    com_ponte = [c for c in origem.orcamento.controles if c.ponte and c.uniq]
    if not com_ponte:
        return None
    escolhido = com_ponte[-1]
    return escolhido.uniq, str(escolhido.ponte)


def ordem_de_redistribuicao(
    planos: Mapping[str, PlanoDoAdaptador],
    *,
    varrendo: Iterable[str] | None = None,
) -> Redistribuicao | None:
    """A ordem de serviço — UM movimento —, ou ``None`` quando não há o que mover.

    **Esta é a régua AUTORITATIVA do arranjo, por decisão dela de 20/09/2026**
    (``D-A-REGUA-DO-ARRANJO-SE-DECIDE-COM-A-DIVERGENCIA-NA-MAO``). Havia duas
    funções respondendo *"qual controle move para qual adaptador"*, e elas
    divergiam; a palavra dela foi *"O motor (o que manda mover)"*. O
    ``arranjo_da_mesa.plano_dos_controles`` **aconselha**; quem emite ordem de
    serviço é esta função, e é aqui que filtro novo nasce. Uma régua só, uma
    grafia só. A R12 de 23/09 a mantém dona do «Equilibrar»: ela propõe UM
    movimento, a pessoa aperta PS + Create, a central confere, e só então esta
    função é chamada de novo e propõe o próximo.

    **O QUE ELA PESA MUDOU EM 23/09/2026 (MOVER-UM-POR-VEZ-01)**: as PONTES
    contra ``n_max``, não o total aditivo de fatias. Ela nasce quando um
    adaptador passa do limite de pontes, e o destino é o primeiro da D8
    (:func:`ordem_dos_destinos`) que ainda tem vaga — nunca um que ficaria além
    do limite ao receber (R3: a terceira ponte não sobe sem perguntar).

    FATO SUBSTITUÍDO: até 23/09 esta função nascia quando a fração ADITIVA
    passava de ``CORTE_APERTADA`` (0,85 de 1.600), movia o controle com
    microfone, e a mesa cheia dela — quatro com microfone, 0,69 — nunca gerava
    ordem. O estudo de 23/09 mediu por quê isso era a pergunta errada: a entrada
    ocupa o ar que sobra, e quem derruba os controles são as pontes.

    ``varrendo`` são os **endereços** dos adaptadores em modo de busca agora
    (:func:`varredura_do_radio.quem_esta_varrendo`). Eles vão para o FIM da fila
    de destinos — e a palavra é *fim*, não *fora*:

    * **excluir mataria a máquina de um adaptador só.** Com um adaptador, o
      único destino possível é o que varre; tirá-lo da lista faria o produto
      calar exatamente onde a perda é maior, e calar não é conselho;
    * mandar um controle PARA um adaptador que varre é mandá-lo para onde se
      mede de 32,5% a 43,4% de queda de pacotes (19/09/2026). Se houver outro
      destino que caiba, ele ganha — e se não houver, o que varre continua
      valendo.

    ``None`` é *"não perguntei"*, e é o padrão: **"não sei" nunca vira
    penalidade** — penalizar por ignorância moveria controle por palpite.

    **Qual controle move:** o que carrega ponte, e entre eles o último a chegar
    (:func:`_quem_move`). O texto NUNCA promete resultado: ele nomeia as pontes
    dos dois lados depois da mudança. "Ganho esperado" é aritmética, não
    promessa, e :data:`radio_da_mesa.PALAVRAS_DE_CULPA` é varrida contra ele.
    """
    reais = {
        endereco: plano
        for endereco, plano in planos.items()
        if endereco != SEM_ADAPTADOR
    }
    alem = sorted(
        (p for p in reais.values() if p.pontes > p.n_max),
        key=lambda p: (-(p.pontes - p.n_max), p.endereco),
    )
    if not alem:
        return None
    origem = alem[0]
    quem = _quem_move(origem)
    if quem is None:
        return None
    controle, modo = quem
    for destino in ordem_dos_destinos(reais, varrendo=varrendo, exceto=origem.endereco):
        if destino.pontes + 1 > destino.n_max:
            continue
        na_origem = origem.pontes - 1
        no_destino = destino.pontes + 1
        return Redistribuicao(
            origem=origem.endereco,
            destino=destino.endereco,
            origem_na_tela=origem.nome_na_tela,
            destino_na_tela=destino.nome_na_tela,
            o_que_eu_vi=(
                f"{origem.pontes} pontes de som e vibração num adaptador que "
                f"comporta {origem.n_max}."
            ),
            por_que_importa=POR_QUE_IMPORTA,
            ganho_esperado=(
                f'o "{origem.nome_na_tela}" ficaria com {na_origem} de '
                f'{origem.n_max}, e o "{destino.nome_na_tela}" com {no_destino} '
                f"de {destino.n_max}."
            ),
            controle=controle,
            modo=modo,
            pontes_na_origem_depois=na_origem,
            pontes_no_destino_depois=no_destino,
            n_max=origem.n_max,
        )
    return None


# ---------------------------------------------------------------------------
# O selo, e as frases que carregam a procedência do número
# ---------------------------------------------------------------------------


def selo_da_especificacao() -> str:
    """As 1600 fatias — especificação de terceiro, nunca medida aqui."""
    return (
        f"as {SLOTS_POR_SEGUNDO} fatias por segundo: especificação de "
        "terceiro (Bluetooth Classic, 625 µs por fatia)"
    )


def selo_do_medido() -> str:
    """O custo de UM controle — medido nesta casa, e só de um."""
    total_com_mic = HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC
    return (
        f"{_numero(HZ_INPUT_SEM_MIC)} sem microfone e "
        f"{_numero(total_com_mic)} com: medido aqui, A/B de 25/07/2026, "
        "e é UM controle"
    )


def selo_do_derivado() -> str:
    """A soma de N controles — derivada da conta, e nunca medida."""
    return "a soma de N controles: derivado da conta, e nunca medido"


def selo_das_procedencias(plano: PlanoDoAdaptador) -> tuple[str, ...]:
    """As três partes do selo, mais a confissão quando ela é devida.

    A quarta linha só aparece de :data:`ENSAIO_MAXIMO_DESTA_CASA` + 1 controles
    para cima, e é aí que a extrapolação começa a doer. Com um controle a conta
    **é** a medição, e a frase ali seria ruído.
    """
    partes = [selo_da_especificacao(), selo_do_medido(), selo_do_derivado()]
    if plano.agora.controles > ENSAIO_MAXIMO_DESTA_CASA:
        partes.append(frase_da_extrapolacao())
    return tuple(partes)


def frase_da_extrapolacao() -> str:
    """A confissão do que esta casa nunca mediu — e o número sai do ensaio."""
    return (
        "Esta conta soma o custo medido de UM controle. O maior ensaio desta "
        f"casa no rádio foi de {ENSAIO_MAXIMO_DESTA_CASA} — "
        f"{MESA_CHEIA_DESTA_CASA} ao mesmo tempo nunca foi medido."
    )


# ---------------------------------------------------------------------------
# O preço do microfone — o número de que ela precisa para decidir
# ---------------------------------------------------------------------------


def microfone_nasce_ligado() -> bool:
    """O microfone nasce ligado? **Sim, desde 17/09/2026.**

    A ``D-O-MIC-LIGADO-VALE-NO-RADIO`` FOI IMPLEMENTADA (NASCE-LIGADO-MIC-01), e
    o dono do padrão é ``daemon/subsystems/hotkey.nascer_no_ar``, chamado pelo
    gancho de conexão do daemon: a chegada de cada controle põe o microfone
    dele no ar, nos dois transportes, sem gesto nenhum dela. A régua é
    ``tests/unit/test_nasce_ligado_mic_01_o_microfone_nasce_no_ar.py``.

    **SUBSTITUÍDO O DONO, E A SUBSTITUIÇÃO É A CURA.** Aqui se lia o ``default``
    de ``ControleDeclarado.microfone`` (``utils/maquina.py``), com a promessa de
    que *"quando a decisão for tomada, quem muda é aquele campo"*. Aquele campo
    **não pode** mudar: ``utils/maquina.py`` diz que só ``True`` chega ao disco
    e que DESLIGAR grava ``None``, então ``None`` é ao mesmo tempo *"nunca
    pedi"* e *"não quero"*. Um ``default=True`` ali deixaria o gesto de
    desligar do card dela sem como se escrever — a cura mataria o interruptor
    que ela usa. São DOIS eixos: a declaração é o interruptor por card, o
    nascimento é o padrão; e este módulo fala do segundo.

    Não há valor a ler porque não há valor: o padrão virou COMPORTAMENTO, e
    derivá-lo de um campo que não o governa mais seria o instrumento apontando
    para outra coisa — a armadilha nº 1 desta casa.
    """
    return True


def frase_do_preco_por_controle() -> str:
    """O preço do microfone em UM controle — os dois números, lado a lado.

    É o número que a ``D-O-MIC-LIGADO-VALE-NO-RADIO`` precisa ter na mesa:
    276,7 das 1600 fatias com o microfone ligado, contra 260,4 sem. Sem ele a
    decisão de ligar o microfone por padrão no rádio seria tomada sem o preço.

    A última oração é a que fica pronta para receber o padrão: ela diz o que
    vale HOJE, e deriva de :func:`microfone_nasce_ligado`.
    """
    total_com_mic = HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC
    hoje = (
        "Hoje ele nasce ligado assim que o controle conecta."
        if microfone_nasce_ligado()
        else "Hoje ele nasce desligado, e só você o liga."
    )
    return (
        f"Um controle no rádio ocupa {_numero(HZ_INPUT_SEM_MIC)} das "
        f"{SLOTS_POR_SEGUNDO} fatias sem microfone, e {_numero(total_com_mic)} "
        f"com ele ligado. {hoje}"
    )


def frase_da_capacidade_do_mic(quantos: int = MESA_CHEIA_DESTA_CASA) -> str:
    """O achado que muda a decisão: quem enche o adaptador é a QUANTIDADE.

    A frase que existia dizia o custo do microfone e parava ali. O que ela não
    dizia — e é o que decide — está na conta: com quatro controles num
    adaptador só, ligar o microfone dos quatro sobe de 1042 para 1107 das
    1600 fatias. Quatro pontos. O vilão da intuição não é o vilão da medição.

    Todos os números derivam das constantes; nenhum é digitado.
    """
    quantos = max(1, quantos)
    sem = _somar(Ocupacao(), com_mic=False, quantos=quantos)
    com = _somar(Ocupacao(), com_mic=True, quantos=quantos)
    pontos = round((com.fracao_total - sem.fracao_total) * 100)
    return (
        f"Com {quantos} controles no mesmo adaptador, ligar o microfone de "
        f"todos sobe de {round(sem.slots_total)} para "
        f"{round(com.slots_total)} das {sem.slots_teto} fatias — "
        f"{pontos} pontos. Quem enche o adaptador é a quantidade de "
        "controles, não o microfone."
    )


# ---------------------------------------------------------------------------
# A fala da tela sobre um plano
# ---------------------------------------------------------------------------


def nomes_dos_jogadores(plano: PlanoDoAdaptador) -> str:
    """``"Jogadores 1 e 2"`` — e :data:`SEM_NUMERO` para quem não tem número.

    Nunca ``índice + 1``: a conta posicional já deu "Jogador 4" a DOIS cards
    da mesma mesa (22/08/2026). Null honesto vale mais que número errado.
    """
    numeros = [str(j) for j in plano.jogadores if j is not None]
    sem_numero = sum(1 for j in plano.jogadores if j is None)
    partes: list[str] = []
    if numeros:
        rotulo = "Jogadores" if len(numeros) > 1 else "Jogador"
        partes.append(f"{rotulo} {_lista_em_portugues(numeros)}")
    if sem_numero:
        partes.append(SEM_NUMERO if sem_numero == 1 else f"{sem_numero}x {SEM_NUMERO}")
    return ", ".join(partes) if partes else SEM_NUMERO


def linha_do_plano(plano: PlanoDoAdaptador) -> str:
    """A linha de um adaptador: nome, quem está nele, a conta e a palavra."""
    ocupacao = plano.agora
    quantos_com_mic = ocupacao.com_microfone
    if quantos_com_mic == 0:
        mic = "sem microfone"
    elif quantos_com_mic == ocupacao.controles:
        mic = "com microfone"
    else:
        mic = f"{quantos_com_mic} com microfone"
    return (
        f'Adaptador "{plano.nome_na_tela}" · {nomes_dos_jogadores(plano)}, '
        f"{mic}   {round(ocupacao.slots_total)}/{ocupacao.slots_teto}  "
        f"{ocupacao.rotulo}"
    )


def linha_do_cabe_mais_um(plano: PlanoDoAdaptador, *, com_mic: bool = True) -> str:
    """A pergunta do planejamento, respondida sem inventar controle nenhum.

    É a metade que a ``D-MIC-SO-QUEM-ESTA-NA-MESA`` pediu: as caixinhas são uma
    por controle PRESENTE, e o planejamento se responde por esta linha derivada
    em vez de uma caixinha de um controle que não tem MAC onde ser gravado.
    """
    cabe, depois = cabe_mais_um(plano.agora, com_mic=com_mic)
    com = "com microfone" if com_mic else "sem microfone"
    resposta = "sim" if cabe else "não"
    return (
        f'Cabe mais um controle {com} no "{plano.nome_na_tela}": {resposta} — '
        f"ficaria em {round(depois.slots_total)} de {depois.slots_teto}."
    )


def linha_do_declarado_que_nao_subiu(plano: PlanoDoAdaptador) -> str | None:
    """A segunda linha, quando o que ela quer não é o que está de pé.

    ``None`` quando as duas contas coincidem — e aí a linha não aparece,
    porque a tela não tem nada a corrigir.

    **A FRASE PERDEU O "VOCÊ MARCOU" EM 18/09/2026, e ela estava mentindo.**
    Dizia *"Você marcou o microfone de um controle deste adaptador"*, e era
    verdade enquanto o microfone fosse opt-in. Com a ordem dela — *"todos os
    controles tem que nascer com tudo mic, giroscopio e afins"* — o produto
    liga por padrão, e a tela passaria a atribuir a ela um ato que ela não fez:
    o caso mais comum agora é justamente o do controle que ela nunca tocou.

    É a regra da casa sobre a tela: o produto não diz que ela fez o que ele
    fez sozinho.
    """
    pendentes = plano.declarado_que_nao_subiu
    if not pendentes:
        return None
    quantos = len(pendentes)
    if quantos == 1:
        return "O microfone de um controle deste adaptador ainda não subiu."
    return (
        f"O microfone de {quantos} controles deste adaptador ainda não subiu."
    )


def _lista_em_portugues(itens: Sequence[str]) -> str:
    """``["1", "2", "3"]`` → ``"1, 2 e 3"``."""
    if len(itens) <= 1:
        return "".join(itens)
    return f"{', '.join(itens[:-1])} e {itens[-1]}"


def _inteiro(valor: Any) -> int | None:
    """Inteiro, ou ``None`` — nunca um número chutado a partir da posição."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    return None


__all__ = [
    "ADAPTADOR_DESCONHECIDO",
    "ADAPTADOR_SEM_NOME",
    "ENSAIO_MAXIMO_DESTA_CASA",
    "FRASE_DO_ADAPTADOR_UNICO",
    "MESA_CHEIA_DESTA_CASA",
    "POR_QUE_IMPORTA",
    "SEM_NUMERO",
    "PlanoDoAdaptador",
    "Redistribuicao",
    "apelido_por_endereco",
    "cabe_mais_um",
    "frase_da_capacidade_do_mic",
    "frase_da_extrapolacao",
    "frase_do_preco_por_controle",
    "linha_do_cabe_mais_um",
    "linha_do_declarado_que_nao_subiu",
    "linha_do_plano",
    "microfone_nasce_ligado",
    "nomes_dos_jogadores",
    "ordem_de_redistribuicao",
    "ordem_dos_destinos",
    "plano_por_adaptador",
    "selo_da_especificacao",
    "selo_das_procedencias",
    "selo_do_derivado",
    "selo_do_medido",
]
