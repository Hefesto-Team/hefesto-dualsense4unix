"""O-MODO-UNICO-VALE-PARA-TODOS-OS-CONTROLES-01 — a máscara é o modo único; o arquivo de antes sai.

D-2710-O-MODO-E-UM-SO-PARA-TODOS-OS-CONTROLES (27/10/2026): o `controller_masks.json`
guardava a máscara de CADA controle (MÁSCARA-01, E1). Agora a máscara é a do modo único,
igual para todos, e o arquivo que sobrar na casa vira o modo uma vez e sai do disco, sem
perder a escolha: com perfil ativo a migração do perfil já a levou; sem perfil, ela vai ao
padrão do computador; o pad desligado e o arquivo ilegível ficam onde estão.

MORDIDAS: devolva à `mascara_efetiva` a leitura por identidade (o P2 com outra máscara
reprova `test_a_mascara_e_a_mesma_para_todo_controle`); tire o `unlink` da migração (o
arquivo fica e `test_o_arquivo_sem_perfil_vai_ao_computador_e_sai` reprova).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.subsystems import external_mask as em
from hefesto_dualsense4unix.utils import session as session_mod
from hefesto_dualsense4unix.utils.session import load_gamepad_emulation, save_gamepad_emulation

MACS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
IDENTIDADE_VOLATIL = "dev:0003:057E:2009.0001"


@pytest.fixture(autouse=True)
def _casa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`config_dir` em tmp: o arquivo de antes e o flag da máquina."""
    from hefesto_dualsense4unix.utils import xdg_paths

    alvo = tmp_path / "config"

    def _config_dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(xdg_paths, "config_dir", _config_dir)
    monkeypatch.setattr(session_mod, "config_dir", _config_dir)
    return alvo


def _arquivo_de_antes(casa: Path, mascaras: list[str]) -> Path:
    casa.mkdir(parents=True, exist_ok=True)
    arquivo = casa / em.ARQUIVO_DE_MASCARAS_DE_ANTES
    entradas = [
        {"identity": mac.replace(":", ""), "flavor": mascara}
        for mac, mascara in zip(MACS, mascaras, strict=False)
    ]
    arquivo.write_text(json.dumps({"version": 1, "masks": entradas}), encoding="utf-8")
    return arquivo


def test_as_mascaras_validas_sao_as_tres() -> None:
    assert set(em.mascaras_validas()) == {"dualsense", "xbox", "nintendo"}
    assert em.normalizar_mascara(" XBOX ") == "xbox"
    assert em.normalizar_mascara("wiimote") is None


@pytest.mark.parametrize("modo", ["dualsense", "xbox", "nintendo"])
def test_a_mascara_e_a_mesma_para_todo_controle(modo: str) -> None:
    """Os quatro controles, e o de identidade volátil, recebem o modo único."""
    for quem in (*MACS, IDENTIDADE_VOLATIL, None):
        assert em.mascara_efetiva(quem, modo) == modo, quem


def test_sem_arquivo_nada_acontece(_casa: Path) -> None:
    assert em.o_arquivo_de_mascaras_vira_o_modo(None) is None
    assert not (_casa / em.ARQUIVO_DE_MASCARAS_DE_ANTES).exists()


def test_com_perfil_ativo_o_arquivo_so_sai(_casa: Path) -> None:
    """O perfil já levou a escolha ao `mode`: o arquivo era só o cache dele."""
    save_gamepad_emulation(True, "dualsense")
    arquivo = _arquivo_de_antes(_casa, ["xbox", "xbox"])

    assert em.o_arquivo_de_mascaras_vira_o_modo("Jogo") is None
    assert not arquivo.exists()
    assert load_gamepad_emulation() == (True, "dualsense"), "o computador não muda"


@pytest.mark.parametrize(
    ("mascaras", "fica"),
    [
        (["xbox"], "xbox"),
        (["nintendo", "nintendo", "xbox"], "nintendo"),
        (["xbox", "dualsense"], "xbox"),
    ],
)
def test_o_arquivo_sem_perfil_vai_ao_computador_e_sai(
    _casa: Path, mascaras: list[str], fica: str
) -> None:
    """Sem perfil, a escolha feita só no arquivo vai ao padrão do computador."""
    save_gamepad_emulation(True, "dualsense")
    arquivo = _arquivo_de_antes(_casa, mascaras)

    assert em.o_arquivo_de_mascaras_vira_o_modo(None) == fica
    assert not arquivo.exists()
    assert load_gamepad_emulation() == (True, fica)
    assert em.o_arquivo_de_mascaras_vira_o_modo(None) is None, "uma vez só"
    assert load_gamepad_emulation() == (True, fica)


def test_com_o_pad_desligado_o_arquivo_espera(_casa: Path) -> None:
    """Desligado, o padrão não tem onde guardar a máscara: o arquivo fica para o próximo boot."""
    save_gamepad_emulation(False, None)
    arquivo = _arquivo_de_antes(_casa, ["xbox"])
    antes = arquivo.read_bytes()

    assert em.o_arquivo_de_mascaras_vira_o_modo(None) is None
    assert arquivo.read_bytes() == antes
    assert load_gamepad_emulation()[0] is False


def test_o_arquivo_vazio_so_sai(_casa: Path) -> None:
    save_gamepad_emulation(True, "dualsense")
    arquivo = _arquivo_de_antes(_casa, [])

    assert em.o_arquivo_de_mascaras_vira_o_modo(None) is None
    assert not arquivo.exists()
    assert load_gamepad_emulation() == (True, "dualsense")


@pytest.mark.parametrize("conteúdo", ["{", "[]", '{"masks": "sei lá"}'])
def test_o_arquivo_ilegivel_fica_intocado(_casa: Path, conteúdo: str) -> None:
    """O que não se lê não se apaga: é o arquivo dela, e ninguém o reescreve."""
    save_gamepad_emulation(True, "dualsense")
    _casa.mkdir(parents=True, exist_ok=True)
    arquivo = _casa / em.ARQUIVO_DE_MASCARAS_DE_ANTES
    arquivo.write_text(conteúdo, encoding="utf-8")

    assert em.o_arquivo_de_mascaras_vira_o_modo(None) is None
    assert arquivo.read_text(encoding="utf-8") == conteúdo
    assert load_gamepad_emulation() == (True, "dualsense")
