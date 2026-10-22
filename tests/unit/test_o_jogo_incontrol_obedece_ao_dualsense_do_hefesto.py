"""O-JOGO-INCONTROL-OBEDECE-AO-DUALSENSE-DO-HEFESTO-01 (22/10/2026).

O InControl Native repete o `IsXInputDevice` da Microsoft: todo `DeviceID` do
WMI com `IG_` marca o VID:PID como XInput, e o DirectInput o pula. O `wbemprox`
do Wine lista toda chave de `Enum`, presente ou não, então o gêmeo XInput de um
controle de meses atrás fazia o jogo ignorar o DualSense de hoje. A cura é o
curador do registro esquecer, antes de cada jogo, o controle que se foi.

A fixture copia a FORMA das chaves do prefixo do Mullet MadJack, com VID/PID
reais da Sony e da Microsoft (não são endereço) e todo endereço em faixa forjada.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks
from tests.unit.test_haptica_nativa_01_o_device_ks_que_o_jogo_procura import (
    _CABECALHO,
    _ENV_LIGADO,
    PADRAO,
    _prefixo,
    _wineserver_de_mentira,
)
from tests.unit.test_install_universal_01_o_device_ks_espera_e_deixa_rastro import (
    _lancar,
    _rastro,
)

_HID = "{INTERFACE-HID}"
_PROP = "{4340A6C5-93FA-4706-972C-PROPRIEDADE}"
_XB = "VID_045E&PID_028E&IG_00"
_XB_INST = "272&FANTASMA-XB&0&0&1"
_DS = "VID_054C&PID_0CE6&IG_00"
_DS_INST = "33024&FANTASMA-DS&0&0&1"
_ENUM = "[System\\\\ControlSet001\\\\Enum\\\\"
_CLASSES = f"[System\\\\ControlSet001\\\\Control\\\\DeviceClasses\\\\{_HID}\\\\"
#: a chave do driver: a do aparelho esquecido sai junto, a de quem fica, fica
_CLASSE_HID = "[System\\\\ControlSet001\\\\Control\\\\Class\\\\{classe-hid}\\\\"
_DRIVER = '"Driver"="{CLASSE-HID}\\\\%s"'


def _chave(cabecalho: str, *linhas: str) -> str:
    return f"{cabecalho}] 1784672144\n#time=1dd17d4214d7c18\n" + "".join(f"{x}\n" for x in linhas)


def _interface(vid_pid: str, inst: str) -> list[str]:
    nome = f"##?#HID#{vid_pid}#{inst}#{_HID}"
    return [
        _chave(f"{_CLASSES}{nome}", f'"DeviceInstance"="HID\\\\{vid_pid}\\\\{inst}"'),
        _chave(f"{_CLASSES}{nome}\\\\#", f'"SymbolicLink"="\\\\\\\\?\\\\HID#{vid_pid}#{inst}"'),
        _chave(f"{_CLASSES}{nome}\\\\#\\\\Control", '"Linked"=dword:00000001'),
    ]


#: o que a lembrança de controle XInput deixa, e a cura tira
SAEM = [
    _chave(f"{_ENUM}WINEXINPUT\\\\{_DS}\\\\{_DS_INST}", '"Class"="HIDClass"', _DRIVER % "0101"),
    _chave(f"{_CLASSE_HID}0101", '"InfPath"="winehid.inf"'),
    _chave(f"{_ENUM}WINEXINPUT\\\\{_DS}\\\\{_DS_INST}\\\\Device Parameters"),
    _chave(
        f"{_ENUM}WINEXINPUT\\\\{_DS}\\\\{_DS_INST}\\\\Properties\\\\{_PROP}\\\\0008", "@=hex:00"
    ),
    _chave(f"{_ENUM}WINEXINPUT\\\\VID_054C&PID_0CE6&XI_00\\\\{_DS_INST}", '"Class"="HIDClass"'),
    _chave(f"{_ENUM}WINEXINPUT\\\\{_XB}\\\\{_XB_INST}", '"Class"="HIDClass"'),
    _chave(f"{_ENUM}HID\\\\{_XB}\\\\{_XB_INST}", '"Class"="HIDClass"'),
    _chave(f"{_ENUM}HID\\\\{_XB}\\\\{_XB_INST}\\\\Device Parameters"),
    *_interface(_DS, _DS_INST),
    *_interface(_XB, _XB_INST),
]

#: o que parece e FICA: o mesmo VID:PID sem `IG_`, o USB, o nosso, o instalador
FICAM = [
    _chave(
        f"{_ENUM}HID\\\\VID_054C&PID_0CE6\\\\0&02:FE:00:00:00:0D&0&0&0",
        '"Class"="HIDClass"',
        _DRIVER % "0102",
    ),
    _chave(f"{_CLASSE_HID}0102", '"InfPath"="input.inf"'),
    _chave(f"{_ENUM}HID\\\\VID_054C&PID_0CE6\\\\0&02:FE:00:00:00:0D&0&0&0\\\\Device Parameters"),
    _chave(f"{_ENUM}HID\\\\VID_054C&PID_0CE6&MI_00\\\\256&HEFESTO-PAD-01-02FE0000000D&0&0&0"),
    _chave(f"{_ENUM}USB\\\\VID_054C&PID_0CE6\\\\512&256&3&3", '"ClassGUID"="{36FC9E60}"'),
    _chave(f"{_ENUM}WINEBUS\\\\VID_845E&PID_0002\\\\0&FANTASMA-BUS&0&0&0"),
    _chave(
        "[System\\\\ControlSet001\\\\Control\\\\Class\\\\{classe-hid}"
        "\\\\0007",
        '"InfPath"="winexinput.inf"',
    ),
    *[
        _chave(f"{_CLASSES}##?#HID#VID_054C&PID_0CE6#0&02:FE:00:00:00:0D&0&0&0#{_HID}{sufixo}", x)
        for sufixo, x in (
            ("", '"DeviceInstance"="HID\\\\VID_054C&PID_0CE6\\\\0&02:FE:00:00:00:0D&0&0&0"'),
            ("\\\\#", '"SymbolicLink"="x"'),
        )
    ],
    _chave("[Software\\\\Wine\\\\IG_Qualquer", '"Valor"="1"'),
]

#: o que um lançamento anterior gravou, e o `--remover` tira
NOSSO = ks.blocos_do_controle(PADRAO, [bytes(8)], 1)


def _texto(*blocos: str) -> str:
    return _CABECALHO + "\n" + "\n".join(blocos)


def _misturado() -> str:
    """Os blocos que ficam e os que saem, intercalados como o Wine os deixa."""
    meio = len(FICAM) // 2
    return _texto(*FICAM[:meio], *SAEM, *NOSSO, *FICAM[meio:])


def _ler(compat: Path) -> str:
    return (compat / "pfx" / "system.reg").read_text(encoding="utf-8")


def test_a_lembranca_sai_e_o_resto_fica_byte_a_byte() -> None:
    # D-2210-O-PREFIXO-ESQUECE-O-CONTROLE-XINPUT-QUE-SE-FOI.
    meio = len(FICAM) // 2
    esperado = _texto(*FICAM[:meio], *NOSSO, *FICAM[meio:])
    novo, contados = ks.esquecer_os_controles_que_se_foram(_misturado())
    assert novo == esperado
    assert contados == 2, "o DualSense e o Xbox: um por VID:PID, não por chave"
    assert "&IG_" not in novo
    assert "Enum\\\\WINEXINPUT" not in novo


def test_sem_lembranca_o_texto_volta_o_mesmo_objeto() -> None:
    limpo = _texto(*FICAM, *NOSSO)
    novo, contados = ks.esquecer_os_controles_que_se_foram(limpo)
    assert novo is limpo and contados == 0


def test_o_current_control_set_tambem_vale() -> None:
    texto = _texto(
        _chave(f"[System\\\\CurrentControlSet\\\\Enum\\\\WINEXINPUT\\\\{_DS}\\\\{_DS_INST}"),
        *FICAM,
    )
    assert ks.esquecer_os_controles_que_se_foram(texto) == (_texto(*FICAM), 1)


def test_o_aplicar_grava_com_backup_e_nao_regrava(tmp_path: Path) -> None:
    compat = _prefixo(tmp_path, _misturado())
    original = _ler(compat)
    r = ks.aplicar(compat, controles=[], proc=tmp_path / "proc", carimbo=1)
    assert r.escreveu and r.esquecidos == 2
    assert "&IG_" not in _ler(compat)
    assert (compat / "pfx" / "system.reg.bak.hefesto-audio-ks").read_text() == original
    outra = ks.aplicar(compat, controles=[], proc=tmp_path / "proc", carimbo=2)
    assert not outra.escreveu and outra.esquecidos == 0


@pytest.mark.parametrize("podar", [False, True], ids=["remover", "com-poda"])
def test_com_controle_no_cabo_o_nosso_refaz_e_a_lembranca_sai(tmp_path: Path, podar: bool) -> None:
    compat = _prefixo(tmp_path, _misturado())
    r = ks.aplicar(compat, controles=[PADRAO], proc=tmp_path / "proc", carimbo=1, podar=podar)
    texto = _ler(compat)
    assert r.escreveu and r.esquecidos == 2
    assert "HEFESTOKS&003&028&0" in texto
    assert "Enum\\\\WINEXINPUT" not in texto


def test_com_o_wineserver_vivo_nada_se_esquece(tmp_path: Path) -> None:
    compat = _prefixo(tmp_path, _misturado())
    antes = _ler(compat)
    _wineserver_de_mentira(tmp_path / "proc", "4242", str(compat / "pfx") + "/")
    r = ks.aplicar(compat, controles=[], proc=tmp_path / "proc")
    assert r.motivo == "ocupado" and not r.escreveu and r.esquecidos == 0
    assert _ler(compat) == antes


def test_a_cli_remover_esquece_e_o_remover_de_todos_tambem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    um = _prefixo(tmp_path / "a", _misturado())
    outro = _prefixo(tmp_path / "b", _misturado())
    assert ks.main(["--prefixo", str(um), "--remover", "--sysfs", str(tmp_path / "sys")]) == 0
    assert "Enum\\\\WINEXINPUT" not in _ler(um)
    monkeypatch.setattr(ks, "prefixos_de_todas_as_bibliotecas", lambda: [outro])
    assert ks.main(["--remover-de-todos"]) == 0
    assert "Enum\\\\WINEXINPUT" not in _ler(outro)
    assert "&IG_" not in _ler(outro)


# --- o lançador: o gatilho do `curar_audio_ks` ---------------------------------------

_SEM_A_OPCAO = "PROTON_ENABLE_MHWILDS_USB_AUDIO=0\n"


def test_o_lancador_chama_o_curador_quando_so_ha_lembranca(tmp_path: Path) -> None:
    """A MORDIDA do gatilho: sem o `grep` de `&IG_`/`WINEXINPUT`, o lançador voltava cedo."""
    feito, compat, arquivo = _lancar(
        tmp_path, env_do_daemon=_SEM_A_OPCAO, registro=_texto(*FICAM, *SAEM)
    )
    assert feito.returncode == 0, feito.stderr
    assert "o jogo abriu" in feito.stdout
    assert _ler_compat(compat) == _texto(*FICAM)
    rastro = _rastro(arquivo)
    assert rastro["motivo"] == "desligado", "nenhum device KS saiu: não pode dizer removido"
    assert rastro["rc"] == "0"


def test_o_lancador_chama_o_curador_so_com_o_winexinput(tmp_path: Path) -> None:
    """A outra metade do gatilho: o gêmeo `XI_` sozinho, sem nenhum `&IG_` no registro."""
    xi = _chave(f"{_ENUM}WINEXINPUT\\\\VID_054C&PID_0CE6&XI_00\\\\{_DS_INST}")
    feito, compat, arquivo = _lancar(
        tmp_path, env_do_daemon=_SEM_A_OPCAO, registro=_texto(*FICAM, xi)
    )
    assert feito.returncode == 0, feito.stderr
    assert _ler_compat(compat) == _texto(*FICAM)
    assert _rastro(arquivo)["motivo"] == "desligado"


def test_com_lembranca_e_bloco_nosso_o_rastro_diz_removido(tmp_path: Path) -> None:
    feito, compat, arquivo = _lancar(
        tmp_path, env_do_daemon=_SEM_A_OPCAO, registro=_misturado()
    )
    assert feito.returncode == 0, feito.stderr
    texto = _ler_compat(compat)
    assert "HEFESTOKS" not in texto and "Enum\\\\WINEXINPUT" not in texto
    assert _rastro(arquivo)["motivo"] == "removido"


def test_com_a_opcao_ligada_a_lembranca_sai_e_o_rastro_diz_ok(tmp_path: Path) -> None:
    feito, compat, arquivo = _lancar(
        tmp_path, env_do_daemon=_ENV_LIGADO, registro=_texto(*FICAM, *SAEM)
    )
    assert feito.returncode == 0, feito.stderr
    texto = _ler_compat(compat)
    assert "Enum\\\\WINEXINPUT" not in texto and "&IG_" not in texto
    assert "HEFESTOKS" in texto
    assert _rastro(arquivo)["motivo"] == "ok"


def test_registro_limpo_o_lancador_nao_chama_o_curador(tmp_path: Path) -> None:
    limpo = _texto(*FICAM)
    feito, compat, arquivo = _lancar(tmp_path, env_do_daemon=_SEM_A_OPCAO, registro=limpo)
    assert feito.returncode == 0, feito.stderr
    assert _ler_compat(compat) == limpo
    assert _rastro(arquivo)["motivo"] == "desligado"
    assert not (compat / "pfx" / "system.reg.bak.hefesto-audio-ks").exists()


def _ler_compat(compat: Path) -> str:
    return (compat / "pfx" / "system.reg").read_text(encoding="utf-8")
