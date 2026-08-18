"""O instrumento oficial não conseguia fotografar quatro controles — 14/08/2026.

A leva "mesa cheia" inteira é sobre **quatro jogadores aparecerem na tela**, e a
regra da casa (PROVA-DE-TELA-01) é que interface só fecha com foto antes e
depois. Só que `scripts/gui-captura/retratar_abas.py` alimentava as abas com
dublês fixos — Início e "No jogo" com DOIS controles sintéticos, Status com UM
card. Medido no dia em que ela conectou os quatro: rodado com a mesa cheia,
**nove dos dez PNGs saíram byte a byte idênticos** aos de quando havia um
controle só.

Isso não era defeito: o cabeçalho do script declara, como garantia de
privacidade, que ele **nunca** fala com o daemon. A cura não pode desfazer
isso — e não desfaz. O dublê passou a poder ser alimentado por
`tests/fixtures/state_full_quatro_controles.json`, que é payload real
**versionado e já anonimizado pelos portões de `tests/`**. Nada sai do daemon na
hora da foto; o dado entrou no repositório por um commit, que é a revisão.

AS TRÊS MORDIDAS
----------------

1. **Menos de quatro.** Fazendo o modo montar menos controles (um `[:2]` no
   `controllers`, ou um fixture truncado), `test_a_aba_status_da_mesa_cheia_tem_os_quatro_cards`,
   `test_a_aba_inicio_da_mesa_cheia_nomeia_os_quatro` e
   `test_o_modo_recusa_uma_mesa_incompleta` reprovam dizendo quantos sobraram.
2. **Falar com o daemon.** Tirando o desvio de `_maybe_fetch_externals` (ou
   pondo qualquer chamada de IPC no caminho da foto),
   `test_a_foto_da_mesa_cheia_nao_fala_com_o_daemon` reprova: ele roda a
   montagem inteira com TODA porta de IPC do pacote `app` trocada por uma que
   levanta exceção.
3. **Quebrar o modo padrão.** Mudando o destino, os nomes ou o dublê de dois,
   `test_o_modo_padrao_continua_sendo_o_de_dois_controles` e
   `test_a_mesa_cheia_nao_grava_nas_imagens_da_documentacao` reprovam. As dez
   imagens de `docs/usage/assets/` são as do README e do guia da interface: o
   modo novo é ADICIONAL, com pasta e prefixo próprios.
"""

from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`. Contra o stub
# (`Gtk.Box = object`) as contagens deste arquivo passariam sem que card nenhum
# existisse.
exigir_gi_real("a mesa cheia na foto")

import ast
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "3.0")

import pytest

# CI headless sem libcairo cai no stub do card (sem sub-widgets de desenho).
pytest.importorskip("cairo")

from gi.repository import Gtk

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "gui-captura" / "retratar_abas.py"

#: As portas de IPC do pacote `app`. Cada uma delas, chamada durante a foto,
#: traria estado da máquina dela para uma imagem que ninguém revisa.
_PORTAS_DE_IPC = (
    "call_async",
    "run_in_thread",
    "_safe_call",
    "_run_call",
    "daemon_state_full",
    "daemon_status_basic",
)


def _script() -> Any:
    """Importa o script de retrato como módulo, sem rodar o `main`."""
    assert SCRIPT.is_file(), f"{SCRIPT} sumiu — o retrato das abas é rotina desta casa"
    spec = importlib.util.spec_from_file_location("_retratar_abas_mesa_cheia", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _janela(modulo: Any) -> Any:
    """Monta o glade numa `Gtk.OffscreenWindow`, como o `main` monta.

    `OffscreenWindow` e não `Gtk.Window`: sob Xvfb não há gerenciador de
    janelas, a janela nunca é mapeada e o filho fica 1x1 para sempre — toda
    contagem de widget tirada dali passaria com qualquer desenho.
    """
    builder = Gtk.Builder()
    builder.add_from_file(str(modulo.GLADE))
    notebook = builder.get_object("main_notebook")
    assert notebook is not None, "`main_notebook` sumiu do glade"

    janela = Gtk.OffscreenWindow()
    pai = notebook.get_parent()
    if pai is not None:
        pai.remove(notebook)
    janela.add(notebook)
    janela.set_size_request(modulo.LARGURA, modulo.ALTURA)
    janela.show_all()
    modulo._assentar()
    return builder


def _descendentes(raiz: Any) -> list[Any]:
    """Todo widget abaixo de `raiz`, em qualquer profundidade."""
    achados: list[Any] = [raiz]
    if isinstance(raiz, Gtk.Container):
        for filho in raiz.get_children():
            achados.extend(_descendentes(filho))
    return achados


def _textos(raiz: Any) -> list[str]:
    """Os textos de todo `Gtk.Label` abaixo de `raiz`."""
    return [
        w.get_text()
        for w in _descendentes(raiz)
        if isinstance(w, Gtk.Label) and w.get_text()
    ]


def _cards(builder: Any) -> list[Any]:
    """Os `ControllerCard` que existem na aba Status agora."""
    from hefesto_dualsense4unix.app.widgets.controller_card import ControllerCard

    slot = builder.get_object("status_players_slot")
    assert slot is not None, "`status_players_slot` sumiu do glade"
    return [w for w in _descendentes(slot) if isinstance(w, ControllerCard)]


# ----------------------------------------------------------------------
# O fixture: é ele que torna a foto possível SEM falar com o daemon
# ----------------------------------------------------------------------


def test_o_fixture_da_mesa_cheia_e_versionado_e_anonimo() -> None:
    """A premissa de tudo: o dado já está no repositório, e já está mascarado.

    Se o fixture ganhar um MAC de verdade, um caminho de arquivo ou um nome de
    perfil, a foto passa a publicar dado da máquina dela — e os portões de
    anonimato não varrem imagens.
    """
    modulo = _script()
    caminho = modulo.FIXTURE_MESA_CHEIA

    assert caminho.is_file(), f"{caminho} sumiu — o modo mesa cheia depende dele"
    assert caminho.is_relative_to(RAIZ / "tests"), (
        f"o fixture da mesa cheia saiu de tests/ ({caminho}). Sob tests/ ele "
        "passa pelos portões de anonimato que garantem a máscara; fora de lá, "
        "por nenhum."
    )

    estado = json.loads(caminho.read_text(encoding="utf-8"))
    controles = estado.get("controllers", [])

    assert len(controles) == modulo.CONTROLES_DA_MESA_CHEIA, (
        f"o fixture tem {len(controles)} controles e a mesa cheia são "
        f"{modulo.CONTROLES_DA_MESA_CHEIA}"
    )
    for controle in controles:
        uniq = str(controle.get("uniq", ""))
        assert uniq.startswith("aabbcc"), (
            f"o `uniq` {uniq!r} do fixture não está mascarado. A máscara de "
            "`tests/` é mais severa que a de `docs/`: o portão de anonimato de "
            "fixtures é allowlist de PREFIXO, e um OUI de fabricante de "
            "verdade fica vermelho nele."
        )

    # Nenhuma string livre: só enumerações. Um caminho, um nome de jogo ou um
    # título de janela entrariam por aqui, e a foto os publicaria.
    def _strings(objeto: Any) -> list[str]:
        if isinstance(objeto, dict):
            return [t for v in objeto.values() for t in _strings(v)]
        if isinstance(objeto, list):
            return [t for v in objeto for t in _strings(v)]
        return [objeto] if isinstance(objeto, str) else []

    suspeitas = [
        texto
        for texto in _strings(estado)
        if "/" in texto or "@" in texto or texto.startswith("~")
    ]
    assert not suspeitas, (
        f"o fixture da mesa cheia ganhou texto que parece caminho ou endereço: "
        f"{suspeitas}. Ele é fotografado e a foto vai para o repositório."
    )


def test_o_modo_recusa_uma_mesa_incompleta(tmp_path: Path) -> None:
    """Uma foto de "mesa cheia" com dois controles é pior que nenhuma.

    Ela parece certa. É o mesmo defeito que a leva inteira existe para curar —
    a foto que não mostra o que diz mostrar —, e por isso a recusa é dura.
    """
    modulo = _script()
    truncado = tmp_path / "state_full_truncado.json"
    estado = json.loads(modulo.FIXTURE_MESA_CHEIA.read_text(encoding="utf-8"))
    estado["controllers"] = estado["controllers"][:2]
    truncado.write_text(json.dumps(estado), encoding="utf-8")
    modulo.FIXTURE_MESA_CHEIA = truncado

    with pytest.raises(SystemExit) as recusa:
        modulo._estado_da_mesa_cheia()

    assert "mesa cheia" in str(recusa.value).lower()


# ----------------------------------------------------------------------
# As três abas que a mesa cheia muda
# ----------------------------------------------------------------------


def test_a_aba_status_da_mesa_cheia_tem_os_quatro_cards() -> None:
    """Um card por controle, pelo caminho de produção (`_sync_status_cards`)."""
    modulo = _script()
    builder = _janela(modulo)
    recado = modulo._injetar_cards_da_mesa_cheia(
        builder, modulo._estado_da_mesa_cheia()
    )
    modulo._assentar()

    achados = _cards(builder)
    assert len(achados) == modulo.CONTROLES_DA_MESA_CHEIA, (
        f"a aba Status da mesa cheia saiu com {len(achados)} card(s), e a mesa "
        f"são {modulo.CONTROLES_DA_MESA_CHEIA}. É esta foto que a leva da mesa "
        f"cheia precisa mostrar. O script disse: {recado!r}"
    )


def test_a_aba_status_da_mesa_cheia_traz_o_frame_estado_de_volta() -> None:
    """CARD-ÚNICO-01 pelo avesso: com 2+ controles o frame "Estado" reaparece.

    Com um controle só ele some (o card diz tudo o que ele dizia). A foto de um
    controle nunca poderia mostrar isto, e é altura que a entrega 2.13 tem de
    contar.
    """
    modulo = _script()
    builder = _janela(modulo)
    modulo._injetar_cards_da_mesa_cheia(builder, modulo._estado_da_mesa_cheia())
    modulo._assentar()

    frame = builder.get_object("frame_status_estado")
    assert frame is not None and frame.get_visible(), (
        'o frame "Estado" saiu escondido da foto da mesa cheia. Com 2+ '
        "controles ele é a única voz de perfil e daemon — sem ele, a foto não "
        "mostra nem qual perfil está ativo."
    )
    assert any("Conectado" in t for t in _textos(frame)), (
        'o frame "Estado" saiu sem a linha de conexão preenchida — a foto '
        'mostraria "Consultando..." ao lado de quatro cards.'
    )


def test_a_aba_inicio_da_mesa_cheia_nomeia_os_quatro() -> None:
    """Quatro cartões na Início, e é onde a contradição do número aparece.

    Com um controle só, `player` e `player_slot` coincidem e a contradição é
    invisível. Com quatro, a Início escreve "Controle 4 — P1": o número da cor
    e o número do co-op, lado a lado, discordando.
    """
    modulo = _script()
    builder = _janela(modulo)
    recado = modulo._montar_aba_inicio(builder, modulo._estado_da_mesa_cheia())
    modulo._assentar()

    caixa = builder.get_object("tab_home_box")
    assert caixa is not None, "`tab_home_box` sumiu do glade"
    nomeados = [t for t in _textos(caixa) if t.startswith("Controle ")]

    assert len(nomeados) == modulo.CONTROLES_DA_MESA_CHEIA, (
        f"a aba Início da mesa cheia nomeou {len(nomeados)} controle(s) "
        f"({nomeados}), e a mesa são {modulo.CONTROLES_DA_MESA_CHEIA}. O "
        f"script disse: {recado!r}"
    )


def test_a_aba_no_jogo_da_mesa_cheia_tem_um_painel_por_jogador() -> None:
    """Quatro painéis — e é a foto que mostra o giroscópio só no cabo."""
    modulo = _script()
    builder = _janela(modulo)
    recado = modulo._montar_aba_no_jogo(builder, modulo._estado_da_mesa_cheia())
    modulo._assentar()

    caixa = builder.get_object("tab_no_jogo_box")
    assert caixa is not None, "`tab_no_jogo_box` sumiu do glade"
    titulos = [t for t in _textos(caixa) if t.startswith("Controle ")]

    assert len(titulos) == modulo.CONTROLES_DA_MESA_CHEIA, (
        f'a aba "No jogo" da mesa cheia saiu com {len(titulos)} painel(is) '
        f"({titulos}), e a mesa são {modulo.CONTROLES_DA_MESA_CHEIA}. O "
        f"script disse: {recado!r}"
    )


# ----------------------------------------------------------------------
# A garantia que não se toca
# ----------------------------------------------------------------------


def test_a_foto_da_mesa_cheia_nao_fala_com_o_daemon(monkeypatch: Any) -> None:
    """A montagem inteira roda com TODA porta de IPC minada.

    Não é verificação de texto: as portas de verdade são trocadas por uma
    função que levanta exceção, e a montagem roda por cima delas. Se qualquer
    caminho de produção usado pela foto pedir estado ao daemon vivo — o
    `_maybe_fetch_externals`, que enumera os externos, é o mais próximo —,
    este teste reprova nomeando a porta.

    O motivo é o de sempre, e está no cabeçalho do script: o estado real
    carrega o MAC dos controles dela, e estas fotos vão para o repositório sem
    revisão humana e sem portão que varra imagens.
    """
    tocadas: list[str] = []

    def _porta_minada(nome: str) -> Any:
        def _explode(*_args: Any, **_kwargs: Any) -> Any:
            tocadas.append(nome)
            raise AssertionError(f"a foto chamou {nome} — isso é o daemon vivo")

        return _explode

    minadas = 0
    for nome_modulo, modulo_app in list(sys.modules.items()):
        if not nome_modulo.startswith("hefesto_dualsense4unix.app"):
            continue
        for porta in _PORTAS_DE_IPC:
            if hasattr(modulo_app, porta):
                monkeypatch.setattr(
                    modulo_app, porta, _porta_minada(f"{nome_modulo}.{porta}")
                )
                minadas += 1

    assert minadas, (
        "nenhuma porta de IPC foi minada — o pacote `app` não estava "
        "importado, e este teste passaria sem testar nada"
    )

    modulo = _script()
    builder = _janela(modulo)
    estado = modulo._estado_da_mesa_cheia()
    recados = [
        modulo._injetar_cards_da_mesa_cheia(builder, estado),
        modulo._montar_aba_inicio(builder, estado),
        modulo._montar_aba_no_jogo(builder, estado),
    ]
    modulo._assentar()

    assert not tocadas, f"a foto da mesa cheia falou com o daemon: {tocadas}"
    assert len(_cards(builder)) == modulo.CONTROLES_DA_MESA_CHEIA, (
        "com as portas de IPC minadas a foto perdeu cards — o caminho da foto "
        f"depende do daemon em algum ponto. Recados: {recados}"
    )


def test_o_host_da_mesa_cheia_desvia_o_inventario_de_externos() -> None:
    """O desvio é EXPLÍCITO no fonte, e não acidental.

    `_render_slow_state` chama `_maybe_fetch_externals`, que faz
    `call_async("controller.list", {"external": True})`. O teste acima prova
    que a porta não é usada; este prova que alguém a fechou de propósito — sem
    isso, a próxima mudança na `status_actions` a reabre em silêncio.
    """
    arvore = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    funcao = next(
        (
            no
            for no in arvore.body
            if isinstance(no, ast.FunctionDef) and no.name == "_host_da_aba_status"
        ),
        None,
    )
    assert funcao is not None, "`_host_da_aba_status` sumiu do `retratar_abas.py`"

    definidos = {no.name for no in ast.walk(funcao) if isinstance(no, ast.FunctionDef)}
    assert "_maybe_fetch_externals" in definidos, (
        "o host da aba Status parou de sobrescrever `_maybe_fetch_externals`. "
        "O de produção pergunta ao daemon VIVO pelo inventário de externos, e "
        "a resposta chega por callback — depois de a foto já estar salva, o "
        "que torna o vazamento silencioso."
    )


# ----------------------------------------------------------------------
# O modo padrão, que não pode mudar
# ----------------------------------------------------------------------


def test_o_modo_padrao_continua_sendo_o_de_dois_controles() -> None:
    """Sem argumento, a foto é a de sempre — é ela que a documentação publica."""
    modulo = _script()
    builder = _janela(modulo)
    recado = modulo._montar_aba_inicio(builder)
    modulo._assentar()

    caixa = builder.get_object("tab_home_box")
    nomeados = [t for t in _textos(caixa) if t.startswith("Controle ")]

    assert len(nomeados) == 2, (
        f"o modo PADRÃO da aba Início mudou: saiu com {len(nomeados)} "
        f"controle(s) ({nomeados}) em vez dos 2 dublês de sempre. As imagens "
        "de docs/usage/assets/ são as do README e do guia da interface — "
        f"trocá-las é mudança que ninguém pediu. O script disse: {recado!r}"
    )


def test_a_mesa_cheia_nao_grava_nas_imagens_da_documentacao() -> None:
    """Pasta própria e prefixo próprio: o modo é ADICIONAL, não substituto."""
    modulo = _script()

    assert not modulo.DESTINO_MESA_CHEIA.is_relative_to(modulo.DESTINO_DOC), (
        f"o destino da mesa cheia ({modulo.DESTINO_MESA_CHEIA}) caiu dentro de "
        f"{modulo.DESTINO_DOC}. Além de misturar medição com documentação, "
        "isso engana o `test_as_fotos_acompanham_a_versao.py`, que mede a "
        "procedência das fotos do README pelo último commit da pasta."
    )
    assert not set(modulo.NOMES) & set(modulo.NOMES_MESA_CHEIA), (
        "um nome do modo mesa cheia colidiu com um do README: a foto de "
        "medição sobrescreveria a imagem da documentação."
    )
    assert all(n.startswith("mesa_cheia_") for n in modulo.NOMES_MESA_CHEIA)
    assert len(modulo.NOMES_MESA_CHEIA) == len(modulo.NOMES)


def test_a_linha_de_comando_separa_os_dois_modos() -> None:
    """`--mesa-cheia` é opt-in; sem ele, nada muda."""
    modulo = _script()

    assert modulo._ler_argumentos([]) == (None, False)
    assert modulo._ler_argumentos(["/tmp/olhar"]) == ("/tmp/olhar", False)
    assert modulo._ler_argumentos(["--mesa-cheia"]) == (None, True)
    assert modulo._ler_argumentos(["--mesa-cheia", "/tmp/x"]) == ("/tmp/x", True)
    with pytest.raises(SystemExit):
        modulo._ler_argumentos(["--o-que-e-isso"])


# ----------------------------------------------------------------------
# O ruído que sujava o `git status` a cada execução
# ----------------------------------------------------------------------


def test_a_foto_nao_depende_do_relogio() -> None:
    """As animações do GTK punham o relógio dentro da imagem.

    `readme_inicio.png` saía diferente a cada execução — ~3 mil pixels, delta 1
    a 2, sempre nas bordas dos dois botões segmentados SELECIONADOS. A causa
    não era ruído de gradiente: é a transição de CSS do estado `:checked`, que
    a foto pegava no meio. Com as animações desligadas, o GTK pinta o estado
    final na hora.
    """
    modulo = _script()
    ajustes = Gtk.Settings.get_default()
    if ajustes is None:  # display sem Settings: nada a travar
        pytest.skip("sem Gtk.Settings neste display")
    ajustes.set_property("gtk-enable-animations", True)

    recado = modulo._desligar_animacoes()

    assert ajustes.get_property("gtk-enable-animations") is False, (
        f"`_desligar_animacoes` não desligou nada ({recado!r}). O retrato "
        "volta a sair diferente a cada execução, e o `git status` volta a "
        "mentir depois de toda foto — com o CLAUDE.md mandando rodar o script "
        "antes de commitar."
    )


def test_o_main_desliga_as_animacoes_e_conhece_a_mesa_cheia() -> None:
    """Função que existe e não é chamada não conserta nada.

    Verificação sobre o AST do `main`: uma menção em comentário não desliga
    animação nenhuma nem monta card nenhum.
    """
    arvore = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    main = next(
        (
            no
            for no in arvore.body
            if isinstance(no, ast.FunctionDef) and no.name == "main"
        ),
        None,
    )
    assert main is not None, "o `main` sumiu do `retratar_abas.py`"

    chamadas = {
        no.func.id
        for no in ast.walk(main)
        if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
    }

    for exigida in (
        "_desligar_animacoes",
        "_estado_da_mesa_cheia",
        "_injetar_cards_da_mesa_cheia",
        "_fotografar_o_cabecalho",
    ):
        assert exigida in chamadas, (
            f"o `main` do retrato das abas parou de chamar `{exigida}`. A "
            "função continua no arquivo, os dez PNGs continuam saindo, e "
            "ninguém percebe."
        )
