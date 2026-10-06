"""O estado REAL da máquina do usuário em 23/08/2026, e a cura tem de conviver com ele."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("frase do censo do modo jogo")

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

WIN64 = (
    r"C:\Program Files (x86)\Epic Games\Epic Online Services"
    r"\managedArtifacts\98bc04bc842e4906993fd6d6644ffb8d"
    r"\EOSOverlayVkLayer-Win64.json"
)
WIN32 = WIN64.replace("Win64", "Win32")

SUFIXO_DELA = ".desligado"


@pytest.fixture()
def prefixo_dela(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`compatdata/1599660` no estado exato em que a máquina do usuário está."""
    raiz = tmp_path / "compatdata" / "1599660"
    (raiz / "pfx").mkdir(parents=True)
    (raiz / "pfx" / "system.reg").write_text(
        "\n".join(
            [
                "WINE REGISTRY Version 2",
                "",
                "[Software\\\\Khronos\\\\Vulkan\\\\Drivers] 1774238072",
                '"C:\\\\windows\\\\system32\\\\winevulkan.json"=dword:00000000',
                "",
                "[Software\\\\Khronos\\\\Vulkan\\\\ImplicitLayers] 1783894861",
                "#time=1dd124cb857832a",
                f'"{cv._escapar(WIN64)}"=dword:00000000',
                "",
                "[Software\\\\Wow6432Node\\\\Khronos\\\\Vulkan\\\\ImplicitLayers] 1783894861",
                "#time=1dd124cb8577cea",
                f'"{cv._escapar(WIN32)}"=dword:00000000',
                "",
            ]
        ),
        encoding="utf-8",
    )
    pasta = cv.caminho_no_prefixo(raiz, WIN64)
    assert pasta is not None
    pasta.parent.mkdir(parents=True)
    for caminho in (WIN64, WIN32):
        alvo = cv.caminho_no_prefixo(raiz, caminho)
        assert alvo is not None
        alvo.with_name(alvo.name + SUFIXO_DELA).write_text("{}", encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return raiz


def _manifestos_no_disco(raiz: Path) -> set[str]:
    """Régua independente: os nomes de arquivo que existem, lidos do disco."""
    alvo = cv.caminho_no_prefixo(raiz, WIN64)
    assert alvo is not None
    return {p.name for p in alvo.parent.iterdir()}


def test_a_camada_renomeada_a_mao_esta_ligada_no_registro_e_ausente_no_disco(
    prefixo_dela: Path,
) -> None:
    prefixo = cv.prefixo_de_jogo(prefixo_dela, appid="1599660")
    assert len(prefixo.camadas) == 2
    for camada in prefixo.camadas:
        assert camada.ligada is True, "o registro diz 00000000 = LIGADA"
        assert camada.presente is False, (
            "o manifesto está renomeado; o caminho registrado não existe"
        )
        assert camada.e_sobra is True, (
            "entrada viva no registro continua sendo trabalho para a cura"
        )


def test_curar_desliga_as_duas_entradas_sem_tocar_nos_arquivos_dela(
    prefixo_dela: Path, tmp_path: Path
) -> None:
    """Instrução explícita: *não desfaça* — é o estado que ela está usando."""
    antes = _manifestos_no_disco(prefixo_dela)
    assert antes == {
        "EOSOverlayVkLayer-Win64.json.desligado",
        "EOSOverlayVkLayer-Win32.json.desligado",
    }

    resultado = cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo_dela, appid="1599660"),
        forcar=True,
        home=tmp_path / "casa",
    )
    assert resultado.erro == ""
    assert sorted(resultado.desligadas) == [
        "EOSOverlayVkLayer-Win32.json",
        "EOSOverlayVkLayer-Win64.json",
    ]

    texto = (prefixo_dela / "pfx" / "system.reg").read_text(encoding="utf-8")
    assert texto.count("=dword:00000001") == 2
    assert '"C:\\\\windows\\\\system32\\\\winevulkan.json"=dword:00000000' in texto

    assert _manifestos_no_disco(prefixo_dela) == antes, (
        "a cura renomeou/apagou arquivo dentro do prefixo dela — ela só pode "
        "escrever no system.reg e no backup dele"
    )


def test_devolver_volta_byte_a_byte_e_os_arquivos_dela_seguem_como_estavam(
    prefixo_dela: Path, tmp_path: Path
) -> None:
    registro = prefixo_dela / "pfx" / "system.reg"
    casa = tmp_path / "casa"
    original = registro.read_bytes()
    arquivos = _manifestos_no_disco(prefixo_dela)

    cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo_dela, appid="1599660"), forcar=True, home=casa
    )
    assert registro.read_bytes() != original, "a cura não escreveu — teste sem mordida"

    cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo_dela, appid="1599660"), religar=True, home=casa
    )
    assert registro.read_bytes() == original
    assert _manifestos_no_disco(prefixo_dela) == arquivos


def test_o_lancamento_seguinte_nao_desfaz_a_devolucao_dela(
    prefixo_dela: Path, tmp_path: Path
) -> None:
    """O usuário clicou em devolver; abrir o jogo de novo não pode desligar outra vez."""
    casa = tmp_path / "casa"
    cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo_dela, appid="1599660"), forcar=True, home=casa
    )
    cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo_dela, appid="1599660"), religar=True, home=casa
    )

    resultado = cv.curar_um_prefixo(prefixo_dela, appid="1599660", home=casa)
    assert resultado.desligadas == ()
    assert sorted(resultado.respeitadas) == [
        "EOSOverlayVkLayer-Win32.json",
        "EOSOverlayVkLayer-Win64.json",
    ]
    texto = (prefixo_dela / "pfx" / "system.reg").read_text(encoding="utf-8")
    assert texto.count("=dword:00000001") == 0
