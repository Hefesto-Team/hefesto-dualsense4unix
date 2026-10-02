"""Seção 1 da aba Configurações — um card por controle da mesa.

Aqui entra o que o aparelho não anuncia e o produto não deduz: o modo em que um
controle não-Sony foi ligado, o rótulo dos botões, e a cor do plástico quando a
leitura falha. Todo campo nasce em "não sei", e "não sei" é resposta válida.

TERRITÓRIO DE CONFIG-06. Quem trabalha nesta seção escreve AQUI — o título, a
dica e todo widget dela. O montador da aba (`mixin.py`) só cria a moldura e
chama `montar`; ele não sabe o que há dentro, e é assim que cinco seções
crescem sem se pisarem.

DE ONDE VEM CADA COISA NA TELA
-------------------------------

* **os controles adotados** — `daemon.state_full`, que é o único lugar onde o
  `player_slot` de um DualSense existe (`ipc_handlers.py:2328`); o
  `controller.list` devolve a lista sem ele;
* **os que o Hefesto só vê** — `controller.list {external: true}`, que já traz o
  `player_slot` deles resolvido pelo registro do daemon;
* **a cor do plástico** — lida DO APARELHO, pelos DOIS transportes, por
  `integrations/cor_do_plastico` (decisão T6). Antes desta leva a leitura vivia
  fora do aplicativo, em `scripts/ensaios/`, e toda linha "Cor:" nasceria em
  "Não sei" — inclusive nos controles no cabo, que o desenho mostra com a cor
  lida. **Quem decide se um nó pode responder é `cor_do_plastico`**, dono único
  do envelope de cada transporte — aqui não há `if` de barramento nenhum, e a
  razão está em :meth:`_PainelDosControles._perguntar_as_cores`;
* **o resto** — declaração dela, acumulada em `_maquina_pendente` e gravada
  pelo "Aplicar" do rodapé (`D-A4`: a aba é diferida, o clique só marca).

DUAS CHAMADAS, E NUNCA NUM TIQUE
---------------------------------

Os tiques desta casa são de 100 ms, 500 ms e 2 s. Enumerar o `/dev/input`
inteiro e sondar quem segura cada `hidraw` custa de 10 a 40 ms mais um
subprocesso (`ipc_handlers.py:561`), e nada disso muda entre dois quadros. A
leitura roda ao ENTRAR na aba, e só.
"""
from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

from hefesto_dualsense4unix.app.actions.config import secao_mesa
from hefesto_dualsense4unix.app.actions.config.moldura import (
    QUANDO_VALE,
    rotulo_de_apoio,
)
from hefesto_dualsense4unix.app.actions.external_controllers import (
    ID_DE_OUTRA_COR,
    chave_de_maquina,
    declaracoes_do_aparelho,
    external_key,
    marca_e_via,
    modo_deduzido,
    slot_of,
    via_do_controle,
)
from hefesto_dualsense4unix.app.alvo_de_edicao import alvo_de_edicao
from hefesto_dualsense4unix.app.fala_do_mapa import formata_pt_br
from hefesto_dualsense4unix.app.ipc_bridge import (
    call_async,
    identity_number_set,
    run_in_thread,
)
from hefesto_dualsense4unix.app.widgets.external_card import (
    DadosDoControle,
    ExternalCard,
)
from hefesto_dualsense4unix.integrations.cor_do_plastico import (
    cor_do_nome,
    ler_pelo_cabo,
    tom_para_a_borda,
)
from hefesto_dualsense4unix.utils.i18n import _
from hefesto_dualsense4unix.utils.logging_config import get_logger
from hefesto_dualsense4unix.utils.maquina import carregar_maquina, fundir_declaracao

logger = get_logger(__name__)

TITULO = "Os controles"

DICA: str | None = (
    "A borda de cada card é a cor do plástico daquele controle. O anel roxo "
    "por dentro marca qual está selecionado no cabeçalho da janela."
)

NOME_DO_REFRESH = "_refresh_config_controles"

COLUNAS = 3

_ESPACAMENTO = 10

FRASE_SEM_CONTROLE = (
    "Nenhum controle ligado agora. Conecte um pelo cabo ou pelo rádio e entre "
    "nesta aba de novo. Um controle ligado em modo D-input pode não aparecer "
    "aqui — esse caso ainda não foi medido nesta casa."
)

FRASE_SEM_RESPOSTA = (
    "O Hefesto está desligado, então não dá para saber quais controles estão "
    "ligados. Ligue-o na aba Sistema e entre nesta aba de novo."
)

TITULO_SEM_NUMERO = "Sem número ainda"


# A barra do DualSense por rádio nasce travada em ALGUMAS instâncias de conexão,
# 2. **o produto NÃO reconecta.** O botão PS é dela. Este arquivo derruba e
#    espera; `integrations/gesto_de_reconexao` não tem `reconectar` de propósito;

TEXTO_DO_BOTAO = "A luz não acende"

ESPERA_PELO_PS_S = 60

FRASE_APERTE_PS = "Aperte PS no controle"

TEXTO_CANCELAR = "Cancelar"

DICA_NO_RADIO = (
    "Derruba este controle do BT. Depois aperte PS nele para ele voltar — é "
    "a única cura conhecida para a barra que nasce travada. O Hefesto não "
    "reconecta sozinho: o botão PS é seu."
)

DICA_NO_CABO = (
    "Só vale no BT. Pelo USB a barra obedece — o defeito que este gesto "
    "cura não existe no USB, e por isso o botão fica apagado aqui."
)

# O AVISO DA MESA SUJA SAIU DA DICA — FRASES-E-DICAS-02, 13/09/2026. Aqui

ESPERA_PROCURANDO = "procurando"
ESPERA_VOLTOU = "voltou"
ESPERA_NAO_CAIU = "nao_caiu"  # (noqa-acento): chave de máquina
ESPERA_NAO_VOLTOU = "nao_voltou"  # (noqa-acento): chave de máquina
ESPERA_CANCELADA = "cancelada"

FRASE_NAO_CAIU = (
    "O controle não chegou a cair do rádio, então não houve o que reconectar. "
    "Ele continua pareado."
)


def frase_da_procura(restantes: int) -> str:
    """A linha que conta o tempo, do desenho: ``procurando…  38s``."""
    return f"procurando…  {max(0, int(restantes))}s"


def frase_nao_voltou(segundos: int) -> str:
    """O controle caiu e não voltou no tempo."""
    return (
        f"Não voltou em {int(segundos)}s. Ele continua pareado — aperte PS nele "
        "quando quiser."
    )


# moravam `FRASE_NASCEU_CONDENADO` e `frase_do_nascimento`
# anexo da dica do mesmo botão na aba 08. A ordem dela de 13/09
# O carimbo `nascimento` continua no `state_full`, para o diagnóstico.


def pode_derrubar(dados: Any) -> bool:
    """O botão é clicável neste card?

    Três condições, e a regra dela é a primeira: **no rádio**. As outras duas
    são o que o gesto precisa para existir — um DualSense adotado (o 8BitDo não
    tem barra) e um endereço para o BlueZ procurar.
    """
    return (
        bool(getattr(dados, "adotado", False))
        and not bool(getattr(dados, "no_cabo", False))
        and bool(getattr(dados, "uniq", ""))
    )


def dica_do_botao(dados: Any) -> str:
    """A dica do botão, e ela nunca é vazia."""
    if not pode_derrubar(dados):
        return DICA_NO_CABO
    return DICA_NO_RADIO


def uniq_normalizado(mac: Any) -> str:
    """``AA:BB:CC:00:00:01`` → ``aabbcc000001``; o que não é MAC → ``""``."""
    limpo = str(mac or "").replace(":", "").replace("-", "").strip().lower()
    if len(limpo) != 12 or any(c not in "0123456789abcdef" for c in limpo):
        return ""
    return limpo


def uniqs_no_radio() -> set[str] | None:
    """Os DualSense que estão no rádio AGORA. ``None`` = não consegui olhar.

    Só leitura de sysfs (`integrations/sinal_da_barra.instancias_dualsense`):
    nada aqui abre `/dev/hidraw`, roda subprocesso ou toca o aparelho — é o que
    a torna barata o bastante para um tique de um segundo.

    **A terceira resposta é a razão desta função existir.** Uma lista vazia
    porque `/sys` não pôde ser lido é indistinguível de uma lista vazia porque
    todos os controles caíram — e essa confusão faria a espera anunciar "caiu"
    sem nada ter caído. Por isso a raiz é conferida antes, e a ausência dela
    devolve ``None``, que a espera trata como "continua esperando".
    """
    try:
        import os

        from hefesto_dualsense4unix.integrations.sinal_da_barra import (
            RAIZ_UHID,
            instancias_dualsense,
        )
    except ImportError:
        return None
    if not os.path.isdir(RAIZ_UHID):
        return None
    try:
        vivas = instancias_dualsense()
    except OSError:
        return None
    return {
        uniq_normalizado(instancia.uniq)
        for instancia in vivas
        if instancia.no_radio and uniq_normalizado(instancia.uniq)
    }


class EsperaPeloPS:
    """A espera pelo botão PS de UM controle. Sem GTK, sem IPC, sem relógio."""

    def __init__(
        self,
        uniq: str,
        *,
        total_s: int = ESPERA_PELO_PS_S,
        sonda: Callable[[], set[str] | None] | None = None,
    ) -> None:
        self.alvo = uniq_normalizado(uniq)
        self.total_s = int(total_s)
        self.restantes = int(total_s)
        self.estado = ESPERA_PROCURANDO
        self.caiu = False
        self._sonda = sonda if sonda is not None else uniqs_no_radio

    @property
    def acabou(self) -> bool:
        return self.estado != ESPERA_PROCURANDO

    @property
    def porque(self) -> str:
        """A frase do fim, para a tela. Vazia enquanto ainda procura."""
        if self.estado == ESPERA_NAO_CAIU:
            return FRASE_NAO_CAIU
        if self.estado == ESPERA_NAO_VOLTOU:
            return frase_nao_voltou(self.total_s)
        return ""

    def cancelar(self) -> None:
        """Ela desistiu. NÃO reconecta — não existe reconexão neste produto."""
        if not self.acabou:
            self.estado = ESPERA_CANCELADA

    def tique(self) -> str:
        """Passa um segundo e devolve o estado. Idempotente depois do fim."""
        if self.acabou:
            return self.estado
        presentes = self._olhar()
        if presentes is not None:
            if self.alvo in presentes:
                if self.caiu:
                    self.estado = ESPERA_VOLTOU
                    return self.estado
            else:
                self.caiu = True
        self.restantes = max(0, self.restantes - 1)
        if self.restantes == 0:
            self.estado = ESPERA_NAO_VOLTOU if self.caiu else ESPERA_NAO_CAIU
        return self.estado

    def _olhar(self) -> set[str] | None:
        """A sonda, embrulhada: uma falha dela não pode derrubar a janela."""
        try:
            return self._sonda()
        except Exception:
            logger.debug("config_luz_sonda_falhou", exc_info=True)
            return None


#    <!-- noqa-acento: citação literal dela -->
#    derrubou a regra assim: *"esse aviso nao devia aparecer pq era  # (dela) noqa-acento
#    O que a declaração diz é *"o microfone deste controle chega ao PC pelo

TEXTO_DO_MIC = "Microfone"

DICA_MIC_NO_RADIO = (
    "Traz o microfone deste controle pelo rádio, como no PS5. Ele nasce "
    "desligado por privacidade: a ponte é um gesto seu, e vale só para este "
    "controle."
)

DICA_MIC_NO_CABO = (
    "Pelo cabo o canal deste microfone já existe: o PipeWire o publica sozinho, "
    "e o Hefesto não precisa de ponte para entregá-lo. A escolha fica gravada "
    "para quando este controle voltar ao rádio, onde a ponte é o que o traz."
)

#: :func:`tem_canal_de_captura`, e existe porque a `dica_do_microfone` passou a
#: pendura o interruptor em card que não é DualSense adotado —, e é justamente
DICA_MIC_SEM_CANAL = (
    "Este controle não tem canal de captura para o Hefesto entregar: o áudio do "
    "microfone vem tunelado num report HID da Sony, e só um DualSense adotado o "
    "carrega."
)

DICA_MIC_SEM_ENDERECO = (
    "Este controle não tem endereço fixo, então o Hefesto não tem como guardar "
    "a quem esta ponte pertence."
)


def _numero(valor: float) -> str:
    """Uma casa decimal, com vírgula — é assim que ela lê número nesta casa.

    Delega ao DONO ÚNICO (`app/fala_do_mapa.formata_pt_br`) desde 26/08/2026.
    Até então era uma segunda implementação da mesma regra, e a saída idêntica
    é o que fazia ninguém notar: no dia em que uma delas mudasse de
    arredondamento, esta seção e a célula do mapa passariam a dizer números
    diferentes sobre o mesmo fato. O nome local fica porque as quatro chamadas
    abaixo o usam e ele diz o que faz nesta seção.
    """
    return formata_pt_br(valor)


def frase_da_capacidade_do_mic() -> str:
    """Quanto do rádio um microfone ocupa. DERIVADA, nunca digitada."""
    from hefesto_dualsense4unix.integrations.radio_da_mesa import (
        HZ_AUDIO_COM_MIC,
        HZ_INPUT_COM_MIC,
        HZ_INPUT_SEM_MIC,
        SLOTS_POR_SEGUNDO,
    )

    total = HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC
    return (
        f"Com o microfone ligado, um controle no BT troca {_numero(HZ_INPUT_SEM_MIC)} "
        f"relatórios de entrada por segundo por {_numero(HZ_INPUT_COM_MIC)} mais "
        f"{_numero(HZ_AUDIO_COM_MIC)} quadros de áudio: {_numero(total)} das "
        f"{SLOTS_POR_SEGUNDO} fatias daquele adaptador. Quanto já está em uso "
        f'está na seção "{secao_mesa.TITULO}".'
    )


def tem_canal_de_captura(dados: Any) -> bool:
    """Este controle tem canal de captura? **A pergunta que substituiu "é cabo?"**

    04/09/2026, D-12: *"o botão é pra ligar o microfone e ele ser ouvido no
    canal específico dele"*. A pergunta certa nunca foi o transporte — é se
    existe um canal de captura DESTE controle a ligar.

    E o dono da resposta já existe e já sabe os dois transportes:
    `integrations/eleicao_de_microfone.EleitorDoMicrofone._canal_no_ar`, que diz
    com todas as letras — *"se existe (o caso do CABO, que publica sozinho),
    nada é pedido e nada é esperado (…) se não existe, pede uma vez e espera o
    PipeWire publicá-lo"*. Os dois transportes têm canal; o que muda é **quem o
    põe no ar**, e nenhum dos dois é uma recusa.

    Então a condição estrutural é a mesma nos dois: um DualSense **adotado** (a
    ponte é Opus tunelado em report HID da Sony, e o 8BitDo não tem isso) com um
    `uniq` pelo qual o daemon o case com o nó do sysfs. Nada de `pactl` aqui: um
    canal que está no ar AGORA é leitura de instante, e esta pergunta responde
    pelo aparelho, não pelo relógio.
    """
    return bool(getattr(dados, "adotado", False)) and bool(
        getattr(dados, "uniq", "")
    )


def pode_ligar_o_mic(dados: Any) -> bool:
    """O interruptor é clicável neste card?

    **ERAM QUATRO CONDIÇÕES E SÃO TRÊS — 04/09/2026.** A que saiu era
    `not no_cabo`, e ela não era uma exigência: era a `PonteMicBluetooth`
    usando o nome da capacidade (ver :data:`DICA_MIC_NO_CABO`). Ficam as que a
    escolha realmente precisa — :func:`tem_canal_de_captura` (o aparelho tem
    canal a ligar) e um `endereco` de doze hexa para a escolha ter **onde ser
    gravada** no `maquina.json`.

    NO CABO A DECLARAÇÃO NÃO ACENDE NADA, E ISSO NÃO É DEFEITO: o
    `bt_mic.alvos()` só enxerga nós de Bluetooth (`nos_dualsense_bluetooth`),
    então declarar pelo cabo é inerte HOJE e vale no dia em que este controle
    voltar ao rádio. É a mesma natureza durável que o "Nativo" sempre teve.
    """
    return tem_canal_de_captura(dados) and bool(getattr(dados, "endereco", ""))


def dica_do_microfone(dados: Any) -> str:
    """A dica do interruptor, e ela nunca é vazia."""
    if not tem_canal_de_captura(dados):
        return DICA_MIC_SEM_CANAL
    if not bool(getattr(dados, "endereco", "")):
        return DICA_MIC_SEM_ENDERECO
    return (
        DICA_MIC_NO_CABO
        if bool(getattr(dados, "no_cabo", False))
        else DICA_MIC_NO_RADIO
    )


class _BlocoDoMicrofone:
    """O interruptor de UM card. Dono de widgets, não subclasse de widget."""

    def __init__(
        self,
        dados: DadosDoControle,
        *,
        ligado: bool,
        ao_alternar: Callable[[str, bool], None],
    ) -> None:
        from gi.repository import Gtk

        self.dados = dados
        self._ao_alternar = ao_alternar
        self._mudo = False

        self.caixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.botao = Gtk.CheckButton(label=_(TEXTO_DO_MIC))
        self.botao.set_active(bool(ligado))
        self.botao.set_sensitive(pode_ligar_o_mic(dados))
        self.botao.set_tooltip_text(_(dica_do_microfone(dados)))
        self.botao.connect("toggled", self._ao_clicar)
        self.caixa.pack_start(self.botao, False, False, 0)

    def encaixar(self, card: Any) -> None:
        """Põe a caixa no corpo do card, ANTES do espaçador."""
        corpo = card.get_child()
        if corpo is None:
            return
        antes = corpo.get_children()
        corpo.pack_start(self.caixa, False, False, 0)
        with contextlib.suppress(Exception):
            corpo.reorder_child(self.caixa, max(0, len(antes) - 2))

    def _ao_clicar(self, botao: Any) -> None:
        if self._mudo:
            return
        self._ao_alternar(self.dados.chave, bool(botao.get_active()))


def montar(host: Any, caixa: Any) -> None:
    """Monta a seção dentro de `caixa` — a caixa interna da moldura."""
    painel = _PainelDosControles(host)
    painel.montar(caixa)
    setattr(host, NOME_DO_REFRESH, painel.reexaminar)


class _PainelDosControles:
    """A grade de cards e as duas leituras que a preenchem."""

    def __init__(self, host: Any) -> None:
        self._host = host
        self._caixa: Any = None
        self._estado: dict[str, Any] = {}
        self._cores: dict[str, Any] = {}
        self._cards: dict[str, Any] = {}
        self._luzes: dict[str, Any] = {}
        self._microfones: dict[str, Any] = {}
        self._mic_declarado: dict[str, bool] = {}


    def montar(self, caixa: Any) -> None:
        from gi.repository import Gtk

        self._caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa, False, False, 0)
        self._desenhar([])
        # não existe widget nenhum para hospedar a frase — que é exatamente o
        capacidade = rotulo_de_apoio(frase_da_capacidade_do_mic())
        with contextlib.suppress(Exception):
            capacidade.set_tooltip_text(_(QUANDO_VALE))
        caixa.pack_start(capacidade, False, False, 0)
        self.reexaminar()


    def reexaminar(self) -> None:
        """Relê a mesa e redesenha a grade. Engole a própria exceção."""
        try:
            leitor = getattr(self._host, "_controles_leitor", None)
            if leitor is not None:
                self._aplicar(leitor())
                return
            if self._e_bancada_de_retrato():
                self._desenhar([])
                return
            call_async(
                "daemon.state_full",
                {},
                self._chegou_o_estado,
                self._nao_respondeu,
                timeout_s=1.0,
            )
        except Exception:
            logger.warning("config_controles_reexame_falhou", exc_info=True)

    def _e_bancada_de_retrato(self) -> bool:
        """O hospedeiro é uma bancada de retrato, e não o produto?"""
        return getattr(self._host, "_mesa_leitor", None) is not None

    def _chegou_o_estado(self, resultado: Any) -> bool:
        """Guarda os adotados e vai buscar os que o Hefesto só vê."""
        self._estado = resultado if isinstance(resultado, dict) else {}
        call_async(
            "controller.list",
            {"external": True},
            self._chegou_o_inventario,
            self._nao_respondeu,
            # O inventário externo enumera TODOS os /dev/input e sonda quem
            timeout_s=3.0,
        )
        return False

    def _chegou_o_inventario(self, resultado: Any) -> bool:
        inventario = resultado if isinstance(resultado, dict) else {}
        self._aplicar(
            {
                "controllers": self._estado.get("controllers")
                or inventario.get("controllers")
                or [],
                "external": inventario.get("external") or [],
            }
        )
        return False

    def _nao_respondeu(self, erro: Exception) -> bool:
        logger.debug("config_controles_sem_resposta", erro=str(erro))
        self._desenhar(None)
        return False

    def _aplicar(self, payload: Any) -> None:
        """Traduz o que chegou em cards e redesenha."""
        bruto = payload if isinstance(payload, dict) else {}
        adotados = [c for c in _lista(bruto.get("controllers")) if c.get("connected")]
        externos = _lista(bruto.get("external"))
        self._desenhar(self._cards_da_mesa(adotados, externos))
        self._perguntar_as_cores(adotados)

    def _cards_da_mesa(
        self, adotados: list[dict[str, Any]], externos: list[dict[str, Any]]
    ) -> list[DadosDoControle]:
        """Os dados de cada card, ordenados pelo número de jogador."""
        declarado = self._declaracoes()
        alvo = alvo_de_edicao(self._host).uniq
        cards: list[DadosDoControle] = []
        for entrada in adotados:
            cards.append(
                self._card(
                    {**entrada, "bus": str(entrada.get("transport") or "")},
                    adotado=True,
                    # `player_slot` nulo (o registro do daemon ainda sem opinião)
                    slot=_inteiro(entrada.get("player_slot")),
                    declarado=declarado,
                    alvo=alvo,
                )
            )
        for indice, entrada in enumerate(externos):
            cards.append(
                self._card(
                    entrada,
                    adotado=False,
                    slot=slot_of(entrada, len(adotados), indice),
                    declarado=declarado,
                    alvo=alvo,
                )
            )
        return _sem_chave_repetida(_por_numero_de_jogador(cards))

    def _card(
        self,
        entrada: dict[str, Any],
        *,
        adotado: bool,
        slot: int | None,
        declarado: dict[str, Any],
        alvo: Any,
    ) -> DadosDoControle:
        chave = external_key(entrada)
        endereco = chave_de_maquina(entrada)
        meu = declarado.get(endereco or "", {})
        campos = dict(
            (nome, valor)
            for nome, _rotulo, valor in declaracoes_do_aparelho(
                entrada, adotado=adotado, declarado=meu
            )
        )
        if endereco:
            # A ponte de microfone não passa por `declaracoes_do_aparelho` (ela
            # não é campo do card, é gesto), então é lida do bruto aqui. `True`
            # e só `True`: ausência e `False` deixam a ponte no chão do mesmo
            # jeito, e é essa a razão de o desligar gravar "não sei".
            self._mic_declarado[endereco] = meu.get("microfone") is True
        uniq = str(entrada.get("uniq") or chave or "")
        lida = self._cores.get(uniq)
        cor_id, cor_livre, nome_da_cor = _cor_na_tela(campos.get("cor"), lida)
        return DadosDoControle(
            chave=chave,
            titulo=f"Jogador {slot}" if slot is not None else TITULO_SEM_NUMERO,
            subtitulo=marca_e_via(entrada, marca="Sony" if adotado else None),
            uniq=uniq,
            slot=slot,
            adotado=adotado,
            modo="" if adotado else modo_deduzido(entrada),
            cor_id=cor_id,
            cor_lida=nome_da_cor if not cor_id else "",
            cor_livre=cor_livre,
            tom=_tom_da_cor(campos.get("cor"), lida),
            botoes=campos.get("botoes"),
            no_cabo=via_do_controle(entrada) == "cabo",
            endereco=endereco or "",
            selecionado=bool(alvo) and alvo == uniq,
        )

    def _declaracoes(self) -> dict[str, Any]:
        """O que está no disco, com a pendência desta sessão por cima."""
        gravado: dict[str, Any] = {}
        with contextlib.suppress(Exception):
            gravado = {
                chave: valor.model_dump()
                for chave, valor in carregar_maquina().controles.items()
            }
        pendente = getattr(self._host, "_maquina_pendente", None)
        if isinstance(pendente, dict):
            controles = pendente.get("controles")
            if isinstance(controles, dict):
                gravado = fundir_declaracao(gravado, controles)
        return gravado

    def _perguntar_as_cores(self, adotados: list[dict[str, Any]]) -> None:
        """Pergunta a cor do plástico a cada DualSense NOVO da mesa.

        Uma vez por endereço e por sessão, porque a resposta não muda: a cor
        está no serial de fábrica. Sem esse cache, cada entrada na aba mandaria
        de novo um comando da família `0x80` para os quatro controles dela — e
        essa família é a mesma em que um par errado RESETA o aparelho. A trava
        de `integrations/cor_do_plastico` recusa qualquer par que não seja o do
        serial, mas não mandar é melhor que mandar e ser recusado.

        **O FILTRO DE CABO SAIU DAQUI — 03/09/2026.** A linha era
        ``transporte != "usb"``, e ela era NOSSA: o aparelho sempre respondeu.
        Ela é a IRMÃ do filtro que a ``ONDA-CONEXOES-11`` arrancou de
        ``cor_do_plastico.alvo_do_controle`` em 02/09 — a mesma razão herdada
        (*"por rádio o SET_FEATURE 0x80 devolve EIO"*, E7, 15/08/2026), que
        caiu em 27/08 quando se mediu que o EIO era a semente do NOSSO CRC, e
        de novo em 02/09 com o controle dela no rádio devolvendo o serial pelo
        produto. Arrancado o filtro de lá, este ficou de pé sozinho: a GTK
        continuava mostrando "Não sei" no card do controle de rádio enquanto a
        interface nova já mostrava o nome de fábrica dele.

        **E NENHUM SEGUNDO FILTRO ENTROU NO LUGAR, de propósito.** Quem decide
        se um nó pode responder é `cor_do_plastico.alvo_do_controle`, que já
        sabe o transporte e já escolhe o ENVELOPE por ele (nu no cabo, assinado
        com CRC de semente `0x53` no rádio) — e devolve `None` sem levantar
        quando não sabe, que é "Não sei" na tela. Um gate aqui seria um SEGUNDO
        dono da mesma pergunta, e é assim que dois donos se afastam.

        A célula do mapa que responde por esta leitura é
        :data:`ID_DA_COR_NO_MAPA`, e ela diz `sim` nos dois lados. Quem quiser
        o gate LIDO DO MAPA aqui — como faz a interface nova em
        `interface/mesa_viva.LeitorDeCor.pendentes`, que precisa dele porque
        pergunta num tique de 10 Hz — leia antes o custo medido em 03/09/2026:
        importar `app/fatos_do_mapa` em produção põe as chaves do dicionário
        gerado (`canal`, `aciona`, `existe`…) ao alcance da régua PLANA do
        portão `casa-sabe`, e uma promessa pública com um desses nomes passa a
        contar como alcançada sem ter chamador. Aqui não é preciso: a pergunta
        sai UMA VEZ por endereço e por sessão, e a trava confere o pedido byte
        a byte antes do `ioctl`.
        """
        leitor = getattr(self._host, "_cor_do_plastico_leitor", None)
        for entrada in adotados:
            uniq = str(entrada.get("uniq") or "")
            if not uniq or uniq in self._cores:
                continue
            self._cores[uniq] = None
            alvo = leitor if leitor is not None else ler_pelo_cabo
            run_in_thread(_pergunta_de_cor(uniq, alvo), self._chegou_a_cor)

    def _chegou_a_cor(self, resultado: Any) -> bool:
        """Repinta SÓ a borda do card que ganhou cor."""
        try:
            uniq, cor = resultado
        except (TypeError, ValueError):
            return False
        if cor is None:
            return False
        self._cores[uniq] = cor
        for card in self._cards.values():
            if card.dados.uniq != uniq or card.dados.cor_id:
                continue
            with contextlib.suppress(Exception):
                card.repintar_a_borda(tom_para_a_borda(cor.tom))
                card.repintar_o_nome_da_cor(cor.nome)
        return False


    def _desenhar(self, cards: list[DadosDoControle] | None) -> None:
        """A grade, ou a frase de que não há o que mostrar.

        `None` distingue "o Hefesto não respondeu" de "respondeu e a mesa está
        vazia". As duas frases são diferentes porque a ação dela é diferente:
        uma pede ligar o Hefesto, a outra pede conectar um controle.
        """
        if self._caixa is None:
            return
        from gi.repository import Gtk

        for bloco in self._luzes.values():
            with contextlib.suppress(Exception):
                bloco.encerrar()
        self._luzes = {}
        self._microfones = {}
        self._esvaziar(self._caixa)
        self._cards = {}
        if not cards:
            self._caixa.pack_start(
                rotulo_de_apoio(
                    FRASE_SEM_RESPOSTA if cards is None else FRASE_SEM_CONTROLE
                ),
                False,
                False,
                0,
            )
            self._caixa.show_all()
            return

        grade = Gtk.Grid()
        grade.set_column_spacing(_ESPACAMENTO)
        grade.set_row_spacing(_ESPACAMENTO)
        grade.set_column_homogeneous(True)
        grade.set_row_homogeneous(True)
        for indice, dados in enumerate(cards):
            card = ExternalCard(
                dados, ao_declarar=self._ao_declarar, ao_numerar=self._ao_numerar
            )
            self._cards[dados.chave] = card
            self._pendurar_a_luz(card, dados)
            self._pendurar_o_microfone(card, dados)
            grade.attach(card, indice % COLUNAS, indice // COLUNAS, 1, 1)
        self._caixa.pack_start(grade, False, False, 0)
        self._caixa.show_all()

    @staticmethod
    def _esvaziar(caixa: Any) -> None:
        for filho in caixa.get_children():
            caixa.remove(filho)
            filho.destroy()

    def _pendurar_a_luz(self, card: Any, dados: DadosDoControle) -> None:
        """Encaixa o bloco do gesto da luz dentro deste card, se ele couber.

        Só em DualSense adotado: o 8BitDo e o Pro não têm barra, e um botão
        "A luz não acende" num card sem luz é promessa que o produto não pode
        cumprir. **No cabo o botão VAI**, apagado — é a regra dela.
        """
        if not bool(getattr(dados, "adotado", False)) or not dados.uniq:
            return
        try:
            bloco = _BlocoDaLuz(
                dados,
                ao_derrubar=getattr(self._host, "_luz_derrubador", None)
                or _derrubar_o_controle,
                ao_voltar=self.reexaminar,
                agendar=getattr(self._host, "_luz_agendador", None),
                correr=getattr(self._host, "_luz_corredor", None),
            )
            bloco.encaixar(card)
        except Exception:
            logger.debug("config_luz_bloco_nao_montou", exc_info=True)
            return
        self._luzes[dados.chave] = bloco

    def _pendurar_o_microfone(self, card: Any, dados: DadosDoControle) -> None:
        """Encaixa o interruptor de microfone neste card.

        Só em DualSense adotado, e a razão é de protocolo, não de gosto: a ponte
        é Opus tunelado num report HID da Sony (`0x31`/`0x32`), e o 8BitDo, o Pro
        e o Xbox não têm isso. Um interruptor num card onde ele não pode ligar
        nada é promessa que o produto não cumpre.

        **No cabo o interruptor VAI, e ACESO — 04/09/2026, D-12.** Aqui estava
        escrito *"no cabo o interruptor VAI, apagado — é a regra dela, a mesma
        do botão da luz logo acima"*, e a comparação com o botão da luz é o que
        estava errado: aquele gesto é mesmo do rádio (é um repareamento), e o
        microfone não. Ver :func:`pode_ligar_o_mic`.
        """
        if not bool(getattr(dados, "adotado", False)) or not dados.uniq:
            return
        try:
            bloco = _BlocoDoMicrofone(
                dados,
                ligado=self._mic_declarado.get(dados.endereco, False),
                ao_alternar=self._ao_alternar_o_microfone,
            )
            bloco.encaixar(card)
        except Exception:
            logger.debug("config_mic_bloco_nao_montou", exc_info=True)
            return
        self._microfones[dados.chave] = bloco


    def _ao_alternar_o_microfone(self, chave: str, ligado: bool) -> None:
        """A ponte de microfone deste controle entra no rascunho.

        DESLIGAR grava `None`, não `False`: "nunca pedi" e "não quero" deixam a
        ponte no chão do mesmo jeito, e um `false` em disco seria um valor de
        catálogo para o silêncio — a porta pela qual o default entra disfarçado
        de escolha dela (a regra é do `utils/maquina.py`).

        Quem grava continua sendo o "Aplicar" do rodapé, e quem sobe a ponte é o
        daemon, no `machine.declare`. A janela NÃO fala com
        `integrations/dualsense_bt_audio` — o processo da janela não pode ter
        esse gesto ao alcance de um clique enquanto a posse do hidraw não for
        arbitrada — o susto de 16/08/2026 está no estudo `O-PS-PRESO`, em
        `docs/process/estudos/`.
        """
        self._ao_declarar(chave, "microfone", True if ligado else None)

    def _ao_declarar(self, chave: str, campo: str, valor: str | bool | None) -> None:
        """Acumula a escolha dela no rascunho. NÃO grava — quem grava é o rodapé."""
        card = self._cards.get(chave)
        endereco = "" if card is None else card.dados.endereco
        if not endereco:
            self._repintar(chave, campo, valor)
            return
        self._host._maquina_pendente = fundir_declaracao(
            getattr(self._host, "_maquina_pendente", None),
            {"controles": {endereco: {campo: valor}}},
        )
        marcar = getattr(self._host, "_marcar_declaracao_por_aplicar", None)
        if marcar is not None:
            with contextlib.suppress(Exception):
                marcar()
        logger.info("config_controle_declarado", campo=campo, tem_valor=valor is not None)
        self._repintar(chave, campo, valor)

    def _repintar(self, chave: str, campo: str, valor: str | bool | None) -> None:
        """A borda acompanha a escolha na hora — é o que o desenho promete."""
        if campo != "cor":
            return
        card = self._cards.get(chave)
        if card is None:
            return
        lida = self._cores.get(card.dados.uniq)
        with contextlib.suppress(Exception):
            card.repintar_a_borda(_tom_da_cor(valor if isinstance(valor, str) else None, lida))

    def _ao_numerar(self, uniq: str, numero: int) -> None:
        """Pede o número ao daemon e RELÊ quando ele confirmar."""

        def _fim(resultado: Any) -> bool:
            ok, motivo = resultado
            if not ok:
                logger.info("config_numero_recusado", motivo=motivo or "sem resposta")
            self.reexaminar()
            return False

        run_in_thread(lambda: identity_number_set(uniq, numero), _fim)


class _BlocoDaLuz:
    """Os dois estados do desenho dela, encaixados no corpo de um card."""

    def __init__(
        self,
        dados: DadosDoControle,
        *,
        ao_derrubar: Callable[[str], Any],
        ao_voltar: Callable[[], None],
        agendar: Callable[[Callable[[], bool]], Any] | None = None,
        correr: Callable[[Callable[[], Any], Callable[[Any], bool]], None] | None = None,
    ) -> None:
        from gi.repository import Gtk

        self.dados = dados
        self._ao_derrubar = ao_derrubar
        self._ao_voltar = ao_voltar
        self._agendar = agendar if agendar is not None else _agendar_um_segundo
        self._correr = correr if correr is not None else run_in_thread
        self._corpo: Any = None
        self._escondidos: list[Any] = []
        self._fonte: Any = None
        self._espera: EsperaPeloPS | None = None

        self.caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        self.botao = Gtk.Button(label=TEXTO_DO_BOTAO)
        self.botao.set_sensitive(pode_derrubar(dados))
        self.botao.set_tooltip_text(dica_do_botao(dados))
        self.botao.connect("clicked", self._ao_clicar)
        self.caixa.pack_start(self.botao, False, False, 0)

        self.aviso = _oculto(_apoio_do_bloco(f"▲ {FRASE_APERTE_PS}"))
        self.contagem = _oculto(_apoio_do_bloco(frase_da_procura(ESPERA_PELO_PS_S)))
        self.cancelar = _oculto(Gtk.Button(label=TEXTO_CANCELAR))
        self.cancelar.connect("clicked", self._ao_cancelar)
        self.recado = _oculto(_apoio_do_bloco(""))
        for widget in (self.aviso, self.contagem, self.cancelar, self.recado):
            self.caixa.pack_start(widget, False, False, 0)


    def encaixar(self, card: Any) -> None:
        """Põe a caixa no corpo do card, ANTES do espaçador."""
        corpo = card.get_child()
        if corpo is None:
            return
        antes = corpo.get_children()
        corpo.pack_start(self.caixa, False, False, 0)
        with contextlib.suppress(Exception):
            corpo.reorder_child(self.caixa, max(0, len(antes) - 2))
        self._corpo = corpo

    def encerrar(self) -> None:
        """Desarma o tique. Chamado antes de o card ser destruído."""
        if self._espera is not None:
            self._espera.cancelar()
        self._parar_o_tique()


    def _ao_clicar(self, _botao: Any) -> None:
        if self._espera is not None and not self._espera.acabou:
            return
        self._entrar_na_espera()
        alvo = str(self.dados.uniq)
        self._correr(lambda: self._ao_derrubar(alvo), self._chegou_o_gesto)

    def _ao_cancelar(self, _botao: Any) -> None:
        if self._espera is not None:
            self._espera.cancelar()
        self._parar_o_tique()
        self._sair_da_espera("")

    def _chegou_o_gesto(self, resultado: Any) -> bool:
        """O `Disconnect` respondeu. Só conta o tempo se o controle CAIU."""
        if getattr(resultado, "caiu", False):
            self._espera = EsperaPeloPS(self.dados.uniq)
            self._mostrar_a_contagem()
            self._fonte = self._agendar(self._tique)
            return False
        self._sair_da_espera(str(getattr(resultado, "porque", "")))
        return False

    def _tique(self) -> bool:
        """Um segundo. Devolve True enquanto o relógio deve continuar."""
        espera = self._espera
        if espera is None or espera.acabou:
            return False
        estado = espera.tique()
        if estado == ESPERA_PROCURANDO:
            self._mostrar_a_contagem()
            return True
        self._fonte = None
        if estado == ESPERA_VOLTOU:
            self._sair_da_espera("")
            with contextlib.suppress(Exception):
                self._ao_voltar()
            return False
        self._sair_da_espera(espera.porque)
        return False

    def _mostrar_a_contagem(self) -> None:
        espera = self._espera
        if espera is None:
            return
        with contextlib.suppress(Exception):
            self.contagem.set_text(frase_da_procura(espera.restantes))

    def _entrar_na_espera(self) -> None:
        """Estado 2 do desenho: some o que não interessa, entra o pedido do PS."""
        with contextlib.suppress(Exception):
            self.recado.hide()
            self.botao.set_no_show_all(True)
            self.botao.hide()
            for widget in (self.aviso, self.contagem, self.cancelar):
                widget.show()
        self._esconder_os_irmaos()

    def _sair_da_espera(self, recado: str) -> None:
        """Estado 1 do desenho, com o recado do que aconteceu (ou sem nenhum)."""
        self._espera = None
        with contextlib.suppress(Exception):
            for widget in (self.aviso, self.contagem, self.cancelar):
                widget.hide()
            self.botao.set_no_show_all(False)
            self.botao.show()
            if recado:
                self.recado.set_text(recado)
                self.recado.show()
        self._mostrar_os_irmaos()


    def _esconder_os_irmaos(self) -> None:
        """Esconde "Cor:" e "Jogador:" — o desenho dela mostra só o pedido."""
        self._escondidos = []
        if self._corpo is None:
            return
        for indice, filho in enumerate(self._corpo.get_children()):
            if indice < 2 or filho is self.caixa or _e_o_respiro(filho):
                continue
            with contextlib.suppress(Exception):
                if filho.get_visible():
                    self._escondidos.append(filho)
                    filho.set_no_show_all(True)
                    filho.hide()

    def _mostrar_os_irmaos(self) -> None:
        for filho in self._escondidos:
            with contextlib.suppress(Exception):
                filho.set_no_show_all(False)
                filho.show()
        self._escondidos = []

    def _parar_o_tique(self) -> None:
        if self._fonte is None:
            return
        with contextlib.suppress(Exception):
            from gi.repository import GLib

            GLib.source_remove(self._fonte)
        self._fonte = None


def _e_o_respiro(widget: Any) -> bool:
    """O espaçador do card: uma caixa vazia que se estica na vertical."""
    try:
        return not widget.get_children() and bool(widget.get_vexpand())
    except Exception:
        return False


def _oculto(widget: Any) -> Any:
    """Nasce escondido e SOBREVIVE ao `show_all` da seção."""
    with contextlib.suppress(Exception):
        widget.set_no_show_all(True)
        widget.hide()
    return widget


def _apoio_do_bloco(texto: str) -> Any:
    """Um rótulo de apoio, quebrando linha — as frases do fim são compridas."""
    rotulo = rotulo_de_apoio(texto)
    with contextlib.suppress(Exception):
        rotulo.set_line_wrap(True)
    return rotulo


def _agendar_um_segundo(passo: Callable[[], bool]) -> Any:
    """O relógio de verdade: um tique por segundo no laço da janela."""
    from gi.repository import GLib

    return GLib.timeout_add_seconds(1, passo)


def _derrubar_o_controle(uniq: str) -> Any:
    """Chama o gesto de verdade. Import tardio: a seção monta sem D-Bus."""
    from hefesto_dualsense4unix.integrations.gesto_de_reconexao import desconectar

    return desconectar(uniq)


def _sem_chave_repetida(cards: list[DadosDoControle]) -> list[DadosDoControle]:
    """Garante que dois cards nunca respondam pela mesma chave."""
    from dataclasses import replace

    vistas: set[str] = set()
    saida: list[DadosDoControle] = []
    for indice, dados in enumerate(cards):
        chave = dados.chave
        if chave in vistas:
            chave = f"{dados.chave}#{indice}"
        vistas.add(chave)
        saida.append(dados if chave == dados.chave else replace(dados, chave=chave))
    return saida


def _por_numero_de_jogador(
    cards: list[DadosDoControle],
) -> list[DadosDoControle]:
    """Ordena os cards por jogador, e põe quem não tem número no fim."""
    return sorted(
        cards,
        key=lambda card: (card.slot is None, card.slot if card.slot else 0),
    )


ID_DA_COR_NO_MAPA = "identidade.cor_do_aparelho@dualsense"


def _pergunta_de_cor(
    uniq: str, ler: Callable[[str], Any]
) -> Callable[[], tuple[str, Any]]:
    """Fecha o endereço e o leitor numa função de zero argumento."""

    def _perguntar() -> tuple[str, Any]:
        return uniq, ler(uniq)

    return _perguntar


def _lista(valor: Any) -> list[dict[str, Any]]:
    if not isinstance(valor, list):
        return []
    return [item for item in valor if isinstance(item, dict)]


def _inteiro(valor: Any) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _cor_na_tela(declarada: str | None, lida: Any) -> tuple[str, str, str]:
    """`(id a marcar na lista, texto do campo livre, nome a mostrar)`."""
    if declarada:
        conhecida = cor_do_nome(declarada)
        if conhecida is not None:
            return conhecida.codigo, "", conhecida.nome
        return ID_DE_OUTRA_COR, declarada, declarada
    return "", "", "" if lida is None else lida.nome


def _tom_da_cor(declarada: str | None, lida: Any) -> str:
    """O hexa da borda, já clareado. "" quando ninguém sabe a cor."""
    if declarada:
        conhecida = cor_do_nome(declarada)
        return "" if conhecida is None else tom_para_a_borda(conhecida.tom)
    if lida is None:
        return ""
    return tom_para_a_borda(lida.tom)
