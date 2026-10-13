"""Os números da Sony e os ajudantes copiados têm um dono só (13/10/2026).

Cinco curas, cada uma com a régua que a segura:

1. o VID/PID mora em `core/numeros_da_sony.py` e a catraca `scripts/check_numeros_da_sony.py`
   conta o literal que ainda mora fora; o `launch_env` monta as envs com o par do dono;
2. o leitor de texto do `/sys` é um (`utils/texto_do_sysfs.ler_texto`), e nenhuma cópia volta;
3. a chamada ao daemon dos comandos `controller`, `coop`, `gamepad` e `mouse` é uma;
4. a regra do `custom_mult` e o multiplicador da política fixa são um, no `schema`;
5. os quatro invólucros do `lifecycle` sem chamador não voltam.

Nenhum aparelho, nenhum daemon: função pura, árvore de mentira em `tmp_path` ou leitura do código.
"""
from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import numeros_da_sony as dono
from hefesto_dualsense4unix.utils.texto_do_sysfs import ler_texto

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
SCRIPT = RAIZ / "scripts" / "check_numeros_da_sony.py"


def _carregar_catraca() -> Any:
    spec = importlib.util.spec_from_file_location("check_numeros_da_sony", SCRIPT)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


catraca = _carregar_catraca()


# ------------------------------------------------------------
# 1. O dono dos números e a catraca
# ------------------------------------------------------------


def test_o_dono_diz_os_numeros_do_dualsense() -> None:
    assert dono.VENDOR_SONY == 0x054C
    assert dono.PID_DUALSENSE == 0x0CE6
    assert dono.PID_DUALSENSE_EDGE == 0x0DF2
    assert sorted(dono.PIDS_DUALSENSE) == [0x0CE6, 0x0DF2]
    assert dono.PID_DO_PAD_VIRTUAL == 0x0DF2
    assert dono.PAR_DUALSENSE_FISICO == (0x054C, 0x0CE6)


def test_o_dono_concorda_com_as_constantes_que_ainda_nao_migraram() -> None:
    """Enquanto os módulos não importam do dono, o literal deles não pode divergir dele."""
    from hefesto_dualsense4unix.core import evdev_reader
    from hefesto_dualsense4unix.integrations import pad_usb, uhid_gamepad, uinput_gamepad

    assert evdev_reader.DUALSENSE_VENDOR == dono.VENDOR_SONY
    assert set(evdev_reader.DUALSENSE_PIDS) == set(dono.PIDS_DUALSENSE)
    assert uhid_gamepad.DUALSENSE_VENDOR == dono.VENDOR_SONY
    assert uhid_gamepad.DUALSENSE_PRODUCT == dono.PID_DUALSENSE
    assert uhid_gamepad.VPAD_PRODUCT == dono.PID_DO_PAD_VIRTUAL
    assert uinput_gamepad.DUALSENSE_PRODUCT == dono.PID_DUALSENSE
    assert uinput_gamepad.DUALSENSE_EDGE_PRODUCT == dono.PID_DUALSENSE_EDGE
    assert pad_usb.VENDOR_SONY == dono.VENDOR_SONY
    assert uhid_gamepad.VPAD_HID_PHYS == dono.HID_PHYS_DO_PAD
    assert pad_usb.VPAD_HID_PHYS == dono.HID_PHYS_DO_PAD


def test_o_launch_env_monta_as_envs_com_o_par_do_dono(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon import launch_env

    assert launch_env.PAR_DUALSENSE_FISICO is dono.PAR_DUALSENSE_FISICO

    # Uma cópia do módulo, carregada com o dono trocado: se o par morasse dentro do `launch_env`,
    # a troca não chegaria às envs.
    monkeypatch.setattr(dono, "PAR_DUALSENSE_FISICO", (0x1234, 0x5678))
    nome = "launch_env_com_o_dono_trocado"
    spec = importlib.util.spec_from_file_location(nome, launch_env.__file__)
    assert spec is not None and spec.loader is not None
    copia = importlib.util.module_from_spec(spec)
    sys.modules[nome] = copia
    try:
        spec.loader.exec_module(copia)
    finally:
        sys.modules.pop(nome, None)

    assert copia.PAR_DUALSENSE_FISICO == (0x1234, 0x5678)
    assert "0x1234/0x5678" in copia._IGNORE_VALUE
    assert copia._DISABLE_HIDRAW_VALUE == "0x1234/0x5678"
    assert "0x054c" not in copia._IGNORE_VALUE.lower().replace("0x054c/0x0ce6", "")


def _arvore(tmp_path: Path, **arquivos: str) -> Path:
    base = tmp_path / "src" / "hefesto_dualsense4unix"
    base.mkdir(parents=True)
    for nome, texto in arquivos.items():
        (base / f"{nome}.py").write_text(texto, encoding="utf-8")
    return tmp_path


def test_o_literal_fora_do_dono_sobe_a_contagem_e_reprova_acima_do_piso(tmp_path: Path) -> None:
    limpa = _arvore(tmp_path / "a", modulo="X = 1\n")
    assert catraca.main(["--raiz", str(limpa), "--piso", "0"]) == 0

    suja = _arvore(tmp_path / "b", modulo="VID = 0x0CE6\nOUTRO = (0x054c, 0x0df2)\n")
    assert len(catraca.linhas_com_o_literal(suja)) == 2
    assert catraca.main(["--raiz", str(suja), "--piso", "1"]) == 1
    assert catraca.main(["--raiz", str(suja), "--piso", "2"]) == 0


@pytest.mark.parametrize(
    "literal", ["0x054c", "0x054C", "0x0ce6", "0x0CE6", "0x0df2", "0x0DF2"]
)
def test_cada_literal_conta_sozinho_nas_duas_caixas(tmp_path: Path, literal: str) -> None:
    raiz = _arvore(tmp_path, modulo=f"NUMERO = {literal}\n")

    assert catraca.linhas_com_o_literal(raiz) == [("src/hefesto_dualsense4unix/modulo.py", 1)]


def test_o_dono_nao_conta_contra_si_mesmo(tmp_path: Path) -> None:
    raiz = _arvore(tmp_path)
    pasta = raiz / "src" / "hefesto_dualsense4unix" / "core"
    pasta.mkdir()
    (pasta / "numeros_da_sony.py").write_text("VENDOR_SONY = 0x054C\n", encoding="utf-8")

    assert catraca.linhas_com_o_literal(raiz) == []


def test_piso_folgado_tambem_reprova_porque_a_catraca_so_desce(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    raiz = _arvore(tmp_path, modulo="VID = 0x0CE6\n")

    assert catraca.main(["--raiz", str(raiz), "--piso", "5"]) == 1
    assert "Baixe PISO para 1" in capsys.readouterr().out


def test_sem_src_a_catraca_diz_nao_medido(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert catraca.main(["--raiz", str(tmp_path)]) == 1
    assert capsys.readouterr().out.startswith("NÃO MEDIDO")


def test_a_catraca_esta_verde_na_arvore_de_verdade() -> None:
    assert catraca.main([]) == 0
    feito = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False, cwd=RAIZ
    )
    assert feito.returncode == 0, feito.stdout


# ------------------------------------------------------------
# 2. O leitor de texto do /sys
# ------------------------------------------------------------


def test_o_leitor_unico_devolve_o_texto_e_vazio_em_qualquer_erro(tmp_path: Path) -> None:
    arquivo = tmp_path / "uevent"
    arquivo.write_bytes(b"HID_ID=0003\xff\n")

    assert ler_texto(str(arquivo)).startswith("HID_ID=0003")  # byte inválido vira «�», não erro
    assert ler_texto(str(tmp_path / "sumiu")) == ""
    assert ler_texto(str(tmp_path)) == ""  # diretório: OSError (EISDIR)


#: As variantes que NÃO são o corpo do leitor único e ficam, cada uma com o motivo numa linha.
#: As de `.strip()` migram quando a sprint do módulo dela o tocar (`ler_texto(p).strip()`).
VARIANTES_DO_LEITOR = {
    "integrations/censo_do_gabinete.py::_ler_texto": "abre com errors='ignore'",
    "daemon/battery_journal.py::_ler_texto": "recebe Path e devolve None: «sumiu» não é «vazio»",
    "integrations/pad_usb.py::_ler_atributo": "devolve o texto sem as pontas (`.strip()`)",
    "integrations/no_do_vpad.py::_texto_do_sysfs": "devolve o texto sem as pontas (`.strip()`)",
    "integrations/faixa_do_wifi.py::_ler_arquivo": "devolve o texto sem as pontas (`.strip()`)",
    "integrations/endpoint_de_haptica.py::_ler": "lê Path em ascii e devolve sem as pontas",
    "integrations/sinal_da_barra.py::_ler": "abre sem errors='replace' e devolve sem as pontas",
}


def _corpo_do_leitor_unico() -> str:
    arvore = ast.parse((SRC / "utils" / "texto_do_sysfs.py").read_text(encoding="utf-8"))
    funcao = next(
        n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == "ler_texto"
    )
    return ast.dump(ast.Module(body=funcao.body[1:], type_ignores=[]))


def _copias_do_leitor(raiz: Path) -> list[str]:
    """Toda função de `src` (fora do dono) cujo corpo é, inteiro, o do leitor único."""
    alvo = _corpo_do_leitor_unico()
    achadas: list[str] = []
    for arquivo in sorted(raiz.rglob("*.py")):
        if arquivo.name == "texto_do_sysfs.py":
            continue
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.FunctionDef) or not no.body:
                continue
            corpo = no.body[1:] if ast.get_docstring(no) is not None else no.body
            if ast.dump(ast.Module(body=corpo, type_ignores=[])) == alvo:
                achadas.append(f"{arquivo.relative_to(raiz).as_posix()}::{no.name}")
    return achadas


def test_nenhuma_copia_do_leitor_de_texto_mora_em_src() -> None:
    assert _copias_do_leitor(SRC) == []


def test_as_sete_integracoes_importam_o_leitor_unico() -> None:
    nomes = (
        "apelido_do_dongle", "censo_do_barramento", "cor_do_plastico", "entradas_do_gabinete",
        "mesa_de_radio", "radio_da_mesa", "usb_pai",
    )
    for nome in nomes:
        texto = (SRC / "integrations" / f"{nome}.py").read_text(encoding="utf-8")
        assert "from hefesto_dualsense4unix.utils.texto_do_sysfs import ler_texto" in texto, nome
        assert "def _ler_texto" not in texto, nome


def test_a_regua_de_copia_acha_a_copia_que_voltou(tmp_path: Path) -> None:
    pasta = tmp_path / "integrations"
    pasta.mkdir()
    (pasta / "volta.py").write_text(
        'def _ler_texto(caminho: str) -> str:\n'
        '    """Lê um arquivo."""\n'
        '    try:\n'
        '        with open(caminho, encoding="utf-8", errors="replace") as arquivo:\n'
        '            return arquivo.read()\n'
        '    except OSError:\n'
        '        return ""\n',
        encoding="utf-8",
    )

    assert _copias_do_leitor(tmp_path) == ["integrations/volta.py::_ler_texto"]


def test_as_variantes_declaradas_existem_e_nao_sao_a_copia() -> None:
    for chave in VARIANTES_DO_LEITOR:
        relativo, nome = chave.split("::")
        arvore = ast.parse((SRC / relativo).read_text(encoding="utf-8"))
        nomes = {n.name for n in ast.walk(arvore) if isinstance(n, ast.FunctionDef)}
        assert nome in nomes, f"a variante {chave} saiu: tire-a da lista"


# ------------------------------------------------------------
# 3. A chamada ao daemon dos comandos
# ------------------------------------------------------------

#: As cópias do corpo de `chamar_o_daemon` que ficam, cada uma com o motivo numa linha.
COPIAS_DA_CHAMADA = {
    "cli/cmd_native.py::_call_sync": "é de outra sprint: migra quando ela tocar o `cmd_native`",
}


def _copias_da_chamada(pasta: Path) -> set[str]:
    """Toda função de `cli/` (fora do dono) cujo corpo é, inteiro, o de `chamar_o_daemon`."""
    dono_ = ast.parse((SRC / "cli" / "chamada_ao_daemon.py").read_text(encoding="utf-8"))
    funcao = next(
        n for n in dono_.body if isinstance(n, ast.FunctionDef) and n.name == "chamar_o_daemon"
    )
    alvo = ast.dump(ast.Module(body=funcao.body[1:], type_ignores=[]))
    achados: set[str] = set()
    for arquivo in sorted(pasta.glob("*.py")):
        if arquivo.name == "chamada_ao_daemon.py":
            continue
        for no in ast.walk(ast.parse(arquivo.read_text(encoding="utf-8"))):
            if not isinstance(no, ast.FunctionDef) or not no.body:
                continue
            corpo = no.body[1:] if ast.get_docstring(no) is not None else no.body
            if ast.dump(ast.Module(body=corpo, type_ignores=[])) == alvo:
                achados.add(f"cli/{arquivo.name}::{no.name}")
    return achados


def test_so_a_copia_declarada_repete_o_corpo_da_chamada_ao_daemon() -> None:
    assert _copias_da_chamada(SRC / "cli") == set(COPIAS_DA_CHAMADA)


def test_a_regua_da_chamada_acha_a_copia_que_voltou(tmp_path: Path) -> None:
    corpo = (SRC / "cli" / "cmd_native.py").read_text(encoding="utf-8")
    (tmp_path / "cmd_novo.py").write_text(corpo, encoding="utf-8")

    assert "cli/cmd_novo.py::_call_sync" in _copias_da_chamada(tmp_path)


@pytest.mark.parametrize("comando", ["cmd_controller", "cmd_coop", "cmd_gamepad", "cmd_mouse"])
def test_os_quatro_comandos_chamam_pelo_dono(comando: str) -> None:
    texto = (SRC / "cli" / f"{comando}.py").read_text(encoding="utf-8")

    assert "from hefesto_dualsense4unix.cli.chamada_ao_daemon import chamar_o_daemon" in texto
    assert "def _call_sync" not in texto


def test_o_dono_da_chamada_responde_o_prazo_a_recusa_e_o_daemon_fora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import io

    import typer
    from rich.console import Console

    from hefesto_dualsense4unix.app import ipc_bridge
    from hefesto_dualsense4unix.cli.chamada_ao_daemon import chamar_o_daemon
    from hefesto_dualsense4unix.cli.ipc_client import IpcError

    def com(excecao: BaseException | None, devolve: Any = None) -> None:
        def _falso(*_a: Any, **_k: Any) -> Any:
            if excecao is not None:
                raise excecao
            return devolve

        monkeypatch.setattr(ipc_bridge, "_run_call", _falso)

    saida = io.StringIO()
    console = Console(file=saida, width=200, no_color=True)

    com(None, {"ok": True})
    assert chamar_o_daemon(console, "daemon.state_full") == {"ok": True}

    com(IpcError(-32000, "não quero"))
    with pytest.raises(typer.Exit) as recusa:
        chamar_o_daemon(console, "coop.set", {"enabled": True})
    assert recusa.value.exit_code == 2
    assert "daemon recusou chamada" in saida.getvalue()

    com(ConnectionRefusedError("sem socket"))
    with pytest.raises(typer.Exit) as fora:
        chamar_o_daemon(console, "daemon.state_full")
    assert fora.value.exit_code == 3
    assert "daemon offline" in saida.getvalue()


# ------------------------------------------------------------
# 4. A regra do custom_mult e o multiplicador da política
# ------------------------------------------------------------


def test_as_duas_bordas_do_custom_mult_chamam_a_mesma_regra() -> None:
    from pydantic import ValidationError

    from hefesto_dualsense4unix.profiles import schema

    for classe in (schema.RumbleConfig, schema.ControllerRumbleOverride):
        assert classe(policy="custom", custom_mult=1.5).custom_mult == 1.5
        with pytest.raises(ValidationError, match="fora de"):
            classe(policy="custom", custom_mult=schema.RUMBLE_CUSTOM_MULT_MAX + 0.1)
        with pytest.raises(ValidationError, match="só é válido com policy='custom'"):
            classe(policy="max", custom_mult=1.0)

    for nome in ("RumbleConfig", "ControllerRumbleOverride"):
        arvore = ast.parse((SRC / "profiles" / "schema.py").read_text(encoding="utf-8"))
        classe = next(
            n for n in arvore.body if isinstance(n, ast.ClassDef) and n.name == nome
        )
        validador = next(
            n for n in classe.body
            if isinstance(n, ast.FunctionDef) and n.name == "_validate_custom_mult"
        )
        chamadas = [
            n.func.id for n in ast.walk(validador)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        ]
        assert "_conferir_custom_mult" in chamadas, nome
        assert not any(isinstance(n, ast.Raise) for n in ast.walk(validador)), nome


def test_o_manager_importa_o_multiplicador_do_schema() -> None:
    from hefesto_dualsense4unix.profiles import manager, schema

    assert manager._mult_da_vibracao is schema._mult_da_vibracao
    assert not hasattr(manager, "_mult_da_politica")
    assert schema._mult_da_vibracao("custom", 1.25) == 1.25
    assert schema._mult_da_vibracao("auto", None) is None
    assert schema._mult_da_vibracao(None, 1.0) is None
    assert schema._mult_da_vibracao("max", None) is not None


# ------------------------------------------------------------
# 5. Os invólucros sem chamador
# ------------------------------------------------------------

INVOLUCROS_MORTOS = (
    "_stop_hotkey_manager", "_stop_mouse_emulation", "_start_mic_hotkey", "_stop_plugins",
)


@pytest.mark.parametrize("nome", INVOLUCROS_MORTOS)
def test_o_invólucro_sem_chamador_nao_volta_ao_lifecycle(nome: str) -> None:
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    assert not hasattr(Daemon, nome)
    achados = subprocess.run(
        ["git", "grep", "-l", "-w", nome, "--", "src", "tests", "scripts"],
        capture_output=True, text=True, check=False, cwd=RAIZ,
    )
    # o próprio teste cita o nome: só ele pode aparecer
    assert achados.stdout.split() in ([], ["tests/unit/test_os_numeros_da_sony_tem_um_dono.py"])
