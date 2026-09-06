"""Aba Lightbar + Player LEDs."""
# ruff: noqa: E402
from __future__ import annotations

from typing import Any

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions import footer_actions
from hefesto_dualsense4unix.app.actions.base import WidgetAccessMixin
from hefesto_dualsense4unix.app.alvo_de_edicao import AlvoDeEdicao, alvo_de_edicao
from hefesto_dualsense4unix.app.ipc_bridge import (
    led_set_detalhado,
    player_leds_set_detalhado,
)
from hefesto_dualsense4unix.app.textos_de_aplicacao import (
    alvo_fora_da_mesa,
    coop_manda_nas_luzes,
    frase_de_guardado,
    frase_do_desfecho,
    modo_nativo_manda_no_output,
)
from hefesto_dualsense4unix.utils.i18n import _

#: APLICAR-VERDADE-01/E2: a frase de quando NÃO HOUVE RESPOSTA do daemon. Ela
#: continua palavra por palavra a de sempre — a cura não pode trocar uma
#: mentira por outra, e com o Hefesto realmente desligado a aba Sistema É o
#: lugar certo para onde mandar.
_AVISO_HEFESTO_DESLIGADO = (
    "Não consegui aplicar a cor — o Hefesto pode estar desligado "
    "(ligue na aba Sistema)"
)

#: A frase do CAMINHO FELIZ, e a palavra dela é "enviada" de propósito.
#:
#: Ela dizia "Cor aplicada no controle", e isso é uma afirmação que o produto
#: NÃO tem como sustentar: o ``ok`` que a escolhe significa "o daemon aceitou o
#: pedido" (``led.set``) ou "a seção ``leds`` entrou no ``apply_draft``" — nos
#: dois casos, "o report saiu", nunca "a barra acendeu".
#:
#: A medição que obriga a troca (LIGHTBAR-BT-RESET-01, provado ao vivo em
#: 17-18/07 e ainda em vigor na mesa dela em 09/08): por Bluetooth, depois que o
#: daemon adota o controle, o firmware perde o claim da lightbar e passa a
#: ACEITAR E IGNORAR as escritas de cor — 330 mil escritas ignoradas com a barra
#: apagada. Nesse estado a frase antiga era falsa em 100% das vezes, e ela passou
#: dias acreditando que a cor tinha ido, porque a janela dizia que sim.
#:
#: Por que não existe aqui uma confirmação de verdade: a única leitura de volta
#: que o produto tem é o nó sysfs ``multi_intensity``, e ele é o ECO do nosso
#: pedido, não a lâmpada (``core/sysfs_leds.get_rgb``: o valor sai do último
#: write pela classe LED; o caminho interno do kernel que acende a barra nunca o
#: atualiza, e escrita por hidraw também não). Confirmar por ele seria trocar
#: uma afirmação sem prova por outra. Quem sabe se acendeu é o olho dela.
#:
#: O vocabulário é EMPRESTADO da própria tela, não inventado: o botão que
#: dispara isto se descreve como "Envia cor selecionada para a barra de LED do
#: controle" (``main.glade``, descrição acessível de ``lightbar_apply``) e o
#: seletor de cor diz "a cor só vai ao controle quando você clicar em Aplicar no
#: controle". O "(N% de brilho)" fica: o brilho é o que foi ENVIADO, e é a
#: informação que ela usa para saber que o seletor viajou junto.
_TOAST_COR_ENVIADA = "Cor enviada ao controle ({pct}% de brilho)"

#: O mesmo assunto, quando a frase que o segue é a do GUARDADO (D-9). O brilho
#: continua ali pelo motivo de sempre: é o que ela usa para saber que o seletor
#: viajou junto — e num ajuste guardado saber O QUE ficou guardado importa mais
#: ainda, porque ela só vai ver o efeito quando o controle voltar.
_ASSUNTO_COR = "Cor ({pct}% de brilho)"

#: A frase seca do "Apagar", e o assunto dela quando o que segue é o GUARDADO.
#:
#: Conserto 1.5: este era o QUINTO gesto de saída da aba Lightbar e o único que
#: continuava afirmando fato consumado — "Lightbar apagada" — com o alvo fora
#: da mesa ou em Modo Nativo, onde nenhum byte sai. Ele escreve pela MESMA rota
#: por-MAC do "Aplicar no controle" logo ao lado (`led_set((0, 0, 0),
#: uniq=estado_alvo.uniq)` -> `led.set` -> `apply_output_for` -> "registrado"
#: -> `guardado_em: [uniq]`), então mentia pelo mesmo motivo — e o comentário
#: dentro do próprio método já registrava isso desde a APLICAR-VERDADE-01.
#:
#: O assunto vira INFINITIVO ("Apagar a lightbar") porque a frase do guardado
#: fala do que ainda VAI acontecer; "Lightbar apagada — guardado" seria a
#: afirmação e a ressalva se contradizendo dentro da mesma linha. A palavra é a
#: do botão que o dispara ("Apagar", `lightbar_off` no `main.glade`).
_TOAST_LIGHTBAR_APAGADA = "Lightbar apagada"
_ASSUNTO_APAGAR = "Apagar a lightbar"

#: Aviso D4 (sprint cores-e-led-automaticos): cor única em "Todos" com o
#: automático ligado seria INVISÍVEL (a paleta vence o global no merge do
#: backend) — então o fluxo desliga o toggle e avisa, nunca em popup.
_AVISO_D4 = "Cores automáticas desligadas para aplicar uma cor única"

#: PLAYER-01 entrega 6: recusa do envio de desenho SEM destinatário. Quando a
#: janela ainda não sabe quem está na mesa (nenhum tique do daemon), o pedido
#: saía sem ``uniq`` e o daemon o gravava no default GLOBAL — uma camada ABAIXO
#: da automática no merge por campo do backend (D5). O automático o desfazia no
#: reforço seguinte, e era esse o "volta sozinho" que ela relatou. Recusar é a
#: única resposta honesta: escrever numa camada que será sobrescrita é pior que
#: não escrever, porque parece ter funcionado por meio segundo.
_AVISO_SEM_DESTINATARIO = (
    "Ainda não sei quais controles estão ligados — espere um instante e "
    "tente de novo (mandar sem destinatário seria desfeito pela numeração "
    "automática)"
)

#: L12 (25/08/2026) — a frase que PARA DE ESCONDER o efeito do "Todos".
#:
#: **O fato (M7).** Clicar "Desenho do P2" com o alvo em "Todos" manda o MESMO
#: bitmask para cada MAC da mesa, e grava esse mesmo desenho no override de
#: cada um: os quatro controles passam a exibir o desenho do jogador 2, e o
#: perfil dela guarda assim. É a invariante do co-op quebrada exatamente na
#: superfície que existe para distinguir jogadores — e **nada na tela avisava**.
#:
#: **O que esta frase NÃO é:** o conserto. As duas respostas possíveis — (a) os
#: botões P1..P4 recusarem com o alvo em "Todos", como ``_enviar_player_leds``
#: já sabe recusar; (b) "Todos" passar a significar *cada um com o desenho do
#: próprio número*, que ``player_led_pattern(slot)`` já sabe produzir — são
#: escolha DELA, e estão no §8 da sprint. Enquanto a resposta não vem, o
#: mínimo honesto é a tela contar o que o clique fez. A frase sai da tela junto
#: com a resposta dela, seja qual for.
#:
#: "Todas acesas"/"Todas apagadas" também a recebem, e está certo: lá o
#: para-todos é o sentido do botão, e dizer em quantos controles ele pegou
#: continua sendo informação, não aviso.
_AVISO_MESMO_DESENHO_NOS_QUATRO = (
    "O mesmo desenho foi para os {n} controles ligados."
)

#: PLAYER-01: desenho vazio = SEM opinião. Um ``player_leds`` todo apagado no
#: perfil nunca chega ao hardware — a camada automática (o padrão do NÚMERO do
#: controle) vence o default global no merge por campo, e um override por-MAC
#: idêntico ao global é podado por ``with_controller_leds``. Então "tudo
#: apagado no rascunho" significa, com certeza, "quem manda é o automático" —
#: e é isso que a moldura passa a dizer, em vez de mostrar nada escolhido
#: enquanto o controle exibe três luzes acesas.
_DESENHO_VAZIO: tuple[bool, bool, bool, bool, bool] = (False,) * 5


def mensagem_de_secao_fora(resposta: Any) -> str | None:
    """Frase honesta quando o daemon RESPONDEU e a cor não entrou (E2).

    Devolve ``None`` quando NÃO houve resposta (``apply_draft_detalhado`` deu
    ``None``: daemon offline ou erro de transporte) — aí quem fala é a frase de
    sempre, a que manda ligar o Hefesto na aba Sistema. Esta função só tem
    opinião sobre o caso oposto: o daemon está vivo, respondeu, e a seção não
    entrou. Antes da APLICAR-VERDADE-01/E2 os dois casos chegavam aqui como o
    mesmo ``False`` e a aba mandava caçar o problema no lugar errado.

    O VOCABULÁRIO é emprestado do rodapé, não reinventado: os nomes das seções
    saem de ``footer_actions._lista_de_secoes`` (o mesmo ``_NOMES_DE_SECAO`` que
    traduz ``leds`` para "luzes"), e o caso "respondeu e nada entrou, sem dizer
    o que falhou" é devolvido pelo próprio ``_mensagem_de_aplicacao``. Frase
    copiada entre superfícies diverge — é o que a RADAR-01 mediu.

    Por que NÃO usar ``_mensagem_de_aplicacao`` também no caso com ``failed``:
    o payload da Lightbar tem uma seção só (``leds``), então uma falha dela
    deixa ``applied`` vazio e o rodapé responderia "Nada foi aplicado ao
    controle." — verdade, mas sem o nome da seção, que é exatamente a
    informação que esta entrega existe para levar até a tela. A frase daqui diz
    as duas coisas: que o Hefesto está ligado (logo, não adianta ir na aba
    Sistema) e QUAL seção ficou de fora.
    """
    if not isinstance(resposta, dict) or resposta.get("status") != "ok":
        return None
    secoes = footer_actions._lista_de_secoes(resposta.get("failed"))
    if secoes:
        return _("O Hefesto está ligado, mas não entrou: {secoes}").format(
            secoes=secoes
        )
    return footer_actions._mensagem_de_aplicacao(resposta)


def somar_os_corpos(corpos: list[Any]) -> dict[str, Any] | None:
    """Junta em UM corpo as N respostas de um envio por MAC ("Todos", R-14).

    BG-01 (26/08/2026). Com o alvo em "Todos" esta aba manda um pedido POR
    CONTROLE — é a R-14/R-17, e é o que faz a cor única vencer a paleta
    automática sem desligar o automático de ninguém. O daemon responde N
    vezes; a tela diz UMA frase. Somar é unir ``aplicado_em`` e ``guardado_em``
    das N respostas, sem repetir MAC e sem perder a ordem em que os controles
    foram atendidos — o mesmo vocabulário que
    ``ipc_bridge.destinos_da_aplicacao`` lê, e que
    ``textos_de_aplicacao.frase_do_desfecho`` decide.

    Somar em vez de olhar só a primeira resposta importa na mesa cheia dela:
    com dois controles na mesa e um terceiro que caiu, a soma diz *aplicado em
    2* e *guardado em 1* — escolher uma resposta ao acaso diria uma das duas
    metades como se fosse a história inteira.

    Devolve ``None`` quando NENHUMA das N respostas veio (daemon desligado,
    transporte): aí não há corpo a ler, e quem chama cai na frase de sempre.
    Uma resposta que não é dicionário é ignorada pelo mesmo motivo que
    ``_corpo_do_daemon`` a descarta — não é o daemon falando.

    ``motivo`` não é somado, e é medido: nem ``led.set`` nem
    ``led.player_set`` publicam esse campo (``daemon/ipc_handlers.py``, os dois
    devolvem ``status``/``aplicado_em``/``guardado_em``, mais ``bits`` no
    segundo). Se um dia publicarem, esta função tem de crescer junto — está
    escrito aqui de propósito, em vez de descoberto na tela.
    """
    aplicado_em: list[str] = []
    guardado_em: list[str] = []
    houve_resposta = False
    for corpo in corpos:
        if not isinstance(corpo, dict):
            continue
        houve_resposta = True
        aplicado, guardado = ipc_bridge.destinos_da_aplicacao(corpo)
        for mac in aplicado:
            if mac not in aplicado_em:
                aplicado_em.append(mac)
        for mac in guardado:
            if mac not in guardado_em:
                guardado_em.append(mac)
    if not houve_resposta:
        return None
    return {
        "status": "ok",
        "aplicado_em": aplicado_em,
        "guardado_em": guardado_em,
    }


def frase_do_envio(
    assunto: str,
    enviado: str,
    corpo: Any,
    host: Any,
    *,
    coop_aplica: bool = False,
) -> str:
    """A frase do gesto decidida pelo CORPO do daemon (BG-01, 26/08/2026).

    **Quem decide é ``textos_de_aplicacao.frase_do_desfecho``, e só ele.** Esta
    função não lê ``aplicado_em``, não conhece a ordem das razões e não tem
    opinião sobre ramo nenhum: ela chama o dono da decisão e, no ramo do
    APLICADO — e só nele —, devolve a frase que esta aba já tinha.

    **Por que a troca de palavra, e por que ela não é preferência.** O ramo do
    aplicado sai de lá como *"<assunto> aplicado"*, e "aplicada" é uma
    afirmação que esta aba MEDIU como falsa: LIGHTBAR-BT-RESET-01 (17-18/07,
    ainda em vigor em 09/08) — por Bluetooth, depois que o daemon adota o
    controle, o firmware ACEITA E IGNORA as escritas de cor; foram 330 mil
    escritas ignoradas com a barra apagada. O que o daemon sabe é que o byte
    saiu no fio, que é exatamente o que "enviada" diz e "aplicada" não. A
    decisão está registrada em ``_TOAST_COR_ENVIADA``, com a medição; trocar a
    palavra aqui seria desfazê-la em silêncio.

    **Se o ramo do aplicado mudar de forma lá, esta função para de reconhecê-lo**
    e a frase de lá aparece na tela com a palavra que esta aba recusa. É um
    acoplamento REAL, e por isso ele tem régua: ``test_a_regua_do_ramo_aplicado``
    em ``tests/unit/test_aplicar_verdade_ponte_lightbar.py`` reprova no dia em
    que as duas formas divergirem, em vez de a divergência sair na tela dela.

    ``coop_aplica`` viaja intacto: só quem escreve os 5 LEDs de jogador o passa
    ``True`` (``_COOP_LAYER_FIELDS = ("player_leds",)`` no backend), e a cor da
    lightbar nunca foi governada pelo co-op.
    """
    frase = frase_do_desfecho(assunto, corpo, host, coop_aplica=coop_aplica)
    return enviado if frase.startswith(f"{assunto} aplicado") else frase


def nome_do_desenho(bits: tuple[bool, ...] | list[bool]) -> str | None:
    """"desenho do P3" quando ``bits`` é um padrão canônico; ``None`` se não.

    Os padrões vêm de ``core.led_control.player_led_pattern`` — a MESMA fonte
    que o daemon usa para acender, para a janela nunca batizar de "P3" um
    desenho que o hardware não chamaria assim. A varredura vai até 8 porque o
    espaço de numeração é único entre DualSense, externos e co-op (R-24/R-25)
    e um DualSense pode legitimamente cair no 5 ou acima.
    """
    from hefesto_dualsense4unix.core.led_control import player_led_pattern

    alvo = tuple(bool(b) for b in bits)
    for numero in range(1, 9):
        if tuple(player_led_pattern(numero)) == alvo:
            return f"desenho do P{numero}"
    return None


#: L5 (25/08/2026) — o PREFIXO do rótulo de estado das 5 luzes, e ele é o
#: conserto inteiro desta tarefa.
#:
#: A frase dizia **"Aceso agora:"**, e isso é uma leitura de volta que o
#: produto NÃO TEM. ``texto_do_desenho_aceso`` é função PURA do rascunho —
#: nada nela consulta o aparelho — e o mapa de canais mede que consultar não é
#: possível: ``luz.led_jogador.leitura@dualsense`` tem ``cabo_aceita = não`` e
#: ``radio_aceita = não``. Não há canal de leitura em transporte nenhum.
#:
#: O vocabulário não é inventado: é o mesmo que esta casa já usa para separar
#: o pedido do efeito — ``_TOAST_COR_ENVIADA`` diz *"Cor enviada ao
#: controle"* (nunca "acesa"), e o ``lightbar_source == "desired"`` do daemon
#: significa, literalmente, *a última cor que mandamos*.
#:
#: Quem cobra isto é ``tests/unit/test_lightbar_lexico_sem_leitura.py``: um
#: rótulo desta aba não pode afirmar estado de barra enquanto o mapa não
#: registrar canal de leitura para a chave correspondente.
_PREFIXO_DESENHO = "Desenho que mandamos"


def texto_do_desenho_aceso(
    player_leds: tuple[bool, ...] | list[bool],
    slot: int | None,
    *,
    coop_ligado: bool = False,
    descricao_livre: str = "",
) -> str:
    """A frase do desenho das 5 luzes EM VIGOR (PLAYER-01 entrega 5, L5).

    Função PURA: a moldura só sabia mostrar o RASCUNHO, e a camada automática
    nunca entra nele — num perfil recém-criado ela via "nada escolhido"
    enquanto o controle exibia três luzes acesas. Aqui a janela responde a
    pergunta útil: *qual desenho o produto está mandando, e por ordem de
    quem?*

    **O que ela NÃO responde, e por quê (L5):** *o que está aceso*. Ver
    ``_PREFIXO_DESENHO`` — não existe canal de leitura de LED de jogador, em
    transporte nenhum, e a frase antiga afirmava um estado do aparelho que
    ninguém pode conferir.

    As três respostas possíveis, na ordem em que o backend resolve:

    1. **co-op ligado** — a camada de co-op sobrescreve o desenho ACIMA da
       escolha manual, por construção. Com ele ativo, escolher desenho aqui
       não adianta, e a tela diz isso em vez de deixá-la descobrir sozinha;
    2. **escolha dela** — qualquer desenho não-vazio no rascunho vence a
       camada automática por campo (D5), com as cores automáticas ligadas ou
       desligadas;
    3. **automático** — rascunho vazio: vale o desenho do NÚMERO do controle.
       Sem número conhecido (registro ainda sem opinião), a frase diz apenas
       que o automático manda, sem inventar um número.
    """
    if coop_ligado:
        return (
            f"{_PREFIXO_DESENHO}: o do co-op — com o co-op ligado, é ele que "
            "manda nas 5 luzes."
        )
    bits = tuple(bool(b) for b in player_leds)
    if bits != _DESENHO_VAZIO:
        nome = nome_do_desenho(bits) or descricao_livre or "desenho próprio"
        return f"{_PREFIXO_DESENHO}: {nome} — escolha sua."
    if isinstance(slot, int) and slot >= 1:
        return (
            f"{_PREFIXO_DESENHO}: desenho do P{slot} — automático, do número "
            "deste controle."
        )
    return (
        f"{_PREFIXO_DESENHO}: o desenho automático do número do controle "
        "(nenhuma escolha sua)."
    )


class LightbarActionsMixin(WidgetAccessMixin):
    """Controla a aba Lightbar + Player LEDs."""

    _current_rgb: tuple[int, int, int] = (255, 128, 0)
    # Luminosidade em [0.0, 1.0]; 1.0 = máximo (FEAT-LED-BRIGHTNESS-01).
    _current_brightness: float = 1.0
    # Valor pendente de brightness a persistir no próximo save de perfil.
    # Usado enquanto FEAT-PROFILE-STATE-01 (DraftConfig) não está disponível.
    _pending_brightness: float = 1.0
    # Guard para bloquear o handler durante refresh programático do slider.
    _refresh_guard: bool = False
    # BOTÃO-QUE-NÃO-MENTE-01 (entrega 1): houve movimento no controle
    # deslizante de brilho que ainda NÃO foi escrito no hardware. Cada pixel de
    # arraste apenas marca isto; quem escreve é o soltar. Sem a marca, um
    # clique no trilho que não muda valor mandaria uma escrita à toa.
    _brilho_pendente: bool = False
    # Idempotência da fiação do "aplicar ao soltar": ``install_lightbar_tab``
    # tem DOIS pontos de chamada em ``app.py`` (janela normal e janela que
    # nasce oculta na bandeja). Conectar duas vezes o mesmo sinal mandaria duas
    # escritas por gesto — o dobro de tráfego na fila que o adiamento existe
    # para poupar.
    _soltar_fiado: bool = False

    def _uniqs_conectados(self) -> list[str]:
        """MACs dos controles CONECTADOS, na ordem do índice (R-14).

        Fonte: ``_target_uniq_by_index``, o mapa que a aba Status recalcula do
        ``state_full`` a cada tick (só controles conectados entram). Controle
        sem MAC estável (handle por path) fica de fora — para ele não existe
        override por-controle, e a escrita dele continua sendo a global.

        Lista vazia = a GUI ainda não sabe quem está na mesa (nenhum tick do
        daemon, host parcial de teste). Os chamadores tratam isso como
        "escopo desconhecido" e caem no caminho global de sempre, nunca em
        broadcast disfarçado de por-controle.
        """
        mapa = getattr(self, "_target_uniq_by_index", None)
        if not isinstance(mapa, dict):
            return []
        vistos: set[str] = set()
        saida: list[str] = []
        for _idx, uniq in sorted(mapa.items(), key=lambda kv: kv[0]):
            if isinstance(uniq, str) and uniq and uniq not in vistos:
                vistos.add(uniq)
                saida.append(uniq)
        return saida

    def _edit_uniq(self) -> AlvoDeEdicao:
        """O alvo de edição (PERFIL-04), com o estado explícito ao lado do MAC.

        Vem do dono único (``app/alvo_de_edicao.py``) — nunca mais um
        ``getattr`` cru no atributo legado. Z2-1 (24/08/2026): antes disto o
        ``None`` do ``getattr`` respondia por DUAS coisas diferentes — "ela
        escolheu Todos" e "a janela ainda não sabe" — e a segunda escrevia
        global em silêncio. Quem só quer o endereço lê ``.uniq`` (``None`` nos
        dois casos, como sempre); quem VAI ESCREVER verifica
        ``.desconhecido`` primeiro.
        """
        return alvo_de_edicao(self)

    def _auto_preview_slot(self) -> int | None:
        """Slot do controle em edição QUANDO a prévia deve mostrar a cor
        AUTOMÁTICA (achado ao vivo 2026-07-17).

        Com "Cores automáticas por controle" LIGADO e um controle específico
        selecionado no seletor do banner, o que ele EXIBE é a cor da paleta
        (azul/vermelho...), não a cor manual global — mas a prévia mostrava a
        manual (roxo), MENTINDO. ``None`` = mostrar a cor manual (automático
        desligado, alvo "Todos", ou número desconhecido).

        L7 (25/08/2026) — o número vem de ``_edit_target_slot``, o número
        CANÔNICO do alvo, mantido pela aba Status a partir do ``state_full``
        (``status_actions.py:1998``) e já usado por
        ``_atualizar_estado_das_luzes`` sete linhas abaixo. A leitura anterior
        era uma expressão regular sobre o TEXTO do rótulo do cabeçalho
        (``re.search(r"Controle\\s+(\\d+)", _edit_target_label)``), e esse
        rótulo é ``translatable="yes"``: em inglês ele vira "Controller 2", a
        busca falha, a função devolve ``None`` e a prévia volta a mostrar a
        cor manual — **o defeito exato de 17/07 ressuscitado por um idioma**.
        Uma cura que morre ao traduzir a interface não é cura.

        O ``getattr`` defensivo FICA: os mixins só convivem de fato na
        instância composta, e sem slot conhecido a resposta continua sendo
        ``None`` (mostrar a cor manual), exatamente como antes.
        """
        draft = getattr(self, "draft", None)
        if draft is None or not draft.leds.auto_player_colors:
            return None
        if self._edit_uniq().uniq is None:
            return None
        slot = getattr(self, "_edit_target_slot", None)
        if isinstance(slot, int) and not isinstance(slot, bool) and slot >= 1:
            return slot
        return None

    def _persist_leds_update(self, update: dict[str, Any]) -> bool:
        """Grava campos de LEDs no draft — no GLOBAL ou no override do alvo.

        PERFIL-04 (sprint perfis-por-controle): com um controle selecionado
        no seletor do banner, a edição cai em ``draft.controllers[uniq].leds``
        — semeada com o que está NA TELA (o efetivo do alvo), então mudar só
        a cor preserva brilho/player-LEDs exibidos. É o que faz o "Salvar
        Perfil" do rodapé persistir o ajuste DENTRO do perfil, por controle
        ("configurei pro 1-BT, fica salvo pra ele dentro do meu perfil").

        Em "Todos", seção global do draft — E o campo editado sai dos
        overrides por-controle (fix HIGH do review 2026-07-16), espelhando a
        regra que o backend aplica ao vivo: sem a limpeza, "mudei todos para
        azul" + "Salvar Perfil" ressuscitava a cor antiga do alvo na próxima
        ativação. Cor e brilho saem JUNTOS (formam um único campo — o RGB
        pré-escalado — no estado desejado do backend).

        COR-04 (semântica D4): COR (``lightbar_rgb``) editada em "Todos" com
        o automático ligado também DESLIGA ``auto_player_colors`` no draft —
        senão a cor única seria invisível (a paleta automática vence o global
        no merge). Brilho NÃO dispara o D4 (o brilho escala a própria paleta
        — D11). ONDA-U (U9): ``player_leds`` (clique manual de player-LED)
        AGORA também dispara o D4 — antes só ``lightbar_rgb`` disparava, e a
        paleta automática (COR-03) reescrevia o player-LED por cima no
        próximo merge do backend, fazendo o clique manual parecer que "não
        funciona". Devolve True quando o D4 desligou o automático AGORA (o
        chamador compõe o aviso ``_AVISO_D4`` no toast — visível, nunca
        popup); o checkbox da aba é sincronizado aqui mesmo, sob guard.

        R-14 (auditoria 23/07) — o D4 vira EXCEÇÃO, não regra. Desligar
        ``auto_player_colors`` é o martelo mais pesado que a aba tem: além da
        paleta, o flag governava a numeração dos DualSense E a dos externos
        (Pro Nintendo/8BitDo paravam de receber número), e o valor ainda ia
        para o JSON do perfil — um clique de cor em "Todos" apagava a
        identidade automática de todo mundo, para sempre. Com os controles
        CONECTADOS conhecidos, o mesmo desejo ("esta cor/este padrão em todo
        mundo") é expresso como OVERRIDE POR-MAC em cada um deles: override
        vence a camada automática no merge por campo do backend (D5), então a
        cor única aparece **sem** desligar nada e a numeração continua viva.
        A ordem importa: os overrides são escritos ANTES de o global mudar,
        porque ``with_controller_leds`` só guarda o que DIVERGE do global — se
        o global já tivesse o valor novo, o override seria podado e a paleta
        automática voltaria a vencer (a cor "não pegaria").

        ABAS-02 (25/07) — a limpeza é do campo EDITADO, e só dele. Cor e brilho
        saíam JUNTOS dos overrides (formam um único campo no estado desejado do
        backend: o RGB pré-escalado), mas o brilho não tem alvo para re-semear
        (ele não disputa com o automático, então ``alvos`` fica vazio neste
        ramo). Efeito medido: com o alvo em "Todos", arrastar o controle de
        brilho UM PIXEL apagava o campo de cor de TODOS os ajustes por controle
        — Controle 1 azul e Controle 2 vermelho viravam nada — e o evento
        dispara a cada movimento do arraste, então bastava encostar. Limpando
        só o campo editado, o brilho global passa a valer em todo mundo (que é
        o que "Todos" quer dizer) e a cor própria de cada controle sobrevive: a
        emissão por campo de ``_controllers_to_ipc`` resolve o brilho do GLOBAL
        quando o override fala só de cor, e o merge por campo do backend faz o
        mesmo na ativação. A recíproca também melhora — editar a COR em "Todos"
        deixa de apagar o brilho próprio de quem tem um.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return False
        estado_alvo = self._edit_uniq()
        if estado_alvo.desconhecido:
            # Z2-1: a janela não sabe o alvo — zero escrita no rascunho.
            # Nunca cai no ramo "Todos" (que apagaria os overrides por
            # controle do perfil inteiro, o defeito que o P3 mediu).
            return False
        uniq = estado_alvo.uniq
        if uniq is None:
            campos: set[str] = set()
            if "lightbar_rgb" in update:
                campos.add("lightbar")
            if "lightbar_brightness" in update:
                campos.add("lightbar_brightness")
            if "player_leds" in update:
                campos.add("player_leds")
            # Campos "de opinião" (cor e padrão de player-LED) são os que
            # disputam com a camada automática; brilho apenas ESCALA a paleta
            # (D11) e nunca disputou.
            disputa_com_o_auto = "lightbar_rgb" in update or "player_leds" in update
            alvos = self._uniqs_conectados() if disputa_com_o_auto else []
            campos_update = dict(update)
            d4_disparou = bool(
                disputa_com_o_auto and draft.leds.auto_player_colors and not alvos
            )
            if d4_disparou:
                # Escopo desconhecido (a GUI não sabe quem está conectado): sem
                # alvo para o override, o único jeito de a cor única aparecer
                # continua sendo desligar a paleta. Caminho degradado, honesto
                # e avisado — nunca o caminho normal.
                campos_update["auto_player_colors"] = False
            if campos:
                # Tira o valor VELHO de todos os overrides (inclusive dos
                # desconectados, que ressuscitariam na próxima ativação).
                draft = draft.with_override_fields_cleared("leds", campos)
            for alvo in alvos:
                base = draft.effective_leds_for(alvo)
                draft = draft.with_controller_leds(
                    alvo, base.model_copy(update=update)
                )
            new_leds = draft.leds.model_copy(update=campos_update)
            draft = draft.model_copy(update={"leds": new_leds})
            self.draft = draft
            if d4_disparou:
                self._sync_auto_checkbox(False)
            return d4_disparou
        base = draft.effective_leds_for(uniq)
        self.draft = draft.with_controller_leds(uniq, base.model_copy(update=update))
        return False

    def _refresh_lightbar_from_draft(self) -> None:
        """Popula widgets da aba Lightbar a partir do draft.

        PERFIL-04: exibe os LEDs EFETIVOS do alvo de edição atual — o
        override por-controle quando existe (brilho incluso, lido do PERFIL,
        não do backend), senão a seção global. Protegido por _refresh_guard
        para não disparar handlers de signal durante a atualização
        programatica dos widgets.
        """
        if self._refresh_guard:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        self._refresh_guard = True
        try:
            leds = draft.effective_leds_for(self._edit_uniq().uniq)
            # COR-04: o checkbox "Cores automáticas por controle" reflete o
            # GLOBAL do draft (campo do PERFIL), nunca o efetivo do alvo — um
            # override por-controle não tem opinião sobre o toggle.
            auto_check: Gtk.CheckButton = self._get("auto_player_colors_check")
            if auto_check is not None:
                auto_check.set_active(bool(draft.leds.auto_player_colors))
            # Cor RGB
            if leds.lightbar_rgb is not None:
                r, g, b = leds.lightbar_rgb
                self._current_rgb = (r, g, b)
                button: Gtk.ColorButton = self._get("lightbar_color_button")
                if button is not None:
                    rgba = Gdk.RGBA()
                    rgba.red = r / 255.0
                    rgba.green = g / 255.0
                    rgba.blue = b / 255.0
                    rgba.alpha = 1.0
                    button.set_rgba(rgba)
            # Prévia HONESTA (achado ao vivo): com automático ligado + um
            # controle específico em edição, mostra a cor REAL da paleta desse
            # controle (o brilho é aplicado no draw, como no caminho manual) —
            # antes a prévia ficava roxa enquanto o controle estava azul.
            auto_slot = self._auto_preview_slot()
            if auto_slot is not None:
                from hefesto_dualsense4unix.core.led_control import player_slot_color

                self._current_rgb = player_slot_color(auto_slot)
                auto_btn: Gtk.ColorButton = self._get("lightbar_color_button")
                if auto_btn is not None:
                    ar, ag, ab = self._current_rgb
                    auto_rgba = Gdk.RGBA()
                    auto_rgba.red = ar / 255.0
                    auto_rgba.green = ag / 255.0
                    auto_rgba.blue = ab / 255.0
                    auto_rgba.alpha = 1.0
                    auto_btn.set_rgba(auto_rgba)
            # Brightness
            pct = float(leds.lightbar_brightness)
            self._current_brightness = pct / 100.0
            self._pending_brightness = self._current_brightness
            scale: Gtk.Scale = self._get("lightbar_brightness_scale")
            if scale is not None:
                scale.set_value(pct)
            # Player LEDs
            for i, state in enumerate(leds.player_leds, start=1):
                checkbox: Gtk.CheckButton = self._get(f"player_led_{i}")
                if checkbox is not None:
                    checkbox.set_active(bool(state))
            # PLAYER-01 entrega 5: leitura de volta do que está ACESO. Os
            # checkboxes acima seguem sendo o RASCUNHO (e não podem virar o
            # resolvido: "Aplicar o desenho" os lê, e congelar a numeração
            # automática num override por-MAC seria o defeito que o R-14
            # desfez). O estado resolvido vive neste rótulo.
            self._atualizar_estado_das_luzes(leds.player_leds)
            # L6: o que o DAEMON sabe da barra deste controle chega à aba da
            # cor. Fica DENTRO do guard, e depois de tudo, porque é a única
            # linha desta função que sai da janela para buscar dado.
            self._atualizar_estado_da_barra()
            # Repinta preview
            preview: Gtk.DrawingArea = self._get("lightbar_preview")
            if preview is not None:
                preview.queue_draw()
        finally:
            self._refresh_guard = False

    def _atualizar_estado_da_barra(self) -> None:
        """Escreve no rótulo ``lightbar_estado_no_controle`` o que o daemon sabe.

        **L6 (25/08/2026) — a aba da barra era a ÚNICA do produto que não lia
        nada do que o produto já sabe sobre a barra.** Medido:

        ``grep -rln "lightbar_source\\|lightbar_disputada\\|lightbar_on"
        src/hefesto_dualsense4unix/app/`` devolvia **um** arquivo, e era
        ``widgets/controller_card.py`` — o card, que mora na Status, na Início
        e na "No jogo". Consequência direta: quem está na aba da COR era
        justamente quem não era avisado de que a Steam segura o ``hidraw``
        deste controle (``lightbar_disputada``, ESCRITOR-CRU-01) nem de que o
        valor exibido é o que o Hefesto PEDIU, não o que a lâmpada faz
        (``lightbar_source``).

        **A interpretação é REUSADA, não reescrita.** A frase sai de
        ``widgets/controller_card.rotulo_lightbar``, a mesma que os cards já
        usam, com a mesma ordem de precedência (Modo Nativo → disputa →
        fonte desconhecida → apagada). Escrever uma segunda leitura destes
        campos aqui seria o defeito F5 nascendo dentro da própria cura: duas
        semânticas para ``lightbar_source`` no mesmo produto.

        **Quando o rótulo SOME**, e é regra, não descuido: sem alvo por
        controle ("Todos" ou alvo desconhecido), sem daemon, com o controle
        fora do bloco ``controllers``, ou quando ``rotulo_lightbar`` não tem
        aviso a dar (cor conhecida e acesa) — aí a prévia ao lado já diz tudo,
        e um aviso sem conteúdo é ruído. Um "não sei" **não** vira aviso: é a
        mesma disciplina que a `secao_controles` já aplica.
        """
        rotulo = self._get("lightbar_estado_no_controle")
        if rotulo is None:
            return
        texto = self._texto_do_estado_da_barra()
        rotulo.set_text(texto or "")
        if texto:
            rotulo.show()
        else:
            rotulo.hide()

    def _texto_do_estado_da_barra(self) -> str | None:
        """O aviso da barra para o controle EM EDIÇÃO; ``None`` = nenhum (L6).

        Uma leitura por repintura da aba, nunca por tique: quem chama é
        ``_refresh_lightbar_from_draft``, que roda ao ENTRAR na aba
        (``app._REFRESH_POR_ABA``), ao trocar de alvo, ao trocar de perfil e
        na transição do co-op. A chamada síncrona ao ``daemon.state_full``
        segue o precedente de
        ``daemon_actions._refresh_window_detect_diag``: leitura read-only do
        ``state_full``, feita de dentro do refresh da aba, com o corpo inteiro
        num ``try`` — porque linha informativa não derruba aba
        (DIAGNÓSTICO-NAO-DERRUBA-A-ABA-01). O precedente que esta linha citava
        antes foi apagado pela T-12 em 25/08/2026, por ser código sem chamador;
        o nome dele não se repete aqui de propósito — há portão que reprova
        símbolo morto ressuscitado em prosa.
        """
        from hefesto_dualsense4unix.app.mesa import controles_conectados
        from hefesto_dualsense4unix.app.widgets.controller_card import (
            rotulo_lightbar,
        )

        uniq = self._edit_uniq().uniq
        if uniq is None:
            return None
        try:
            state = ipc_bridge.daemon_state_full()
        except Exception:
            return None
        if not isinstance(state, dict):
            return None
        for entrada in controles_conectados(state):
            if entrada.get("uniq") == uniq:
                texto, _cor = rotulo_lightbar(entrada, state)
                return texto
        return None

    def _atualizar_estado_das_luzes(
        self, player_leds: tuple[bool, ...] | list[bool]
    ) -> None:
        """Escreve no rótulo ``player_leds_estado`` o desenho ACESO (PLAYER-01).

        O número do alvo (``_edit_target_slot``) e o estado do co-op
        (``_coop_ligado``) são mantidos pela aba Status a partir do
        ``state_full`` — ``getattr`` defensivo porque os mixins só convivem de
        fato na instância composta, nunca isolados nos testes. Sem os dois, a
        frase degrada para "o automático manda", que continua sendo verdade.
        """
        rotulo = self._get("player_leds_estado")
        if rotulo is None:
            return
        rotulo.set_text(
            texto_do_desenho_aceso(
                player_leds,
                getattr(self, "_edit_target_slot", None),
                coop_ligado=bool(getattr(self, "_coop_ligado", False)),
                descricao_livre=self._descreve_player_leds(list(player_leds)),
            )
        )

    def install_lightbar_tab(self) -> None:
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.connect("draw", self._on_lightbar_preview_draw)
        # Seta cor inicial programaticamente (Glade não suporta inline
        # RGBA com syntax "rgb(...)" sem segfault em todas as versões).
        button: Gtk.ColorButton = self._get("lightbar_color_button")
        if button is not None:
            rgba = Gdk.RGBA()
            rgba.red = 1.0
            rgba.green = 128 / 255
            rgba.blue = 0.0
            rgba.alpha = 1.0
            button.set_rgba(rgba)
            self._current_rgb = (255, 128, 0)
        # COR-04: widgets do automático conectados em CÓDIGO (não pelo Glade)
        # — o dict de ``_signal_handlers()`` vive em app.py, e a fiação aqui
        # segue o precedente do install_triggers_tab (SegmentedSelector).
        auto_check: Gtk.CheckButton = self._get("auto_player_colors_check")
        if auto_check is not None:
            auto_check.connect("toggled", self.on_auto_player_colors_toggled)
        reset_target: Gtk.Button = self._get("lightbar_auto_reset_target")
        if reset_target is not None:
            reset_target.connect("clicked", self.on_lightbar_auto_reset_target)
        reset_all: Gtk.Button = self._get("lightbar_auto_reset_all")
        if reset_all is not None:
            reset_all.connect("clicked", self.on_lightbar_auto_reset_all)
        self._fiar_aplicar_ao_soltar()

    def _fiar_aplicar_ao_soltar(self) -> None:
        """Liga o "acende ao SOLTAR" da cor e do brilho (BOTÃO-QUE-NÃO-MENTE-01).

        O defeito medido: escolher uma cor não acendia nada. O handler do
        seletor gravava só no rascunho e o hardware só via a cor no SEGUNDO
        clique, num botão trinta linhas de layout abaixo ("Aplicar no
        controle"). Ela clicava, o controle não mudava, e concluía que a janela
        era maquete. Estava funcionando — e não estava contando.

        Adiar a escrita continua CERTO: aplicar a cada pixel de arraste do
        controle deslizante saturaria a fila do rádio (por Bluetooth cada
        escrita disputa a mesma fila dos relatórios de input, e são quatro
        controles). O defeito nunca foi o adiamento: era o adiamento
        SILENCIOSO. A cura mantém o adiamento e encurta a janela dele para um
        gesto: escreve ao **soltar**, uma vez.

        Os dois gestos, e por que cada sinal:

        * **cor** — ``color-set`` do ``GtkColorButton`` já É o soltar: só
          dispara quando ela confirma a cor no diálogo, nunca durante a
          escolha. Um gesto, uma escrita;
        * **brilho** — ``value-changed`` do ``GtkScale`` dispara a CADA pixel
          do arraste, então ele continua sem tocar no hardware (só rascunho e
          prévia) e quem escreve é ``button-release-event``. O
          ``key-release-event`` cobre quem move o controle pelas setas do
          teclado, que nunca solta botão de mouse nenhum.

        A fiação é em CÓDIGO e não no glade de propósito: o dict de sinais do
        ``app.py`` já leva ``color-set`` e ``value-changed`` aos handlers de
        rascunho, e o Builder conecta ANTES desta instalação — a ordem garante
        que o rascunho já esteja atualizado quando a escrita sai. É o mesmo
        precedente do checkbox de cores automáticas acima.
        """
        if self._soltar_fiado:
            return
        botao_cor: Gtk.ColorButton = self._get("lightbar_color_button")
        if botao_cor is not None:
            botao_cor.connect("color-set", self._on_lightbar_cor_solta)
        escala: Gtk.Scale = self._get("lightbar_brightness_scale")
        if escala is not None:
            escala.connect("button-release-event", self._on_lightbar_brilho_solto)
            escala.connect("key-release-event", self._on_lightbar_brilho_solto)
        self._soltar_fiado = True

    def _on_lightbar_cor_solta(self, _botao: Any = None) -> None:
        """Cor confirmada no diálogo -> acende no controle AGORA (entrega 1).

        Roda depois do ``on_lightbar_color_set`` do Builder (ordem de conexão),
        então ``_current_rgb`` e o rascunho já estão atualizados. Reusa o mesmo
        caminho de escrita do botão "Aplicar no controle" — nada de rota
        paralela, para a cor não passar a viajar por dois códigos diferentes
        conforme quem a mandou.
        """
        if self._refresh_guard:
            return
        # O brilho da tela vai junto na mesma escrita (cor e brilho são um
        # único campo no estado desejado do backend), então não fica pendente.
        self._brilho_pendente = False
        self._aplicar_cor_no_controle()

    def _on_lightbar_brilho_solto(
        self, _widget: Any = None, _evento: Any = None
    ) -> bool:
        """Soltou o controle deslizante de brilho -> UMA escrita (entrega 1).

        Devolve ``False`` sempre: este handler observa o evento, não o consome.
        Devolver ``True`` num ``button-release-event`` do ``GtkRange`` roubaria
        o fim do arraste do próprio widget (o botão ficaria "preso").

        Sem movimento pendente não há escrita: clicar no controle deslizante
        sem mudar o valor não é um pedido de nada, e a fila do rádio é curta.
        """
        if self._refresh_guard:
            return False
        if not self._brilho_pendente:
            return False
        self._brilho_pendente = False
        self._aplicar_cor_no_controle()
        return False

    # --- signals lightbar ---

    def on_lightbar_color_set(self, button: Gtk.ColorButton) -> None:
        if self._refresh_guard:
            return
        rgba = button.get_rgba()
        self._current_rgb = (
            int(rgba.red * 255),
            int(rgba.green * 255),
            int(rgba.blue * 255),
        )
        # Atualiza draft (global ou override do alvo — PERFIL-04). Em "Todos"
        # com o automático ligado, o D4 desliga o toggle — aviso visível
        # (COR-04; sem outro toast por cima: escolher cor não tem toast).
        if self._persist_leds_update({"lightbar_rgb": self._current_rgb}):
            self._toast_light(_AVISO_D4)
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()

    def on_lightbar_apply(self, _btn: Gtk.Button) -> None:
        """Botão "Aplicar no controle" — reenvia a cor da tela ao hardware.

        Continua existindo depois da entrega 1 do BOTÃO-QUE-NÃO-MENTE-01 (a
        cor já acende ao soltar o seletor): é o reenvio explícito, útil depois
        de reconectar um controle ou trocar de alvo no seletor do banner, e é
        o botão que os textos da tela citam. Um único caminho de escrita para
        os dois gestos — ``_aplicar_cor_no_controle``.
        """
        self._aplicar_cor_no_controle()

    def _aplicar_cor_no_controle(self) -> bool:
        """Envia a cor da tela ao hardware. Devolve True quando todos aceitaram.

        CAMINHO ÚNICO de escrita da cor: o botão "Aplicar no controle" e o
        aplicar-ao-soltar (cor e brilho) entram os dois por aqui. Duplicar a
        rota faria a cor viajar por códigos diferentes conforme o gesto — e as
        regras abaixo (R-14, COR-04, PERFIL-05) valem para os dois.

        R-14 (auditoria 23/07): em "Todos" com os controles CONECTADOS
        conhecidos, a cor vai por MAC para cada um (``led.set`` com ``uniq``)
        — o override por-uniq vence a camada automática no merge por campo do
        backend (D5), então a cor única aparece sem desligar a paleta (e sem
        levar junto a numeração e os externos, que o mesmo flag governava).

        COR-04 (caminho degradado, só quando a GUI ainda não sabe quem está
        conectado): a cor viaja JUNTO com o toggle do automático num único
        ``profile.apply_draft`` parcial (seção ``leds``) — o ``led.set``
        clássico gravaria só o default e a paleta automática venceria no
        próximo reassert ("apliquei e voltou colorido"). Com um controle
        selecionado (ou sem draft — hosts parciais de teste), o fluxo
        por-controle clássico permanece: ``led.set`` respeita o alvo do
        seletor e não mexe no toggle.
        """
        estado_alvo = self._edit_uniq()
        if estado_alvo.desconhecido:
            # Z2-2: a recusa chega à tela em vez de a cor viajar às cegas —
            # zero IPC. A frase já existe pronta em `alvo_de_edicao.py`.
            self._toast_light(estado_alvo.recusa() or _AVISO_HEFESTO_DESLIGADO)
            return False
        pct = round(self._current_brightness * 100)
        draft = getattr(self, "draft", None)
        d4_disparou = False
        # APLICAR-VERDADE-01/E2: a resposta do daemon, quando houve uma. Fica
        # `None` nos caminhos que não passam pelo `apply_draft` (led.set), e é
        # o que separa "o Hefesto está desligado" de "a seção de luzes caiu".
        resposta: Any = None
        # BG-01: o corpo do `led.set`, com `aplicado_em`/`guardado_em`. Fica
        # `None` na rota COR-04 (`profile.apply_draft`), que publica
        # `applied`/`failed` e NÃO publica destino — é ele quem separa as duas.
        corpo: Any = None
        alvos = self._uniqs_conectados() if estado_alvo.uniq is None else []
        if estado_alvo.uniq is None and alvos:
            ok, corpo = self._enviar_led_em_todos(
                self._current_rgb, self._current_brightness, alvos
            )
        elif estado_alvo.uniq is None and draft is not None:
            d4_disparou = self._d4_disable_auto_for_single_color()
            resposta = ipc_bridge.apply_draft_detalhado(
                {
                    "leds": {
                        "lightbar_rgb": list(self._current_rgb),
                        "lightbar_brightness": self._current_brightness,
                        "auto_player_colors": self.draft.leds.auto_player_colors,
                    }
                }
            )
            ok = ipc_bridge.aplicacao_confirmada(resposta)
        else:
            # PERFIL-05 (22/07): com um controle selecionado, o MAC viaja no
            # pedido — o daemon aplica SÓ nele (antes: caminho por índice que
            # caía em broadcast quando desalinhava).
            corpo = led_set_detalhado(
                self._current_rgb,
                brightness=self._current_brightness,
                uniq=estado_alvo.uniq,
            )
            # BG-01: `None` é a MESMA resposta que o `led_set` dava como
            # `False` — daemon sem responder. Ver `ipc_bridge._corpo_do_daemon`.
            ok = corpo is not None
        if not ok:
            msg = mensagem_de_secao_fora(resposta) or _AVISO_HEFESTO_DESLIGADO
        elif corpo is not None:
            # BG-01 (26/08/2026) — A INVERSÃO. Até aqui a frase saía da
            # HEURÍSTICA do estado da janela (`alvo_fora_da_mesa`,
            # `modo_nativo_manda_no_output`), que enxerga duas das razões que o
            # daemon conhece e nenhuma das outras três — e caía na rota que a
            # bancada mediu em 23/08: mesa vazia, alvo em "Todos", corpo
            # dizendo ZERO destino, tela dizendo que a cor foi. Agora o corpo
            # do daemon decide, e as leituras da janela viram a EXPLICAÇÃO
            # (dentro de `frase_do_desfecho`), nunca mais a decisão.
            #
            # `coop_aplica` fica no padrão `False`, e é medido: a camada do
            # co-op tem vocabulário de um campo só
            # (`backend_pydualsense._COOP_LAYER_FIELDS = ("player_leds",)`),
            # então ela não governa a COR.
            msg = frase_do_envio(
                _ASSUNTO_COR.format(pct=pct),
                _TOAST_COR_ENVIADA.format(pct=pct),
                corpo,
                self,
            )
        else:
            # COR-04, a rota degradada: a cor viaja dentro de um
            # `profile.apply_draft` parcial, cujo corpo publica `applied` e
            # `failed` e NÃO publica destino — não há o que ler. Aqui a
            # heurística continua sendo tudo o que existe, e ela SOMA as
            # pendências (conserto 1.5), coisa que o ramo sem corpo de
            # `frase_do_desfecho` não faz. Está relatado como o que sobrou.
            #
            # MESA-CHEIA-09/E3 + D-9: com o alvo FORA da mesa, o daemon
            # registra o override e o hotplug o aplica quando ele voltar —
            # nenhum byte saiu agora. Conserto 1.3: em Modo Nativo a cor também
            # não sai — a rota sysfs está desabilitada sob mute e o `0x31`
            # avulso é pulado.
            msg = frase_de_guardado(
                _ASSUNTO_COR.format(pct=pct),
                alvo_ausente=alvo_fora_da_mesa(self),
                nativo=modo_nativo_manda_no_output(self),
            ) or _TOAST_COR_ENVIADA.format(pct=pct)
        if d4_disparou:
            msg = f"{_AVISO_D4} — {msg}"
        self._toast_light(msg)
        return bool(ok)

    def on_lightbar_brightness_changed(self, scale: Gtk.Scale) -> None:
        """Controle deslizante 0-100 (%) -> luminosidade corrente e prévia.

        NÃO escreve no hardware: este sinal dispara a cada pixel do arraste, e
        uma escrita por pixel saturaria a fila do rádio (por Bluetooth ela
        disputa com os relatórios de input do próprio controle). O que o
        movimento faz é marcar ``_brilho_pendente``; quem escreve, uma vez só,
        é o soltar (``_on_lightbar_brilho_solto`` — BOTÃO-QUE-NÃO-MENTE-01
        entrega 1). O guard ``_refresh_guard`` previne o laço quando
        ``_refresh_lightbar_from_draft`` move o controle programaticamente
        (FEAT-LED-BRIGHTNESS-03) — e é por isso que a marca de pendente fica
        DEPOIS dele: repovoar a aba não é gesto dela, e não pode virar escrita.
        """
        if self._refresh_guard:
            return
        raw = float(scale.get_value())
        # Clamp defensivo: GtkAdjustment ja limita, mas nunca confie cego.
        pct = max(0.0, min(100.0, raw))
        self._current_brightness = pct / 100.0
        self._pending_brightness = self._current_brightness
        # Atualiza draft com novo valor de brightness (global ou override do
        # alvo — PERFIL-04).
        self._persist_leds_update({"lightbar_brightness": round(pct)})
        self._brilho_pendente = True
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()

    def on_lightbar_off(self, _btn: Gtk.Button) -> None:
        estado_alvo = self._edit_uniq()
        if estado_alvo.desconhecido:
            # Z2-2: mesma recusa do "Aplicar" — zero IPC, zero rascunho.
            self._toast_light(estado_alvo.recusa() or _AVISO_HEFESTO_DESLIGADO)
            return
        self._current_rgb = (0, 0, 0)
        rgba = Gdk.RGBA()
        rgba.red = 0.0
        rgba.green = 0.0
        rgba.blue = 0.0
        rgba.alpha = 1.0
        button: Gtk.ColorButton = self._get("lightbar_color_button")
        if button is not None:
            button.set_rgba(rgba)
        # B2: espelha a cor preta no draft (mesmo mecanismo de
        # on_lightbar_color_set). Sem isso, "Apagar" + "Salvar Perfil" gravava a
        # cor antiga e revisitar a aba repintava a cor anterior.
        # COR-04 (D4): apagar é aplicar a cor única preta — em "Todos" com o
        # automático ligado, o toggle desliga (senão a paleta reacenderia por
        # cima no próximo reassert) e o preto viaja com o toggle num único
        # apply_draft parcial, como no on_lightbar_apply.
        d4_disparou = self._persist_leds_update({"lightbar_rgb": self._current_rgb})
        preview: Gtk.DrawingArea = self._get("lightbar_preview")
        if preview is not None:
            preview.queue_draw()
        draft = getattr(self, "draft", None)
        # APLICAR-VERDADE-01/E2: ver o comentário homônimo em
        # `_aplicar_cor_no_controle` — "Apagar" é aplicar a cor preta e mente
        # pelo mesmo motivo.
        resposta: Any = None
        # BG-01: idem `_aplicar_cor_no_controle` — o corpo do `led.set`.
        corpo: Any = None
        alvos = self._uniqs_conectados() if estado_alvo.uniq is None else []
        if estado_alvo.uniq is None and alvos:
            # R-14: apagar é aplicar a cor única preta — mesma rota por-MAC do
            # "Aplicar", sem desligar a paleta automática de ninguém.
            ok, corpo = self._enviar_led_em_todos((0, 0, 0), None, alvos)
        elif estado_alvo.uniq is None and draft is not None:
            resposta = ipc_bridge.apply_draft_detalhado(
                {
                    "leds": {
                        "lightbar_rgb": [0, 0, 0],
                        "auto_player_colors": draft.leds.auto_player_colors,
                    }
                }
            )
            ok = ipc_bridge.aplicacao_confirmada(resposta)
        else:
            # R-17 (auditoria 23/07): o "Apagar" era o ÚNICO output da GUI que
            # não mandava o `uniq` do alvo — o "Aplicar" logo ao lado manda. Sem
            # ele o pedido cai na rota GLOBAL (broadcast) que o PERFIL-05
            # abandonou: apagava a lightbar dos QUATRO controles quando ela
            # pediu para apagar a de UM, e ainda derrubava o override por-MAC
            # dos outros.
            corpo = led_set_detalhado((0, 0, 0), uniq=estado_alvo.uniq)
            ok = corpo is not None
        if not ok:
            # E2: o "Falha (daemon offline?)" continua palavra por palavra para
            # o daemon REALMENTE offline; com ele vivo, quem fala é a seção.
            msg = mensagem_de_secao_fora(resposta) or "Falha (daemon offline?)"
        elif corpo is not None:
            # BG-01: o quinto gesto de saída da aba passa a decidir pelo corpo
            # do daemon, como os outros. `coop_aplica` fica de fora pelo mesmo
            # motivo medido do "Aplicar": a camada do co-op só governa
            # `player_leds`, nunca a cor.
            msg = frase_do_envio(
                _ASSUNTO_APAGAR, _TOAST_LIGHTBAR_APAGADA, corpo, self
            )
        else:
            # COR-04: ver o comentário homônimo em `_aplicar_cor_no_controle`.
            # Conserto 1.5: o quinto gesto entra no mesmo vocabulário dos
            # outros quatro (ver `_ASSUNTO_APAGAR`).
            msg = frase_de_guardado(
                _ASSUNTO_APAGAR,
                alvo_ausente=alvo_fora_da_mesa(self),
                nativo=modo_nativo_manda_no_output(self),
            ) or _TOAST_LIGHTBAR_APAGADA
        if d4_disparou:
            msg = f"{_AVISO_D4} — {msg}"
        self._toast_light(msg)

    # --- signals cores automáticas por controle (COR-04) ---

    def on_auto_player_colors_toggled(self, checkbox: Gtk.CheckButton) -> None:
        """Checkbox "Cores automáticas por controle" → ``draft.leds``.

        Campo do PERFIL: grava SEMPRE na seção GLOBAL do draft, mesmo com um
        controle selecionado no seletor (um override por-controle não tem
        opinião sobre o toggle — regra do schema). Persiste no "Salvar
        Perfil" (``to_profile``) e viaja no "Aplicar" (``to_ipc_dict``).
        RELIGAR o automático NÃO apaga cores explícitas por-controle: elas
        continuam vencendo onde existirem (merge do backend, D5) — quem as
        remove são os botões "Voltar ao automático".
        """
        if self._refresh_guard:
            return
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        ativo = bool(checkbox.get_active())
        if bool(draft.leds.auto_player_colors) == ativo:
            return  # sem mudança real (eco de set_active programático)
        self.draft = draft.model_copy(
            update={
                "leds": draft.leds.model_copy(update={"auto_player_colors": ativo})
            }
        )
        if ativo:
            self._toast_light(
                "Cores automáticas ligadas — cores escolhidas por controle "
                "continuam valendo onde existirem"
            )
        else:
            self._toast_light(
                "Cores automáticas desligadas — vale a cor única do perfil"
            )

    def on_lightbar_auto_reset_target(self, _btn: Gtk.Button) -> None:
        """"Voltar ao automático" — remove a cor explícita do ALVO selecionado.

        Só a cor (``lightbar`` + ``lightbar_brightness``, que formam UM campo
        no backend) sai do override do controle; player-LEDs e gatilhos
        próprios ficam. A automática volta a valer nele no próximo Aplicar
        (ou na próxima ativação do perfil salvo). Com o alvo em "Todos" não
        há controle selecionado: orienta pelo toast, sem popup.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        uniq = self._edit_uniq().uniq
        if uniq is None:
            self._toast_light(
                'Sem um controle escolhido, use o botão '
                '"Voltar todos ao automático".'
            )
            return
        self.draft = draft.with_controller_fields_cleared(
            uniq, "leds", {"lightbar", "lightbar_brightness"}
        )
        self._refresh_lightbar_from_draft()
        if self.draft.leds.auto_player_colors:
            self._toast_light(
                "Cor própria removida — a cor automática volta a valer "
                "neste controle no próximo Aplicar"
            )
        else:
            self._toast_light(
                'Cor própria removida — ligue "Cores automáticas por '
                'controle" para valer a paleta'
            )

    def on_lightbar_auto_reset_all(self, _btn: Gtk.Button) -> None:
        """"Voltar todos ao automático" — limpa as cores explícitas e religa o auto.

        Remove ``lightbar``/``lightbar_brightness`` de TODOS os overrides
        por-controle do draft (player-LEDs e gatilhos explícitos ficam) e
        religa ``auto_player_colors`` — a paleta automática volta a valer em
        todo mundo no próximo Aplicar/Salvar.
        """
        draft = getattr(self, "draft", None)
        if draft is None:
            return
        novo = draft.with_override_fields_cleared(
            "leds", {"lightbar", "lightbar_brightness"}
        )
        novo = novo.model_copy(
            update={"leds": novo.leds.model_copy(update={"auto_player_colors": True})}
        )
        self.draft = novo
        self._refresh_lightbar_from_draft()
        self._toast_light(
            "Cores automáticas religadas para todos os controles — aplique "
            "ou salve o perfil para valer"
        )

    def _enviar_led_em_todos(
        self,
        rgb: tuple[int, int, int],
        brightness: float | None,
        alvos: list[str],
    ) -> tuple[bool, dict[str, Any] | None]:
        """``led.set`` por MAC em cada controle conectado (R-14).

        "Todos" deixa de ser um broadcast sem dono: cada controle recebe o
        pedido com o próprio ``uniq``, e o daemon grava override por-uniq
        (``_record_desired_locked`` com alvo) em vez de escrever o default
        global e limpar os overrides. É o que faz a cor única vencer a paleta
        automática SEM desligar o automático — e é a mesma disciplina do
        R-17 ("todo output da GUI leva ``uniq``").

        Sucesso só quando TODOS aceitaram: um controle que ficou de fora é
        falha visível, não silêncio. Sem curto-circuito — o `and` preguiçoso
        pularia os controles seguintes na primeira falha.

        BG-01 (26/08/2026): devolve ``(ok, corpo)``. O ``ok`` é o de sempre —
        ``None`` do daemon é o ``False`` de ontem —, e o ``corpo`` é a SOMA das
        N respostas (:func:`somar_os_corpos`), para a frase sair do que o
        daemon disse e não do que a janela deduziu.
        """
        corpos = [
            led_set_detalhado(rgb, brightness=brightness, uniq=alvo)
            for alvo in alvos
        ]
        return all(corpo is not None for corpo in corpos), somar_os_corpos(corpos)

    def _enviar_player_leds(
        self, bits: tuple[bool, bool, bool, bool, bool]
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Envia o desenho das 5 luzes ao alvo certo (R-14/R-17/PLAYER-01).

        Devolve ``(ok, motivo, corpo)``: ``motivo`` preenchido é uma recusa
        NOSSA, com explicação própria — o chamador a mostra em vez da frase
        genérica "o Hefesto pode estar desligado", que mandaria a usuária caçar
        o problema no lugar errado. ``corpo`` é a resposta do daemon (BG-01,
        26/08/2026), somada quando o pedido foi por MAC em vários controles —
        é dela que sai a frase, e não mais da heurística da janela.

        Alvo selecionado → só ele. "Todos" com os conectados conhecidos → um
        pedido POR MAC (override por-uniq vence a numeração automática no
        merge do backend; era o que o desligar-o-flag do U9 tentava obter
        pelo caminho destrutivo).

        PLAYER-01 entrega 6 — "Todos" SEM saber quem está conectado deixou de
        cair na rota global. O pedido sem ``uniq`` era gravado pelo daemon no
        default GLOBAL, que fica ABAIXO da camada automática no merge por
        campo (D5): o próximo reforço do automático o desfazia, e a escolha
        dela "voltava sozinha". Era um sucesso mentiroso — o IPC respondia
        ``ok``, o toast dizia que aplicou, e meio segundo depois o controle
        voltava ao desenho anterior. Recusar com motivo é a única resposta
        honesta; o mapa de conectados chega no próximo tique do daemon e o
        clique seguinte funciona.
        """
        estado_alvo = self._edit_uniq()
        if estado_alvo.desconhecido:
            # Z2-2: mesma família da recusa acima — motivo próprio, sem IPC.
            return False, estado_alvo.recusa(), None
        if estado_alvo.uniq is not None:
            corpo = player_leds_set_detalhado(bits, uniq=estado_alvo.uniq)
            return corpo is not None, None, corpo
        alvos = self._uniqs_conectados()
        if not alvos:
            return False, _AVISO_SEM_DESTINATARIO, None
        corpos = [player_leds_set_detalhado(bits, uniq=alvo) for alvo in alvos]
        return (
            all(corpo is not None for corpo in corpos),
            None,
            somar_os_corpos(corpos),
        )

    def _d4_disable_auto_for_single_color(self) -> bool:
        """D4 fora do ``_persist_leds_update``: desliga o auto no draft.

        Usado pelos caminhos que APLICAM a cor da tela sem editá-la
        (``on_lightbar_apply``): religou o automático e clicou "Aplicar no
        controle" em "Todos" → o toggle desliga aqui, e o chamador compõe o
        ``_AVISO_D4`` no toast do resultado. Devolve True quando desligou
        AGORA; False se já estava desligado (ou sem draft).
        """
        draft = getattr(self, "draft", None)
        if draft is None or not draft.leds.auto_player_colors:
            return False
        self.draft = draft.model_copy(
            update={"leds": draft.leds.model_copy(update={"auto_player_colors": False})}
        )
        self._sync_auto_checkbox(False)
        return True

    def _sync_auto_checkbox(self, active: bool) -> None:
        """Reflete ``active`` no checkbox SEM disparar o handler (guard)."""
        check: Gtk.CheckButton = self._get("auto_player_colors_check")
        if check is None:
            return
        prev = self._refresh_guard
        self._refresh_guard = True
        try:
            check.set_active(active)
        finally:
            self._refresh_guard = prev

    # --- signals player leds ---

    def aplicar_desenho_do_jogador(self, numero: int) -> None:
        """Aplica o desenho CANÔNICO do jogador ``numero`` (L9, 25/08/2026).

        **A fiação que faltava.** Os quatro botões "Desenho do P1..P4" traziam
        o padrão escrito à mão — ``[False, True, False, True, False]`` e os
        outros três — enquanto ``core/led_control.player_led_pattern`` já é a
        tabela canônica que o DAEMON usa para acender, cobre **1..8** (R-25,
        porque o espaço de numeração é único entre DualSense, externos e co-op
        — R-24) e ainda tem padrão de overflow para ≥9. Literal e tabela eram
        duas cópias independentes que nada amarrava: mudar a tabela deixava os
        botões pintando o desenho antigo, sem um único teste vermelho. O mesmo
        arquivo já lia a tabela em ``nome_do_desenho`` para BATIZAR o desenho —
        então a aba nomeava por uma fonte e pintava por outra.

        Ela também é o que torna baratas as duas respostas possíveis da
        pergunta que é DELA (§8 da sprint): quantos botões de desenho aparecem
        — sempre oito, ou só até o maior número vivo na mesa. Esta entrega é a
        fiação; **quantos botões existem na tela continua sendo escolha dela**,
        e por isso o glade segue com os mesmos quatro.
        """
        from hefesto_dualsense4unix.core.led_control import player_led_pattern

        self._set_player_leds(list(player_led_pattern(numero)))

    def on_player_leds_preset_all(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([True] * 5)

    def on_player_leds_preset_p1(self, _btn: Gtk.Button) -> None:
        self.aplicar_desenho_do_jogador(1)

    def on_player_leds_preset_p2(self, _btn: Gtk.Button) -> None:
        self.aplicar_desenho_do_jogador(2)

    def on_player_leds_preset_p3(self, _btn: Gtk.Button) -> None:
        # FEAT-COOP-PLAYER-LED-01: padrões canônicos P3/P4 (os mesmos que o
        # co-op local aplica por controle) também disponíveis como preset.
        self.aplicar_desenho_do_jogador(3)

    def on_player_leds_preset_p4(self, _btn: Gtk.Button) -> None:
        self.aplicar_desenho_do_jogador(4)

    def on_player_leds_preset_none(self, _btn: Gtk.Button) -> None:
        self._set_player_leds([False] * 5)

    def on_player_leds_apply(self, _btn: Gtk.Button) -> None:
        """Reenvia o padrão atual dos 5 checkboxes ao hardware
        (BUG-PLAYER-LEDS-APPLY-01).

        Botão explícito para o fluxo pedido pelo usuário: marcar o padrão,
        clicar em "Aplicar LEDs" e ver o controle refletir. Também útil para
        reemitir o bitmask após reconectar o controle ou trocar de perfil
        (quando o autoswitch já foi aplicado mas o usuário quer confirmar).
        """
        if self._refresh_guard:
            return
        bits = self.get_current_player_leds()
        # Atualiza draft — mantém consistência com on_player_led_toggled.
        # ONDA-U (U9): player-LEDs em "Todos" com o automático ligado também
        # dispara o D4 (mesma composição de toast do on_lightbar_apply).
        d4_disparou = self._persist_leds_update({"player_leds": bits})
        ok, motivo, corpo = self._enviar_player_leds(bits)
        descricao = self._descreve_player_leds(bits)
        msg = self._msg_do_desenho(
            ok=ok,
            motivo=motivo,
            corpo=corpo,
            descricao=descricao,
            feito="aplicado",
            fazer="aplicar",
        )
        if d4_disparou:
            msg = f"{_AVISO_D4} — {msg}"
        self._toast_light(msg)
        # L4: o MESMO tratamento dos presets — o rótulo acompanha o reenvio
        # quando ele deu certo, e fica onde está quando o produto recusou.
        if ok:
            self._atualizar_estado_das_luzes(bits)

    def on_player_led_toggled(self, _checkbox: Gtk.CheckButton) -> None:
        """Sinal de toggle de qualquer checkbox de player LED.

        Recalcula o bitmask completo dos 5 checkboxes e envia ao hardware via IPC.
        Pula silenciosamente quando `_player_leds_batch_guard` esta ativo (preset
        em andamento faz o envio final ele mesmo, evitando 5 IPCs redundantes).
        """
        if self._refresh_guard:
            return
        if getattr(self, "_player_leds_batch_guard", False):
            return
        bits = self.get_current_player_leds()
        # Atualiza draft (global ou override do alvo — PERFIL-04)
        # ONDA-U (U9): idem — player-LEDs em "Todos" com auto ligado dispara D4.
        d4_disparou = self._persist_leds_update({"player_leds": bits})
        ok, motivo, corpo = self._enviar_player_leds(bits)
        descricao = self._descreve_player_leds(bits)
        msg = self._msg_do_desenho(
            ok=ok,
            motivo=motivo,
            corpo=corpo,
            descricao=descricao,
            feito="atualizado",
            fazer="atualizar",
        )
        if d4_disparou:
            msg = f"{_AVISO_D4} — {msg}"
        self._toast_light(msg)

    # --- helpers ---

    def _set_player_leds(self, pattern: list[bool]) -> None:
        """Atualiza checkboxes e envia bitmask ao hardware via IPC (1 chamada).

        Aplica `_player_leds_batch_guard` enquanto atualiza os 5 checkboxes para
        evitar que `on_player_led_toggled` dispare IPCs redundantes -- so envia
        o bitmask final ao fim, em uma chamada única.
        """
        self._player_leds_batch_guard = True
        try:
            for i, state in enumerate(pattern, start=1):
                checkbox: Gtk.CheckButton = self._get(f"player_led_{i}")
                if checkbox is not None:
                    checkbox.set_active(state)
        finally:
            self._player_leds_batch_guard = False
        bits: tuple[bool, bool, bool, bool, bool] = (
            pattern[0], pattern[1], pattern[2], pattern[3], pattern[4]
        )
        # Atualiza draft (global ou override do alvo — PERFIL-04)
        # ONDA-U (U9): presets também disparam o D4 em "Todos" com auto ligado.
        d4_disparou = self._persist_leds_update({"player_leds": bits})
        ok, motivo, corpo = self._enviar_player_leds(bits)
        descricao = self._descreve_player_leds(pattern)
        msg = self._msg_do_desenho(
            ok=ok,
            motivo=motivo,
            corpo=corpo,
            descricao=descricao,
            feito="atualizado",
            fazer="atualizar",
        )
        if d4_disparou:
            msg = f"{_AVISO_D4} — {msg}"
        self._toast_light(msg)
        # PLAYER-01: o rótulo de leitura de volta acompanha o preset na hora —
        # o `_refresh_lightbar_from_draft` não roda neste caminho (ele é o
        # sentido inverso: draft → widgets).
        #
        # L4 (25/08/2026): SÓ quando o envio deu certo. O rótulo dizia o
        # desenho novo mesmo depois de uma RECUSA nossa — com a mesa vazia o
        # `_enviar_player_leds` devolve `_AVISO_SEM_DESTINATARIO`, o toast
        # dizia que não deu, e o rótulo três centímetros acima passava a
        # anunciar o desenho como se estivesse valendo. Duas afirmações
        # contraditórias, na mesma aba, do mesmo clique.
        #
        # Na recusa o rótulo MANTÉM o que estava — que continua sendo o último
        # desenho que o produto de fato mandou. Escolha deliberada de não
        # inventar frase nova de tela: "não foi aplicado" seria texto novo, e
        # texto novo é dela.
        if ok:
            self._atualizar_estado_das_luzes(bits)

    def get_current_player_leds(self) -> tuple[bool, bool, bool, bool, bool]:
        states: list[bool] = []
        for i in range(1, 6):
            checkbox: Gtk.CheckButton = self._get(f"player_led_{i}")
            states.append(bool(checkbox.get_active()) if checkbox is not None else False)
        return (states[0], states[1], states[2], states[3], states[4])

    def _msg_do_desenho(
        self,
        *,
        ok: bool,
        motivo: str | None,
        corpo: dict[str, Any] | None,
        descricao: str,
        feito: str,
        fazer: str,
    ) -> str:
        """A frase do desenho das 5 luzes — UMA, para os três gestos.

        MESA-CHEIA-09/E3. Os três caminhos ("Aplicar LEDs", marcar uma caixa e
        os presets) compunham a frase cada um por si, e os três diziam
        *aplicado* em dois casos em que nenhum byte pegou:

        * **co-op ligado** — a camada do co-op vence a escolha manual, e a
          MESMA aba já dizia isso no rótulo de leitura de volta
          (``texto_do_desenho_aceso``). O toast contradizia o rótulo três
          centímetros acima dele;
        * **alvo fora da mesa** — o override fica guardado e o hotplug o
          aplica quando o controle voltar (D-9);
        * **Modo Nativo** (conserto 1.3) — o backend muta TODA escrita de
          output e re-escreve o desejado no desmute.

        A ordem importa: os donos de AGORA (co-op, Modo Nativo) vêm primeiro
        porque valem mesmo com o controle na mesa — não são pendência.

        **Conserto 1.5: as três SOMAM.** Este método parava na primeira
        condição verdadeira, e com co-op ligado E o alvo fora da mesa — o
        estado normal da mesa dela, porque a R-16 mantém o alvo justamente
        quando o controle cai — o toast prometia *"Vale quando o co-op sair"*,
        e sair do co-op não faz valer nada: o controle continua fora. A ordem
        (e a soma) mora agora em `textos_de_aplicacao.frase_de_guardado`.

        **BG-01 (26/08/2026): quem decide passou a ser o CORPO do daemon.** As
        três razões acima continuam na frase — como EXPLICAÇÃO de um guardado
        que o daemon declarou, nunca mais como a dedução que o declara. O
        `coop_aplica=True` é obrigatório aqui e só aqui nesta aba: o co-op
        governa `player_leds` e nada mais.
        """
        if not ok:
            return motivo or (
                f"Não consegui {fazer} o desenho das luzes — o Hefesto pode "
                "estar desligado (ligue na aba Sistema)"
            )
        assunto = f"Desenho das luzes ({descricao})"
        enviado = f"Desenho das luzes {feito} — {descricao}"
        if coop_manda_nas_luzes(self):
            # BG-01 + MESA-CHEIA-09: aqui o corpo do daemon NÃO basta, e é
            # MEDIDO. Com o co-op ligado e o controle na mesa, o byte SAI —
            # `apply_output_for` escreve o campo cru e devolve `"escreveu"`,
            # logo o daemon responde `aplicado_em: [uniq]` — e no mesmo
            # handler o `reassert_resolved_outputs` reescreve o desenho do
            # co-op por cima, porque a camada dele vence a manual no merge por
            # campo (R-13). O daemon diz a verdade sobre o BYTE; quem sabe que
            # ele não FICA é a janela. Deixar o corpo decidir aqui devolveria o
            # toast que contradiz o rótulo de leitura de volta três centímetros
            # acima — o defeito que a MESA-CHEIA-09 mediu e curou.
            #
            # É a ÚNICA exceção da aba, e ela é do co-op sobre `player_leds`:
            # a cor e o Modo Nativo o daemon já reporta certo (`"registrado"`
            # -> `guardado_em`), e por isso os outros dois gestos entregaram a
            # decisão inteira ao corpo.
            frase = frase_de_guardado(
                assunto,
                alvo_ausente=alvo_fora_da_mesa(self),
                coop=True,
                nativo=modo_nativo_manda_no_output(self),
            ) or enviado
        else:
            frase = frase_do_envio(assunto, enviado, corpo, self, coop_aplica=True)
        quantos = self._quantos_recebem_o_desenho()
        if quantos >= 2:
            frase = f"{frase} {_AVISO_MESMO_DESENHO_NOS_QUATRO.format(n=quantos)}"
        return frase

    def _quantos_recebem_o_desenho(self) -> int:
        """Quantos controles um clique de desenho atinge; 0 se for um só (L12).

        Só o "Todos" DELIBERADO conta: com alvo por controle o gesto vale para
        um, e com alvo desconhecido nada sai (a escrita já foi recusada antes
        de chegar aqui).
        """
        estado_alvo = self._edit_uniq()
        if estado_alvo.desconhecido or estado_alvo.uniq is not None:
            return 0
        return len(self._uniqs_conectados())

    @staticmethod
    def _descreve_player_leds(bits: list[bool] | tuple[bool, ...]) -> str:
        """Padrão dos LEDs de jogador em palavras (LB-03).

        Troca a antiga notação "x - - - -" (parecia depuração) por texto que
        casa com os rótulos "LED 1".."LED 5" das caixas: "LEDs acesos: 1 e 3".
        """
        acesos = [str(i) for i, ligado in enumerate(bits, start=1) if ligado]
        if not acesos:
            return "todos os LEDs apagados"
        if len(acesos) == 1:
            return f"LED aceso: {acesos[0]}"
        return "LEDs acesos: " + ", ".join(acesos[:-1]) + " e " + acesos[-1]

    def _on_lightbar_preview_draw(
        self, widget: Gtk.DrawingArea, cairo_ctx: Any
    ) -> bool:
        alloc = widget.get_allocation()
        r, g, b = self._current_rgb
        # Pré-visualização respeita a luminosidade corrente para dar feedback
        # imediato do slider antes de aplicar no hardware.
        level = max(0.0, min(1.0, self._current_brightness))
        cairo_ctx.set_source_rgb(
            (r / 255) * level,
            (g / 255) * level,
            (b / 255) * level,
        )
        cairo_ctx.rectangle(0, 0, alloc.width, alloc.height)
        cairo_ctx.fill()
        return False

    def _toast_light(self, msg: str) -> None:
        self._status_toast("light", msg)
