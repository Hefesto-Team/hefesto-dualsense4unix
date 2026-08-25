"""Seção 3 da aba Configurações — o PERFIL de desempenho e a conta do rádio.

TERRITÓRIO DE CONFIG-05. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.

A SEÇÃO RESPONDE DUAS PERGUNTAS, E SÓ AGORA A SEGUNDA
------------------------------------------------------

1. *"o que eu quero que fique ligado?"* — o **perfil de desempenho**;
2. *"cabe o que eu quero fazer?"* — a **conta de fatias por adaptador**, que é
   a pergunta que decide o produto (*cabem quatro controles com todas as
   features no rádio, nesta máquina?*) e que a seção nunca soube fazer.

AS DECISÕES QUE ESTE ARQUIVO CARREGA
------------------------------------

**1. Um perfil, três escolhas — `D-PERFIL-DE-DESEMPENHO` (24/08/2026).** Os
cinco degraus viraram três, e não por gosto de redação: medido em
`core/rumble.py`, `_ORCAMENTO_COM_TETO` só casa com `economia`, e
`balanceado`, `max`, `auto` e o não-declarado devolvem `None`. Eram cinco
botões, quatro sem efeito nenhum, governando uma feature. **A chave de disco
NÃO muda** — o esquema continua `Literal["economia", "balanceado", "max",
"auto"] | None`, e :data:`PERFIL_POR_TETO` é a migração 1-para-1 que lê o que
já está gravado.

**2. O microfone fica FORA do perfil.** Ele é o único que **capta a sala**, e
o mapa de canais registra que ele nasce desligado por privacidade **e** banda.
Perfil que liga microfone sozinho transforma uma escolha de desempenho numa
escolha de privacidade feita pelas costas. O que esta seção mostra dele é o
**preço** (:func:`plano_de_radio.frase_do_preco_por_controle`) — o número que
a `D-O-MIC-LIGADO-VALE-NO-RADIO` (aberta) precisa ter na mesa.

**3. A tabela tem UMA linha com ponto de aplicação, e diz as outras quatro.**
:data:`LINHAS_DO_TETO` é o dono único da lista, e :func:`alcance_de_hoje`
DERIVA a frase dela em vez de repeti-la. Antes eram duas coisas — uma frase
digitada ao lado de uma tabela — e elas podiam divergir sem ninguém notar.

**4. Esta seção NÃO grava.** O dono da escolha é o `machine.declare`, e o
gesto de gravar é o "Aplicar" do rodapé. O clique aqui só acumula em
`host._maquina_pendente`. A ÚNICA conversa com o daemon é a LEITURA de
`daemon.state_full`, sem a qual a conta não sabe quem está no rádio; o portão
`test_o_clique_nao_grava_nada` nomeia essa leitura e reprova qualquer outra.

**5. O número de percentual não é escrito aqui.** Ele vem de
`core.rumble.teto_do_orcamento`, que por sua vez o deriva de
`RUMBLE_POLICY_MULT` — o dono único do degrau. Escrever "30%" à mão nesta tela
é o HARM-19 de novo: a faixa valeu 2.0 no schema, 1.0 no handler e 200% no
deslizador ao mesmo tempo, e quem pagou foi ela.
"""
from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import Any

from hefesto_dualsense4unix.app.actions.config.moldura import (
    QUANDO_VALE,
    rotulo_de_apoio,
)
from hefesto_dualsense4unix.app.widgets.segmented_selector import SegmentedSelector
from hefesto_dualsense4unix.core.rumble import teto_do_orcamento
from hefesto_dualsense4unix.integrations import plano_de_radio
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

#: O título como ela o lê na tela.
#:
#: **PENDENTE DE COSTURA — DESEMP-1.** A `D-PERFIL-DE-DESEMPENHO` renomeia a
#: seção para "Desempenho", e o renome tem DUAS pontas: esta constante e
#: `ipc_bridge._CAMPOS_DA_MAQUINA["orcamento"]`, que é a frase com que o rodapé
#: nomeia o campo descartado. `ipc_bridge.py` é território de outra frente
#: nesta leva, e trocar só uma das duas pontas deixaria o rodapé chamando a
#: seção por um nome que não existe mais. O portão
#: `test_o_titulo_da_secao_e_o_rotulo_do_rodape_sao_a_mesma_palavra` já está de
#: pé e reprova a meia-correção — trocar as duas linhas de uma vez é o gesto.
TITULO = "Orçamento"

#: A dica do título. Ela mudou com a `D-PERFIL-DE-DESEMPENHO`: não é mais "um
#: teto", é um perfil que decide o que fica ligado.
DICA: str | None = (
    "O que fica ligado na mesa inteira, e quanto do rádio isso ocupa. As abas "
    "continuam mandando no que fazem — nenhum ajuste seu é apagado."
)

def _lista(itens: list[str]) -> str:
    """``["a", "b", "c"]`` → ``"a, b e c"``."""
    if len(itens) <= 1:
        return "".join(itens)
    return f"{', '.join(itens[:-1])} e {itens[-1]}"


#: As quatro chaves que o DISCO aceita. São as MESMAS de
#: `OrcamentoDeclarado.teto` (`utils/maquina.py`), e continuam as quatro mesmo
#: com a tela oferecendo três perfis: o esquema não muda, porque tirar `"auto"`
#: do `Literal` faria o `extra="forbid"` do pydantic recusar o DOCUMENTO
#: INTEIRO de quem já o declarou — o sintoma seria "não consegui gravar", que é
#: o sintoma errado para a causa certa.
#:
#: Gravar o RÓTULO no lugar da chave falha na próxima carga, e falha feio. O
#: teste `test_as_chaves_sao_as_do_schema` prende esta tupla ao Literal do
#: schema justamente para que as duas listas não possam divergir.
CHAVES: tuple[str, ...] = ("economia", "balanceado", "max", "auto")

#: Os três perfis, na ordem da tela. São ids de BOTÃO, nunca de disco — a
#: tradução para disco é :data:`TETO_POR_PERFIL`.
PERFIL_TUDO_LIGADO = "tudo_ligado"
PERFIL_BATERIA_LONGA = "bateria_longa"
PERFIL_EU_ESCOLHO = "eu_escolho"

PERFIS: tuple[str, ...] = (
    PERFIL_TUDO_LIGADO,
    PERFIL_BATERIA_LONGA,
    PERFIL_EU_ESCOLHO,
)

#: O rótulo de cada perfil — palavra dela, na `D-PERFIL-DE-DESEMPENHO`.
ROTULOS_DOS_PERFIS: dict[str, str] = {
    PERFIL_TUDO_LIGADO: "Tudo ligado",
    PERFIL_BATERIA_LONGA: "Bateria longa",
    PERFIL_EU_ESCOLHO: "Eu escolho",
}

#: Perfil da TELA -> chave do DISCO. `None` é a ausência da declaração, que é o
#: que "Eu escolho" quer dizer: nenhum teto de mesa, cada aba manda na sua.
#:
#: `"Tudo ligado"` grava `balanceado` e não `max` porque os dois devolvem o
#: mesmo teto (`None`) e `balanceado` é o que a aba Rumble já chama de "sem
#: teto". Gravar `max` prometeria uma diferença que o produto não tem.
TETO_POR_PERFIL: dict[str, str | None] = {
    PERFIL_TUDO_LIGADO: "balanceado",
    PERFIL_BATERIA_LONGA: "economia",
    PERFIL_EU_ESCOLHO: None,
}

#: Chave do DISCO -> perfil da TELA. É a migração da
#: `D-PERFIL-DE-DESEMPENHO`, e ela não perde nada: `economia` é o único que
#: impunha teto, e `balanceado`/`max`/`auto` devolviam os três o mesmo `None` —
#: quatro nomes para um comportamento só.
#:
#: **A AUSÊNCIA não está aqui, e é de propósito.** A decisão dela lista
#: "vazio → Tudo ligado" na tabela de migração; mas "vazio" não é um valor a
#: migrar, é a falta de qualquer declaração. Afundar "Tudo ligado" para quem
#: nunca declarou faria a tela afirmar uma escolha que ela não fez, e — pior —
#: mataria o gesto de desfazer: o `SegmentedSelector` é grupo de rádio e
#: IGNORA o clique no botão já afundado, então quem clicasse "Eu escolho"
#: (que grava a ausência) veria "Tudo ligado" afundar de novo na remontagem,
#: sem gesto nenhum para sair dali. É o mesmo defeito que fez o quinto botão
#: nascer. **PROVISÓRIO — decisão dela:** se ela quiser mesmo o botão afundado
#: por padrão, o conserto é o esquema ganhar um valor para "cada aba manda", e
#: aí a ausência deixa de existir.
PERFIL_POR_TETO: dict[str, str] = {
    "economia": PERFIL_BATERIA_LONGA,
    "balanceado": PERFIL_TUDO_LIGADO,
    "max": PERFIL_TUDO_LIGADO,
    "auto": PERFIL_TUDO_LIGADO,
}

#: O que a tela diz quando o perfil não impõe teto nenhum. Não é "100%": um
#: percentual afirmaria um limite onde não há, e o "Máximo" da aba Rumble
#: entrega 150% justamente por não ter limite.
SEM_TETO = "Sem teto"

#: A célula do "Eu escolho": não há teto de mesa, e a aba de origem decide.
CADA_ABA_MANDA = "Cada aba manda"

#: O que a célula diz de uma linha sem ponto de aplicação. Ela existe porque
#: uma célula vazia seria lida como "sem teto", e "sem teto" é uma AFIRMAÇÃO
#: sobre um limite que ninguém tem por onde impor.
SEM_PONTO_DE_APLICACAO = "Ainda não tem por onde ser limitado"


@dataclass(frozen=True)
class LinhaDoTeto:
    """Uma coisa que o perfil deveria alcançar, e se ela tem por onde.

    `ponto_de_aplicacao` é `"módulo:atributo"` — o funil por onde o teto passa
    de verdade —, ou `None` quando não existe nenhum. É `None` que a tabela
    mostra como :data:`SEM_PONTO_DE_APLICACAO`, e é dele que
    :func:`alcance_de_hoje` deriva a frase.

    O portão `test_so_a_vibracao_tem_ponto_de_aplicacao_hoje` IMPORTA cada
    ponto declarado: marcar "Gatilhos" como tendo ponto sem que exista reprova
    nomeando a linha. É a rede contra a tela prometer teto que ninguém impõe.
    """

    nome: str
    vem_de: str
    ponto_de_aplicacao: str | None = None

    @property
    def tem_ponto(self) -> bool:
        return bool(self.ponto_de_aplicacao)


#: As cinco coisas que o perfil deveria alcançar. Dono único: a tabela e a
#: frase de apoio saem daqui, e quando uma delas ganhar ponto de aplicação,
#: mudar o campo muda as duas de uma vez.
LINHAS_DO_TETO: tuple[LinhaDoTeto, ...] = (
    LinhaDoTeto(
        "Vibração",
        "Rumble",
        "hefesto_dualsense4unix.core.rumble:_effective_mult",
    ),
    LinhaDoTeto("Gatilhos", "Gatilhos"),
    LinhaDoTeto("Barra de luz", "Lightbar"),
    LinhaDoTeto("Microfone por rádio", "Os controles"),
    LinhaDoTeto("Giroscópio", "Perfis"),
)

#: Dica por perfil — cada uma diz o que aquele botão LIGA, e nenhuma promete
#: efeito que o clique não produz.
#:
#: A dica do antigo "Auto" **saiu inteira**, sem nota e sem data: ela dizia
#: *"A vibração acompanha a bateria: cheia joga inteira, pela metade cai para
#: 70%, abaixo de 20% cai para 30%"*, e isso é a escada de
#: `core.rumble._effective_mult` no ramo da política da **aba Rumble** — clicar
#: naquele botão não ligava a escada, não a desligava e não mudava nada. Fato
#: errado se substitui (regra dela, 11/08/2026), não se guarda ao lado do
#: certo.
#:
#: A do "Bateria longa" é DERIVADA, e por causa do mesmo defeito. A palavra
#: dela na `D-PERFIL-DE-DESEMPENHO` era *"vibração com teto de 30% e barra de
#: luz apagada"* — e a barra de luz **não tem ponto de aplicação nenhum** hoje
#: (:data:`LINHAS_DO_TETO`), então escrevê-la aqui prometeria de novo o que o
#: clique não produz. Derivando da tabela, a frase não pode prometer mais do
#: que a tabela mostra, e o dia em que a barra de luz ganhar esse ponto ela
#: entra sozinha nas duas.
def _dica_da_bateria_longa() -> str:
    """O que o perfil de bateria faz HOJE, e o que ele ainda não alcança."""
    chave = TETO_POR_PERFIL[PERFIL_BATERIA_LONGA]
    teto = teto_do_orcamento(chave) if isinstance(chave, str) else None
    forca = f"{round(teto * 100)}% da força" if teto is not None else SEM_TETO
    pendentes = [linha.nome for linha in LINHAS_DO_TETO if not linha.tem_ponto]
    if not pendentes:
        return f"Vibração com {forca}."
    return (
        f"Vibração com {forca}. {_lista(pendentes)} continuam como estão: o "
        "teto ainda não os alcança."
    )


DICAS: dict[str, str] = {
    PERFIL_TUDO_LIGADO: (
        "Gatilho adaptativo, vibração no que o jogo pedir, barra de luz, "
        "giroscópio e touchpad."
    ),
    PERFIL_BATERIA_LONGA: _dica_da_bateria_longa(),
    PERFIL_EU_ESCOLHO: (
        "Nenhum teto de mesa: os ajustes de cada aba mandam, um por um."
    ),
}

#: Cabeçalho da tabela de consequências. DERIVADO dos perfis: uma coluna por
#: opção oferecida, sempre. Antes eram três colunas para cinco botões, e a
#: tabela calava justamente sobre os dois que não faziam nada.
COLUNAS: tuple[str, ...] = ("O que", "Vem de", *(ROTULOS_DOS_PERFIS[p] for p in PERFIS))


def alcance_de_hoje() -> str:
    """A frase de apoio, DERIVADA de :data:`LINHAS_DO_TETO`.

    Ela existe porque a ausência das outras quatro linhas não fala — e
    silêncio, nesta tela, seria lido como "o teto vale para tudo". Derivar em
    vez de repetir é a cura de sempre: um dono só. Antes, a frase era um
    literal ao lado da tabela, e as duas podiam divergir sem ninguém notar.
    """
    com_ponto = [linha.nome for linha in LINHAS_DO_TETO if linha.tem_ponto]
    sem_ponto = [linha.nome for linha in LINHAS_DO_TETO if not linha.tem_ponto]
    alcanca = _lista(com_ponto) if com_ponto else "nada"
    if not sem_ponto:
        return f"Por enquanto o teto alcança {alcanca}."
    return (
        f"Por enquanto o teto alcança {alcanca} e nada mais. "
        f"{_lista(sem_ponto)} entram quando ganharem esse ponto."
    )


def orcamento_em_vigor(host: Any = None) -> str | None:
    """A chave do orçamento que está GRAVADA — nunca a que espera o "Aplicar".

    É de propósito que ela ignore `host._maquina_pendente`: quem lê esta função
    é a aba de origem (a linha "limitado a 30% pelo orçamento" da aba Rumble), e
    aquela linha descreve o que o Hefesto está aplicando AGORA. Mostrar ali a
    escolha ainda pendente faria a aba Rumble afirmar um limite que o daemon não
    está impondo, que é a mentira oposta e igualmente cara.

    `host._orcamento_lido` é o ponto de injeção, no molde do `_mesa_leitor` da
    seção da mesa: é por ele que o retrato das abas alimenta a tela sem tocar o
    disco dela, e é por ele que o teste roda sem depender do `config_dir()` da
    máquina em que está.

    Devolve `None` quando ninguém declarou nada — e `None` aqui significa "não
    sei", nunca "sem teto".
    """
    leitor = getattr(host, "_orcamento_lido", None) if host is not None else None
    if leitor is not None:
        with contextlib.suppress(Exception):
            valor = leitor()
            return valor if isinstance(valor, str) else None
        return None
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    return carregar_maquina().orcamento.teto


def orcamento_na_tela(host: Any = None) -> str | None:
    """A chave que o BOTÃO desta aba mostra — o gravado, ou o que espera o Aplicar.

    **Por que ela existe ao lado de `orcamento_em_vigor`, e não no lugar dela**
    (achado da conferência de 23/08/2026). As duas respondem perguntas
    diferentes, e cada consumidor precisa de uma:

    * a aba Rumble pergunta *"que limite o daemon está impondo AGORA?"* — e
      responde com `orcamento_em_vigor`, que ignora o pendente de propósito.
      Mostrar ali a escolha ainda não aplicada faria aquela linha afirmar um
      limite que ninguém está impondo;
    * o botão DESTA aba pergunta *"o que a pessoa escolheu?"* — e a resposta tem
      de incluir o que ela acabou de declarar. Sem isso a tela se contradiz: o
      rodapé diz "há escolhas por aplicar" e o botão mostra o valor do disco.

    É o mesmo contrato que as seções irmãs já usam (`secao_mesa`,
    `secao_controles`): disco por baixo, declaração por cima.

    O caso que mais dói, e é novo: o "Eu escolho" declara ``teto: None``. Sem
    esta função, remontar a aba traz o botão ANTIGO de volta afundado — a
    escolha da pessoa some da tela sem nada avisar.
    """
    pendente = getattr(host, "_maquina_pendente", None) or {}
    orcamento = pendente.get("orcamento") if isinstance(pendente, dict) else None
    if isinstance(orcamento, dict) and "teto" in orcamento:
        teto = orcamento["teto"]
        return str(teto) if isinstance(teto, str) else None
    return orcamento_em_vigor(host)


def perfil_na_tela(host: Any = None) -> str | None:
    """Qual dos três botões nasce afundado, lendo o que já está no disco.

    `None` quer dizer **nenhum** — e é o caso de quem nunca declarou nada. Ver
    a nota de :data:`PERFIL_POR_TETO` para o porquê de a ausência não afundar
    "Tudo ligado".
    """
    gravado = orcamento_na_tela(host)
    if not isinstance(gravado, str):
        return None
    return PERFIL_POR_TETO.get(gravado)


def celula_do_teto(orcamento: str) -> str:
    """O que a coluna de um orçamento diz sobre a vibração.

    O número sai de `teto_do_orcamento`, que o deriva de `RUMBLE_POLICY_MULT`.
    Nenhum percentual desta tela é digitado: um número digitado sobrevive à
    mudança do degrau que ele descrevia, e aí a tela passa a prometer o que o
    daemon não faz.
    """
    teto = teto_do_orcamento(orcamento)
    if teto is None:
        return SEM_TETO
    return f"No máximo {round(teto * 100)}% da força"


def celula_do_perfil(perfil: str, linha: LinhaDoTeto) -> str:
    """A célula de um perfil numa linha da tabela.

    Sem ponto de aplicação, a célula diz isso e não "Sem teto": "Sem teto" é
    uma afirmação sobre um limite, e afirmar limite nenhum onde não existe nem
    por onde impor é a tela falando do que não sabe.
    """
    if not linha.tem_ponto:
        return SEM_PONTO_DE_APLICACAO
    chave = TETO_POR_PERFIL.get(perfil)
    if chave is None:
        return CADA_ABA_MANDA
    return celula_do_teto(chave)


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura.

    `host` é o `HefestoApp`: dele vêm `_get` (widgets do Glade) e o que os
    outros mixins já penduraram. `caixa` é um `Gtk.Box` vertical, com as
    margens da casa já aplicadas.

    Contrato, e ele vale para as cinco: **nunca levantar**. Uma seção que
    falha ao montar não pode derrubar a aba, e uma aba que falha não pode
    derrubar a janela. Quem chama já embrulha em `contextlib.suppress`, mas a
    tolerância começa aqui.
    """
    caixa.pack_start(_fileira_dos_perfis(host), False, False, 0)
    caixa.pack_start(rotulo_de_apoio(QUANDO_VALE), False, False, 0)
    caixa.pack_start(_bloco_da_conta(host), False, False, 0)
    caixa.pack_start(_tabela_das_consequencias(), False, False, 0)
    caixa.pack_start(rotulo_de_apoio(alcance_de_hoje()), False, False, 0)


def _fileira_dos_perfis(host: Any) -> Any:
    """Os três perfis, deitados, com o que já está no disco marcado.

    **Por que a orientação é trocada à mão.** O `SegmentedSelector` sem `wrap`
    é um `Gtk.Box` VERTICAL (`segmented_selector.py:206`) e empilharia as
    opções uma sobre a outra; com `wrap=True` ele vira grade de TRÊS colunas
    fixas (`_WRAP_COLUNAS`). Deitar a caixa é a terceira via, e é a barata: a
    classe `linked` que o widget já aplica sem `wrap` foi feita para
    exatamente esta fileira de botões colados, e `set_orientation` é API do
    próprio `Gtk.Box`. Mexe só nesta instância.

    A marcação inicial vem ANTES do `connect`, e a ordem é a cura: o
    `set_active_id` EMITE "changed" (espelha o `GtkComboBox`), e com o handler
    já ligado abrir a janela deixaria uma declaração pendente que ninguém fez —
    e o próximo "Aplicar" a gravaria como escolha dela.
    """
    from gi.repository import Gtk

    seletor = SegmentedSelector()
    with contextlib.suppress(Exception):
        seletor.set_orientation(Gtk.Orientation.HORIZONTAL)
    seletor.set_items([(perfil, ROTULOS_DOS_PERFIS[perfil]) for perfil in PERFIS])
    seletor.set_tooltips(dict(DICAS))
    perfil = perfil_na_tela(host)
    if perfil in PERFIS:
        with contextlib.suppress(Exception):
            seletor.set_active_id(str(perfil))
    else:
        # Ninguém declarou: nenhum botão afundado. Ver a nota de
        # `PERFIL_POR_TETO`.
        with contextlib.suppress(Exception):
            seletor.limpar_ativo()
    seletor.set_hexpand(False)
    seletor.connect("changed", lambda sel: _ao_escolher(host, sel))
    host._config_orcamento_seletor = seletor

    linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    linha.pack_start(seletor, False, False, 0)
    return linha


def _ao_escolher(host: Any, seletor: Any) -> None:
    """Acumula a escolha em `_maquina_pendente`. NÃO grava, NÃO manda IPC.

    A declaração é PARCIAL de propósito: `fundir_declaracao` desce nos
    dicionários aninhados, então mandar só `{"orcamento": {"teto": ...}}` não
    apaga o que as outras quatro seções declararam na mesma janela.

    O "Eu escolho" vira `None` ANTES da guarda, e não pode virar depois: `None`
    presente na declaração é escolha ("voltei a decidir aba por aba") e
    SOBRESCREVE, enquanto a AUSÊNCIA da chave preserva o que havia — devolver
    cedo aqui deixaria a escolha antiga no rascunho e no disco.
    """
    from hefesto_dualsense4unix.utils.maquina import fundir_declaracao

    escolha = seletor.get_active_id()
    if escolha not in TETO_POR_PERFIL:
        return
    teto = TETO_POR_PERFIL[str(escolha)]
    host._maquina_pendente = fundir_declaracao(
        getattr(host, "_maquina_pendente", None),
        {"orcamento": {"teto": teto}},
    )
    # A marca "há escolhas por aplicar" no rodapé (23/08/2026). Sem esta chamada
    # ela só acendia ao trocar de aba ou ao ir para a bandeja — quem declarava e
    # clicava direto no X via o diálogo de fechamento sem nunca ter visto o aviso.
    # `getattr` com guarda é o idioma da casa para fiação de aba: hospedeiro de
    # teste sem rodapé não pode derrubar a declaração.
    marcar = getattr(host, "_marcar_declaracao_por_aplicar", None)
    if marcar is not None:
        with contextlib.suppress(Exception):
            marcar()
    logger.info("config_orcamento_escolhido", perfil=escolha, teto=teto)


def _tabela_das_consequencias() -> Any:
    """A tabela "o que o perfil faz com cada coisa" — as cinco linhas.

    `Gtk.Grid` e não caixas encaixadas porque as colunas têm de alinhar entre
    as linhas.

    Sem `column_homogeneous`: a coluna "O que" tem uma palavra e a de Bateria
    longa tem uma frase, e forçar largura igual daria à palavra o tamanho da
    frase — é a mesma medição que proíbe `set_homogeneous(True)` nas fileiras
    desta aba (`main.glade:1644-1650`: 459px para a palavra "Auto", e a largura
    mínima da janela em 1004px numa janela que abre com 1180 e não rola na
    horizontal).
    """
    from gi.repository import Gtk

    grade = Gtk.Grid()
    grade.set_row_spacing(4)
    grade.set_column_spacing(16)
    grade.set_margin_top(4)

    for coluna, titulo in enumerate(COLUNAS):
        grade.attach(_celula(titulo, cabecalho=True), coluna, 0, 1, 1)

    for indice, linha in enumerate(LINHAS_DO_TETO, start=1):
        grade.attach(_celula(linha.nome), 0, indice, 1, 1)
        grade.attach(_celula(linha.vem_de), 1, indice, 1, 1)
        if not linha.tem_ponto:
            # A frase vale para os TRÊS perfis, e por isso ocupa as três
            # colunas de uma vez. Repeti-la três vezes na mesma linha custou
            # 503px de largura mínima à seção (medido em 25/08/2026: 939px
            # contra 436px), e a janela abre com 1180 sem rolagem horizontal.
            # Uma célula que atravessa também LÊ melhor: a informação é sobre a
            # linha, não sobre cada perfil.
            grade.attach(
                _celula(SEM_PONTO_DE_APLICACAO), 2, indice, len(PERFIS), 1
            )
            continue
        for coluna, perfil in enumerate(PERFIS, start=2):
            grade.attach(_celula(celula_do_perfil(perfil, linha)), coluna, indice, 1, 1)
    return grade


def _celula(texto: str, *, cabecalho: bool = False) -> Any:
    """Uma célula da tabela: alinhada à esquerda, sem quebra.

    O cabeçalho é esmaecido em vez de negrito: negrito numa linha inteira
    compete com o título da seção logo acima, e a coluna já se distingue pela
    posição.
    """
    from gi.repository import Gtk

    rotulo = Gtk.Label(label=_(texto))
    rotulo.set_xalign(0.0)
    if cabecalho:
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("dim-label")
    return rotulo


# ---------------------------------------------------------------------------
# A conta de fatias — a pergunta que decide o produto
# ---------------------------------------------------------------------------

#: O que a tela diz enquanto não sabe quem está no rádio. **Nunca "Folgada"**:
#: a cura da B1, medida em 23/08/2026 — com o Hefesto parado as três barras
#: diziam "Folgada", em verde, "0/1600", byte a byte a tela de um rádio vazio.
#: Zero pinta verde, e "0/1600" é afirmação numérica sobre o que não se leu.
SEM_RESPOSTA_DO_DAEMON = (
    "Não sei quem está no rádio — o Hefesto não respondeu. Ligue-o na aba "
    "Sistema para ver a conta."
)

#: O que a tela diz quando o daemon respondeu e não há ninguém no rádio. É
#: diferente de não saber, e a diferença é a informação inteira.
NINGUEM_NO_RADIO = "Nenhum controle no rádio agora — nada ocupando fatia."

#: O cabeçalho do bloco da conta.
TITULO_DA_CONTA = "Quanto do rádio cada adaptador já gasta"


def _bloco_da_conta(host: Any) -> Any:
    """A conta por adaptador, montada e pendurada no hospedeiro.

    Devolve a caixa; o objeto que a mantém viva e a redesenha fica em
    `host._config_conta_de_slots`, no mesmo molde do seletor logo acima (solto
    numa variável local ele é coletado ao fim do `montar`, e o redesenho depois
    da resposta do daemon cairia no vazio).
    """
    conta = _ContaDeSlots(host)
    host._config_conta_de_slots = conta
    conta.pedir_o_estado()
    return conta.caixa


class _ContaDeSlots:
    """O bloco que responde *"cabe o que eu quero fazer?"*.

    **A única conversa desta seção com o daemon, e ela é LEITURA.** O bloco
    precisa de uma coisa que o sysfs não tem: a lista de controles conectados,
    com transporte e `uniq`. Ela mora no `daemon.state_full`, e vem por
    `call_async` porque o montador roda na thread do GTK — um IPC síncrono ali
    congelaria a janela no gesto mais comum da aba.

    **A foto não fala com o daemon.** Quem injetou `_mesa_leitor` está
    capturando `docs/usage/assets/`, e o `state_full` desta máquina traz o
    `uniq` dos controles DELA, que é MAC — nenhum portão de anonimato varre
    imagem (F5). Com o desvio de pé o bloco fica com o que tem, que é nada, e
    diz que não sabe. `_desempenho_leitor` é o ponto de injeção do teste e da
    foto que QUER a conta.

    **Dívida declarada:** este é o SEGUNDO `state_full` por entrada na aba (o
    primeiro é o da seção Conexões). O conserto é um leitor único no nível da
    aba, com assinantes, e ele toca território de outra frente — está na
    entrega desta, em "o que sobrou para o próximo".
    """

    def __init__(self, host: Any) -> None:
        from gi.repository import Gtk

        self._host = host
        self._controles: list[dict[str, Any]] = []
        self._com_ponte_de_mic: tuple[str, ...] = ()
        self._respondeu: bool | None = None
        self._pedido_em_voo = False
        self.caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.caixa.set_margin_top(8)
        self._desenhar()

    # -- leitura ---------------------------------------------------------

    def pedir_o_estado(self) -> None:
        """Pede ao daemon quem está no rádio — sem bloquear a thread da tela."""
        leitor = getattr(self._host, "_desempenho_leitor", None)
        if leitor is not None:
            estado: Any = None
            with contextlib.suppress(Exception):
                estado = leitor()
            self._respondeu = estado is not None
            self._aplicar_estado(estado if isinstance(estado, dict) else None)
            return
        if getattr(self._host, "_mesa_leitor", None) is not None:
            # Bancada do retrato: sem IPC, e a tela diz que não sabe.
            return
        if self._pedido_em_voo:
            return

        # O timeout é o MESMO de toda leitura de `daemon.state_full` da casa
        # (`mode_transition.py:43`, HARM-15: 1,0 s, porque sob hotplug o daemon
        # passa dos 0,25 s de padrão e a janela o declarava morto estando vivo).
        from hefesto_dualsense4unix.app.actions.mode_transition import (
            STATE_IPC_TIMEOUT_S,
        )
        from hefesto_dualsense4unix.app.ipc_bridge import call_async

        def _chegou(estado: Any) -> bool:
            self._pedido_em_voo = False
            self._respondeu = True
            self._aplicar_estado(estado if isinstance(estado, dict) else None)
            return False

        def _falhou(_exc: Exception) -> bool:
            self._pedido_em_voo = False
            self._respondeu = False
            self._aplicar_estado(None)
            return False

        self._pedido_em_voo = True
        with contextlib.suppress(Exception):
            call_async(
                "daemon.state_full",
                None,
                _chegou,
                _falhou,
                timeout_s=STATE_IPC_TIMEOUT_S,
            )

    def _aplicar_estado(self, estado: dict[str, Any] | None) -> None:
        """Guarda os controles e os `uniq` com a ponte DE PÉ, e redesenha."""
        controles = (estado or {}).get("controllers")
        self._controles = (
            [c for c in controles if isinstance(c, dict)]
            if isinstance(controles, list)
            else []
        )
        bt_mic = (estado or {}).get("bt_mic")
        uniqs = bt_mic.get("uniqs") if isinstance(bt_mic, dict) else None
        self._com_ponte_de_mic = (
            tuple(str(u) for u in uniqs if u) if isinstance(uniqs, list) else ()
        )
        self._desenhar()

    def _declaracoes(self) -> tuple[str, ...]:
        """Os `uniq` cujo microfone ELA marcou — o rascunho por cima do disco."""
        declaradas: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.utils.maquina import carregar_maquina

            declaradas = {
                chave: valor.microfone
                for chave, valor in carregar_maquina().controles.items()
            }
        pendente = getattr(self._host, "_maquina_pendente", None) or {}
        controles = pendente.get("controles") if isinstance(pendente, dict) else None
        if isinstance(controles, dict):
            for chave, valor in controles.items():
                if isinstance(valor, dict) and "microfone" in valor:
                    declaradas[chave] = valor["microfone"]
        return tuple(chave for chave, ligado in declaradas.items() if ligado)

    # -- desenho ---------------------------------------------------------

    def _planos(self) -> dict[str, plano_de_radio.PlanoDoAdaptador]:
        # `_desempenho_sysfs` é o ponto de injeção da VARREDURA, e ele existe
        # pela mesma razão do `_desempenho_leitor`: quem amarra controle a
        # adaptador é o `/sys/class/hidraw` desta máquina, e um teste que
        # dependesse dele mediria a bancada de quem o roda em vez do código.
        sysfs = getattr(self._host, "_desempenho_sysfs", None) or {}
        with contextlib.suppress(Exception):
            return plano_de_radio.plano_por_adaptador(
                self._controles,
                com_ponte_de_mic=self._com_ponte_de_mic,
                mic_declarado=self._declaracoes(),
                apelidos=self._apelidos(),
                **dict(sysfs),
            )
        return {}

    def _apelidos(self) -> dict[str, str]:
        """`endereço -> nome dela`, quando o hospedeiro já conhece os dongles.

        Sem dongles conhecidos a tela diz :data:`ADAPTADOR_SEM_NOME`, nunca
        `hciN`: o índice é a vaga, não o aparelho, e ele inverte entre boots.
        """
        dongles = getattr(self._host, "_config_dongles", None) or ()
        with contextlib.suppress(Exception):
            return plano_de_radio.apelido_por_endereco(tuple(dongles))
        return {}

    def _desenhar(self) -> None:
        with contextlib.suppress(Exception):
            for filho in list(self.caixa.get_children()):
                self.caixa.remove(filho)
        for texto in self.falas():
            self.caixa.pack_start(rotulo_de_apoio(texto), False, False, 0)
        with contextlib.suppress(Exception):
            self.caixa.show_all()

    def falas(self) -> tuple[str, ...]:
        """Todo o texto do bloco, na ordem — e é por aqui que o teste o lê.

        Devolver o texto antes de o virar widget é o que deixa o portão das
        `PALAVRAS_DE_CULPA` varrer TUDO que a seção produz, e não só o que
        alguém lembrou de olhar.
        """
        linhas: list[str] = [TITULO_DA_CONTA]
        if self._respondeu is not True:
            linhas.append(SEM_RESPOSTA_DO_DAEMON)
            linhas.append(plano_de_radio.frase_do_preco_por_controle())
            return tuple(linhas)

        planos = self._planos()
        if not planos:
            linhas.append(NINGUEM_NO_RADIO)
            linhas.append(plano_de_radio.frase_do_preco_por_controle())
            return tuple(linhas)

        maior = 0
        for _endereco, plano in sorted(planos.items()):
            linhas.append(plano_de_radio.linha_do_plano(plano))
            pendente = plano_de_radio.linha_do_declarado_que_nao_subiu(plano)
            if pendente:
                linhas.append(pendente)
            linhas.append(plano_de_radio.linha_do_cabe_mais_um(plano))
            maior = max(maior, plano.agora.controles)

        ordem = plano_de_radio.ordem_de_redistribuicao(planos)
        if ordem is not None:
            linhas.append(
                f'1 mudança recomendada: mova um controle do "{ordem.origem_na_tela}" '
                f'para o "{ordem.destino_na_tela}".'
            )
            linhas.append(f"O que eu vi aqui: {ordem.o_que_eu_vi}")
            linhas.append(f"Por que importa: {ordem.por_que_importa}")
            linhas.append(f"Ganho esperado: {ordem.ganho_esperado}")
        elif _algum_apertado(planos):
            linhas.append(plano_de_radio.FRASE_DO_ADAPTADOR_UNICO)

        linhas.append(plano_de_radio.frase_do_preco_por_controle())
        linhas.append(plano_de_radio.frase_da_capacidade_do_mic(max(maior, 1)))
        maior_plano = max(planos.values(), key=lambda p: p.agora.controles)
        linhas.extend(plano_de_radio.selo_das_procedencias(maior_plano))
        return tuple(linhas)


def _algum_apertado(planos: dict[str, plano_de_radio.PlanoDoAdaptador]) -> bool:
    """Algum adaptador passou do corte da "Apertada"?"""
    from hefesto_dualsense4unix.integrations.radio_da_mesa import CORTE_APERTADA

    return any(p.agora.fracao_total > CORTE_APERTADA for p in planos.values())
