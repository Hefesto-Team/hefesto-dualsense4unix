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
  `player_slot` de um DualSense existe (`ipc_handlers.py:3058`); o
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
subprocesso (`ipc_handlers.py:3679`), e nada disso muda entre dois quadros. A
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

#: O título como ela o lê na tela.
TITULO = "Os controles"

#: A dica do título, palavra por palavra como saiu do desenho aprovado
#: (`TOOLTIPS.md`). Ela não se reescreve na hora.
DICA: str | None = (
    "A borda de cada card é a cor do plástico daquele controle. O anel roxo "
    "por dentro marca qual está selecionado no cabeçalho da janela."
)

#: O nome que o `_REFRESH_POR_ABA` de `app/app.py` procura para reler a mesa ao
#: ENTRAR na aba. Ele é pendurado no hospedeiro por `montar`, como o
#: `_reexaminar_a_mesa` de CONFIG-02 e o `_refresh_saude_da_mesa` de CONFIG-09.
NOME_DO_REFRESH = "_refresh_config_controles"

#: Quantas colunas de card a grade tem. FIXO, e não `Gtk.FlowBox`: o FlowBox
#: decide as colunas pela largura que RECEBE, o rolador lhe entrega a MÍNIMA, e
#: o resultado medido em `segmented_selector.py:214-231` foi 606px de altura
#: empilhada virando o piso de TODAS as abas do notebook.
#:
#: Três, e não cinco como no desenho: um card pede 208px de largura mínima, e a
#: janela abre com 1180px sem rolagem horizontal. Cinco cards lado a lado com a
#: lista de cor de três colunas dentro não cabem — e o portão
#: `test_config_01_a_aba_nasce_vazia::test_a_aba_montada_cabe_na_largura_da_janela`
#: reprova antes de a tela existir. Com três colunas, a mesa de cinco vira duas
#: fileiras, e a altura igual continua valendo (é o `row_homogeneous`).
COLUNAS = 3

#: Espaço entre cards, o mesmo `--sp-3` do desenho.
_ESPACAMENTO = 10

#: O que a seção diz quando não há controle nenhum.
#:
#: A segunda frase é a resposta on-screen à medição 3 do aceite desta sprint
#: ("em modo D-input, o Hefesto vê o controle?"), cuja previsão é NÃO com grau
#: MÉDIO. Enquanto a medição não acontece, o estado vazio precisa ser
#: *"não estou vendo nada e sei por quê"* — que é entrega, não falha.
FRASE_SEM_CONTROLE = (
    "Nenhum controle ligado agora. Conecte um pelo cabo ou pelo rádio e entre "
    "nesta aba de novo. Um controle ligado em modo D-input pode não aparecer "
    "aqui — esse caso ainda não foi medido nesta casa."
)

#: O que a seção diz quando o Hefesto não respondeu.
FRASE_SEM_RESPOSTA = (
    "O Hefesto está desligado, então não dá para saber quais controles estão "
    "ligados. Ligue-o na aba Sistema e entre nesta aba de novo."
)

#: Título de um card sem número. "Jogador —" leria como defeito; esta frase diz
#: a mesma coisa e diz que é normal (é o estado dos primeiros segundos, enquanto
#: o registro do daemon ainda não opinou).
TITULO_SEM_NUMERO = "Sem número ainda"


# ---------------------------------------------------------------------------
# O gesto da luz — "A luz não acende"
# ---------------------------------------------------------------------------
#
# A barra do DualSense por rádio nasce travada em ALGUMAS instâncias de conexão,
# e a única cura conhecida é derrubar a conexão e deixar a pessoa apertar PS
# (medido em 12/08 e de novo em 22/08/2026, com o olho dela). O `Disconnect` do
# BlueZ tinha ZERO chamadores em `src/` — a cura estava escrita e nunca ligada.
#
# TRÊS REGRAS DELA, e as três estão escritas em código aqui:
#
# 1. *"sempre visível mas só acionável quando tiver no rádio"* — o botão existe
#    no card do cabo também, apagado, com a dica dizendo por quê. Botão que SOME
#    ensina que a tela é instável;
# 2. **o produto NÃO reconecta.** O botão PS é dela. Este arquivo derruba e
#    espera; `integrations/gesto_de_reconexao` não tem `reconectar` de propósito;
# 3. **o fim da espera diz o que aconteceu**, e "não voltou" nunca é dito como
#    "não deu certo": o controle continua PAREADO, e a frase precisa dizê-lo ou
#    a pessoa acha que perdeu o pareamento.
#
# O QUE ESTE BOTÃO NÃO PROMETE: que a barra vai acender. Ninguém nesta casa
# consegue LER a lâmpada — `multi_intensity` é a memória da última escrita pela
# classe LED, e leu `[0 255 0]` com a barra apagada E com ela verde (16/08). Por
# isso nenhuma frase daqui diz "acesa" nem "apagada".

#: O rótulo do botão em repouso — a queixa dela, não o remédio. Quem vê a barra
#: apagada procura "a luz não acende", nunca "reiniciar a conexão Bluetooth".
TEXTO_DO_BOTAO = "A luz não acende"

#: Quanto tempo o card espera o botão PS depois de derrubar o controle.
#:
#: Sessenta segundos porque o gesto tem DUAS pernas humanas — pegar o controle e
#: apertar PS — e porque o custo de esperar demais é uma linha na tela, enquanto
#: o de esperar de menos é dizer "não voltou" para um controle que voltou.
ESPERA_PELO_PS_S = 60

#: O aviso do estado de espera, palavra por palavra como no desenho aprovado.
FRASE_APERTE_PS = "Aperte PS no controle"

#: O rótulo do botão que desiste da espera. Cancelar NÃO reconecta — não existe
#: reconexão neste produto.
TEXTO_CANCELAR = "Cancelar"

#: A dica do botão quando ele PODE ser clicado.
DICA_NO_RADIO = (
    "Derruba este controle do rádio. Depois aperte PS nele para ele voltar — é "
    "a única cura conhecida para a barra que nasce travada. O Hefesto não "
    "reconecta sozinho: o botão PS é seu."
)

#: A dica do botão apagado. Ela diz POR QUE está apagado, que é a metade que
#: falta em todo botão insensível desta casa.
DICA_NO_CABO = (
    "Só vale no rádio. Pelo cabo a barra obedece — o defeito que este gesto "
    "cura não existe no cabo, e por isso o botão fica apagado aqui."
)

#: O que se acrescenta à dica quando outro programa está segurando nó de
#: controle AGORA. É AVISO, nunca trava: a mesa dela vive com a Steam aberta, e
#: o experimento que fecha a célula do mapa PRECISA do gesto com ela aberta.
AVISO_DA_MESA_SUJA = (
    "Atenção: outro programa está segurando controle agora, e nessa condição a "
    "conexão nova nasce travada igual. Feche-o antes para o gesto valer."
)

#: Os quatro fins possíveis da espera. Nenhum é acento — são chaves de máquina.
ESPERA_PROCURANDO = "procurando"
ESPERA_VOLTOU = "voltou"
ESPERA_NAO_CAIU = "nao_caiu"  # (noqa-acento): chave de máquina
ESPERA_NAO_VOLTOU = "nao_voltou"  # (noqa-acento): chave de máquina
ESPERA_CANCELADA = "cancelada"

#: O controle nunca sumiu do rádio — então o `Disconnect` não surtiu efeito, e
#: mandar a pessoa apertar PS seria gastar o gesto dela à toa. É o remédio do
#: ELO-MUDO-01 aplicado aqui: o produto respondeu pelo TRANSPORTE (o `busctl`
#: devolveu zero) e o EFEITO não veio.
FRASE_NAO_CAIU = (
    "O controle não chegou a cair do rádio, então não houve o que reconectar. "
    "Ele continua pareado."
)


def frase_da_procura(restantes: int) -> str:
    """A linha que conta o tempo, do desenho: ``procurando…  38s``."""
    return f"procurando…  {max(0, int(restantes))}s"


def frase_nao_voltou(segundos: int) -> str:
    """O controle caiu e não voltou no tempo.

    A segunda oração é obrigatória e não é gentileza: sem ela a pessoa lê "não
    voltou" como "perdi o pareamento" e vai reparear um controle que está
    pareado.
    """
    return (
        f"Não voltou em {int(segundos)}s. Ele continua pareado — aperte PS nele "
        "quando quiser."
    )


#: A razão de reserva, quando o daemon condena a conexão e não manda a frase.
#: Nunca diz "acesa" nem "apagada" — ninguém nesta casa consegue LER a lâmpada,
#: e há teste que reprova se alguma frase daqui passar a dizer.
FRASE_NASCEU_CONDENADO = (
    "Esta conexão nasceu com outro programa segurando o controle, e nessa "
    "condição a barra não obedece."
)


def frase_do_nascimento(nascimento: Any) -> str | None:
    """A razão que o card mostra; ``None`` = o card não diz nada.

    SINAL-NO-NASCIMENTO-01/E2. O botão da cura existe desde 22/08 e não dizia
    POR QUE oferecia a cura. A razão vem PRONTA do daemon
    (`integrations/sinal_da_barra.Carimbo.porque`, no campo `nascimento` do
    payload por controle): a tela não reescreve diagnóstico, e é isso que
    mantém uma frase só para as duas superfícies.

    **Só a condenação fala.** Os outros três casos calam, e cada um por um
    motivo medido:

    * ``None`` — o daemon não carimbou esta conexão. Ausência NÃO é inocência,
      e também não é acusação: a tela não afirma o que ninguém mediu;
    * ``limpa`` — dizer "nasceu bem" em todo card é ruído crônico, e ruído
      crônico ensina a ignorar o card no dia em que ele acusa;
    * ``nao_sei`` — é o terceiro estado honesto do módulo (Modo Nativo, diário
      rotacionado). Um alarme sem medição atrás treina a pessoa a ignorar
      alarmes, que é o defeito que a `_mesa_suja` já evita logo acima.
    """
    if not isinstance(nascimento, dict):
        return None
    if not bool(nascimento.get("pede_reconexao")):
        return None
    porque = str(nascimento.get("porque") or "").strip()
    return f"▲ {porque or FRASE_NASCEU_CONDENADO}"


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


def dica_do_botao(dados: Any, mesa_suja: bool = False) -> str:
    """A dica do botão, e ela nunca é vazia.

    No cabo diz por que está apagado; no rádio diz o que o clique faz e o que
    ele NÃO faz. Com a mesa suja, o aviso vem junto — anexado, nunca no lugar:
    a pessoa continua precisando saber o que o botão faz.
    """
    if not pode_derrubar(dados):
        return DICA_NO_CABO
    return f"{DICA_NO_RADIO} {AVISO_DA_MESA_SUJA}" if mesa_suja else DICA_NO_RADIO


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
    """A espera pelo botão PS de UM controle. Sem GTK, sem IPC, sem relógio.

    Quem chama dá o tique (uma vez por segundo, na janela) e recebe o estado.
    Fazer assim é o que torna a espera inteira exercitável em teste puro — e a
    espera é justamente onde mora a mentira fácil.

    A MENTIRA QUE ESTA CLASSE EXISTE PARA IMPEDIR
    ---------------------------------------------
    No instante do clique o controle AINDA ESTÁ no sysfs — o `Disconnect` foi
    pedido, e o nó leva um tempo para sumir. Uma espera que só perguntasse "ele
    está aí?" responderia **voltou** no primeiro tique, sem nada ter acontecido:
    o card piscaria e a pessoa nunca apertaria PS.

    Por isso são DOIS marcos, nesta ordem: primeiro é preciso VER O CONTROLE
    SUMIR, e só depois vê-lo voltar. É a mesma disciplina do ELO-MUDO-01 — não
    tratar ausência de notícia como notícia de sucesso.
    """

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
        #: Já vi este controle SUMIR? Sem isto, "voltou" é chute.
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
        except Exception:  # best-effort por contrato: a sonda não derruba a janela
            logger.debug("config_luz_sonda_falhou", exc_info=True)
            return None


# ---------------------------------------------------------------------------
# O gesto do microfone — a ponte por rádio, POR CONTROLE (QUATRO-MICROFONES-01)
# ---------------------------------------------------------------------------
#
# O campo `bt_mic_enabled` era lido por três lugares e escrito por NENHUM: a
# ponte de microfone por Bluetooth só subia por `HEFESTO_DUALSENSE4UNIX_BT_MIC=1`
# no ambiente do daemon. É a família A-CASA-SABE-E-O-PRODUTO-NAO-FAZ, e este
# interruptor é a porta que faltava.
#
# AS QUATRO REGRAS DELA, de 22/08/2026, e as quatro estão em código aqui:
#
# 1. **POR CONTROLE.** Textual: *"por controle"*. Um por card, quatro
#    independentes. Não existe chave de mesa inteira, e o daemon acompanha: o
#    gate deixou de ser um `bool` e passou a ser um CONJUNTO de `uniq`
#    (`daemon/subsystems/bt_mic.py`, que explica por que o `bool` não servia);
# 2. **nasce desligado**, sempre. Ausência é desligado, e é por isso que
#    desligar volta a "não sei" em vez de gravar um `false`;
# 3. **sempre visível, e acionável nos DOIS transportes** — REESCRITA em
#    04/09/2026 (D-12). Ela dizia *"só acionável no rádio"*, e a queixa 15 dela
#    <!-- noqa-acento: citação literal dela -->
#    derrubou a regra assim: *"esse aviso nao devia aparecer pq era  # (dela) noqa-acento
#    pra funcionar em ambos ne"*. O CSV desta casa já dizia o mesmo —
#    `audio.microfone` tem `cabo_aciona=sim` e `radio_aciona=parcial`
#    (`docs/data/mapa-controles.csv`): quem é PARCIAL é o rádio. O que "não vale
#    no cabo" nunca foi a feature — é uma IMPLEMENTAÇÃO dela, a
#    `PonteMicBluetooth`, e a frase deu à ponte o nome da capacidade.
#    O que a declaração diz é *"o microfone deste controle chega ao PC pelo
#    canal dele"*, e ela é DURÁVEL: no cabo ela não sobe ponte nenhuma (o
#    `bt_mic.alvos()` só enxerga nós de Bluetooth) e fica escrita para quando
#    este controle voltar ao rádio. Botão que SOME ensina que a tela é instável;
#    botão que RECUSA no transporte em que a feature é mais forte ensina pior;
# 4. **capacidade, não advertência.** A frase de preço que existia foi derrubada
#    por ela no mesmo dia — comparava 170 Hz de rádio com um espelho de 250 Hz
#    que é a taxa NATIVA DO CABO. O que fica ao lado do interruptor é quanto do
#    rádio o microfone ocupa, derivado das constantes do medidor.

#: O rótulo do interruptor. Uma palavra, porque o card tem 208px de largura
#: mínima e as outras linhas dele já são "Modo:", "Botões:", "Cor:" e "Jogador:".
TEXTO_DO_MIC = "Microfone"

#: A dica quando o interruptor PODE ser clicado. Ela diz o que o clique faz,
#: quanto custa e que a escolha é dela — nunca "não faça isto".
DICA_MIC_NO_RADIO = (
    "Traz o microfone deste controle pelo rádio, como no PS5. Ele nasce "
    "desligado por privacidade: a ponte é um gesto seu, e vale só para este "
    "controle."
)

#: A dica no CABO. **Ela era uma RECUSA e virou INFORMAÇÃO — 04/09/2026, D-12.**
#:
#: O que ela dizia, palavra por palavra: *"Só vale no rádio. Pelo cabo o
#: microfone deste controle é uma placa de som USB e não passa por esta ponte —
#: ele já funciona sem ela."* Três coisas erradas numa frase só:
#:
#: 1. **"Só vale no rádio" está de cabeça para baixo.** `audio.microfone` é
#:    `cabo_aciona=sim` e `radio_aciona=parcial` no `mapa-controles.csv`. A
#:    frase promovia o transporte fraco e recusava o forte;
#: 2. **deu à PONTE o nome da CAPACIDADE.** O que não vale no cabo é a
#:    `PonteMicBluetooth`, não o microfone;
#: 3. **"ele já funciona sem ela" é falso** sob o conceito dela: pelo cabo o
#:    canal existe mas nasce PARADO — `SUSPENDED`, medido em
#:    `daemon/subsystems/bt_mic.py`. Existir não é ser ouvido.
#:
#: A que fica diz o que o transporte muda de verdade — a ROTA, nunca se o
#: microfone existe — e não recusa nada: no cabo o interruptor está ACESO.
DICA_MIC_NO_CABO = (
    "Pelo cabo o canal deste microfone já existe: o PipeWire o publica sozinho, "
    "e o Hefesto não precisa de ponte para entregá-lo. A escolha fica gravada "
    "para quando este controle voltar ao rádio, onde a ponte é o que o traz."
)

#: A dica de quem NÃO TEM canal de captura a ligar — 04/09/2026. Ela nasce com
#: :func:`tem_canal_de_captura`, e existe porque a `dica_do_microfone` passou a
#: ter dois motivos de recusa e não podia responder aos dois com a frase do
#: endereço: uma frase só mandaria a pessoa procurar endereço onde o problema é
#: o aparelho. Na GUI ela não chega à tela — `_pendurar_o_microfone` nem
#: pendura o interruptor em card que não é DualSense adotado —, e é justamente
#: por isso que ela precisa existir: o dia em que alguém pendurar, a frase está
#: pronta em vez de mentir sobre o motivo.
DICA_MIC_SEM_CANAL = (
    "Este controle não tem canal de captura para o Hefesto entregar: o áudio do "
    "microfone vem tunelado num report HID da Sony, e só um DualSense adotado o "
    "carrega."
)

#: A dica do interruptor apagado por falta de endereço. Sem os doze hexa não há
#: chave no `maquina.json`, e o daemon não teria como saber de quem é a ponte.
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
    """Quanto do rádio um microfone ocupa. DERIVADA, nunca digitada.

    Os quatro números saem das constantes do medidor
    (`integrations/radio_da_mesa`), que é o mesmo lugar de onde a barra de
    "Rádio em uso" tira os dela. Digitá-los aqui criaria a segunda verdade — e a
    primeira vez que alguém remedisse o A/B, a tela e a barra passariam a dizer
    coisas diferentes sobre o mesmo fato.

    É CAPACIDADE, não advertência: diz o que o rádio carrega, e a pergunta
    "cabe?" quem responde é a barra da seção vizinha.

    **O NOME DA SEÇÃO É LIDO, nunca digitado — corrigido em 26/08/2026.** Esta
    frase mandava a pessoa procurar uma seção chamada "A mesa"; a LEX-1 renomeou
    a seção para o léxico dela no mesmo dia, e a frase passou a apontar para um
    nome que não existe mais na tira. Quem lesse procuraria "A mesa" e leria
    "Conexões" — a tela mandando para um lugar que ela mesma renomeou. Ler o
    ``TITULO`` faz o ponteiro seguir o renomeio de graça, para sempre.
    """
    from hefesto_dualsense4unix.integrations.radio_da_mesa import (
        HZ_AUDIO_COM_MIC,
        HZ_INPUT_COM_MIC,
        HZ_INPUT_SEM_MIC,
        SLOTS_POR_SEGUNDO,
    )

    total = HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC
    return (
        f"Com o microfone ligado, um controle no rádio troca {_numero(HZ_INPUT_SEM_MIC)} "
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
    """A dica do interruptor, e ela nunca é vazia.

    **OS DOIS MOTIVOS DE ESTAR APAGADO MUDARAM DE PAR — 04/09/2026.** Eram *"no
    cabo não FAZ FALTA, sem endereço não TEM ONDE ser guardada"*; o do cabo caiu
    com a D-12 — no cabo o interruptor está ACESO, e o que a dica faz ali é
    INFORMAR por onde o canal vem, não recusar. O par que sobrou é **não tem
    canal** e **não tem onde guardar**, e cada um continua com a frase dele:
    responder aos dois com uma só mandaria a pessoa procurar endereço onde o
    problema é o aparelho.

    E as duas perguntas são feitas na ORDEM em que elas mandam: sem canal, o
    endereço não interessa.
    """
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
    """O interruptor de UM card. Dono de widgets, não subclasse de widget.

    Mesma disciplina do `_BlocoDaLuz` logo abaixo, e pela mesma razão: assim
    `app/widgets/external_card.py` continua sem saber que este gesto existe.

    E o gesto é DIFERIDO como o resto da seção (`D-A4`): o clique acumula em
    `host._maquina_pendente` e quem grava é o "Aplicar" do rodapé. Não é
    detalhe de implementação — é o que a frase `QUANDO_VALE`, no pé da seção,
    promete à pessoa que clicou. Gravar na hora aqui faria a seção mentir em
    uma linha e dizer a verdade nas outras quatro.
    """

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
        # O valor inicial entra ANTES do `connect`, como todo campo deste card:
        # `set_active` EMITE "toggled", e com o handler já ligado a abertura da
        # janela declararia sozinha o que ninguém escolheu.
        self.botao.set_active(bool(ligado))
        self.botao.set_sensitive(pode_ligar_o_mic(dados))
        self.botao.set_tooltip_text(_(dica_do_microfone(dados)))
        self.botao.connect("toggled", self._ao_clicar)
        self.caixa.pack_start(self.botao, False, False, 0)

    def encaixar(self, card: Any) -> None:
        """Põe a caixa no corpo do card, ANTES do espaçador.

        Mesma conta do `_BlocoDaLuz.encaixar`, e por isso a ordem entre os dois
        é a ordem em que a seção os pendura: quem entra depois fica embaixo.
        """
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
    """Monta a seção dentro de `caixa` — a caixa interna da moldura.

    `host` é o `HefestoApp`: dele vêm `_get` (widgets do Glade) e o que os
    outros mixins já penduraram. `caixa` é um `Gtk.Box` vertical, com as
    margens da casa já aplicadas.

    Contrato, e ele vale para as cinco: **nunca levantar**. Uma seção que
    falha ao montar não pode derrubar a aba, e uma aba que falha não pode
    derrubar a janela. Quem chama já embrulha em `contextlib.suppress`, mas a
    tolerância começa aqui.

    O último gesto pendura `_refresh_config_controles` no hospedeiro. Ele
    NASCE aqui e não no `mixin.py` pela mesma razão do refresher da mesa: o
    montador da aba não conhece uma linha do que há dentro de nenhuma seção.
    """
    painel = _PainelDosControles(host)
    painel.montar(caixa)
    setattr(host, NOME_DO_REFRESH, painel.reexaminar)


class _PainelDosControles:
    """A grade de cards e as duas leituras que a preenchem.

    Uma instância por montagem. A grade mora dentro de uma caixa que FICA:
    reexaminar esvazia a caixa e a preenche de novo, em vez de mexer na página —
    assim a ordem dos filhos da seção nunca muda e a tela não pula.
    """

    def __init__(self, host: Any) -> None:
        self._host = host
        self._caixa: Any = None
        self._estado: dict[str, Any] = {}
        #: `{uniq: CorDoPlastico | None}` — `None` gravado é "já perguntei e o
        #: aparelho não respondeu". Sem guardar a falha, cada entrada na aba
        #: mandaria de novo o comando de fábrica para o mesmo controle.
        self._cores: dict[str, Any] = {}
        #: Os cards vivos, por chave, para repintar a borda sem redesenhar tudo
        #: (redesenhar tira o foco de quem está digitando no campo livre).
        self._cards: dict[str, Any] = {}
        #: Os blocos do gesto da luz, por chave do card.
        self._luzes: dict[str, Any] = {}
        #: Os interruptores de microfone, por chave do card.
        self._microfones: dict[str, Any] = {}
        #: `{endereco: True}` para quem tem a ponte de microfone declarada. Vive
        #: separado do `DadosDoControle` de propósito: o card
        #: (`app/widgets/external_card.py`) é território de outra frente, e um
        #: campo novo lá obrigaria as duas a mexerem no mesmo arquivo.
        self._mic_declarado: dict[str, bool] = {}
        #: Outro programa está segurando nó de controle agora? `None` = ainda
        #: não perguntei, ou a sonda não pôde responder — e "não sei" NÃO vira
        #: aviso: um alarme sem medição atrás ensina a ignorar alarmes.
        self._mesa_suja: bool | None = None
        #: `{uniq: veredito}` — como a CONEXÃO de cada controle nasceu, do campo
        #: `nascimento` do payload por controle (SINAL-NO-NASCIMENTO-01/E2).
        #: Vive fora do `DadosDoControle` pela mesma razão do `_mic_declarado`:
        #: o card (`app/widgets/external_card.py`) é território de outra frente,
        #: e um campo novo lá obrigaria as duas a mexerem no mesmo arquivo.
        self._nascimentos: dict[str, Any] = {}

    # -- montagem ----------------------------------------------------------

    def montar(self, caixa: Any) -> None:
        from gi.repository import Gtk

        self._caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.pack_start(self._caixa, False, False, 0)
        # O estado vazio vai à tela AGORA, antes de qualquer pergunta: a
        # resposta chega por callback, e uma seção em branco enquanto ela não
        # chega leria como seção quebrada.
        self._desenhar([])
        # Cor e número de jogador são DIFERIDOS como o resto da aba, e a frase
        # é a mesma constante do Orçamento e da Mesa. Ver `moldura.QUANDO_VALE`
        # para o defeito que ela fecha: a aba tinha três semânticas de salvar e
        # só uma escrita na tela.
        #
        # Ela fica FORA de `self._caixa` de propósito: aquela caixa é esvaziada
        # e repreenchida a cada reexame, e a frase não é dado da mesa — some e
        # volta piscaria a cada troca de aba.
        # A capacidade do microfone vem ANTES da frase de quando a escolha vale,
        # e vem UMA vez por seção, não uma por card: são 208px de largura por
        # card, e a mesma frase repetida cinco vezes vira ruído em vez de
        # informação. Ela fica fora de `self._caixa` pelo mesmo motivo da outra
        # — aquela caixa é esvaziada a cada reexame, e a capacidade do rádio não
        # é dado da mesa.
        #
        # LEX-2, ITEM 4 — A `QUANDO_VALE` SAIU DA PÁGINA (26/08/2026) e virou a
        # dica da frase de capacidade. Ela diria a mesma coisa com a mesa vazia
        # e com a mesa cheia, logo é EXPLICAÇÃO, e explicação vai para o hover.
        #
        # POR QUE ESTE RÓTULO E NÃO O INTERRUPTOR QUE ELA EXPLICA: o
        # interruptor nasce e morre com o card, e numa mesa sem controle nenhum
        # não existe widget nenhum para hospedar a frase — que é exatamente o
        # caso que `test_a_aba_diz_quando_a_escolha_fica_guardada.py` monta
        # (hospedeiro vazio). Este rótulo é o único desta seção que existe
        # sempre e que fica FORA de `self._caixa`, a caixa que o reexame
        # esvazia.
        capacidade = rotulo_de_apoio(frase_da_capacidade_do_mic())
        with contextlib.suppress(Exception):
            capacidade.set_tooltip_text(_(QUANDO_VALE))
        caixa.pack_start(capacidade, False, False, 0)
        self.reexaminar()

    # -- leitura -----------------------------------------------------------

    def reexaminar(self) -> None:
        """Relê a mesa e redesenha a grade. Engole a própria exceção.

        É o refresher da aba: `app.py` chama o nome direto, sem embrulhar, e uma
        leitura que falhe não pode derrubar a troca de aba.
        """
        try:
            leitor = getattr(self._host, "_controles_leitor", None)
            if leitor is not None:
                self._aplicar(leitor())
                return
            if self._e_bancada_de_retrato():
                # O retrato NUNCA publica dado vivo (F5). Sem um dublê montado,
                # a seção mostra o estado vazio em vez de fotografar a mesa dela
                # — e, principalmente, em vez de mandar o comando de fábrica que
                # lê a cor para os quatro controles durante uma captura.
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
        """O hospedeiro é o de `scripts/gui-captura/retratar_abas.py`?

        O sinal é o `_mesa_leitor`, que aquele host monta para a seção da mesa
        (`secao_mesa.py:772`, `_mesa_leitor`) e que nenhum hospedeiro de produção tem. Usar um
        sinal que já existe é melhor que inventar uma segunda bandeira: uma
        bandeira nova precisaria ser posta em `retratar_abas.py`, que é
        território de outra frente nesta leva, e até lá a captura sairia falando
        com o daemon vivo — falha CALADA, do tipo que só aparece no PNG.
        """
        return getattr(self._host, "_mesa_leitor", None) is not None

    def _chegou_o_estado(self, resultado: Any) -> bool:
        """Guarda os adotados e vai buscar os que o Hefesto só vê.

        Em série e não em paralelo de propósito: o executor da ponte tem UM
        worker (`ipc_bridge._get_executor`), então duas chamadas simultâneas
        seriam duas filas na mesma fila — com a segunda pagando o tempo da
        primeira de qualquer jeito, e o código ficando com dois caminhos de
        chegada para reconciliar.
        """
        self._estado = resultado if isinstance(resultado, dict) else {}
        call_async(
            "controller.list",
            {"external": True},
            self._chegou_o_inventario,
            self._nao_respondeu,
            # O inventário externo enumera TODOS os /dev/input e sonda quem
            # segura cada hidraw: 10-40 ms mais um subprocesso. O default de
            # 0,25 s da ponte estoura.
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
        self._nascimentos = {
            uniq_normalizado(entrada.get("uniq")): entrada.get("nascimento")
            for entrada in adotados
            if uniq_normalizado(entrada.get("uniq"))
            and isinstance(entrada.get("nascimento"), dict)
        }
        self._desenhar(self._cards_da_mesa(adotados, externos))
        self._perguntar_as_cores(adotados)
        self._perguntar_pela_mesa()

    def _cards_da_mesa(
        self, adotados: list[dict[str, Any]], externos: list[dict[str, Any]]
    ) -> list[DadosDoControle]:
        """Os dados de cada card, ordenados pelo número de jogador."""
        declarado = self._declaracoes()
        # Z2-5 (24/08/2026): o dono único, não mais o campo legado por
        # getattr. `selecionado=bool(alvo) and alvo == uniq` já era imune ao
        # defeito do P3 (`None` — TODOS ou DESCONHECIDO — nunca marca card
        # nenhum), então a migração é byte-idêntica na tela; o que muda é a
        # fonte deixar de ser o campo que o portão da Z2-6 apaga.
        alvo = alvo_de_edicao(self._host).uniq
        cards: list[DadosDoControle] = []
        for entrada in adotados:
            cards.append(
                self._card(
                    {**entrada, "bus": str(entrada.get("transport") or "")},
                    adotado=True,
                    # Sem fallback posicional, e a ausência dele é a cura: com
                    # `player_slot` nulo (o registro do daemon ainda sem opinião)
                    # a conta `índice + 1` deu "Jogador 4" a DOIS cards da mesa
                    # de cinco, medido em 22/08/2026 contra
                    # `tests/fixtures/inventario_externos.json`. É o mesmo ponto
                    # cego que a NUMA-05 curou nos externos
                    # (`external_controllers.slot_of`): null honesto vale mais
                    # que número errado, e o card tem título para dizê-lo.
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
        """O que está no disco, com a pendência desta sessão por cima.

        Decisão C5 — entrar na aba RELÊ o disco. E a pendência vence porque ela
        é mais nova: o "Aplicar" ainda não rodou, e mostrar o valor antigo faria
        o clique dela parecer perdido.
        """
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
        """Repinta SÓ a borda do card que ganhou cor.

        Redesenhar a grade inteira tiraria o foco de quem estivesse digitando no
        campo livre de outro card — e a resposta chega segundos depois da
        montagem, que é exatamente quando ela poderia estar digitando.
        """
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

    def _perguntar_pela_mesa(self) -> None:
        """Alguém está segurando nó de controle agora? Fora do tique, e uma vez.

        A resposta muda só a DICA do botão da luz — nunca a sensibilidade dele.
        A regra dela é literal (*"sempre visível mas só acionável quando tiver
        no rádio"*), e há um segundo motivo medido: o experimento que fecha a
        célula do mapa de canais precisa do gesto rodando **com a Steam
        aberta** (BARRA-MUDA-01 §6). Um produto que recusasse aí tornaria a
        própria medição impossível.
        """
        leitor = getattr(self._host, "_mesa_limpa_leitor", None)
        if leitor is None and self._e_bancada_de_retrato():
            return
        run_in_thread(leitor or _pergunta_da_mesa, self._chegou_a_mesa)

    def _chegou_a_mesa(self, resultado: Any) -> bool:
        """Guarda o veredito e reescreve as dicas dos botões que já estão na tela."""
        self._mesa_suja = resultado if isinstance(resultado, bool) else None
        for bloco in self._luzes.values():
            with contextlib.suppress(Exception):
                bloco.reler_a_dica(bool(self._mesa_suja))
        return False

    # -- desenho -----------------------------------------------------------

    def _desenhar(self, cards: list[DadosDoControle] | None) -> None:
        """A grade, ou a frase de que não há o que mostrar.

        `None` distingue "o Hefesto não respondeu" de "respondeu e a mesa está
        vazia". As duas frases são diferentes porque a ação dela é diferente:
        uma pede ligar o Hefesto, a outra pede conectar um controle.
        """
        if self._caixa is None:
            return
        from gi.repository import Gtk

        # Uma espera viva aponta para widgets que o `_esvaziar` vai destruir —
        # e um tique que chegasse depois disso mexeria em widget morto. Cancelar
        # antes é o que impede a janela de cair numa troca de aba durante a
        # contagem.
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
        # `row_homogeneous` iguala LINHAS entre si — é o que faz o card da
        # segunda fileira ter a mesma altura do da primeira. O que iguala dois
        # cards da MESMA fileira é o `valign=FILL` + `vexpand` de cada card
        # (`app/widgets/external_card.py`). Precisa das duas metades.
        grade.set_row_homogeneous(True)
        for indice, dados in enumerate(cards):
            card = ExternalCard(
                dados, ao_declarar=self._ao_declarar, ao_numerar=self._ao_numerar
            )
            self._cards[dados.chave] = card
            self._pendurar_a_luz(card, dados)
            # Depois da luz, e a ordem é a do encaixe: os dois usam a mesma
            # conta de posição, então quem entra por último fica embaixo.
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
                mesa_suja=bool(self._mesa_suja),
                nascimento=self._nascimentos.get(uniq_normalizado(dados.uniq)),
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

    # -- gestos ------------------------------------------------------------

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
        """Acumula a escolha dela no rascunho. NÃO grava — quem grava é o rodapé.

        `D-A4`, sem exceção: o clique marca o rascunho e o efeito sai no
        "Aplicar". Chamar `machine.declare` daqui criaria um segundo dono do
        gesto de gravar, que é a classe de defeito que a `ABAS-01` curou.
        """
        card = self._cards.get(chave)
        endereco = "" if card is None else card.dados.endereco
        if not endereco:
            # Sem endereço de doze hexa não há chave no `maquina.json`, e o card
            # já mostra a frase que diz isso. A escolha continua valendo na tela
            # — a borda repinta — e morre com a janela.
            self._repintar(chave, campo, valor)
            return
        self._host._maquina_pendente = fundir_declaracao(
            getattr(self._host, "_maquina_pendente", None),
            {"controles": {endereco: {campo: valor}}},
        )
        # A marca "há escolhas por aplicar" no rodapé (23/08/2026). Sem esta chamada
        # ela só acendia ao trocar de aba ou ao ir para a bandeja — quem declarava e
        # clicava direto no X via o diálogo de fechamento sem nunca ter visto o aviso.
        # `getattr` com guarda é o idioma da casa para fiação de aba: hospedeiro de
        # teste sem rodapé não pode derrubar a declaração.
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
        """Pede o número ao daemon e RELÊ quando ele confirmar.

        Nada é pintado por conta própria: o número que aparece é o que o daemon
        devolveu no reexame, nunca o que a janela achou que ia acontecer. É a
        mesma disciplina do chip da aba Status (`status_actions.py:1854-1868`),
        e ela existe porque a alternativa cria a terceira verdade — três
        superfícies, dois números, o mesmo controle.
        """

        def _fim(resultado: Any) -> bool:
            ok, motivo = resultado
            if not ok:
                logger.info("config_numero_recusado", motivo=motivo or "sem resposta")
            self.reexaminar()
            return False

        run_in_thread(lambda: identity_number_set(uniq, numero), _fim)


# ---------------------------------------------------------------------------
# O bloco do gesto da luz, dentro do card
# ---------------------------------------------------------------------------


class _BlocoDaLuz:
    """Os dois estados do desenho dela, encaixados no corpo de um card.

    Ele NÃO é uma subclasse de widget: é um dono de widgets. Assim o arquivo do
    card (`app/widgets/external_card.py`) continua sem saber que este gesto
    existe — território de outra frente nesta leva, e um card que aprendesse a
    falar com o BlueZ deixaria de ser um card.

    Tudo que toca o mundo entra pelo construtor (`ao_derrubar`, `ao_voltar`,
    `agendar`): é o que permite exercer a máquina inteira sem BlueZ, sem
    controle e sem relógio.
    """

    def __init__(
        self,
        dados: DadosDoControle,
        *,
        mesa_suja: bool,
        nascimento: Any = None,
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
        #: Quem sai da thread da janela. Injetável porque o `Disconnect` pode
        #: levar segundos, e porque um teste não pode depender do laço do GTK
        #: para provar que o card entrou no estado certo.
        self._correr = correr if correr is not None else run_in_thread
        self._corpo: Any = None
        self._escondidos: list[Any] = []
        self._fonte: Any = None
        self._espera: EsperaPeloPS | None = None

        self.caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        self.botao = Gtk.Button(label=TEXTO_DO_BOTAO)
        self.botao.set_sensitive(pode_derrubar(dados))
        self.botao.set_tooltip_text(dica_do_botao(dados, mesa_suja))
        self.botao.connect("clicked", self._ao_clicar)
        self.caixa.pack_start(self.botao, False, False, 0)

        #: A RAZÃO, logo abaixo do botão: por que a cura se aplica a ESTA
        #: conexão. Vem do carimbo que o daemon tirou no nascimento dela; sem
        #: carimbo, ou com carimbo que não condena, a linha não existe.
        self._tem_razao = frase_do_nascimento(nascimento)
        self.razao = _apoio_do_bloco(self._tem_razao or "")
        if not self._tem_razao:
            _oculto(self.razao)
        self.caixa.pack_start(self.razao, False, False, 0)

        self.aviso = _oculto(_apoio_do_bloco(f"▲ {FRASE_APERTE_PS}"))
        self.contagem = _oculto(_apoio_do_bloco(frase_da_procura(ESPERA_PELO_PS_S)))
        self.cancelar = _oculto(Gtk.Button(label=TEXTO_CANCELAR))
        self.cancelar.connect("clicked", self._ao_cancelar)
        #: O recado do fim. Ele SOBREVIVE ao fim da espera de propósito: o card
        #: volta ao normal, mas a frase fica — sem ela, "não voltou" viraria
        #: silêncio, que é o defeito que o ELO-MUDO-01 nomeou.
        self.recado = _oculto(_apoio_do_bloco(""))
        for widget in (self.aviso, self.contagem, self.cancelar, self.recado):
            self.caixa.pack_start(widget, False, False, 0)

    # -- encaixe -----------------------------------------------------------

    def encaixar(self, card: Any) -> None:
        """Põe a caixa no corpo do card, ANTES do espaçador.

        O espaçador é o que empurra "Jogador:" para o rodapé de todos os cards
        (`external_card.py`, o `respiro`). Entrar depois dele jogaria o botão
        para baixo da linha do jogador, que não é o desenho dela.
        """
        corpo = card.get_child()
        if corpo is None:
            return
        antes = corpo.get_children()
        corpo.pack_start(self.caixa, False, False, 0)
        with contextlib.suppress(Exception):
            corpo.reorder_child(self.caixa, max(0, len(antes) - 2))
        self._corpo = corpo

    def reler_a_dica(self, mesa_suja: bool) -> None:
        """A sonda da mesa respondeu depois do desenho — a dica acompanha."""
        with contextlib.suppress(Exception):
            self.botao.set_tooltip_text(dica_do_botao(self.dados, mesa_suja))

    def encerrar(self) -> None:
        """Desarma o tique. Chamado antes de o card ser destruído."""
        if self._espera is not None:
            self._espera.cancelar()
        self._parar_o_tique()

    # -- os dois estados ---------------------------------------------------

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
        """O `Disconnect` respondeu. Só conta o tempo se o controle CAIU.

        `caiu` é falso tanto para "não achei o controle no Bluetooth" quanto
        para "não consegui falar com o `bluetoothd`" — e nos dois casos mandar
        a pessoa apertar PS seria gastar o gesto dela por uma coisa que não
        aconteceu. A frase que aparece é a do próprio gesto, que sabe distinguir
        os quatro fins.
        """
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
            # O card volta ao normal pela releitura da mesa, e não por este
            # bloco se redesenhar: o número de jogador e a cor podem ter mudado
            # com a instância nova, e quem sabe disso é o daemon.
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
            # A razão some junto com o botão: durante a espera o desenho dela
            # mostra SÓ o pedido do PS, e a razão é o argumento do botão que
            # acabou de sair da tela.
            for widget in (self.botao, self.razao):
                widget.set_no_show_all(True)
                widget.hide()
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
            if self._tem_razao:
                self.razao.set_no_show_all(False)
                self.razao.show()
            if recado:
                self.recado.set_text(recado)
                self.recado.show()
        self._mostrar_os_irmaos()

    # -- as linhas do card que somem na espera ------------------------------

    def _esconder_os_irmaos(self) -> None:
        """Esconde "Cor:" e "Jogador:" — o desenho dela mostra só o pedido.

        O espaçador FICA: é ele que segura a altura do card, e um card que
        encolhe no clique faria a fileira inteira pular.
        """
        self._escondidos = []
        if self._corpo is None:
            return
        for indice, filho in enumerate(self._corpo.get_children()):
            if indice < 2 or filho is self.caixa or _e_o_respiro(filho):
                continue
            with contextlib.suppress(Exception):
                if filho.get_visible():
                    self._escondidos.append(filho)
                    # O `no_show_all` junto com o `hide` é cinto e suspensório:
                    # um `show_all()` que chegasse de fora durante a espera
                    # devolveria "Cor:" e "Jogador:" por cima do pedido do PS.
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
    except Exception:  # um Label não tem `get_children`
        return False


def _oculto(widget: Any) -> Any:
    """Nasce escondido e SOBREVIVE ao `show_all` da seção.

    Sem o `no_show_all`, o `show_all()` que a seção dá depois de montar a grade
    revelaria os quatro widgets do estado de espera — e o card nasceria pedindo
    o botão PS sem ninguém ter clicado em nada.
    """
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


def _pergunta_da_mesa() -> bool | None:
    """Alguém está segurando nó de controle agora? `None` = não sei.

    As três respostas são de propósito, e a terceira é a que importa: um
    "não sei" não pode virar aviso, porque alarme sem medição atrás ensina a
    ignorar alarme.
    """
    try:
        from hefesto_dualsense4unix.integrations.sinal_da_barra import (
            CONFIANCA_LIMPA,
            CONFIANCA_SUSPEITA,
            limpo_para_conectar,
        )
    except ImportError:
        return None
    try:
        confianca, _porque, _pids = limpo_para_conectar()
    except Exception:  # best-effort: a janela não pode cair por causa disto
        logger.debug("config_luz_mesa_nao_respondeu", exc_info=True)
        return None
    if confianca == CONFIANCA_SUSPEITA:
        return True
    return False if confianca == CONFIANCA_LIMPA else None


# ---------------------------------------------------------------------------
# Tradução — pura, sem GTK e sem IPC
# ---------------------------------------------------------------------------


def _sem_chave_repetida(cards: list[DadosDoControle]) -> list[DadosDoControle]:
    """Garante que dois cards nunca respondam pela mesma chave.

    A chave sai de `external_key`, que degrada para `evdev_path`, `hidraw`,
    `name` e, no fim da fila, `"?"`. Dois aparelhos que caiam no MESMO degrau de
    degradação teriam a MESMA chave — e então declarar a cor de um repintaria a
    borda do outro, que é o defeito de CLONE-01 voltando pela porta dos fundos
    (dois Nintendo-class no cabo, com o `uniq` sintetizado igual pelo
    `hid-nintendo`, respondendo pelo mesmo botão).

    O sufixo é posicional e vive só na sessão: ele NUNCA chega ao disco, porque
    quem indexa o `maquina.json` é o `endereco`, e um aparelho sem endereço já
    não persiste nada.
    """
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
    """Ordena os cards por jogador, e põe quem não tem número no fim.

    A mesa entrega os controles na ordem em que os viu — que é a ordem de
    enumeração do kernel, não a de chegada nem a dos jogadores. Numa foto de
    quatro controles isso saiu como "Jogador 4, Jogador 1, Jogador 3, Jogador 2"
    (medido em 22/08/2026 contra o fixture da mesa cheia), e uma fileira assim
    lê como erro de montagem antes de ler como informação.

    Estável: dois cards sem número guardam a ordem em que a mesa os entregou, em
    vez de dançarem entre duas leituras. Quem não tem número vai para o fim
    porque ele ainda não é jogador de ninguém — e o começo da fileira é onde o
    olho procura o Jogador 1.
    """
    return sorted(
        cards,
        key=lambda card: (card.slot is None, card.slot if card.slot else 0),
    )


#: O endereço da linha do mapa de canais que responde por esta leitura, e que
#: diz `aciona = sim` nos DOIS lados desde 02/09/2026. Está escrito aqui para
#: quem vier conferir a célula antes de mexer no comportamento da seção.
ID_DA_COR_NO_MAPA = "identidade.cor_do_aparelho@dualsense"


def _pergunta_de_cor(
    uniq: str, ler: Callable[[str], Any]
) -> Callable[[], tuple[str, Any]]:
    """Fecha o endereço e o leitor numa função de zero argumento.

    Um `lambda` com valor por omissão faria o mesmo e é o que estava aqui — o
    `mypy --strict` recusa inferir o tipo dele, e um `# type: ignore` num
    fechamento sobre variável de laço é onde um dia se esconde o bug clássico
    de todas as threads lerem o ÚLTIMO endereço do laço.
    """

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
    """`(id a marcar na lista, texto do campo livre, nome a mostrar)`.

    Três situações, e a ordem é a decisão dela de 21/08/2026 — *"a pessoa pode
    escolher a cor, e a escolha dela vence a tabela"*:

    1. **declarou um nome de fábrica** → a lista marca aquele botão;
    2. **declarou outro nome** → a lista marca "Outra" e o campo livre traz o
       texto dela;
    3. **não declarou** → a lista nasce sem marca e o nome mostrado é o que o
       aparelho respondeu, se respondeu.
    """
    if declarada:
        conhecida = cor_do_nome(declarada)
        if conhecida is not None:
            return conhecida.codigo, "", conhecida.nome
        return ID_DE_OUTRA_COR, declarada, declarada
    return "", "", "" if lida is None else lida.nome


def _tom_da_cor(declarada: str | None, lida: Any) -> str:
    """O hexa da borda, já clareado. "" quando ninguém sabe a cor.

    A escolha dela vence a leitura; um nome que a casa não conhece não tem tom,
    e o card fica com a borda neutra em vez de uma cor inventada.
    """
    if declarada:
        conhecida = cor_do_nome(declarada)
        return "" if conhecida is None else tom_para_a_borda(conhecida.tom)
    if lida is None:
        return ""
    return tom_para_a_borda(lida.tom)
