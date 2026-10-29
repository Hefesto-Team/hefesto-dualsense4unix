#!/usr/bin/env python3
"""A aba Jogar LÊ o que mostra — o interruptor, o chip, a máscara e os avisos.

POR QUE ESTA RÉGUA EXISTE, e o que ela mede foi fotografado em 02/09/2026 e
remedido no daemon do usuário em 03/09. Com ``native_mode false`` e
``gamepad_emulation.enabled false`` — logo ``mode_of_state`` = **desktop** — a
página publicada mostrava, ao mesmo tempo:

    interruptor      **Ligado**       (o `<input>` do arquivo nasce `checked`)
    fileira de modo  **Sony DualSense** aceso (`aba01.MODO_ACESO`, cravado)
    cartão do P2     **Xbox 360** aceso, com o daemon em `flavor=dualsense`
    coluna Atenção   selo verde **CERTO** sob o cabeçalho laranja "Atenção"
    conta            "3 avisos", com UM par `aviso-selo`/`aviso-texto` na página

Nenhuma dessas quatro coisas era atraso de tique: **não havia quem repintasse**.
A página tinha 11 `data-campo` e ZERO `data-hef-quando`, então nenhum ESTADO —
posição do interruptor, chip aceso, máscara acesa — chegava do daemon.

O QUE A RÉGUA COBRA, e cada item é uma forma de a cura morrer calada:

* o pacote **lê** os estados (posição, chip) das funções do produto (a máscara do
  cartão saiu da Jogar com o cartão em 28/10/2026), e a régua troca essas funções
  para provar que ele as segue — uma régua que comparasse textos passaria com o
  pacote digitando o valor;
* **daemon calado não pinta nada.** É a armadilha desta aba: ``mode_of_state({})``
  devolve ``desktop``, então um pacote descuidado acende **Ligado** sobre um
  estado que ninguém leu;
* a coluna **Atenção** sai de ``painel.avisos_do_estado`` — as seis fontes puras
  da GTK —, e **não** dos achados `certo` do Check-up;
* o selo do exame é o do produto: a linha antiga montava
  ``{"selo": …, **i}`` e o ``**i`` sobrescrevia o selo pretendido;
* a página publica os endereços, na quantidade certa — um a menos deixa uma
  posição acesa para sempre;
* o ``ACHADO_DO_TIMEOUT`` fala do ``ponte.TETOS`` de hoje, e não dos 250 ms que
  a cura já tinha substituído.
"""
from __future__ import annotations

import collections
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"


for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.interface import aba01, onde
from pacotes import LUGAR_VAZIO, Contexto
from pacotes import a01_jogar as aba

VIVO_NAVEGACAO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense",
                          "wrapper_used": None, "mascara_divergente": None},
    "paused": False,
    "controllers": [{"uniq": "aa", "connected": True, "player_slot": 1}],
}
VIVO_GAMEPAD_XBOX: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "xbox", "caminho": "xbox"},
    "paused": False,
}
VIVO_NATIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": True,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
}


def _ctx(state: dict[str, Any]) -> Contexto:
    return Contexto(state=state, mesa=[], conectados=[], estados={})


UNIQ_A = "aa:bb:cc:00:00:01"
UNIQ_B = "aa:bb:cc:00:00:02"


def _com_mesa(state: dict[str, Any], por_aparelho: dict[str, str] | None = None,
              quantos: int = 1) -> Contexto:
    """Um contexto com mesa VIVA — a máscara passou a ser de cada cartão.

    A mesa sai de `mesa_viva.mesa_do_estado`, que é o dono do valor por
    aparelho: ela lê `gamepad_emulation.por_aparelho` e cai na máscara da
    sessão para quem não escolheu. Montá-la à mão aqui seria escrever a regra
    de herança uma segunda vez, e a de cá envelheceria sozinha.
    """
    from hefesto_dualsense4unix.interface import mesa_viva

    conectados = [
        {"uniq": u, "connected": True, "player_slot": i, "transport": t}
        for i, (u, t) in enumerate(((UNIQ_A, "usb"), (UNIQ_B, "bluetooth"))[:quantos],
                                   start=1)
    ]
    cheio = {**state, "controllers": conectados}
    if por_aparelho is not None:
        emul = dict(cheio.get("gamepad_emulation") or {})
        emul["por_aparelho"] = por_aparelho
        cheio["gamepad_emulation"] = emul
    mesa = mesa_viva.mesa_do_estado(cheio, {})
    return Contexto(state=cheio, mesa=mesa, conectados=conectados, estados={})


@pytest.mark.parametrize(
    ("state", "posicao", "chip"),
    [
        (VIVO_NAVEGACAO, "desligado", "navegacao"),
        (VIVO_GAMEPAD_XBOX, "ligado", "xbox"),
        (VIVO_NATIVO, "desligado", "nativo"),
    ],
)
def test_o_interruptor_e_o_chip_saem_do_daemon(
    state: dict[str, Any], posicao: str, chip: str
) -> None:
    """Os três casos que a tela cravada errava — e o do meio é o que mais dói.

    Com o daemon em `desktop` a GTK marcaria "Controlar o PC"; a página mostrava
    **Ligado** + **Sony DualSense**. O `Ligado` até está certo (o Hefesto está no
    meio), mas por acaso: nada o tinha lido.

    COM UM CONTROLE NA MESA desde 22/09/2026: sem ninguém a fileira apaga
    inteira (`a01_jogar._a_fileira_com_a_mesa`, pedido), e o que esta régua
    mede é de onde vem o chip quando ele acende.
    """
    fora = aba.pacote(_com_mesa(state))
    assert fora["hef-posicao"] == posicao, (
        f"a posição do interruptor saiu {fora['hef-posicao']!r} com o daemon em "
        f"{painel.modo_vivo(state)!r}")
    assert fora["modo-aceso"] == chip, (
        f"o chip aceso saiu {fora['modo-aceso']!r} e o daemon está em "
        f"{painel.modo_vivo(state)!r}")


def test_o_daemon_calado_nao_acende_nada() -> None:
    """A armadilha desta aba: `mode_of_state({})` devolve **desktop**.

    Ele só devolve `None` para um NÃO-dicionário. Sem a guarda, um tique sem
    resposta acenderia **Ligado** e o chip **Navegação** sobre um estado que
    ninguém leu — a tela afirmando com o Hefesto fora do ar. O interruptor marca
    **Desligado** (a posição vazia caía no Ligado do gerador, 15/10/2026) e
    nenhum chip acende.
    """
    fora = aba.pacote(_ctx({}))
    assert fora["hef-posicao"] == "desligado"
    assert fora["modo-aceso"] == ""
    assert fora["cartoes"] == {}


def test_a_leitura_e_do_produto_e_nao_uma_copia(monkeypatch: Any) -> None:
    """Troca os dois leitores do produto e cobra que o pacote os siga."""
    from hefesto_dualsense4unix.app.actions import home_actions

    monkeypatch.setattr(painel, "hefesto_ligado", lambda _s: False)
    fora = aba.pacote(_com_mesa(VIVO_NAVEGACAO))
    assert fora["hef-posicao"] == "desligado", (
        "o pacote deixou de usar `painel.hefesto_ligado` — a posição virou cópia")

    monkeypatch.setattr(painel, "hefesto_ligado", lambda _s: True)
    monkeypatch.setattr(painel, "modo_vivo", lambda _s: "gamepad")
    monkeypatch.setattr(painel, "caminho_vivo", lambda _s: "xbox")
    monkeypatch.setattr(home_actions, "mascara_do_aparelho", lambda _s: "dualsense")
    fora = aba.pacote(_com_mesa(VIVO_NAVEGACAO))
    assert fora["modo-aceso"] == "xbox", (
        "o pacote deixou de usar `painel.modo_vivo` + `painel.caminho_vivo` — ou "
        "voltou a acender o chip de modo pela máscara")


VIVO_JOGO_SEM_ATALHO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "paused": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense",
                          "backend": "uhid", "wrapper_used": False},
    "window_detect_last_class": "steam_app_570",
    "controllers": [{"uniq": "aa", "connected": True, "player_slot": 1}],
}


@pytest.fixture()
def duas_listas_vazias(tmp_path: Any, monkeypatch: Any) -> Any:
    """As DUAS listas de recusa em disco, num diretório só deste teste."""
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    dispensados = tmp_path / "launch_dialog_dismissed.json"
    sem_wrapper = tmp_path / "jogos_sem_wrapper.txt"
    monkeypatch.setattr(lwd, "_dismissed_path", lambda **_: dispensados)
    monkeypatch.setattr(slo, "sem_wrapper_path", lambda *_a, **_k: sem_wrapper)
    return lwd, slo


def _coluna(ctx: Contexto) -> tuple[list[str], list[str]]:
    """Os selos e os textos do CANAL de avisos, na ordem da gravidade."""
    fora = aba.coluna_de_atencao(ctx)
    return [a["selo"] for a in fora], [a["texto"] for a in fora]


def test_o_aviso_do_jogo_sem_atalho_acende_na_coluna(duas_listas_vazias: Any) -> None:
    """Sem recusa nenhuma, a coluna acusa — e é do dono que a frase vem."""
    from hefesto_dualsense4unix.app.actions import home_actions

    selos, textos = _coluna(_ctx(VIVO_JOGO_SEM_ATALHO))
    assert selos == ["JOGO"], f"a coluna não acendeu o aviso do jogo: {selos!r}"
    assert textos == [home_actions.WRAPPER_MISSING_TEXT], (
        "o texto da coluna deixou de ser o do dono")


def test_a_bancada_desta_aba_abre_a_pagina_que_a_aba_publica() -> None:
    """A BANCADA desta aba mediu o VAZIO — medido em 06/09/2026, ONDA5-07-03."""
    if str(RAIZ / "scripts" / "tela") not in sys.path:
        sys.path.insert(0, str(RAIZ / "scripts" / "tela"))
    jogar_vivo = pytest.importorskip(
        "jogar_vivo", reason="a bancada precisa do Gtk/WebKit do sistema")
    assert jogar_vivo.PAGINA.exists(), (
        f"a bancada da aba Jogar abre {jogar_vivo.PAGINA}, que não existe — "
        "ela mede o vazio e sai verde")
    assert jogar_vivo.PAGINA.samefile(onde.PUBLICADO / "01-jogar.html"), (
        f"a bancada abre {jogar_vivo.PAGINA}, e não a página que esta aba publica")


def test_a_coluna_atencao_sai_das_fontes_da_gtk(monkeypatch: Any) -> None:
    """Troca `painel.avisos_do_estado` e cobra que os avisos venham de lá.

    As seis fontes de `painel.AVISOS_DA_TELA` já existiam em `home_actions` e
    quem as chamava era a BANCADA (`scripts/tela/jogar_vivo.py`). O produto
    mostrava, no lugar delas, o Check-up da aba Conexões — dois conjuntos
    disjuntos, e o da GTK era o que respondia pelas perguntas desta tela.
    """
    monkeypatch.setattr(
        painel, "avisos_do_estado",
        lambda _s: [{"selo": "PAUSA", "texto": "de outro dono", "fonte": "x"}])
    selos, textos = _coluna(_ctx(VIVO_NAVEGACAO))
    assert "PAUSA" in selos, (
        "o pacote deixou de chamar `painel.avisos_do_estado`")
    assert "de outro dono" in textos


def test_uma_fonte_que_quebra_nao_apaga_a_coluna(monkeypatch: Any) -> None:
    """A fonte que levanta vira um aviso com o selo `ERRO`, e a coluna não some.

    A política é a de `painel.avisos_do_estado`. Silêncio é o pior dos dois desfechos: ele se lê
    como "não havia achado nenhum".
    """
    def explode(_s: Any) -> dict[str, str]:
        raise RuntimeError("a divergência caiu")

    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    monkeypatch.setattr(aba, "_aviso_da_divergencia_de_mascara", explode)
    selos, _textos = _coluna(_ctx(VIVO_NAVEGACAO))
    assert "ERRO" in selos, (
        "a divergência quebrou e a coluna ficou vazia — o silêncio voltou")


def test_nenhuma_fonte_fala_sem_este_arquivo_saber(monkeypatch: Any) -> None:
    """Calado `painel.avisos_do_estado`, `coluna_de_atencao` não diz NADA em `VIVO_NAVEGACAO`.

    A mensagem diz o campo ``fonte`` de quem falou, que é o endereço da fonte nova: uma fonte que
    pergunte à máquina e não ao ``state`` faz as réguas da coluna responderem sobre o computador em
    que rodam (custou nove vermelhos em 11/09/2026).
    """
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    sobrando = aba.coluna_de_atencao(_ctx(VIVO_NAVEGACAO))
    assert sobrando == [], (
        "uma fonte que este arquivo não conhece acendeu a coluna: "
        + ", ".join(f"{a.get('fonte')} ({a.get('selo')})" for a in sobrando)
        + " — cale-a pelo nome no teste que a tiver por assunto")


def _em_trabalho() -> bool:
    arquivo = onde.BANCADA / "DIVERGENCIAS.md"
    if not arquivo.exists():
        return False
    corpo = arquivo.read_text(encoding="utf-8").split("\n---\n", 1)[-1]
    return "\n## 01-jogar.html" in f"\n{corpo}"


def _atras_so_por_endereco() -> bool:
    import importlib.util

    alvo = RAIZ / "scripts" / "check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("_desenho_aprovado", alvo)
    if spec is None or spec.loader is None:  # pragma: no cover
        return False
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    nome = "01-jogar.html"
    bancada, produto = onde.BANCADA / nome, onde.PUBLICADO / nome
    if not produto.exists() or bancada.read_bytes() == produto.read_bytes():
        return False
    return bool(modulo.so_mudou_endereco(nome))


@pytest.mark.parametrize("publicado", [False, True])
def test_a_pagina_publica_os_enderecos_na_quantidade_certa(publicado: bool) -> None:
    """Um endereço a menos deixa uma posição acesa para sempre."""
    if publicado and _em_trabalho():
        pytest.skip("01-jogar está declarada em trabalho no `mockup/DIVERGENCIAS.md`: "
                    "o produto recebe no `--publicar`, que é ato da costura")
    if publicado and _atras_so_por_endereco():
        pytest.skip("o produto está atrás da bancada SÓ POR ENDEREÇO — nenhum "
                    "pixel mudou. Fecha com: scripts/check_o_desenho_aprovado.py "
                    "--publicar-enderecos 01")
    corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(encoding="utf-8")
    por_campo = collections.Counter(
        aba01._campo_do_chip(m) for m in aba01.MODOS + aba01.DO_DESLIGADO)
    esperado = {
        "hef-posicao": len(aba01.INTERRUPTOR),
        "modo-aceso": por_campo["modo-aceso"],
        "steam-input-aceso": por_campo["steam-input-aceso"],
        "mascara-cartao": 0,
        "pendente-ha": 0,
    }
    for campo, quantos in esperado.items():
        achei = corpo.count(f'data-campo="{campo}" data-hef-alvo="classe"')
        assert achei == quantos, (
            f"{'publicado' if publicado else 'bancada'}: o endereço {campo!r} "
            f"aparece {achei} vezes e deviam ser {quantos}")
    cliques = corpo.count('data-gesto="mascara"')
    assert cliques == 0, (
        f"{'publicado' if publicado else 'bancada'}: o clique da máscara do cartão "
        f"voltou em {cliques} chips, e a máscara saiu da Jogar com o cartão")


def test_todo_endereco_que_o_pacote_emite_existe_na_pagina() -> None:
    """A régua nos DOIS sentidos — sem ela, o pacote emite para o vazio."""
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    for publicado in (True, False) if _em_trabalho() else (True,):
        corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(encoding="utf-8")
        for campo in fora:
            if campo in {"cartoes", "cobertura", "sem_dono", "blocos", LUGAR_VAZIO}:
                continue
            assert f'data-campo="{campo}"' in corpo, (
                f"o pacote emite {campo!r} e a página {'publicada' if publicado else 'do desenho'} "
                f"não tem onde escrever")


def test_a_cena_da_coluna_atencao_continua_com_um_aviso() -> None:
    """A CENA MUDOU POR ORDEM DE PRODUTO — 07/09/2026, e esta régua trocou de sinal."""
    for publicado in (False, True):
        corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(
            encoding="utf-8")
        onde_ = "publicado" if publicado else "bancada"
        for morto in ('class="aviso-item', 'class="col-atencao"',
                      'class="conta-avisos"',
                      'data-campo="aviso-vivo"', 'data-campo="atencao-conta"'):
            assert morto not in corpo, f"{onde_}: a coluna Atenção voltou ({morto!r})"
        assert corpo.count('data-gesto="reconectar"') == 1, (
            f"{onde_}: o botão Reconectar Controles sumiu — ele é o que ela "
            f"mandou DEIXAR, e uma régua que só proíbe passaria sem ele")


def test_os_metodos_da_troca_de_modo_tem_a_folga_do_produto() -> None:
    """`ACHADO_DO_TIMEOUT` afirmava 250 ms; `ponte.TETOS` já dava 2,0 s."""
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_IPC_TIMEOUT_S
    from pacotes import ponte

    from hefesto_dualsense4unix.daemon.protocolo_do_ipc import TETO_DO_GESTO_QUE_PEDE_O_P1_S

    for metodo in aba.METODOS_DA_TROCA_DE_MODO:
        esperado = (TETO_DO_GESTO_QUE_PEDE_O_P1_S if metodo == "gamepad.emulation.set"
                    else MODE_IPC_TIMEOUT_S)
        assert ponte.teto(metodo) == esperado, (
            f"{metodo} espera {ponte.teto(metodo)}s e o produto declara "
            f"{esperado}s para ele")
    assert "TETOS" in aba.ACHADO_DO_TIMEOUT and "2,0 s" in aba.ACHADO_DO_TIMEOUT, (
        f"o fato caduco voltou — o texto precisa nomear a tabela que já dá a "
        f"folga: {aba.ACHADO_DO_TIMEOUT!r}")


def test_o_arranjo_do_desktop_tem_teto_proprio_e_maior() -> None:
    """O passo que abre perfil não pode cair nos 250 ms do bridge.

    Ele está FORA de `METODOS_DA_TROCA_DE_MODO`, e sem esta régua esse "fora"
    seria um teto esquecido: `ponte.teto()` devolve o default de 250 ms para
    todo método ausente da tabela, em silêncio. É o mesmo furo que o
    `gamepad.mask.set` deixou aberto até 04/09.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_IPC_TIMEOUT_S
    from pacotes import ponte

    assert "desktop.arranjo.apply" in aba.METODOS, (
        "o arranjo do desktop saiu da declaração desta aba — e é o terceiro "
        "passo do modo Navegação."
    )
    teto = ponte.teto("desktop.arranjo.apply")
    assert teto > MODE_IPC_TIMEOUT_S, (
        f"o arranjo tem teto de {teto}s contra os {MODE_IPC_TIMEOUT_S}s da "
        "troca de modo. Ele faz MAIS: abre um perfil do disco além de falar "
        "com os devices."
    )
