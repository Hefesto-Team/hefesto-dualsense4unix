"""controller_card.py — card de UM controle na aba Status (STATUS-02/03 + BT-03).

A aba Status deixou de ser single-controller: cada DualSense conectado ganha
um card com identidade própria — título pelo ``player_slot`` de sessão,
bateria própria, swatch da cor CRUA da lightbar — e os inputs ao vivo DAQUELE
controle (barras L2/R2, dois ``StickPreviewGtk`` e o grid 4x4 de
``ButtonGlyph``) com os traços pintados na cor da lightbar dele, ajustada por
``ensure_min_contrast`` (decisão D8: o swatch mostra a cor crua; só os TRAÇOS
recebem a ajustada).

O corpo do card ocupa DUAS linhas, montadas em código — não no Glade::

    [ L2 / R2 ......  |  Giroscópio ......                        ]
    [ Touchpad     |                | Microfone     |             ]
    [ Lightbar     | L3 | R3        | Alto-falante  | botões 4x4  ]

Antes eram seis blocos de largura total, empilhados: o card pedia 457px de
altura e o giroscópio caía abaixo do corte da janela. Emparelhado, o que
somava altura passou a dividir a mesma faixa.

STATUS-SIMETRIA-01 fechou a faixa de baixo em três pontos, todos pedidos pela
mantenedora depois de olhar a tela:

* o **microfone à direita dos analógicos**, em coluna própria e DENTRO do card
  (a madrugada de 26/07 o mandou para o rodapé da aba e foi revertida);
* os **dois analógicos alinhados pelo desenho**, com um ``Gtk.SizeGroup``
  vertical amarrando as duas linhas de título — o degrau de 20px nascia do
  rótulo da esquerda quebrar em 3 linhas e o da direita em 2;
* o **glifo dos botões derivado da escala de fonte** (:func:`glyph_size`), que
  era o único tamanho da interface fora do alcance do ajuste dela.

STATUS-SIMETRIA-02 é o veredito dela sobre aquela entrega: *"só distanciou as
coisas"*. Espalhar os módulos pela largura resolveu o amontoamento e não
produziu leitura. As seis mudanças desta rodada, todas medidas na tela dela:

* **o microfone não sai mais da faixa** (MIC-PRESENTE-01). Os dois ``hide()``
  viraram estado apagado com o motivo em palavras, e a largura do bloco é
  reservada por construção — campo fixo do rótulo mais ``Gtk.SizeGroup``
  horizontal. Sumir era indistinguível de "não existe", e fazia os analógicos
  pularem 42px a cada vez que o sinal ia e voltava (por Bluetooth, o tempo
  todo);
* **as duas legendas de analógico têm o mesmo número de linhas**, agora por
  construção: a quebra está ESCRITA no rótulo e o ``(L3)``/``(R3)`` desceu
  para a linha dos números. O ``SizeGroup`` vertical da rodada anterior
  igualava a altura do bloco, não o número de linhas do texto;
* **cada sensor tem bloco com moldura** no card de um controle — a coluna da
  esquerda era uma lista de seis itens sem separação entre dois assuntos. No
  card compacto a moldura não cabe na largura, e o motivo está em `_bloco`;
* **o alto-falante existe na tela** mesmo sem ninguém ter ajustado o volume;
* **as barras e o giroscópio ganharam teto de largura**, e o card de um
  controle também (:data:`LARGURA_CARD_UNICO`): o vazio deixou de ser buraco
  entre os módulos e virou margem em volta de uma coluna de conteúdo;
* **a bateria aparece uma vez só**: com um controle, quem fala é o frame
  "Estado"; com 2+, quem fala é cada card.

SOM-01 é a terceira rodada, e vem dos três pedidos que ela fez olhando a v2
("quase perfeito"): *"dava pra colocar o auto falante abaixo do microfone"*,
*"aumentar e espaçar mais os botões do controle tipo x quadrado bola e
triângulo e afins"* e *"permitir a expansão da janela"*. As três mudanças:

* **o alto-falante mudou de coluna**: saiu de baixo da lightbar (coluna da
  esquerda) e passou a ficar imediatamente ABAIXO do microfone, numa coluna de
  som própria (:meth:`_montar_coluna_audio`). Os dois são o mesmo assunto — o
  áudio do controle — e estavam em pontas opostas da faixa;
* **os glifos dos botões cresceram e ganharam respiro** no card de UM controle
  (:func:`glyph_size_unico`, :data:`GLYPH_ESPACO_UNICO`). No card compacto eles
  ficam com o tamanho de hoje, e o motivo está em :func:`glyph_size_unico`:
  com 2+ cards lado a lado cada px soma direto no mínimo da janela;
* **o teto de largura virou ELÁSTICO**: o card cresce com a janela do piso
  (:data:`LARGURA_CARD_UNICO`) até :data:`LARGURA_CARD_ELASTICA`, em vez de
  ficar travado num número só. O que impede o vazio de voltar não é o teto e
  sim o CONTEÚDO crescer junto — desenhos maiores e a sobra repartida entre os
  três blocos da faixa, medida em ``test_status_faixa_blocos``.

SOM-02 é a rodada em que o alto-falante deixou de ser só leitura. O bloco
ganhou um controle deslizante de volume (E1), um botão de mudo cuja primeira
linha é INSENSÍVEL (E2) e o botão de devolução da posse (E3, do lado do IPC), e
a barra continuou sendo LEITURA — quem repinta é o tique de 10 Hz relendo
``daemon.state_full``, nunca o valor mandado. A insensibilidade da primeira
linha é entrega, não detalhe: sem volume conhecido, um ``muted`` tranca o
alto-falante em zero e o próprio botão não tem como soltá-lo (armadilha 2 da
sprint, medida no backend real).

Contratos honrados (sprint status-por-controle, itens 6-9 do desenho):

* Rótulo da lightbar pela FONTE (``lightbar_source`` do ``state_full``):
  fonte conhecida e apagada → "Lightbar: apagada"; ``"desconhecida"`` →
  "Lightbar: cor desconhecida" (NUNCA "apagada" — o 0,0,0 da classe LED sem
  escrita nossa pode ser o azul-kernel brilhando agora, refutação 1 do
  sprint); o Modo Nativo segue as mesmas regras desde 24/09/2026 (a barra é
  do Hefesto nele também). Sem cor conhecida, os traços usam o accent neutro
  (``ACCENT_NEUTRO``) ajustado.
* BT-03: ``vpad_backend == "uinput"`` com ``vpad_motivo`` preenchido acende
  uma linha visível de degradação com o motivo em palavras leigas
  (``MOTIVOS_DEGRADACAO_LEIGOS``). O texto NUNCA crava o mecanismo do sono
  BT como causa — diz o que aconteceu com o "modo completo", não por quê.
* ``inputs is None`` → a área de inputs mostra "—" (sem leitor); o card
  NUNCA congela o último valor como se fosse vivo.
* ``update()`` tem DIFF interno por seção (título/bateria/cor/degradação/
  inputs): repetir o mesmo estado a 10 Hz não re-renderiza nada.

Sem timers RECORRENTES próprios (quem agenda o tique é a mixin de status, com
os timers que ela JÁ tinha; o aceite do STATUS-02 é diff contra esse baseline)
e sem popups (cosmic-epoch#2497): tudo inline, sempre visível. A ÚNICA exceção
é o repouso do controle deslizante de volume (SOM-02/E1): um
``GLib.timeout_add`` de UM disparo, armado por gesto humano e desarmado ao
disparar ou ao soltar o botão do mouse — sem ele, arrastar o controle vira uma
rajada de IPC bloqueante (um pedido por pixel). Como os demais widgets da casa,
há a variante GTK real e um stub puro para ambiente sem GTK (testes/CI sem
display).
"""
from __future__ import annotations

import contextlib
from typing import Any, Final, NamedTuple

from hefesto_dualsense4unix.app import audio_saida, ipc_bridge
from hefesto_dualsense4unix.app.draft_config import (
    registrar_alto_falante_no_rascunho,
    registrar_microfone_no_rascunho,
)
from hefesto_dualsense4unix.app.widgets.sensor_widgets import (
    ESCALA_ACCEL_G,
    GyroBars,
    LightbarBar,
    MicMeter,
    SpeakerBar,
    TouchpadView,
    fracao_do_volume,
    percentual_do_volume,
    posicao_normalizada,
    selo_mic,
    texto_eixo_g,
    texto_toques,
    texto_volume,
    volume_do_percentual,
)
from hefesto_dualsense4unix.gui.widgets import (
    BUTTON_GLYPH_LABELS,
    ButtonGlyph,
    StickPreviewGtk,
)
from hefesto_dualsense4unix.utils.color_contrast import (
    ACCENT_NEUTRO,
    ensure_min_contrast,
    rgb_para_hex,
    tintar_progressbar,
)
from hefesto_dualsense4unix.utils.repo_files import como_atualizar_esta_instalacao

RGB = tuple[int, int, int]


GRID_BOTOES: Final[list[list[str]]] = [
    ["cross",   "circle",    "square",    "triangle"],
    ["dpad_up", "dpad_down", "dpad_left", "dpad_right"],
    ["l1",      "r1",        "l2",        "r2"],
    ["share",   "options",   "ps",        "touchpad"],
]

ALL_BUTTONS: Final[list[str]] = [b for linha in GRID_BOTOES for b in linha]

L2_R2_THRESHOLD: Final[int] = 30

GLYPH_SIZE_BASE: Final[int] = 24

GLYPH_PX_POR_DEGRAU_DE_FONTE: Final[int] = 4


def _escala_da_interface() -> int:
    """Delta de fonte (px) que a interface está usando, ou 0 sem tema."""
    try:
        from hefesto_dualsense4unix.app.theme import escala_fonte

        return max(0, int(escala_fonte()))
    except (ImportError, ValueError, TypeError, OSError):
        return 0


GLYPH_FATOR_UNICO_OITAVOS: Final[int] = 12

GLYPH_ESPACO_COMPACTO: Final[int] = 2
GLYPH_ESPACO_UNICO: Final[int] = 10


def glyph_size(escala: int | None = None) -> int:
    """Tamanho do glifo em px, DERIVADO da escala de fonte da interface."""
    if escala is None:
        escala = _escala_da_interface()
    return GLYPH_SIZE_BASE + GLYPH_PX_POR_DEGRAU_DE_FONTE * max(0, int(escala))


def glyph_size_unico(escala: int | None = None) -> int:
    """Tamanho do glifo no card de UM controle — maior, e por quanto."""
    return glyph_size(escala) * GLYPH_FATOR_UNICO_OITAVOS // 8


STICK_SIZE_SINGLE: Final[int] = 140
STICK_SIZE_COMPACT: Final[int] = 70

_TITULO_STICK_ESQ: Final[str] = "Analógico\nesquerdo"
_TITULO_STICK_DIR: Final[str] = "Analógico\ndireito"

ROTULO_STICK_ESQ: Final[str] = "L3"
ROTULO_STICK_DIR: Final[str] = "R3"

LARGURA_CARD_UNICO: Final[int] = 1040

LARGURA_BARRA_BATERIA_CARD: Final[int] = 300

TEXTO_PERFIL_SEM_DADO: Final[str] = "Nenhum"

TEXTO_DAEMON_SEM_DADO: Final[str] = "Consultando..."

LARGURA_CARD_ELASTICA: Final[int] = 1400

LARGURA_BARRA_GATILHO_UNICO: Final[int] = 400
LARGURA_GYRO_UNICO: Final[int] = 420
CROMO_DA_MOLDURA_DE_SENSOR: Final[int] = 14
LARGURA_BARRA_GATILHO_COMPACTO: Final[int] = 200
LARGURA_GYRO_COMPACTO: Final[int] = 220

_TOUCHPAD_PX_UNICO: Final[tuple[int, int]] = (180, 80)
_MIC_METER_PX_UNICO: Final[tuple[int, int]] = (180, 28)
_BARRA_FINA_PX_UNICO: Final[tuple[int, int]] = (160, 18)
_BARRA_SPEAKER_PX_UNICO: Final[tuple[int, int]] = (160, 12)

_DESENHO_NATURAL_PX_UNICO: Final[int] = 360

TEXTO_MIC_AUSENTE: Final[str] = "Sem sinal"
TEXTO_MIC_SEM_MUTE: Final[str] = "Captando"

_MIC_ESTADO_CHARS: Final[int] = len(TEXTO_MIC_AUSENTE)

TEXTO_BOTAO_MIC_ATIVAR: Final[str] = "Ativar"
TEXTO_BOTAO_MIC_SILENCIAR: Final[str] = "Silenciar"
#: DualSense não devolve o volume nem o estado do mute (não há report de
#: ~90px e faria os três rótulos da linha cortarem em 1180px (medido).
TEXTO_BOTAO_MIC_DEVOLVER: Final[str] = "Liberar"
TEXTO_BOTAO_MIC_SEM_LEITURA: Final[str] = "Silenciar"

DICA_MIC_ATIVAR: Final[str] = (
    "O microfone está mudo no firmware do controle (camada 3). Desmutar daqui "
    "faz o hefesto assumir o registrador — e o botão de microfone do controle "
    "para de valer até você clicar em Liberar."
)
DICA_MIC_SILENCIAR: Final[str] = (
    "O microfone está aberto e quem manda no mudo é o botão físico do "
    "controle. Silenciar daqui faz o hefesto assumir o registrador."
)
DICA_MIC_DEVOLVER: Final[str] = (
    "Quem manda no mudo agora é o hefesto, e por isso o botão de microfone do "
    "controle não responde. Liberar faz o botão físico voltar a valer."
)
DICA_MIC_SEM_LEITURA: Final[str] = (
    "O daemon ainda não leu o estado do microfone deste controle. Sem saber "
    "se ele está mudo, mandar mutar ou desmutar seria chute."
)


# O DualSense não expõe ganho de microfone — o que existe no firmware é o mudo,
TEXTO_MIC_VOLUME_TITULO: Final[str] = "Microfone"

DICA_MIC_ESCALA: Final[str] = (
    "Volume da captura do microfone, no sistema. Vale igual no cabo e no "
    "rádio: o Hefesto escolhe o caminho sozinho. Este controle NÃO mexe no "
    "mudo do firmware — quem faz isso é o botão ao lado, e só ele apaga a luz "
    "vermelha do microfone. Salvar ou aplicar o perfil grava este valor."
)

#:
#: **PROVISÓRIO — decisão dela.** Com dois DualSense no cabo há DUAS placas de
TEXTO_MIC_ALVO_NAO_HONRADO: Final[str] = (
    "O volume foi para o microfone de OUTRO controle: o Hefesto não conseguiu "
    "mirar este, e o pedido caiu no controle PRIMÁRIO. O perfil deste controle "
    "não mudou."
)

#: Repouso do controle deslizante do microfone, em ms. Mesmo número do
_MIC_REPOUSO_MS: Final[int] = 180

#: Alto-falante sem volume conhecido. O DualSense NÃO devolve o volume — não
TEXTO_SPEAKER_SEM_DADO: Final[str] = "Não ajustado"

TITULO_SPEAKER: Final[str] = "Alto-falante"


TEXTO_CANAL_PERGUNTA: Final[str] = "O que sai no controle:"

CANAL_SONS_DO_JOGO: Final[str] = "jogo"
CANAL_TODO_O_PC: Final[str] = "tudo"

CANAL_NADA_NO_CONTROLE: Final[str] = "nada"
CANAIS_DO_SPEAKER: Final[tuple[tuple[str, str], ...]] = (
    (CANAL_SONS_DO_JOGO, "Sons do jogo"),
    (CANAL_TODO_O_PC, "Todo o som do PC"),
)

DICAS_DO_CANAL: Final[tuple[tuple[str, str], ...]] = (
    (
        CANAL_SONS_DO_JOGO,
        "O que sai no controle: só o que o jogo mandar para ele. A trilha "
        "continua na TV. Depende do jogo ter essa opção.",
    ),
    (
        CANAL_TODO_O_PC,
        "O que sai no controle: todo o som do computador passa a sair pelo "
        "alto-falante dele.",
    ),
)

ROTA_DO_CANAL: Final[dict[str, int]] = {
    CANAL_SONS_DO_JOGO: 2,
    CANAL_TODO_O_PC: 3,
    CANAL_NADA_NO_CONTROLE: 0,
}

TEXTO_BOTAO_SPEAKER_ATIVAR: Final[str] = "Ativar"
TEXTO_BOTAO_SPEAKER_SILENCIAR: Final[str] = "Silenciar"
TEXTO_BOTAO_SPEAKER_DEVOLVER: Final[str] = "Liberar"
TEXTO_BOTAO_SPEAKER_SEM_DADO: Final[str] = "Silenciar"

_SPEAKER_BOTAO_CHARS: Final[int] = len(TEXTO_BOTAO_SPEAKER_SILENCIAR)

DICA_SPEAKER_ESCALA: Final[str] = (
    "Mover isto faz o hefesto assumir o volume do alto-falante E do fone do "
    "controle. O DualSense não devolve esse valor: depois disso, quem manda é "
    "a janela até você clicar em Liberar ou desconectar o controle."
)

DICA_SPEAKER_SILENCIAR: Final[str] = (
    "O alto-falante está no volume que o hefesto mandou. Silenciar manda zero "
    "sem perder esse volume — Ativar o devolve."
)
DICA_SPEAKER_ATIVAR: Final[str] = (
    "O alto-falante está mudo por ordem nossa. Ativar devolve o mesmo volume "
    "de antes do mudo."
)
DICA_SPEAKER_SEM_DADO: Final[str] = (
    "Ainda não há volume conhecido — use o controle deslizante primeiro"
)
DICA_SPEAKER_DEVOLVER: Final[str] = (
    "Liberar faz o hefesto parar de mandar o volume, e o botão do controle volta "
    "a valer. O que estiver valendo continua até você desconectar o controle — "
    "o DualSense não devolve o volume anterior."
)
DICA_SPEAKER_DEVOLVER_SEM_POSSE: Final[str] = (
    "Não há o que soltar: o volume ainda é do firmware do controle"
)

DICA_BLOCO_SPEAKER: Final[str] = (
    "O volume é do firmware do controle e ele não o devolve; mover o controle "
    "deslizante passa a mandá-lo"
)


TEXTO_AUDIO_SEM_ENDERECO: Final[str] = (
    "Som desligado: este controle está sem endereço"
)

DICA_AUDIO_SEM_ENDERECO: Final[str] = (
    "Este controle não publicou endereço, e sem ele todo comando de som iria "
    "para o controle PRIMÁRIO — outro controle, com o título deste na frente. "
    "O som volta sozinho quando o endereço aparecer."
)

TEXTO_SELO_SAIDA_MUDA: Final[str] = "Saída muda"

TEXTO_SELO_SEM_SOM: Final[str] = "Sem som"


_SELO_CHARS: Final[int] = max(
    len(TEXTO_SELO_SAIDA_MUDA),
    len(TEXTO_SELO_SEM_SOM),
)


SUFIXO_CANAL_ACORDADO: Final[str] = "acordado"
SUFIXO_CANAL_DORMINDO: Final[str] = "dormindo"

DICA_CANAL_ACORDADO: Final[str] = (
    "O canal de áudio deste controle está acordado: o próximo som sai desde o "
    "primeiro instante."
)
#: depois, com o nó já acordado, saiu "tuuuuuuuu". Três leituras daquela
DICA_CANAL_DORMINDO: Final[str] = (
    "O canal de áudio deste controle está SUSPENSO no PipeWire. Religar o "
    "hardware come o começo do som — medido: o mesmo canal, no mesmo volume e "
    "na mesma rota, não saiu com o nó ocioso e saiu inteiro com ele acordado. "
    "Num jogo é o efeito sonoro sumindo na hora que importa."
)
DICA_CANAL_E_PADRAO: Final[str] = (
    "É o padrão: o Hefesto instala a regra que impede o alto-falante de "
    "dormir junto com o produto, para todo controle. Não há nada a ligar aqui."
)
def dica_canal_sem_a_regra() -> str:
    """A cura foi arrancada (ou nunca entrou) — e a tela denuncia."""
    return (
        "A regra que impede o alto-falante de dormir NÃO está instalada nesta "
        f"máquina — {como_atualizar_esta_instalacao()} e ela entra sem flag "
        "nenhuma."
    )
DICA_SPEAKER_POSSE_NOSSA: Final[str] = (
    "Quem manda no volume do alto-falante agora é o Hefesto. O DualSense não "
    "devolve esse valor: o número acima é o que NÓS mandamos, não uma leitura "
    "do aparelho."
)

_SPEAKER_REPOUSO_MS: Final[int] = 250

#: moldura de cada bloco só se lê como bloco com ar em volta.
_ESPACO_FAIXA_COMPACTO: Final[int] = 8
_ESPACO_FAIXA_UNICO: Final[int] = 16

_XY_MARKUP: Final[str] = "X:{x:>3}\nY:{y:>3}"


def _markup_xy(x: int, y: int) -> str:
    """``"X:128" / "Y:128"`` — o par de eixos, em mono, sem a lateral."""
    return _XY_MARKUP.format(x=x, y=y)


#: Motivo técnico (``vpad_motivo`` do state_full) → frase curta leiga. As
MOTIVOS_DEGRADACAO_LEIGOS: Final[dict[str, str]] = {
    "uhid_indisponivel": "o modo completo não está disponível neste sistema",
    "uhid_start_falhou": "o modo completo falhou ao iniciar",
    "uhid_bind_falhou": "o sistema não aceitou o modo completo",
    "uhid_vetado_pelo_chamador": "o modo completo foi desligado nesta sessão",
    "sem_uhid": "o modo completo não subiu",
}

#: Sentinela para caches de diff cujo valor válido inclui ``None``.
_SENTINELA: Final[object] = object()


def _rgb3(valor: Any) -> RGB | None:
    """Normaliza o ``lightbar_rgb`` do IPC (``[r, g, b]``/tuple) em tuple.

    ``None`` para qualquer coisa fora do contrato (ausente, tamanho errado,
    canal não numérico) — o chamador trata como "sem cor conhecida".
    """
    if isinstance(valor, (list, tuple)) and len(valor) == 3:
        try:
            r, g, b = (max(0, min(255, int(c))) for c in valor)
        except (TypeError, ValueError):
            return None
        return (r, g, b)
    return None


def _int_ou_none(valor: Any) -> int | None:
    """int estrito (rejeita bool — blindagem contra payload malformado)."""
    if isinstance(valor, int) and not isinstance(valor, bool):
        return valor
    return None


def titulo_do_card(entry: dict[str, Any]) -> str:
    """Título "Controle {N} — {USB|BT}[ · Jogador {X}]" (função pura).

    ``N`` é o ``player_slot`` de sessão (COR-01/D6 — o MESMO número da CLI e
    do applet); sem slot (registry ausente, controle sem MAC) cai em
    ``index + 1``, a posição 1-based. O sufixo "· Jogador {X}" só aparece
    quando o daemon numerou um jogador (D7): fora do co-op todos os controles
    alimentam o MESMO vpad e o jogo vê um controle só — inventar número de
    jogador seria mentira.
    """
    slot = _int_ou_none(entry.get("player_slot"))
    if slot is None:
        indice = _int_ou_none(entry.get("index"))
        slot = (indice + 1) if indice is not None else 1
    transporte = str(entry.get("transport") or "?").upper()
    titulo = f"Controle {slot} — {transporte}"
    jogador = _int_ou_none(entry.get("player"))
    if jogador is not None:
        titulo += f" · Jogador {jogador}"
    return titulo


DICA_TITULO_SEM_VPAD: Final[str] = (
    "Este controle ainda não alimenta gamepad virtual nenhum."
)


def dica_do_titulo(entry: dict[str, Any], state_global: dict[str, Any]) -> str | None:
    """Dica do título: QUAL gamepad virtual este controle alimenta (função pura)."""
    uniq = uniq_do_entry(entry)
    if uniq is None:
        return None
    coop = state_global.get("coop")
    mesa = coop.get("mesa") if isinstance(coop, dict) else None
    if not isinstance(mesa, list):
        return None
    for item in mesa:
        if not isinstance(item, dict) or item.get("uniq") != uniq:
            continue
        backend = item.get("vpad_backend")
        if not isinstance(backend, str) or not backend:
            return DICA_TITULO_SEM_VPAD
        numero = _int_ou_none(item.get("player"))
        alvo = f"do Jogador {numero}" if numero else "deste jogador"
        vpad_uniq = item.get("vpad_uniq")
        detalhe = (
            f"{backend} · {vpad_uniq}"
            if isinstance(vpad_uniq, str) and vpad_uniq
            else backend
        )
        frase = f"Alimenta o gamepad virtual {alvo} ({detalhe})."
        nome = item.get("vpad_nome")
        if item.get("nome_divergente") and isinstance(nome, str) and nome:
            frase += f" No sistema ele se chama “{nome}”."
        return frase
    return None


ROTULO_LIGHTBAR_SEGURADA = "A Steam tem este controle aberto"


def rotulo_lightbar(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> tuple[str | None, RGB | None]:
    """``(rótulo, cor_base_do_accent)`` da lightbar de UM controle.

    Regras (STATUS-03 + refutação 1 do sprint — o dono da escrita decide):

    * O Modo Nativo não tem ramo desde 24/09/2026 (`D-2409-NO-NATIVO-A-TELA-
      MOSTRA-A-COR`): a barra é do Hefesto no Nativo também, e «Em Nativo o
      jogo é dono do LED» virou fato errado; o Nativo cai nas regras abaixo.
    * ``lightbar_disputada`` (ESCRITOR-CRU-01) → "a Steam tem este controle
      aberto"; o accent segue a última cor NOSSA. Vem antes de tudo o mais
      porque é um aviso sobre a CONFIANÇA no valor, não sobre o valor: com a
      Steam segurando o hidraw, o que a classe LED devolve é o que o Hefesto
      PEDIU — a madrugada de 16/08 leu ``[0 255 0]`` com a barra apagada e
      ``[0 255 0]`` com ela verde. Dizer "apagada" ou pintar a bolinha de
      verde sem ressalva seria, nos dois casos, afirmar o que ninguém mediu.

      LUZ-CEGA-01/F2 (22/08/2026) — a frase era *"a Steam também escreve
      nesta barra"*, e isso é justamente o que o campo NÃO mede. O booleano
      sai de quem SEGURA o ``fd`` (``fuser`` nos oito nós, medido). Quem
      ESCREVE somos nós: no fio, 32 s com o daemon vivo deram **426** reports
      de saída contra **1** com ele parado, a Steam aberta nos dois lados.
      Segurar não é escrever — e a frase antiga mandava a pessoa procurar o
      defeito na Steam, onde ele não está.
    * ``lightbar_source == "desconhecida"`` (ou rgb ausente) → "Lightbar: cor
      desconhecida" + accent neutro. NUNCA "apagada": o 0,0,0 do sysfs sem
      escrita nossa pode ser o azul-kernel brilhando neste exato momento.
    * fonte conhecida (``sysfs``/``desired`` — a escrita foi NOSSA) e apagada
      (``lightbar_on`` False ou rgb preto) → "Lightbar: apagada" + neutro.
    * cor conhecida e acesa → sem rótulo; o accent é a própria cor.

    A cor devolvida é a BASE do accent (crua); ``None`` = usar o neutro.
    O chamador ajusta com ``ensure_min_contrast`` antes de pintar traço.
    """
    rgb = _rgb3(entry.get("lightbar_rgb"))
    if bool(entry.get("lightbar_disputada")):
        return (ROTULO_LIGHTBAR_SEGURADA, rgb)
    fonte = str(entry.get("lightbar_source") or "desconhecida")
    if fonte == "desconhecida" or rgb is None:
        return ("Lightbar: cor desconhecida", None)
    if not bool(entry.get("lightbar_on")) or rgb == (0, 0, 0):
        return ("Lightbar: apagada", None)
    return (None, rgb)


def texto_degradacao(entry: dict[str, Any]) -> str | None:
    """Linha do badge de degradação (BT-03); ``None`` = badge some."""
    if entry.get("vpad_backend") != "uinput":
        return None
    motivo = entry.get("vpad_motivo")
    if not isinstance(motivo, str) or not motivo:
        return None
    legivel = MOTIVOS_DEGRADACAO_LEIGOS.get(motivo, motivo.replace("_", " "))
    return f"Emulação degradada (uinput): {legivel}"


def texto_motion(entry: dict[str, Any], state_global: dict[str, Any]) -> str | None:
    """Linha discreta do giroscópio espelhado (GYRO-03); ``None`` = some.

    Só aparece quando o vpad DESTE controle está com o espelho de motion
    ATIVO (``motion_streaming`` no ``rumble_ff.per_vpad`` do state_full) —
    a ausência da linha não é alarme: uinput/máscara xbox/Modo Nativo não
    têm espelho por design, e acusar "sem giroscópio" em todo card seria
    ruído crônico (quem diagnostica silêncio anômalo é o doctor).

    Mapeamento controle→vpad: entrada com ``player`` numerado (co-op, D7)
    casa com o vpad daquele jogador; sem número, o PRIMÁRIO casa com o vpad
    do P1 (fora do co-op o espelho só existe nele). Demais controles → None.

    GYRO-03-FIX: jogador 1 SEM ``is_primary`` nunca mostra a linha — fora do
    co-op ``resolve_player_numbers`` numera TODOS os conectados como jogador
    1 (é o que o jogo vê), mas o espelho do vpad P1 lê só o hidraw do
    PRIMÁRIO; exibir a linha num secundário seria telemetria mentindo.

    PAINEL-DA-VERDADE-01 acrescentou DOIS casos em que o silêncio deixa de
    ser a resposta certa, e só dois. A decisão medida acima continua inteira
    — a ausência da linha não é alarme, e "sem giroscópio" em todo card seria
    ruído crônico. O que mudou é que há duas situações em que o silêncio faz
    a tela parecer QUEBRADA quando ela está certa:

    * **máscara Xbox 360** — o JOGO não recebe giroscópio, e o motivo não é
      defeito nosso: a API do controle de Xbox não tem esse sensor. Sem a
      frase, ela vê um card com giroscópio desenhado e nenhum sinal de que o
      dado não sai dali. **O sujeito é o jogo, e não o controle** (21/09/2026,
      ordem dela): o aparelho segue publicando movimento, e a Navegação e os
      gestos seguem usando;
    * **Modo Nativo** — não existe gamepad virtual, e perguntar se o dado
      "chegou ao vpad" não faz sentido. O jogo abre o hidraw do controle
      físico e recebe tudo, inclusive o giroscópio.

    Nos dois casos a frase EXPLICA; nos demais o silêncio continua.

    **O GIRO QUE NÃO VAI COMO GIROSCÓPIO NÃO FLUI** — 24/09/2026. Com a Mira
    Virtual acesa (A-MIRA-POR-MOVIMENTO-NA-TELA-02, o bloco `mira`) ou com o
    chip Giroscópio desligado por ela (A-MIRA-NA-NAVEGACAO-01, o `False` de
    `sensores.giroscopio_ligado`), o filtro do report tira o giroscópio da
    janela daquele controle (`virtual_motion.REGISTRO.filtrar`), e o
    `motion_streaming` segue ligado pelo acelerômetro: «fluindo para o jogo»
    seria fato errado, e a linha some. Sem o bloco, ninguém leu, e a linha
    segue a telemetria. O Nativo vem antes (o jogo lê o `hidraw` do físico, e o
    interruptor não o alcança); a Xbox, entre os dois: com o Giroscópio desligado
    o «no Hefesto ele segue ativo» dela contradiria o chip na mesma linha.
    """
    if bool(state_global.get("native_mode")):
        return f"Giroscópio: {_FRASE_NATIVO}"
    sensores = entry.get("sensores")
    if isinstance(sensores, dict) and sensores.get("giroscopio_ligado") is False:
        return None
    if _mascara_e_xbox(state_global, entry):
        return f"Giroscópio: {_FRASE_MASCARA_XBOX['giroscopio']}"
    mira = entry.get("mira")
    if isinstance(mira, dict) and mira.get("ligada") is True:
        return None
    rumble_ff = state_global.get("rumble_ff")
    per_vpad = rumble_ff.get("per_vpad") if isinstance(rumble_ff, dict) else None
    if not isinstance(per_vpad, list):
        return None
    player = _int_ou_none(entry.get("player"))
    if player == 1 and not bool(entry.get("is_primary")):
        # Co-op OFF com 2+ DualSense: todos vêm com player=1, mas só o
        return None
    if player is None:
        if not bool(entry.get("is_primary")):
            return None
        player = 1
    for item in per_vpad:
        if not isinstance(item, dict) or _int_ou_none(item.get("player")) != player:
            continue
        if item.get("motion_streaming") is not True:
            return None
        hz = item.get("motion_hz")
        if isinstance(hz, (int, float)) and not isinstance(hz, bool) and hz > 0:
            return f"Giroscópio: fluindo para o jogo (~{hz:.0f} Hz)"
        return "Giroscópio: fluindo para o jogo"
    return None


ATIVIDADE_FRESCA_S: Final[float] = 3.0

_VERDADE_MAX_CHARS: Final[int] = 110

#: dígitos porque o `motion_hz` é medido, não declarado — o DualSense entrega
_HZ_MAIS_LARGO: Final[str] = "1000"

_MOTOR_MAIS_LARGO: Final[str] = "255"

SITUACAO_CHEGANDO: Final[str] = "chegando"
SITUACAO_PARADO: Final[str] = "parado"
SITUACAO_NUNCA: Final[str] = "nunca"
SITUACAO_IMPOSSIVEL: Final[str] = "impossivel"
SITUACAO_NATIVO: Final[str] = "nativo"


class EstadoDoRecurso(NamedTuple):
    """A situação de um recurso e a frase que a diz, em português leigo."""

    situacao: str
    frase: str


RECURSOS_SEM_MASCARA_XBOX: Final[frozenset[str]] = frozenset(
    {"giroscopio", "touchpad"}
)

_CATEGORIA_DO_RECURSO: Final[dict[str, str]] = {
    "touchpad": "touchpad_click",
    "lightbar": "lightbar",
    "gatilho": "trigger",
    "vibracao": "rumble",
    # próprio controle. A Sony fez o mesmo pro DualSense."*
    "alto_falante": "audio_do_jogo",
}

_NOME_NA_FRASE: Final[tuple[tuple[str, str], ...]] = (
    ("giroscopio", "giroscópio"),
    ("vibracao", "vibração"),
    ("gatilho", "gatilho"),
    ("lightbar", "luz"),
    ("touchpad", "clique do touchpad"),
    ("alto_falante", "som do controle"),
)

#: `home_actions.TEXTO_CUSTO_MASCARA_XBOX`, para caber dentro do bloco.
_FRASE_MASCARA_XBOX: Final[dict[str, str]] = {
    "giroscopio": (
        "o jogo vê este controle como Xbox 360, e essa API não leva "
        "giroscópio — no Hefesto ele segue ativo"),
    "touchpad": (
        "o jogo vê este controle como Xbox 360, e essa API não leva "
        "touchpad — no Hefesto ele segue ativo"),
}

#: E a do Modo Nativo, em que não há gamepad virtual nenhum: o jogo abre o
#: hidraw do controle FÍSICO e fala com ele direto. Tudo chega — não porque
#: nós entregamos, mas porque não há intermediário.
_FRASE_NATIVO: Final[str] = "o jogo fala direto com o controle"


def _item_do_vpad(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> dict[str, Any] | None:
    """O bloco `rumble_ff.per_vpad` do vpad DESTE controle; ``None`` = não há.

    O casamento controle→vpad é o MESMO do `texto_motion`, e as regras dele
    estão documentadas lá — inclusive o guarda do GYRO-03-FIX (jogador 1 sem
    `is_primary` nunca casa: fora do co-op todos os conectados vêm como
    jogador 1, mas só o primário tem reader).

    Este é o dono único do casamento. Dois jeitos de responder "qual vpad é o
    deste controle" divergiriam na primeira mudança do co-op, e esta casa tem
    defeito registrado com essa forma exata.
    """
    rumble_ff = state_global.get("rumble_ff")
    per_vpad = rumble_ff.get("per_vpad") if isinstance(rumble_ff, dict) else None
    if not isinstance(per_vpad, list):
        return None
    player = _int_ou_none(entry.get("player"))
    if player == 1 and not bool(entry.get("is_primary")):
        return None
    if player is None:
        if not bool(entry.get("is_primary")):
            return None
        player = 1
    for item in per_vpad:
        if isinstance(item, dict) and _int_ou_none(item.get("player")) == player:
            return item
    return None


def _visto_ha_s_do_vpad(entry: dict[str, Any], state_global: dict[str, Any]) -> Any:
    """O bloco `visto_ha_s` do vpad deste controle; ``None`` se não há vpad."""
    item = _item_do_vpad(entry, state_global)
    if item is None:
        return None
    visto = item.get("visto_ha_s")
    return visto if isinstance(visto, dict) else {}


def _contagem(item: Any, chave: str) -> int:
    """Um contador cumulativo do bloco do vpad; 0 quando não há."""
    if not isinstance(item, dict):
        return 0
    valor = item.get(chave)
    if isinstance(valor, bool) or not isinstance(valor, int):
        return 0
    return valor


def motores_no_fisico(item: Any) -> tuple[int, int] | None:
    """``(weak, strong)`` que chegou AOS MOTORES agora; ``None`` = nada a dizer.

    MOTOR-QUE-NAO-SE-VE-01 (09/08/2026). Três respostas viram ``None``, e as
    três de propósito:

    * **daemon antigo / vpad uinput** — a chave não existe. Silêncio, como em
      todo campo opcional deste payload;
    * **nunca escreveu** (``rumble_no_fisico_ha_s`` ausente) — dizer 0/0 aqui
      seria afirmar que os motores receberam uma parada, quando o que houve
      foi ninguém ter escrito;
    * **velho** — mais de `ATIVIDADE_FRESCA_S` sem escrita. É o mesmo teto que
      governa o resto da linha, e pelo mesmo motivo: um número congelado de
      três minutos atrás ao lado da palavra "chegando" é a mentira confortável
      que esta tela existe para não contar.

    O par ``(0, 0)`` fresco também some: ele é o jogo mandando PARAR, e a
    parada não é o número que responde *"a vibração saiu do nosso lado?"*.
    """
    if not isinstance(item, dict):
        return None
    idade = item.get("rumble_no_fisico_ha_s")
    if isinstance(idade, bool) or not isinstance(idade, (int, float)):
        return None
    if idade > ATIVIDADE_FRESCA_S:
        return None
    par = item.get("rumble_no_fisico")
    if not isinstance(par, (list, tuple)) or len(par) != 2:
        return None
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in par):
        return None
    if par[0] == 0 and par[1] == 0:
        return None
    return (int(par[0]), int(par[1]))


#: O nome do ramo de DESCARTE no anel de vibração do vpad
#: (``uhid_gamepad.RAMO_DESCARTADO``). Mesmo contrato por string das chaves de
#: :data:`_CATEGORIA_DO_RECURSO`: a janela é outro processo e não importa nada
#: do daemon; o que viaja entre os dois é o nome.
_RAMO_DESCARTADO: Final[str] = "descartado"


def pedido_de_vibracao_fresco(item: Any) -> bool:
    """Algum jogo PEDIU vibração de verdade nos últimos ``ATIVIDADE_FRESCA_S``?

    NO-JOGO-SEM-FALSO-VERDE-01/T1 (25/08/2026). Esta é a pergunta que a linha
    "vibração" faz, e até esta leva ela era respondida pelo carimbo errado.

    **O que estava medido, e é o defeito inteiro em três linhas.** O vpad
    carimba ``visto_ha_s["rumble"]`` nos DOIS ramos — no pedido de verdade
    (``uhid_gamepad:2159``) e na PARADA do SDL (``:2091``, flags zerados e
    motores zerados) —, e carimbar a parada está certo: ela é prova de que o
    jogo está falando conosco, e é para isso que o ``ff_parada_sdl_count``
    existe. O que estava errado era a TELA ler aquele carimbo como se ele
    respondesse "o jogo pediu vibração". Na bancada dela, às 21h50 de 23/08,
    com **zero** DualSense na mesa e nenhum jogo aberto, uma parada solta
    (``ff_parada_sdl_count: 1``, ``ff_nao_nulo_count: 0``) deixou a linha verde
    e escrita "no jogo agora" por três segundos.

    **Por que a resposta sai do anel e não de um carimbo novo.** O
    ``ff_ultimos_reports`` (QUEM ESCREVEU-01) já viaja no ``state_full``, com
    ``ha_s``, ``weak``, ``strong`` e o ``ramo`` de cada um dos últimos oito
    reports — ou seja, o payload de HOJE já separa o pedido da parada, e
    ninguém lia. Um carimbo novo no vpad daria a mesma resposta e só a partir
    do **próximo start do daemon**: nesta casa "o daemon vivo é mais velho que
    o código" é rotina (install editable), e a cura que precisa de restart é a
    cura que não vale na mesa dela hoje.

    As três provas que a função aceita, todas positivas — a ausência de prova
    nunca vira "chegando":

    1. ``rumble_no_fisico`` fresco e não-nulo (:func:`motores_no_fisico`): o par
       chegou aos motores, então houve pedido. É a prova mais forte, e é a
       única que sobrevive a um anel que já rodou;
    2. um report do anel com ``weak`` ou ``strong`` não-nulo e ``ha_s`` dentro
       do teto. O ramo ``descartado`` fica de fora: aquele report chegou e nós
       o recusamos na porta, então o jogo pediu e a vibração **não** saiu — quem
       conta essa história é o ``ff_descartado_count``, não esta linha;
    3. nada disso: ``False``. Inclusive quando o anel não vem no payload — que
       é o caso do dublê da foto e de um vpad uinput. Dizer "no jogo agora"
       sem uma prova é exatamente o que esta função existe para impedir.
    """
    if not isinstance(item, dict):
        return False
    if motores_no_fisico(item) is not None:
        return True
    anel = item.get("ff_ultimos_reports")
    if not isinstance(anel, list):
        return False
    for report in anel:
        if not isinstance(report, dict) or report.get("ramo") == _RAMO_DESCARTADO:
            continue
        if not (_contagem(report, "weak") or _contagem(report, "strong")):
            continue
        idade = report.get("ha_s")
        if (
            isinstance(idade, (int, float))
            and not isinstance(idade, bool)
            and idade <= ATIVIDADE_FRESCA_S
        ):
            return True
    return False


def estado_do_recurso(
    recurso: str, entry: dict[str, Any], state_global: dict[str, Any]
) -> EstadoDoRecurso | None:
    """A situação de um recurso AGORA; ``None`` = não há o que afirmar."""
    if bool(state_global.get("native_mode")):
        return EstadoDoRecurso(SITUACAO_NATIVO, _FRASE_NATIVO)

    if recurso in RECURSOS_SEM_MASCARA_XBOX and _mascara_e_xbox(
            state_global, entry):
        frase = _FRASE_MASCARA_XBOX.get(recurso)
        return EstadoDoRecurso(SITUACAO_IMPOSSIVEL, frase) if frase else None

    visto = _visto_ha_s_do_vpad(entry, state_global)
    if visto is None:
        return None

    item = _item_do_vpad(entry, state_global)

    if recurso == "giroscopio":
        # `motion_hz` é melhor: ele traz o número que ela vê na tela.
        if not isinstance(item, dict) or item.get("motion_streaming") is not True:
            if _contagem(item, "motion_forwards") > 0:
                return EstadoDoRecurso(SITUACAO_PARADO, "giroscópio")
            return EstadoDoRecurso(SITUACAO_NUNCA, "giroscópio")
        hz = item.get("motion_hz")
        if isinstance(hz, (int, float)) and not isinstance(hz, bool) and hz > 0:
            return EstadoDoRecurso(
                SITUACAO_CHEGANDO, f"giroscópio (~{hz:.0f} Hz)"
            )
        return EstadoDoRecurso(SITUACAO_CHEGANDO, "giroscópio")

    categoria = _CATEGORIA_DO_RECURSO.get(recurso)
    if categoria is None:
        return None
    nome = dict(_NOME_NA_FRASE)[recurso]

    if (
        recurso == "touchpad"
        and isinstance(item, dict)
        and item.get("touchpad_pressionado") is True
    ):
        return EstadoDoRecurso(SITUACAO_CHEGANDO, nome)

    idade = visto.get(categoria)
    if not isinstance(idade, (int, float)) or isinstance(idade, bool):
        situacao = SITUACAO_NUNCA
    elif idade <= ATIVIDADE_FRESCA_S:
        situacao = SITUACAO_CHEGANDO
    else:
        situacao = SITUACAO_PARADO

    if recurso == "vibracao" and situacao == SITUACAO_CHEGANDO:
        if not pedido_de_vibracao_fresco(item):
            situacao = SITUACAO_PARADO
        else:
            motores = motores_no_fisico(item)
            if motores is not None:
                nome = f"{nome} (motores: {motores[0]}/{motores[1]})"

    return EstadoDoRecurso(situacao, nome)


def resumo_do_que_chega_ao_jogo(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> str | None:
    """A linha que responde *"vai funcionar na hora de jogar?"*; ``None`` = some."""
    if bool(state_global.get("native_mode")):
        return "Modo Nativo: o jogo fala direto com o controle — tudo chega."
    if _mascara_e_xbox(state_global):
        # esses DOIS" enquanto `home_actions.TEXTO_CUSTO_MASCARA_XBOX` já dizia
        return (
            "Máscara Xbox 360: giroscópio, acelerômetro e touchpad não chegam "
            "ao jogo — o controle de Xbox não tem esses três. Vibração, luz e "
            "gatilho vão."
        )
    if _visto_ha_s_do_vpad(entry, state_global) is None:
        return None

    por_situacao: dict[str, list[str]] = {}
    for recurso, _nome in _NOME_NA_FRASE:
        estado = estado_do_recurso(recurso, entry, state_global)
        if estado is None:
            continue
        por_situacao.setdefault(estado.situacao, []).append(estado.frase)

    partes = []
    if por_situacao.get(SITUACAO_CHEGANDO):
        partes.append(
            "No jogo agora: " + ", ".join(por_situacao[SITUACAO_CHEGANDO])
        )
    if por_situacao.get(SITUACAO_PARADO):
        partes.append("pararam: " + ", ".join(por_situacao[SITUACAO_PARADO]))
    if por_situacao.get(SITUACAO_NUNCA):
        partes.append(
            "sem pedido ainda: " + ", ".join(por_situacao[SITUACAO_NUNCA])
        )
    if not partes:
        return None
    texto = " · ".join(partes) + "."
    return texto[0].upper() + texto[1:]


def frase_mais_longa_do_que_chega_ao_jogo() -> str:
    """A MAIOR frase que :func:`resumo_do_que_chega_ao_jogo` sabe montar.

    NAO-DANCA-01 (13/08/2026). Ela não é para ser mostrada a ninguém: é a
    régua que reserva a altura da linha da verdade no card, para que a frase
    encolher ou crescer não mova mais nada — o defeito que ela relatou assim:
    *"não sei se dá pra ver mas o layout fica sambando aqui na interface"*.

    **Por que a maior frase, e não um número de linhas escrito à mão.** A
    altura que se reserva tem de ser a altura MÁXIMA que a frase pode pedir,
    e essa altura depende da largura que o card recebeu e da escala de fonte
    dela — as duas mudam. Um "2" cravado no código seria um número inventado
    que envelhece calado no dia em que um recurso ganhar nome mais longo.

    O que torna esta frase a maior, item por item:

    * **os TRÊS grupos aparecem**. Os seis recursos estão sempre na frase; o
      que muda é como se repartem. Com os três prefixos na tela ("No jogo
      agora: ", "pararam: ", "sem pedido ainda: ") e os dois " · " que os
      separam, o texto fixo é o mais longo possível — e o número de ", " entre
      nomes é o mesmo em qualquer repartição (seis nomes menos três grupos);
    * **os dois detalhes numéricos entram**, e os dois só existem na situação
      "chegando" (o `(~N Hz)` do giroscópio e o `(motores: a/b)` da vibração),
      então os dois moram no primeiro grupo;
    * **os números vão no maior tamanho que podem ter**: o Hz com quatro
      dígitos e os motores com os três de 255, que é o teto de um byte.

    Deriva de :data:`_NOME_NA_FRASE` de propósito: ela é a lista-dona dos
    recursos, e uma cópia dos nomes aqui viraria mentira no primeiro rename.
    """
    nomes = dict(_NOME_NA_FRASE)
    com_detalhe = ("giroscopio", "vibracao")
    chegando = [
        f"{nomes['giroscopio']} (~{_HZ_MAIS_LARGO} Hz)",
        f"{nomes['vibracao']} (motores: {_MOTOR_MAIS_LARGO}/{_MOTOR_MAIS_LARGO})",
    ]
    restantes = [
        nome for recurso, nome in _NOME_NA_FRASE if recurso not in com_detalhe
    ]
    meio = len(restantes) // 2
    partes = [
        "No jogo agora: " + ", ".join(chegando),
        "pararam: " + ", ".join(restantes[:meio]),
        "sem pedido ainda: " + ", ".join(restantes[meio:]),
    ]
    return " · ".join(partes) + "."


def _mascara_e_xbox(
    state_global: dict[str, Any], entry: dict[str, Any] | None = None
) -> bool:
    """True quando ESTE controle está com a máscara de Xbox 360.

    **O SUJEITO É O CONTROLE, E ATÉ 21/09/2026 ERA A SESSÃO.** A função lia só
    `gamepad_emulation.flavor` — o GLOBAL —, e a máscara por aparelho existe
    desde a MASCARA-NO-PERFIL-01 (08/09), com ordem escrita: o degrau 1
    (`controllers[uniq].mascara` do perfil ativo) **vence** o degrau 2
    (`mode.gamepad_flavor`). Ler só o degrau 2 é perguntar a quem perde.

    Medido na mesa dela naquele dia, com o perfil PRAGMATA:

        flavor (global) = "xbox"
        por_aparelho    = {os quatro: "dualsense"}

    A máscara efetiva dos quatro era DualSense, e a tela dizia Xbox — e com
    ela vinha a frase do giroscópio, que ela leu e recusou: *"essa frase não
    deveria existir"*. **As duas queixas eram o mesmo defeito.**

    O `flavor` continua sendo o FALLBACK, e não some: é o que responde quando
    aquele controle não escolheu, que é a regra de herança da D-5 (*máscara do
    JOGADOR, com a do jogo como padrão herdado*).

    `entry` opcional preserva os chamadores que perguntam pela SESSÃO — há
    um, e ele é legítimo: o custo da máscara na aba Jogar fala do modo inteiro.
    """
    gamepad = state_global.get("gamepad_emulation")
    if not isinstance(gamepad, dict):
        return False
    if entry is not None:
        uniq = uniq_do_entry(entry)
        por_aparelho = gamepad.get("por_aparelho")
        if uniq and isinstance(por_aparelho, dict):
            dele = por_aparelho.get(uniq)
            if isinstance(dele, str) and dele:
                return dele == "xbox"
    return gamepad.get("flavor") == "xbox"


def gyro_do_inputs(inputs: Any) -> tuple[float, float, float] | None:
    """``(x, y, z)`` em graus/s do bloco ``inputs.gyro``; None = sem sensor."""
    if not isinstance(inputs, dict):
        return None
    bloco = inputs.get("gyro")
    if not isinstance(bloco, dict):
        return None
    try:
        return (
            float(bloco["x"]),
            float(bloco["y"]),
            float(bloco["z"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def accel_do_inputs(inputs: Any) -> tuple[float, float, float] | None:
    """``(x, y, z)`` em **g** do bloco ``inputs.accel``; None = sem sensor."""
    if not isinstance(inputs, dict):
        return None
    bloco = inputs.get("accel")
    if not isinstance(bloco, dict):
        return None
    try:
        return (
            float(bloco["x"]),
            float(bloco["y"]),
            float(bloco["z"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def touchpad_do_inputs(inputs: Any) -> tuple[bool, float, float] | None:
    """``(tocando, fx, fy)`` do bloco ``inputs.touchpad``; None = sem sensor."""
    if not isinstance(inputs, dict):
        return None
    bloco = inputs.get("touchpad")
    if not isinstance(bloco, dict):
        return None
    try:
        fx, fy = posicao_normalizada(
            int(bloco["x"]),
            int(bloco["y"]),
            int(bloco.get("width", 1920)),
            int(bloco.get("height", 1080)),
        )
    except (KeyError, TypeError, ValueError):
        return None
    return (bool(bloco.get("touching")), fx, fy)


def dedos_do_inputs(inputs: Any) -> tuple[tuple[float, float], ...] | None:
    """Os dedos apoiados AGORA, normalizados 0..1; ``None`` = sem sensor.

    MULTITOQUE-01 (18/09/2026). O DualSense tem DOIS pontos de toque no
    hardware (`ABS_MT_SLOT 0..1`, medido no aparelho dela), e o payload os
    traz em ``touchpad.pontos``. Três respostas, e as três são diferentes:

    - ``None`` — não há bloco de touchpad: **não sei**, o desenho some.
    - ``()`` — há bloco e nenhum dedo: **ninguém está tocando**.
    - N tuplas — os dedos, em ordem de slot do kernel.

    **O caso do payload VELHO, e ele é o que evita o dedo fantasma:** um
    daemon anterior a esta data publica ``touching``/``x``/``y`` e NÃO
    publica ``pontos``. Aí o resumo vira um dedo só — a verdade que aquele
    daemon sabe dizer —, em vez de "nenhum dedo", que apagaria o toque na
    tela de quem ainda não atualizou o serviço.
    """
    if not isinstance(inputs, dict):
        return None
    bloco = inputs.get("touchpad")
    if not isinstance(bloco, dict):
        return None
    largura = int(bloco.get("width", 1920) or 1920)
    altura = int(bloco.get("height", 1080) or 1080)
    pontos = bloco.get("pontos")
    if isinstance(pontos, list):
        saida: list[tuple[float, float]] = []
        for ponto in pontos:
            if not isinstance(ponto, dict):
                continue
            try:
                saida.append(
                    posicao_normalizada(
                        int(ponto["x"]), int(ponto["y"]), largura, altura
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return tuple(saida)
    # Payload sem `pontos`: cai para o resumo (ver a docstring).
    lido = touchpad_do_inputs(inputs)
    if lido is None:
        return None
    return ((lido[1], lido[2]),) if lido[0] else ()


def speaker_do_entry(entry: Any) -> tuple[int, bool | None] | None:
    """``(volume 0-255, muted)`` do alto-falante; ``None`` = sem dado."""
    bloco: Any = None
    if isinstance(entry, dict):
        bloco = entry.get("speaker")
        if not isinstance(bloco, dict):
            inputs = entry.get("inputs")
            bloco = inputs.get("speaker") if isinstance(inputs, dict) else None
    if not isinstance(bloco, dict):
        return None
    volume = bloco.get("volume")
    if isinstance(volume, bool) or not isinstance(volume, (int, float)):
        return None
    muted = bloco.get("muted")
    return (
        max(0, min(255, round(volume))),
        muted if isinstance(muted, bool) else None,
    )


class AcaoMic(NamedTuple):
    """O que o botão do microfone diz e o que ele manda quando clicado."""

    rotulo: str
    valor: bool | None
    sensivel: bool
    dica: str


def acao_mic(entry: Any) -> AcaoMic:
    """Estado do botão de microfone a partir de ``entry['audio']``."""
    audio = entry.get("audio") if isinstance(entry, dict) else None
    if not isinstance(audio, dict):
        return AcaoMic(TEXTO_BOTAO_MIC_SEM_LEITURA, None, False, DICA_MIC_SEM_LEITURA)
    mudo = audio.get("mic_mudo")
    if not isinstance(mudo, bool):
        return AcaoMic(TEXTO_BOTAO_MIC_SEM_LEITURA, None, False, DICA_MIC_SEM_LEITURA)
    if mudo:
        return AcaoMic(TEXTO_BOTAO_MIC_ATIVAR, False, True, DICA_MIC_ATIVAR)
    if isinstance(audio.get("mic_mudo_desejado"), bool):
        return AcaoMic(TEXTO_BOTAO_MIC_DEVOLVER, None, True, DICA_MIC_DEVOLVER)
    return AcaoMic(TEXTO_BOTAO_MIC_SILENCIAR, True, True, DICA_MIC_SILENCIAR)


class AcaoSpeaker(NamedTuple):
    """O que um botão do alto-falante diz e o que ele manda quando clicado.

    ``muted`` é o argumento homônimo de ``ipc_bridge.speaker_set`` (``None`` =
    não mexer no mudo) e ``release`` pede a DEVOLUÇÃO da posse. Nenhum dos dois
    carrega volume: volume só sai do controle deslizante, e sempre explícito.
    """

    rotulo: str
    muted: bool | None
    release: bool
    sensivel: bool
    dica: str


def acao_speaker_mudo(entry: Any) -> AcaoSpeaker:
    """Estado do botão de MUDO do alto-falante (SOM-02, entrega 2).

    A tabela, e cada linha vem de medição:

    ==============================  ==========  ===================
    estado                          rótulo      manda
    ==============================  ==========  ===================
    sem volume conhecido            sem dado    (insensível)
    tocando, posse nossa            Silenciar   ``muted=True``
    mudo por nossa ordem            Ativar      ``muted=False``
    ==============================  ==========  ===================

    **A primeira linha é INSENSÍVEL, e isso é a entrega.** A chave ``speaker``
    só existe depois de um ``speaker.set`` nosso com volume; antes dela, um
    ``muted=True`` faria o backend assumir a posse com preferência ZERO, e o
    ``muted=False`` seguinte "restauraria" essa preferência — o par tranca o
    alto-falante em ``{'volume': 0, 'muted': True}`` e o próprio botão não tem
    como soltá-lo (armadilha 2 da SOM-02, executada contra o backend real).

    O botão fica insensível em vez de sumir, pela mesma regra do microfone:
    sumir muda a largura dos vizinhos e é indistinguível de "este controle não
    tem alto-falante" (MIC-PRESENTE-01).
    """
    dados = speaker_do_entry(entry)
    if dados is None:
        return AcaoSpeaker(
            TEXTO_BOTAO_SPEAKER_SEM_DADO, None, False, False, DICA_SPEAKER_SEM_DADO
        )
    _volume, muted = dados
    if muted:
        return AcaoSpeaker(
            TEXTO_BOTAO_SPEAKER_ATIVAR, False, False, True, DICA_SPEAKER_ATIVAR
        )
    return AcaoSpeaker(
        TEXTO_BOTAO_SPEAKER_SILENCIAR, True, False, True, DICA_SPEAKER_SILENCIAR
    )


def acao_speaker_devolucao(entry: Any) -> AcaoSpeaker:
    """Estado do botão de DEVOLUÇÃO da posse (SOM-02, entrega 3).

    Sensível exatamente quando há posse — que é o mesmo que dizer "quando a
    chave ``speaker`` existe", porque o daemon só a publica enquanto o volume
    for nosso. Sem posse não há o que devolver, e mandar ``release`` ali seria
    pedir ao daemon que soltasse um byte que ele nunca tomou.

    O rótulo não muda de estado: ele já diz o que o clique faz. O que muda é a
    dica, e ela é HONESTA sobre o limite — devolver para de mandar o volume, e
    o firmware fica com o ÚLTIMO valor que mandamos. Não existe leitura, logo
    não existe restauração: prometer que o volume anterior volta seria a mesma
    família de mentira que a SOM-01 recusou ao não publicar ``0 %``.
    """
    if speaker_do_entry(entry) is None:
        return AcaoSpeaker(
            TEXTO_BOTAO_SPEAKER_DEVOLVER,
            None,
            False,
            False,
            DICA_SPEAKER_DEVOLVER_SEM_POSSE,
        )
    return AcaoSpeaker(
        TEXTO_BOTAO_SPEAKER_DEVOLVER, None, True, True, DICA_SPEAKER_DEVOLVER
    )


def saida_muda_do_entry(entry: Any, mic: Any = None) -> bool | None:
    """A CAMADA 1 (o sink do PipeWire) está muda? ``None`` = não dá para saber.

    SENSOR-VIVO-01/E5 e SOM-02/E5, item 4 — são a mesma verdade vista dos dois
    lados. Com o sink do controle mudo no PipeWire, mover o volume do
    registrador HID (a camada 2, a única que a janela alcança nos dois
    transportes) não produz som nenhum: o bloco ficaria dizendo uma
    porcentagem enquanto nada sai.

    Duas posições aceitas, nesta ordem, e nenhuma delas inventada aqui:

    1. o PAYLOAD do daemon, em ``speaker.saida_muda`` ou ``audio.saida_muda`` —
       é onde a leitura mora quando quem lê o PipeWire é o daemon;
    2. a leitura do microfone da própria janela (``LeituraMic.saida_muda``), lida
       por ``getattr`` defensivo — é onde ela mora se quem passar a ler o sink
       for o ``app/mic_monitor.py``, que já é o leitor de PipeWire desta
       interface e já roda fora da thread GTK.

    **A posição 2 EXISTE desde então, e é por ela que o selo acende hoje.** O
    ``MicMonitor`` ganhou a thread supervisora do sink (``_saidas_mudas``,
    `app/mic_monitor.py:335`, preenchida em `:622` e servida em `:510`), e a
    ``LeituraMic`` carrega o campo. A posição 1 (o daemon publicar
    ``speaker.saida_muda``) continua não existindo, e continua sendo um encaixe
    válido — quem a implementar não precisa tocar no card.

    Isto **substitui** a afirmação anterior desta docstring ("hoje nenhuma das
    duas existe", medida em 01/08/2026), que caducou sem que ninguém percebesse
    e custou uma bancada: em 17/08 o JANELA-CORTADA-01 tentou revelar o selo
    montando um card com ``speaker={"muted": True}`` e concluiu que ele "continua
    escondido". Continua mesmo — ``muted`` é a camada 2 (o registrador HID) e
    esta função lê a camada 1 (o sink do PipeWire). São chaves diferentes, de
    camadas diferentes, e a docstring errada apontava para o lugar errado.
    A chave que acende é ``speaker.saida_muda`` (ou ``audio.saida_muda``).

    Só ``True`` acende o selo. ``False`` (a saída está aberta) e ``None`` (não
    sabemos) mostram a mesma coisa — nada —, porque um selo "saída viva" seria
    ruído em cima do que a barra já diz.
    """
    inputs = entry.get("inputs") if isinstance(entry, dict) else None
    for dono in (entry, inputs):
        if not isinstance(dono, dict):
            continue
        for bloco_nome in ("speaker", "audio"):
            bloco = dono.get(bloco_nome)
            if isinstance(bloco, dict):
                valor = bloco.get("saida_muda")
                if isinstance(valor, bool):
                    return valor
    valor = getattr(mic, "saida_muda", None)
    return valor if isinstance(valor, bool) else None


def uniq_do_entry(entry: Any) -> str | None:
    """O endereço DESTE controle, ou ``None`` — a regra, num lugar só."""
    uniq = entry.get("uniq") if isinstance(entry, dict) else None
    if isinstance(uniq, str) and uniq.strip():
        return uniq
    return None


def audio_sem_endereco(entry: Any) -> bool:
    """O bloco de som deste card tem de ficar DESLIGADO? (função pura)"""
    return uniq_do_entry(entry) is None


def frase_do_alvo_do_mic(honrado: bool | None) -> str:
    """O que dizer sobre DE QUEM foi o microfone que o daemon mexeu (função pura)."""
    return TEXTO_MIC_ALVO_NAO_HONRADO if honrado is False else ""


def accent_do_card(entry: dict[str, Any], state_global: dict[str, Any]) -> RGB:
    """Cor AJUSTADA dos traços do card (contraste mínimo garantido).

    Base = cor da lightbar quando conhecida (via :func:`rotulo_lightbar`);
    sem cor conhecida, o neutro ``ACCENT_NEUTRO`` — sempre passado por
    ``ensure_min_contrast`` (o neutro cru rende ~2.6:1, ilegível de traço).
    """
    _rotulo, base = rotulo_lightbar(entry, state_global)
    return ensure_min_contrast(base if base is not None else ACCENT_NEUTRO)


def cor_do_swatch(entry: Any) -> RGB | None:
    """A cor CRUA do quadradinho ao lado do título. ``None`` = desconhecida."""
    return _rgb3(entry.get("lightbar_rgb") if isinstance(entry, dict) else None)


def desenhar_swatch(
    ctx: Any, largura: int, altura: int, rgb: RGB | None
) -> None:
    """Desenha o quadradinho de cor num contexto cairo já posicionado."""
    if rgb is not None:
        ctx.set_source_rgb(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
        ctx.rectangle(0, 0, largura, altura)
        ctx.fill()
    ctx.set_source_rgb(
        ACCENT_NEUTRO[0] / 255,
        ACCENT_NEUTRO[1] / 255,
        ACCENT_NEUTRO[2] / 255,
    )
    ctx.set_line_width(1)
    ctx.rectangle(0.5, 0.5, largura - 1, altura - 1)
    ctx.stroke()


LADO_DO_SWATCH: Final[int] = 14


try:
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk, Pango

    from hefesto_dualsense4unix.app.widgets.segmented_selector import (
        SegmentedSelector,
    )

    _GTK_DISPONIVEL = all(
        hasattr(Gtk, attr)
        for attr in (
            "Frame",
            "Box",
            "Button",
            "Grid",
            "Label",
            "ProgressBar",
            "DrawingArea",
            "Align",
            "Orientation",
        )
    )
except (ImportError, ValueError):
    _GTK_DISPONIVEL = False


if _GTK_DISPONIVEL:

    class ControllerCard(Gtk.Frame):  # type: ignore[misc]
        """Card de UM controle físico na aba Status.

        Uso (a mixin de status monta e distribui — STATUS-02)::

            card = ControllerCard(compact=False, mostrar_estado_global=True)
            card.update(entry, state_full)        # diff interno por seção
            card.reset_inputs()                   # IPC falhou → mostra "—"

        **`compact=False` não é um exemplo entre outros: é o único que
        produção constrói.** Desde a EMPILHA-02 (02/08/2026, decisão dela —
        um card por linha, com rolagem) a aba dá a largura inteira a todo
        card, e `status_actions._rebuild_status_cards` passa `compact=False`
        sempre. O que continua dependendo da quantidade é
        `mostrar_estado_global`: com 2+ controles quem responde por perfil e
        daemon é o frame "Estado", e repeti-lo em cada card seria a
        duplicação que a STATUS-SIMETRIA-02 curou na bateria.

        CORREÇÃO DE FATO (25/08/2026, STATUS-DIZ-O-QUE-VÊ-01/T5): este
        exemplo dizia que `compact` era o modo de 2+ cards. Ficou falso
        naquele 02/08 e atravessou 23 dias, com sete arquivos de teste
        medindo — e travando — um desenho que nenhuma janela monta.

        ``entry`` é uma entrada de ``state_full.controllers`` (contrato em
        ``daemon/ipc_handlers._enrich_controllers_per_controller``);
        ``state_full`` inteiro entra como contexto global (``native_mode``).
        """

        def __init__(
            self,
            *,
            compact: bool = False,
            mostrar_estado_global: bool | None = None,
        ) -> None:
            super().__init__()
            self._compact = compact
            self._mostrar_estado_global = (
                (not compact)
                if mostrar_estado_global is None
                else mostrar_estado_global
            )
            self._espaco = (
                _ESPACO_FAIXA_COMPACTO if compact else _ESPACO_FAIXA_UNICO
            )
            self._last_titulo: str | None = None
            self._last_dica_titulo: str | None = None
            self._last_battery: Any = _SENTINELA
            self._last_lightbar: Any = _SENTINELA
            self._last_degradacao: Any = _SENTINELA
            self._last_motion: Any = _SENTINELA
            self._last_verdade: Any = _SENTINELA
            self._accent: RGB | None = None
            self._accent_hex: str = rgb_para_hex(
                ensure_min_contrast(ACCENT_NEUTRO)
            )
            self._swatch_rgb: RGB | None = None
            self._sem_leitor: bool | None = None
            self._last_l2: int | None = None
            self._last_r2: int | None = None
            self._last_lx: int | None = None
            self._last_ly: int | None = None
            self._last_rx: int | None = None
            self._last_ry: int | None = None
            self._last_buttons: frozenset[str] | None = None
            self._last_l2_lit: bool | None = None
            self._last_r2_lit: bool | None = None
            self._l3_pressed = False
            self._r3_pressed = False
            self._glyphs: dict[str, ButtonGlyph] = {}
            self._last_gyro: Any = _SENTINELA
            self._last_accel: Any = _SENTINELA
            self._last_touch: Any = _SENTINELA
            self._last_mic: Any = _SENTINELA
            self._last_speaker: Any = _SENTINELA
            self._uniq: str | None = None
            self._audio_sem_endereco: bool | None = None
            self._mic_acao: AcaoMic | None = None
            self._speaker_acao_mudo: AcaoSpeaker | None = None
            self._speaker_acao_devolucao: AcaoSpeaker | None = None
            self._speaker_arrastando = False
            self._speaker_canal_pintando = False
            self._pedir_rota_do_sistema: Any = None
            self._dono_do_rascunho: Any = None
            self._speaker_lido: tuple[int, bool | None] | None = None
            self._speaker_pintando = False
            self._speaker_repouso_id: int | None = None
            self._speaker_volume_enviado: int | None = None
            # SOM-04 — o som de confirmação. O DualSense não devolve o volume
            # no RÁDIO, onde o DualSense não publica placa de som nenhuma (a
            self._speaker_sink = ""
            self._speaker_recado_do_som = ""
            # `_aplicar_selo_do_som` precisa dos dois para decidir a prioridade.
            self._speaker_saida_muda: bool | None = None
            # lugar? Os dois entram de FORA (`definir_estado_do_canal`), pela
            self._speaker_canal_estado = ""
            self._speaker_regra_do_sono: bool | None = None
            self._montar_ui()
            self.connect("destroy", lambda _w: self._cancelar_repouso_do_volume())
            self.connect("destroy", lambda _w: self._cancelar_repouso_do_mic())


        def update(
            self,
            entry: dict[str, Any],
            state_global: dict[str, Any],
            mic: Any = None,
        ) -> None:
            """Atualiza o card a partir de ``controllers[i]`` (diff interno).

            ``mic`` é a `LeituraMic` do `MicMonitor` da GUI (nível + mute) —
            opcional porque o microfone é o único sensor que NÃO vem pelo
            IPC: quem captura é a própria interface, só enquanto a aba Status
            está visível. ``None`` = sem microfone atribuível a este controle,
            e o módulo some.
            """
            self._uniq = uniq_do_entry(entry)
            self._update_titulo(entry, state_global)
            self._update_bateria(entry)
            self._update_lightbar(entry, state_global)
            self._update_degradacao(entry)
            self._update_motion(entry, state_global)
            self._update_verdade(entry, state_global)
            self._update_inputs(entry.get("inputs"))
            self._update_gyro(entry.get("inputs"))
            self._update_accel(entry.get("inputs"))
            self._update_touchpad(entry.get("inputs"))
            self._update_mic(mic, str(entry.get("transport") or ""))
            self._update_mic_botao(entry)
            self._update_speaker(entry, mic)
            self._update_guarda_de_audio()

        def reset_inputs(self) -> None:
            """IPC sem resposta: mostra "—" — nunca o último valor como vivo."""
            self._mostrar_sem_leitor()


        def do_size_allocate(self, allocation: Any) -> None:
            """Teto ELÁSTICO do card de um controle (SOM-01, pedido 3).

            O GTK3 não tem largura máxima: `set_size_request` declara o
            MÍNIMO, e `halign=CENTER` com um mínimo declarado trava o widget
            naquele número exato — era assim que o card ficava em 960px com a
            janela em 1920 e sobravam ~950px de margem morta.

            Aqui o card aceita toda a largura que a aba der até
            :data:`LARGURA_CARD_ELASTICA` e devolve o excedente como margem,
            centrando-se. Abaixo do teto ele cresce junto com a janela, que é
            o pedido; acima dele para de crescer, que é o que impede a sobra
            de voltar a virar buraco entre os blocos.

            A alocação recebida NÃO é mutada: ela é a variável local do
            `gtk_widget_size_allocate` do pai, usada depois para o clip. O
            corte vai numa CÓPIA (`.copy()` do próprio retângulo, que já é um
            `Gdk.Rectangle` — sem import novo neste módulo).
            """
            if allocation.width > LARGURA_CARD_ELASTICA:
                sobra = allocation.width - LARGURA_CARD_ELASTICA
                cortado = allocation.copy()
                cortado.x = allocation.x + sobra // 2
                cortado.width = LARGURA_CARD_ELASTICA
                allocation = cortado
            Gtk.Frame.do_size_allocate(self, allocation)

        def _montar_ui(self) -> None:
            if not self._compact:
                self.set_size_request(LARGURA_CARD_UNICO, -1)
                self.set_halign(Gtk.Align.FILL)
                self.set_hexpand(True)
            header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            swatch = Gtk.DrawingArea()
            swatch.set_size_request(LADO_DO_SWATCH, LADO_DO_SWATCH)
            swatch.set_valign(Gtk.Align.CENTER)
            swatch.connect("draw", self._on_draw_swatch)
            self._swatch = swatch
            header.pack_start(swatch, False, False, 0)
            titulo = Gtk.Label(label="Controle")
            titulo.set_xalign(0.0)
            self._title_label = titulo
            header.pack_start(titulo, False, False, 0)
            header.show_all()
            self.set_label_widget(header)

            corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            corpo.set_margin_top(10)
            corpo.set_margin_bottom(10)
            corpo.set_margin_start(12)
            corpo.set_margin_end(12)
            corpo.get_style_context().add_class("hefesto-dualsense4unix-card")
            self.add(corpo)
            self._montar_estado_global(corpo)

            # na tela dela. A regra antiga ("aparece uma vez só") continua
            linha_bateria = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=12
            )
            cap_bateria = Gtk.Label(label="Bateria:")
            cap_bateria.set_xalign(1.0)
            linha_bateria.pack_start(cap_bateria, False, False, 0)
            bateria = Gtk.ProgressBar()
            self._battery_bar = bateria
            bateria.set_show_text(False)
            bateria.set_text("— %")
            bateria.set_valign(Gtk.Align.CENTER)
            bateria.set_size_request(LARGURA_BARRA_BATERIA_CARD, -1)
            linha_bateria.pack_start(bateria, False, False, 0)
            pct = Gtk.Label(label="— %")
            pct.set_xalign(0.0)
            self._battery_pct_label = pct
            linha_bateria.pack_start(pct, False, False, 0)
            self._battery_row = linha_bateria
            if self._compact:
                corpo.pack_start(linha_bateria, False, False, 0)

            rotulo = Gtk.Label()
            rotulo.set_xalign(0.0)
            rotulo.get_style_context().add_class("dim-label")
            rotulo.set_no_show_all(True)
            rotulo.hide()
            self._lightbar_label = rotulo
            corpo.pack_start(rotulo, False, False, 0)

            badge = Gtk.Label()
            badge.set_xalign(0.0)
            badge.set_line_wrap(True)
            badge.get_style_context().add_class(
                "hefesto-dualsense4unix-status-warn"
            )
            badge.set_no_show_all(True)
            badge.hide()
            self._degradacao_badge = badge
            corpo.pack_start(badge, False, False, 0)

            aviso = Gtk.Label(label=TEXTO_AUDIO_SEM_ENDERECO)
            aviso.set_xalign(0.0)
            aviso.set_line_wrap(True)
            aviso.get_style_context().add_class(
                "hefesto-dualsense4unix-status-warn"
            )
            aviso.set_no_show_all(True)
            aviso.hide()
            self._audio_aviso = aviso
            corpo.pack_start(aviso, False, False, 0)

            aviso_alvo = Gtk.Label(label=TEXTO_MIC_ALVO_NAO_HONRADO)
            aviso_alvo.set_xalign(0.0)
            aviso_alvo.set_line_wrap(True)
            aviso_alvo.get_style_context().add_class(
                "hefesto-dualsense4unix-status-warn"
            )
            aviso_alvo.set_no_show_all(True)
            aviso_alvo.hide()
            self._mic_aviso_alvo = aviso_alvo
            corpo.pack_start(aviso_alvo, False, False, 0)

            motion = Gtk.Label()
            motion.set_xalign(0.0)
            motion.get_style_context().add_class("dim-label")
            motion.set_no_show_all(True)
            motion.hide()
            self._motion_label = motion
            if self._compact:
                corpo.pack_start(motion, False, False, 0)
            else:
                #
                # ao lado da bateria — *"a bateria fica ao lado do hertz do
                faixa = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=12
                )
                faixa.pack_start(motion, False, False, 0)
                linha_bateria.set_halign(Gtk.Align.END)
                faixa.pack_end(linha_bateria, False, False, 0)
                corpo.pack_start(faixa, False, False, 0)
                self._faixa_gyro_bateria = faixa
                corpo.reorder_child(faixa, 1)

            sem_leitor = Gtk.Label(label="—")
            sem_leitor.get_style_context().add_class("dim-label")
            sem_leitor.set_no_show_all(True)
            sem_leitor.hide()
            self._sem_leitor_label = sem_leitor
            corpo.pack_start(sem_leitor, False, False, 0)

            area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            self._inputs_area = area
            corpo.pack_start(area, False, False, 0)
            area.pack_start(self._montar_gatilhos_e_gyro(), False, False, 0)
            area.pack_start(self._montar_linha_inferior(), False, False, 0)

        def _montar_estado_global(self, corpo: Any) -> None:
            """A linha ``Perfil ativo: <v>    Hefesto: <v>``, no topo do card."""
            self._perfil_ativo_label = None
            self._daemon_label = None
            self._linha_estado_global = None
            self._verdade_label = None
            if self._compact:
                return

            verdade = RotuloDeAlturaReservada()
            verdade.set_xalign(0.0)
            verdade.set_halign(Gtk.Align.START)
            verdade.set_line_wrap(True)
            verdade.set_max_width_chars(_VERDADE_MAX_CHARS)
            verdade.get_style_context().add_class("dim-label")
            verdade.set_no_show_all(True)
            verdade.hide()
            self._verdade_label = verdade

            if not self._mostrar_estado_global:
                return
            linha = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=6
            )
            cap_perfil = Gtk.Label(label="Perfil ativo:")
            cap_perfil.set_xalign(1.0)
            linha.pack_start(cap_perfil, False, False, 0)
            perfil = Gtk.Label(label=TEXTO_PERFIL_SEM_DADO)
            perfil.set_xalign(0.0)
            self._perfil_ativo_label = perfil
            linha.pack_start(perfil, False, False, 0)

            vao = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            linha.pack_start(vao, True, True, 0)

            cap_daemon = Gtk.Label(label="Hefesto:")
            cap_daemon.set_xalign(1.0)
            linha.pack_start(cap_daemon, False, False, 0)
            daemon = Gtk.Label(label=TEXTO_DAEMON_SEM_DADO)
            daemon.set_xalign(0.0)
            self._daemon_label = daemon
            linha.pack_start(daemon, False, False, 0)

            self._linha_estado_global = linha
            corpo.pack_start(linha, False, False, 0)


        def definir_estado_global(self, perfil: str, daemon: str) -> None:
            """Escreve o par ``Perfil ativo``/``Hefesto`` — chamada pela aba."""
            for rotulo, texto in (
                (self._perfil_ativo_label, perfil),
                (self._daemon_label, daemon),
            ):
                if rotulo is not None and texto and rotulo.get_text() != texto:
                    rotulo.set_text(texto)

        def _montar_gatilhos_e_gyro(self) -> Any:
            """Linha 1: gatilhos à esquerda, giroscópio à direita."""
            grid = Gtk.Grid()
            grid.set_column_spacing(self._espaco)
            gatilhos = self._montar_gatilhos()
            grid.attach(gatilhos, 0, 0, 1, 1)
            slot = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL, spacing=self._espaco
            )
            slot.pack_start(self._montar_gyro(), True, True, 0)
            slot.pack_start(self._montar_accel(), True, True, 0)
            self._gyro_slot = slot
            grid.attach(slot, 1, 0, 1, 1)

            self._grupo_coluna_esquerda = Gtk.SizeGroup(
                mode=Gtk.SizeGroupMode.HORIZONTAL
            )
            self._grupo_coluna_esquerda.add_widget(gatilhos)
            self._grupo_coluna_direita = Gtk.SizeGroup(
                mode=Gtk.SizeGroupMode.HORIZONTAL
            )
            self._grupo_coluna_direita.add_widget(slot)
            return grid

        def largura_da_barra_de_gatilho(self) -> int:
            """Teto da barra de L2/R2 neste card, em px."""
            if self._compact:
                return LARGURA_BARRA_GATILHO_COMPACTO
            return LARGURA_BARRA_GATILHO_UNICO

        def largura_do_giroscopio(self) -> int:
            """Teto da COLUNA de sensores de movimento neste card, em px."""
            if self._compact:
                return LARGURA_GYRO_COMPACTO
            return LARGURA_GYRO_UNICO

        def largura_do_meio_sensor(self) -> int:
            """Metade dela — o piso de CADA um dos dois desenhos, em px."""
            sobra = (
                self.largura_do_giroscopio()
                - self._espaco
                - 2 * CROMO_DA_MOLDURA_DE_SENSOR
            )
            return max(60, sobra // 2)

        def _montar_gatilhos(self) -> Any:
            """As duas barras de gatilho, com TETO de largura."""
            grid = Gtk.Grid()
            grid.set_row_spacing(6)
            grid.set_column_spacing(12)
            grid.set_valign(Gtk.Align.START)
            for linha, nome in enumerate(("L2", "R2")):
                cap = Gtk.Label(label=nome)
                cap.set_xalign(1.0)
                cap.set_width_chars(3)
                grid.attach(cap, 0, linha, 1, 1)
                barra = Gtk.ProgressBar()
                barra.set_show_text(True)
                barra.set_text("0 / 255")
                barra.set_size_request(self.largura_da_barra_de_gatilho(), -1)
                barra.set_halign(Gtk.Align.FILL)
                barra.set_hexpand(True)
                grid.attach(barra, 1, linha, 1, 1)
                if nome == "L2":
                    self._l2_bar = barra
                else:
                    self._r2_bar = barra
            return grid

        @staticmethod
        def _rotulo_secao(texto: str, *, elidir: bool = False) -> Any:
            """Rótulo pequeno de seção (mesmo peso visual do `dim-label`)."""
            label = Gtk.Label(label=texto)
            label.set_xalign(0.0)
            label.get_style_context().add_class("dim-label")
            if elidir:
                label.set_ellipsize(Pango.EllipsizeMode.END)
            return label

        def _bloco(self, titulo: str, *, elidir: bool = False) -> tuple[Any, Any]:
            """``(bloco, miolo)`` de UM assunto da faixa de leitura."""
            if self._compact:
                caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                caixa.pack_start(
                    self._rotulo_secao(titulo, elidir=elidir), False, False, 0
                )
                return caixa, caixa
            moldura = Gtk.Frame()
            moldura.set_label_widget(self._rotulo_secao(titulo, elidir=elidir))
            moldura.set_valign(Gtk.Align.START)
            miolo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            miolo.set_margin_top(4)
            miolo.set_margin_bottom(4)
            miolo.set_margin_start(6)
            miolo.set_margin_end(6)
            moldura.add(miolo)
            return moldura, miolo

        @staticmethod
        def _esconder_modulo(widget: Any) -> None:
            """Deixa o módulo pronto para aparecer, mas apagado."""
            widget.show_all()
            widget.set_no_show_all(True)
            widget.hide()

        def _montar_gyro(self) -> Any:
            caixa, miolo = self._bloco("Giroscópio (graus/s)", elidir=True)
            barras = GyroBars()
            _largura, altura = barras.get_size_request()
            barras.set_size_request(self.largura_do_meio_sensor(), altura)
            barras.set_halign(Gtk.Align.FILL)
            barras.set_hexpand(True)
            caixa.set_halign(Gtk.Align.FILL)
            miolo.pack_start(barras, True, True, 0)
            self._gyro_bars = barras
            self._gyro_box = caixa
            self._esconder_modulo(caixa)
            return caixa

        def _montar_accel(self) -> Any:
            """O acelerômetro, no MOLDE do giroscópio e AO LADO dele."""
            caixa, miolo = self._bloco("Acelerômetro (g)", elidir=True)
            barras = GyroBars(escala=ESCALA_ACCEL_G, texto=texto_eixo_g)
            _largura, altura = barras.get_size_request()
            barras.set_size_request(self.largura_do_meio_sensor(), altura)
            barras.set_halign(Gtk.Align.FILL)
            barras.set_hexpand(True)
            caixa.set_halign(Gtk.Align.FILL)
            miolo.pack_start(barras, True, True, 0)
            self._accel_bars = barras
            self._accel_box = caixa
            self._esconder_modulo(caixa)
            return caixa

        def _montar_linha_inferior(self) -> Any:
            """A faixa de leitura ao vivo, na ordem que a mantenedora pediu.

            STATUS-SIMETRIA-01 — *"a área do mic que deveria ficar à direita
            dos analógicos"*; SOM-01 — *"dava pra colocar o auto falante abaixo
            do microfone"*::

                [ Touchpad ]                 [ Microfone    ] [ ] [ ] [ ] [ ]
                [ Lightbar ] [ L3 ] [ R3 ]   [ Alto-falante ] [ ] [ ] [ ] [ ]
                                                              [ ] [ ] [ ] [ ]
                                                              [ ] [ ] [ ] [ ]

            O microfone continua DENTRO do card — a madrugada de 26/07 o mandou
            para o rodapé da aba, que é o oposto do pedido, e foi revertida.

            Cada módulo se esconde SOZINHO quando não há sensor: nenhum deles
            arrasta o vizinho, e nenhum deles leva os botões junto (a armadilha
            de LEGIBILIDADE-01, quando o grid morava dentro da linha que sumia).

            **A sobra de largura se reparte entre os TRÊS blocos da faixa.**
            Os três filhos entram com ``expand=True, fill=False``: cada um
            recebe um terço do excedente e fica CENTRADO no próprio pedaço, de
            modo que o que sobra vira o mesmo respiro em toda a faixa. Com a
            sobra indo só para o miolo (o que valia antes do teto elástico),
            ela se acumulava em dois vãos — e com o card podendo chegar a
            1400px seriam ~270px de nada de cada lado, acima do aceite de 200px
            que `test_status_faixa_blocos` cobra. `fill=False` é o que mantém
            os blocos com a largura do conteúdo: com `fill=True` a moldura de
            cada um esticaria e o vazio voltaria para DENTRO dos blocos.
            """
            linha = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=self._espaco,
            )

            esquerda = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=self._espaco,
            )
            esquerda.pack_start(self._montar_coluna_sensores(), True, False, 0)
            esquerda.pack_end(self._montar_sticks(), True, False, 0)
            self._metade_esquerda = esquerda
            self._grupo_coluna_esquerda.add_widget(esquerda)
            linha.pack_start(esquerda, True, True, 0)

            miolo = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=self._espaco,
            )
            miolo.pack_start(self._montar_coluna_audio(), True, False, 0)
            glyphs = self._montar_glyphs()
            glyphs.set_halign(Gtk.Align.END)
            miolo.pack_end(glyphs, True, False, 0)
            self._miolo_inferior = miolo
            self._grupo_coluna_direita.add_widget(miolo)
            linha.pack_start(miolo, True, True, 0)
            self._linha_inferior = linha
            return linha

        def _montar_coluna_sensores(self) -> Any:
            """Coluna da esquerda: touchpad e lightbar empilhados."""
            coluna = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=self._espaco // 2,
            )
            coluna.pack_start(self._montar_touchpad(), False, False, 0)
            coluna.pack_start(self._montar_lightbar(), False, False, 0)
            coluna.set_valign(Gtk.Align.START)
            self._coluna_sensores = coluna
            return coluna

        def _montar_coluna_audio(self) -> Any:
            """Coluna do SOM: microfone e, logo abaixo dele, o alto-falante."""
            coluna = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL,
                spacing=self._espaco // 2,
            )
            coluna.pack_start(self._montar_mic(), False, False, 0)
            coluna.pack_start(self._montar_speaker(), False, False, 0)
            coluna.set_valign(Gtk.Align.START)
            self._coluna_audio = coluna
            return coluna

        def _montar_touchpad(self) -> Any:
            touch, miolo = self._bloco("Touchpad")
            painel = TouchpadView()
            if not self._compact:
                # O piso é o de sempre; o teto de crescimento é o natural.
                painel.set_size_request(*_TOUCHPAD_PX_UNICO)
                painel.definir_largura_natural(_DESENHO_NATURAL_PX_UNICO)
            miolo.pack_start(painel, False, False, 0)
            rotulo = self._rotulo_secao(texto_toques(0))
            miolo.pack_start(rotulo, False, False, 0)
            self._touch_view = painel
            self._touch_label = rotulo
            self._touch_box = touch
            self._esconder_modulo(touch)
            return touch

        def _montar_mic(self) -> Any:
            """Bloco PRÓPRIO do microfone, à direita dos dois analógicos.

            MIC-PRESENTE-01 — ele NUNCA se esconde. Esconder um widget de uma
            faixa horizontal muda a largura de todos os vizinhos: além de o
            microfone desaparecer (e sumir é indistinguível de "não existe"),
            os analógicos e o grid de botões pulavam de lugar a cada vez que
            ele entrava ou saía — e por Bluetooth ele sai quase sempre, porque
            a captura é Opus tunelado em HID e é instável.

            A largura fica reservada por construção, em dois pontos: o campo
            fixo do rótulo de estado (`_MIC_ESTADO_CHARS`, medido pela mais
            longa das frases) e um `Gtk.SizeGroup` HORIZONTAL amarrando o
            medidor ao rótulo — os dois passam a ter a largura do maior, e
            trocar de estado não mexe em nenhuma das duas.
            """
            mic, miolo = self._bloco("Microfone")
            medidor = MicMeter()
            medidor.set_valign(Gtk.Align.CENTER)
            if not self._compact:
                medidor.set_size_request(*_MIC_METER_PX_UNICO)
                medidor.definir_largura_natural(_DESENHO_NATURAL_PX_UNICO)
            miolo.pack_start(medidor, False, False, 0)
            selo = Gtk.Label()
            selo.set_valign(Gtk.Align.CENTER)
            selo.set_halign(Gtk.Align.START)
            selo.set_width_chars(_MIC_ESTADO_CHARS)
            selo.set_max_width_chars(_MIC_ESTADO_CHARS)
            selo.get_style_context().add_class("hefesto-selo")
            miolo.pack_start(selo, False, False, 0)
            # Ele entra ABAIXO do medidor porque o miolo do bloco é vertical:
            botao = Gtk.Button()
            botao.set_halign(Gtk.Align.FILL)
            rotulo_botao = Gtk.Label(label=TEXTO_BOTAO_MIC_SEM_LEITURA)
            rotulo_botao.set_ellipsize(Pango.EllipsizeMode.END)
            rotulo_botao.set_max_width_chars(_MIC_ESTADO_CHARS)
            botao.add(rotulo_botao)
            self._mic_botao_rotulo = rotulo_botao
            botao.connect("clicked", self._on_mic_clicado)
            escala_mic = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0, 100, 1
            )
            escala_mic.set_draw_value(False)
            escala_mic.set_valign(Gtk.Align.CENTER)
            escala_mic.set_hexpand(True)
            escala_mic.set_tooltip_text(DICA_MIC_ESCALA)
            escala_mic.connect("value-changed", self._on_mic_escala_mudou)
            escala_mic.connect("button-press-event", self._on_mic_escala_pega)
            escala_mic.connect("button-release-event", self._on_mic_escala_solta)
            escala_mic.connect("key-release-event", self._on_mic_escala_solta)
            self._mic_escala = escala_mic
            self._mic_arrastando = False
            self._mic_pintando = False
            self._mic_repouso_id: int | None = None

            linha_mic = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            linha_mic.pack_start(escala_mic, True, True, 0)
            linha_mic.pack_start(botao, False, False, 0)
            miolo.pack_start(linha_mic, False, False, 0)
            grupo = Gtk.SizeGroup(mode=Gtk.SizeGroupMode.HORIZONTAL)
            grupo.add_widget(medidor)
            grupo.add_widget(selo)
            self._grupo_largura_mic = grupo
            self._mic_meter = medidor
            self._mic_selo = selo
            self._mic_botao = botao
            self._mic_box = mic
            self._aplicar_estado_mic(None, presente=False)
            self._aplicar_acao_mic(acao_mic(None))
            return mic

        def _on_mic_clicado(self, _botao: Any) -> None:
            """Manda o pedido de mudo ao firmware — fora da thread GTK.

            O IPC é bloqueante (``ipc_bridge.mic_set`` espera a resposta do
            daemon), e bloquear a thread GTK num clique é como esta interface
            já congelou antes. O callback de volta não pinta nada: quem repinta
            é o tick de 10 Hz da aba, relendo ``daemon.state_full``. Guardar o
            valor MANDADO como se fosse leitura é justamente o hábito que fez a
            tela parecer mentirosa quando ela nunca mentiu.

            **O MUDO NÃO VAI AO RASCUNHO — O-MUDO-E-DO-CONTROLE-01.** Ele é do
            controle e mora no ``maquina.json``, e o escritor dele é o ato do
            microfone no daemon (``hotkey.ligar_o_microfone``), nunca o
            «Salvar Perfil». O callback ainda entrega ``muted``/``soltar_mudo``
            a ``registrar_microfone_no_rascunho``, e ``DraftConfig.with_mic``
            os descarta. Continua não pintando nada.
            """
            acao = self._mic_acao
            if acao is None or not acao.sensivel or self._som_sem_alvo():
                return
            valor = acao.valor
            uniq = self._uniq

            def _pedir() -> bool:
                return ipc_bridge.mic_set(valor, uniq)

            ipc_bridge.run_in_thread(
                _pedir,
                self._mic_confirmado_pelo_daemon(
                    muted=valor, soltar_mudo=valor is None
                ),
            )

        def _montar_lightbar(self) -> Any:
            """Bloco "Lightbar": a cor que já chega no card, agora como BARRA."""
            caixa, miolo = self._bloco("Lightbar")
            barra = LightbarBar()
            barra.set_valign(Gtk.Align.CENTER)
            if not self._compact:
                barra.set_size_request(*_BARRA_FINA_PX_UNICO)
            miolo.pack_start(barra, False, False, 0)
            hexa = self._rotulo_secao("")
            miolo.pack_start(hexa, False, False, 0)
            self._lightbar_bar = barra
            self._lightbar_hex = hexa
            self._lightbar_box = caixa
            self._esconder_modulo(caixa)
            return caixa

        def _montar_speaker(self) -> Any:
            """Bloco "Alto-falante": leitura EM CIMA, comando EMBAIXO.

            STATUS-SIMETRIA-02, entrega 4 — *"não tem a parte do som"*. O
            bloco sumia da tela dela por construção: o daemon só publica a
            chave ``speaker`` DEPOIS de um ``speaker.set`` nosso, porque o
            DualSense não devolve o volume (não há report de input nem feature
            report que o leia — ver ``ipc_handlers``), e o card escondia o
            módulo inteiro na ausência da chave. Só que sumir é
            indistinguível de "este controle não tem alto-falante". O bloco
            NUNCA se esconde, em nenhum dos caminhos.

            SOM-02 põe o comando ao lado da leitura, e as duas peças têm
            significados diferentes de propósito:

            * **a barra e o rótulo são LEITURA** — repintados pelo tique de
              10 Hz a partir de ``daemon.state_full``, jamais pelo valor que
              mandamos. Sem posse, a barra fica vazia e o rótulo diz
              ``não ajustado``;
            * **o controle deslizante é COMANDO** — e fica em repouso (no
              zero) enquanto não houver posse, sem afirmar posição. Pôr o
              cursor no meio com o rótulo ``não ajustado`` seria desenhar 50 %
              e negá-lo por escrito;
            * **os dois botões** só ficam sensíveis com posse
              (:func:`acao_speaker_mudo`, :func:`acao_speaker_devolucao`).

            Tudo isso entra ABAIXO da barra pelo mesmo motivo que o botão do
            microfone (`_montar_mic`): no miolo vertical do bloco o custo é de
            ALTURA, que sobra, e não de largura, que é a restrição dura desta
            aba. Medido nesta bancada com a fonte na escala 3: no card de um
            controle o mínimo do bloco é 174px com posse e 200px sem ela, e o
            do controle deslizante 34px; no compacto, 94px contra os mesmos
            34px — o controle deslizante custa ZERO largura nos dois, pelo
            mesmo teste que o botão do microfone passou.

            SOM-03 arrumou a ORDEM das quatro peças, que era o que tornava o
            controle deslizante inútil (30px de bolinha sem trilho na tela
            dela). O desenho de agora, nos dois cards::

                [============ barra ============]   leitura
                [--------O---------------------]    comando
                71 %             [Silenciar][Devolver]

            O controle deslizante tem LINHA PRÓPRIA e nasce colado na barra que
            comanda — as duas peças continuam sendo duas (E5), e ficarem uma
            sobre a outra, do mesmo tamanho, é o que deixa ler de relance que
            dizem a mesma grandeza. No card compacto o rótulo de valor fica na
            linha dele e os botões na de baixo, porque fundi-los ali estouraria
            a largura da aba — os números estão no bloco de comentários do
            empacotamento, mais abaixo.
            """
            caixa, miolo = self._bloco(TITULO_SPEAKER)
            self._speaker_titulo = (
                caixa.get_label_widget() if not self._compact else None
            )
            caixa.set_tooltip_text(DICA_BLOCO_SPEAKER)
            barra = SpeakerBar()
            barra.set_valign(Gtk.Align.CENTER)
            if not self._compact:
                barra.set_size_request(*_BARRA_SPEAKER_PX_UNICO)
            valor = self._rotulo_secao(TEXTO_SPEAKER_SEM_DADO)
            selo_saida = self._rotulo_secao(TEXTO_SELO_SAIDA_MUDA)
            selo_saida.set_ellipsize(Pango.EllipsizeMode.END)
            selo_saida.set_max_width_chars(_SELO_CHARS)
            escala = Gtk.Scale.new_with_range(
                Gtk.Orientation.HORIZONTAL, 0, 100, 1
            )
            escala.set_draw_value(False)
            escala.set_valign(Gtk.Align.CENTER)
            escala.set_hexpand(True)
            escala.set_tooltip_text(DICA_SPEAKER_ESCALA)
            escala.connect("value-changed", self._on_speaker_escala_mudou)
            escala.connect("button-press-event", self._on_speaker_escala_pega)
            escala.connect("button-release-event", self._on_speaker_escala_solta)
            escala.connect("key-release-event", self._on_speaker_escala_solta)
            botao_mudo = self._botao_de_acao(TEXTO_BOTAO_SPEAKER_SEM_DADO)
            botao_mudo.connect("clicked", self._on_speaker_mudo_clicado)
            botao_devolver = self._botao_de_acao(TEXTO_BOTAO_SPEAKER_DEVOLVER)
            botao_devolver.connect(
                "clicked", self._on_speaker_devolucao_clicada
            )
            #   JÁ tinha linha própria desde a SOM-02 — recebe 113px com dois
            if self._compact:
                valor.set_ellipsize(Pango.EllipsizeMode.END)
                linha_leitura = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=4
                )
                linha_leitura.pack_start(barra, True, True, 0)
                linha_leitura.pack_start(valor, False, False, 0)
                miolo.pack_start(linha_leitura, False, False, 0)
                miolo.pack_start(escala, False, False, 0)
                # usa com um DualSense — os dois rótulos aparecem inteiros
                linha_botoes = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=4
                )
                linha_botoes.set_homogeneous(True)
                linha_botoes.pack_start(botao_mudo, True, True, 0)
                linha_botoes.pack_start(botao_devolver, True, True, 0)
                miolo.pack_start(linha_botoes, False, False, 0)
            else:
                miolo.pack_start(barra, False, False, 0)
                miolo.pack_start(escala, False, False, 0)
                # alto-falante do DualSense, e a tela hoje trata os dois como
                #      manda um som para o dispositivo de áudio do controle e
                linha_acoes = Gtk.Box(
                    orientation=Gtk.Orientation.HORIZONTAL, spacing=4
                )
                seletor = SegmentedSelector()
                seletor.get_style_context().add_class("hefesto-seletor-compacto")
                seletor.set_items(list(CANAIS_DO_SPEAKER))
                seletor.set_tooltips(dict(DICAS_DO_CANAL))
                seletor.connect("changed", self._on_canal_do_speaker_mudou)
                self._speaker_canal = seletor
                linha_acoes.pack_start(seletor, True, True, 0)
                linha_acoes.pack_start(botao_mudo, False, False, 0)
                # utilidade real dele: *"o DualSense não tem botão físico de
                #
                self._speaker_rota_slot = None
                miolo.pack_start(linha_acoes, False, False, 0)
            miolo.pack_start(selo_saida, False, False, 0)
            self._esconder_modulo(selo_saida)
            self._speaker_bar = barra
            self._speaker_label = valor
            self._speaker_selo_saida = selo_saida
            self._speaker_escala = escala
            self._speaker_botao_mudo = botao_mudo
            self._speaker_botao_devolver = botao_devolver
            self._speaker_box = caixa
            self._aplicar_estado_speaker(None)
            self._aplicar_acoes_speaker(
                acao_speaker_mudo(None), acao_speaker_devolucao(None)
            )
            return caixa

        def _botao_de_acao(self, rotulo_inicial: str) -> Any:
            """Botão de ação de bloco, no molde do botão do microfone.

            O rótulo é um Label NOSSO, e não o que ``Gtk.Button(label=...)``
            fabrica, pela razão medida em `_montar_mic`: ``set_label()``
            DESTRÓI e recria o label interno e levaria o teto de largura junto
            no primeiro troca-troca de estado. O campo fixo
            (:data:`_SPEAKER_BOTAO_CHARS`) é o que impede o rótulo mais longo
            de decidir a largura da coluna.
            """
            botao = Gtk.Button()
            botao.set_halign(Gtk.Align.FILL)
            rotulo = Gtk.Label(label=rotulo_inicial)
            rotulo.set_ellipsize(Pango.EllipsizeMode.END)
            rotulo.set_max_width_chars(_SPEAKER_BOTAO_CHARS)
            botao.add(rotulo)
            botao._rotulo_hefesto = rotulo
            return botao


        def _on_mic_escala_pega(self, _escala: Any, _evento: Any) -> bool:
            """A mão dela assumiu: o tique de 10 Hz para de mexer no cursor.

            Sem isto, a releitura do estado brigaria com o arrasto e o controle
            pularia para trás no meio do gesto.
            """
            self._mic_arrastando = True
            return False

        def _on_mic_escala_solta(self, _escala: Any, _evento: Any) -> bool:
            """Fim do gesto: manda o volume agora, sem esperar o repouso."""
            self._mic_arrastando = False
            self._enviar_volume_do_mic()
            return False

        def _on_mic_escala_mudou(self, _escala: Any) -> None:
            """Valor mudou: arma o repouso — nunca manda no ato."""
            if self._mic_pintando:
                return
            self._cancelar_repouso_do_mic()
            self._mic_repouso_id = GLib.timeout_add(
                _MIC_REPOUSO_MS, self._on_mic_repouso
            )

        def _on_mic_repouso(self) -> bool:
            """Passou o repouso sem novo movimento: manda."""
            self._mic_repouso_id = None
            if not self._mic_arrastando:
                self._enviar_volume_do_mic()
            return False

        def _cancelar_repouso_do_mic(self) -> None:
            """Desarma o disparo pendente, se houver."""
            if self._mic_repouso_id is not None:
                with contextlib.suppress(Exception):
                    GLib.source_remove(self._mic_repouso_id)
                self._mic_repouso_id = None

        def _enviar_volume_do_mic(self) -> None:
            """Manda o volume ao daemon, FORA da thread do GTK.

            O IPC é bloqueante, e bloquear a thread do GTK num gesto é como
            esta interface já congelou antes. Não pintamos nada de volta: quem
            repinta é o tique relendo o estado. Guardar o valor MANDADO como se
            fosse leitura é o hábito que fez a tela parecer mentirosa.
            """
            self._cancelar_repouso_do_mic()
            escala = getattr(self, "_mic_escala", None)
            if escala is None or self._som_sem_alvo():
                return
            volume = round(escala.get_value())
            if volume == getattr(self, "_mic_volume_enviado", None):
                # número duas vezes é rajada, não pedido.
                return
            self._mic_volume_enviado = volume
            uniq = self._uniq
            # verdade e continua atendido; o que caducou é o callback ser
            ipc_bridge.run_in_thread(
                lambda: ipc_bridge.mic_volume_set_detalhado(
                    volume=volume, uniq=uniq
                ),
                self._mic_confirmado_pelo_daemon(volume=volume),
            )

        def _pintar_volume_do_mic(self, volume: int | None) -> None:
            """Repõe o cursor a partir do ESTADO — sem disparar novo pedido."""
            escala = getattr(self, "_mic_escala", None)
            if escala is None or volume is None or self._mic_arrastando:
                return
            if round(escala.get_value()) == int(volume):
                return
            self._mic_pintando = True
            try:
                escala.set_value(float(volume))
            finally:
                self._mic_pintando = False

        def _on_speaker_escala_pega(self, _escala: Any, _evento: Any) -> bool:
            """Botão do mouse APERTADO no controle: a mão dela assumiu."""
            self._speaker_arrastando = True
            return False

        def _on_speaker_escala_solta(self, _escala: Any, _evento: Any) -> bool:
            """Soltou o botão (ou a tecla): manda o volume AGORA."""
            self._speaker_arrastando = False
            self._enviar_volume_do_controle()
            return False

        def _on_speaker_escala_mudou(self, _escala: Any) -> None:
            """Valor mudou: arma o repouso — nunca manda no ato.

            ``value-changed`` dispara por pixel de arrasto, e o IPC é
            BLOQUEANTE: mandar aqui viraria uma rajada de pedidos enfileirados
            num executor de uma thread só. Quem manda é o fim do gesto
            (`_on_speaker_escala_solta`) ou o repouso, o que vier primeiro.

            A guarda do `_speaker_pintando` é a parte que não pode cair: sem
            ela, o tique de 10 Hz que repinta o controle a partir do estado
            dispararia um pedido de volta ao daemon — um laço de eco entre
            leitura e comando.
            """
            if self._speaker_pintando:
                return
            self._agendar_envio_de_volume()

        def _agendar_envio_de_volume(self) -> None:
            """(Re)arma o disparo único do repouso."""
            self._cancelar_repouso_do_volume()
            self._speaker_repouso_id = GLib.timeout_add(
                _SPEAKER_REPOUSO_MS, self._on_speaker_repouso
            )

        def _cancelar_repouso_do_volume(self) -> None:
            fonte = self._speaker_repouso_id
            self._speaker_repouso_id = None
            if fonte is not None:
                GLib.source_remove(fonte)

        def _on_speaker_repouso(self) -> bool:
            self._speaker_repouso_id = None
            self._enviar_volume_do_controle()
            return False

        def _enviar_volume_do_controle(self) -> None:
            """Manda o volume do controle deslizante — fora da thread GTK.

            Três invariantes, cada uma paga com uma medição da SOM-02:

            * **o valor vai SEMPRE explícito.** ``speaker.set`` sem ``volume``
              não é consulta: o backend cai na preferência, que sem volume
              anterior é ZERO, toma a posse e emudece o controle (armadilha 1);
            * **nada de bloquear a thread do GTK**: o pedido vai por
              ``run_in_thread``, como o botão do microfone. Esta interface já
              congelou por IPC bloqueante num clique;
            * **o valor mandado NÃO vira leitura.** O callback não pinta nada;
              quem repinta é o tique de 10 Hz relendo ``daemon.state_full``. Um
              número pintado a partir do que mandamos seria "a tela mentindo"
              no dia em que o daemon recusasse o pedido.
            """
            self._cancelar_repouso_do_volume()
            if self._som_sem_alvo():
                # PRIMÁRIO. O repouso já podia estar armado quando o endereço
                # sumiu, e é por isso que a tranca é aqui e não só no gesto.
                return
            volume = volume_do_percentual(self._speaker_escala.get_value())
            if volume == self._speaker_volume_enviado:
                return
            self._speaker_volume_enviado = volume
            uniq = self._uniq

            def _pedir() -> Any:
                ok = ipc_bridge.speaker_set(volume=volume, uniq=uniq)
                return self._confirmar_com_som() if ok else None

            ipc_bridge.run_in_thread(
                _pedir, self._confirmado_pelo_daemon(volume=volume, muted=False)
            )

        def _on_canal_do_speaker_mudou(self, seletor: Any) -> None:
            """O gesto dela no seletor: escolhe ONDE o som do controle sai.

            SOM-CANAL-01/E2. Os dois estados fazem coisas de CAMADAS
            diferentes, e é por isso que eles não podiam ser um botão só:

            * **Sons do jogo** mexe no byte `OUTPUT_PATH_SEL` (camada 2, o
              firmware) e devolve o default sink do sistema para onde ele
              estava. O jogo continua mandando som para o dispositivo de áudio
              do controle; o byte decide que só o canal direito sai no
              alto-falante e o esquerdo vai para o fone/TV;
            * **Todo o som do PC** mexe no default sink (camada 1, o PipeWire)
              E põe a rota em "só o alto-falante" — com o som inteiro do PC
              vindo por aqui, mandar metade para um fone que não existe seria
              perder metade.

            **A camada 1 vence a camada 2** (armadilha 3 da sprint): volume e
            rota perfeitos num sink mudo é trabalho invisível. Por isso o
            estado "Todo o som do PC" mexe nas duas.

            E ele TOCA o som de confirmação, que é ideia dela: *"ao clicar em
            cada botão ele emite o som (...) tem que ajudar a entender o
            conceito"*. O seletor não só configura — ele demonstra.
            """
            canal = seletor.get_active_id()
            if canal is None or self._speaker_canal_pintando:
                return
            if self._som_sem_alvo():
                return
            rota = ROTA_DO_CANAL.get(canal)
            if rota is None:
                return

            pedir_rota_do_sistema = self._pedir_rota_do_sistema
            #
            uniq = self._uniq
            volume = volume_do_percentual(self._speaker_escala.get_value())

            sink = self._speaker_sink

            def _pedir() -> Any:
                ok = ipc_bridge.speaker_set(rota=rota, volume=volume, uniq=uniq)
                audio_saida.garantir_saida_audivel(sink)
                if pedir_rota_do_sistema is not None:
                    pedir_rota_do_sistema(canal == CANAL_TODO_O_PC)
                return self._confirmar_com_som() if ok else None

            volume_anotado = self._volume_lido_do_daemon()
            ipc_bridge.run_in_thread(
                _pedir,
                self._confirmado_pelo_daemon(
                    volume=volume if volume_anotado is None else volume_anotado,
                    muted=False,
                    rota=rota,
                ),
            )

        def definir_pedido_de_rota(self, callback: Any) -> None:
            """Quem executa a camada 1 quando ela troca o canal."""
            self._pedir_rota_do_sistema = callback

        def definir_dono_do_rascunho(self, janela: Any) -> None:
            """Quem GUARDA o rascunho do perfil em edição (SOM-02/E4).

            A aba injeta a própria janela na montagem dos cards, do mesmo jeito
            que injeta o sink e o pedido de rota. Sem ela o bloco continua
            funcionando ao vivo e nada é anotado — que é o comportamento
            correto de um card avulso, e é como todo teste de geometria deste
            widget o monta.

            **O card PEDE, quem escreve é o dono.** A escrita mora em
            ``draft_config.registrar_alto_falante_no_rascunho``, escritor único
            e visível ao portão de AST: a classe de defeito desta casa é *"três
            escritores do perfil sem dono"* (auditoria 23/07).
            """
            self._dono_do_rascunho = janela

        def _confirmado_pelo_daemon(
            self,
            *,
            volume: int | None = None,
            muted: bool = False,
            rota: int | None = None,
            soltar: bool = False,
        ) -> Any:
            """O callback de sucesso dos gestos do alto-falante.

            REGISTRAR NÃO É APLICAR, e registrar é DEPOIS. Quem aplica é o
            ``speaker.set`` que já saiu; aqui só se anota no rascunho o que
            ficou DE PÉ, para o "Salvar Perfil" persistir — a mesma disciplina
            de ``registrar_modo_no_rascunho`` na aba Emulação.

            O defeito que isto cura (auditoria de 09/08/2026): o bloco mandava
            o volume por IPC e não tocava no rascunho, então ``to_profile``
            devolvia o número VELHO e ``lifecycle.apply_profile_speaker`` o
            reaplicava ao controle na ativação. Ela ajustava o volume, clicava
            em Salvar, e o próprio gesto de salvar desfazia o ajuste — não só
            perder o valor novo, mas persistir um eco do estado velho.

            ``resultado is None`` é o daemon tendo RECUSADO o pedido (contrato
            escrito em ``_on_som_de_confirmacao``): aí não há o que registrar,
            porque o rascunho descreve o que está de pé e não a intenção.

            ``soltar`` é a DEVOLUÇÃO da posse, e apaga a seção do rascunho — um
            perfil salvo depois de "Soltar" não pode continuar carregando um
            número que a ativação seguinte reaplicaria, retomando a posse que
            ela acabou de largar.

            ``volume=None`` SEM ``soltar`` não registra nada, e a distinção é a
            entrega: "não sei o volume" e "ela largou o volume" são coisas
            opostas, e confundi-las apagaria a seção do perfil num gesto de
            mudo que só não tinha leitura ainda.
            """

            def _feito(resultado: Any) -> bool:
                if resultado is not None and (soltar or volume is not None):
                    registrar_alto_falante_no_rascunho(
                        self._dono_do_rascunho,
                        volume=None if soltar else volume,
                        muted=muted,
                        rota=rota,
                        # POR-UNIDADE-01: DE QUEM foi o gesto. O bloco já manda
                        uniq=self._uniq,
                    )
                return self._on_som_de_confirmacao(resultado)

            return _feito

        def _mic_confirmado_pelo_daemon(
            self,
            *,
            volume: int | None = None,
            muted: bool | None = None,
            soltar_mudo: bool = False,
        ) -> Any:
            """O callback de sucesso dos gestos do MICROFONE (18/08/2026).

            Irmão exato do ``_confirmado_pelo_daemon`` do alto-falante, e nasceu
            do mesmo defeito um andar ao lado. Pedido dela em 18/08/2026, depois
            de o microfone ficar mudo e o DON'T SCREAM não ouvir nada:
            *"informação de microfone e som, touch, acelerômetro, giroscópio e
            afins. cara, temos que salvar isso no perfil sempre."* Medido no
            mesmo dia: nenhum dos 18 perfis dela tinha a seção ``mic``.

            REGISTRAR NÃO É APLICAR, e registrar é DEPOIS. Quem aplica é o
            ``mic.set``/``mic.volume.set`` que já saiu; aqui só se anota o que
            ficou DE PÉ, para o "Salvar Perfil" persistir.

            ``ok`` falso é o daemon tendo RECUSADO — e, no volume, também o
            ``sem_fonte`` do Bluetooth sem a ponte de áudio de pé. Nos dois, não
            há o que registrar: o rascunho descreve o que está de pé, não a
            intenção.

            **DUAS FORMAS DE ``ok``, e é de propósito (MIC-DA-MESA-CHEIA-01,
            26/08/2026).** O gesto do MUDO chega com o ``bool`` de
            ``ipc_bridge.mic_set``; o do VOLUME chega com o CORPO de
            ``mic_volume_set_detalhado``, que é um ``dict`` (ou ``None``). O
            corpo é o que permite a pergunta que o ``bool`` apagava: *o daemon
            mexeu no controle que ela escolheu?* — ``por_uniq``, lido aqui por
            ``ipc_bridge.alvo_honrado``.

            **ALVO NÃO HONRADO NÃO ENTRA NO RASCUNHO.** O daemon respondeu
            ``ok``, mas mexeu no microfone de OUTRO controle (a rota global, com
            a mesa cheia, pega a primeira das duas placas de som). Gravar esse
            número no rascunho deste controle seria a tela guardando, no perfil
            dela, um volume que este controle nunca teve. ``None`` — o daemon
            não se pronunciou — continua registrando: "não sei" não é "não
            honrei", e recusar por ausência de notícia inventaria um defeito.

            Não pinta nada, como o gesto nunca pintou: quem repinta é o tique
            de 10 Hz relendo ``daemon.state_full``. A única coisa que aparece é
            a CONFISSÃO, e só no caso em que ela é verdade. Devolver ``False`` é
            o contrato do ``run_in_thread`` (repostado pelo laço ocioso do
            GLib).
            """

            def _feito(ok: Any) -> bool:
                corpo = ok if isinstance(ok, dict) else None
                honrado = (
                    ipc_bridge.alvo_honrado(corpo) if corpo is not None else None
                )
                self._dizer_alvo_do_mic(honrado)
                aceito = (
                    corpo.get("status") == "ok" if corpo is not None else bool(ok)
                )
                if aceito and honrado is not False:
                    registrar_microfone_no_rascunho(
                        self._dono_do_rascunho,
                        volume=volume,
                        muted=muted,
                        soltar_mudo=soltar_mudo,
                    )
                return False

            return _feito

        def _dizer_alvo_do_mic(self, honrado: bool | None) -> None:
            """Mostra (ou apaga) a confissão do alvo não honrado."""
            aviso = getattr(self, "_mic_aviso_alvo", None)
            if aviso is None:
                return
            if frase_do_alvo_do_mic(honrado):
                aviso.show()
            else:
                aviso.hide()

        def _volume_lido_do_daemon(self) -> int | None:
            """A preferência de volume que o daemon publica, ou None."""
            lido = self._speaker_lido
            return None if lido is None else lido[0]

        def _on_speaker_mudo_clicado(self, _botao: Any) -> None:
            """Silenciar/Ativar — nunca a PRIMEIRA escrita (ver `acao_speaker_mudo`)."""
            acao = self._speaker_acao_mudo
            if acao is None or not acao.sensivel or acao.muted is None:
                return
            if self._som_sem_alvo():
                return
            muted = acao.muted
            uniq = self._uniq

            def _pedir() -> Any:
                ok = ipc_bridge.speaker_set(muted=muted, uniq=uniq)
                return self._confirmar_com_som() if ok else None

            ipc_bridge.run_in_thread(
                _pedir,
                self._confirmado_pelo_daemon(
                    volume=self._volume_lido_do_daemon(), muted=muted
                ),
            )

        def _on_speaker_devolucao_clicada(self, _botao: Any) -> None:
            """Devolver a posse dos bytes de volume (SOM-02, entrega 3)."""
            acao = self._speaker_acao_devolucao
            if acao is None or not acao.sensivel or not acao.release:
                return
            if self._som_sem_alvo():
                return
            uniq = self._uniq

            def _pedir() -> Any:
                ok = ipc_bridge.speaker_set(release=True, uniq=uniq)
                return self._confirmar_com_som() if ok else None

            ipc_bridge.run_in_thread(
                _pedir, self._confirmado_pelo_daemon(soltar=True)
            )


        def definir_sink_de_saida(self, sink: str) -> None:
            """O sink de saída DESTE controle, para o som de confirmação.

            Quem resolve "qual sink é de qual controle" é o ``mic_monitor``
            (``escolher_sink``), que já é o leitor de PipeWire da janela e roda
            fora da thread do GTK com cadência própria; quem repassa é a
            ``status_actions``, no tique dos cards. **O card não vai ao sistema
            por conta própria** — um segundo leitor de PipeWire aqui seria a
            mesma classe de defeito dos três escritores de perfil.

            ``""`` é resposta legítima e frequente: o controle está no RÁDIO,
            onde o DualSense não publica placa de som (medido 15/08/2026 — a
            placa segue o transporte). No cabo o ``escolher_sink`` casa placa e
            controle pelo dispositivo USB em que os dois penduram, e responde
            com o sink certo por card. Com "" não se toca.
            """
            self._speaker_sink = sink or ""

        def definir_estado_do_canal(
            self, estado: str, *, regra_instalada: bool | None = None
        ) -> None:
            """O canal deste controle está acordado ou dormindo (e é padrão?).

            SOM-ACORDADO-01, e é a metade "ligar isso a interface" da decisão
            dela. Dois fatos entram por aqui, os dois de fora:

            * ``estado`` — ``"acordado"``, ``"dormindo"`` ou ``""``. O
              vocabulário é o do ``audio_saida`` (:data:`CANAL_ACORDADO` e
              irmãos) e ``""`` é **não sei**: pelo rádio o DualSense não
              publica placa de som nenhuma (medido em 15/08/2026 — a placa
              segue o transporte), e ali não há canal a descrever;
            * ``regra_instalada`` — o drop-in 54 do WirePlumber está no lugar?
              É o que separa "acordado agora, por acaso" de "acordado por
              padrão". ``None`` = ninguém perguntou, e a dica não afirma nem
              um nem outro.

            **O card não vai ao sistema por conta própria**, aqui como no
            ``definir_sink_de_saida``: quem lê o PipeWire é a ``status_actions``,
            uma vez por ciclo, para todos os cards. Um `pactl` por card seria
            quatro por ciclo na mesa dela — e um segundo leitor de PipeWire
            nesta janela é a mesma classe de defeito dos três escritores de
            perfil.

            Só repinta quando algo MUDA: este método é chamado no tique de
            10 Hz dos cards, e `set_text` a 10 Hz num rótulo de moldura é
            trabalho de layout por nada.
            """
            estado = estado or ""
            if (
                estado == self._speaker_canal_estado
                and regra_instalada == self._speaker_regra_do_sono
            ):
                return
            self._speaker_canal_estado = estado
            self._speaker_regra_do_sono = regra_instalada
            self._escrever_valor_do_speaker(self._speaker_label.get_text())
            self._aplicar_selo_do_som()

        def _confirmar_com_som(self) -> Any:
            """Toca a confirmação — JÁ na thread worker, nunca na do GTK.

            Chamado de DENTRO do mesmo ``_pedir`` do IPC, e de propósito: o som
            é a confirmação daquele pedido, e emiti-lo antes de o daemon
            responder confirmaria uma coisa que pode não ter acontecido.

            Por que o som existe: o registrador de volume do DualSense não tem
            leitura, e o número que o bloco mostra é o que NÓS mandamos. Sem o
            som não há como saber se a mudança valeu — é o mesmo papel que o
            "bip" de qualquer controle de volume de sistema operacional cumpre,
            aqui por necessidade e não por costume.

            A saída muda da camada 1 entra como argumento porque, com o sink do
            sistema mudo, tocar gastaria um processo para produzir silêncio — e
            ela leria o silêncio como defeito do controle, que é exatamente o
            contrário do que a confirmação existe para dizer.

            **Um som por gesto, não um por pixel.** Três camadas empilhadas, e
            nenhuma delas mora aqui: o repouso de 250ms
            (:data:`_SPEAKER_REPOUSO_MS`) e a deduplicação do mesmo volume, em
            `_enviar_volume_do_controle`, e a trava de um som por vez do
            `audio_saida`, para o caso de o gesto ser mais rápido que o tocador
            (medido: 0,35s de ponta a ponta).
            """
            return audio_saida.tocar_confirmacao(
                self._speaker_sink, saida_muda=self._speaker_saida_muda
            )

        def _on_som_de_confirmacao(self, resultado: Any) -> bool:
            """Guarda o recado do som e repinta o selo (contrato do idle_add)."""
            recado = getattr(resultado, "recado", "") if resultado is not None else ""
            if recado != self._speaker_recado_do_som:
                self._speaker_recado_do_som = recado
                self._aplicar_selo_do_som()
            return False

        def _aplicar_selo_do_som(self) -> None:
            """A linha de recado do bloco: camada 1, depois o som, depois nada."""
            recado = self._speaker_recado_do_som
            texto = TEXTO_SELO_SAIDA_MUDA if self._speaker_saida_muda is True else ""
            if texto:
                self._speaker_selo_saida.set_text(texto)
                self._speaker_selo_saida.show()
            else:
                self._speaker_selo_saida.hide()
            partes = [
                DICA_BLOCO_SPEAKER
                if self._speaker_lido is None
                else DICA_SPEAKER_POSSE_NOSSA
            ]
            partes.extend(self._frases_do_canal())
            if recado and self._speaker_saida_muda is not True:
                partes.append(recado)
            caixa = getattr(self, "_speaker_box", None)
            if caixa is not None:
                caixa.set_tooltip_text("\n\n".join(partes))

        def _frases_do_canal(self) -> list[str]:
            """As frases do canal na dica do bloco: o estado, e se é o padrão.

            SOM-ACORDADO-01. Sem leitura do canal não sai frase nenhuma — o
            silêncio da dica é a resposta honesta para o controle no rádio, que
            não tem placa de som para acordar.

            A frase do PADRÃO é condicionada à regra estar instalada, e a
            condição é a metade que importa: um nó pode estar acordado por
            acaso (alguém acabou de tocar algo) com o drop-in fora do lugar, e
            chamar isso de "é o padrão" seria a tela dando por curado o que só
            está momentaneamente de pé — mesma regra que o `texto_do_sono` do
            `audio_saida` já aplica do lado da leitura.
            """
            estado = self._speaker_canal_estado
            if not estado:
                return []
            frases = [
                DICA_CANAL_DORMINDO
                if estado == SUFIXO_CANAL_DORMINDO
                else DICA_CANAL_ACORDADO
            ]
            if self._speaker_regra_do_sono is True:
                frases.append(DICA_CANAL_E_PADRAO)
            elif self._speaker_regra_do_sono is False:
                frases.append(dica_canal_sem_a_regra())
            return frases

        def _montar_capsula_stick(
            self, titulo: str, rotulo_stick: str, tamanho: int
        ) -> tuple[Any, StickPreviewGtk, Any, Any]:
            caps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            caps.set_halign(Gtk.Align.CENTER)
            caps.set_valign(Gtk.Align.START)
            label_titulo = Gtk.Label()
            label_titulo.set_markup(titulo)
            label_titulo.set_xalign(0.5)
            label_titulo.set_line_wrap(False)
            label_titulo.set_justify(Gtk.Justification.CENTER)
            label_titulo.get_style_context().add_class("dim-label")
            self._grupo_titulos_stick.add_widget(label_titulo)
            caps.pack_start(label_titulo, False, False, 0)
            preview = StickPreviewGtk(label=rotulo_stick)
            preview.set_size_request(tamanho, tamanho)
            slot = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            slot.set_halign(Gtk.Align.CENTER)
            slot.pack_start(preview, False, False, 0)
            caps.pack_start(slot, False, False, 0)
            label_xy = Gtk.Label()
            label_xy.set_markup(_markup_xy(128, 128))
            label_xy.set_xalign(0.5)
            label_xy.set_justify(Gtk.Justification.CENTER)
            label_xy.get_style_context().add_class("hefesto-valor-mono")
            caps.pack_start(label_xy, False, False, 0)
            return caps, preview, label_titulo, label_xy

        def _montar_sticks(self) -> Any:
            """Os dois analógicos, lado a lado, dentro da faixa de baixo."""
            tamanho = (
                STICK_SIZE_COMPACT if self._compact else STICK_SIZE_SINGLE
            )
            # O grupo é POR CARD: amarrar títulos de cards diferentes faria um
            self._grupo_titulos_stick = Gtk.SizeGroup(
                mode=Gtk.SizeGroupMode.VERTICAL
            )
            # uma pede o próprio desenho.
            faixa = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=self._espaco,
            )

            caps_esq, stick_esq, titulo_esq, xy_esq = (
                self._montar_capsula_stick(
                    _TITULO_STICK_ESQ, ROTULO_STICK_ESQ, tamanho
                )
            )
            self._stick_left = stick_esq
            self._stick_left_title = titulo_esq
            self._stick_left_xy = xy_esq
            faixa.pack_start(caps_esq, False, False, 0)

            caps_dir, stick_dir, titulo_dir, xy_dir = (
                self._montar_capsula_stick(
                    _TITULO_STICK_DIR, ROTULO_STICK_DIR, tamanho
                )
            )
            self._stick_right = stick_dir
            self._stick_right_title = titulo_dir
            self._stick_right_xy = xy_dir
            faixa.pack_start(caps_dir, False, False, 0)
            self._faixa_sticks = faixa
            return faixa

        def _montar_glyphs(self) -> Any:
            """Grid 4x4 dos 16 botões — o bloco da direita na linha de baixo."""
            tamanho = glyph_size() if self._compact else glyph_size_unico()
            espaco = (
                GLYPH_ESPACO_COMPACTO if self._compact else GLYPH_ESPACO_UNICO
            )
            self._glyph_size = tamanho
            glyph_grid = Gtk.Grid()
            glyph_grid.set_row_spacing(espaco)
            glyph_grid.set_column_spacing(espaco)
            glyph_grid.set_halign(Gtk.Align.CENTER)
            glyph_grid.set_valign(Gtk.Align.CENTER)
            for row, linha in enumerate(GRID_BOTOES):
                for col, nome in enumerate(linha):
                    tooltip = BUTTON_GLYPH_LABELS.get(nome, nome)
                    glyph = ButtonGlyph(
                        nome, size=tamanho, tooltip_pt_br=tooltip
                    )
                    self._glyphs[nome] = glyph
                    glyph_grid.attach(glyph, col, row, 1, 1)
            self._glyph_grid = glyph_grid
            return glyph_grid


        def _update_titulo(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            titulo = titulo_do_card(entry)
            if titulo != self._last_titulo:
                self._last_titulo = titulo
                self._title_label.set_text(titulo)
            dica = dica_do_titulo(entry, state_global)
            if dica != self._last_dica_titulo:
                self._last_dica_titulo = dica
                self._title_label.set_tooltip_text(dica)

        def _update_bateria(self, entry: dict[str, Any]) -> None:
            bateria = _int_ou_none(entry.get("battery_pct"))
            if bateria == self._last_battery:
                return
            self._last_battery = bateria
            if bateria is None:
                self._battery_bar.set_fraction(0.0)
                texto = "— %"
            else:
                self._battery_bar.set_fraction(
                    max(0, min(100, bateria)) / 100
                )
                texto = f"{bateria} %"
            self._battery_bar.set_text(texto)
            if self._battery_pct_label is not None:
                self._battery_pct_label.set_text(texto)

        def _update_lightbar(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            cru = cor_do_swatch(entry)
            rotulo, base = rotulo_lightbar(entry, state_global)
            accent = ensure_min_contrast(
                base if base is not None else ACCENT_NEUTRO
            )
            chave = (cru, rotulo, accent)
            if chave == self._last_lightbar:
                return
            self._last_lightbar = chave

            if cru != self._swatch_rgb:
                self._swatch_rgb = cru
                self._swatch.queue_draw()

            self._aplicar_lightbar_bar(cru)

            if rotulo:
                self._lightbar_label.set_text(rotulo)
                self._lightbar_label.show()
            else:
                self._lightbar_label.hide()

            if accent != self._accent:
                self._accent = accent
                self._accent_hex = rgb_para_hex(accent)
                self._stick_left.set_accent(accent)
                self._stick_right.set_accent(accent)
                for glyph in self._glyphs.values():
                    glyph.set_accent(accent)
                tintar_progressbar(self._l2_bar, accent)
                tintar_progressbar(self._r2_bar, accent)
                self._pintar_titulos_sticks()

        def _aplicar_lightbar_bar(self, cru: RGB | None) -> None:
            """Bloco "Lightbar" da linha de baixo: a faixa e o hex, ou nada.

            Cor desconhecida (o caso do 0,0,0 sem escrita nossa) esconde o
            bloco em vez de pintar preto: "não sei" e "apagada" não podem
            desenhar a mesma faixa.
            """
            if cru is None:
                self._lightbar_bar.set_cor(None)
                self._lightbar_box.hide()
                return
            self._lightbar_bar.set_cor(cru)
            self._lightbar_hex.set_text(rgb_para_hex(cru))
            self._lightbar_box.show()

        def _update_degradacao(self, entry: dict[str, Any]) -> None:
            texto = texto_degradacao(entry)
            if texto == self._last_degradacao:
                return
            self._last_degradacao = texto
            if texto:
                self._degradacao_badge.set_text(texto)
                self._degradacao_badge.show()
            else:
                self._degradacao_badge.hide()

        def _update_motion(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            texto = texto_motion(entry, state_global)
            if texto == self._last_motion:
                return
            self._last_motion = texto
            if texto:
                self._motion_label.set_text(texto)
            if self._motion_label.get_parent() is None:
                return
            if texto:
                self._motion_label.show()
            else:
                self._motion_label.hide()

        def _update_verdade(
            self, entry: dict[str, Any], state_global: dict[str, Any]
        ) -> None:
            """PAINEL-DA-VERDADE-01: a linha do que chega ao jogo agora."""
            if self._verdade_label is None:
                return
            texto = resumo_do_que_chega_ao_jogo(entry, state_global)
            if texto == self._last_verdade:
                return
            self._last_verdade = texto
            if texto:
                self._verdade_label.set_text(texto)
                self._verdade_label.show()
            else:
                self._verdade_label.hide()


        def _update_gyro(self, inputs: Any) -> None:
            valores = gyro_do_inputs(inputs)
            if valores == self._last_gyro:
                return
            self._last_gyro = valores
            if valores is None:
                self._gyro_bars.limpar()
                self._gyro_box.hide()
                return
            self._gyro_bars.set_valores(*valores)
            self._gyro_box.show()

        def _update_accel(self, inputs: Any) -> None:
            """Idem ao do giro, e com o mesmo cache de diff.

            O `!=` contra o último valor não é gosto: a 10 Hz, com quatro
            controles, redesenhar três barras que não mudaram é trabalho de
            GPU por nada — e o acelerômetro em repouso passa MINUTOS no mesmo
            valor, que é justamente quando o cache paga.
            """
            valores = accel_do_inputs(inputs)
            if valores == self._last_accel:
                return
            self._last_accel = valores
            if valores is None:
                self._accel_bars.limpar()
                self._accel_box.hide()
                return
            self._accel_bars.set_valores(*valores)
            self._accel_box.show()

        def _update_touchpad(self, inputs: Any) -> None:
            dados = touchpad_do_inputs(inputs)
            if dados == self._last_touch:
                return
            self._last_touch = dados
            if dados is None:
                self._touch_view.set_toque(None)
                self._touch_box.hide()
                return
            tocando, fx, fy = dados
            self._touch_view.set_toque((fx, fy) if tocando else None)
            self._touch_label.set_text(texto_toques(1 if tocando else 0))
            self._touch_box.show()

        def _update_mic(self, mic: Any, transporte: str = "") -> None:
            nivel = getattr(mic, "nivel", None) if mic is not None else None
            muted = getattr(mic, "muted", None) if mic is not None else None
            chave = (nivel, muted, transporte)
            if chave == self._last_mic:
                return
            self._last_mic = chave
            if nivel is None:
                self._mic_meter.limpar()
                self._aplicar_estado_mic(None, presente=False)
                return
            self._mic_meter.set_nivel(float(nivel))
            self._aplicar_estado_mic(muted, presente=True)

        def _update_mic_botao(self, entry: dict[str, Any]) -> None:
            """Rótulo/sensibilidade do botão a partir de ``entry['audio']``."""
            acao = acao_mic(entry)
            if acao == self._mic_acao:
                return
            self._aplicar_acao_mic(acao)

        def _aplicar_acao_mic(self, acao: AcaoMic) -> None:
            self._mic_acao = acao
            self._mic_botao_rotulo.set_text(acao.rotulo)
            self._mic_botao.set_sensitive(acao.sensivel)
            self._mic_botao.set_tooltip_text(acao.dica)

        def _aplicar_estado_mic(
            self, muted: Any, *, presente: bool
        ) -> None:
            """Diz o estado do microfone em palavras — sem nunca esconder.

            Quatro estados, um espaço só (a tabela da MIC-PRESENTE-01):
            captando com mute lido vira o selo colorido ``ATIVO``/``MUDO``;
            captando sem mute lido vira ``captando`` apagado (cravar "ATIVO"
            sem ter lido o mute seria afirmar que o microfone está aberto por
            chute); sem sinal nenhum vira ``sem sinal``, também apagado.
            """
            selo = selo_mic(muted) if presente else None
            contexto = self._mic_selo.get_style_context()
            if selo is None:
                contexto.add_class("dim-label")
                self._mic_selo.set_text(
                    TEXTO_MIC_SEM_MUTE if presente else TEXTO_MIC_AUSENTE
                )
                return
            contexto.remove_class("dim-label")
            texto, fundo, cor = selo
            self._mic_selo.set_markup(
                f'<span background="{fundo}" foreground="{cor}">'
                f" {texto} </span>"
            )

        def _update_speaker(self, entry: dict[str, Any], mic: Any = None) -> None:
            dados = speaker_do_entry(entry)
            # o canal registram no rascunho é esta LEITURA — a preferência que
            self._speaker_lido = dados
            saida_muda = saida_muda_do_entry(entry, mic)
            chave = (dados, saida_muda)
            if chave == self._last_speaker:
                return
            self._last_speaker = chave
            self._aplicar_estado_speaker(dados, saida_muda=saida_muda)
            self._aplicar_acoes_speaker(
                acao_speaker_mudo(entry), acao_speaker_devolucao(entry)
            )

        def _aplicar_estado_speaker(
            self,
            dados: tuple[int, bool | None] | None,
            *,
            saida_muda: bool | None = None,
        ) -> None:
            """Volume do alto-falante, ou a frase que diz que ninguém ajustou.

            O bloco NUNCA se esconde: some é o que ela leu como "não tem a
            parte do som".

            O controle deslizante acompanha a LEITURA (é o mesmo estado, e é
            de onde o próximo gesto dela parte), com duas guardas: não repinta
            embaixo da mão dela (``_speaker_arrastando``) e não dispara pedido
            ao se mover (``_speaker_pintando``). Sem posse ele volta ao
            repouso, no zero — não ao meio, que desenharia 50 % ao lado de um
            rótulo dizendo que ninguém ajustou nada.
            """
            # `_aplicar_selo_do_som`, porque o rótulo ganhou um SEGUNDO
            self._speaker_saida_muda = saida_muda
            self._aplicar_selo_do_som()
            if dados is None:
                self._speaker_bar.set_volume(0.0, None)
                self._escrever_valor_do_speaker(TEXTO_SPEAKER_SEM_DADO)
                self._pintar_escala_do_speaker(0)
                self._speaker_volume_enviado = None
                return
            volume, muted = dados
            self._speaker_bar.set_volume(fracao_do_volume(volume), muted)
            self._escrever_valor_do_speaker(texto_volume(volume, muted))
            self._pintar_escala_do_speaker(percentual_do_volume(volume))

        def _escrever_valor_do_speaker(self, texto: str) -> None:
            """O valor do alto-falante, no rótulo E no título da moldura.

            SOM-ROTA-NO-CARD-01. O `_speaker_label` continua existindo e sendo
            escrito: ele é o dono do texto, é o que os testes leem, e no card
            COMPACTO ele é o que aparece na tela. O que mudou é o card único —
            lá o rótulo saiu do empacotamento para o botão da rota caber no
            lugar dele, e quem MOSTRA o valor passou a ser o rótulo da
            moldura, que já existia e não custa pixel nenhum.

            O título é montado aqui, e não guardado pronto, porque
            "Alto-falante" é o nome do bloco e tem de sobreviver a qualquer
            valor — inclusive a `None`, que é como o card nasce.

            CARD-ÚNICO-01, entrega 2 — *"remover o não ajustado"*. O sufixo
            some no estado SEM DADO e continua no estado com valor
            (`Alto-falante · 71 %`). É a leitura literal do pedido, e a que
            custa zero: das duas opções escritas na sprint, a outra (tirar o
            sufixo sempre) obrigaria o valor a achar um terceiro lugar, e os
            três candidatos já foram medidos e todos cobram pixel — o rótulo
            de valor deste bloco foi justamente quem cedeu o lugar para o
            botão da rota, na leva anterior.

            O `_speaker_label` continua recebendo o texto CRU, sem exceção:
            ele é o dono do valor e é o que os testes leem. Quem decide o que
            aparece na moldura é só a linha de baixo.
            """
            self._speaker_label.set_text(texto)
            titulo = getattr(self, "_speaker_titulo", None)
            if titulo is not None and hasattr(titulo, "set_text"):
                titulo.set_text(self._titulo_do_speaker(texto))

        def _titulo_do_speaker(self, texto: str) -> str:
            """O rótulo da moldura: nome · volume · estado do canal.

            SOM-ACORDADO-01. Os dois sufixos entram do mesmo jeito e pela mesma
            razão — são LEITURA, e o rótulo da moldura é o único lugar deste
            bloco que custa zero pixel de altura (a medição está no bloco de
            comentários de :data:`SUFIXO_CANAL_ACORDADO`).

            Cada um some sozinho quando não há o que dizer, e os dois somem
            juntos no card recém-nascido:

            * sem posse do volume, o nome fica sozinho (CARD-ÚNICO-01, decisão
              dela: *"remover o não ajustado"*);
            * sem leitura do canal — o caso do rádio, em que não há placa de
              som —, não entra sufixo nenhum. "" é **não sei**, e escrever
              "acordado" a partir de ausência seria prometer que o som sai
              inteiro num controle que não tem por onde tocá-lo.
            """
            partes = [TITULO_SPEAKER]
            if texto != TEXTO_SPEAKER_SEM_DADO:
                partes.append(texto)
            estado = getattr(self, "_speaker_canal_estado", "")
            if estado:
                partes.append(estado)
            return " · ".join(partes)

        def _pintar_escala_do_speaker(self, percentual: int) -> None:
            """Move o cursor SEM disparar pedido (e nunca durante o arrasto)."""
            if self._speaker_arrastando:
                return
            self._speaker_pintando = True
            try:
                self._speaker_escala.set_value(percentual)
            finally:
                self._speaker_pintando = False

        def _aplicar_acoes_speaker(
            self, mudo: AcaoSpeaker, devolucao: AcaoSpeaker
        ) -> None:
            self._speaker_acao_mudo = mudo
            self._speaker_acao_devolucao = devolucao
            for botao, acao in (
                (self._speaker_botao_mudo, mudo),
                (self._speaker_botao_devolver, devolucao),
            ):
                botao._rotulo_hefesto.set_text(acao.rotulo)
                botao.set_sensitive(acao.sensivel)
                botao.set_tooltip_text(acao.dica)
            self._speaker_box.set_tooltip_text(
                DICA_BLOCO_SPEAKER
                if mudo.sensivel
                else f"{DICA_BLOCO_SPEAKER} ({DICA_SPEAKER_SEM_DADO})"
            )


        def _pecas_que_escrevem_som(self) -> tuple[Any, ...]:
            """As peças de COMANDO do som — as que viajam com o ``uniq``."""
            pecas: list[Any] = [
                self._mic_botao,
                # MIC-VOLUME-01 — o controle deslizante do microfone ocupa aqui
                # a vaga que era do interruptor "Pelo rádio" (saiu em 16/08), e
                # ele PRECISA da vaga: `mic.volume.set` sem `uniq` cai no
                # controle primário, que é o microfone de outra pessoa na mesa
                # cheia. A tranca de dentro do gesto (`_enviar_volume_do_mic`)
                # é a segunda; esta é a que ela VÊ.
                self._mic_escala,
                self._speaker_escala,
                self._speaker_botao_mudo,
                self._speaker_botao_devolver,
            ]
            canal = getattr(self, "_speaker_canal", None)
            if canal is not None:
                pecas.append(canal)
            return tuple(pecas)

        def _update_guarda_de_audio(self) -> None:
            """Desliga (ou devolve) o som do card conforme haja endereço.

            **O estado ligado é reaplicado a cada tique, e isso não é
            desperdício.** Os `_update_` do som são diffados: qualquer mudança
            no que o daemon publica sobre este controle os faz repintar a
            sensibilidade das peças, e sem a reaplicação um `speaker` que
            aparecesse no meio da sessão devolveria os botões por baixo da
            guarda. `set_sensitive` com o mesmo valor é no-op no GTK.

            **A volta é diffada**, porque é ela que precisa acontecer UMA vez:
            quem sabe o estado certo de cada peça são as ações já calculadas
            (`_aplicar_acao_mic`, `_aplicar_acoes_speaker`), e reaplicá-las é a
            única forma de devolver a sensibilidade sem a guarda ter de
            adivinhá-la. Os dois controles deslizantes não têm ação calculada —
            eles só dependem do endereço, e por isso voltam direto.
            """
            if self._uniq is None:
                for peca in self._pecas_que_escrevem_som():
                    peca.set_sensitive(False)
                self._mic_box.set_tooltip_text(DICA_AUDIO_SEM_ENDERECO)
                self._speaker_box.set_tooltip_text(DICA_AUDIO_SEM_ENDERECO)
                self._audio_aviso.show()
                self._audio_sem_endereco = True
                return
            if self._audio_sem_endereco is False:
                return
            self._audio_sem_endereco = False
            self._audio_aviso.hide()
            self._mic_box.set_tooltip_text(None)
            self._aplicar_acao_mic(self._mic_acao or acao_mic(None))
            self._mic_escala.set_sensitive(True)
            self._speaker_escala.set_sensitive(True)
            canal = getattr(self, "_speaker_canal", None)
            if canal is not None:
                canal.set_sensitive(True)
            self._aplicar_acoes_speaker(
                self._speaker_acao_mudo or acao_speaker_mudo(None),
                self._speaker_acao_devolucao or acao_speaker_devolucao(None),
            )

        def _som_sem_alvo(self) -> bool:
            """A guarda vista de DENTRO do gesto — a segunda tranca."""
            return self._uniq is None


        def _update_inputs(self, inputs: Any) -> None:
            if not isinstance(inputs, dict):
                self._mostrar_sem_leitor()
                return
            if self._sem_leitor is not False:
                self._sem_leitor = False
                self._sem_leitor_label.hide()
                self._inputs_area.show()

            l2 = int(inputs.get("l2_raw", 0))
            r2 = int(inputs.get("r2_raw", 0))
            if l2 != self._last_l2:
                self._l2_bar.set_fraction(l2 / 255)
                self._l2_bar.set_text(f"{l2} / 255")
                self._last_l2 = l2
            if r2 != self._last_r2:
                self._r2_bar.set_fraction(r2 / 255)
                self._r2_bar.set_text(f"{r2} / 255")
                self._last_r2 = r2

            lx = int(inputs.get("lx", 128))
            ly = int(inputs.get("ly", 128))
            rx = int(inputs.get("rx", 128))
            ry = int(inputs.get("ry", 128))
            if lx != self._last_lx or ly != self._last_ly:
                self._stick_left.update(lx, ly)
                self._stick_left_xy.set_markup(
                    _markup_xy(lx, ly)
                )
                self._last_lx = lx
                self._last_ly = ly
            if rx != self._last_rx or ry != self._last_ry:
                self._stick_right.update(rx, ry)
                self._stick_right_xy.set_markup(
                    _markup_xy(rx, ry)
                )
                self._last_rx = rx
                self._last_ry = ry

            buttons_raw = inputs.get("buttons") or []
            buttons_pressed = frozenset(str(b) for b in buttons_raw)
            self._refresh_glyphs(buttons_pressed, l2, r2)

        def _refresh_glyphs(
            self, buttons_pressed: frozenset[str], l2_raw: int, r2_raw: int
        ) -> None:
            l2_lit = l2_raw > L2_R2_THRESHOLD
            r2_lit = r2_raw > L2_R2_THRESHOLD
            if (
                buttons_pressed == self._last_buttons
                and l2_lit == self._last_l2_lit
                and r2_lit == self._last_r2_lit
            ):
                return
            self._last_buttons = buttons_pressed
            self._last_l2_lit = l2_lit
            self._last_r2_lit = r2_lit

            efetivos: dict[str, bool] = {
                nome: (nome in buttons_pressed) for nome in ALL_BUTTONS
            }
            efetivos["l2"] = l2_lit
            efetivos["r2"] = r2_lit
            efetivos["share"] = ("share" in buttons_pressed) or (
                "create" in buttons_pressed
            )
            for nome, glyph in self._glyphs.items():
                glyph.set_pressed(efetivos.get(nome, False))

            l3 = "l3" in buttons_pressed
            r3 = "r3" in buttons_pressed
            if l3 != self._l3_pressed or r3 != self._r3_pressed:
                self._l3_pressed = l3
                self._r3_pressed = r3
                self._stick_left.set_l3_pressed(l3)
                self._stick_right.set_l3_pressed(r3)
                self._pintar_titulos_sticks()

        def _pintar_titulos_sticks(self) -> None:
            """Títulos dos sticks: accent do CONTROLE quando pressionados."""
            self._pintar_titulo_stick(
                self._stick_left_title, _TITULO_STICK_ESQ, self._l3_pressed
            )
            self._pintar_titulo_stick(
                self._stick_right_title, _TITULO_STICK_DIR, self._r3_pressed
            )

        def _pintar_titulo_stick(
            self, label: Any, texto: str, pressionado: bool
        ) -> None:
            if pressionado:
                label.set_markup(
                    f'<span foreground="{self._accent_hex}">{texto}</span>'
                )
            else:
                label.set_markup(texto)

        def _mostrar_sem_leitor(self) -> None:
            if self._sem_leitor is True:
                return
            self._sem_leitor = True
            self._inputs_area.hide()
            self._sem_leitor_label.show()
            self._reset_inputs_render()

        def _reset_inputs_render(self) -> None:
            """Volta a área de inputs ao repouso e invalida os caches."""
            self._l2_bar.set_fraction(0.0)
            self._l2_bar.set_text("0 / 255")
            self._r2_bar.set_fraction(0.0)
            self._r2_bar.set_text("0 / 255")
            self._stick_left.update(128, 128)
            self._stick_left.set_l3_pressed(False)
            self._stick_right.update(128, 128)
            self._stick_right.set_l3_pressed(False)
            self._stick_left_xy.set_markup(
                _markup_xy(128, 128)
            )
            self._stick_right_xy.set_markup(
                _markup_xy(128, 128)
            )
            for glyph in self._glyphs.values():
                glyph.set_pressed(False)
            self._l3_pressed = False
            self._r3_pressed = False
            self._pintar_titulos_sticks()
            self._last_l2 = None
            self._last_r2 = None
            self._last_lx = None
            self._last_ly = None
            self._last_rx = None
            self._last_ry = None
            self._last_buttons = None
            self._last_l2_lit = None
            self._last_r2_lit = None
            self._gyro_bars.limpar()
            self._gyro_box.hide()
            self._accel_bars.limpar()
            self._accel_box.hide()
            self._touch_view.set_toque(None)
            self._touch_box.hide()
            self._mic_meter.limpar()
            self._aplicar_estado_mic(None, presente=False)
            self._aplicar_acao_mic(acao_mic(None))
            self._aplicar_estado_speaker(None)
            self._aplicar_acoes_speaker(
                acao_speaker_mudo(None), acao_speaker_devolucao(None)
            )
            self._last_gyro = _SENTINELA
            self._last_accel = _SENTINELA
            self._last_touch = _SENTINELA
            self._last_mic = _SENTINELA
            self._last_speaker = _SENTINELA


        def _on_draw_swatch(self, widget: Any, ctx: Any) -> bool:
            desenhar_swatch(
                ctx,
                widget.get_allocated_width(),
                widget.get_allocated_height(),
                self._swatch_rgb,
            )
            return False

    class CaixaDeTetoElastico(Gtk.Bin):  # type: ignore[misc]
        """Dá a um widget do glade o MESMO teto elástico do card."""

        def __init__(self, filho: Any) -> None:
            super().__init__()
            self.set_halign(Gtk.Align.FILL)
            self.set_hexpand(True)
            self.add(filho)

        def do_size_allocate(self, allocation: Any) -> None:
            if allocation.width > LARGURA_CARD_ELASTICA:
                sobra = allocation.width - LARGURA_CARD_ELASTICA
                cortado = allocation.copy()
                cortado.x = allocation.x + sobra // 2
                cortado.width = LARGURA_CARD_ELASTICA
                allocation = cortado
            Gtk.Bin.do_size_allocate(self, allocation)

    class RotuloDeAlturaReservada(Gtk.Label):  # type: ignore[misc]
        """Um rótulo que pede a altura da MAIOR frase que pode receber."""

        def __init__(self) -> None:
            super().__init__()
            self._alturas: dict[int, int] = {}
            self.connect("style-updated", self._esquecer_alturas)

        def _esquecer_alturas(self, *_args: Any) -> None:
            """A fonte mudou: a altura de uma linha mudou junto."""
            self._alturas.clear()

        def altura_reservada(self, largura_perguntada: int = 0) -> int:
            """A altura da frase mais longa possível, em px, na largura REAL."""
            largura = self.get_allocated_width()
            if largura <= 1:
                largura = largura_perguntada
            if largura <= 0:
                return 0
            em_cache = self._alturas.get(largura)
            if em_cache is not None:
                return em_cache
            layout = self.create_pango_layout(
                frase_mais_longa_do_que_chega_ao_jogo()
            )
            layout.set_wrap(self.get_line_wrap_mode())
            layout.set_width(largura * Pango.SCALE)
            altura = int(layout.get_pixel_size()[1])
            self._alturas[largura] = altura
            return altura

        def do_get_preferred_height_for_width(
            self, largura: int
        ) -> tuple[int, int]:
            minimo, natural = Gtk.Label.do_get_preferred_height_for_width(
                self, largura
            )
            reserva = self.altura_reservada(largura)
            return max(minimo, reserva), max(natural, reserva)

        def do_get_preferred_height(self) -> tuple[int, int]:
            minimo, natural = Gtk.Label.do_get_preferred_height(self)
            reserva = self.altura_reservada(
                Gtk.Label.do_get_preferred_width(self)[1]
            )
            return max(minimo, reserva), max(natural, reserva)


else:

    class CaixaDeTetoElastico:  # type: ignore[no-redef]
        """Stub sem GTK3 — a caixa só existe para layout."""

        def __init__(self, filho: Any) -> None:
            self.filho = filho


    class ControllerCard:  # type: ignore[no-redef]
        """Stub para ambientes sem GTK3 (testes/CI sem display)."""

        def __init__(self, *, compact: bool = False) -> None:
            self._compact = compact
            self.titulo: str | None = None
            self.dica_titulo: str | None = None
            self.rotulo: str | None = None
            self.accent: RGB | None = None
            self.degradacao: str | None = None
            self.motion: str | None = None
            self.verdade: str | None = None
            self.sem_leitor: bool = False
            self.gyro: tuple[float, float, float] | None = None
            self.accel: tuple[float, float, float] | None = None
            self.touchpad: tuple[bool, float, float] | None = None
            self.mic_selo: tuple[str, str, str] | None = None
            self.mic_nivel: float | None = None
            self.mic_acao: AcaoMic = acao_mic(None)
            self.uniq: str | None = None
            self.audio_sem_endereco: bool = True
            self.speaker: tuple[int, bool | None] | None = None
            self.speaker_acao_mudo: AcaoSpeaker = acao_speaker_mudo(None)
            self.speaker_acao_devolucao: AcaoSpeaker = acao_speaker_devolucao(None)
            self.speaker_saida_muda: bool | None = None
            #: são só o que entrou pelo `definir_estado_do_canal`.
            self.speaker_canal: str = ""
            self.speaker_regra_do_sono: bool | None = None
            self.speaker_sink: str = ""
            self.perfil_ativo: str | None = (
                None if compact else TEXTO_PERFIL_SEM_DADO
            )
            self.daemon: str | None = None if compact else TEXTO_DAEMON_SEM_DADO

        def definir_estado_global(self, perfil: str, daemon: str) -> None:
            """Guarda o par global (mesmo contrato do widget real)."""
            if self._compact:
                return
            if perfil:
                self.perfil_ativo = perfil
            if daemon:
                self.daemon = daemon

        def update(
            self,
            entry: dict[str, Any],
            state_global: dict[str, Any],
            mic: Any = None,
        ) -> None:
            """Aplica as funções puras (mesma semântica do widget real)."""
            self.titulo = titulo_do_card(entry)
            self.dica_titulo = dica_do_titulo(entry, state_global)
            self.rotulo, _base = rotulo_lightbar(entry, state_global)
            self.accent = accent_do_card(entry, state_global)
            self.degradacao = texto_degradacao(entry)
            self.motion = texto_motion(entry, state_global)
            self.verdade = resumo_do_que_chega_ao_jogo(entry, state_global)
            self.sem_leitor = not isinstance(entry.get("inputs"), dict)
            self.gyro = gyro_do_inputs(entry.get("inputs"))
            self.accel = accel_do_inputs(entry.get("inputs"))
            self.touchpad = touchpad_do_inputs(entry.get("inputs"))
            self.mic_nivel = getattr(mic, "nivel", None) if mic is not None else None
            self.mic_selo = selo_mic(
                getattr(mic, "muted", None) if mic is not None else None
            )
            self.mic_acao = acao_mic(entry)
            self.uniq = uniq_do_entry(entry)
            self.audio_sem_endereco = audio_sem_endereco(entry)
            self.speaker = speaker_do_entry(entry)
            self.speaker_acao_mudo = acao_speaker_mudo(entry)
            self.speaker_acao_devolucao = acao_speaker_devolucao(entry)
            self.speaker_saida_muda = saida_muda_do_entry(entry, mic)

        def definir_estado_do_canal(
            self, estado: str, *, regra_instalada: bool | None = None
        ) -> None:
            """Guarda o estado do canal (mesmo contrato do widget real)."""
            self.speaker_canal = estado or ""
            self.speaker_regra_do_sono = regra_instalada

        def definir_sink_de_saida(self, sink: str) -> None:
            """Guarda o sink deste controle (mesmo contrato do widget real)."""
            self.speaker_sink = sink or ""

        def reset_inputs(self) -> None:
            """IPC sem resposta → "—" (mesmo contrato do widget real)."""
            self.sem_leitor = True

        def show_all(self) -> None:
            """No-op no stub."""

        def destroy(self) -> None:
            """No-op no stub."""


__all__ = [
    "ALL_BUTTONS",
    "CROMO_DA_MOLDURA_DE_SENSOR",
    "DICA_AUDIO_SEM_ENDERECO",
    "DICA_BLOCO_SPEAKER",
    "DICA_CANAL_ACORDADO",
    "DICA_CANAL_DORMINDO",
    "DICA_CANAL_E_PADRAO",
    "DICA_MIC_ATIVAR",
    "DICA_MIC_DEVOLVER",
    "DICA_MIC_SEM_LEITURA",
    "DICA_MIC_SILENCIAR",
    "DICA_SPEAKER_ATIVAR",
    "DICA_SPEAKER_DEVOLVER",
    "DICA_SPEAKER_DEVOLVER_SEM_POSSE",
    "DICA_SPEAKER_ESCALA",
    "DICA_SPEAKER_POSSE_NOSSA",
    "DICA_SPEAKER_SEM_DADO",
    "DICA_SPEAKER_SILENCIAR",
    "DICA_TITULO_SEM_VPAD",
    "GLYPH_ESPACO_COMPACTO",
    "GLYPH_ESPACO_UNICO",
    "GLYPH_FATOR_UNICO_OITAVOS",
    "GLYPH_PX_POR_DEGRAU_DE_FONTE",
    "GLYPH_SIZE_BASE",
    "GRID_BOTOES",
    "L2_R2_THRESHOLD",
    "LADO_DO_SWATCH",
    "LARGURA_BARRA_GATILHO_COMPACTO",
    "LARGURA_BARRA_GATILHO_UNICO",
    "LARGURA_CARD_ELASTICA",
    "LARGURA_CARD_UNICO",
    "LARGURA_GYRO_COMPACTO",
    "LARGURA_GYRO_UNICO",
    "MOTIVOS_DEGRADACAO_LEIGOS",
    "ROTULO_LIGHTBAR_SEGURADA",
    "ROTULO_STICK_DIR",
    "ROTULO_STICK_ESQ",
    "STICK_SIZE_COMPACT",
    "STICK_SIZE_SINGLE",
    "SUFIXO_CANAL_ACORDADO",
    "SUFIXO_CANAL_DORMINDO",
    "TEXTO_AUDIO_SEM_ENDERECO",
    "TEXTO_BOTAO_MIC_ATIVAR",
    "TEXTO_BOTAO_MIC_DEVOLVER",
    "TEXTO_BOTAO_MIC_SEM_LEITURA",
    "TEXTO_BOTAO_MIC_SILENCIAR",
    "TEXTO_BOTAO_SPEAKER_ATIVAR",
    "TEXTO_BOTAO_SPEAKER_DEVOLVER",
    "TEXTO_BOTAO_SPEAKER_SEM_DADO",
    "TEXTO_BOTAO_SPEAKER_SILENCIAR",
    "TEXTO_MIC_ALVO_NAO_HONRADO",
    "TEXTO_MIC_AUSENTE",
    "TEXTO_MIC_SEM_MUTE",
    "TEXTO_SELO_SAIDA_MUDA",
    "TEXTO_SELO_SEM_SOM",
    "TEXTO_SPEAKER_SEM_DADO",
    "TITULO_SPEAKER",
    "AcaoMic",
    "AcaoSpeaker",
    "CaixaDeTetoElastico",
    "ControllerCard",
    "acao_mic",
    "acao_speaker_devolucao",
    "acao_speaker_mudo",
    "accel_do_inputs",
    "accent_do_card",
    "audio_sem_endereco",
    "cor_do_swatch",
    "dedos_do_inputs",
    "desenhar_swatch",
    "dica_canal_sem_a_regra",
    "dica_do_titulo",
    "frase_do_alvo_do_mic",
    "frase_mais_longa_do_que_chega_ao_jogo",
    "glyph_size",
    "glyph_size_unico",
    "gyro_do_inputs",
    "rotulo_lightbar",
    "saida_muda_do_entry",
    "speaker_do_entry",
    "texto_degradacao",
    "texto_motion",
    "titulo_do_card",
    "touchpad_do_inputs",
    "uniq_do_entry",
]
