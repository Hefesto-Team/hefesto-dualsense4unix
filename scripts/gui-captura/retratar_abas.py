#!/usr/bin/env python3
"""Retrata as ONZE abas da janela, com o card do controle vivo dentro.

É o script que a documentação e quem for trabalhar na interface usam —
pessoa ou assistente. Uma execução, nenhum
clique, nenhuma janela na frente: ele monta a interface numa janela offscreen
do tamanho da tela maximizada dela e salva um PNG por aba.

    scripts/gui-captura/retratar_abas.py                 # atualiza as imagens
                                                         # da documentação
    scripts/gui-captura/retratar_abas.py /tmp/olhar      # só olhar, sem tocar
                                                         # no repositório
    scripts/gui-captura/retratar_abas.py --mesa-cheia    # os QUATRO controles,
                                                         # em outra pasta

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
* alimentar o card com um payload copiado de uma sessão real **e não
  anonimizado**.

Se algum dia isto mudar, **a foto passa a precisar de revisão humana antes de
ir para o repositório** — e aí o script deixa de poder gravar direto em
`docs/`.

O MODO MESA CHEIA, E POR QUE ELE **NÃO** ENFRAQUECE NADA (14/08/2026)
---------------------------------------------------------------------

`--mesa-cheia` fotografa as mesmas dez abas com **quatro** controles em vez
dos dublês de dois. A promessa acima continua **literalmente** de pé: este
script **nunca fala com o daemon**, nem neste modo.

A diferença entre os dois modos é só a FONTE do dublê:

* modo padrão — dublês escritos à mão neste arquivo e na suíte;
* `--mesa-cheia` — `tests/fixtures/state_full_quatro_controles.json`, um
  arquivo **versionado**, lido do DISCO como qualquer outro fixture da suíte.

O fixture é payload real de 14/08, mas ele **já passou pelos portões de
`tests/`**, que são mais severos que a máscara de `docs/`: o
`test_anonimato_de_fixtures.py` é allowlist de PREFIXO e reprova até OUI de
fabricante de verdade, então cada `uniq` ali é `aabbcc0000NN`. E o payload
inteiro não tem **uma** string livre — nem nome de perfil, nem caminho, nem
título de janela; só enumerações (`usb`, `bt`, `uhid`, `sysfs`) e números. Isso
foi conferido, não suposto.

**Ler um arquivo do repositório não é falar com o daemon**, e a distinção é a
mesma que a nota da aba Perfis já faz para o disco: o que a garantia proíbe é
estado VIVO entrar na foto sem revisão. Aqui o dado entrou no repositório por
um commit, que é a revisão.

**O que continuaria inseguro:** trocar o fixture por uma captura nova sem
passar pelos portões de `tests/`, ou apontar o `--mesa-cheia` para
`docs/usage/assets/` — as fotos da mesa cheia têm pasta própria, fora das
imagens do README, e é assim que o modo continua ADICIONAL em vez de
substituir o que a documentação publica.

POR QUE AS ANIMAÇÕES DO GTK FICAM DESLIGADAS (14/08/2026)
----------------------------------------------------------

`readme_inicio.png` saía DIFERENTE a cada execução — ~3 mil pixels, delta 1 a
2, sempre nas bordas dos dois botões segmentados SELECIONADOS. O `git status`
ficava sujo depois de toda foto, e o `CLAUDE.md` manda rodar este script antes
de commitar: o ruído chegava a toda leva.

A causa não é ruído de gradiente, é **transição de CSS**: um `Gtk.RadioButton`
que acaba de ser marcado anima a mudança de estado (o tema do sistema traz
`transition` em `button:checked`), e a foto sai no meio da animação — em que
ponto dela depende do relógio, não do desenho. A aba Início é a primeira a ser
fotografada, e por isso era a única que não tinha tempo de assentar.

`gtk-enable-animations = False` faz o GTK pintar o estado FINAL na hora. As
outras nove fotos saem byte a byte idênticas com ou sem a chave (medido); a da
Início passa a sair sempre igual, e na cor que a transição estava tentando
alcançar — ou seja, mais fiel ao que ela vê, não menos.

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

import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

RAIZ = Path(os.environ.get("HEFESTO_RAIZ", Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("GDK_BACKEND", "x11")

# CONFIG-01 (21/08/2026): a cura do snap NÃO entrou aqui, e a razão é medida.
#
# O produto já se defende sozinho (`app/main._sanear_loaders_do_gdk_pixbuf`), e
# a tentação era importar essa função aqui, antes do `import gi`. Ela funciona —
# e cobra um preço que só apareceu na comparação das fotos: importar
# `app.main` arrasta `app.app`, que ABRE um GdkDisplay já no import, antes de
# este script aplicar o tema. Medido em 21/08 sob Xvfb, com o mesmo glade e o
# mesmo comando: `gtk-font-name` saiu `Fira Sans 12.25` sem o import e
# `Sans 12.25` com ele. As DEZ fotos da documentação mudaram inteiras, por uma
# razão que não tem nada a ver com o produto.
#
# A cura, então, fica FORA do script, na chamada:
#
#     GDK_PIXBUF_MODULE_FILE=/usr/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache \
#       scripts/gui-captura/retratar_abas.py
#
# Um instrumento que muda o que mede não serve de instrumento — e esta casa já
# pagou três medições falsas num dia por esquecer isso.

import gi  # noqa: E402 — depois de gi.require_version, obrigatoriamente

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402

GLADE = RAIZ / "src/hefesto_dualsense4unix/gui/main.glade"

#: O destino padrão é onde a documentação já aponta. Rodar sem argumento
#: ATUALIZA as imagens do README e do guia da interface — é o comportamento
#: pedido: uma execução e a documentação deixa de mentir.
DESTINO_DOC = RAIZ / "docs/usage/assets"

#: O destino do modo `--mesa-cheia`. FORA de `docs/usage/assets` de propósito,
#: e por duas razões:
#:
#: * essas dez imagens são as do README e do guia da interface, e a mesa cheia
#:   é MEDIÇÃO, não o retrato da interface que a documentação publica;
#: * `tests/unit/test_as_fotos_acompanham_a_versao.py` mede a PROCEDÊNCIA das
#:   fotos pelo último commit que tocou `docs/usage/assets` — commitar foto de
#:   mesa cheia lá dentro faria o portão dar as fotos do README por conferidas
#:   sem ninguém as ter regerado.
#:
#: A pasta segue a convenção das medições desta casa
#: (`docs/process/estudos/assets/`), mas SEM data no nome: as outras são
#: instantâneas de um dia, esta é um modo do instrumento, que se roda de novo
#: e sobrescreve.
DESTINO_MESA_CHEIA = RAIZ / "docs/process/estudos/assets/mesa-cheia"

#: O payload dos quatro controles. É arquivo VERSIONADO e anonimizado pelos
#: portões de `tests/` — ver a seção de privacidade lá em cima. Ler daqui é ler
#: o repositório, não o daemon.
FIXTURE_MESA_CHEIA = RAIZ / "tests/fixtures/state_full_quatro_controles.json"

#: Quantos controles a mesa cheia tem de mostrar. Não é número decorativo: é o
#: teto do co-op e o que a leva "mesa cheia" existe para provar. O modo RECUSA
#: rodar com menos — uma foto de mesa cheia com dois controles seria a mentira
#: mais cara possível aqui, porque parece certa.
CONTROLES_DA_MESA_CHEIA = 4

#: A tela dela maximizada. Não é número inventado: é a resolução em que as
#: bancadas de layout desta casa medem, e a mesma do `retrato_offscreen.py`.
LARGURA, ALTURA = 1920, 1080

#: Os nomes que a documentação referencia. A ORDEM é a das abas no notebook.
#: O `interface.md` cita os nomes; mudar um nome aqui quebra a documentação, então
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
    "readme_configuracoes",
)

#: Os nomes do modo mesa cheia. Prefixo próprio para que nenhuma delas possa
#: ser confundida com — nem sobrescrever — uma imagem do README, mesmo que
#: alguém aponte o modo para a pasta da documentação.
NOMES_MESA_CHEIA = tuple(
    nome.replace("readme_", "mesa_cheia_", 1) for nome in NOMES
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


#: Quanto tempo de RELÓGIO esperar por um redimensionamento da janela
#: offscreen. É a única espera de parede deste script, e ela é necessária:
#: `_assentar()` drena eventos PENDENTES, e a superfície offscreen só é
#: recriada no tique do frame clock, que é um temporizador — sem tempo passar,
#: `Gtk.events_pending()` devolve falso e o pixbuf sai no tamanho ANTIGO
#: (medido: 1080 px numa janela já pedida com 2055). Não reintroduz o ruído das
#: animações: aqui o que se espera é uma geometria, que converge e para.
ESPERA_DO_REDIMENSIONAMENTO_S = 1.0


def _esperar_o_redimensionamento(
    segundos: float = ESPERA_DO_REDIMENSIONAMENTO_S,
) -> None:
    """Drena o laço deixando o relógio andar, para o resize chegar."""
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(0.01)


def _desligar_animacoes() -> str:
    """Tira o relógio de dentro da foto (ver a seção do cabeçalho).

    Com as animações ligadas, um botão recém-marcado é fotografado NO MEIO da
    transição de CSS, e o ponto da transição depende de quanto tempo de parede
    passou — a mesma tela produzia PNGs diferentes a cada execução. Desligadas,
    o GTK pinta o estado final imediatamente.

    Falha aqui não impede a foto: sem `Gtk.Settings` (display incomum) o script
    volta ao comportamento antigo, que é ruidoso mas correto.
    """
    try:
        ajustes = Gtk.Settings.get_default()
        if ajustes is None:
            return "animações não desligadas (sem Gtk.Settings)"
        ajustes.set_property("gtk-enable-animations", False)
    except Exception as exc:
        return f"animações não desligadas ({exc})"
    return "animações desligadas (a foto não depende do relógio)"


def _estado_da_mesa_cheia() -> dict:
    """Lê o fixture VERSIONADO dos quatro controles.

    Isto é leitura de arquivo do repositório, e não conversa com o daemon — a
    seção de privacidade do cabeçalho explica por que a distinção é a que
    importa, e o `tests/unit/test_retrato_das_abas_nao_vaza_dado_real.py` a
    trava dos dois lados.

    A conferência de que há QUATRO controles conectados é dura de propósito: o
    modo existe para provar a mesa cheia, e um fixture truncado produziria uma
    foto que parece certa e não é.
    """
    if not FIXTURE_MESA_CHEIA.is_file():
        raise SystemExit(
            f"ERRO: {FIXTURE_MESA_CHEIA} não existe. O modo --mesa-cheia "
            "depende desse arquivo versionado; ele NÃO pergunta ao daemon."
        )
    estado = json.loads(FIXTURE_MESA_CHEIA.read_text(encoding="utf-8"))
    controles = [
        c
        for c in estado.get("controllers", [])
        if isinstance(c, dict) and c.get("connected")
    ]
    if len(controles) < CONTROLES_DA_MESA_CHEIA:
        raise SystemExit(
            f"ERRO: {FIXTURE_MESA_CHEIA.name} tem {len(controles)} controle(s) "
            f"conectado(s), e a mesa cheia são {CONTROLES_DA_MESA_CHEIA}. "
            "Uma foto de mesa cheia com menos que isso é pior que nenhuma: "
            "ela parece certa."
        )
    return estado


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


def _montar_aba_inicio(builder, estado=None) -> str:  # type: ignore[no-untyped-def]
    """Monta a aba Início e a preenche com um estado plausível do daemon.

    COOP-SEM-INTERRUPTOR-01 (06/08/2026) — a cura que a `PEDIDOS-DELA-01`
    nomeou como pré-requisito da prova de tela. A aba Início é **100% código**
    (`install_home_tab`): o glade só reserva o `tab_home_box`. Enquanto sobrou
    ali um frame de glade — a seção "Jogar acompanhada" — a foto documentava
    aquele frame e mais nada, e passava por retrato da aba. Com o frame fora, a
    foto virou um retângulo vazio: honesta e inútil.

    Mesmo desenho do card do Status e dos modos de gatilho: host mínimo com um
    `_get` que resolve ids do builder, nada de IPC e nada de tique. O
    `_render_home` recebe um `state_full` de mesa — dois controles, dois
    jogadores — porque é ele que a aba existe para responder.

    Com `estado`, o dublê de dois cede lugar ao que o chamador trouxer (o modo
    `--mesa-cheia` traz o fixture dos quatro). Sem ele, nada muda: o padrão
    continua produzindo o MESMO pixel de sempre, que é o que a documentação
    publica.
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

    if estado is None:
        estado = {
            "connected": True,
            "native_mode": False,
            "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
            "coop": {"enabled": True, "players": 2},
            "controllers": [
                _controle(0, 1, primario=True),
                _controle(1, 2, primario=False),
            ],
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
    quantos = len(estado.get("controllers", []))
    jogadores = (estado.get("coop") or {}).get("players", quantos)
    return f"aba Início montada ({quantos} controles = {jogadores} jogadores)"


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


def _montar_aba_no_jogo(builder, estado=None) -> str:  # type: ignore[no-untyped-def]
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

    if estado is None:
        estado = _NO_JOGO_ESTADO
        recado = "2 jogadores, as três situações na tela"
    else:
        vpads = (estado.get("rumble_ff") or {}).get("per_vpad") or []
        recado = f"{len(vpads)} espelhos, do fixture da mesa cheia"
    try:
        host = _Host()
        host.install_no_jogo_tab()
        host._sync_paineis_no_jogo(dict(estado))
    except Exception as exc:
        return f'aba "No jogo" não montada ({exc})'
    caixa = builder.get_object("tab_no_jogo_box")
    if caixa is not None:
        caixa.show_all()
    return f'aba "No jogo" montada ({recado})'


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


def _montar_aba_configuracoes(builder) -> str:  # type: ignore[no-untyped-def]
    """Monta a aba Configurações — o glade dela é só o container vazio.

    CONFIG-01 (21/08/2026). Mesmo defeito que a PERFIS-NA-FOTO-01 pagou: o
    conteúdo desta aba é montado em CÓDIGO (`install_config_tab`), então uma
    foto do glade cru sairia com a página em branco — e a documentação passaria
    a afirmar que a aba nova não tem nada dentro.

    O método é o de PRODUÇÃO, e não uma cópia da montagem. Aqui isso é barato:
    o `install_config_tab` não fala com o daemon, não lê disco e não depende de
    dado nenhum da máquina, então o host mínimo é só o `builder` — não há o que
    desviar, ao contrário da aba Perfis.
    """
    try:
        from hefesto_dualsense4unix.app.actions.config_actions import (
            ABA_CONFIG,
            SECOES,
            ConfigActionsMixin,
        )
    except Exception as exc:
        return f"aba Configurações não montada ({exc})"

    class _Host(ConfigActionsMixin):  # type: ignore[misc, name-defined]
        def __init__(self) -> None:
            self.builder = builder

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

    try:
        _Host().install_config_tab()
    except Exception as exc:
        return f"aba Configurações não montada ({exc})"

    caixa = builder.get_object(ABA_CONFIG)
    if caixa is not None:
        caixa.show_all()
    return f"aba Configurações montada ({len(SECOES)} seções, ainda vazias)"


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
    #
    # A chave vai na RAIZ do entry, e não dentro de `audio`. Até 16/08/2026 ela
    # estava em `audio`, onde o `speaker_do_entry` não olha (ele aceita a raiz
    # ou `inputs`) — e a foto vinha saindo com o bloco em "Alto-falante" seco,
    # exatamente o estado que esta linha existe para evitar. Defeito do
    # instrumento, não do produto, e o sintoma era a AUSÊNCIA de dado na foto.
    #
    # 255 é o volume que o produto passou a pôr sozinho em todo controle
    # (decisão dela: *"setar o som sempre em todos os controles no 100%"*), e é
    # o que a foto tem de mostrar — o padrão, não um número de exemplo.
    card.update(
        {**_ENTRY, "speaker": {"volume": 255, "muted": False}},
        estado,
        LeituraMic(nivel=0.6, muted=False),
    )
    # SOM-ACORDADO-01: o outro estado que a aba passou a mostrar. Na foto ele
    # vem CRAVADO, e não lido do PipeWire desta máquina: este script nunca fala
    # com o sistema vivo (ver "PRIVACIDADE", no cabeçalho), e um retrato que
    # mudasse conforme o áudio de quem o roda não seria documentação.
    definir_canal = getattr(card, "definir_estado_do_canal", None)
    if definir_canal is not None:
        from hefesto_dualsense4unix.app.audio_saida import CANAL_ACORDADO

        definir_canal(CANAL_ACORDADO, regra_instalada=True)
    return "card do controle injetado na aba Status"


def _host_da_aba_status(builder):  # type: ignore[no-untyped-def]
    """O host mínimo da aba Status, com os DOIS desvios que a foto exige.

    Sai daqui e não de dentro de cada função porque duas fotos precisam dele —
    a dos cards e a do cabeçalho —, e um segundo host copiado seria a chance de
    um deles perder um desvio. O que os desvios protegem está escrito no
    `_injetar_cards_da_mesa_cheia`.
    """
    from hefesto_dualsense4unix.app.actions.status_actions import (
        StatusActionsMixin,
    )

    class _Host(StatusActionsMixin):  # type: ignore[misc]
        def __init__(self) -> None:
            self.builder = builder
            self._status_cards = {}
            self._status_card_keys = []

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            if nome == "main_notebook":
                return None
            return self.builder.get_object(nome)

        def _status_toast(self, _contexto: str, _msg: str) -> None:
            return None

        def _maybe_fetch_externals(self) -> None:  # type: ignore[override]
            # O de produção pergunta ao daemon VIVO. Aqui, nunca.
            return None

    return _Host()


def _injetar_cards_da_mesa_cheia(builder, estado) -> str:  # type: ignore[no-untyped-def]
    """Põe os QUATRO cards na aba Status, pelo caminho de PRODUÇÃO.

    O `_injetar_card` acima monta UM card à mão porque o dublê da suíte é uma
    entrada de controle, não um `state_full`. Aqui há um `state_full` inteiro —
    então quem monta é `_sync_status_cards`, o mesmo método que a janela dela
    roda a cada tique. Repetir a montagem aqui seria um segundo dono do
    desenho, e a foto passaria a mentir no dia em que a `status_actions`
    mudasse.

    Ganha-se, de graça, tudo o que só aparece com 2+ controles e que NENHUMA
    foto desta casa já mostrou: o empilhamento de um card por linha
    (EMPILHA-01), o frame "Estado" que volta à tela (CARD-ÚNICO-01) e a
    diferença entre o `player_slot` — que manda na cor — e o `player` do co-op.

    Nada de IPC, nada de tique: `_mic_monitor` fica `None` (é atributo de
    classe), e sem monitor o `_sync_status_cards` não consulta nem o PipeWire.

    O QUE É DESVIADO, E POR QUÊ
    ---------------------------

    Quem preenche a aba inteira — a linha "Conectado (4 controles)", a fita de
    chips, a faixa de números, os banners — é o `_render_slow_state`, o tique
    de 2 Hz da janela dela. Ele é chamado aqui inteiro, e não copiado, pela
    razão de sempre: uma cópia seria um segundo dono do desenho. Duas coisas
    dentro dele são desviadas, no mesmo molde do que a aba Perfis já faz:

    * ``_maybe_fetch_externals`` **FALA COM O DAEMON VIVO**
      (`controller.list {external: true}`). É no-op no host. Sem isto, o
      script quebraria a garantia de privacidade do cabeçalho no primeiro
      `--mesa-cheia` — e, pior, calado: o inventário de externos volta por
      callback, depois de a foto já ter sido salva;
    * ``_get("main_notebook")`` devolve `None`, pelo mesmo motivo que o host
      da aba "No jogo" já documenta: com o notebook de verdade na mão, o gate
      de EXISTÊNCIA da aba poderia TIRÁ-LA da tira, e a foto dela sumiria.
    """
    try:
        host = _host_da_aba_status(builder)
        host._init_controller_target_combo()
        host._render_slow_state(estado)
    except Exception as exc:
        return f"cards não injetados ({exc}) — a aba Status sai vazia"

    quantos = len(host._status_cards)
    if quantos < CONTROLES_DA_MESA_CHEIA:
        return (
            f"ATENÇÃO: só {quantos} card(s) na aba Status — a mesa cheia "
            f"são {CONTROLES_DA_MESA_CHEIA}"
        )
    return f"{quantos} cards de controle injetados na aba Status"


#: A aba que a mesa cheia estoura, e o nome da foto que mostra o estouro
#: inteiro. É a Status: quatro cards empilhados (EMPILHA-01, decisão dela de
#: 02/08) pedem mais que o dobro da altura da tela dela.
ABA_QUE_ESTOURA = "mesa_cheia_status"

#: Teto da foto esticada, em px. Não é medo do arquivo grande: é o sinal de que
#: alguma coisa cresceu sem limite e a foto viraria uma tira ilegível.
ALTURA_MAXIMA_ESTICADA = 4000

#: A foto do cabeçalho — ver `_fotografar_o_cabecalho`. Ela existe só no modo
#: mesa cheia porque é lá que a fita do alvo tem o que mostrar: com um controle
#: só, o seletor não aparece.
NOME_DO_CABECALHO = "mesa_cheia_cabecalho"


def _fotografar_a_aba_inteira(janela, notebook, saida, indice, nome) -> str:  # type: ignore[no-untyped-def]
    """Fotografa UMA aba na altura que ela PEDE, não na que ela recebe.

    A foto de 1920x1080 é a verdade sobre o que ela vê — e é por isso que a da
    mesa cheia mostra dois cards e meio. Esta aqui responde a outra pergunta,
    que a leva também faz: *o que existe abaixo da dobra?*

    As duas juntas são a medida do problema da entrega 2.13 (empilhar os
    cards): a altura pedida ao lado da altura disponível, com a mesma régua.
    """
    notebook.set_current_page(indice)
    _assentar()
    _, natural = notebook.get_preferred_height()
    altura = min(max(natural, ALTURA), ALTURA_MAXIMA_ESTICADA)
    janela.set_size_request(LARGURA, altura)
    _esperar_o_redimensionamento()
    arquivo = saida / f"{nome}_inteira.png"
    pixbuf = janela.get_pixbuf()
    pixbuf.savev(str(arquivo), "png", [], [])
    saiu = pixbuf.get_height()
    janela.set_size_request(LARGURA, ALTURA)
    _esperar_o_redimensionamento()
    if saiu != altura:
        return (
            f"  AVISO: {arquivo.name} saiu com {saiu} px e não com {altura} — "
            "o redimensionamento não chegou a tempo, e a foto esticada está "
            "cortada. Aumente ESPERA_DO_REDIMENSIONAMENTO_S."
        )
    return (
        f"  {arquivo.name}: a aba pede {natural} px de altura e recebe "
        f"{ALTURA} — a foto esticada mostra o que fica abaixo da dobra"
    )


def _fotografar_o_cabecalho(builder, estado, saida, nome) -> str:  # type: ignore[no-untyped-def]
    """Fotografa o `header_bar` — a fita do alvo, que NENHUMA foto mostrava.

    Achado de 14/08/2026, e ele é do tipo que só aparece quando alguém procura:
    o `main` deste script arranca o `main_notebook` do `root_box` e fotografa a
    janela pelo NOTEBOOK. O `header_bar` fica de fora das dez fotos por
    construção do recorte — não porque não esteja na tela dela.

    Isso importa porque a fita "Ajustes vão para: …" e o selo "Editando: …"
    moram lá, e são o assunto de duas entregas da leva da mesa cheia. A
    PROVA-DE-TELA-01 exige foto antes e depois; sem esta função, essa foto não
    existia.

    A ORDEM AQUI É A CURA DE UMA MENTIRA POSSÍVEL
    ---------------------------------------------

    `show_all()` acende TUDO — inclusive os avisos que o produto esconde (o
    badge de vibração travada, o selo de edição, a faixa de números). Uma foto
    tirada logo depois dele mostraria uma tela que nunca existe.

    Por isso o `_render_slow_state` roda DE NOVO, depois do `show_all()`: quem
    decide o que fica escondido é a produção, não este script.
    """
    cabecalho = builder.get_object("header_bar")
    if cabecalho is None:
        return "  cabeçalho não fotografado (`header_bar` ausente no glade)"
    try:
        pai = cabecalho.get_parent()
        if pai is not None:
            pai.remove(cabecalho)
        janela = Gtk.OffscreenWindow()
        janela.add(cabecalho)
        janela.set_size_request(LARGURA, -1)
        _aplicar_tema(janela)
        janela.show_all()
        host = _host_da_aba_status(builder)
        # `_render_online` é quem escreve a linha da direita ("Conectado (4
        # controles) · USB + USB + BT + BT"). Ela NÃO sai do `_render_slow_state`
        # — na janela dela quem a escreve é a máquina de reconexão, a 0,5 Hz —,
        # e sem esta chamada a foto sairia com o default do glade, "Controle
        # Desconectado" em vermelho, ao lado de quatro chips de controle.
        host._render_online(estado)
        host._render_slow_state(estado)
        _esperar_o_redimensionamento()
        arquivo = saida / f"{nome}.png"
        pixbuf = janela.get_pixbuf()
        pixbuf.savev(str(arquivo), "png", [], [])
    except Exception as exc:
        return f"  cabeçalho não fotografado ({exc})"
    return (
        f"  {arquivo.name}: o cabeçalho com {pixbuf.get_height()} px de "
        "altura — a fita do alvo, que não cabe em nenhuma foto de aba"
    )


def main(destino: str | None = None, *, mesa_cheia: bool = False) -> int:
    padrao = DESTINO_MESA_CHEIA if mesa_cheia else DESTINO_DOC
    saida = Path(destino) if destino else padrao
    nomes = NOMES_MESA_CHEIA if mesa_cheia else NOMES
    # O fixture é lido ANTES de o GTK montar coisa alguma: se ele não estiver
    # onde deveria, ninguém perde tempo montando uma janela para descobrir isso
    # dez segundos depois.
    estado_da_mesa = _estado_da_mesa_cheia() if mesa_cheia else None
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
    print(f"  {_desligar_animacoes()}")
    print(f"  {_aplicar_tema(janela)}")
    janela.show_all()
    _assentar()
    if estado_da_mesa is None:
        print(f"  {_injetar_card(builder)}")
    else:
        print(f"  fixture lido: {FIXTURE_MESA_CHEIA.relative_to(RAIZ)}")
        print(f"  {_injetar_cards_da_mesa_cheia(builder, estado_da_mesa)}")
    print(f"  {_injetar_modos_de_gatilho(builder)}")
    print(f"  {_montar_aba_inicio(builder, estado_da_mesa)}")
    print(f"  {_montar_aba_no_jogo(builder, estado_da_mesa)}")
    print(f"  {_montar_aba_perfis(builder)}")
    print(f"  {_montar_aba_configuracoes(builder)}")
    _assentar()

    total = notebook.get_n_pages()
    if total != len(nomes):
        print(
            f"AVISO: o notebook tem {total} abas e este script conhece "
            f"{len(nomes)} nomes. A documentação cita os nomes de "
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
        nome = nomes[indice] if indice < len(nomes) else f"aba_{indice:02d}"
        arquivo = saida / f"{nome}.png"
        janela.get_pixbuf().savev(str(arquivo), "png", [], [])
        kb = arquivo.stat().st_size // 1024
        print(f"  {rotulo:<22} {arquivo.name:<26} {kb:>4} KB")

    if mesa_cheia and ABA_QUE_ESTOURA in nomes:
        print(
            _fotografar_a_aba_inteira(
                janela,
                notebook,
                saida,
                nomes.index(ABA_QUE_ESTOURA),
                ABA_QUE_ESTOURA,
            )
        )
    if mesa_cheia and estado_da_mesa is not None:
        print(
            _fotografar_o_cabecalho(
                builder, estado_da_mesa, saida, NOME_DO_CABECALHO
            )
        )

    print(f"\n  {total} aba(s) em {saida}")
    if saida == DESTINO_DOC:
        print(f"  {_gravar_prova_da_foto(saida)}")
        print("  as imagens do README e de docs/usage/interface.md estão em dia.")
    if mesa_cheia:
        print(
            "  mesa cheia: quatro controles do fixture versionado. Estas NÃO "
            "são as imagens do README."
        )
    return 0


#: O que sai quando alguém erra a linha de comando. Em português, como o resto.
USO = (
    "uso: retratar_abas.py [DESTINO] [--mesa-cheia]\n"
    "\n"
    "  sem argumento   atualiza as imagens da documentação\n"
    f"                  ({DESTINO_DOC.relative_to(RAIZ)})\n"
    "  DESTINO         grava nessa pasta e não toca no repositório\n"
    "  --mesa-cheia    fotografa com os QUATRO controles do fixture\n"
    f"                  versionado; destino padrão "
    f"{DESTINO_MESA_CHEIA.relative_to(RAIZ)}\n"
)


#: O nome do recibo. Vive JUNTO das fotos de propósito: é o commit dele que faz
#: `docs/usage/assets` avançar quando nenhum pixel se move.
NOME_DA_PROVA = "PROVA-DA-FOTO.txt"


def _gravar_prova_da_foto(saida: Path) -> str:
    """Grava o recibo do ensaio: quando rodou, contra qual tela, e o que saiu.

    FOTO-QUE-NAO-MOVE-PIXEL-01 (19/08/2026). O portão
    `test_as_fotos_nao_ficam_atras_do_codigo_da_tela` compara TOPOLOGIA: o
    commit que tocou `src/…/app` ou `src/…/gui` tem de ser ancestral do commit
    que tocou `docs/usage/assets`. O critério está certo — data mentiria — mas
    tem um ponto cego: uma mudança de tela que não move pixel nenhum (uma frase
    de aviso, um comentário, um caminho de IPC) faz as fotos saírem **byte a
    byte idênticas**. O `git` não registra nada, o commit das fotos não avança,
    e o portão fica vermelho para sempre — exigindo, na prática, um commit
    falso. Aconteceu na leva NATIVO-RUMBLE-01.

    O recibo resolve dizendo a verdade em vez de fingir: ele muda porque a data
    e o commit da tela mudaram, então o commit dele É a prova de que o ensaio
    rodou. E as somas dizem o que saiu — se um PNG for editado à mão depois,
    a soma não bate mais.
    """

    pngs = sorted(q for q in saida.glob("*.png") if q.is_file())
    linhas = [
        "# Recibo do ensaio de fotos — gerado por scripts/gui-captura/retratar_abas.py",
        "#",
        "# NÃO edite à mão. Rode o script; ele reescreve este arquivo.",
        "# Existe porque uma mudança de tela que não move pixel deixa as fotos",
        "# idênticas, e sem este recibo o portão das fotos ficaria vermelho para",
        "# sempre. Ver FOTO-QUE-NAO-MOVE-PIXEL-01 no próprio script.",
        "",
        f"ensaio: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"abas:   {len(pngs)}",
        "",
        "# soma sha256 de cada foto, em ordem alfabética",
    ]
    for q in pngs:
        linhas.append(f"{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}")
    (saida / NOME_DA_PROVA).write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return f"recibo do ensaio em {NOME_DA_PROVA} ({len(pngs)} soma[s])"


def _ler_argumentos(argv: list[str]) -> tuple[str | None, bool]:
    """Lê `[DESTINO] [--mesa-cheia]`, em qualquer ordem.

    À mão e não com `argparse` de propósito: o `argparse` imprime "usage:" e
    "positional arguments" em inglês, e esta casa escreve em português — há
    portão que reprova.
    """
    destino: str | None = None
    mesa_cheia = False
    for arg in argv:
        if arg == "--mesa-cheia":
            mesa_cheia = True
        elif arg.startswith("-"):
            raise SystemExit(f"argumento desconhecido: {arg}\n\n{USO}")
        elif destino is None:
            destino = arg
        else:
            raise SystemExit(f"destino demais: {arg}\n\n{USO}")
    return destino, mesa_cheia


if __name__ == "__main__":
    _destino, _mesa_cheia = _ler_argumentos(sys.argv[1:])
    raise SystemExit(main(_destino, mesa_cheia=_mesa_cheia))
