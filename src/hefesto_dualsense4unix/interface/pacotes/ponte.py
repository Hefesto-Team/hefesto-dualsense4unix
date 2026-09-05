#!/usr/bin/env python3
"""A PONTE PARA O PRODUTO — o que os gestos usam para agir. Nada se reescreve.

PERGUNTA DELA, 01/09/2026, e ela mudou esta camada: *"mas vc comparou com o
produto estável? tipo não estamos refazendo do zero né?"* — seguida de *"em
todas as abas temos praticamente tudo pronto"*.

Não estávamos refazendo o motor, mas estávamos reescrevendo a camada de cima: os
primeiros gestos chamavam o socket CRU, montando o payload à mão. Isso perde o
que o produto já sabe — o `led_set` do `app/ipc_bridge.py` tem
`_payload_led_set`, timeout pensado, a variante `_detalhado` que diz ONDE a cor
acendeu, e o `_call_checked` que traduz a recusa do daemon em frase de tela.

OS TRÊS DEGRAUS DO REUSO, nesta ordem — e a ordem é a regra:

    1. `app/ipc_bridge.py`   36 funções, SEM GTK. É a camada que a GUI estável
                             usa para falar com o daemon. `led_set`,
                             `trigger_set`, `rumble_policy_set_checked`,
                             `mic_set`, `speaker_set`, `apply_draft_detalhado`,
                             `identity_number_set`, `profile_switch`…
    2. os módulos da CLI     `cli/cmd_native.py`, `cli/cmd_coop.py` — também
                             puros, e donos dos métodos que o bridge não expõe.
    3. `chamar(metodo, …)`   o degrau cru, e SÓ para o que não tem nenhum dos  # (noqa-acento) id
                             dois. Ele passa pelo `_safe_call` do bridge, então
                             herda o timeout e o tratamento de erro — não é um
                             segundo caminho de escrita, é o mesmo sem atalho.

O QUE **NÃO** SE REUSA, e a razão é estrutural: os `app/actions/*.py` são mixins
GTK. O `lightbar_actions` depende de `self._get` (widgets), `self._toast_light`,
`self.draft` — 22 acessos a widget só no primeiro. Eles são a camada da JANELA
antiga, e a janela nova tem a sua. O que se reusa é o que está ABAIXO deles, que
é exatamente o `ipc_bridge`.

COMO UM GESTO USA:

    @gesto("04-iluminacao.html", "cor")
    def cor(ctx, o, p):
        p.led_set((r, g, b), uniq=o["uniq"])

O `p` é este módulo. A régua passa um dublê com os mesmos nomes e cobra QUAL
função foi chamada e com quê — que é como se prova que o botão faz, e não só
que existe.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[4]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.app import ipc_bridge as _b  # noqa: E402

# ---------------------------------------------------------------------------
# Degrau 1: o que o `ipc_bridge` já resolve. Os nomes ficam IGUAIS aos de lá,
# de propósito: quem procurar `led_set` acha os dois e vê que são o mesmo.
# ---------------------------------------------------------------------------
led_set = _b.led_set
led_set_detalhado = _b.led_set_detalhado
player_leds_set = _b.player_leds_set
player_leds_set_detalhado = _b.player_leds_set_detalhado
identity_number_set = _b.identity_number_set

trigger_set = _b.trigger_set
trigger_set_checked = _b.trigger_set_checked
trigger_set_detalhado = _b.trigger_set_detalhado
trigger_reset_detalhado = _b.trigger_reset_detalhado

rumble_set = _b.rumble_set
rumble_set_checked = _b.rumble_set_checked
rumble_stop = _b.rumble_stop
rumble_stop_checked = _b.rumble_stop_checked
rumble_passthrough = _b.rumble_passthrough
rumble_policy_set_checked = _b.rumble_policy_set_checked
rumble_policy_custom = _b.rumble_policy_custom
#: A BARRA DE CADA MOTOR, no perfil e por peça (VIBRACAO-POR-MOTOR-01). Ela
#: nasceu na ONDA1-D2 em 04/09/2026 **sem chamador**, e a razão estava escrita:
#: *"quem atravessa é a aba 05, que está no `nao_toca:` desta sprint"*. Esta
#: linha é a travessia, e ela fecha as duas dívidas que a D2 declarou nos
#: portões (`test_ipc_bridge._SEM_TRAVESSIA_DECLARADA` e
#: `portao_a_casa_sabe_e_o_produto_nao_faz._SEM_CAMINHO_HOJE`).
rumble_motores_set = _b.rumble_motores_set

mic_set = _b.mic_set
mic_set_detalhado = _b.mic_set_detalhado
# O ATO INTEIRO DO MICROFONE (D-12, 04/09/2026): o canal DESTE controle e o
# mudo do firmware, num pedido só. A ONDA1-D1 construiu as três funções no
# `ipc_bridge` e elas nasceram SEM chamador de tela — o gesto do 🎙 da aba 02 é
# quem as chama, e um gesto só alcança o que este módulo expõe.
mic_canal_set = _b.mic_canal_set
mic_canal_set_detalhado = _b.mic_canal_set_detalhado
mic_volume_set = _b.mic_volume_set
# A RESPOSTA INTEIRA DO VOLUME DO MICROFONE, e ela existe por um fato da MESA
# CHEIA: com dois DualSense no cabo há duas placas de som, e a rota global pega
# a PRIMEIRA — o microfone de outra pessoa. O `bool` do `mic_volume_set`
# colapsa isso em sucesso; o corpo traz `por_uniq`, que `ipc_bridge.
# alvo_honrado` lê em três estados.
mic_volume_set_detalhado = _b.mic_volume_set_detalhado
speaker_set = _b.speaker_set
speaker_set_detalhado = _b.speaker_set_detalhado

profile_list = _b.profile_list
profile_switch = _b.profile_switch
apply_draft_detalhado = _b.apply_draft_detalhado
autoswitch_lock_set = _b.autoswitch_lock_set
machine_declare = _b.machine_declare

daemon_state_full = _b.daemon_state_full
daemon_status_basic = _b.daemon_status_basic


# ---------------------------------------------------------------------------
# Degrau 3: o cru, e SÓ para o que não tem função em lugar nenhum.
# ---------------------------------------------------------------------------
#: OS TETOS DE TEMPO DO PRODUTO, e cada um é uma cicatriz medida — achado do
#: agente que ligou a aba Jogar em 01/09/2026:
#:
#:     `_safe_call` sem timeout usa **250 ms**, e desde o
#:     BUG-IPC-READ-NO-TIMEOUT-01 esse teto cobre também a LEITURA da resposta
#:     (`app/ipc_bridge.py:85-105`). Mas trocar de modo CRIA uinput e faz grab: o
#:     produto declara **2,0 s** para isso (`app/actions/mode_transition.py:37`,
#:     `MODE_IPC_TIMEOUT_S`), e o comentário de lá diz por quê — *"sem folga o
#:     toast dizia 'Falha' com o modo JÁ aplicado"*. O `profile.switch` teve a
#:     mesma cicatriz e ganhou **3,0 s** (`ipc_bridge.py:49`).
#:
#: Sem isto, um `chamar("gamepad.emulation.set", …)` volta `False` com o modo
#: aplicado — e um gesto que levantasse nesse `False` reintroduziria o defeito
#: exato que o `MODE_IPC_TIMEOUT_S` curou.
TETOS = {
    "gamepad.emulation.set": 2.0, "native.mode.set": 2.0,
    "mouse.emulation.set": 2.0, "keyboard.emulation.set": 2.0,
    "mouse.emulation.restore": 2.0, "daemon.emulation.suppress": 2.0,
    "profile.switch": 3.0, "profile.apply_draft": 3.0,
    "coop.set": 2.0, "coop.sync": 2.0, "identity.renumber": 2.0,
    # A MÁSCARA GRAVA EM DISCO E PODE RECRIAR O VPAD — mesma família do
    # `gamepad.emulation.set` logo acima, e por isso o mesmo teto. Sem ele o
    # gesto caía nos 250 ms do bridge, que desde o BUG-IPC-READ-NO-TIMEOUT-01
    # cobrem também a LEITURA da resposta: sob carga, `chamar` voltaria `False`
    # com a escolha JÁ gravada — o defeito exato que o `MODE_IPC_TIMEOUT_S`
    # curou, de volta por outra porta. Entrou em 04/09/2026, junto com a cura do
    # gesto que passava os parâmetros como `timeout` posicional e nunca chegava
    # ao daemon.
    "gamepad.mask.set": 2.0,
    "identity.number.set": 2.0,
    # Medido no daemon dela em 01/09: `daemon.reload` leva 9,5 SEGUNDOS.
    "daemon.reload": 15.0,
}


def teto(metodo: str) -> float:
    """Quanto tempo esperar por aquele método. O padrão é o do bridge."""
    return TETOS.get(metodo, 0.25)


def chamar(metodo: str, timeout: float | None = None, **params: Any) -> bool:
    """Um método do daemon que ainda não tem função no bridge nem na CLI.

    ANTES DE USAR ISTO, procure: o `ipc_bridge` tem 36 funções e a CLI tem os
    `cmd_*.py`. Uma chamada crua aqui para algo que já existe lá em cima é a
    segunda verdade que esta casa persegue — e perde a tradução da recusa, que é
    o que faz a tela dizer *por que* não deu, em vez de não dizer nada.

    Ele passa pelo `_safe_call` do bridge de propósito: herda o timeout e o
    tratamento de erro, e não vira um segundo caminho de escrita.
    """
    ok, _ = _b._safe_call(metodo, params, timeout=timeout or teto(metodo))
    return bool(ok)


def chamar_detalhado(metodo: str, **params: Any) -> tuple[bool, str | None]:
    """Como `chamar`, mas devolve `(ok, motivo)` — a recusa do daemon traduzida.

    Prefira esta quando o botão precisar DIZER por que não deu. Um botão que
    falha calado é a mesma doença de um botão que não faz nada.
    """
    return _b._call_checked(metodo, params, timeout=teto(metodo))


def resultado(metodo: str, timeout: float | None = None, **params: Any) -> Any:
    """O QUE O DAEMON RESPONDEU — e não só se ele aceitou.

    POR QUE ELA PRECISOU EXISTIR, 01/09/2026: `chamar()` devolve `bool` e joga
    fora o `result` que o `_safe_call` já traz de graça. Para um botão que
    ESCREVE isso basta; para um botão cuja promessa é MOSTRAR, não — e foi
    exatamente o que deixou `ver-plugins` sem dono na aba Sistema, com o daemon
    atendendo `plugin.list` desde sempre. Um gesto que chamasse `plugin.list` e
    descartasse a lista seria o botão "Ver os plugins carregados" que não mostra
    plugin nenhum: o botão que responde calado.

    ELA LEVANTA quando o daemon não atende, em vez de devolver `None`: um `None`
    silencioso viraria "não há plugins", que é uma afirmação diferente de "não
    consegui perguntar". O piloto pega a exceção e a imprime como `[gesto
    falhou]` — quem clicou fica sabendo.
    """
    ok, r = _b._safe_call(metodo, params, timeout=timeout or teto(metodo))
    if not ok:
        raise RuntimeError(f"o daemon não respondeu a {metodo}")
    return r


# ---------------------------------------------------------------------------
# O QUE SÓ A JANELA PODE FAZER — e por isso é INJETADO, não importado
# ---------------------------------------------------------------------------
#: ESCOLHER UM ARQUIVO é do SISTEMA, não da página: o WebView não abre
#: `FileChooserDialog`, e a página não tem acesso ao disco. Quem pode abri-lo é
#: o piloto, que é GTK — e ele substitui esta função ao subir
#: (`ponte.escolher_arquivo = self._escolher_arquivo`).
#:
#: POR QUE UM PONTO DE EXTENSÃO E NÃO UM IMPORT DE GTK AQUI: porque os pacotes
#: são PUROS e é isso que os torna testáveis sem abrir janela. Um `import gi`
#: neste módulo obrigaria toda régua a ter GTK, e o CI a rodar com display.
#:
#: O padrão RECUSA DIZENDO. Rodar um gesto de importação fora da janela é um
#: erro de quem chamou, e um `None` silencioso aqui viraria "ela cancelou" —
#: que é uma mentira sobre o que aconteceu.
def escolher_arquivo(titulo: str, padrao: str = "*", **_: Any) -> str | None:
    """O caminho que ela escolheu, ou `None` se cancelou. Substituído pelo piloto."""
    raise RuntimeError(
        f"escolher_arquivo({titulo!r}) foi chamado fora da janela. Só o piloto "
        f"pode abrir o seletor do sistema — ele substitui esta função ao subir.")


def salvar_arquivo(titulo: str, sugestao: str = "", **_: Any) -> str | None:
    """Onde ela quer gravar, ou `None` se cancelou. Substituído pelo piloto."""
    raise RuntimeError(
        f"salvar_arquivo({titulo!r}) foi chamado fora da janela. Só o piloto "
        f"pode abrir o seletor do sistema — ele substitui esta função ao subir.")
