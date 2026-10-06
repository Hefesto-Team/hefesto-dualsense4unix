"""O `tray` sobe o `AppTray`, e ele abre o PAINEL — não a TUI."""
from __future__ import annotations

import inspect
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[2]


def test_o_subcomando_sobe_o_apptray_e_nao_o_pobre() -> None:
    """A troca inteira cabe nesta afirmação."""
    from hefesto_dualsense4unix.cli import cmd_tray

    fonte = inspect.getsource(cmd_tray)
    assert "from hefesto_dualsense4unix.app.tray import AppTray" in fonte, (
        "o `tray` deixou de subir o `AppTray`. O `TrayController` abre a TUI "
        "no terminal — quem clica no ícone quer o painel.")
    assert "TrayController(" not in fonte, (
        "o `TrayController` voltou a ser instanciado aqui. Ele é o tray pobre: "
        "sem «Abrir painel», sem marca do perfil ativo, e com uma thread "
        "própria de refresh que o `AppTray` não precisa.")


def test_os_quatro_callbacks_estao_ligados() -> None:
    """Um callback faltando é um item de menu que não faz nada."""
    from hefesto_dualsense4unix.cli import cmd_tray

    fonte = inspect.getsource(cmd_tray.tray_cmd)
    for ligacao in ("on_show_window=", "on_quit=", "on_list_profiles=",
                    "on_switch_profile=", "on_state="):
        assert ligacao in fonte, (
            f"o `AppTray` subiu sem `{ligacao}` — o item correspondente do "
            f"menu nasce morto")


def test_abrir_painel_chama_o_lancador_instalado_e_nao_a_arvore() -> None:
    """O «Abrir painel» tem de funcionar em QUALQUER computador."""
    from hefesto_dualsense4unix.cli import cmd_tray

    assert cmd_tray.LANCADOR_DO_PAINEL == "hefesto-dualsense4unix-gui", (
        f"o lançador virou {cmd_tray.LANCADOR_DO_PAINEL!r}")
    fonte = inspect.getsource(cmd_tray._abrir_o_painel)
    assert "interface.sh" not in fonte and "/mnt/" not in fonte, (
        "o «Abrir painel» passou a apontar para um caminho de árvore")
    assert "start_new_session=True" in fonte, (
        "sem `start_new_session`, fechar o tray fecharia o painel que ele abriu")


def test_o_estado_vem_do_state_full_e_nao_do_status() -> None:
    """`daemon.status` não traz a lista de controles.

    O `AppTray._controllers_suffix_from_state` a lê para dizer quantos estão na
    mesa; com o `status` o tray diria sempre «1 controle». Medido em 19/09 na
    máquina do usuário: `state_full` devolveu perfil, bateria e a lista.
    """
    from hefesto_dualsense4unix.cli import cmd_tray

    fonte = inspect.getsource(cmd_tray._estado)
    assert "daemon.state_full" in fonte, (
        "o estado do tray voltou a vir do `daemon.status`, que não tem a lista "
        "de controles")


def test_o_ipc_silencia_em_vez_de_levantar() -> None:
    """Estes callbacks rodam DENTRO do laço do GTK."""
    from hefesto_dualsense4unix.cli import cmd_tray

    fonte = inspect.getsource(cmd_tray._chamar)
    for classe in ("ConnectionError", "IpcError", "OSError", "FileNotFoundError"):
        assert classe in fonte, f"`{classe}` saiu da guarda do IPC do tray"
    assert "return None" in fonte


def test_o_apptray_espera_o_watcher_no_cosmic() -> None:
    """A peça que faz o ícone aparecer, e ela é do `AppTray`."""
    fonte = (RAIZ / "src/hefesto_dualsense4unix/app/tray.py").read_text(
        encoding="utf-8")
    assert "_desktop_is_cosmic" in fonte and "_start_deferred" in fonte, (
        "a espera pelo watcher do COSMIC saiu do `AppTray`")
    assert "IndicatorStatus.ACTIVE" in fonte, (
        "o indicador deixou de ser posto em ACTIVE — em PASSIVE ele é "
        "registrado e NÃO aparece na barra, que é a forma mais silenciosa "
        "deste defeito")
