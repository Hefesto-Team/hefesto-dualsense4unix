"""O doctor diz quando o sistema não deixa ler o teclado ou o pedal (o acionador da aba Conexões).

A pergunta tem um dono só, ``system_check.permissao_de_ler_a_entrada``, que abre um nó de evento
comum pelo mesmo dono da 08 (``utils.maquina.abrir_o_aparelho_de_entrada``) e o fecha na hora.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.cli import cmd_doctor
from hefesto_dualsense4unix.core import system_check
from hefesto_dualsense4unix.utils import maquina

#: O ``capabilities/key`` de um teclado (só teclas baixas) e o de um controle (com BTN_SOUTH).
TECLAS_DE_TECLADO = "fffffffffffffffe"
TECLAS_DE_CONTROLE = "7fff000000000000 0 0 0 0"
#: O de um manche sem ``BTN_SOUTH``: só ``BTN_TRIGGER`` (0x120), que também ganha a ACL da sessão.
TECLAS_DE_MANCHE = "100000000 0 0 0 0"


def _no(raiz: Path, evento: str, *, nome: str, vendor: str = "1a2c", teclas: str = "") -> None:
    dentro = raiz / evento / "device"
    (dentro / "id").mkdir(parents=True)
    (dentro / "capabilities").mkdir()
    (dentro / "name").write_text(nome + "\n", encoding="utf-8")
    (dentro / "phys").write_text("usb-0000:00:14.0-1/input0\n", encoding="utf-8")
    (dentro / "id" / "vendor").write_text(vendor + "\n", encoding="utf-8")
    (dentro / "id" / "product").write_text("0002\n", encoding="utf-8")
    (dentro / "capabilities" / "key").write_text((teclas or "0") + "\n", encoding="utf-8")


class _Aberto:
    def __init__(self) -> None:
        self.fechado = False

    def close(self) -> None:
        self.fechado = True


def _recusa(evento: str) -> Any:
    raise maquina.SemPermissaoDeLerError(
        13, maquina.FRASE_SEM_PERMISSAO_DE_LER, f"/dev/input/{evento}")


def test_o_aparelho_que_recusa_a_leitura_da_warn_com_a_frase_do_dono(tmp_path: Path) -> None:
    _no(tmp_path, "event3", nome="Teclado USB", teclas=TECLAS_DE_TECLADO)

    tag, mensagem = system_check.permissao_de_ler_a_entrada(raiz=str(tmp_path), abrir=_recusa)

    assert tag == "[WARN]"
    assert mensagem is maquina.FRASE_SEM_PERMISSAO_DE_LER


def test_o_aparelho_que_abre_da_ok_e_fecha_na_hora(tmp_path: Path) -> None:
    _no(tmp_path, "event3", nome="Pedal USB", teclas=TECLAS_DE_TECLADO)
    abertos: list[tuple[str, _Aberto]] = []

    def abrir(evento: str) -> _Aberto:
        aberto = _Aberto()
        abertos.append((evento, aberto))
        return aberto

    tag, mensagem = system_check.permissao_de_ler_a_entrada(raiz=str(tmp_path), abrir=abrir)

    assert (tag, mensagem) == ("[ OK ]", system_check.LINHA_LE_A_ENTRADA)
    assert [e for e, _ in abertos] == ["event3"]
    assert abertos[0][1].fechado, "o doctor nunca segura o aparelho aberto"


def test_a_pasta_vazia_da_info(tmp_path: Path) -> None:
    def abrir(evento: str) -> Any:
        raise AssertionError(f"nada para abrir, e abriu {evento}")

    tag, mensagem = system_check.permissao_de_ler_a_entrada(raiz=str(tmp_path), abrir=abrir)

    assert (tag, mensagem) == ("[INFO]", system_check.LINHA_SEM_ENTRADA_PARA_MEDIR)


def test_controle_dualsense_e_no_do_hefesto_ficam_fora_da_medida(tmp_path: Path) -> None:
    """O nó de controle e o do DualSense têm a permissão do broker; o do Hefesto é nosso."""
    _no(tmp_path, "event1", nome="Pro Controller", vendor="057e", teclas=TECLAS_DE_CONTROLE)
    _no(tmp_path, "event2", nome="DualSense Wireless Controller Touchpad", vendor="054c",
        teclas=TECLAS_DE_TECLADO)
    _no(tmp_path, "event4", nome="Hefesto Virtual Keyboard", teclas=TECLAS_DE_TECLADO)
    _no(tmp_path, "event5", nome="Power Button", teclas="")
    abertos: list[str] = []

    def abrir(evento: str) -> _Aberto:
        abertos.append(evento)
        return _Aberto()

    tag, _ = system_check.permissao_de_ler_a_entrada(raiz=str(tmp_path), abrir=abrir)

    assert tag == "[INFO]"
    assert abertos == []


def test_o_manche_sem_btn_south_tambem_fica_fora_da_medida(tmp_path: Path) -> None:
    """O joystick tem a ACL da sessão: abri-lo daria [ OK ] numa máquina que não lê o teclado."""
    _no(tmp_path, "event1", nome="Manche USB", vendor="044f", teclas=TECLAS_DE_MANCHE)
    _no(tmp_path, "event3", nome="Teclado USB", teclas=TECLAS_DE_TECLADO)
    abertos: list[str] = []

    def abrir(evento: str) -> _Aberto:
        abertos.append(evento)
        if evento == "event3":
            _recusa(evento)
        return _Aberto()

    tag, _ = system_check.permissao_de_ler_a_entrada(raiz=str(tmp_path), abrir=abrir)

    assert tag == "[WARN]"
    assert abertos == ["event3"]


def test_um_que_abre_vence_o_que_recusa(tmp_path: Path) -> None:
    _no(tmp_path, "event3", nome="Teclado A", teclas=TECLAS_DE_TECLADO)
    _no(tmp_path, "event7", nome="Teclado B", teclas=TECLAS_DE_TECLADO)

    def abrir(evento: str) -> _Aberto:
        if evento == "event3":
            _recusa(evento)
        return _Aberto()

    tag, _ = system_check.permissao_de_ler_a_entrada(raiz=str(tmp_path), abrir=abrir)

    assert tag == "[ OK ]"


def test_por_omissao_a_pergunta_abre_pelo_dono_da_08(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _no(tmp_path, "event3", nome="Teclado USB", teclas=TECLAS_DE_TECLADO)
    monkeypatch.setattr(maquina, "abrir_o_aparelho_de_entrada", _recusa)

    tag, mensagem = system_check.permissao_de_ler_a_entrada(raiz=str(tmp_path))

    assert tag == "[WARN]"
    assert mensagem is maquina.FRASE_SEM_PERMISSAO_DE_LER


def test_o_bloco_do_doctor_imprime_a_resposta_do_dono_e_devolve_a_gravidade(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(system_check, "permissao_de_ler_a_entrada",
                        lambda: ("[WARN]", maquina.FRASE_SEM_PERMISSAO_DE_LER))

    rc = cmd_doctor._print_bloco_entrada()

    assert rc == cmd_doctor._gravidade_das_linhas([("[WARN]", "")])
    assert rc > 0
    assert maquina.FRASE_SEM_PERMISSAO_DE_LER in capsys.readouterr().out.replace("\n", " ")


def test_o_aviso_da_permissao_sobe_o_codigo_de_saida_do_doctor(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """O ``doctor_cmd`` inteiro, com os outros blocos mudos: o [WARN] da permissão sai como 1."""
    import typer

    async def sem_daemon() -> list[tuple[str, str]]:
        return []

    for bloco in ("_print_storm_block", "_print_bloco_contratos", "_print_bloco_proton_fixado"):
        monkeypatch.setattr(cmd_doctor, bloco, lambda: 0)
    monkeypatch.setattr(cmd_doctor, "_find_doctor_sh", lambda: None)
    monkeypatch.setattr(cmd_doctor, "_avisar_ausente", lambda *a, **k: None)
    monkeypatch.setattr(cmd_doctor, "_print_bloco_perfis", lambda: False)
    monkeypatch.setattr(cmd_doctor, "_daemon_checks", sem_daemon)
    monkeypatch.setattr(system_check, "permissao_de_ler_a_entrada",
                        lambda: ("[WARN]", maquina.FRASE_SEM_PERMISSAO_DE_LER))

    with pytest.raises(typer.Exit) as saiu:
        cmd_doctor.doctor_cmd()

    assert saiu.value.exit_code == 1
    assert "== teclado e pedal" in capsys.readouterr().out


def test_a_suite_nunca_abre_o_teclado_desta_maquina() -> None:
    """A fixture da sessão (``tests/conftest.py``) põe a pergunta num ``/sys`` vazio.

    Sem ela, o ``doctor_cmd`` dos outros testes abria o aparelho de quem roda e o código de saída
    dependia do grupo ``input`` dessa pessoa.
    """
    def abrir(evento: str) -> Any:
        raise AssertionError(f"a suíte abriu o {evento} desta máquina")

    assert maquina.RAIZ_DAS_ENTRADAS != "/sys/class/input"
    assert system_check.permissao_de_ler_a_entrada(abrir=abrir) == (
        "[INFO]", system_check.LINHA_SEM_ENTRADA_PARA_MEDIR)
