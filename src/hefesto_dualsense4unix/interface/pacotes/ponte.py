#!/usr/bin/env python3
"""A PONTE PARA O PRODUTO — o que os gestos usam para agir. Nada se reescreve.

PERGUNTA, 01/09/2026, e ela mudou esta camada: ** — seguida de .

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
from hefesto_dualsense4unix.integrations.central_do_radio import (  # noqa: E402
    PRAZO_DA_TRAVA_DO_GESTO_S,
)

# de propósito: quem procurar `led_set` acha os dois e vê que são o mesmo.
led_set = _b.led_set
led_set_detalhado = _b.led_set_detalhado
player_leds_set = _b.player_leds_set
player_leds_set_detalhado = _b.player_leds_set_detalhado
player_led_brightness_set_detalhado = _b.player_led_brightness_set_detalhado
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
#: linha é a travessia, e ela fecha as duas dívidas que a D2 declarou nos
#: `portao_a_casa_sabe_e_o_produto_nao_faz._SEM_CAMINHO_HOJE`).
rumble_motores_set = _b.rumble_motores_set

mic_set = _b.mic_set
mic_set_detalhado = _b.mic_set_detalhado
mic_canal_set = _b.mic_canal_set
mic_canal_set_detalhado = _b.mic_canal_set_detalhado
mic_volume_set = _b.mic_volume_set
# CHEIA: com dois DualSense no cabo há duas placas de som, e a rota global pega
mic_volume_set_detalhado = _b.mic_volume_set_detalhado
speaker_set = _b.speaker_set
speaker_set_detalhado = _b.speaker_set_detalhado

sensor_set_detalhado = _b.sensor_set_detalhado

mira_set_detalhado = _b.mira_set_detalhado

profile_list = _b.profile_list
profile_switch = _b.profile_switch
apply_draft_detalhado = _b.apply_draft_detalhado
freestyle_set = _b.freestyle_set
machine_declare = _b.machine_declare

daemon_state_full = _b.daemon_state_full
daemon_status_basic = _b.daemon_status_basic


#:     toast dizia 'Falha' com o modo JÁ aplicado"*. O `profile.switch` teve a
#: Sem isto, um `chamar("gamepad.emulation.set", …)` volta `False` com o modo
TETOS = {
    "gamepad.emulation.set": 2.0, "native.mode.set": 2.0,
    "mouse.emulation.set": 2.0, "keyboard.emulation.set": 2.0,
    "desktop.status.set": 2.0,
    "mouse.emulation.restore": 2.0, "daemon.emulation.suppress": 2.0,
    # Navegação. **3,0 s — a família do `profile.switch`, e não a do
    # `mouse.emulation.restore` de 2,0 s logo acima.** A razão é o que ele faz
    # `key_bindings`/`button_actions` e pode CRIAR o device de teclado além do
    "desktop.arranjo.apply": 3.0,
    "profile.switch": 3.0, "profile.apply_draft": 3.0,
    # O-APLICAR-E-A-ATIVACAO-SAO-UMA-SO-01 (01/10/2026): o «Aplicar» roda a
    # cadeia da ativação, e por isso o teto é o do `profile.switch`.
    "profile.reaplicar": 3.0,
    "coop.set": 2.0, "coop.sync": 2.0, "identity.renumber": 2.0,
    "gamepad.mask.set": 2.0,
    "identity.number.set": 2.0,
    # O pedido do «Procurar» espera a busca SUBIR no serviço (o BlueZ abre a janela:
    # 107 a 366 ms medidos no diário dela em 03/10), e o serviço espera, no pior caso,
    # o prazo da trava mais 1 s. O prazo de tela de 0,25 s dava «não respondeu» sobre
    # uma busca que subia.
    "radio.busca.set": PRAZO_DA_TRAVA_DO_GESTO_S + 2.0,
    # Medido no daemon do usuário em 01/09: `daemon.reload` leva 9,5 SEGUNDOS.
    "daemon.reload": 15.0,
}


def teto(metodo: str) -> float:
    """Quanto tempo esperar por aquele método. O padrão é o do bridge."""
    return TETOS.get(metodo, 0.25)


def chamar(metodo: str, timeout: float | None = None, **params: Any) -> bool:
    """Um método do daemon que ainda não tem função no bridge nem na CLI."""
    ok, _ = _b._safe_call(metodo, params, timeout=timeout or teto(metodo))
    return bool(ok)


def chamar_detalhado(metodo: str, **params: Any) -> tuple[bool, str | None]:
    """Como `chamar`, mas devolve `(ok, motivo)` — a recusa do daemon traduzida.

    Prefira esta quando o botão precisar DIZER por que não deu. Um botão que
    falha calado é a mesma doença de um botão que não faz nada.

    **`motivo` JUNTA AS DUAS FORMAS DE O DAEMON DIZER NÃO** — A-PERNA-QUE-FALTA-01,
    11/09/2026 — e até hoje ela só trazia uma.

    Esta casa tem dois "não" (`ipc_bridge._recusa_no_corpo`): o erro JSON-RPC de
    parâmetro inválido, e a FRASE NO CORPO de uma resposta bem-sucedida — o
    pedido era válido e mesmo assim não se realizou. `_call_checked` só lê o
    primeiro: para o segundo ele responde `(True, None)`, porque o RPC foi bem.

    O QUE ISSO CUSTAVA, medido: `gamepad.mask.set` responde
    `{"status": "ok", "gravado": false, "motivo": "sem_perfil"}` quando não há
    onde guardar a máscara. O RPC deu certo; a gravação não. A tela recebia
    `(True, None)` e piscava verde sobre um perfil que não mudou — a família de
    defeito mais cara desta casa.

    A CURA É O PADRÃO QUE O BRIDGE JÁ USA, e não um terceiro caminho:
    `_call_checked_detalhado` + `_recusa_no_corpo`, exatamente como
    `trigger_set_detalhado` e `trigger_reset_detalhado` fazem. O corpo continua
    descartado aqui — quem o quer inteiro chama `resultado`.

    O CONTRATO NÃO MUDA: continua `(ok, motivo)`, e `ok` continua sendo só o do
    RPC. Um corpo que traz `motivo` sem ter fracassado — um `sem_mudanca`, uma
    ressalva — chega com `ok=True` e a frase ao lado; **quem decide o que é
    recusa e o que é ressalva é o dono do assunto**, que é o gesto. Ver
    `a01_jogar.mascara_do_controle`.
    """
    ok, motivo, corpo = _b._call_checked_detalhado(
        metodo, params, timeout=teto(metodo)
    )
    return ok, motivo or _b._recusa_no_corpo(corpo)


def profile_reaplicar(nome: str) -> dict[str, Any] | None:
    """O «Aplicar» do rodapé: a resposta do `profile.reaplicar`, ou ``None``."""
    ok, r = _b._safe_call(
        "profile.reaplicar", {"name": nome}, timeout=teto("profile.reaplicar")
    )
    return r if ok and isinstance(r, dict) else None


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


def escolher_arquivo(titulo: str, padrao: str = "*", **_: Any) -> str | None:
    """O caminho que o usuário escolheu, ou `None` se cancelou. Substituído pelo piloto."""
    raise RuntimeError(
        f"escolher_arquivo({titulo!r}) foi chamado fora da janela. Só o piloto "
        f"pode abrir o seletor do sistema — ele substitui esta função ao subir.")


def salvar_arquivo(titulo: str, sugestao: str = "", **_: Any) -> str | None:
    """Onde ela quer gravar, ou `None` se cancelou. Substituído pelo piloto."""
    raise RuntimeError(
        f"salvar_arquivo({titulo!r}) foi chamado fora da janela. Só o piloto "
        f"pode abrir o seletor do sistema — ele substitui esta função ao subir.")


def dentro_da_janela() -> bool:
    """A janela do produto está de pé NESTE processo? (função pura)

    **NÃO É ADIVINHAÇÃO, E MUITO MENOS "estou sob teste?"** — é a leitura de um
    fato que já existia: quem sobe a janela SUBSTITUI os dois pontos de extensão
    acima (`ponte.escolher_arquivo` e `ponte.salvar_arquivo`, atribuídos em
    `interface/hefesto_vivo.py:2406`), e mais ninguém o faz. Enquanto
    `escolher_arquivo` for a função declarada aqui, não há janela: quem está
    chamando um gesto é uma régua, um script ou um driver de medição.

    **POR QUE ISSO PRECISOU EXISTIR — 06/09/2026, por um defeito medido.** O som
    de confirmação da aba 02 (A-CONFISSAO-NO-BOTAO-01) chama o tocador do
    sistema. Medido na bancada: com o `pactl` DUBLADO de uma régua vizinha, o
    sink do DualSense casa pela regra do um-para-um, o motor o encontra "na
    lista viva" e segue para o `paplay` — que **não** está dublado. A suíte
    tocava som no alto-falante do controle do usuário, enquanto ele trabalhava.

    A guarda-mãe do `audio_saida` não alcança este caso de propósito: ela
    confere o sink contra a lista viva, e numa régua a lista viva é de mentira.
    Quem sabe que ninguém clicou é esta camada.

    **É O MESMO DESENHO QUE O MEDIDOR DE ONDAS JÁ USA**, e pela mesma razão
    escrita lá: *"a suíte chama `a02_controles.pacote()` centenas de vezes, e um
    fluxo de captura aberto a cada chamada seguraria o microfone do usuário aberto
    durante a suíte inteira. O piloto é o produto; é ele quem autoriza."* A
    diferença é que ali o piloto acende a chave com uma linha própria, e aqui o
    fato já estava disponível sem tocar no piloto.
    """
    return getattr(escolher_arquivo, "__module__", __name__) != __name__


haptica_testar = _b.haptica_testar
