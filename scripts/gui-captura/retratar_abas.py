#!/usr/bin/env python3
"""Retrata as ONZE abas da JANELA GTK, com o card do controle vivo dentro.

ELE NÃO É O RETRATISTA DO PRODUTO DE HOJE — 05/09/2026
-------------------------------------------------------

A janela GTK tem onze abas; o que abre é a interface HTML, com DEZ páginas.
Quem as fotografa é `src/hefesto_dualsense4unix/interface/olhar.py --todas
--publicado --doc`, que grava as `docs/usage/assets/aba-NN-*.png` do README e
do `AS-DEZ-ABAS`. Este arquivo continua sendo o retratista da JANELA, e as
`readme_*.png` que ele produz continuam servindo ao `docs/usage/interface.md`
enquanto a janela viver.

A separação é de dependência, não de gosto: este importa GTK na primeira linha,
e o outro precisa só do Chrome — juntar os dois obrigaria toda máquina que
fotografa HTML a ter PyGObject.

Uma execução, nenhum clique, nenhuma janela na frente: ele monta a interface
numa janela offscreen do tamanho da tela maximizada dela e salva um PNG por
aba.

    scripts/gui-captura/retratar_abas.py                 # atualiza as imagens
                                                         # da documentação
    scripts/gui-captura/retratar_abas.py /tmp/olhar      # só olhar, sem tocar
                                                         # no repositório
    scripts/gui-captura/retratar_abas.py --mesa-cheia    # os QUATRO controles,
                                                         # em outra pasta
    scripts/gui-captura/retratar_abas.py --cinco         # os CINCO — a mesa
                                                         # real desta casa

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

`--mesa-cheia` fotografa as mesmas abas com **quatro** controles em vez dos
dublês de dois, e `--cinco` faz o mesmo com **cinco** — a mesa real desta casa,
que é o pior caso de largura e o que o item 15 do `TODO-INTEGRACAO.md` da leva
da aba Configurações pede. A promessa acima continua **literalmente** de pé: este
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

import contextlib
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

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

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

#: O payload dos CINCO controles — a mesa real desta casa.
#:
#: Pedido do item 15 do `TODO-INTEGRACAO.md` da leva da aba Configurações, e a
#: razão é de LARGURA: *"a mesa real desta casa é de cinco; a captura de quatro
#: não mostra o pior caso"*. A seção "Os controles" da aba Configurações e a
#: pilha de cards da Status são as duas que estouram primeiro, e é com cinco
#: que elas estouram.
#:
#: Nasceu do fixture dos quatro (mesmo formato, mesmo dono), com um quinto
#: controle no rádio: `player 5`, `player_slot 5` — a extensão R-25 da paleta,
#: laranja — e bateria em 45% de propósito, para a foto mostrar também um card
#: que não está cheio. O MAC segue a máscara da casa (`aabbcc0000…`) e passa
#: pelo `test_anonimato_de_fixtures.py` como os outros quatro.
FIXTURE_MESA_DE_CINCO = RAIZ / "tests/fixtures/state_full_cinco_controles.json"

#: Onde as fotos da mesa de cinco caem. Pasta PRÓPRIA, pelas mesmas duas razões
#: da mesa cheia: não são as imagens do README, e não podem fazer o portão da
#: procedência dar as do README por conferidas.
DESTINO_MESA_DE_CINCO = RAIZ / "docs/process/estudos/assets/mesa-de-cinco"

#: Quantos controles a mesa de cinco tem de mostrar. Mesma dureza da mesa
#: cheia, e pelo mesmo motivo: uma foto de cinco com quatro parece certa.
CONTROLES_DA_MESA_DE_CINCO = 5

#: Quantos controles a mesa cheia tem de mostrar. Não é número decorativo: é o
#: teto do co-op e o que a leva "mesa cheia" existe para provar. O modo RECUSA
#: rodar com menos — uma foto de mesa cheia com dois controles seria a mentira
#: mais cara possível aqui, porque parece certa.
CONTROLES_DA_MESA_CHEIA = 4

#: A tela dela maximizada. Não é número inventado: é a resolução em que as
#: bancadas de layout desta casa medem, e a mesma do `retrato_offscreen.py`.
LARGURA, ALTURA = 1920, 1080

#: Os nomes que a documentação referencia. A ORDEM é a das abas no notebook.  (noqa-acento: verbo referenciar, 3.ª pessoa — a documentação REFERENCIA os nomes; o substantivo "referência" falsificaria a frase)
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

#: Os nomes do modo de cinco. Prefixo próprio pela mesma razão do de quatro —
#: nenhuma das duas medições pode sobrescrever a outra nem uma foto do README.
NOMES_MESA_DE_CINCO = tuple(
    nome.replace("readme_", "mesa_de_cinco_", 1) for nome in NOMES
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


def _estado_da_mesa_cheia(fixture=None, quantos=None) -> dict:  # type: ignore[no-untyped-def]
    """Lê o fixture VERSIONADO da mesa — quatro controles, ou cinco.

    Os dois argumentos nascem `None` e caem nas constantes do módulo de
    propósito: `tests/unit/test_a_mesa_cheia_na_foto.py` troca
    `FIXTURE_MESA_CHEIA` no módulo para provar que um fixture truncado é
    RECUSADO, e uma leitura congelada na assinatura mataria essa mordida.

    Isto é leitura de arquivo do repositório, e não conversa com o daemon — a
    seção de privacidade do cabeçalho explica por que a distinção é a que
    importa, e o `tests/unit/test_retrato_das_abas_nao_vaza_dado_real.py` a
    trava dos dois lados.

    A conferência de que há QUATRO controles conectados é dura de propósito: o
    modo existe para provar a mesa cheia, e um fixture truncado produziria uma
    foto que parece certa e não é.
    """
    fixture = FIXTURE_MESA_CHEIA if fixture is None else fixture
    quantos = CONTROLES_DA_MESA_CHEIA if quantos is None else quantos
    if not fixture.is_file():
        raise SystemExit(
            f"ERRO: {fixture} não existe. O modo depende desse arquivo "
            "versionado; ele NÃO pergunta ao daemon."
        )
    estado = json.loads(fixture.read_text(encoding="utf-8"))
    controles = [
        c
        for c in estado.get("controllers", [])
        if isinstance(c, dict) and c.get("connected")
    ]
    if len(controles) < quantos:
        raise SystemExit(
            f"ERRO: {fixture.name} tem {len(controles)} controle(s) "
            f"conectado(s), e a mesa são {quantos}. "
            "Uma foto de mesa cheia com menos que isso é pior que nenhuma: "
            "ela parece certa."
        )
    return estado


#: A classe de estilo da janela do produto, a única parte do tema que é POR
#: JANELA — o resto (`add_provider_for_screen`, a fonte, a variante escura)
#: vale para a tela inteira e já foi aplicado pela primeira chamada.
CLASSE_DA_JANELA = "hefesto-dualsense4unix-window"


def _aplicar_tema(janela) -> str:  # type: ignore[no-untyped-def]
    """Aplica o tema do produto — UMA VEZ POR EXECUÇÃO.

    `apply_theme` NÃO é idempotente, e isso não é defeito dele: em produção ele
    roda uma vez (`app/app.py:286`). Ele lê `gtk-font-name` do `Gtk.Settings`,
    soma o delta de acessibilidade e grava de volta — então a segunda chamada
    soma o delta sobre o nome JÁ somado, a terceira sobre o da segunda, e a
    fonte da tela inteira cresce a cada janela nova.

    MEDIDO em 24/08/2026, fotografando o `header_bar` cinco vezes seguidas
    (cada foto criava uma `OffscreenWindow` e chamava esta função): o cabeçalho
    saía com 117, 119, 122, 126 e 130 px de altura, com o MESMO conteúdo e os
    MESMOS 17 widgets visíveis. A foto do cabeçalho vinha, desde 14/08/2026,
    com a tipografia um degrau maior que as fotos de aba — e com duas fotos de
    cabeçalho a segunda sairia maior que a primeira, sugerindo que esmaecer a
    fita muda o tamanho do texto. Não muda.

    Por isso a segunda chamada em diante só marca a janela com a classe de
    estilo, que é a única parte do tema que é por janela.
    """
    try:
        from hefesto_dualsense4unix.app.theme import apply_theme
    except Exception as exc:  # tema indisponível não impede a foto
        return f"tema indisponível ({exc})"
    global _tema_ja_aplicado
    if _tema_ja_aplicado:
        with contextlib.suppress(Exception):
            janela.get_style_context().add_class(CLASSE_DA_JANELA)
        return "tema já aplicado nesta execução (só a classe da janela)"
    for tentativa in (lambda: apply_theme(janela), lambda: apply_theme()):
        try:
            tentativa()
            _tema_ja_aplicado = True
            return "tema aplicado"
        except TypeError:
            continue
        except Exception as exc:
            return f"tema falhou ({exc})"
    return "tema não aplicado"


#: Ver `_aplicar_tema`: a segunda chamada em diante inflaria a fonte da tela.
_tema_ja_aplicado = False


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


def _controle_padrao(indice: int, jogador: int, *, primario: bool) -> dict:  # type: ignore[type-arg]
    """Um dos dois controles do dublê padrão — um no cabo, um no rádio.

    O `uniq` segue a máscara desta casa (octetos 4 e 5 zerados; há portão que
    reprova MAC real em arquivo versionado) e existe por uma razão de tela: a
    fita "Ajustes vão para:" do cabeçalho só ganha um chip por controle quando
    ele tem endereço — sem `uniq`, a foto do cabeçalho sairia com a legenda e
    nenhum botão, que é o retrato de uma janela que não existe.
    """
    return {
        "index": indice,
        "connected": True,
        "transport": "usb" if primario else "bt",
        "is_primary": primario,
        "player": jogador,
        "player_slot": jogador,
        "battery_pct": 87 if primario else 64,
        "uniq": f"aa:bb:cc:00:00:0{indice + 1}",
    }


#: A mesa que dez das onze fotos da documentação retratam: DOIS controles, um
#: no cabo e um no rádio, dois jogadores.
#:
#: Mora aqui, e não dentro do `_montar_aba_inicio`, desde 24/08/2026: a foto do
#: cabeçalho passou a existir no modo padrão, e ela precisa da MESMA mesa que
#: as abas mostram. Duas cópias do dublê seriam duas mesas — a fita do
#: cabeçalho podendo dizer "2 controles" ao lado de uma aba Início com outros
#: dois, e ninguém percebendo.
ESTADO_PADRAO_DE_DOIS: dict = {  # type: ignore[type-arg]
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "coop": {"enabled": True, "players": 2},
    "controllers": [
        _controle_padrao(0, 1, primario=True),
        _controle_padrao(1, 2, primario=False),
    ],
    "active_profile": "coop_local",
}


#: Onde caem as fotos dos estados da aba Início que nenhuma imagem mostrava.
#:
#: Pasta PRÓPRIA, fora de `docs/usage/assets/`, pelas MESMAS duas razões da
#: mesa cheia: estas são MEDIÇÃO, não o retrato que a documentação publica, e
#: commitá-las junto das do README faria o portão da procedência
#: (`test_as_fotos_acompanham_a_versao.py`) dar as do README por conferidas sem
#: ninguém as ter regerado.
DESTINO_ESTADOS_DO_INICIO = RAIZ / "docs/process/estudos/assets/estados-do-inicio"

#: O inventário de externos, VERSIONADO e anonimizado pelos portões de
#: `tests/`. Lido do disco em vez de escrito à mão aqui pela mesma razão do
#: fixture da mesa cheia: um endereço digitado neste script é um endereço que
#: nenhum portão de anonimato de `tests/` confere.
FIXTURE_DOS_EXTERNOS = RAIZ / "tests/fixtures/inventario_externos.json"


def _um_externo_versionado() -> dict:  # type: ignore[type-arg]
    """O primeiro externo do inventário versionado; ``{}`` se ele sumir.

    Ler é ler o repositório, não falar com o daemon — a mesma distinção que a
    seção de privacidade do cabeçalho faz para o fixture da mesa cheia.
    """
    if not FIXTURE_DOS_EXTERNOS.is_file():
        return {}
    with contextlib.suppress(Exception):
        bruto = json.loads(FIXTURE_DOS_EXTERNOS.read_text(encoding="utf-8"))
        externos = bruto.get("external") if isinstance(bruto, dict) else None
        if isinstance(externos, list) and externos:
            primeiro = externos[0]
            if isinstance(primeiro, dict):
                return dict(primeiro)
    return {}


def _mesa_com(**delta) -> dict:  # type: ignore[no-untyped-def,type-arg]
    """A mesa padrão de dois com as chaves de `delta` por cima. Cópia rasa.

    Cópia, e nunca mutação: `ESTADO_PADRAO_DE_DOIS` é a mesa que DEZ fotos da
    documentação retratam, e um estado que a alterasse no lugar mudaria as
    outras fotos da mesma execução — o defeito de instrumento mais difícil de
    ver, porque a foto continua saindo.
    """
    estado = dict(ESTADO_PADRAO_DE_DOIS)
    estado["controllers"] = [dict(c) for c in ESTADO_PADRAO_DE_DOIS["controllers"]]
    estado["gamepad_emulation"] = dict(ESTADO_PADRAO_DE_DOIS["gamepad_emulation"])
    estado["coop"] = dict(ESTADO_PADRAO_DE_DOIS["coop"])
    estado.update(delta)
    return estado


#: OS CINCO ESTADOS QUE NENHUMA FOTO DESTA CASA JAMAIS MOSTROU (25/08/2026)
#: ------------------------------------------------------------------------
#:
#: I10 da sprint INÍCIO NÃO MENTE-01. Medido no §2.4 dela: o dublê da foto não
#: traz `paused`, nem `primary_grab_state`, nem `external`, nem `steam_input`,
#: nem `draft` — e são justamente esses cinco que as outras tarefas da onda
#: mudam. Uma prova de tela feita só sobre o caminho feliz é prova sobre
#: ficção.
#:
#: Cada valor é `(delta do state_full, máscara do rascunho, o que a foto passa
#: a mostrar)`. A máscara do rascunho é o que alimenta `draft.source_mode` —
#: a fonte 2 de `_mascara_escolhida_por_ela`, e a única forma de a linha de
#: divergência aparecer numa foto.
ESTADOS_DO_INICIO: dict[str, tuple[dict, str | None, str]] = {  # type: ignore[type-arg]
    "caminho_feliz": (
        {},
        None,
        "a mesa de dois do README — a régua contra a qual os outros se comparam",
    ),
    "em_pausa": (
        {"paused": True},
        None,
        "o Hefesto parado por decisão de outra aba ou de outra sessão",
    ),
    "grab_falhou": (
        {"primary_grab_state": "failed"},
        None,
        "o aviso de grab dentro do card do primário",
    ),
    "externo_na_mesa": (
        {
            "external": [_um_externo_versionado()],
            "coop": {"enabled": True, "players": 2, "externals": 1},
        },
        None,
        "um controle que o Hefesto VÊ e não adota, na mesma mesa dos DualSense",
    ),
    "steam_input": (
        {"steam_input": {"excecao_ativa": True, "vpad_suspenso": False}},
        None,
        "a exceção de Steam Input ligada — e a aba, de propósito, igualzinha",
    ),
    "mascara_divergente": (
        {},
        "xbox",
        "a divergência entre a máscara do perfil e a que o aparelho tem",
    ),
    "mesa_vazia": (
        {"controllers": [], "coop": {"enabled": True, "players": 0}},
        None,
        "o payload MEDIDO em 23/08 com zero controle na casa (§2.1 da sprint)",
    ),
}

#: Os estados que a aba, HOJE, **não** distingue — e que por isso saem byte a
#: byte iguais ao caminho feliz. A declaração existe porque a régua da I10
#: (`test_cada_estado_produz_uma_foto_diferente_do_caminho_feliz`) trata foto
#: repetida como defeito, e ela está certa: em 14/08/2026 nove de dez PNGs
#: saíram idênticos e o instrumento era cego. Um estado só sai daquela régua
#: DECLARADO, com a razão e a data — e entra nesta, que cobra o contrário.
#:
#: Quem fizer a aba reagir a um destes tem o teste avisando: o estado passa a
#: sair diferente, a régua de igualdade reprova, e a resposta é mover o nome de
#: volta. É a mesma disciplina do `_PAR_ACEITO` do portão do par assimétrico.
ESTADOS_SEM_EFEITO_NA_ABA: dict[str, str] = {
    "steam_input": (
        "25/08/2026, I6/ramo 2. A exceção de Steam Input NÃO muda a linha da "
        "Ponte, e é medição, não descuido: desde a ESCONDER-EM-VEZ-DE-SAIR-01 "
        "(09/08/2026, decisão dela) a exceção esconde o FÍSICO e mantém o vpad "
        "de pé, e em 11/08/2026, com um appid da allowlist dela em sessão, a "
        "medição em jogo achou ZERO espelhos da Steam e os vpads do Hefesto "
        "alimentando quatro controles (pilha-steam-input-xpad-sdl.md, §2.4-bis). "
        "Quem entrega o controle durante a exceção continua sendo o Hefesto — "
        "logo a resposta certa da aba é a mesma do caminho feliz. A foto existe "
        "para ela poder VER que é a mesma; se um dia a aba nomear a exceção "
        "(texto novo na primeira tela, e isso é palavra DELA), este nome volta "
        "para a régua da diferença."
    ),
}


def _rascunho_com_mascara(mascara):  # type: ignore[no-untyped-def]
    """Um `DraftConfig` cujo perfil de origem pede ``mascara``; ``None`` sem ela.

    Usa o construtor de PRODUÇÃO (`DraftConfig.with_mode`) em vez de um dublê
    local: um segundo montador do rascunho passaria a mentir no dia em que o
    esquema mudasse, e a foto é justamente o instrumento que deveria acusar.
    """
    if not mascara:
        return None
    with contextlib.suppress(Exception):
        from hefesto_dualsense4unix.app.draft_config import DraftConfig

        return DraftConfig().with_mode(
            {"kind": "gamepad", "gamepad_flavor": str(mascara)}
        )
    return None


def _montar_aba_inicio(builder, estado=None, *, draft=None) -> str:  # type: ignore[no-untyped-def]
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

    ``draft`` (25/08/2026, I10) é o rascunho do perfil em edição. Ele existe
    porque a linha de divergência de máscara lê `draft.source_mode.
    gamepad_flavor` (`_mascara_escolhida_por_ela`, fonte 2) — sem rascunho no
    host, esse aviso é INALCANÇÁVEL por foto, e foi por isso que ele nunca
    apareceu em imagem nenhuma deste repositório. ``None`` deixa o host como
    sempre foi.
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
            if draft is not None:
                self.draft = draft

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

        def _status_toast(self, _contexto: str, _msg: str) -> None:
            return None

        def _refresh_home_tab(self) -> None:
            return None

    if estado is None:
        estado = ESTADO_PADRAO_DE_DOIS
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


#: A LISTA DE MENTIRA do Steam Input, para a foto da aba Perfis.
#:
#: A-LISTA-QUE-FALTAVA-01 (22/08/2026). A caixinha do Steam Input NUNCA tinha
#: sido fotografada: ela só aparece com "Aplica a = Jogo da Steam", e os três
#: perfis da foto casavam por `process_name`. A lista nova nasceria invisível na
#: documentação — que é o mesmo defeito que este script existe para não repetir.
#:
#: Os appids são inventados e não existem em biblioteca nenhuma desta casa. Dois
#: têm nome no mapa abaixo e um NÃO tem, de propósito: é o caso honesto da tela
#: — sem `appmanifest` no disco, a linha mostra o número e diz por quê, e a foto
#: precisa mostrar isso tanto quanto mostra o caso feliz.
_APPIDS_DA_LISTA_DE_MENTIRA: tuple[str, ...] = ("101010", "202020", "303030")

_JOGOS_DA_LISTA_DE_MENTIRA: dict[str, str] = {
    "101010": "Jogo de Exemplo",
    "202020": "Outro Jogo de Exemplo",
    # "303030" fica de fora: é o que faz a foto mostrar "nome não encontrado".
}


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
            # A-LISTA-QUE-FALTAVA-01 (22/08/2026): o nome dos jogos da lista do
            # Steam Input. INVENTADO, como os perfis — o mapa de verdade sai de
            # `appmanifest_*.acf` e poria a biblioteca DELA num PNG versionado.
            self._nomes_dos_jogos = dict(_JOGOS_DA_LISTA_DE_MENTIRA)

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

        def _instalar_lista_de_jogos_do_pc(self) -> None:  # type: ignore[override]
            # O de produção VARRE O DISCO DELA — `appmanifest_*.acf` de toda
            # biblioteca Steam mais os `.desktop` — para montar a completação do
            # campo do jogo, e guarda o resultado em `self._nomes_dos_jogos`.
            #
            # DOIS motivos para ele não rodar aqui, e o segundo foi medido em
            # 22/08/2026 escrevendo esta função:
            #
            # 1. PRIVACIDADE, a mesma da bancada da mesa: a biblioteca dela não
            #    entra num PNG versionado. A lista suspensa não é desenhada na
            #    foto, mas o catálogo fica vivo no widget, e um script de
            #    fotografia que lê o disco dela já quebrou essa promessa antes;
            # 2. ele roda numa THREAD e SOBRESCREVE `_nomes_dos_jogos` quando
            #    volta. Foi por isso que a primeira foto saiu com os três jogos
            #    dizendo "nome não encontrado" mesmo com o mapa de mentira posto
            #    no `__init__`: o catálogo real (vazio, sem Steam no ambiente da
            #    foto) chegou depois e apagou os nomes inventados.
            return None

        @staticmethod
        def _appids_do_steam_input() -> set[str]:  # type: ignore[override]
            # O de produção lê `~/.config/.../steam_input_apps.txt` — a lista
            # DELA. Nunca aqui: são três appids que não existem em máquina
            # nenhuma desta casa, escolhidos para a foto mostrar os dois casos
            # que a lista sabe desenhar (com nome no disco e sem).
            return set(_APPIDS_DA_LISTA_DE_MENTIRA)

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

    # "Aplica a = Jogo da Steam" com um appid escrito: é o único estado em que a
    # caixinha do Steam Input e a lista dela existem na tela. Sem isto a foto
    # continuaria sem mostrá-las, e a documentação afirmaria por escrito uma
    # tela que ninguém vê.
    with contextlib.suppress(Exception):
        host._aplica_a.set_active_id("steam_game")
        builder.get_object("profile_simple_custom_name").set_text("404040")
        while Gtk.events_pending():
            Gtk.main_iteration()

    caixa = builder.get_object("profiles_paned")
    if caixa is not None:
        caixa.show_all()
    return (
        f"aba Perfis montada ({len(perfis)} perfis inventados, "
        '"Aplica a" e "Modo" com botões, e a lista do Steam Input com '
        f"{len(_APPIDS_DA_LISTA_DE_MENTIRA)} jogos de mentira)"
    )


#: A BANCADA DE MENTIRA da seção "A mesa" — sysfs inteiro em memória.
#:
#: CONFIG-02 (22/08/2026). A seção lê `/sys` de verdade em produção, e uma foto
#: tirada com a leitura real publicaria o barramento DELA num PNG versionado:
#: quais dongles ela tem, em que porta, sob que controlador. Nenhum portão
#: desta casa varre imagem — `test_retrato_das_abas_nao_vaza_dado_real`
#: inspeciona o SCRIPT, e `check_test_data.sh` só olha `tests/`.
#:
#: Os aparelhos aqui não existem em máquina nenhuma desta casa: são dois
#: adaptadores, um hub e quatro rádios inventados para exercitar TODOS os
#: estados que a seção sabe desenhar — painel lido e painel ausente, adaptador
#: em porta direta e adaptador atrás de hub, par colado e rádio USB 3.0 ao lado
#: de um adaptador. A bancada real de 22/08/2026 mostraria menos: ela tem ZERO
#: adaptadores.
_MESA_PCI_A = "0000:aa:00.0"
_MESA_PCI_B = "0000:bb:00.0"
_MESA_RAIZ_BT = "/bancada/class/bluetooth"
_MESA_RAIZ_USB = "/bancada/bus/usb/devices"
_MESA_USB1 = f"/bancada/devices/pci0000:00/{_MESA_PCI_A}/usb1"
_MESA_USB2 = f"/bancada/devices/pci0000:00/{_MESA_PCI_B}/usb2"

#: `nó -> {atributo: valor}`. Atributo ausente é ausente de verdade: é assim
#: que "Não sei" e "Em hub" chegam à foto pelo mesmo caminho do produto.
_MESA_APARELHOS: dict[str, dict[str, str]] = {
    f"{_MESA_USB1}/1-1": {
        "idVendor": "0a12",
        "idProduct": "0001",
        "bDeviceClass": "e0",
        "busnum": "1",
        "devnum": "4",
        "devpath": "1",
        "speed": "12",
        "physical_location/panel": "back",
    },
    f"{_MESA_USB1}/1-2": {
        "idVendor": "05e3",
        "idProduct": "0608",
        "bDeviceClass": "09",
        "busnum": "1",
        "devnum": "5",
        "devpath": "2",
        "speed": "480",
    },
    f"{_MESA_USB1}/1-2/1-2.1": {
        "idVendor": "0bda",
        "idProduct": "8771",
        "bDeviceClass": "e0",
        "busnum": "1",
        "devnum": "6",
        "devpath": "2.1",
        "speed": "12",
    },
    f"{_MESA_USB1}/1-2/1-2.2": {
        "idVendor": "0bda",
        "idProduct": "b812",
        "bDeviceClass": "00",
        "busnum": "1",
        "devnum": "7",
        "devpath": "2.2",
        "speed": "5000",
    },
    f"{_MESA_USB1}/1-3": {
        "idVendor": "1d57",
        "idProduct": "fa20",
        "bDeviceClass": "00",
        "busnum": "1",
        "devnum": "8",
        "devpath": "3",
        "speed": "12",
        "physical_location/panel": "front",
    },
    f"{_MESA_USB1}/1-4": {
        "idVendor": "046d",
        "idProduct": "c52b",
        "bDeviceClass": "00",
        "busnum": "1",
        "devnum": "9",
        "devpath": "4",
        "speed": "12",
        "physical_location/panel": "front",
    },
    f"{_MESA_USB2}/2-1": {
        "idVendor": "0cf3",
        "idProduct": "3005",
        "bDeviceClass": "00",
        "busnum": "2",
        "devnum": "3",
        "devpath": "1",
        "speed": "480",
        "physical_location/panel": "right",
    },
}

#: A INTERFACE 0 de cada aparelho da bancada, que é de onde o kernel diz o que
#: cada coisa É (`bInterfaceClass/SubClass/Protocol`). Sem estas linhas o censo
#: do barramento não teria o que ler e a coluna "O que é" sairia inteira em
#: "não sei" — a foto mostraria a tela de uma máquina que não existe.
#:
#: A bancada exercita os DOIS casos que a coluna sabe desenhar, e é obrigada a
#: isso: `03/01/01` e `03/01/02` viram "Teclado" e "Mouse" com o selo `(lido)`,
#: `e0/01/01` vira "Bluetooth", e o `ff/ff/ff` do Realtek — o fabricante que
#: declinou de classificar — é a única linha que nasce com o seletor aberto e
#: o `▲`. Uma bancada só com casos lidos faria a foto esconder metade da tela.
_MESA_INTERFACES: dict[str, tuple[str, str, str]] = {
    f"{_MESA_USB1}/1-1/1-1:1.0": ("e0", "01", "01"),
    f"{_MESA_USB1}/1-2/1-2:1.0": ("09", "00", "00"),
    f"{_MESA_USB1}/1-2/1-2.1/1-2.1:1.0": ("e0", "01", "01"),
    f"{_MESA_USB1}/1-2/1-2.2/1-2.2:1.0": ("ff", "ff", "ff"),
    f"{_MESA_USB1}/1-3/1-3:1.0": ("03", "01", "01"),
    f"{_MESA_USB1}/1-4/1-4:1.0": ("03", "01", "02"),
    f"{_MESA_USB2}/2-1/2-1:1.0": ("e0", "01", "01"),
}

#: Onde cada `hciN` aterrissa: na INTERFACE do dispositivo, como no sysfs de
#: verdade. Quem sobe daí até o dispositivo é o `dispositivo_usb_pai` do
#: produto — o retrato não reimplementa a subida, senão a foto provaria o
#: retrato e não o produto.
_MESA_INTERFACES_BT: dict[str, str] = {
    "hci0": f"{_MESA_USB1}/1-1/1-1:1.0",
    "hci1": f"{_MESA_USB1}/1-2/1-2.1/1-2.1:1.0",
}


def _bancada_da_mesa():  # type: ignore[no-untyped-def]
    """`(listar, ler, existe, real)` — o sysfs de mentira, montado uma vez.

    Compartilhado pelas DUAS leituras da seção (`ler_a_mesa` e
    `ler_o_barramento`) de propósito: se cada uma tivesse a sua bancada, a foto
    poderia mostrar um rádio na tabela e nenhuma classe para ele — que é
    exatamente o defeito que a coluna nova existe para não ter.
    """
    conteudo = {
        os.path.join(no, atributo): f"{valor}\n"
        for no, atributos in _MESA_APARELHOS.items()
        for atributo, valor in atributos.items()
    }
    conteudo.update(
        {
            os.path.join(no, atributo): f"{valor}\n"
            for no, tripla in _MESA_INTERFACES.items()
            for atributo, valor in zip(
                (
                    "bInterfaceClass",
                    "bInterfaceSubClass",
                    "bInterfaceProtocol",
                ),
                tripla,
                strict=True,
            )
        }
    )
    presentes = set(conteudo)
    reais = {
        os.path.join(_MESA_RAIZ_BT, nome): destino
        for nome, destino in _MESA_INTERFACES_BT.items()
    }
    reais.update(
        {os.path.join(_MESA_RAIZ_USB, os.path.basename(no)): no for no in _MESA_APARELHOS}
    )
    reais.update(
        {os.path.join(_MESA_RAIZ_USB, os.path.basename(no)): no for no in _MESA_INTERFACES}
    )
    listagens = {
        _MESA_RAIZ_BT: sorted(_MESA_INTERFACES_BT),
        _MESA_RAIZ_USB: sorted(
            os.path.basename(no)
            for no in (*_MESA_APARELHOS, *_MESA_INTERFACES)
        ),
    }
    return (
        lambda raiz: list(listagens.get(raiz, [])),
        lambda caminho: conteudo.get(caminho, ""),
        lambda caminho: caminho in presentes,
        lambda caminho: reais.get(caminho, caminho),
    )


def _mesa_de_mentira():  # type: ignore[no-untyped-def]
    """A leitura da seção "A mesa", feita sobre a bancada em memória.

    Chama a função de PRODUÇÃO (`ler_a_mesa`) com as raízes trocadas, e não uma
    cópia da lógica: a foto tem de mostrar o que o produto desenha, inclusive
    quando o produto mudar. Nenhum caminho de `/sys` é aberto — `listar`, `ler`
    e `existe` só conhecem `/bancada/...`.
    """
    from hefesto_dualsense4unix.integrations.mesa_de_radio import ler_a_mesa

    listar, ler, existe, real = _bancada_da_mesa()
    return ler_a_mesa(
        raiz_bt=_MESA_RAIZ_BT,
        raiz_usb=_MESA_RAIZ_USB,
        listar=listar,
        ler=ler,
        existe=existe,
        real=real,
    )


def _censo_de_mentira():  # type: ignore[no-untyped-def]
    """O barramento USB da bancada, pela função de PRODUÇÃO.

    É o que preenche a coluna "O que é" na foto. Mesma regra do irmão acima:
    `ler_o_barramento` é o do produto, com as raízes trocadas — se ele mudar de
    régua, a foto muda junto.
    """
    from hefesto_dualsense4unix.integrations.censo_do_barramento import (
        ler_o_barramento,
    )

    listar, ler, _existe, real = _bancada_da_mesa()
    return ler_o_barramento(
        raiz_usb=_MESA_RAIZ_USB, listar=listar, ler=ler, real=real
    )


#: Os dois adaptadores da bancada pela ótica do BlueZ, para a coluna "Nome".
#:
#: PRIVACIDADE, e é o mesmo motivo da bancada acima: o alias de verdade é texto
#: que ELA escreveu, e o `Address` é o endereço dos adaptadores dela. Ler o
#: BlueZ vivo aqui publicaria os dois num PNG versionado — nenhum portão desta
#: casa varre imagem.
#:
#: Os endereços são forjados (`AA:BB:CC:...`, a faixa que a suíte usa e que
#: `test_o_duble_usado_tem_mac_falso` ancora) e nem aparecem na tela: a coluna
#: mostra o nome.
#:
#: O segundo hospeda Nintendo de propósito. É ele que faz a foto mostrar as
#: DUAS coisas que a costura do prefixo faz: o alias guardado é
#: `"Nintendo Extra"`, e o que a tela desenha é `"Extra"`.
_MESA_DONGLES: tuple[tuple[str, str, bool, str], ...] = (
    ("AA:BB:CC:00:00:01", "Sala", False, "/org/bluez/hci0"),
    ("AA:BB:CC:00:00:02", "Nintendo Extra", True, "/org/bluez/hci1"),
)


def _dongles_de_mentira():  # type: ignore[no-untyped-def]
    """Os `Dongle` da bancada — o tipo de PRODUÇÃO, com dado inventado.

    O tipo é o do produto porque é dele que sai a propriedade `nome`, que é a
    que esconde o prefixo. Uma tupla de mentira com um `nome` calculado à mão
    faria a foto provar o retrato, e não o produto.
    """
    from hefesto_dualsense4unix.integrations.apelido_do_dongle import Dongle

    return tuple(
        Dongle(
            endereco=endereco,
            alias=alias,
            nome_do_sistema="Adaptador de bancada",
            hospeda_nintendo=nintendo,
            ligado=True,
            objeto=objeto,
        )
        for endereco, alias, nintendo, objeto in _MESA_DONGLES
    )



def _controles_de_mentira(fixture=None):  # type: ignore[no-untyped-def]
    """O inventário da seção "Os controles", vindo do fixture versionado.

    Mesmo arquivo que o `--mesa-cheia` usa (`state_full_quatro_controles.json`),
    e pelo mesmo motivo: ele é payload real de 14/08 que JÁ passou pelos portões
    de anonimato da suíte, com MAC de fixture. Ler o daemon vivo aqui poria o
    endereço dos controles dela num PNG versionado.

    O argumento existe para o `--cinco`: o item 15 do `TODO-INTEGRACAO.md` pede
    CINCO controles simultâneos **nesta aba**, e ela era a única que continuava
    lendo o fixture de quatro mesmo no modo de cinco — a foto do pior caso de
    largura sairia com a seção mais larga da janela um card menor.
    """
    try:
        alvo = FIXTURE_MESA_CHEIA if fixture is None else fixture
        return json.loads(alvo.read_text(encoding="utf-8"))
    except Exception:
        return {}


#: Os códigos de cor que os controles da bancada "responderiam" pelo cabo.
#:
#: São códigos do firmware da Sony, e a escolha de quais não é aleatória: o
#: desenho aprovado mostra cards de cores diferentes lado a lado justamente
#: porque a borda colorida é o que distingue um card do outro num relance.
#: `02` é Cosmic Red e `05` é Starlight Blue — a única das vinte e uma linhas
#: da tabela cujo tom é MEDIDO e não aproximado.
_CODIGOS_DA_BANCADA = ("02", "05", "01", "03")


def _cor_de_mentira(endereco: str = ""):  # type: ignore[no-untyped-def]
    """A cor do plástico de um controle da bancada, escolhida pelo endereço.

    Devolve o mesmo tipo que `cor_do_plastico.ler_pelo_cabo` — e passa pela
    tradução de PRODUÇÃO, `cor_por_codigo`, em vez de montar o objeto à mão: se
    um dia a tabela de cores mudar, a foto muda junto, que é o ponto de o
    retrato chamar o produto e não uma cópia dele.

    Determinística de propósito: a mesma bancada tem de produzir a mesma foto
    duas vezes seguidas, senão o portão que compara as imagens acusa mudança
    onde não houve nenhuma.
    """
    from hefesto_dualsense4unix.integrations import cor_do_plastico

    codigo = _CODIGOS_DA_BANCADA[
        sum(endereco.encode()) % len(_CODIGOS_DA_BANCADA) if endereco else 0
    ]
    for nome in ("cor_por_codigo", "_cor_por_codigo", "cor_do_codigo"):
        traduz = getattr(cor_do_plastico, nome, None)
        if traduz is not None:
            return traduz(codigo)
    return None


def _pintar_o_exame_de_bancada(hospedeiro) -> None:  # type: ignore[no-untyped-def]
    """Desenha a seção "Está tudo certo?" com um resultado de bancada.

    Sem isto a foto sai com "Ainda não examinei" e nenhuma das cinco linhas
    pintada — que é o estado CORRETO da aba recém-montada, e um retrato inútil
    da seção mais visual da aba.

    O exame de verdade NÃO roda aqui, e a regra é dura: ele lê a energia das
    portas, os pareamentos e a vizinhança de rádio DESTA máquina, e a foto vai
    para `docs/usage/assets/` sem revisão humana. Os portões de anonimato não
    varrem imagem nenhuma.

    Quem desenha é o método de PRODUÇÃO (`PainelDoExame.aplicar`), com itens de
    bancada e o veredito calculado pela função de produção. Assim a foto
    acompanha o desenho sozinha quando ele mudar — copiar a pintura aqui criaria
    um segundo dono do layout da seção.

    Os cinco estados são os do desenho aprovado: quatro certos e a vizinhança em
    atenção, que é o caso que o desenho escolheu mostrar por ser o único em que
    a tela precisa dizer o que fazer.
    """
    try:
        from hefesto_dualsense4unix.integrations.exame_da_mesa import (
            ESTADO_ATENCAO,
            ESTADO_CERTO,
            ROTULO_ENERGIA_DAS_PORTAS,
            ROTULO_ENERGIA_DO_RADIO,
            ROTULO_PAREAMENTOS,
            ROTULO_SUPORTE_AO_CONTROLE,
            ROTULO_VIZINHANCA,
            Item,
            veredito,
        )
    except Exception:
        return

    painel = getattr(hospedeiro, "_painel_do_exame", None)
    if painel is None:
        return

    itens = [
        Item(
            chave="energia_do_radio",
            rotulo=ROTULO_ENERGIA_DO_RADIO,
            estado=ESTADO_CERTO,
            porque="A economia de energia do rádio está desligada.",
        ),
        Item(
            chave="energia_das_portas",
            rotulo=ROTULO_ENERGIA_DAS_PORTAS,
            estado=ESTADO_CERTO,
            porque="Nenhuma porta da bancada está em economia de energia.",
        ),
        Item(
            chave="pareamentos",
            rotulo=ROTULO_PAREAMENTOS,
            estado=ESTADO_CERTO,
            porque="Os dois pareamentos da bancada estão completos.",
        ),
        Item(
            chave="suporte_ao_controle",
            rotulo=ROTULO_SUPORTE_AO_CONTROLE,
            estado=ESTADO_CERTO,
            porque="O suporte ao DualSense está carregado.",
        ),
        Item(
            chave="vizinhanca_das_portas",
            rotulo=ROTULO_VIZINHANCA,
            estado=ESTADO_ATENCAO,
            porque="Dois rádios da bancada estão em portas vizinhas.",
            cura="Vale mudar um deles de porta.",
        ),
    ]
    with contextlib.suppress(Exception):
        painel.aplicar(itens, veredito(itens), time.time())


def _montar_aba_configuracoes(builder, fixture=None) -> str:  # type: ignore[no-untyped-def]
    """Monta a aba Configurações — o glade dela é só o container vazio.

    CONFIG-01 (21/08/2026). Mesmo defeito que a PERFIS-NA-FOTO-01 pagou: o
    conteúdo desta aba é montado em CÓDIGO (`install_config_tab`), então uma
    foto do glade cru sairia com a página em branco — e a documentação passaria
    a afirmar que a aba nova não tem nada dentro.

    O método é o de PRODUÇÃO, e não uma cópia da montagem. O host mínimo é o
    `builder` mais UM desvio: `_mesa_leitor`, que a seção "A mesa" consulta em
    vez de ler `/sys`. Sem ele a foto sairia com o barramento dela dentro
    (CONFIG-02, 22/08/2026) — e essa é a única coisa que esta aba lê da máquina.
    """
    try:
        from hefesto_dualsense4unix.app.actions.config import (
            ABA_CONFIG,
            SECOES,
            ConfigActionsMixin,
        )
    except Exception as exc:
        return f"aba Configurações não montada ({exc})"

    class _Host(ConfigActionsMixin):  # type: ignore[misc, name-defined]
        def __init__(self) -> None:
            self.builder = builder
            # Atributo de INSTÂNCIA, não de classe: como atributo de classe ele
            # viraria método ligado e receberia `self` que ninguém espera.
            self._mesa_leitor = _mesa_de_mentira
            # A coluna "O que é" nasce LIDA do barramento, e a seção recusa a
            # leitura viva sempre que o `_mesa_leitor` está de pé. Sem este
            # segundo dublê a foto sairia com a coluna inteira em "não sei" —
            # a tela de uma máquina que não existe.
            self._censo_leitor = _censo_de_mentira
            # A coluna "Nome" vem do BlueZ, e o alias é texto que ELA escreveu
            # — mais o endereço dos adaptadores dela. Mesmo motivo dos outros
            # dois dublês: esta foto vai para `docs/usage/assets/` sem revisão.
            self._dongles_leitor = _dongles_de_mentira
            # A seção "Os controles" pergunta ao daemon quem está na mesa. No
            # retrato não há daemon, e não pode haver: o `state_full` de verdade
            # traz o endereço Bluetooth dos controles DELA, e esta foto vai para
            # `docs/usage/assets/` sem revisão humana — os portões de anonimato
            # não varrem imagem. O leitor devolve o mesmo fixture VERSIONADO que
            # a aba Status já usa, cujo MAC é falso por construção.
            self._controles_leitor = lambda: _controles_de_mentira(fixture)
            # A cor do plástico é lida do controle pelo cabo. Sem controle, sem
            # leitura — e a foto mostraria "Não sei" em todos os cards. Este
            # dublê devolve a cor que o card desenharia se o aparelho tivesse
            # respondido, para a borda colorida aparecer na documentação.
            self._cor_do_plastico_leitor = _cor_de_mentira

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

    hospedeiro = _Host()
    try:
        hospedeiro.install_config_tab()
    except Exception as exc:
        return f"aba Configurações não montada ({exc})"
    _pintar_o_exame_de_bancada(hospedeiro)

    caixa = builder.get_object(ABA_CONFIG)
    if caixa is not None:
        caixa.show_all()
    mesa = _mesa_de_mentira()
    censo = _censo_de_mentira()
    lidos = sum(
        1
        for radio in mesa.radios
        for aparelho in [censo.aparelho(radio.no)]
        if aparelho is not None and aparelho.grau == "lido"
    )
    return (
        f"aba Configurações montada ({len(SECOES)} seções; a mesa com "
        f"{len(mesa.adaptadores)} adaptadores e {len(mesa.radios)} rádios "
        f"de bancada, nenhum desta máquina; {lidos} dos {len(mesa.radios)} "
        f"classificados pelo barramento, {len(_MESA_DONGLES)} com nome)"
    )


# ---------------------------------------------------------------------------
# AS CINCO ABAS QUE A FOTO PUBLICAVA CRUAS — P10 (23/08/2026)
# ---------------------------------------------------------------------------
#
# O DEFEITO, medido no diagnóstico das onze abas: Lightbar, Rumble, Sistema,
# Emulação e Navegação não tinham host nenhum aqui, e por isso o README
# publicava o GLADE CRU delas. O que a documentação afirmava:
#
# * Emulação — "Device: Microsoft X-Box 360 pad" e "Buffer: 150", os dois
#   números que a BUG-EMULATION-HOTKEY-CARD-FIXO-01 parou de contar como se
#   fossem estado lido do daemon. A foto seguia contando;
# * Navegação — a legenda de jargão do glade ("Formato: KEY_* … __OPEN_OSK__"),
#   que a KBD-01 substituiu por texto de gente há levas;
# * Sistema — "Diagnóstico ao abrir a aba…", "consultando…", "Verificando…":
#   três estados transitórios publicados como se fossem a tela;
# * Rumble e Lightbar — o rótulo de estado da vibração e o "Aceso agora" nunca
#   saíram do default, e são o assunto inteiro das duas abas.
#
# Custo composto, e é ele que justifica este conserto vir antes de feature: a
# regra desta casa manda OLHAR A FOTO primeiro. Uma foto que mente contamina
# todo trabalho que vem depois dela.
#
# O DESENHO DOS CINCO HOSTS, e onde cada um pode desviar
# -------------------------------------------------------
#
# É o mesmo dos hosts que já existiam: mínimo, com um `_get` que resolve ids do
# builder, o MÉTODO DE PRODUÇÃO fazendo a montagem, e desvio SÓ onde a produção
# falaria com o daemon ou leria a máquina dela. O que muda de aba para aba é
# onde fica a costura:
#
# * onde a produção tem PINTOR SEPARADO (uma função que recebe o que desenhar),
#   o desvio injeta dado de bancada e quem desenha é a produção:
#   `_apply_daemon_view`, `_apply_storm_diag`, `_aplicar_keyboard_switch`,
#   `_apply_policy_to_widgets`, `markup_status_steam_input`,
#   `descrever_deteccao_de_janela`;
# * onde o pedido de IPC e o desenho moram na MESMA função (o caso do
#   `_refresh_gamepad_and_gamemode`), o desvio chama os pintores de produção
#   com o argumento de "não sei" — que é exatamente o que a produção faz quando
#   o daemon não responde. Nunca uma cópia do markup: um segundo dono do
#   desenho é o defeito que o `test_a_foto_monta_como_o_produto_monta` existe
#   para pegar, e que já custou uma decisão dela.
#
# O ATALHO QUE ESTÁ PROIBIDO, e o portão que o tranca
# ----------------------------------------------------
#
# Desviar no TRANSPORTE (trocar o pedido de IPC por um dublê) seria mais curto
# e resolveria as cinco abas de uma vez. Está proibido: o
# `test_retrato_das_abas_nao_vaza_dado_real.py` reprova o nome do transporte no
# código deste script, e é essa proibição que mantém a promessa de privacidade
# do cabeçalho verificável por LEITURA, sem depender de rodar nada. Por isso o
# desvio é sempre no método da aba.

#: O estado de bancada das cinco abas. Inventado aqui, como o `_NO_JOGO_ESTADO`
#: logo acima e pela mesma razão: o estado de verdade traz o endereço Bluetooth
#: dos controles dela, e estas fotos vão para `docs/usage/assets/` sem revisão
#: humana — os portões de anonimato não varrem imagem.
#:
#: É a mesa SAUDÁVEL, jogando pelo Hefesto com dois espelhos de pé, e conta a
#: mesma história das outras abas (o "Pragmata" na frente é o jogo que a aba
#: "No jogo" e a Perfis já mostram). O modo `--mesa-cheia` passa o fixture
#: versionado no lugar deste dicionário — ver `main`.
_ESTADO_DE_BANCADA: dict = {
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense", "backend": "uhid"},
    # A chave do teclado emulado DESENHA na aba Navegação e é lida daqui. Sem o
    # bloco, a produção diz (com razão) "não consegui ler — o Hefesto pode
    # estar desligado", e a foto da Navegação passaria a contradizer a da
    # Sistema, que mostra o Hefesto funcionando. As onze fotos são lidas juntas.
    "keyboard_emulation": {
        "enabled": False,
        "bloqueio": None,
        "despachando": False,
        "device_ativo": False,
        "osk_disponivel": True,
    },
    "rumble_policy": "balanceado",
    "rumble_policy_custom_mult": 0.7,
    "rumble_passthrough": True,
    "rumble_active": None,
    "rumble_ff": {"vpads": 2, "plays": 0, "nao_nulos": 0, "descartados": 0},
    "window_detect_backend": "xlib",
    "window_detect_healthy": True,
    "window_detect_seeing": True,
    "window_detect_current_class": "pragmata.exe",
    "window_detect_last_class": "pragmata.exe",
    "window_detect_reason": None,
    # NÃO há bloco `hotkey` aqui, e a ausência é deliberada: sem ele o
    # `_sync_hotkey_card` escreve "150 (padrão)" e "Não (padrão)", que é a
    # forma de a tela dizer "isto é fábrica, não é estado lido". Foi essa
    # distinção que a BUG-EMULATION-HOTKEY-CARD-FIXO-01 comprou, e é ela que a
    # foto tem de publicar — o "150" seco do glade é indistinguível de um
    # número lido do daemon.
}

#: A máscara que a bancada declara ligada na aba Emulação. Dado, não regra: a
#: tradução de `flavor` para máscara ativa mora na produção, e copiá-la aqui
#: faria deste script um segundo dono dela.
_MASCARA_DE_BANCADA = "dualsense"


def _montar_aba_lightbar(builder) -> str:  # type: ignore[no-untyped-def]
    """Monta a aba Lightbar — a prévia e o "Aceso agora" nascem em código.

    Sem host, a foto saía com a prévia CINZA (o `draw` do `Gtk.DrawingArea` é
    conectado em `install_lightbar_tab`, não no glade) e com o rótulo
    "Aceso agora: consultando…", que é o texto de espera do glade.

    Nada aqui fala com o daemon nem lê o disco: o `DraftConfig()` é o rascunho
    de FÁBRICA do produto, o mesmo que a janela usa antes de qualquer perfil
    ser carregado, e é ele que decide a cor, o brilho e as cinco luzes.
    """
    try:
        from hefesto_dualsense4unix.app.actions.lightbar_actions import (
            LightbarActionsMixin,
        )
        from hefesto_dualsense4unix.app.draft_config import DraftConfig
    except Exception as exc:
        return f"aba Lightbar não montada ({exc})"

    class _Host(LightbarActionsMixin):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            self.builder = builder
            self.draft = DraftConfig()
            # O alvo de edição é mantido pela aba Status a partir do estado
            # vivo. Sem daemon, ele é de bancada — e é o que faz a frase do
            # "Aceso agora" sair na forma que ela vê com um controle escolhido.
            self._edit_target_slot = 1
            self._coop_ligado = True

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

        def _status_toast(self, _contexto: str, _msg: str) -> None:
            return None

    try:
        host = _Host()
        host.install_lightbar_tab()
        host._refresh_lightbar_from_draft()
    except Exception as exc:
        return f"aba Lightbar não montada ({exc})"

    caixa = builder.get_object("tab_lightbar_box")
    if caixa is not None:
        caixa.show_all()
    rotulo = builder.get_object("player_leds_estado")
    frase = rotulo.get_text() if rotulo is not None else "(rótulo ausente)"
    return f"aba Lightbar montada (prévia acesa; {frase!r})"


def _montar_aba_rumble(builder, estado=None) -> str:  # type: ignore[no-untyped-def]
    """Monta a aba Rumble — o rótulo de estado da vibração é o assunto dela.

    `install_rumble_tab` tem UMA linha, e essa linha pede o `state_full` ao
    daemon. Sem host, tudo o que a aba desenha a partir da resposta ficava fora
    da foto: a política acesa nos quatro botões, o multiplicador no deslizador,
    o rótulo "Estado da vibração" e o aviso de alcance.

    O DESVIO é o pedido de IPC, e só ele: `_apply_policy_to_widgets` e
    `_update_rumble_state_label` são os pintores de PRODUÇÃO, recebendo o
    estado de bancada em vez do estado vivo.

    O aviso de alcance (`rumble_policy_aviso`) continua ESCONDIDO nesta foto, e
    isso não é omissão: com dois espelhos de pé a produção decide esconder, e
    quem decide o que fica escondido é ela, não este script. Fotografá-lo
    exigiria uma segunda bancada, no quadrante sem dono do rumble.
    """
    try:
        from hefesto_dualsense4unix.app.actions.rumble_actions import (
            _MULT_PADRAO,
            RumbleActionsMixin,
        )
    except Exception as exc:
        return f"aba Rumble não montada ({exc})"

    fonte = dict(estado) if estado else dict(_ESTADO_DE_BANCADA)

    class _Host(RumbleActionsMixin):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            self.builder = builder

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

        def _status_toast(self, _contexto: str, _msg: str) -> None:
            return None

        def _sync_policy_from_state(  # type: ignore[override]
            self, *, indicar_sem_opiniao: bool = False
        ) -> None:
            """O desvio: a bancada no lugar do `state_full` do daemon vivo.

            Os defaults são os da produção (`_on_state` lá) — a política cai em
            "balanceado" e o multiplicador em `_MULT_PADRAO` quando a chave não
            vem, e é assim que a foto continua certa se a bancada mudar.
            """
            self._apply_policy_to_widgets(
                str(fonte.get("rumble_policy", "balanceado")),
                float(fonte.get("rumble_policy_custom_mult", _MULT_PADRAO)),
            )
            self._update_rumble_state_label(fonte)

    try:
        host = _Host()
        host.install_rumble_tab()
    except Exception as exc:
        return f"aba Rumble não montada ({exc})"

    caixa = builder.get_object("tab_rumble_box")
    if caixa is not None:
        caixa.show_all()
    aviso = builder.get_object("rumble_policy_aviso")
    visivel = aviso is not None and aviso.get_visible()
    return (
        f"aba Rumble montada (política {fonte.get('rumble_policy')!r}; aviso de "
        f"alcance {'visível' if visivel else 'escondido pela produção'})"
    )


#: As linhas do cartão "Saúde do sistema" na foto da aba Sistema.
#:
#: INVENTADAS, e não lidas: `storm_doctor.storm_report()` varre a máquina de
#: quem rodar o script (drop-ins do WirePlumber, regras de udev, o vdf da
#: Steam) e o caminho de produção ainda pergunta ao daemon quantos controles
#: estão no cabo. As duas coisas estão proibidas aqui pela seção de privacidade
#: do cabeçalho — e uma foto de README que mudasse conforme o que está plugado
#: na hora seria ruído em toda leva.
_SAUDE_DE_BANCADA: tuple[tuple[str, str], ...] = (
    ("[ OK ]", "Quirk de áudio USB ativo — sem tempestade de erro -71."),
    ("[ OK ]", "Regra de udev do uinput instalada."),
    ("[ OK ]", "Steam Input desligado para os jogos fora da lista de exceções."),
    ("[INFO]", "Microfone do controle livre, com prioridade acima do eco."),
)

#: As cores do cartão de saúde. São as MESMAS do `_refresh_storm_diag`, e a
#: repetição é conhecida: lá elas moram dentro do worker que varre a máquina, e
#: não há como alcançá-las sem varrer junto. Se as cores mudarem lá, esta foto
#: fica atrás — é o preço de não fotografar a máquina de quem roda o script.
_CORES_DA_SAUDE: dict[str, str] = {
    "[ OK ]": "#50fa7b",
    "[WARN]": "#ffb86c",
    "[INFO]": "#8b8fa8",
}

#: O painel "Detalhes técnicos" da aba Sistema, inventado.
#:
#: É o painel que JÁ VAZOU uma vez: o `README.md` registra que ele teve de ser
#: borrado à mão porque o log mostrava o endereço Bluetooth real dos controles.
#: Aqui ele nasce de bancada — nada de `systemctl status` da máquina de quem
#: roda o script.
_LOG_DE_BANCADA = (
    "● hefesto-dualsense4unix.service - Hefesto DualSense4Unix\n"
    "     Loaded: loaded (hefesto-dualsense4unix.service; enabled)\n"
    "     Active: active (running)\n"
    "   Main PID: 4242 (hefesto-dualsen)\n"
    "\n"
    "controle_conectado transporte=usb jogador=1\n"
    "controle_conectado transporte=bt jogador=2\n"
    "perfil_aplicado nome=Pragmata origem=janela\n"
)


def _montar_aba_sistema(builder) -> str:  # type: ignore[no-untyped-def]
    """Monta a aba Sistema — a que publicava três estados de espera.

    Os TRÊS desvios são os três lugares em que a produção sai da janela, e
    cada um deles é obrigatório aqui:

    * `_refresh_daemon_view_async` roda `systemctl is-active/is-enabled/status`
      da máquina de quem fotografa. O desvio entrega o resultado de bancada ao
      `_apply_daemon_view`, que é o pintor de produção — inclusive do painel
      "Detalhes técnicos", que é o que já vazou MAC uma vez;
    * `_refresh_storm_diag` varre o disco E pergunta ao daemon quantos
      controles estão no cabo. O desvio entrega o markup de bancada ao
      `_apply_storm_diag`;
    * `_refresh_window_detect_diag` pede `daemon.state_full`. O desvio chama a
      `descrever_deteccao_de_janela`, que é a função PURA de produção, com o
      estado de bancada.

    O que NÃO foi desviado, de propósito:
    `_sync_restart_daemon_button_sensitivity` só olha se a unit do systemd está
    instalada nesta máquina, e o que ela decide é se um botão fica cinza. Não
    há identidade nisso, e desviá-la seria copiar comportamento de produção
    para nada.
    """
    try:
        from hefesto_dualsense4unix.app.actions.daemon_actions import (
            DaemonActionsMixin,
            descrever_deteccao_de_janela,
        )
    except Exception as exc:
        return f"aba Sistema não montada ({exc})"

    markup_da_saude = "\n".join(
        f'<span foreground="{_CORES_DA_SAUDE.get(tag, "#c8ccda")}">{tag}</span> {msg}'
        for tag, msg in _SAUDE_DE_BANCADA
    )

    class _Host(DaemonActionsMixin):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            self.builder = builder

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

        def _status_toast(self, _contexto: str, _msg: str) -> None:
            return None

        def _refresh_daemon_view_async(self) -> None:  # type: ignore[override]
            self._apply_daemon_view("online_systemd", "enabled", _LOG_DE_BANCADA)

        def _refresh_storm_diag(self) -> None:  # type: ignore[override]
            self._apply_storm_diag(markup_da_saude)

        def _refresh_window_detect_diag(self) -> None:  # type: ignore[override]
            rotulo = self._get("window_detect_diag_label")
            if rotulo is not None:
                rotulo.set_markup(
                    descrever_deteccao_de_janela(dict(_ESTADO_DE_BANCADA))
                )

    try:
        host = _Host()
        host.install_daemon_tab()
    except Exception as exc:
        return f"aba Sistema não montada ({exc})"

    caixa = builder.get_object("daemon_box")
    if caixa is not None:
        caixa.show_all()
    return (
        f"aba Sistema montada ({len(_SAUDE_DE_BANCADA)} linhas de saúde, o log "
        "de bancada e o detector de janela — nenhum byte desta máquina)"
    )


def _montar_aba_emulacao(builder) -> str:  # type: ignore[no-untyped-def]
    """Monta a aba Emulação — a que publicava "X-Box 360 pad" e "Buffer: 150".

    Os dois textos são o DEFAULT do glade, e a produção os substitui na
    primeira linha de `install_emulation_tab`: o nome do aparelho sai da
    constante `DEVICE_NAME` e o buffer vira "150 (padrão)" pelo
    `_sync_hotkey_card(None)` — que é o jeito de a tela dizer que aquilo é
    fábrica, e não estado lido. A foto contava a versão que a
    BUG-EMULATION-HOTKEY-CARD-FIXO-01 apagou.

    OS DESVIOS, e por que cada um:

    * `_refresh_steam_input_status` traduz appid em NOME DE JOGO lendo o
      `appmanifest` da Steam de quem fotografa. Ia direto para o README. O
      desvio chama `markup_status_steam_input`, o pintor puro de produção, com
      a bancada "Steam Input desligado";
    * `_mic_state` lê os drop-ins do WirePlumber do `$HOME`. O desvio devolve
      o estado ligado, e quem pinta continua sendo `_refresh_mic_status`;
    * `_refresh_gamepad_and_gamemode` e `_refresh_keyboard_switch` pedem
      `daemon.state_full`. Aqui não há pintor separado que receba o estado — o
      desenho mora dentro do `_on_state` —, então o desvio chama os pintores de
      produção (`_highlight_gamepad`, `_sync_uinput_card`, `_sync_hotkey_card`,
      `_sync_gamemode_button`, `_aplicar_keyboard_switch`) com o dado de
      bancada. Duas coisas ficam FORA da foto por isso, e é o limite honesto
      deste conserto: os rótulos "Gamepad para os jogos:" e "Modo jogo:"
      continuam no "—" do glade, porque o markup deles nasce dentro do
      `_on_state` e copiá-lo aqui criaria um segundo dono do desenho.

    O QUE **NÃO** FOI DESVIADO, e é o único ponto em que esta foto muda de
    máquina para máquina: `_refresh_emulation_view` conta os `/dev/input/js*` e
    olha a permissão do `/dev/uinput`. Não há identidade ali — é contagem de
    aparelho ligado, sem nome de rede, MAC nem caminho de `$HOME` — e não há
    costura para desviar sem copiar os quatro markups da produção. O recado
    devolvido diz o que saiu, para quem fotografa conferir antes de commitar.
    """
    try:
        from hefesto_dualsense4unix.app.actions.emulation_actions import (
            EmulationActionsMixin,
            markup_status_steam_input,
        )
        from hefesto_dualsense4unix.app.actions.mode_transition import mode_of_state
    except Exception as exc:
        return f"aba Emulação não montada ({exc})"

    class _Host(EmulationActionsMixin):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            self.builder = builder

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

        def _status_toast(self, _contexto: str, _msg: str) -> None:
            return None

        def _mic_state(self) -> str:  # type: ignore[override]
            return str(self.MIC_LIGADO)

        def _refresh_steam_input_status(self) -> None:  # type: ignore[override]
            rotulo = self._get("emulation_steam_input_status_label")
            if rotulo is not None:
                rotulo.set_markup(markup_status_steam_input(False, [], [], None))

        def _refresh_gamepad_and_gamemode(self) -> None:  # type: ignore[override]
            estado = dict(_ESTADO_DE_BANCADA)
            self._highlight_gamepad(_MASCARA_DE_BANCADA)
            # É esta chamada que escreve `emulation_vidpid_label` com o
            # VID:PID da máscara ATIVA, não o do glade cru ("045E:028E (Xbox
            # 360)"). Régua em `test_p10_..._ROTULOS_QUE_O_CODIGO_REESCREVE`
            # (Z0-4, §2.2/M4 da sprint Z0-01) — mordida provada em 24/08.
            self._sync_uinput_card(_MASCARA_DE_BANCADA)
            self._sync_hotkey_card(estado)
            self._sync_gamemode_button(mode_of_state(estado))

        def _refresh_keyboard_switch(self) -> None:  # type: ignore[override]
            self._aplicar_keyboard_switch(
                dict(_ESTADO_DE_BANCADA).get("keyboard_emulation")
            )

    try:
        host = _Host()
        host.install_emulation_tab()
    except Exception as exc:
        return f"aba Emulação não montada ({exc})"

    caixa = builder.get_object("emulation_box")
    if caixa is not None:
        caixa.show_all()
    gamepads = builder.get_object("emulation_js_label")
    lido = gamepads.get_text() if gamepads is not None else "(rótulo ausente)"
    return (
        "aba Emulação montada (o cartão do aparelho e o do atalho vêm do "
        f"código). Desta máquina saiu só a contagem de gamepads: {lido!r}"
    )


def _montar_aba_navegacao(builder) -> str:  # type: ignore[no-untyped-def]
    """Monta a aba Navegação — a que publicava a legenda de jargão.

    O glade traz, no `key_bindings_legend`, o texto que a KBD-01 aposentou:
    *"Formato: KEY_* (ex: KEY_C, KEY_ENTER) ou __OPEN_OSK__/__CLOSE_OSK__"*.
    Quem escreve a legenda de verdade é `_install_key_bindings_treeview`, que
    também é quem cria as DUAS COLUNAS da lista de atalhos — sem host, a foto
    publicava a lista sem coluna nenhuma e a legenda em jargão.

    Nada aqui fala com o daemon: o `DraftConfig()` de fábrica tem
    `key_bindings is None`, que a produção resolve para os atalhos de FÁBRICA
    (`DEFAULT_BUTTON_BINDINGS`) — exatamente o que ela vê ao abrir a janela sem
    perfil carregado.

    A chave do teclado emulado desta aba NÃO é montada aqui: o dono dela é o
    mixin da Emulação (`_refresh_keyboard_switch`), e é de lá que ela vem —
    ver a nota da `EMULACAO-NO-JOGO-01/E1` na produção.
    """
    try:
        from hefesto_dualsense4unix.app.actions.input_actions import (
            InputActionsMixin,
        )
        from hefesto_dualsense4unix.app.draft_config import DraftConfig
    except Exception as exc:
        return f"aba Navegação não montada ({exc})"

    class _Host(InputActionsMixin):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            self.builder = builder
            self.draft = DraftConfig()

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

        def _status_toast(self, _contexto: str, _msg: str) -> None:
            return None

    try:
        host = _Host()
        host.install_input_tab()
    except Exception as exc:
        return f"aba Navegação não montada ({exc})"

    caixa = builder.get_object("tab_navegacao_dsx")
    if caixa is not None:
        caixa.show_all()
    linhas = len(host._key_bindings_store) if host._key_bindings_store else 0
    return f"aba Navegação montada ({linhas} atalhos de fábrica na lista)"


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
    # O MÉTODO DE PRODUÇÃO, e não uma cópia dele. SUBSTITUÍDO em 22/08/2026,
    # e a razão é medida: esta função montava os modos À MÃO
    # (`SegmentedSelector(wrap=True)` mais `slot.pack_start(sel, True, True, 0)`)
    # em vez de chamar `install_triggers_tab`. Era um SEGUNDO DONO da montagem —
    # exatamente o que o docstring acima diz que não se deve fazer com os
    # rótulos, cometido com o LAYOUT.
    #
    # O preço, medido no mesmo dia: o `expand=True` daquele `pack_start` não
    # existe no produto, e por causa dele a foto saía com a moldura esticada até
    # o pé da página. Ela decidiu a fila de interface OLHANDO ESTA FOTO — a
    # dúvida da decisão 1 do `DECISOES.md` ("o vazio dos Gatilhos não sumiu,
    # mudou de lado") nasceu de um vazio que era do INSTRUMENTO. Com o método de
    # produção a moldura mede 482px de 1040; com a montagem à mão, 1016.
    #
    # Mesmo desenho da aba Perfis e do card do Status logo abaixo: host mínimo
    # com `_get`, nada de IPC, nada de tique.
    try:
        from hefesto_dualsense4unix.app.actions.triggers_actions import (
            TriggersActionsMixin,
        )
    except Exception as exc:
        return f"modos de gatilho não injetados ({exc})"

    class _Host(TriggersActionsMixin):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            self.builder = builder

        def _get(self, nome: str):  # type: ignore[no-untyped-def]
            return self.builder.get_object(nome)

        def _status_toast(self, _contexto: str, _msg: str) -> None:
            return None

    try:
        _Host().install_triggers_tab()
    except Exception as exc:
        return f"modos de gatilho não injetados ({exc})"

    from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS

    return f"{len(PRESETS)} modos de gatilho injetados pelo método de produção"


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


def _host_do_cabecalho(builder):  # type: ignore[no-untyped-def]
    """O host da Status com a fita do alvo JÁ montada — e um só por execução.

    `_init_controller_target_combo` **empacota** a faixa "Ajustes vão para:" no
    `header_bar` a cada chamada: dois hosts, duas faixas empilhadas, e a foto
    do cabeçalho mostrando uma janela que não existe. Por isso quem precisa da
    fita — a aba Status da mesa cheia e as duas fotos do cabeçalho — recebe o
    MESMO host, criado uma vez pelo `main`.
    """
    host = _host_da_aba_status(builder)
    host._init_controller_target_combo()
    return host


def _injetar_cards_da_mesa_cheia(builder, estado, host=None) -> str:  # type: ignore[no-untyped-def]
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
        host = _host_do_cabecalho(builder) if host is None else host
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

#: As abas que pedem mais altura do que a janela tem, e por isso ganham foto
#: esticada TAMBÉM no modo normal — não só no `--mesa-cheia`.
#:
#: A Configurações entrou em 22/08/2026, quando as cinco seções ficaram
#: prontas: ela pede mais de 1080px sozinha, e a foto de 1920x1080 cortava a
#: seção "A janela" pela metade. A documentação da aba mostraria quatro seções
#: e meia, o que é pior do que não mostrar nenhuma — quem lê conclui que a
#: quinta não existe.
ABAS_ESTICADAS = ("readme_configuracoes",)

#: Teto da foto esticada, em px. Não é medo do arquivo grande: é o sinal de que
#: alguma coisa cresceu sem limite e a foto viraria uma tira ilegível.
ALTURA_MAXIMA_ESTICADA = 4000

#: A moldura da tira de abas em volta do rótulo, em px: as margens que o tema
#: dá à aba ativa mais a linha rosa embaixo dela. Medido no tema desta casa;
#: sem ela a foto esticada corta os últimos pixels da última seção.
_FOLGA_DA_TIRA = 26

#: A foto do cabeçalho com a fita do alvo VIVA — ver `_fotografar_o_cabecalho`.
#:
#: Ela nasceu só no modo mesa cheia (14/08/2026) e passou a existir em TODOS os
#: modos em 24/08/2026, com o `readme_` da documentação: a Z2-8 fez a fita
#: esmaecer em SEIS abas que antes ficavam sensíveis, e nenhuma foto deste
#: repositório mostrava o cabeçalho para provar como isso ficou. O texto do
#: `interface.md` que dizia *"esta seção foi escrita contra o código"* caducou
#: com ela.
NOME_DO_CABECALHO = "readme_cabecalho"

#: A foto do MESMO cabeçalho numa aba que não lê o alvo — a fita esmaecida.
#:
#: Duas fotos e não uma porque o assunto da Z2-8 é a DIFERENÇA entre os dois
#: estados: uma foto sozinha não diz se aquilo é a fita normal ou a inerte.
#: Quem escolhe as duas abas é `_as_duas_abas_do_alvo`, lendo o mapa
#: `_ALVO_POR_ABA` do produto — não uma lista repetida aqui.
NOME_DO_CABECALHO_INERTE = "readme_cabecalho_alvo_inativo"


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
    # A altura é a que ESTA página pede, não a que o notebook pede.
    #
    # `notebook.get_preferred_height()` devolve o MAIOR natural entre as onze
    # páginas — é assim que um GtkNotebook funciona, e é o que ele precisa
    # saber para não encolher ao trocar de aba. Usar esse número aqui esticava
    # toda foto até a altura da aba mais alta, e o excedente aparecia como um
    # vão vazio entre as seções da página fotografada. Medido em 22/08/2026: a
    # Configurações pede 1005 px e a foto saía com 1925, com 900 px de folga
    # espalhada.
    pagina = notebook.get_nth_page(indice)
    _, natural_da_pagina = pagina.get_preferred_height()
    _, natural_da_tira = notebook.get_tab_label(pagina).get_preferred_height()
    natural = natural_da_pagina + natural_da_tira + _FOLGA_DA_TIRA
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


def _as_duas_abas_do_alvo() -> tuple[str, str, str] | None:
    """Uma aba que LÊ o alvo e uma que não lê, com o motivo — lidos do produto.

    O mapa é `HefestoApp._ALVO_POR_ABA` (`app/app.py`): `None` = a aba lê o
    alvo e a fita fica sensível; um texto = a aba se desqualifica, e o texto é
    o motivo que `set_alvo_inativo` guarda. Ler o mapa em vez de repetir aqui
    a resposta é o que impede a foto de continuar mostrando o estado de ontem
    quando uma onda ligar o leitor de mais uma aba.

    Devolve `(id da aba que lê, id da aba que não lê, motivo)`, ou `None` se o
    produto não puder ser importado ou o mapa não tiver os dois lados — caso
    em que a foto da fita inerte não sai, e o `main` diz por quê.
    """
    try:
        from hefesto_dualsense4unix.app.app import HefestoApp
    except Exception:
        return None
    mapa = getattr(HefestoApp, "_ALVO_POR_ABA", None)
    if not isinstance(mapa, dict):
        return None
    le = next((aba for aba, motivo in mapa.items() if motivo is None), None)
    # A Início é a primeira aba da tira e uma das SEIS que a Z2-8 passou a
    # esmaecer — é a que a leitura da documentação encontra primeiro. Se ela
    # sair do lado inerte um dia, qualquer outra aba com motivo serve.
    inerte = next(
        (
            aba
            for aba in ("tab_home_box", *mapa)
            if isinstance(mapa.get(aba), str)
        ),
        None,
    )
    if le is None or inerte is None:
        return None
    return le, inerte, str(mapa[inerte])


def _fotografar_o_cabecalho(  # type: ignore[no-untyped-def]
    builder, estado, saida, nome, *, host=None, motivo=None
) -> str:
    """Fotografa o `header_bar` — a fita do alvo, que NENHUMA foto mostrava.

    Achado de 14/08/2026, e ele é do tipo que só aparece quando alguém procura:
    o `main` deste script arranca o `main_notebook` do `root_box` e fotografa a
    janela pelo NOTEBOOK. O `header_bar` fica de fora das onze fotos de aba por
    construção do recorte — não porque não esteja na tela dela.

    Isso importa porque a fita "Ajustes vão para: …" e o selo "Editando: …"
    moram lá. A PROVA-DE-TELA-01 exige foto antes e depois; sem esta função,
    essa foto não existia.

    ``motivo`` (24/08/2026) É O ASSUNTO DA Z2-8
    -------------------------------------------

    Até a Z2-8 só a aba Configurações esmaecia a fita; agora Início, No jogo,
    Perfis, Sistema, Emulação e Navegação esmaecem também
    (`HefestoApp._ALVO_POR_ABA`). Sem `motivo` a fita fica como está — o
    retrato de uma aba que LÊ o alvo. Com `motivo`, quem esmaece é
    `ConfigActionsMixin.set_alvo_inativo`, o método de PRODUÇÃO: uma chamada a
    `set_sensitive(False)` daqui seria um segundo dono da regra, e a foto
    passaria a mentir no dia em que ela mudasse.

    A ORDEM AQUI É A CURA DE UMA MENTIRA POSSÍVEL
    ---------------------------------------------

    `show_all()` acende TUDO — inclusive os avisos que o produto esconde (o
    badge de vibração travada, o selo de edição, a faixa de números). Uma foto
    tirada logo depois dele mostraria uma tela que nunca existe.

    Por isso o `_render_slow_state` roda DE NOVO, depois do `show_all()`: quem
    decide o que fica escondido é a produção, não este script. E o
    `set_alvo_inativo` roda DEPOIS dele, pela mesma razão em espelho: o
    `_render_slow_state` reconstrói os chips da fita, e esmaecer antes seria
    esmaecer o que ele ainda vai refazer.
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
        host = _host_do_cabecalho(builder) if host is None else host
        # `_render_online` é quem escreve a linha da direita ("Conectado (4
        # controles) · USB + USB + BT + BT"). Ela NÃO sai do `_render_slow_state`
        # — na janela dela quem a escreve é a máquina de reconexão, a 0,5 Hz —,
        # e sem esta chamada a foto sairia com o default do glade, "Controle
        # Desconectado" em vermelho, ao lado de quatro chips de controle.
        host._render_online(estado)
        host._render_slow_state(estado)
        from hefesto_dualsense4unix.app.actions.config import ConfigActionsMixin

        ConfigActionsMixin.set_alvo_inativo(host, motivo is not None, motivo or "")
        _esperar_o_redimensionamento()
        arquivo = saida / f"{nome}.png"
        pixbuf = janela.get_pixbuf()
        pixbuf.savev(str(arquivo), "png", [], [])
    except Exception as exc:
        return f"  cabeçalho não fotografado ({exc})"
    estado_da_fita = (
        f"inerte — {motivo}" if motivo else "sensível: a aba lê o alvo"
    )
    return (
        f"  {arquivo.name}: o cabeçalho com {pixbuf.get_height()} px de "
        f"altura, fita {estado_da_fita}"
    )


def _fotografar_um_estado_do_inicio(saida: Path, nome: str) -> tuple[Path, str]:
    """Uma janela nova, um estado nomeado, um PNG. Devolve `(arquivo, recado)`.

    UMA JANELA POR ESTADO, e isso não é desperdício: `install_home_tab` é
    idempotente por `_home_installed`, então reusar o builder pintaria o
    segundo estado por cima dos widgets do primeiro — e o `_render_home` não
    desmonta card nenhum do frame de Controles que já esteja lá. Duas fotos
    saindo do MESMO conjunto de widgets é precisamente o defeito que este modo
    existe para medir.

    Fotografa o NOTEBOOK inteiro, como o `main` fotografa as abas, e não só o
    `tab_home_box`: assim a imagem é comparável, pixel a pixel, com a
    `readme_inicio.png` que a documentação publica.
    """
    delta, mascara, _oque = ESTADOS_DO_INICIO[nome]
    estado = _mesa_com(**delta)

    builder = Gtk.Builder()
    builder.add_from_file(str(GLADE))
    notebook = builder.get_object("main_notebook")
    if notebook is None:
        raise SystemExit("ERRO: `main_notebook` não existe no glade")
    janela = Gtk.OffscreenWindow()
    pai = notebook.get_parent()
    if pai is not None:
        pai.remove(notebook)
    janela.add(notebook)
    janela.set_size_request(LARGURA, ALTURA)
    _aplicar_tema(janela)
    janela.show_all()
    _assentar()

    recado = _montar_aba_inicio(
        builder, estado, draft=_rascunho_com_mascara(mascara)
    )
    notebook.set_current_page(0)
    _assentar()
    _esperar_o_redimensionamento()

    arquivo = saida / f"inicio_{nome}.png"
    janela.get_pixbuf().savev(str(arquivo), "png", [], [])
    janela.destroy()
    _assentar()
    return arquivo, recado


def fotografar_os_estados_do_inicio(destino: Path | None = None) -> int:
    """Um PNG por estado de `ESTADOS_DO_INICIO`, e o recibo do que cada um mostra.

    I10 (25/08/2026). Antes desta função a aba Início tinha UMA foto — a do
    caminho feliz, com dois controles de dublê — e cinco estados que nunca
    foram vistos por ninguém: a pausa, o aviso de grab, o controle externo, a
    exceção de Steam Input e a divergência de máscara. Uma prova de tela feita
    sobre a única foto que existe é prova sobre o caso que já estava certo.

    A promessa de privacidade do cabeçalho continua LITERALMENTE de pé: nada
    aqui fala com o daemon. Os dublês nascem no próprio script (o padrão de
    dois) e no `tests/fixtures/inventario_externos.json`, que é arquivo
    versionado e já passou pelos portões de anonimato de `tests/`.
    """
    saida = destino or DESTINO_ESTADOS_DO_INICIO
    saida.mkdir(parents=True, exist_ok=True)
    print(f"  {_desligar_animacoes()}")
    print(f"\n  {'estado':<22} {'arquivo':<32} tamanho")
    print("  " + "-" * 66)
    for nome in ESTADOS_DO_INICIO:
        arquivo, _recado = _fotografar_um_estado_do_inicio(saida, nome)
        kb = arquivo.stat().st_size // 1024
        print(f"  {nome:<22} {arquivo.name:<32} {kb:>4} KB")
    print("\n  o que cada estado passou a mostrar:")
    for nome, (_delta, _mascara, oque) in ESTADOS_DO_INICIO.items():
        print(f"    {nome:<22} {oque}")
    print(
        f"\n  {len(ESTADOS_DO_INICIO)} estado(s) em {saida}. "
        "Estas NÃO são as imagens do README."
    )
    return 0


def main(
    destino: str | None = None, *, mesa_cheia: bool = False, cinco: bool = False
) -> int:
    # `--cinco` é um modificador da mesa cheia, não um modo solto: sozinho ele
    # não teria fixture nenhum para ler.
    mesa_cheia = mesa_cheia or cinco
    if cinco:
        padrao, nomes = DESTINO_MESA_DE_CINCO, NOMES_MESA_DE_CINCO
        fixture, quantos = FIXTURE_MESA_DE_CINCO, CONTROLES_DA_MESA_DE_CINCO
    else:
        padrao, nomes = DESTINO_MESA_CHEIA, NOMES_MESA_CHEIA
        fixture, quantos = FIXTURE_MESA_CHEIA, CONTROLES_DA_MESA_CHEIA
    if not mesa_cheia:
        padrao, nomes = DESTINO_DOC, NOMES
    saida = Path(destino) if destino else padrao
    # O fixture é lido ANTES de o GTK montar coisa alguma: se ele não estiver
    # onde deveria, ninguém perde tempo montando uma janela para descobrir isso
    # dez segundos depois.
    estado_da_mesa = (
        _estado_da_mesa_cheia(fixture, quantos) if mesa_cheia else None
    )
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
    # Um host da Status para a execução inteira: ele é o dono da fita do alvo
    # no `header_bar` (ver `_host_do_cabecalho`), e dois donos empilhariam duas
    # fitas. A criação vem ANTES das fotos de aba de propósito — o `header_bar`
    # não está dentro da janela que elas retratam, então nada aqui move um
    # pixel delas.
    host_do_cabecalho = _host_do_cabecalho(builder)
    if estado_da_mesa is None:
        print(f"  {_injetar_card(builder)}")
    else:
        print(f"  fixture lido: {FIXTURE_MESA_CHEIA.relative_to(RAIZ)}")
        print(
            f"  {_injetar_cards_da_mesa_cheia(builder, estado_da_mesa, host_do_cabecalho)}"
        )
    print(f"  {_injetar_modos_de_gatilho(builder)}")
    print(f"  {_montar_aba_inicio(builder, estado_da_mesa)}")
    print(f"  {_montar_aba_no_jogo(builder, estado_da_mesa)}")
    print(f"  {_montar_aba_perfis(builder)}")
    print(f"  {_montar_aba_configuracoes(builder, fixture if mesa_cheia else None)}")
    # P10 (23/08/2026): as cinco que saíam do glade cru. A Emulação vem ANTES
    # da Navegação de propósito — a chave do teclado emulado DESENHA na
    # Navegação e o dono dela é o mixin da Emulação; invertendo a ordem, o
    # `install_input_tab` não teria o que acender.
    print(f"  {_montar_aba_lightbar(builder)}")
    print(f"  {_montar_aba_rumble(builder, estado_da_mesa)}")
    print(f"  {_montar_aba_sistema(builder)}")
    print(f"  {_montar_aba_emulacao(builder)}")
    print(f"  {_montar_aba_navegacao(builder)}")
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

    # Os nomes especiais seguem o prefixo do modo: com `--cinco` a foto
    # esticada e a do cabeçalho não podem sobrescrever as de quatro, que são
    # outra medição.
    prefixo = "mesa_de_cinco_" if cinco else ("mesa_cheia_" if mesa_cheia else "readme_")
    for nome_esticado in ABAS_ESTICADAS:
        # A Configurações também estoura nos modos de mesa — mais ainda neles,
        # que é o ponto do item 15 do TODO-INTEGRACAO: cinco controles na
        # seção mais larga da janela. Antes desta tradução de prefixo, a foto
        # esticada só existia no modo padrão, e a medição que a pedia era
        # justamente a da mesa.
        esticado = (
            nome_esticado.replace("readme_", prefixo, 1)
            if mesa_cheia
            else nome_esticado
        )
        if esticado in nomes:
            print(
                _fotografar_a_aba_inteira(
                    janela, notebook, saida, nomes.index(esticado), esticado
                )
            )
    aba_que_estoura = ABA_QUE_ESTOURA.replace("mesa_cheia_", prefixo, 1)
    if mesa_cheia and aba_que_estoura in nomes:
        print(
            _fotografar_a_aba_inteira(
                janela,
                notebook,
                saida,
                nomes.index(aba_que_estoura),
                aba_que_estoura,
            )
        )
    # As DUAS fotos do cabeçalho, e em todos os modos (24/08/2026). No padrão a
    # mesa é o mesmo dublê de dois que as abas mostram; nos modos de mesa é o
    # fixture. A segunda foto é a fita ESMAECIDA, que é o que a Z2-8 entregou e
    # o que nenhuma imagem deste repositório provava.
    estado_do_cabecalho = (
        ESTADO_PADRAO_DE_DOIS if estado_da_mesa is None else estado_da_mesa
    )
    nome_do_cabecalho = NOME_DO_CABECALHO.replace("readme_", prefixo, 1)
    print(
        _fotografar_o_cabecalho(
            builder,
            estado_do_cabecalho,
            saida,
            nome_do_cabecalho,
            host=host_do_cabecalho,
        )
    )
    duas_abas = _as_duas_abas_do_alvo()
    if duas_abas is None:
        print(
            "  fita inerte não fotografada: `HefestoApp._ALVO_POR_ABA` não "
            "tem os dois lados (uma aba que lê e uma que não lê)"
        )
    else:
        aba_que_le, aba_inerte, motivo = duas_abas
        print(
            _fotografar_o_cabecalho(
                builder,
                estado_do_cabecalho,
                saida,
                NOME_DO_CABECALHO_INERTE.replace("readme_", prefixo, 1),
                host=host_do_cabecalho,
                motivo=motivo,
            )
        )
        print(
            f"  a fita viva é a de `{aba_que_le}`; a inerte, a de "
            f"`{aba_inerte}` — as duas lidas de `_ALVO_POR_ABA`"
        )

    print(f"\n  {total} aba(s) em {saida}")
    # Z0-5 (24/08/2026): o recibo passa a nascer nos TRÊS destinos canônicos —
    # antes só o do README ganhava um. Um `destino` arbitrário (o argumento
    # posicional) continua sem recibo, pela mesma razão de sempre: "não toca
    # no repositório" (ver `USO`).
    modo = "--cinco" if cinco else ("--mesa-cheia" if mesa_cheia else "padrão")
    fixture_da_prova = fixture if mesa_cheia else None
    if saida in (DESTINO_DOC, DESTINO_MESA_CHEIA, DESTINO_MESA_DE_CINCO):
        print(
            f"  {_gravar_prova_da_foto(saida, modo=modo, fixture=fixture_da_prova)}"
        )
    if saida == DESTINO_DOC:
        print("  as imagens do README e de docs/usage/interface.md estão em dia.")
    if mesa_cheia:
        print(
            f"  mesa: {quantos} controles do fixture versionado "
            f"({fixture.name}). Estas NÃO são as imagens do README."
        )
    return 0


#: O que sai quando alguém erra a linha de comando. Em português, como o resto.
USO = (
    "uso: retratar_abas.py [DESTINO] [--mesa-cheia] [--cinco] [--estados-do-inicio]\n"
    "\n"
    "  sem argumento   atualiza as imagens da documentação\n"
    f"                  ({DESTINO_DOC.relative_to(RAIZ)})\n"
    "  DESTINO         grava nessa pasta e não toca no repositório\n"
    "  --mesa-cheia    fotografa com os QUATRO controles do fixture\n"
    f"                  versionado; destino padrão "
    f"{DESTINO_MESA_CHEIA.relative_to(RAIZ)}\n"
    "  --cinco         idem, com o fixture de CINCO controles — a mesa real\n"
    "                  desta casa, e o pior caso de largura; destino padrão\n"
    f"                  {DESTINO_MESA_DE_CINCO.relative_to(RAIZ)}\n"
    "  --estados-do-inicio\n"
    "                  um PNG por estado da aba Início — a pausa, o aviso de\n"
    "                  grab, o externo, o Steam Input, a divergência e a mesa\n"
    "                  vazia; destino padrão\n"
    f"                  {DESTINO_ESTADOS_DO_INICIO.relative_to(RAIZ)}\n"
)


#: O nome do recibo. Vive JUNTO das fotos de propósito: é o commit dele que faz
#: `docs/usage/assets` avançar quando nenhum pixel se move.
NOME_DA_PROVA = "PROVA-DA-FOTO.txt"


def _gravar_prova_da_foto(
    saida: Path, *, modo: str = "padrão", fixture: Path | None = None
) -> str:
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

    Z0-5 (24/08/2026), §2.2/M5 da sprint Z0-01: até aqui o recibo dizia QUANDO
    e O QUÊ, e nunca CONTRA QUE BANCADA. As fotos são dublê desde sempre — é a
    privacidade dela que exige isso — mas nada nelas ou ao lado delas dizia
    isso com todas as letras. `modo` e `fixture` são essa proveniência: qual
    dos quatro modos rodou, e qual arquivo (se algum) alimentou os dublês.
    """

    pngs = sorted(q for q in saida.glob("*.png") if q.is_file())
    fixture_txt = (
        str(fixture.relative_to(RAIZ))
        if fixture is not None
        else "nenhum — os dublês nascem fixos no próprio script (padrão de dois "
        "controles)"
    )
    linhas = [
        "# Recibo do ensaio de fotos — gerado por scripts/gui-captura/retratar_abas.py",
        "#",
        "# NÃO edite à mão. Rode o script; ele reescreve este arquivo.",
        "# Existe porque uma mudança de tela que não move pixel deixa as fotos",
        "# idênticas, e sem este recibo o portão das fotos ficaria vermelho para",
        "# sempre. Ver FOTO-QUE-NAO-MOVE-PIXEL-01 no próprio script.",
        "",
        f"ensaio:  {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"abas:    {len(pngs)}",
        f"modo:    {modo}",
        f"fixture: {fixture_txt}",
        "",
        "# toda linha destas imagens é dublê — nenhuma delas é medição desta ou",
        "# de qualquer máquina. Ver docs/usage/interface.md, \"Sobre as capturas\".",
        "",
        "# soma sha256 de cada foto, em ordem alfabética",
    ]
    for q in pngs:
        linhas.append(f"{hashlib.sha256(q.read_bytes()).hexdigest()}  {q.name}")
    (saida / NOME_DA_PROVA).write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return f"recibo do ensaio em {NOME_DA_PROVA} ({len(pngs)} soma[s])"


def _ler_argumentos_completo(
    argv: list[str],
) -> tuple[str | None, bool, bool, bool]:
    """Lê `[DESTINO] [--mesa-cheia] [--cinco] [--estados-do-inicio]`, em qualquer ordem.

    À mão e não com `argparse` de propósito: o `argparse` imprime "usage:" e
    "positional arguments" em inglês, e esta casa escreve em português — há
    portão que reprova.
    """
    destino: str | None = None
    mesa_cheia = False
    cinco = False
    estados = False
    for arg in argv:
        if arg == "--mesa-cheia":
            mesa_cheia = True
        elif arg == "--cinco":
            cinco = True
        elif arg == "--estados-do-inicio":
            estados = True
        elif arg.startswith("-"):
            raise SystemExit(f"argumento desconhecido: {arg}\n\n{USO}")
        elif destino is None:
            destino = arg
        else:
            raise SystemExit(f"destino demais: {arg}\n\n{USO}")
    return destino, mesa_cheia, cinco, estados


def _ler_argumentos(argv: list[str]) -> tuple[str | None, bool]:
    """As duas primeiras respostas do leitor acima, e não um segundo leitor.

    Continua existindo com ESTA aridade porque é assim que a suíte a mede
    (`test_a_mesa_cheia_na_foto.py`) e porque quem só quer saber "é mesa
    cheia?" não precisa saber de quantos controles.
    """
    destino, mesa_cheia, _cinco, _estados = _ler_argumentos_completo(argv)
    return destino, mesa_cheia


if __name__ == "__main__":
    _destino, _mesa_cheia, _cinco, _estados = _ler_argumentos_completo(sys.argv[1:])
    if _estados:
        raise SystemExit(
            fotografar_os_estados_do_inicio(Path(_destino) if _destino else None)
        )
    raise SystemExit(main(_destino, mesa_cheia=_mesa_cheia, cinco=_cinco))
