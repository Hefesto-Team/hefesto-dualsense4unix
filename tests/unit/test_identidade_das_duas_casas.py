"""A régua das DUAS CASAS — o app dela e o de desenvolvimento, lado a lado.

Nasceu em 29/08/2026, do pedido dela: *"Ele é instalado como OUTRO APP com a
logo alterada em dev"* e *"quero garantir que ele funcione enquanto eu tenho a
versão estável instalada"*.

O QUE ESTE ARQUIVO PROTEGE, e por que cada teste morde
------------------------------------------------------
1. **Que o padrão não mudou.** `utils/identidade.py` centralizou literais que
   estavam cravados em oito arquivos. Se um deles tiver sido transcrito errado,
   a máquina DELA muda — perfil noutro diretório, ícone que some da dock,
   daemon que não sobe. Os testes de literal aqui são chatos de propósito.
2. **Que as duas casas não se alcançam.** `app/main.py:_kill_previous_instances`
   mata por `pgrep -f`, que casa SUBSTRING, com SIGTERM e depois SIGKILL. Um
   nome mal escolhido (`...-gui-dev` em vez de `hefesto-dev-...-gui`) faz um app
   matar o outro, sem install nenhum e sem erro nenhum.
3. **Que o código e o `.desktop` concordam.** O `StartupWMClass` do `.desktop` e
   o `res_class` que a janela publica são dois arquivos que nada obriga a
   concordar. Não havia régua para isso — e foi assim que duas janelas do
   produto nasceram com `app_id` errado e ficaram (`app/widgets/mapa_da_mesa.py`,
   `app/widgets/calibrar_entradas.py`).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.utils import identidade

RAIZ = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------
# 1. O PADRÃO NÃO MUDOU — cada literal é o que estava cravado antes
# --------------------------------------------------------------------------
def test_sem_variante_no_ambiente_a_casa_e_a_dela(monkeypatch):
    monkeypatch.delenv(identidade.VARIANTE_ENV, raising=False)
    assert identidade.atual() is identidade.ESTAVEL


@pytest.mark.parametrize(
    ("campo", "esperado"),
    [
        ("slug", "hefesto-dualsense4unix"),
        ("app_id", "hefesto-dualsense4unix"),
        ("wm_instance", "hefesto-dualsense4unix"),
        ("wm_class", "Hefesto-Dualsense4Unix"),
        ("nome_longo", "Hefesto - Dualsense4Unix"),
        ("icone", "hefesto-dualsense4unix"),
        ("unit_daemon", "hefesto-dualsense4unix.service"),
        ("entrypoint_gui", "hefesto-dualsense4unix-gui"),
        ("entrypoint_cli", "hefesto-dualsense4unix"),
    ],
)
def test_o_estavel_tem_os_literais_de_sempre(campo, esperado):
    """Cada um destes estava cravado no código antes de 29/08/2026.

    Mudar qualquer um muda a MÁQUINA DELA: o `slug` é onde os perfis moram, o
    `unit_daemon` é a unit que roda agora, o `wm_class` é o que a dock usa para
    achar o ícone.
    """
    assert getattr(identidade.ESTAVEL, campo) == esperado


def test_o_slug_do_estavel_e_o_diretorio_de_config_de_verdade(monkeypatch):
    """A prova de ponta a ponta: o slug chega mesmo no `platformdirs`."""
    monkeypatch.delenv(identidade.VARIANTE_ENV, raising=False)
    import importlib

    from hefesto_dualsense4unix.utils import xdg_paths

    importlib.reload(xdg_paths)
    try:
        assert xdg_paths.config_dir().name == "hefesto-dualsense4unix"
        assert xdg_paths.IPC_SOCKET_DEFAULT_NAME == "hefesto-dualsense4unix.sock"
    finally:
        importlib.reload(xdg_paths)


def test_variante_desconhecida_cai_no_estavel():
    """Um typo no ambiente não pode separar o app da casa dela.

    O padrão seguro é NÃO se isolar: um `HEFESTO_VARIANTE=deb` que virasse uma
    casa nova deixaria os perfis dela para trás sem uma linha de aviso.
    """
    for lixo in ("", "  ", "DEV ", "beta", "1", "verdadeiro"):
        casa = identidade.identidade_de(lixo)
        if lixo.strip().casefold() == "dev":
            continue
        assert casa is identidade.ESTAVEL, lixo


def test_dev_no_ambiente_muda_a_casa_inteira(monkeypatch):
    monkeypatch.setenv(identidade.VARIANTE_ENV, "dev")
    assert identidade.atual() is identidade.DEV
    import importlib

    from hefesto_dualsense4unix.utils import xdg_paths

    importlib.reload(xdg_paths)
    try:
        assert xdg_paths.config_dir().name == "hefesto-dev-dualsense4unix"
        # O socket isola pelo DIRETÓRIO, não pelo nome do arquivo — é o que
        # impede o app de dev de sequestrar o daemon dela (mesmo caminho da
        # cura BUG-FAKE-SOCKET-SYNC-01, que isola o modo fake assim).
        assert xdg_paths.ipc_socket_path().parent.name == "hefesto-dev-dualsense4unix"
    finally:
        monkeypatch.delenv(identidade.VARIANTE_ENV, raising=False)
        importlib.reload(xdg_paths)


def test_as_duas_casas_nao_dividem_recurso_nenhum():
    """Nome igual entre as casas é colisão — perfil, socket, unit ou ícone."""
    e, d = identidade.ESTAVEL, identidade.DEV
    for campo in ("slug", "app_id", "wm_instance", "wm_class", "nome",
                  "nome_longo", "icone", "unit_daemon", "entrypoint_gui"):
        assert getattr(e, campo) != getattr(d, campo), campo


# --------------------------------------------------------------------------
# 2. NENHUMA CASA ALCANÇA A OUTRA PELO `pgrep -f`
# --------------------------------------------------------------------------
def _cmdlines_plausiveis(casa: identidade.Identidade) -> list[str]:
    """As linhas de comando que um processo desta casa pode publicar."""
    return [
        f"/home/alguem/.local/bin/{casa.entrypoint_gui}",
        f"/home/alguem/.local/bin/{casa.entrypoint_cli} daemon start --foreground",
        f"/mnt/arvore/.venv/bin/{casa.entrypoint_cli} daemon start --foreground",
    ]


def test_nenhum_padrao_de_matanca_alcanca_a_outra_casa():
    """O teste que segura o `dev` NO MEIO do nome — e ele morde.

    `pgrep -f` casa por SUBSTRING. Com o sufixo no fim
    (`hefesto-dualsense4unix-gui-dev`) a string do estável estaria DENTRO da de
    dev, e abrir a GUI dela mandaria SIGTERM e depois SIGKILL na de dev.
    Renomeie `identidade.DEV.entrypoint_gui` para o sufixo no fim e este teste
    reprova.
    """
    for atacante, vitima in (
        (identidade.ESTAVEL, identidade.DEV),
        (identidade.DEV, identidade.ESTAVEL),
    ):
        padroes = [*atacante.padroes_de_matanca, atacante.padrao_do_daemon]
        for cmdline in _cmdlines_plausiveis(vitima):
            for padrao in padroes:
                assert not re.search(padrao, cmdline), (
                    f"o padrão {padrao!r} da casa {atacante.variante or 'estavel'!r} "
                    f"alcança o processo {cmdline!r} da outra casa"
                )


def test_cada_casa_alcanca_os_proprios_processos():
    """A contraprova: os padrões não podem ficar tão restritos que não matem
    a instância anterior DA PRÓPRIA CASA, que é para o que existem."""
    for casa in identidade.AS_DUAS:
        padroes = [*casa.padroes_de_matanca, casa.padrao_do_daemon]
        for cmdline in _cmdlines_plausiveis(casa):
            assert any(re.search(p, cmdline) for p in padroes), cmdline


def test_o_padrao_do_modulo_so_existe_no_estavel():
    """`hefesto_dualsense4unix.app.main` é o único nome que as duas casas
    partilham — as duas importam o mesmo pacote. Ele fica SÓ no estável, e o
    app de dev nasce por console script para não cair nele."""
    assert any("app\\.main" in p for p in identidade.ESTAVEL.padroes_de_matanca)
    assert not any("app\\.main" in p for p in identidade.DEV.padroes_de_matanca)


# --------------------------------------------------------------------------
# 3. O CÓDIGO E O `.desktop` CONCORDAM
# --------------------------------------------------------------------------
def _startup_wm_class(desktop: Path) -> str:
    for linha in desktop.read_text(encoding="utf-8").splitlines():
        if linha.startswith("StartupWMClass="):
            return linha.split("=", 1)[1].strip()
    raise AssertionError(f"{desktop} não declara StartupWMClass")


def test_o_desktop_de_dev_casa_o_wm_class_que_o_codigo_publica():
    """A régua que faltava nesta casa.

    O `StartupWMClass` do `.desktop` e o `res_class` que a janela publica são
    dois arquivos que nada obriga a concordar — e é dessa divergência que sai
    "ícone genérico na dock". Troque uma letra em qualquer um dos dois e este
    teste reprova.
    """
    desktop = RAIZ / "packaging" / "hefesto-dev-dualsense4unix.desktop"
    assert desktop.is_file(), desktop
    assert _startup_wm_class(desktop) == identidade.DEV.wm_class


def test_o_desktop_de_dev_pede_o_icone_da_identidade():
    desktop = RAIZ / "packaging" / "hefesto-dev-dualsense4unix.desktop"
    texto = desktop.read_text(encoding="utf-8")
    assert f"Icon={identidade.DEV.icone}\n" in texto


def test_o_codigo_publica_o_wm_class_por_processo_e_nao_por_janela():
    """`Gdk.set_program_class` tem de estar em `app/main.py`.

    É a linha que conserta as 23 janelas do processo de uma vez — inclusive as
    duas de `widgets/`, o seletor de arquivo e os 17 diálogos, que nunca
    chamaram `set_wmclass`. Medido em 29/08 em Xvfb com `xprop`: sem ela, tudo
    que não é a janela principal publica `res_class` derivado do argv[0].
    Arranque a linha e este teste reprova.
    """
    main = (RAIZ / "src" / "hefesto_dualsense4unix" / "app" / "main.py").read_text(
        encoding="utf-8"
    )
    assert "Gdk.set_program_class(" in main
    assert "wm_class" in main


def test_o_envoltorio_da_interface_veste_a_identidade_de_dev():
    """`scripts/abrir_interface.py` é o que dá logo à janela do piloto.

    O piloto (`novo-layout/_ferramentas/controles_vivos.py`) não pode ser
    editado por esta leva e nem sequer viaja em worktree — `novo-layout/` é
    `.gitignore`. A identidade tem de estar no envoltório versionado.
    """
    envoltorio = (RAIZ / "scripts" / "abrir_interface.py").read_text(encoding="utf-8")
    assert "set_program_class" in envoltorio
    assert "identidade.DEV" in envoltorio
    # E ele NÃO pode ligar a variante: a interface lê o daemon DELA.
    assert "setenv" not in envoltorio
    assert f'"{identidade.VARIANTE_ENV}"' not in envoltorio


# --------------------------------------------------------------------------
# 4. O AUTOSWITCH RETÉM AS DUAS JANELAS
# --------------------------------------------------------------------------
def test_o_autoswitch_reconhece_a_janela_das_duas_casas():
    """MISC-08: focar a nossa janela não é "ela saiu do jogo".

    Com o app de dev instalado, a janela DELE também é nossa — sem isto,
    alt-tab entre o jogo e a interface nova troca o perfil dela no meio da
    partida. Tire `AS_DUAS` de `OWN_GUI_WM_CLASSES` e este teste reprova.
    """
    from hefesto_dualsense4unix.profiles.autoswitch import OWN_GUI_WM_CLASSES

    for casa in identidade.AS_DUAS:
        for nome in (casa.wm_instance, casa.wm_class, casa.entrypoint_gui):
            assert nome.casefold() in OWN_GUI_WM_CLASSES, nome


# --------------------------------------------------------------------------
# 5. A LOGO DE DEV SOBREVIVE AO MOTOR QUE GERA O ÍCONE
# --------------------------------------------------------------------------
def test_a_logo_de_dev_nao_depende_do_que_o_librsvg_ignora():
    """Medido em 29/08 com rsvg-convert 2.58.0: o librsvg IGNORA
    `transform-box` e `transform-origin`.

    A logo nova depende dos dois (o anel e o martelo), e por isso ela perde o
    anel E o martelo quando rasterizada — o desenho apareceria inteiro dentro
    do app (WebKit) e mutilado na dock (librsvg). A logo de dev nasce com os
    transforms ASSADOS na matriz: o Chrome renderiza o antes e o depois
    byte-idênticos (md5 4cb1c2c7…, 0 pixels de diferença) e o librsvg passa a
    mostrar o desenho inteiro.
    """
    svg = (RAIZ / "assets" / "hefesto-dev-logo.svg").read_text(encoding="utf-8")
    assert "transform-origin" not in svg
    assert "transform-box" not in svg


def test_a_logo_de_dev_e_visivelmente_outra():
    """Ela pediu dois apps distinguíveis na dock. Mesmo desenho com a mesma
    paleta não distingue a dois centímetros — a marca de dev é o que separa."""
    dev = (RAIZ / "assets" / "hefesto-dev-logo.svg").read_text(encoding="utf-8")
    assert "Marca de dev" in dev
    # O anel deixa de ser o degradê e vira âmbar chapado: é o sinal que
    # sobrevive a 24 px, porque domina a silhueta externa.
    assert 'stroke="#ffb86c"' in dev
    assert 'stroke="url(#ring)"' not in dev
