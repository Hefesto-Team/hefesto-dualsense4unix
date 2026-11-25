"""D-2511-O-PROGRAMA-GRAVADO-NO-BOTAO-VIRA-NADA: o programa gravado no botão vale «— Nada —».

«Escolher um programa…» (`__PROGRAMA__`) saiu da lista de cada linha da aba Navegação, e o perfil
que já o tinha gravado ficava com três respostas para uma pergunta: a tela dizia «— Nada —», o
arquivo dizia «programa» e seis botões (Círculo, Quadrado e as quatro direções) seguiam emitindo o
de fábrica. A leitura tem um dono, `core/acoes_de_botao.tabela_efetiva`: o que está em
`SEM_ATENDENTE` se lê como `__NADA__`, e daí saem a linha da tela, os botões calados e as sacolas
do `resolver`.

Os quatro lados: a tela (as 21 linhas), o aparelho no caminho do computador (o `ProfileManager`
com os dois devices), o aparelho com o jogo aberto (a `TabelaNoJogo` com os dois devices) e o
salvar (o gesto da linha regrava `__NADA__` no perfil de jogo, ou no `maquina.json` e no arquivo
do Freestyle; sem salvar, o arquivo fica byte a byte). O PS fica de fora de propósito: o degrau
da máquina é a saída de emergência dele.

MORDIDAS (cada uma reprova nomeando as linhas): arrancar a conversão do `tabela_efetiva` reprova
a tela e o caminho do computador nas linhas de fábrica; arrancar também o desvio do `resolver`
reprova o jogo aberto; arrancar a conversão do `_com_a_linha` (a06_navegacao) reprova o salvar, e
arrancar o `_acertar_o_arquivo_do_perfil` reprova só o arquivo do Freestyle, e arrancar a exceção
do PS do `sem_o_que_ninguem_faz` reprova a régua do PS.
"""
from __future__ import annotations

import json
import pathlib
import sys
import types
from typing import Any

import pytest

from hefesto_dualsense4unix.core import acoes_de_botao as acoes
from hefesto_dualsense4unix.daemon.subsystems.mouse import TabelaNoJogo
from hefesto_dualsense4unix.integrations.uinput_keyboard import UinputKeyboardDevice
from hefesto_dualsense4unix.integrations.uinput_mouse import UinputMouseDevice
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import Profile
from tests.unit.test_o_gatilho_vira_clique_sem_ligar_o_cursor import (
    _daemon_de_mentira,
    _estado,
    _saidas,
    _UinputPorDevice,
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

LINHAS = [b for b in acoes.BOTOES if b != acoes.BOTAO_PS]
EIXOS = (acoes.EIXO_ESQUERDO, acoes.EIXO_DIREITO)
DE_FABRICA_QUE_ESCAPAVAM = ["circle", "square", "dpad_up", "dpad_down", "dpad_left", "dpad_right"]
NADA = acoes.rotulo(acoes.TOKEN_NADA)
FORTE = 255
CENTRO = 128
O_QUE_O_EIXO_EMITE = {
    acoes.EIXO_ESQUERDO: {"REL_X", "REL_Y"},
    acoes.EIXO_DIREITO: {"REL_WHEEL", "REL_HWHEEL"},
}


def _ainda_emite(linha: str, saiu: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """O que a própria linha ainda emite: o toque (valor 1) ou o movimento do próprio eixo."""
    if linha in EIXOS:
        return [e for e in saiu if e[0] in O_QUE_O_EIXO_EMITE[linha]]
    return [e for e in saiu if e[1] == 1]


def test_a_lista_de_nenhuma_linha_oferece_o_programa() -> None:
    """A premissa: a opção saiu da lista de cada linha, então o que sobra é só o gravado antigo."""
    for linha in LINHAS:
        oferecidos = {r for _g, rotulos in acoes.por_grupo(linha) for r in rotulos}
        assert acoes.rotulo(acoes.TOKEN_PROGRAMA) not in oferecidos, linha


@pytest.mark.parametrize("linha", LINHAS)
def test_a_tabela_efetiva_le_o_programa_como_nada(linha: str) -> None:
    assert acoes.tabela_efetiva({linha: acoes.TOKEN_PROGRAMA})[linha] == acoes.TOKEN_NADA
    assert linha in acoes.botoes_calados({linha: acoes.TOKEN_PROGRAMA})
    _mouse, _teclado, sem_dono = acoes.resolver({linha: acoes.TOKEN_PROGRAMA})
    assert linha not in sem_dono, f"{linha}: o programa gravado ainda cai na sacola sem dono"


def test_o_ps_continua_com_o_degrau_da_maquina() -> None:
    """O PS fica fora da leitura: o que ele guarda vai ao `ps_solo`, que dá ao programa o degrau
    da máquina (a saída de emergência), e o PS não é calado nem lido como «— Nada —»."""
    from hefesto_dualsense4unix.core import acoes_do_gesto as ag
    from hefesto_dualsense4unix.daemon.subsystems.hotkey import _a_metade_da_maquina

    gravado = {acoes.BOTAO_PS: acoes.TOKEN_PROGRAMA}
    assert acoes.tabela_efetiva(gravado)[acoes.BOTAO_PS] == acoes.TOKEN_PROGRAMA
    assert acoes.BOTAO_PS not in acoes.botoes_calados(gravado)
    escolha = acoes.acao_do_ps(gravado)
    assert escolha == acoes.TOKEN_PROGRAMA
    maquina = types.SimpleNamespace(ps_button_action="steam")
    assert _a_metade_da_maquina(maquina, escolha) == ag.ABRIR_A_STEAM


def test_a_tela_mostra_nada_nas_linhas_com_o_programa_gravado() -> None:
    from pacotes import a06_navegacao

    por_linha = a06_navegacao._linhas_dos_botoes(
        {"button_actions": {b: acoes.TOKEN_PROGRAMA for b in LINHAS}})
    erradas = {c: r for c, r in por_linha.items()
               if c != f"{a06_navegacao.PREFIXO_DA_ACAO}{acoes.BOTAO_PS}"
               and r != NADA}
    assert not erradas, f"a tela não mostra «— Nada —»: {erradas}"


def _uinput(monkeypatch: pytest.MonkeyPatch) -> _UinputPorDevice:
    mod = _UinputPorDevice()
    monkeypatch.setitem(sys.modules, "uinput", mod)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.subsystems.poll.gatilhos_de_cada_controle",
        lambda d: {})
    return mod


def _saiu(mod: _UinputPorDevice) -> list[tuple[str, int]]:
    mouse, teclado = _saidas(mod)
    return [*mouse, *teclado]


def _no_computador(monkeypatch: pytest.MonkeyPatch, linha: str, token: str,
                   ) -> list[tuple[str, int]]:
    """O que o aparelho emite ao apertar a linha (ou empurrar o analógico a fundo), pelo caminho
    do computador: o `ProfileManager` entrega o perfil aos dois devices."""
    mod = _uinput(monkeypatch)
    mouse, teclado = UinputMouseDevice(), UinputKeyboardDevice()
    assert mouse.start() and teclado.start()
    gerente = ProfileManager(
        controller=None, keyboard_device=teclado,
        mouse_device_provider=lambda: mouse, keyboard_device_provider=lambda: teclado)
    perfil = Profile(name="ensaio", match={"type": "any"}, button_actions={linha: token})
    gerente.apply_keyboard(perfil)
    gerente.apply_button_actions(perfil)
    for gravado in mod.saiu.values():
        gravado.clear()
    eixos = dict(lx=CENTRO, ly=CENTRO, rx=CENTRO, ry=CENTRO, l2=0, r2=0)
    if linha in EIXOS:
        eixos.update(lx=FORTE, rx=FORTE)
    for i, apertado in enumerate((frozenset({linha}), frozenset())):
        for tique in range(5):
            mouse.dispatch(buttons=apertado, now=1.0 + i + tique * 0.02, **eixos)
        teclado.dispatch(apertado)
    return _saiu(mod)


def _com_o_jogo_aberto(monkeypatch: pytest.MonkeyPatch, linha: str, token: str,
                       ) -> list[tuple[str, int]]:
    mod = _uinput(monkeypatch)
    daemon = _daemon_de_mentira()
    daemon._osk_controller = types.SimpleNamespace(dispatch_token=lambda *a: None)
    tabela = TabelaNoJogo({linha: token}, None, ligada=True)
    forte = linha in EIXOS
    estado = _estado(raw_lx=FORTE if forte else CENTRO, raw_ly=CENTRO,
                     raw_rx=FORTE if forte else CENTRO, raw_ry=CENTRO)
    tabela.tick(daemon, estado, frozenset({linha}))
    tabela.tick(daemon, estado, frozenset())
    tabela.fechar()
    return _saiu(mod)


@pytest.mark.parametrize("linha", LINHAS)
def test_o_aparelho_cala_a_linha_com_o_programa_no_caminho_do_computador(
    monkeypatch: pytest.MonkeyPatch, linha: str,
) -> None:
    com_nada = _no_computador(monkeypatch, linha, acoes.TOKEN_NADA)
    com_programa = _no_computador(monkeypatch, linha, acoes.TOKEN_PROGRAMA)
    assert com_programa == com_nada, (
        f"{linha}: com o programa gravado o aparelho emite {com_programa}, e com «— Nada —» "
        f"emite {com_nada}")
    assert not _ainda_emite(linha, com_programa), f"{linha} ainda emite: {com_programa}"


@pytest.mark.parametrize("linha", LINHAS)
def test_o_aparelho_cala_a_linha_com_o_programa_com_o_jogo_aberto(
    monkeypatch: pytest.MonkeyPatch, linha: str,
) -> None:
    com_nada = _com_o_jogo_aberto(monkeypatch, linha, acoes.TOKEN_NADA)
    com_programa = _com_o_jogo_aberto(monkeypatch, linha, acoes.TOKEN_PROGRAMA)
    assert com_programa == com_nada, (
        f"{linha}: com o programa gravado e o jogo aberto o aparelho emite {com_programa}, "
        f"e com «— Nada —» emite {com_nada}")
    assert not _ainda_emite(linha, com_programa), f"{linha} ainda emite: {com_programa}"


@pytest.mark.parametrize("linha", DE_FABRICA_QUE_ESCAPAVAM)
def test_o_de_fabrica_nao_escapa_nos_seis_que_o_mouse_refazia(
    monkeypatch: pytest.MonkeyPatch, linha: str,
) -> None:
    """D-2511-O-PROGRAMA-GRAVADO-NO-BOTAO-VIRA-NADA.

    Sem o gravado o de fábrica emite (o controle da régua): o silêncio vem da leitura."""
    sem_nada = _no_computador(monkeypatch, linha, acoes.padrao()[linha])
    assert [e for e in sem_nada if e[1] == 1], f"{linha}: o de fábrica já não emite, a régua mente"


def _ctx_e_ponte(nome: str) -> tuple[Any, Any]:
    import pacotes

    class _Ponte:
        def __getattr__(self, _nome: str) -> Any:
            return lambda *a, **k: True

    ctx = pacotes.Contexto(
        state={"active_profile": nome}, mesa=[], conectados=[], estados={})
    return ctx, _Ponte()


def _gravar_noutra_linha(nome: str) -> None:
    from pacotes import a06_navegacao

    ctx, ponte = _ctx_e_ponte(nome)
    a06_navegacao._gravar_a_linha(ctx, ponte, "triangle", "BTN_MIDDLE")


def _botoes_do_disco(arquivo: pathlib.Path, *caminho: str) -> dict[str, str]:
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    for chave in caminho:
        dados = dados.get(chave) or {}
    return dict(dados)


GRAVADOS = {"cross": acoes.TOKEN_PROGRAMA, "dpad_up": acoes.TOKEN_PROGRAMA,
            "options": acoes.TOKEN_PROGRAMA}


def test_o_salvar_do_jogo_grava_nada_no_lugar_do_programa_e_sem_salvar_o_arquivo_fica() -> None:
    from pacotes import a06_navegacao

    from hefesto_dualsense4unix.profiles import loader

    perfil = Profile.model_validate({
        "name": "Jogo ensaio", "match": {"type": "criteria", "window_class": ["jogo ensaio"]},
        "button_actions": dict(GRAVADOS)})
    caminho = pathlib.Path(loader.save_profile(perfil))
    antes = caminho.read_bytes()

    a06_navegacao._linhas_dos_botoes({"button_actions": dict(GRAVADOS)})
    gerente = ProfileManager(controller=None)
    gerente.apply_button_actions(loader.load_profile("Jogo ensaio"))
    assert caminho.read_bytes() == antes, "ler e aplicar mexeu no arquivo: migração calada"

    _gravar_noutra_linha("Jogo ensaio")
    guardado = _botoes_do_disco(caminho, "button_actions")
    assert guardado.get("triangle") == "BTN_MIDDLE", guardado
    for linha in GRAVADOS:
        assert guardado.get(linha) == acoes.TOKEN_NADA, (
            f"{linha} segue {guardado.get(linha)!r} no perfil de jogo: {guardado}")
    assert acoes.TOKEN_PROGRAMA not in caminho.read_text(encoding="utf-8")


def test_o_salvar_no_computador_grava_nada_no_maquina_json() -> None:
    from pacotes import a06_navegacao

    from hefesto_dualsense4unix.profiles import loader

    loader.seed_default_presets()
    base = loader.load_profile(loader.NOME_DO_PADRAO)
    caminho = pathlib.Path(loader.save_profile(
        base.model_copy(update={"button_actions": dict(GRAVADOS)})))
    antes = caminho.read_bytes()

    a06_navegacao._linhas_dos_botoes({"button_actions": dict(GRAVADOS)})
    assert caminho.read_bytes() == antes

    _gravar_noutra_linha(loader.NOME_DO_PADRAO)
    from hefesto_dualsense4unix.utils.maquina import caminho_da_maquina

    maquina = caminho_da_maquina()
    guardado = _botoes_do_disco(maquina, "computador", "global", "button_actions")
    assert guardado.get("triangle") == "BTN_MIDDLE", guardado
    for linha in GRAVADOS:
        assert guardado.get(linha) == acoes.TOKEN_NADA, (
            f"{linha} segue {guardado.get(linha)!r} no maquina.json: {guardado}")
    assert acoes.TOKEN_PROGRAMA not in maquina.read_text(encoding="utf-8")
    do_freestyle = _botoes_do_disco(caminho, "button_actions")
    for linha in GRAVADOS:
        assert do_freestyle.get(linha) == acoes.TOKEN_NADA, (
            f"{linha} segue {do_freestyle.get(linha)!r} no arquivo do Freestyle: {do_freestyle}")
