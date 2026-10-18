"""«Teclas WASD» e «Setas» são do analógico: só a linha dele os oferece, e o desktop os atende.

Sprint OS-ANALOGICOS-OFERECEM-WASD-E-SETAS-SO-NA-LINHA-DELES-E-O-DESKTOP-OS-ATENDE-01.

Duas curas, cada uma com a sua régua:

* a lista (`por_grupo`, a fonte única que a aba 06 desenha) não oferece o token a linha de
  botão, que o recusaria depois («guardei, e X fica sem quem o atenda»);
* o laço do desktop (`teclas_do_analogico_no_desktop`, sem jogo aberto) emite a tecla pela
  MESMA função que a `TabelaNoJogo` usa com o jogo (`acoes_de_botao.direcoes_apertadas`), e a
  tecla é a união dos controles.

MORDIDAS (arrancadas e devolvidas): devolver o token à lista geral reprova a primeira; esvaziar
`TeclasDoAnalogicoNoDesktop.tick` reprova as do desktop (a chamada dele no laço morde em
`test_o_wasd_do_analogico_age_sem_a_emulacao_de_mouse.py`, não aqui); tirar o
`soltar_as_teclas_do_analogico` do `soltar_o_cursor` ou da troca de perfil deixa a tecla presa
e reprova as de soltura; tirar a condição do `_keyboard_device` reprova a do «Desativado»; ler
pelo hub quem o co-op numera reprova a do vpad que renasce.
"""
from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.daemon.subsystems import mouse as sub_mouse
from tests.unit.test_o_gatilho_vira_clique_sem_ligar_o_cursor import (
    _daemon_de_mentira,
    _estado,
    _saidas,
    _UinputPorDevice,
)

TECLAS = {acoes.TOKEN_WASD, acoes.TOKEN_SETAS}
LINHAS_DE_BOTAO = [b for b in acoes.BOTOES if b not in (acoes.EIXO_ESQUERDO, acoes.EIXO_DIREITO)]
CENTRO = 128


def _tokens(botao: str | None = None) -> set[str]:
    """Os tokens que a lista da linha oferece (a lista guarda o RÓTULO que a tela mostra)."""
    tokens = {
        acoes.token_do_rotulo(r) for _grupo, rotulos in acoes.por_grupo(botao) for r in rotulos
    }
    tokens.discard(None)
    return tokens


# -- a lista ------------------------------------------------------------------------


@pytest.mark.parametrize("linha", [b for b in LINHAS_DE_BOTAO if b != acoes.BOTAO_PS])
def test_a_linha_de_botao_nao_oferece_wasd_nem_setas(linha: str) -> None:
    # D-1710-OS-ANALOGICOS-OFERECEM-TECLAS-SO-NA-LINHA-DELES
    oferecidos = _tokens(linha)
    assert not oferecidos & TECLAS, f"a linha {linha} oferece o que é de analógico"
    assert oferecidos, f"a linha {linha} ficou sem lista"


@pytest.mark.parametrize("linha", [acoes.EIXO_ESQUERDO, acoes.EIXO_DIREITO])
def test_a_linha_do_analogico_oferece_wasd_e_setas(linha: str) -> None:
    assert _tokens(linha) >= TECLAS


@pytest.mark.parametrize("linha", [acoes.EIXO_ESQUERDO, acoes.EIXO_DIREITO])
def test_a_linha_do_analogico_nao_oferece_botao_do_mouse(linha: str) -> None:
    """O que o analógico não atende (`BTN_*`) não se oferece a ele, como o `resolver` decide."""
    assert not [t for t in _tokens(linha) if t.startswith("BTN_")]


def test_a_lista_geral_e_a_do_ps_seguem_como_eram() -> None:
    assert _tokens() >= TECLAS, "a lista geral perdeu as duas ações"
    assert not _tokens(acoes.BOTAO_PS) & TECLAS


@pytest.mark.parametrize("token", sorted(TECLAS))
def test_o_que_a_lista_esconde_e_o_que_o_resolver_recusa(token: str) -> None:
    """A lista e o `resolver` dizem o mesmo: o token que a linha de botão não oferece é o que cai em
    `sem_dono` ali, e na linha do analógico ele tem dono."""
    for linha in LINHAS_DE_BOTAO:
        if linha != acoes.BOTAO_PS:
            assert linha in acoes.resolver({linha: token})[2], f"{linha} atende {token}?"
    for linha in (acoes.EIXO_ESQUERDO, acoes.EIXO_DIREITO):
        assert linha not in acoes.resolver({linha: token})[2]


# -- a função única da deflexão -------------------------------------------------------


def test_a_deflexao_vira_direcao_pelo_limiar_e_a_diagonal_sao_duas() -> None:
    teclas = acoes.teclas_dos_analogicos({acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD})
    e, d = acoes.nome_da_direcao(acoes.EIXO_ESQUERDO, "esquerda"), acoes.nome_da_direcao(
        acoes.EIXO_ESQUERDO, "direita")
    c = acoes.nome_da_direcao(acoes.EIXO_ESQUERDO, "cima")
    assert acoes.direcoes_apertadas(teclas, [(32, 32, CENTRO, CENTRO)]) == {e, c}
    assert acoes.direcoes_apertadas(teclas, [(250, CENTRO, CENTRO, CENTRO)]) == {d}
    assert not acoes.direcoes_apertadas(teclas, [(80, 176, CENTRO, CENTRO)]), "menos de meia"
    assert not acoes.direcoes_apertadas(teclas, [(CENTRO,) * 4])
    # O direito não escolheu teclas: não vira nada.
    assert not acoes.direcoes_apertadas(teclas, [(CENTRO, CENTRO, 250, 250)])


def test_a_tecla_e_a_uniao_dos_controles() -> None:
    teclas = acoes.teclas_dos_analogicos({acoes.EIXO_ESQUERDO: acoes.TOKEN_SETAS})
    esq = acoes.nome_da_direcao(acoes.EIXO_ESQUERDO, "esquerda")
    dir_ = acoes.nome_da_direcao(acoes.EIXO_ESQUERDO, "direita")
    dois = [(20, CENTRO, CENTRO, CENTRO), (250, CENTRO, CENTRO, CENTRO)]
    assert acoes.direcoes_apertadas(teclas, dois) == {esq, dir_}
    mesmo_lado = [(20, CENTRO, CENTRO, CENTRO), (10, CENTRO, CENTRO, CENTRO)]
    assert acoes.direcoes_apertadas(teclas, mesmo_lado) == {esq}


# -- o desktop, sem o jogo aberto ----------------------------------------------------


class _MouseDoDesktop:
    """O `_mouse_device` do desktop: só o que a soltura toca."""

    def __init__(self) -> None:
        self.movidos = 0

    def dispatch(self, **_kw: Any) -> None:
        self.movidos += 1

    def soltar_o_clique_travado(self) -> None:
        pass

    def definir_ajuste(self, *_a: Any) -> None:
        pass

    def stop(self) -> None:
        pass


@pytest.fixture
def desktop(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, _UinputPorDevice]:
    mod = _UinputPorDevice()
    monkeypatch.setitem(sys.modules, "uinput", mod)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: getattr(d, "_outros", {}))
    monkeypatch.setattr(sub_mouse, "mover_o_cursor_pelo_giro", lambda *a, **k: None)
    daemon = _daemon_de_mentira()
    daemon._mouse_device = _MouseDoDesktop()
    daemon._teclas_do_analogico = None
    daemon._outros = {}
    # A «Função do teclado» ligada fora do jogo: o teclado do desktop existe.
    daemon._keyboard_device = types.SimpleNamespace(dispatch=lambda *_a: None, stop=lambda: None)
    return daemon, mod


def _perfil(**escolhas: str) -> Any:
    return types.SimpleNamespace(button_actions=escolhas or None, key_bindings=None)


def _tecla(mod: _UinputPorDevice) -> list[tuple[str, int]]:
    return [(n, v) for n, v in _saidas(mod)[1] if n.startswith("KEY_")]


def _tique(daemon: Any, **eixos: int) -> None:
    base = {"raw_lx": CENTRO, "raw_ly": CENTRO, "raw_rx": CENTRO, "raw_ry": CENTRO}
    sub_mouse.teclas_do_analogico_no_desktop(daemon, _estado(**{**base, **eixos}))


def test_o_analogico_em_wasd_digita_no_desktop_sem_jogo(desktop: Any) -> None:
    daemon, mod = desktop
    sub_mouse.trocar_a_tabela_no_jogo(daemon, _perfil(**{acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD}))
    _tique(daemon, raw_lx=32, raw_ly=32)
    assert sorted(_tecla(mod)) == [("KEY_A", 1), ("KEY_W", 1)], _tecla(mod)
    _tique(daemon, raw_lx=250)
    assert ("KEY_D", 1) in _tecla(mod) and ("KEY_A", 0) in _tecla(mod), _tecla(mod)
    _tique(daemon)
    assert ("KEY_D", 0) in _tecla(mod) and ("KEY_W", 0) in _tecla(mod), _tecla(mod)
    assert not [n for n, v in _saidas(mod)[0] if n in ("REL_X", "REL_Y")], "o cursor andou"


def test_as_setas_no_analogico_direito_do_desktop(desktop: Any) -> None:
    daemon, mod = desktop
    sub_mouse.trocar_a_tabela_no_jogo(daemon, _perfil(**{acoes.EIXO_DIREITO: acoes.TOKEN_SETAS}))
    _tique(daemon, raw_rx=250, raw_ry=250)
    assert sorted(_tecla(mod)) == [("KEY_DOWN", 1), ("KEY_RIGHT", 1)], _tecla(mod)


def test_o_de_fabrica_nao_abre_teclado_nenhum(desktop: Any) -> None:
    daemon, mod = desktop
    sub_mouse.trocar_a_tabela_no_jogo(daemon, _perfil())
    _tique(daemon, raw_lx=32)
    assert daemon._teclas_do_analogico is None
    assert not _tecla(mod)


def test_dois_controles_na_mesma_direcao_soltam_so_quando_o_ultimo_solta(
    desktop: Any,
) -> None:
    daemon, mod = desktop
    sub_mouse.trocar_a_tabela_no_jogo(daemon, _perfil(**{acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD}))
    daemon._outros = {"aa:bb:cc:00:00:02": (frozenset(), 0, 0)}
    daemon._coop_manager = types.SimpleNamespace(live_snapshots=lambda: {
        "aa:bb:cc:00:00:02": types.SimpleNamespace(lx=20, ly=CENTRO, rx=CENTRO, ry=CENTRO)})
    _tique(daemon, raw_lx=20)
    assert _tecla(mod).count(("KEY_A", 1)) == 1, _tecla(mod)
    _tique(daemon)  # o primário volta ao centro, o outro segue empurrando
    assert ("KEY_A", 0) not in _tecla(mod), "a tecla soltou com o outro controle ainda empurrando"
    daemon._coop_manager = types.SimpleNamespace(live_snapshots=lambda: {
        "aa:bb:cc:00:00:02": types.SimpleNamespace(
            lx=CENTRO, ly=CENTRO, rx=CENTRO, ry=CENTRO)})
    _tique(daemon)
    assert ("KEY_A", 0) in _tecla(mod), "o último soltou e a tecla ficou presa"


def test_quem_o_coop_numera_sem_vpad_nao_empurra_pelo_leitor_passivo(desktop: Any) -> None:
    """A regra das fontes é a dos gatilhos: o co-op numera o controle e o vpad dele renasce; o
    leitor passivo do hub veria o último valor, e a tecla ficaria presa até o vpad voltar."""
    daemon, mod = desktop
    sub_mouse.trocar_a_tabela_no_jogo(daemon, _perfil(**{acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD}))
    mac = "aa:bb:cc:00:00:03"
    daemon._outros = {mac: (frozenset(), 0, 0)}
    hub = types.SimpleNamespace(entradas=lambda u: {"lx": 20, "ly": CENTRO, "rx": CENTRO,
                                                    "ry": CENTRO})
    daemon._garantir_sensor_hub = lambda: hub
    daemon._coop_manager = types.SimpleNamespace(
        live_snapshots=lambda: {}, numeros_de_jogador=lambda: {mac: 2})
    _tique(daemon)
    assert ("KEY_A", 1) not in _tecla(mod), "o leitor passivo de quem o co-op numera empurrou"
    daemon._coop_manager = types.SimpleNamespace(live_snapshots=lambda: {},
                                                 numeros_de_jogador=lambda: {})
    _tique(daemon)
    assert ("KEY_A", 1) in _tecla(mod), "o controle fora do co-op não chegou pelo leitor passivo"


def test_trocar_de_perfil_solta_o_que_o_analogico_segurava(desktop: Any) -> None:
    daemon, mod = desktop
    sub_mouse.trocar_a_tabela_no_jogo(daemon, _perfil(**{acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD}))
    _tique(daemon, raw_lx=250)
    assert ("KEY_D", 1) in _tecla(mod)
    sub_mouse.trocar_a_tabela_no_jogo(daemon, _perfil())
    assert ("KEY_D", 0) in _tecla(mod), "a troca de perfil deixou a tecla presa"
    assert daemon._teclas_do_analogico is None


def test_a_emulacao_suspensa_solta_a_tecla(desktop: Any) -> None:
    """O laço que não despacha o mouse chama `soltar_o_cursor`, e a tecla solta junto."""
    daemon, mod = desktop
    sub_mouse.trocar_a_tabela_no_jogo(daemon, _perfil(**{acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD}))
    _tique(daemon, raw_lx=250)
    sub_mouse.soltar_o_cursor(daemon)
    assert ("KEY_D", 0) in _tecla(mod), "a suspensão deixou a tecla presa"


def test_a_parada_do_daemon_fecha_o_teclado_do_analogico(desktop: Any) -> None:
    """Parar a EMULAÇÃO DE MOUSE não solta a tecla (ela é do analógico, e o laço a atende sem o
    mouse); fechar o atendente, na troca de perfil e na parada do daemon, solta e destrói."""
    daemon, mod = desktop
    daemon.config.mouse_emulation_enabled = True
    sub_mouse.trocar_a_tabela_no_jogo(daemon, _perfil(**{acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD}))
    _tique(daemon, raw_lx=250)
    sub_mouse.stop_mouse_emulation(daemon, persist=False)
    assert ("KEY_D", 0) not in _tecla(mod), "parar o mouse soltou a tecla do analógico"
    _tique(daemon, raw_lx=250)  # o atendente segue vivo até o perfil trocar ou o daemon parar
    sub_mouse.fechar_as_teclas_do_analogico(daemon)
    assert ("KEY_D", 0) in _tecla(mod), "a parada do daemon deixou a tecla presa"
    assert daemon._teclas_do_analogico is None


def test_com_o_jogo_aberto_so_a_tabela_digita(desktop: Any) -> None:
    """O pad do jogo despachando: o desktop solta e a tabela (a chave) é quem emite."""
    daemon, mod = desktop
    sub_mouse.trocar_a_tabela_no_jogo(daemon, _perfil(**{acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD}))
    _tique(daemon, raw_lx=250)
    assert ("KEY_D", 1) in _tecla(mod)
    sub_mouse.despachar_no_jogo(daemon, _estado(), frozenset(), no_jogo=True)
    assert ("KEY_D", 0) in _tecla(mod), "o jogo abriu e a tecla do desktop ficou presa"


def test_o_teclado_so_dentro_do_jogo_cala_a_tecla_do_analogico(desktop: Any) -> None:
    daemon, mod = desktop
    daemon._teclado_so_no_jogo = True
    sub_mouse.trocar_a_tabela_no_jogo(
        daemon, types.SimpleNamespace(
            button_actions={acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD}, key_bindings=None,
            teclado_so_no_jogo=True))
    _tique(daemon, raw_lx=250)
    assert not _tecla(mod), "«Só dentro do jogo» digitou no desktop"


def test_o_teclado_desativado_cala_a_tecla_do_analogico(desktop: Any) -> None:
    """«Desativado» é mais que «Só dentro do jogo»: sem o teclado do desktop, o analógico não
    digita, e o que ele segurava solta quando o teclado desliga."""
    daemon, mod = desktop
    sub_mouse.trocar_a_tabela_no_jogo(daemon, _perfil(**{acoes.EIXO_ESQUERDO: acoes.TOKEN_WASD}))
    _tique(daemon, raw_lx=250)
    assert ("KEY_D", 1) in _tecla(mod)
    daemon._keyboard_device = None
    _tique(daemon, raw_lx=250)
    assert ("KEY_D", 0) in _tecla(mod), "desligar o teclado deixou a tecla do analógico presa"
    _tique(daemon, raw_lx=32)
    assert ("KEY_A", 1) not in _tecla(mod), "«Desativado» digitou no desktop"


def test_a_tabela_com_o_jogo_usa_a_uniao_dos_controles(
    desktop: Any,
) -> None:
    """A régua do jogo aberto segue verde pela mesma função, agora com a união dos controles."""
    daemon, mod = desktop
    daemon._osk_controller = types.SimpleNamespace(dispatch_token=lambda *a: None)
    daemon._outros = {"aa:bb:cc:00:00:02": (frozenset(), 0, 0)}
    daemon._coop_manager = types.SimpleNamespace(live_snapshots=lambda: {
        "aa:bb:cc:00:00:02": types.SimpleNamespace(lx=CENTRO, ly=CENTRO, rx=CENTRO, ry=20)})
    tabela = sub_mouse.TabelaNoJogo({acoes.EIXO_DIREITO: acoes.TOKEN_SETAS}, None, ligada=True)
    tabela.tick(daemon, _estado(raw_lx=CENTRO, raw_ly=CENTRO, raw_rx=CENTRO, raw_ry=CENTRO),
                frozenset())
    assert ("KEY_UP", 1) in _tecla(mod), "o analógico do outro controle não chegou à tabela"


# -- o perfil gravado antes de a lista encolher ---------------------------------------


def test_o_perfil_antigo_com_o_token_fora_da_lista_mostra_o_que_o_botao_faz(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any,
) -> None:
    """«Teclas WASD» num botão (e botão do mouse num analógico) carrega sem migração, cai em
    `sem_dono` e a linha mostra «— Nada —», que é o que o botão faz: a opção não existe mais na
    lista dela, e sem isto o `escrever()` se calaria e a linha seguiria no de fábrica.
    MORDIDA: devolver `acoes.rotulo(token)` em `_o_que_a_linha_mostra` reprova."""
    import pathlib

    monkeypatch.syspath_prepend(
        str(pathlib.Path(__file__).resolve().parents[2] / "src/hefesto_dualsense4unix/interface"))
    import pacotes
    from pacotes import a06_navegacao

    from tests.unit.test_a_06_nao_manda_para_o_vazio import (
        ESTADO,
        FALSO,
        MESA,
        _perfil_de_mentira,
    )

    _perfil_de_mentira(monkeypatch, tmp_path, button_actions={
        "cross": acoes.TOKEN_WASD, acoes.EIXO_ESQUERDO: "BTN_LEFT",
        "circle": acoes.TOKEN_CURSOR, "square": "KEY_ESC"})
    ctx = pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})
    mesa = a06_navegacao.pacote(ctx)["mesa"]
    nada = acoes.rotulo(acoes.TOKEN_NADA)
    assert mesa["acao-cross"] == nada, mesa["acao-cross"]
    assert mesa[f"acao-{acoes.EIXO_ESQUERDO}"] == nada, mesa[f"acao-{acoes.EIXO_ESQUERDO}"]
    # O que a lista da linha ainda oferece segue com o próprio nome (a resposta da linha avisa).
    # O cursor num botão deixou de ser oferecido (CURSOR-E-ROLAGEM-SO-NA-LINHA-QUE-OS-ATENDE-01).
    assert mesa["acao-circle"] == nada
    assert mesa["acao-square"] == "Esc"
