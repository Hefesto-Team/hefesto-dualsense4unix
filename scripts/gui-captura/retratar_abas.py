#!/usr/bin/env python3
"""Retrata as DEZ abas da janela, com o card do controle vivo dentro.

É o script que a documentação e quem for trabalhar na interface usam —
pessoa ou assistente. Uma execução, nenhum
clique, nenhuma janela na frente: ele monta a interface numa janela offscreen
do tamanho da tela maximizada dela e salva um PNG por aba.

    scripts/gui-captura/retratar_abas.py                 # atualiza as imagens
                                                         # da documentação
    scripts/gui-captura/retratar_abas.py /tmp/olhar      # só olhar, sem tocar
                                                         # no repositório

POR QUE ELE EXISTE, e por que é ele o certo para a JANELA
---------------------------------------------------------

Esta pasta tem outros quatro. Dois deles fotografam a janela também, e os dois
têm limite conhecido (os outros dois são o `retratar_dialogos.py`, que
fotografa DIÁLOGO e não aba, e o `aba_ativa.sh`, que é sensor e não câmera):

* ``capturar_verificado.sh`` percorre as abas por teclado e fotografa a tela
  DE VERDADE. Precisa da janela aberta, maximizada e em foco — e o COSMIC
  recusou maximizar por atalho, por duplo clique e por F11. Serve para prova
  final com o olho dela, não para rotina;
* ``retrato_offscreen.py`` renderiza o ``.glade`` CRU. Rápido e sem
  dependência, mas mostra a janela VAZIA: combos sem itens, listas sem linhas
  e — o pior — a aba Status sem o card do controle, que é montado em código e
  é justamente a aba mais densa da janela.

Este aqui monta o glade E injeta o card do controle com dados de verdade. É o
único dos três que produz uma foto onde dá para entender a tela.

O QUE ELE **NÃO** É
-------------------

Ele não substitui o olho dela. Um `OffscreenWindow` não passa pelo compositor:
não há sombra, arredondamento de canto nem o tema de janela do COSMIC. Para
"ficou bonito?" a resposta continua sendo a tela real. Para "o que tem nesta
aba, e onde?", esta foto é fiel — e é para isso que ela serve.

ARMADILHAS QUE ESTE ARQUIVO JÁ PAGOU (não as repita)
-----------------------------------------------------

1. **Sob Xvfb não há gerenciador de janelas.** Uma ``Gtk.Window`` de verdade
   nunca é mapeada e o filho fica 1x1 para sempre, por mais que o laço de
   eventos rode. Por isso aqui é ``OffscreenWindow``, que se auto-aloca.
2. **Widget sem alocação mede 1x1**, e qualquer medida tirada dele passa com
   qualquer desenho. O ``_assentar()`` abaixo drena o laço mais de uma vez de
   propósito.
3. **A aba Status sem o card é uma foto de tela vazia.** Foi o que fez uma leva
   inteira ser fotografada sem o objeto que ela mudava.
4. **O tema tem de ser aplicado**, senão as cores saem do tema do sistema e a
   foto não é o produto.

PRIVACIDADE — POR QUE ESTA FOTO É SEGURA, E O QUE A TORNARIA INSEGURA
---------------------------------------------------------------------

O `README.md` avisa que, numa foto antiga da aba Sistema, o bloco "Detalhes
técnicos" **teve de ser borrado à mão** porque o log mostrava o endereço
Bluetooth real dos controles — e que **os portões de anonimato não varrem
imagens**.

Este script não tem esse risco, e não por sorte: ele **nunca fala com o
daemon**. Monta o `.glade` do zero e alimenta o card com os dublês da suíte,
cujo MAC é falso por construção (`aa:bb:cc:...`). O painel de log da aba Sistema
sai vazio porque não há daemon do outro lado.

**O que tornaria inseguro**, e portanto o que NÃO fazer aqui:

* pedir estado ao daemon vivo (`daemon.state_full`) para "deixar a foto mais
  real" — traria MAC, nome de rede e caminho de arquivo da máquina dela;
* fotografar a janela de verdade em vez de montar uma offscreen;
* alimentar o card com um payload copiado de uma sessão real.

Se algum dia isto mudar, **a foto passa a precisar de revisão humana antes de
ir para o repositório** — e aí o script deixa de poder gravar direto em
`docs/`.

O QUE A ABA PERFIS PASSOU A LER DO DISCO (13/08/2026)
-----------------------------------------------------

`install_profiles_tab` agora monta a lista de jogos do campo "Nome do jogo:" a
partir de `integrations/jogos_locais.py`, que lê `~/.steam/.../*.acf` e os
`.desktop` de `~/.local/share/applications`. Isso é DISCO, não daemon — a
promessa acima continua de pé —, mas é a primeira vez que uma foto desta pasta
roda código que abre arquivo da máquina dela.

**Nada disso aparece na foto**, e é medido: a lista mora numa
`Gtk.EntryCompletion`, cujo popup é um toplevel próprio que só existe enquanto
ela digita — a `OffscreenWindow` não o alcança. A aba é fotografada com "Aplica
a: Qualquer", e nesse estado a linha do jogo nem é mostrada.

**O que tornaria inseguro:** fotografar a aba com "Jogo da Steam" escolhido E
texto digitado no campo. Aí a lista de jogos DELA entraria na imagem, e o
portão de anonimato não varre imagem. Se um dia for preciso essa foto, ela vai
para fora de `docs/`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

RAIZ = Path(os.environ.get("HEFESTO_RAIZ", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("GDK_BACKEND", "x11")

import gi  # noqa: E402 — depois de gi.require_version, obrigatoriamente

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

GLADE = RAIZ / "src/hefesto_dualsense4unix/gui/main.glade"

#: O destino padrão é onde a documentação já aponta. Rodar sem argumento
#: ATUALIZA as imagens do README e do guia da interface — é o comportamento
#: pedido: uma execução e a documentação deixa de mentir.
DESTINO_DOC = RAIZ / "docs/usage/assets"

#: A tela dela maximizada. Não é número inventado: é a resolução em que as
#: bancadas de layout desta casa medem, e a mesma do `retrato_offscreen.py`.
LARGURA, ALTURA = 1920, 1080

#: Os nomes que a documentação referencia. A ORDEM é a das abas no notebook.
#: O `interface.md` cita os nove; mudar um nome aqui quebra a documentação, então
#: o script confere no fim e avisa.
NOMES = (
    "readme_inicio",
    "readme_status",
    "readme_no_jogo",
    "readme_gatilhos",
    "readme_lightbar",
    "readme_rumble",
    "readme_perfis",
    "readme_sistema",
    "readme_emulacao",
    "readme_navegacao_dsx",
)


def _assentar(vezes: int = 8) -> None:
    """Drena o laço de eventos até o GTK parar de ter o que fazer.

    Mais de uma passada de propósito: a primeira monta, as seguintes deixam o
    tema, os `SizeGroup` e as elipses assentarem. Widget medido antes disso
    reporta 1x1.
    """
    for _ in range(vezes):
        while Gtk.events_pending():
            Gtk.main_iteration()


def _aplicar_tema(janela) -> str:  # type: ignore[no-untyped-def]
    """Aplica o tema do produto. A assinatura mudou entre versões; tenta as duas."""
    try:
        from hefesto_dualsense4unix.app.theme import apply_theme
    except Exception as exc:  # tema indisponível não impede a foto
        return f"tema indisponível ({exc})"
    for tentativa in (lambda: apply_theme(janela), lambda: apply_theme()):
        try:
            tentativa()
            return "tema aplicado"
        except TypeError:
            continue
        except Exception as exc:
            return f"tema falhou ({exc})"
    return "tema não aplicado"


def _aplicar_regras_de_runtime(builder, card) -> None:  # type: ignore[no-untyped-def]
    """Roda, sobre a janela fotografada, o que a aba Status faz ao vivo.

    O host é mínimo de propósito — a `StatusActionsMixin` precisa de duas
    coisas para estes dois métodos: um `_get` que resolva ids do builder e o
    dicionário de cards. Nada de IPC, nada de tique.
    """
    from hefesto_dualsense4unix.app.actions.status_actions import (
        StatusActionsMixin,
    )

    class _Host(StatusActionsMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self.builder = builder
            self._status_cards = {("card",): card}
            self._status_card_keys = [("card",)]

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

    host = _Host()
    host._alojar_botao_da_rota()
    # Um controle só: o frame "Estado" sai da tela e o card responde por
    # perfil e daemon. Os textos são os que o daemon dela publica hoje.
    host._set_frame_estado_visivel(False)
    card.definir_estado_global("Nenhum", "Ligado")


def _montar_aba_inicio(builder) -> str:  # type: ignore[no-untyped-def]
    """Monta a aba Início e a preenche com um estado plausível do daemon.

    COOP-SEM-INTERRUPTOR-01 (06/08/2026) — a cura que a `PEDIDOS-DELA-01`
    nomeou como pré-requisito da prova de tela. A aba Início é **100% código**
    (`install_home_tab`): o glade só reserva o `tab_home_box`. Enquanto sobrou
    ali um frame de glade — a seção "Jogar acompanhada" — a foto documentava
    aquele frame e mais nada, e passava por retrato da aba. Com o frame fora, a
    foto virou um retângulo vazio: honesta e inútil.

    Mesmo desenho do card do Status e dos modos de gatilho: host mínimo com um
    `_get` que resolve ids do builder, nada de IPC e nada de tique. O
    `_render_home` recebe um `state_full` de mesa cheia — dois controles, dois
    jogadores — porque é ele que a aba existe para responder.
    """
    try:
        from hefesto_dualsense4unix.app.actions.home_actions import (
            HomeActionsMixin,
        )
    except Exception as exc:
        return f"aba Início não montada ({exc})"

    class _Host(HomeActionsMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self.builder = builder

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

        def _status_toast(self, _contexto: str, _msg: str) -> None:
            return None

        def _refresh_home_tab(self) -> None:
            return None

    def _controle(indice: int, jogador: int, *, primario: bool) -> dict:
        return {
            "index": indice,
            "connected": True,
            "transport": "usb" if primario else "bt",
            "is_primary": primario,
            "player": jogador,
            "battery_pct": 87 if primario else 64,
        }

    estado = {
        "connected": True,
        "native_mode": False,
        "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
        "coop": {"enabled": True, "players": 2},
        "controllers": [_controle(0, 1, primario=True), _controle(1, 2, primario=False)],
        "active_profile": "coop_local",
    }
    try:
        host = _Host()
        host.install_home_tab()
        host._render_home(estado)
    except Exception as exc:
        return f"aba Início não montada ({exc})"
    caixa = builder.get_object("tab_home_box")
    if caixa is not None:
        caixa.show_all()
    return "aba Início montada (2 controles = 2 jogadores)"


#: Os dois controles da aba "No jogo", e o vpad de cada um.
#:
#: Os MACs são falsos por construção (octetos 4 e 5 zerados, a máscara desta
#: casa — há portão que reprova MAC real em arquivo versionado), e os números
#: do vpad são os de uma mesa de verdade medida em 09/08 com o jogo aberto:
#: 158,3 Hz de giroscópio, o clique do touchpad visto há 73 s e a vibração
#: chegando aos motores. A mistura é DE PROPÓSITO: só assim a foto mostra as
#: três situações da aba de uma vez — "no jogo agora", "parou" e "sem pedido
#: ainda" — que é o que ela precisa reconhecer ao trocar de máscara.
_NO_JOGO_CONTROLES = (
    {
        "index": 0,
        "connected": True,
        "transport": "usb",
        "is_primary": True,
        "player": 1,
        "player_slot": 1,
        "uniq": "aa:bb:cc:00:00:01",
    },
    {
        "index": 1,
        "connected": True,
        "transport": "bt",
        "is_primary": False,
        "player": 2,
        "player_slot": 2,
        "uniq": "aa:bb:cc:00:00:02",
    },
)

_NO_JOGO_ESTADO = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "controllers": list(_NO_JOGO_CONTROLES),
    # PERFIL-MUDO-01 (10/08/2026): o aviso do perfil que não entrou. A foto o
    # mostra porque ele é a única linha desta aba que pede DECISÃO dela, e uma
    # imagem de documentação que só mostra o caso bom ensina a não procurá-lo.
    # O texto é o do caso real, com o `wine64-preloader` que o Hefesto vê no
    # lugar do `.exe` — a mesma frase que o daemon monta em
    # `profiles.porque_nao_entrou`.
    "active_profile": "fallback",
    "perfil_do_jogo_que_nao_entrou": [
        {
            "nome": "Pragmata",
            "frase": (
                'O seu perfil "Pragmata" é deste jogo, mas não entrou: '
                'ele exige nome do processo "PRAGMATA.exe", e aqui vê '
                '"wine64-preloader".'
            ),
        }
    ],
    "rumble_ff": {
        "per_vpad": [
            {
                "player": 1,
                "backend": "uhid",
                "motion_streaming": True,
                "motion_hz": 158.3,
                "motion_forwards": 48210,
                "touchpad_pressionado": False,
                "rumble_no_fisico": [30, 120],
                "rumble_no_fisico_ha_s": 0.4,
                "visto_ha_s": {
                    "rumble": 0.4,
                    "lightbar": 1.1,
                    "touchpad_click": 73.0,
                },
            },
            {
                "player": 2,
                "backend": "uhid",
                # O espelho DESTE jogador caiu agora há pouco: `motion_streaming`
                # falso com `motion_forwards` > 0 é exatamente o par que separa
                # "o giroscópio parou" de "nunca começou" (ORFAOS-QUE-VOLTAM-01).
                "motion_streaming": False,
                "motion_hz": 0.0,
                "motion_forwards": 12904,
                "touchpad_pressionado": False,
                "visto_ha_s": {"rumble": 0.9},
            },
        ]
    },
}


def _montar_aba_no_jogo(builder) -> str:  # type: ignore[no-untyped-def]
    """Monta a aba "No jogo" e a preenche com uma mesa de dois jogadores.

    Mesmo desenho do card do Status e da aba Início: host mínimo com um `_get`
    que resolve ids do builder, nada de IPC e nada de tique. Os métodos são os
    de PRODUÇÃO (`install_no_jogo_tab` e `_sync_paineis_no_jogo`) — uma cópia
    da montagem aqui seria um segundo dono do desenho, e a foto passaria a
    mentir no dia em que a `status_actions` mudasse.

    O `_get` devolve `None` para o `main_notebook` de propósito, e desde a
    ABA-DO-JOGO-01 (10/08/2026) por DUAS razões, não uma:

    * o gate de "só trabalha com a aba à vista" não tem sentido numa janela
      offscreen em que TODAS as páginas são fotografadas;
    * e o gate de EXISTÊNCIA da aba — ela só entra na tira com um jogo da Steam
      aberto — tiraria da documentação justamente a foto que se quer, que é a
      da aba **jogando**. Sem notebook, `_pagina_do_notebook` devolve `None` e
      os dois gates saem do caminho.

    É o mesmo escape que a própria mixin já documenta para quem monta sem glade.
    Devolver um notebook de verdade aqui apagaria a foto desta aba.
    """
    try:
        from hefesto_dualsense4unix.app.actions.status_actions import (
            StatusActionsMixin,
        )
    except Exception as exc:
        return f'aba "No jogo" não montada ({exc})'

    class _Host(StatusActionsMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self.builder = builder

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            if nome == "main_notebook":
                return None
            return self.builder.get_object(nome)

    try:
        host = _Host()
        host.install_no_jogo_tab()
        host._sync_paineis_no_jogo(dict(_NO_JOGO_ESTADO))
    except Exception as exc:
        return f'aba "No jogo" não montada ({exc})'
    caixa = builder.get_object("tab_no_jogo_box")
    if caixa is not None:
        caixa.show_all()
    return 'aba "No jogo" montada (2 jogadores, as três situações na tela)'


#: Os perfis que aparecem na foto da aba Perfis.
#:
#: São INVENTADOS de propósito, e não lidos do disco: `load_all_profiles()`
#: traria os perfis DELA — nome de jogo, nome de janela, nome de processo — para
#: dentro de uma imagem versionada, que é exatamente o risco que a seção de
#: privacidade deste arquivo manda não correr (os portões de anonimato não
#: varrem imagens). O jogo é o mesmo "Pragmata" que a aba "No jogo" já mostra,
#: para as duas fotos contarem a mesma história.
_PERFIS_DA_FOTO = (
    {
        "name": "Pragmata",
        "priority": 120,
        "process_name": ["PRAGMATA.exe"],
        "kind": "gamepad",
    },
    {
        "name": "Mesa de dois",
        "priority": 60,
        "process_name": ["portal2_linux"],
        "kind": "gamepad",
    },
    {
        "name": "Fora do jogo",
        "priority": 0,
        "process_name": [],
        "kind": "desktop",
    },
)


def _montar_aba_perfis(builder) -> str:  # type: ignore[no-untyped-def]
    """Monta a aba Perfis — a mais editada da janela, e a que saía como casca.

    PERFIS-NA-FOTO-01 (13/08/2026). Até aqui a foto desta aba mostrava
    "Aplica a:" **sem um botão** e o frame "Modo (o que este perfil liga ao
    ativar)" **vazio**, porque os dois são montados em CÓDIGO
    (`install_profiles_tab` e `_install_mode_section`) e este script montava só
    o glade. É literalmente o defeito de que o docstring lá em cima acusa o
    `retrato_offscreen.py` — "mostra a janela VAZIA: combos sem itens" —
    reproduzido no script que existe para ser a cura dele.

    Mesmo desenho do card do Status, da aba Início e da "No jogo": host mínimo
    com um `_get` que resolve ids do builder, nada de IPC e nada de tique. O
    método é o de PRODUÇÃO (`install_profiles_tab`), e não uma cópia da
    montagem — uma cópia seria um segundo dono do desenho e a foto passaria a
    mentir no dia em que a `profiles_actions` mudasse.

    O QUE É DESVIADO, E POR QUÊ
    ---------------------------

    Três coisas dentro do `install_profiles_tab` leem o DISCO DELA, e as três
    são desviadas aqui — não por conveniência, por privacidade e por
    reprodutibilidade:

    * ``_reload_profiles_store`` chamaria `load_all_profiles()` e poria os
      perfis dela na imagem versionada. É sobrescrito no host, e ainda de
      quebra vira SÍNCRONO: o de produção roda numa thread e o `main` já teria
      fotografado antes de a lista chegar;
    * ``load_gui_prefs()`` decide se o editor abre no modo simples ou no
      avançado. Lido do disco, a foto mudaria conforme o switch que ela deixou
      ligado da última vez;
    * ``perfil_que_ela_ativou()`` devolve o nome do perfil ATIVO dela, que a
      lista imprime em negrito e colorido na primeira linha.

    As duas últimas são funções de módulo — o desvio é no módulo, com
    `try/finally` para o processo não ficar com a `profiles_actions` remendada
    depois desta função.

    E uma quarta, que é a mais grave e não é disco: o `on_done` de produção é
    ``_sync_selection_with_active_profile``, que **FALA COM O DAEMON VIVO**
    (`call_async("daemon.status")`). Medido em 13/08/2026 na primeira rodada
    desta função, antes deste desvio existir: o log saiu com
    `perfis_selecao_automatica_recusada pedido=<perfil real dela>` — o nome
    veio da máquina, não daqui. Um script de fotografia que consulta o daemon
    quebra a promessa escrita lá em cima ("ele **nunca** fala com o daemon") e
    põe estado real a um passo da imagem versionada. É no-op no host.
    """
    try:
        from hefesto_dualsense4unix.app.actions import profiles_actions as _pa
        from hefesto_dualsense4unix.profiles.schema import (
            MatchCriteria,
            Profile,
            ProfileModeConfig,
        )
    except Exception as exc:
        return f"aba Perfis não montada ({exc})"

    try:
        perfis = [
            Profile(
                name=dados["name"],
                priority=dados["priority"],
                match=MatchCriteria(process_name=list(dados["process_name"])),
                mode=ProfileModeConfig(kind=dados["kind"]),
            )
            for dados in _PERFIS_DA_FOTO
        ]
    except Exception as exc:
        return f"aba Perfis não montada ({exc})"

    class _Host(_pa.ProfilesActionsMixin):  # type: ignore[misc, name-defined]
        def __init__(self) -> None:
            self.builder = builder

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

        def _status_toast(self, _contexto: str, _msg: str) -> None:
            return None

        def _reload_profiles_store(  # type: ignore[override]
            self, select_name: str | None = None, on_done=None
        ) -> None:
            self._profiles_cache = list(perfis)
            self._populate_profiles_store(list(perfis), select_name)
            if on_done is not None:
                on_done()

        def _sync_selection_with_active_profile(self) -> None:  # type: ignore[override]
            # O de produção pergunta ao daemon VIVO. Aqui, nunca.
            return None

    prefs_de_verdade = _pa.load_gui_prefs
    ativo_de_verdade = _pa.perfil_que_ela_ativou
    _pa.load_gui_prefs = lambda: {"advanced_editor": False}
    _pa.perfil_que_ela_ativou = lambda: perfis[0].name
    try:
        host = _Host()
        host.install_profiles_tab()
    except Exception as exc:
        return f"aba Perfis não montada ({exc})"
    finally:
        _pa.load_gui_prefs = prefs_de_verdade
        _pa.perfil_que_ela_ativou = ativo_de_verdade

    caixa = builder.get_object("profiles_paned")
    if caixa is not None:
        caixa.show_all()
    return (
        f"aba Perfis montada ({len(perfis)} perfis inventados, "
        '"Aplica a" e "Modo" com botões)'
    )


def _injetar_modos_de_gatilho(builder) -> str:  # type: ignore[no-untyped-def]
    """Põe os 19 modos de gatilho na aba Gatilhos.

    Mesmo motivo do card do Status: os botões são montados em CÓDIGO
    (`triggers_actions.install_triggers_tab`), não no glade. Sem isto a aba sai
    com "Modo:" e mais nada — e era assim que ela aparecia na documentação,
    justamente na aba que a TRIGGER-CANON-01 inteira mexeu.

    Os itens saem do `trigger_specs.PRESETS`, que é a mesma fonte que o
    produto usa. Uma lista copiada aqui viraria um segundo dono dos rótulos, e
    a foto passaria a mentir no dia em que um deles mudasse.
    """
    try:
        from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS
        from hefesto_dualsense4unix.app.widgets import SegmentedSelector
    except Exception as exc:
        return f"modos de gatilho não injetados ({exc})"

    itens = [(spec.name, spec.label) for spec in PRESETS]
    postos = 0
    for lado in ("left", "right"):
        slot = builder.get_object(f"trigger_{lado}_mode_slot")
        if slot is None:
            continue
        sel = SegmentedSelector(wrap=True)
        sel.set_items(itens)
        # O primeiro é o "Desligado", e é o que a aba mostra ao abrir.
        sel.set_active_id(itens[0][0])
        slot.pack_start(sel, True, True, 0)
        sel.show_all()
        postos += 1
    if not postos:
        return "modos de gatilho não injetados (slots ausentes no glade)"
    return f"{len(itens)} modos de gatilho injetados nos {postos} lados"


def _injetar_card(builder) -> str:  # type: ignore[no-untyped-def]
    """Põe um card de controle vivo na aba Status.

    É o que separa este script do `retrato_offscreen.py`. Sem isto, a aba mais
    densa da janela sai vazia e a foto não serve para entender nada.

    Os dados vêm dos dublês da suíte (`test_status_faixa_blocos`) de propósito:
    eles já são a entrada canônica de um controle completo — sensores,
    touchpad, bateria — e são mantidos junto com o card. Inventar um payload
    aqui seria criar um segundo dono do formato.
    """
    try:
        from hefesto_dualsense4unix.app.mic_monitor import LeituraMic
        from hefesto_dualsense4unix.app.widgets.controller_card import (
            ControllerCard,
        )
        from tests.unit.test_status_faixa_blocos import _ENTRY, _ESTADO
    except Exception as exc:
        return f"card não injetado ({exc}) — a aba Status sai vazia"

    slot = builder.get_object("status_players_slot")
    if slot is None:
        return "card não injetado (slot ausente no glade)"

    card = ControllerCard(compact=False)
    card.set_hexpand(True)
    card.set_valign(Gtk.Align.START)
    slot.attach(card, 0, 0, 1, 1)
    card.show_all()

    # Duas coisas que a aba Status faz em TEMPO DE EXECUÇÃO e que nenhuma
    # leitura do glade mostra: o botão da rota de som muda de casa para o
    # bloco "Alto-falante" do card, e o frame "Estado" some quando há um
    # controle só (CARD-ÚNICO-01).
    #
    # As duas regras são CHAMADAS aqui, e não repetidas: uma cópia delas neste
    # script seria um segundo dono das regras, e a foto passaria a mentir no
    # dia em que a `status_actions` mudasse — que é exatamente o defeito que
    # este script existe para não deixar acontecer.
    _aplicar_regras_de_runtime(builder, card)

    # O estado global com o vpad VIVO. Sem o bloco `rumble_ff.per_vpad` a
    # linha do PAINEL-DA-VERDADE-01 não teria o que afirmar e sairia da foto —
    # e ela é justamente a linha que responde à pergunta que abriu a leva
    # ("na hora de jogar, isso vai funcionar?"). Os números são os de um
    # controle no cabo com o gamepad virtual espelhando, que é o caso dela.
    estado = {
        **_ESTADO,
        "rumble_ff": {
            "per_vpad": [
                {
                    "player": 1,
                    "motion_streaming": True,
                    "motion_hz": 194.0,
                    "visto_ha_s": {"rumble": 0.4, "lightbar": 1.2},
                }
            ]
        },
    }
    card.update(_ENTRY, estado, LeituraMic(nivel=0.6, muted=False))
    # Um volume conhecido, para o bloco do alto-falante não sair no estado
    # "sem dado" — que é o menos informativo dos possíveis.
    card.update(
        {**_ENTRY, "audio": {"speaker": {"volume": 180, "muted": False}}},
        estado,
        LeituraMic(nivel=0.6, muted=False),
    )
    return "card do controle injetado na aba Status"


def main(destino: str | None = None) -> int:
    saida = Path(destino) if destino else DESTINO_DOC
    saida.mkdir(parents=True, exist_ok=True)

    builder = Gtk.Builder()
    builder.add_from_file(str(GLADE))
    notebook = builder.get_object("main_notebook")
    if notebook is None:
        print("ERRO: `main_notebook` não existe no glade", file=sys.stderr)
        return 1

    janela = Gtk.OffscreenWindow()
    pai = notebook.get_parent()
    if pai is not None:
        pai.remove(notebook)
    janela.add(notebook)
    janela.set_size_request(LARGURA, ALTURA)
    print(f"  {_aplicar_tema(janela)}")
    janela.show_all()
    _assentar()
    print(f"  {_injetar_card(builder)}")
    print(f"  {_injetar_modos_de_gatilho(builder)}")
    print(f"  {_montar_aba_inicio(builder)}")
    print(f"  {_montar_aba_no_jogo(builder)}")
    print(f"  {_montar_aba_perfis(builder)}")
    _assentar()

    total = notebook.get_n_pages()
    if total != len(NOMES):
        print(
            f"AVISO: o notebook tem {total} abas e este script conhece "
            f"{len(NOMES)} nomes. A documentação cita os nomes de "
            "`NOMES` — acrescente o da aba nova ali, ou a foto dela ficará "
            "sem lugar.",
            file=sys.stderr,
        )

    print(f"\n  {'aba':<22} {'arquivo':<26} tamanho")
    print("  " + "-" * 58)
    for indice in range(total):
        notebook.set_current_page(indice)
        _assentar()
        pagina = notebook.get_nth_page(indice)
        rotulo = notebook.get_tab_label_text(pagina) or f"aba {indice}"
        nome = NOMES[indice] if indice < len(NOMES) else f"aba_{indice:02d}"
        arquivo = saida / f"{nome}.png"
        janela.get_pixbuf().savev(str(arquivo), "png", [], [])
        kb = arquivo.stat().st_size // 1024
        print(f"  {rotulo:<22} {arquivo.name:<26} {kb:>4} KB")

    print(f"\n  {total} aba(s) em {saida}")
    if saida == DESTINO_DOC:
        print("  as imagens do README e de docs/usage/interface.md estão em dia.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
