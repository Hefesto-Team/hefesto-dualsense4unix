"""O portão mais importante desta leva: `winevulkan.json` NUNCA entra na mira."""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

REG_REAL = """WINE REGISTRY Version 2
;; All keys relative to REGISTRY\\\\Machine

#arch=win64

[Software\\\\Khronos\\\\Vulkan\\\\Drivers] 1774238072
#time=1dcba78c20ef6fe
"C:\\\\windows\\\\system32\\\\winevulkan.json"=dword:00000000

[Software\\\\Khronos\\\\Vulkan\\\\ImplicitLayers] 1783894861
#time=1dd124cb857832a
"C:\\\\Program Files (x86)\\\\Epic Games\\\\EOSOverlayVkLayer-Win64.json"=dword:00000000

[Software\\\\Wow6432Node\\\\Khronos\\\\Vulkan\\\\Drivers] 1774238073
"C:\\\\windows\\\\system32\\\\winevulkan.json"=dword:00000000

[Software\\\\Wow6432Node\\\\Khronos\\\\Vulkan\\\\ImplicitLayers] 1783894861
"C:\\\\Program Files (x86)\\\\Epic Games\\\\EOSOverlayVkLayer-Win32.json"=dword:00000000
"""


@pytest.fixture()
def prefixo(tmp_path: Path) -> Path:
    """Um `compatdata/<appid>` de mentira com o registro acima."""
    raiz = tmp_path / "compatdata" / "1599660"
    (raiz / "pfx").mkdir(parents=True)
    (raiz / "pfx" / "system.reg").write_text(REG_REAL, encoding="utf-8")
    return raiz


@pytest.mark.parametrize(
    "caminho",
    [
        r"C:\windows\system32\winevulkan.json",
        r"C:\WINDOWS\SYSTEM32\WINEVULKAN.JSON",
        r"C:\qualquer\outra\pasta\winevulkan.json",
        r"Z:\usr\share\vulkan\icd.d\winevulkan.json",
        r"C:\Windows\System32\WineVulkan.Json",
        "C:/windows/system32/winevulkan.json",
        "C:/windows\\system32/winevulkan.json",
        "winevulkan.json",
        r"system32\winevulkan.json",
        r".\winevulkan.json",
        r"C:\windows\system32\.\winevulkan.json",
        "  C:\\windows\\system32\\winevulkan.json  ",
        "\tC:\\windows\\system32\\winevulkan.json",
        r"\\?\C:\windows\system32\winevulkan.json",
        r"\\servidor\compartilhado\winevulkan.json",
    ],
)
def test_o_driver_do_wine_e_reconhecido_em_qualquer_caixa_e_pasta(caminho: str) -> None:
    """Todo caminho que eu consegui imaginar para o driver escapar da recusa."""
    assert cv._e_o_driver(caminho) is True


@pytest.mark.parametrize(
    "caminho",
    [
        r"C:\Jogo\winevulkan2.json",
        r"C:\Jogo\notwinevulkan.json",
        r"C:\Jogo\winevulkan.json.bak",
        r"C:\Jogo\meu-winevulkan-falso.json",
    ],
)
def test_nome_parecido_com_o_driver_nao_e_o_driver_mas_ainda_assim_e_recusado(
    caminho: str,
) -> None:
    """Parecido não é igual — e mesmo assim a cura não mira nele."""
    assert cv._e_o_driver(caminho) is False, "substring virou igualdade"
    assert cv.dono_preservado(caminho) is not None, "caiu na mira da cura"


def test_a_recusa_do_driver_e_por_nome_inteiro_e_nao_por_substring() -> None:
    """Anticircularidade das duas listas acima: elas têm de discordar."""
    assert cv._e_o_driver(r"C:\windows\system32\winevulkan.json") is True
    assert cv._e_o_driver(r"C:\Jogo\notwinevulkan.json") is False
    assert cv.dono_preservado(r"C:\Jogo\EOSOverlayVkLayer-Win64.json") is None


def test_o_driver_do_wine_nunca_e_sobra() -> None:
    """Sobra é o que a cura desligaria. O driver não pode ser sobra jamais."""
    camada = cv.Camada(
        caminho_windows=r"C:\windows\system32\winevulkan.json",
        chave=cv.CHAVES_DE_CAMADAS[0],
        valor="00000000",
        ligada=True,
        presente=True,
        arquivo=None,
        preservada_por=cv.dono_preservado(r"C:\windows\system32\winevulkan.json"),
    )
    assert camada.e_o_driver is True
    assert camada.e_sobra is False


def test_a_leitura_so_enxerga_a_chave_das_camadas_implicitas(prefixo: Path) -> None:
    """O driver mora em `Vulkan\\Drivers`; a cura só lê `ImplicitLayers`."""
    camadas = cv.ler_camadas(prefixo / "pfx" / "system.reg", prefixo=prefixo)
    nomes = sorted(c.nome_curto for c in camadas)
    assert nomes == ["EOSOverlayVkLayer-Win32.json", "EOSOverlayVkLayer-Win64.json"]
    assert all(c.chave in cv.CHAVES_DE_CAMADAS for c in camadas)


def test_a_escrita_recusa_o_driver_mesmo_pedido_de_frente(
    prefixo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Chamador pedindo o driver na bandeja: recusa, e o arquivo não muda."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    registro = prefixo / "pfx" / "system.reg"
    antes = registro.read_bytes()

    driver = cv.Camada(
        caminho_windows=r"C:\windows\system32\winevulkan.json",
        chave=cv.CHAVES_DE_CAMADAS[0],
        valor="00000000",
        ligada=True,
        presente=True,
        arquivo=None,
        preservada_por=None,
    )
    torto = cv.PrefixoDeJogo(
        appid="1599660",
        raiz=prefixo,
        registro=registro,
        camadas=(driver,),
    )
    assert driver.e_sobra is False

    resultado = cv.aplicar_no_prefixo(torto, forcar=True)
    assert resultado.desligadas == ()
    assert registro.read_bytes() == antes

    class DriverQueMente(cv.Camada):  # type: ignore[misc]
        @property
        def e_sobra(self) -> bool:
            return True

        @property
        def e_o_driver(self) -> bool:
            return False

    mentiroso = DriverQueMente(
        caminho_windows=r"C:\windows\system32\winevulkan.json",
        chave=cv.CHAVES_DE_CAMADAS[0],
        valor="00000000",
        ligada=True,
        presente=True,
        arquivo=None,
        preservada_por=None,
    )
    pior = cv.PrefixoDeJogo(
        appid="1599660", raiz=prefixo, registro=registro, camadas=(mentiroso,)
    )
    resultado = cv.aplicar_no_prefixo(pior, forcar=True)
    assert resultado.desligadas == ()
    assert "driver do Wine" in resultado.erro
    assert registro.read_bytes() == antes


def test_curar_de_verdade_desliga_a_sobra_e_deixa_o_driver_em_zero(
    prefixo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A prova pelo lado positivo: a cura age, e as linhas do driver ficam."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    registro = prefixo / "pfx" / "system.reg"

    resultado = cv.curar_um_prefixo(prefixo, appid="1599660")
    assert sorted(resultado.desligadas) == [
        "EOSOverlayVkLayer-Win32.json",
        "EOSOverlayVkLayer-Win64.json",
    ]

    texto = registro.read_text(encoding="utf-8")
    assert texto.count('"C:\\\\windows\\\\system32\\\\winevulkan.json"=dword:00000000') == 2
    assert "EOSOverlayVkLayer-Win64.json\"=dword:00000001" in texto
    assert "EOSOverlayVkLayer-Win32.json\"=dword:00000001" in texto


def test_o_driver_dentro_de_implicitlayers_e_ignorado_e_a_sobra_ainda_cura(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caso patológico: o driver registrado na chave ERRADA, e repetido."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    raiz = tmp_path / "compatdata" / "1599660"
    (raiz / "pfx").mkdir(parents=True)
    registro = raiz / "pfx" / "system.reg"
    registro.write_text(
        "\n".join(
            [
                "WINE REGISTRY Version 2",
                "",
                "[Software\\\\Khronos\\\\Vulkan\\\\ImplicitLayers] 1783894861",
                '"C:\\\\windows\\\\system32\\\\winevulkan.json"=dword:00000000',
                '"C:\\\\Windows\\\\System32\\\\WineVulkan.Json"=dword:00000000',
                '"C:/windows/system32/winevulkan.json"=dword:00000000',
                '"  C:\\\\windows\\\\system32\\\\winevulkan.json  "=dword:00000000',
                '"C:\\\\Jogo\\\\EOSOverlayVkLayer-Win64.json"=dword:00000000',
                "",
            ]
        ),
        encoding="utf-8",
    )

    resultado = cv.curar_um_prefixo(raiz, appid="1599660")
    assert resultado.erro == ""
    assert resultado.desligadas == ("EOSOverlayVkLayer-Win64.json",)

    texto = registro.read_text(encoding="utf-8")
    assert texto.count("=dword:00000000") == 4, (
        "alguma grafia do driver do Wine foi desligada:\n" + texto
    )
    assert texto.count("=dword:00000001") == 1
    assert 'EOSOverlayVkLayer-Win64.json"=dword:00000001' in texto


def test_o_driver_esta_na_lista_de_preservados_com_dono_declarado() -> None:
    """Cinto por cima do suspensório: além da recusa, ele é preservado."""
    dono = cv.dono_preservado(r"C:\windows\system32\winevulkan.json")
    assert dono is not None
    assert "Wine" in dono
