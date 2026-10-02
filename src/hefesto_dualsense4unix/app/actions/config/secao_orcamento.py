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
um perfil de DESEMPENHO que o ligasse ou o calasse transformaria uma escolha
de bateria numa escolha de privacidade feita pelas costas. A decisão é dela
(`D-PERFIL-DE-DESEMPENHO`, 24/08/2026) e continua inteira.

**A RAZÃO CITADA CADUCOU — NASCE-LIGADO-MIC-01, 17/09/2026.** Aqui se lia que
*"o mapa de canais registra que ele nasce desligado por privacidade e banda"*.
Ele nasce LIGADO desde 17/09: a chegada do controle põe o microfone no ar
(`daemon/subsystems/hotkey.nascer_no_ar`), que é a `D-O-MIC-LIGADO-VALE-NO-RADIO`
(decisoes-dela.csv id 38) finalmente implementada. **A decisão de 24/08 não
depende disso** — ela é sobre o perfil não ser o dono do microfone, e isso vale
igual com o microfone nascendo ligado. O que esta seção mostra dele continua
sendo o **preço** (:func:`plano_de_radio.frase_do_preco_por_controle`), que é a
condição que ela mesma pôs: *"LIGADO SEMPRE… COM A TELA DIZENDO O PREÇO"*.

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
    marcar_afordancias,
    rotulo_de_apoio,
)
from hefesto_dualsense4unix.app.widgets.segmented_selector import SegmentedSelector
from hefesto_dualsense4unix.core.rumble import SEM_TETO, teto_do_orcamento
from hefesto_dualsense4unix.integrations import plano_de_radio
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger

logger = get_logger(__name__)

TITULO = "Desempenho"

DICA: str | None = (
    "O que fica ligado em todos os controles, e quanto do rádio isso ocupa. As "
    "abas continuam mandando no que fazem — nenhum ajuste seu é apagado."
)

def _lista(itens: list[str]) -> str:
    """``["a", "b", "c"]`` → ``"a, b e c"``."""
    if len(itens) <= 1:
        return "".join(itens)
    return f"{', '.join(itens[:-1])} e {itens[-1]}"


CHAVES: tuple[str, ...] = ("economia", "balanceado", "max", "auto")

PERFIL_TUDO_LIGADO = "tudo_ligado"
PERFIL_BATERIA_LONGA = "bateria_longa"
PERFIL_EU_ESCOLHO = "eu_escolho"

PERFIS: tuple[str, ...] = (
    PERFIL_TUDO_LIGADO,
    PERFIL_BATERIA_LONGA,
    PERFIL_EU_ESCOLHO,
)

#: Global de Bateria da Sistema leem daqui.
ROTULOS_DOS_PERFIS: dict[str, str] = {
    PERFIL_TUDO_LIGADO: "Perfil Máximo",
    PERFIL_BATERIA_LONGA: "Perfil Econômico",
    PERFIL_EU_ESCOLHO: "Personalizado",
}

TETO_POR_PERFIL: dict[str, str | None] = {
    PERFIL_TUDO_LIGADO: "balanceado",
    PERFIL_BATERIA_LONGA: "economia",
    PERFIL_EU_ESCOLHO: None,
}

PERFIL_POR_TETO: dict[str, str] = {
    "economia": PERFIL_BATERIA_LONGA,
    "balanceado": PERFIL_TUDO_LIGADO,
    "max": PERFIL_TUDO_LIGADO,
    "auto": PERFIL_TUDO_LIGADO,
}


CADA_ABA_MANDA = "Cada aba manda"

SEM_PONTO_DE_APLICACAO = "Ainda não tem por onde ser limitado"


@dataclass(frozen=True)
class LinhaDoTeto:
    """Uma coisa que o perfil deveria alcançar, e se ela tem por onde."""

    nome: str
    vem_de: str
    ponto_de_aplicacao: str | None = None

    @property
    def tem_ponto(self) -> bool:
        return bool(self.ponto_de_aplicacao)


LINHAS_DO_TETO: tuple[LinhaDoTeto, ...] = (
    LinhaDoTeto(
        "Vibração",
        "Rumble",
        "hefesto_dualsense4unix.core.rumble:_effective_mult",
    ),
    LinhaDoTeto(
        "Gatilhos",
        "Gatilhos",
        "hefesto_dualsense4unix.profiles.manager:_perfil_na_economia",
    ),
    LinhaDoTeto(
        "Barra de luz",
        "Lightbar",
        "hefesto_dualsense4unix.profiles.manager:_perfil_na_economia",
    ),
    LinhaDoTeto("Microfone por BT", "Os controles"),
    LinhaDoTeto("Giroscópio", "Perfis"),
)

#: que a tabela mostra, e o dia em que a barra de luz ganhar esse ponto ela
#: gastando menos»* — a luz fica mais fraca e não apaga. <!-- noqa-acento: citação literal dela -->
def _dica_da_bateria_longa() -> str:
    """O que o perfil de bateria faz HOJE, e o que fica como está."""
    chave = TETO_POR_PERFIL[PERFIL_BATERIA_LONGA]
    teto = teto_do_orcamento(chave) if isinstance(chave, str) else None
    forca = f"{round(teto * 100)}% da força" if teto is not None else SEM_TETO
    frase = f"Vibração com {forca}"
    mais_fracos = [
        linha.nome.lower()
        for linha in LINHAS_DO_TETO
        if linha.tem_ponto and linha.nome != "Vibração"
    ]
    if mais_fracos:
        frase += f"; {_lista(mais_fracos)} mais fracos, sem apagar"
    pendentes = [linha.nome for linha in LINHAS_DO_TETO if not linha.tem_ponto]
    if not pendentes:
        return f"{frase}."
    return f"{frase}. {_lista(pendentes)} continuam como estão."


DICAS: dict[str, str] = {
    PERFIL_TUDO_LIGADO: (
        "Gatilho adaptativo, vibração no que o jogo pedir, barra de luz, "
        "giroscópio e touchpad."
    ),
    PERFIL_BATERIA_LONGA: _dica_da_bateria_longa(),
    # 05/09 já tinha trocado a mesma ideia por "o teto geral" em `aba_sistema`.
    PERFIL_EU_ESCOLHO: (
        "Nenhum teto geral: os ajustes de cada aba mandam, um por um."
    ),
}

DICAS_DO_CARTAO: dict[str, str] = {
    **DICAS,
    PERFIL_EU_ESCOLHO: "Nenhum teto: os ajustes de cada aba mandam neste controle.",
}

ECONOMIA_POR_PERFIL: dict[str, bool | None] = {
    PERFIL_TUDO_LIGADO: None,
    PERFIL_BATERIA_LONGA: True,
    PERFIL_EU_ESCOLHO: False,
}


def perfil_do_controle(teto_da_mesa: str | None, escolha: bool | None) -> str:
    """O botão aceso no cartão de um controle: a mesa, e depois o controle."""
    from hefesto_dualsense4unix.profiles.schema import economia_vale, mesa_em_economia

    if economia_vale(escolha, mesa_em_economia(teto_da_mesa)):
        return PERFIL_BATERIA_LONGA
    return PERFIL_EU_ESCOLHO if escolha is False else PERFIL_TUDO_LIGADO


def declaracao_do_perfil(uniq: str, perfil: str) -> dict[str, Any]:
    """O corpo do `machine.declare` do clique num perfil do cartão.

    A chave do controle e a validação são as do dono da economia
    (`schema.declaracao_da_economia`); aqui só se troca o valor pelo do perfil.
    `KeyError` num perfil que não existe, e `ValueError` num `uniq` sem chave.
    """
    from hefesto_dualsense4unix.profiles.schema import declaracao_da_economia

    valor = ECONOMIA_POR_PERFIL[perfil]
    corpo = declaracao_da_economia(uniq, True)
    return {"controles": {chave: {"economia": valor} for chave in corpo["controles"]}}


COLUNAS: tuple[str, ...] = ("O que", "Vem de", *(ROTULOS_DOS_PERFIS[p] for p in PERFIS))


def alcance_de_hoje() -> str:
    """A frase de apoio, DERIVADA de :data:`LINHAS_DO_TETO`."""
    com_ponto = [linha.nome for linha in LINHAS_DO_TETO if linha.tem_ponto]
    sem_ponto = [linha.nome for linha in LINHAS_DO_TETO if not linha.tem_ponto]
    alcanca = _lista(com_ponto) if com_ponto else "nada"
    if not sem_ponto:
        return f"Por enquanto o teto alcança {alcanca}."
    return (
        f"Por enquanto o teto alcança {alcanca} e nada mais. "
        f"{_lista(sem_ponto)} entram quando ganharem esse ponto."
    )


DICA = f"{DICA} {alcance_de_hoje()}"


def orcamento_em_vigor(host: Any = None) -> str | None:
    """A chave do orçamento que está GRAVADA — nunca a que espera o "Aplicar"."""
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
    """Qual dos três botões nasce afundado, lendo o que já está no disco."""
    gravado = orcamento_na_tela(host)
    if not isinstance(gravado, str):
        return None
    return PERFIL_POR_TETO.get(gravado)


def celula_do_teto(orcamento: str) -> str:
    """O que a coluna de um orçamento diz sobre a vibração."""
    teto = teto_do_orcamento(orcamento)
    if teto is None:
        return SEM_TETO
    return f"No máximo {round(teto * 100)}% da força"


def celula_do_perfil(perfil: str, linha: LinhaDoTeto) -> str:
    """A célula de um perfil numa linha da tabela."""
    if not linha.tem_ponto:
        return SEM_PONTO_DE_APLICACAO
    chave = TETO_POR_PERFIL.get(perfil)
    if chave is None:
        return CADA_ABA_MANDA
    if linha.nome == "Vibração":
        return celula_do_teto(chave)
    return celula_da_economia(chave, linha.nome)


def celula_da_economia(orcamento: str, nome: str) -> str:
    """O que a coluna de um orçamento diz sobre uma peça que não é a vibração."""
    from hefesto_dualsense4unix.profiles.schema import (
        A_ECONOMIA_EM_CADA_PECA,
        mesa_em_economia,
    )

    if not mesa_em_economia(orcamento):
        return SEM_TETO
    for peca in A_ECONOMIA_EM_CADA_PECA:
        if peca.nome == nome and peca.ponto_de_aplicacao:
            return peca.o_que_faz
    return SEM_PONTO_DE_APLICACAO


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura."""
    caixa.pack_start(_fileira_dos_perfis(host), False, False, 0)
    caixa.pack_start(_bloco_da_conta(host), False, False, 0)
    caixa.pack_start(_tabela_das_consequencias(), False, False, 0)


def _fileira_dos_perfis(host: Any) -> Any:
    """Os três perfis, deitados, com o que já está no disco marcado."""
    from gi.repository import Gtk

    seletor = SegmentedSelector()
    with contextlib.suppress(Exception):
        seletor.set_orientation(Gtk.Orientation.HORIZONTAL)
    seletor.set_items([(perfil, ROTULOS_DOS_PERFIS[perfil]) for perfil in PERFIS])
    seletor.set_tooltips(
        {perfil: f"{dica} {QUANDO_VALE}" for perfil, dica in DICAS.items()}
    )
    perfil = perfil_na_tela(host)
    if perfil in PERFIS:
        with contextlib.suppress(Exception):
            seletor.set_active_id(str(perfil))
    else:
        with contextlib.suppress(Exception):
            seletor.limpar_ativo()
    seletor.set_hexpand(False)
    seletor.connect("changed", lambda sel: _ao_escolher(host, sel))
    host._config_orcamento_seletor = seletor

    linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    linha.pack_start(seletor, False, False, 0)
    return linha


def _ao_escolher(host: Any, seletor: Any) -> None:
    """Acumula a escolha em `_maquina_pendente`. NÃO grava, NÃO manda IPC."""
    from hefesto_dualsense4unix.utils.maquina import fundir_declaracao

    escolha = seletor.get_active_id()
    if escolha not in TETO_POR_PERFIL:
        return
    teto = TETO_POR_PERFIL[str(escolha)]
    host._maquina_pendente = fundir_declaracao(
        getattr(host, "_maquina_pendente", None),
        {"orcamento": {"teto": teto}},
    )
    marcar = getattr(host, "_marcar_declaracao_por_aplicar", None)
    if marcar is not None:
        with contextlib.suppress(Exception):
            marcar()
    logger.info("config_orcamento_escolhido", perfil=escolha, teto=teto)


def _tabela_das_consequencias() -> Any:
    """A tabela "o que o perfil faz com cada coisa" — as cinco linhas."""
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
            grade.attach(
                _celula(SEM_PONTO_DE_APLICACAO), 2, indice, len(PERFIS), 1
            )
            continue
        for coluna, perfil in enumerate(PERFIS, start=2):
            grade.attach(_celula(celula_do_perfil(perfil, linha)), coluna, indice, 1, 1)
    return grade


def _celula(texto: str, *, cabecalho: bool = False) -> Any:
    """Uma célula da tabela: alinhada à esquerda, sem quebra."""
    from gi.repository import Gtk

    rotulo = Gtk.Label(label=_(texto))
    rotulo.set_xalign(0.0)
    if cabecalho:
        with contextlib.suppress(Exception):
            rotulo.get_style_context().add_class("dim-label")
    return rotulo


SEM_RESPOSTA_DO_DAEMON = (
    "Não sei quem está no rádio — o Hefesto não respondeu. Ligue-o na aba "
    "Sistema para ver a conta."
)

NINGUEM_NO_RADIO = "Nenhum controle no rádio agora — nada ocupando fatia."

TITULO_DA_CONTA = "Quanto do rádio cada adaptador já gasta"


def _bloco_da_conta(host: Any) -> Any:
    """A conta por adaptador, montada e pendurada no hospedeiro."""
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
        self._varrendo: frozenset[str] = frozenset()
        self._respondeu: bool | None = None
        self._pedido_em_voo = False
        self.caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.caixa.set_margin_top(8)
        self._desenhar()


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
            return
        if self._pedido_em_voo:
            return

        # O timeout é o MESMO de toda leitura de `daemon.state_full` da casa
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

    def _ler_a_varredura(self) -> None:
        """Quem está varrendo — UMA leitura por resposta do daemon, não por pintura."""
        leitor = getattr(self._host, "_desempenho_varredura", None)
        if leitor is not None:
            self._varrendo = frozenset()
            with contextlib.suppress(Exception):
                self._varrendo = frozenset(leitor() or ())
            return
        if (
            getattr(self._host, "_desempenho_leitor", None) is not None
            or getattr(self._host, "_mesa_leitor", None) is not None
        ):
            self._varrendo = frozenset()
            return
        self._varrendo = frozenset()
        with contextlib.suppress(Exception):
            from hefesto_dualsense4unix.integrations import varredura_do_radio

            self._varrendo = varredura_do_radio.varredura_recente().varrendo

    def _aplicar_estado(self, estado: dict[str, Any] | None) -> None:
        """Guarda os controles e os `uniq` com a ponte DE PÉ, e redesenha."""
        self._ler_a_varredura()
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


    def _planos(self) -> dict[str, plano_de_radio.PlanoDoAdaptador]:
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
        """`endereço -> nome dela`, quando o hospedeiro já conhece os dongles."""
        dongles = getattr(self._host, "_config_dongles", None) or ()
        with contextlib.suppress(Exception):
            return plano_de_radio.apelido_por_endereco(tuple(dongles))
        return {}

    def _desenhar(self) -> None:
        """As falas viram rótulos — menos as que a LEX-2 mandou para o hover."""
        with contextlib.suppress(Exception):
            for filho in list(self.caixa.get_children()):
                self.caixa.remove(filho)
        no_hover = plano_de_radio.frase_do_preco_por_controle()
        primeiro = True
        for texto in self.falas():
            if texto == no_hover:
                continue
            rotulo = rotulo_de_apoio(texto)
            if primeiro:
                with contextlib.suppress(Exception):
                    rotulo.set_tooltip_text(no_hover)
                primeiro = False
            self.caixa.pack_start(rotulo, False, False, 0)
        with contextlib.suppress(Exception):
            marcar_afordancias(self.caixa)
        with contextlib.suppress(Exception):
            self.caixa.show_all()

    def falas(self) -> tuple[str, ...]:
        """Todo o texto do bloco, na ordem — e é por aqui que o teste o lê."""
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

        ordem = plano_de_radio.ordem_de_redistribuicao(
            planos, varrendo=self._varrendo
        )
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
