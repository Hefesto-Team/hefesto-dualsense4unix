"""controller_card.py — card de UM controle na aba Status (STATUS-02/03 + BT-03).

A aba Status deixou de ser single-controller: cada DualSense conectado ganha
um card com identidade própria — título pelo ``player_slot`` de sessão,
bateria própria, swatch da cor CRUA da lightbar — e os inputs ao vivo DAQUELE
controle (barras L2/R2, dois ``StickPreviewGtk`` e o grid 4x4 de
``ButtonGlyph``) com os traços pintados na cor da lightbar dele, ajustada para
contrastar com o fundo (decisão D8: o swatch mostra a cor crua; só os TRAÇOS
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
  era o único tamanho da interface fora do alcance do ajuste de escala.

STATUS-SIMETRIA-02 é o veredito sobre aquela entrega: só distanciou as
coisas. Espalhar os módulos pela largura resolveu o amontoamento e não
produziu leitura. As seis mudanças desta rodada, todas medidas na tela do usuário:

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

SOM-01 é a terceira rodada, e vem dos três pedidos feitos olhando a v2
(quase perfeita): o alto-falante abaixo do microfone,
os botões do controle (xis, quadrado, bola, triângulo e afins) maiores e mais
espaçados, e a janela que se expande. As três mudanças:

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
  sprint); o modo nativo segue as mesmas regras desde 24/09/2026 (a barra é
  do Hefesto nele também). Sem cor conhecida, os traços usam o accent neutro
  (#6272a4) ajustado.
* BT-03: ``vpad_backend == "uinput"`` com ``vpad_motivo`` preenchido acende
  uma linha visível de degradação com o motivo em palavras leigas
  (``MOTIVOS_DEGRADACAO_LEIGOS``). O texto NUNCA crava o mecanismo do sono
  BT como causa — diz o que aconteceu com o "modo completo", não por quê.
* ``inputs is None`` → a área de inputs mostra "—" (sem leitor); o card
  NUNCA congela o último valor como se fosse vivo.
* ``update()`` tem DIFF interno por seção (título/bateria/cor/degradação/
  inputs): repetir o mesmo estado a 10 Hz não re-renderiza nada.

Sem timers RECORRENTES próprios (quem agenda o tique é a mixin de status, com
os timers que a mixin JÁ tinha; o aceite do STATUS-02 é diff contra esse baseline)
e sem popups (cosmic-epoch#2497): tudo inline, sempre visível. A ÚNICA exceção
é o repouso do controle deslizante de volume (SOM-02/E1): um
``GLib.timeout_add`` de UM disparo, armado por gesto humano e desarmado ao
disparar ou ao soltar o botão do mouse — sem ele, arrastar o controle vira uma
rajada de IPC bloqueante (um pedido por pixel). Como os demais widgets da casa,
há a variante GTK real e um stub puro para ambiente sem GTK (testes/CI sem
display).
"""
from __future__ import annotations

from typing import Any, Final, NamedTuple

from hefesto_dualsense4unix.interface.sensores import (
    posicao_normalizada,
)

RGB = tuple[int, int, int]


GRID_BOTOES: Final[list[list[str]]] = [
    ["cross",   "circle",    "square",    "triangle"],
    ["dpad_up", "dpad_down", "dpad_left", "dpad_right"],
    ["l1",      "r1",        "l2",        "r2"],
    ["share",   "options",   "ps",        "touchpad"],
]

ALL_BUTTONS: Final[list[str]] = [b for linha in GRID_BOTOES for b in linha]

L2_R2_THRESHOLD: Final[int] = 30


TEXTO_BOTAO_MIC_ATIVAR: Final[str] = "Ativar"
TEXTO_BOTAO_MIC_SILENCIAR: Final[str] = "Silenciar"
TEXTO_BOTAO_MIC_DEVOLVER: Final[str] = "Liberar"
TEXTO_BOTAO_MIC_SEM_LEITURA: Final[str] = "Silenciar"

DICA_MIC_SEM_LEITURA: Final[str] = (
    "O daemon ainda não leu o estado do microfone deste controle. Sem saber "
    "se ele está mudo, mandar mutar ou desmutar seria chute."
)


TEXTO_MIC_ALVO_NAO_HONRADO: Final[str] = (
    "O volume foi para o microfone de OUTRO controle: o Hefesto não conseguiu "
    "mirar este, e o pedido caiu no controle PRIMÁRIO. O perfil deste controle "
    "não mudou."
)


CANAL_SONS_DO_JOGO: Final[str] = "jogo"
CANAL_TODO_O_PC: Final[str] = "tudo"

CANAL_NADA_NO_CONTROLE: Final[str] = "nada"


ROTA_DO_CANAL: Final[dict[str, int]] = {
    CANAL_SONS_DO_JOGO: 2,
    CANAL_TODO_O_PC: 3,
    CANAL_NADA_NO_CONTROLE: 0,
}

DICA_AUDIO_SEM_ENDERECO: Final[str] = (
    "Este controle não publicou endereço, e sem ele todo comando de som iria "
    "para o controle PRIMÁRIO — outro controle, com o título deste na frente. "
    "O som volta sozinho quando o endereço aparecer."
)

TEXTO_SELO_SAIDA_MUDA: Final[str] = "Saída muda"


_XY_MARKUP: Final[str] = "X:{x:>3}\nY:{y:>3}"


def _markup_xy(x: int, y: int) -> str:
    """``"X:128" / "Y:128"`` — o par de eixos, em mono, sem a lateral."""
    return _XY_MARKUP.format(x=x, y=y)


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

    * O modo nativo não tem ramo desde 24/09/2026 (`D-2409-NO-NATIVO-A-TELA-
      MOSTRA-A-COR`): a barra é do Hefesto no Nativo também, e «Em Nativo o
      jogo é dono do LED» virou fato errado; o Nativo cai nas regras abaixo.
    * ``lightbar_disputada`` (ESCRITOR-CRU-01) → "a Steam tem este controle
      aberto"; o accent segue a última cor NOSSA. Vem antes de tudo o mais
      porque é um aviso sobre a CONFIANÇA no valor, não sobre o valor: com a
      Steam segurando o hidraw, o que a classe LED devolve é o que o Hefesto
      PEDIU — a madrugada de 16/08 leu ``[0 255 0]`` com a barra apagada e
      ``[0 255 0]`` com a barra verde. Dizer "apagada" ou pintar a bolinha de
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
    O chamador ajusta o contraste antes de pintar traço.
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


ATIVIDADE_FRESCA_S: Final[float] = 3.0


def _item_do_vpad(
    entry: dict[str, Any], state_global: dict[str, Any]
) -> dict[str, Any] | None:
    """O bloco `rumble_ff.per_vpad` do vpad DESTE controle; ``None`` = não há.

    O dono único do casamento controle→vpad, e o casamento é pelo endereço:
    o serviço publica em cada item o `uniq` do controle físico que aquele vpad
    serve. O número do jogador não serve, porque fora do co-op todos os
    conectados vêm como jogador 1 e só o primário alimenta o vpad do P1.
    Controle sem endereço, ou sem vpad próprio, não casa com nenhum.
    """
    uniq = uniq_do_entry(entry)
    rumble_ff = state_global.get("rumble_ff")
    per_vpad = rumble_ff.get("per_vpad") if isinstance(rumble_ff, dict) else None
    if uniq is None or not isinstance(per_vpad, list):
        return None
    for item in per_vpad:
        if isinstance(item, dict) and item.get("uniq") == uniq:
            return item
    return None


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

    O par ``(0, 0)`` fresco também some: ele é o pedido do jogo para PARAR, e a
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
    hardware (`ABS_MT_SLOT 0..1`, medido no aparelho do usuário), e o payload os
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
        return AcaoMic(TEXTO_BOTAO_MIC_ATIVAR, False, True, "")
    if isinstance(audio.get("mic_mudo_desejado"), bool):
        return AcaoMic(TEXTO_BOTAO_MIC_DEVOLVER, None, True, "")
    return AcaoMic(TEXTO_BOTAO_MIC_SILENCIAR, True, True, "")


def saida_muda_do_entry(entry: Any, mic: Any = None) -> bool | None:
    """A CAMADA 1 (o sink do PipeWire) está muda? ``None`` = não dá para saber.

    SENSOR-VIVO-01/E5 e SOM-02/E5, item 4 — são a mesma verdade vista dos dois
    lados. Com o sink do controle mudo no PipeWire, mover o volume do
    registrador HID (a camada 2, a única que a janela alcança nos dois
    transportes) não produz som nenhum: o bloco ficaria dizendo uma
    porcentagem enquanto nada sai.

    Duas posições aceitas, nesta ordem, e nenhuma das duas inventada aqui:

    1. o PAYLOAD do daemon, em ``speaker.saida_muda`` ou ``audio.saida_muda`` —
       é onde a leitura mora quando quem lê o PipeWire é o daemon;
    2. a leitura do microfone da própria janela (``LeituraMic.saida_muda``), lida
       por ``getattr`` defensivo — é onde a posição mora se quem passar a ler o sink
       for o ``app/mic_monitor.py``, que já é o leitor de PipeWire desta
       interface e já roda fora da thread GTK.

    **A posição 2 EXISTE desde então, e é por essa posição que o selo acende hoje.** O
    ``MicMonitor`` ganhou a thread supervisora do sink (``_saidas_mudas``,
    `app/mic_monitor.py:335`, preenchida em `:622` e servida em `:507`), e a
    ``LeituraMic`` carrega o campo. A posição 1 (o daemon publicar
    ``speaker.saida_muda``) continua não existindo, e continua sendo um encaixe
    válido — quem a implementar não precisa tocar no card.

    Isto **substitui** a afirmação anterior desta docstring ("hoje nenhuma das
    duas existe", medida em 01/08/2026), que caducou sem que ninguém percebesse
    e custou um ensaio: em 17/08 o JANELA-CORTADA-01 tentou revelar o selo
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


def frase_do_alvo_do_mic(honrado: bool | None) -> str:
    """O que dizer sobre DE QUEM foi o microfone que o daemon mexeu (função pura)."""
    return TEXTO_MIC_ALVO_NAO_HONRADO if honrado is False else ""


def cor_do_swatch(entry: Any) -> RGB | None:
    """A cor CRUA do quadradinho ao lado do título. ``None`` = desconhecida."""
    return _rgb3(entry.get("lightbar_rgb") if isinstance(entry, dict) else None)


__all__ = [
    "ALL_BUTTONS",
    "DICA_AUDIO_SEM_ENDERECO",
    "DICA_MIC_SEM_LEITURA",
    "DICA_TITULO_SEM_VPAD",
    "GRID_BOTOES",
    "L2_R2_THRESHOLD",
    "ROTULO_LIGHTBAR_SEGURADA",
    "TEXTO_BOTAO_MIC_ATIVAR",
    "TEXTO_BOTAO_MIC_DEVOLVER",
    "TEXTO_BOTAO_MIC_SEM_LEITURA",
    "TEXTO_BOTAO_MIC_SILENCIAR",
    "TEXTO_MIC_ALVO_NAO_HONRADO",
    "TEXTO_SELO_SAIDA_MUDA",
    "AcaoMic",
    "acao_mic",
    "accel_do_inputs",
    "cor_do_swatch",
    "dedos_do_inputs",
    "dica_do_titulo",
    "frase_do_alvo_do_mic",
    "gyro_do_inputs",
    "rotulo_lightbar",
    "saida_muda_do_entry",
    "speaker_do_entry",
    "touchpad_do_inputs",
    "uniq_do_entry",
]
