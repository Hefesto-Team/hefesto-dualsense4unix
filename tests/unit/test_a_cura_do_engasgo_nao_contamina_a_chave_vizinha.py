"""Uma entrada é (CHAVE do registro + caminho) — nunca o caminho sozinho.

ENGASGO-VULKAN-01 (23/08/2026), defeito MEDIDO e curado no mesmo dia.

As camadas implícitas moram em DUAS chaves do `system.reg`, a de 64 bits e a de
32 (`Software\\Khronos\\...` e `Software\\Wow6432Node\\Khronos\\...`). Nada
impede o MESMO caminho de manifesto de estar registrado nas duas — e com
valores DIFERENTES, que é o caso que morde: ligada de um lado, já desligada do
outro.

Enquanto o alvo da escrita era só o caminho, `alvos.get(caminho)` casava a
mesma linha nas duas seções. Medido antes da cura, num prefixo de mentira com
64 em `dword:00000000` (ligada, candidata) e 32 em `dword:00000003` (já
desligada, que o próprio módulo classificava `e_sobra=False`):

    --- original ---            --- depois de curar ---
    Khronos      = 00000000     Khronos      = 00000001
    Wow6432Node  = 00000003     Wow6432Node  = 00000001   <- nunca foi alvo

    --- depois de devolver ---
    Khronos      = 00000000
    Wow6432Node  = 00000000   <- era 00000003. LIGADA sem nunca ter estado.

Dois defeitos num: a cura escreveu numa entrada que ela própria tinha dito que
não ia tocar, e a **reversibilidade byte a byte quebrou** — que é o requisito
que segura a promessa "o mesmo lugar devolve". Pior: o valor devolvido é
`00000000`, LIGADA, então desfazer *ligava* uma camada que estava desligada.

A cura foi passar a chave para dentro do alvo (`_reescrever`) e para dentro da
memória do estado local (`chave_de_estado`). Este arquivo é o portão dos dois.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

#: O mesmo manifesto, registrado nas duas larguras. Não é hipótese de
#: laboratório: instalador que não sabe a arquitetura do jogo grava nas duas.
MANIFESTO = r"C:\Program Files (x86)\Jogo\OverlayVkLayer.json"

#: A de 32 bits está em `00000003` — DESLIGADA, e por um valor que não é o
#: nosso `00000001`. Se algum dia ela voltar como `00000000` ou `00000001`, o
#: teste não distingue mais "devolvemos certo" de "escrevemos por cima".
_VALOR_VIZINHO = "00000003"


def _registro_nas_duas_chaves() -> str:
    """Um `system.reg` com o driver, e o mesmo manifesto nas duas chaves."""
    return "\n".join(
        [
            "WINE REGISTRY Version 2",
            ";; All keys relative to REGISTRY\\\\Machine",
            "",
            "[Software\\\\Khronos\\\\Vulkan\\\\Drivers] 1774238072",
            '"C:\\\\windows\\\\system32\\\\winevulkan.json"=dword:00000000',
            "",
            "[Software\\\\Khronos\\\\Vulkan\\\\ImplicitLayers] 1783894861",
            f'"{cv._escapar(MANIFESTO)}"=dword:00000000',
            "",
            "[Software\\\\Wow6432Node\\\\Khronos\\\\Vulkan\\\\ImplicitLayers] 1783894861",
            f'"{cv._escapar(MANIFESTO)}"=dword:{_VALOR_VIZINHO}',
            "",
        ]
    )


@pytest.fixture()
def prefixo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`compatdata/4242` com o registro acima, e o estado local em `tmp_path`."""
    raiz = tmp_path / "compatdata" / "4242"
    (raiz / "pfx").mkdir(parents=True)
    (raiz / "pfx" / "system.reg").write_text(
        _registro_nas_duas_chaves(), encoding="utf-8"
    )
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return raiz


def _valores(registro: Path) -> dict[str, str]:
    """`{chave_curta: dword}` das entradas de camada — a régua independente.

    Lê o arquivo com um parser BOBO (fatiar texto), de propósito: medir o
    resultado do módulo com o próprio `ler_camadas` do módulo aprovaria um
    parser quebrado junto com a escrita quebrada.
    """
    saida: dict[str, str] = {}
    chave = ""
    for linha in registro.read_text(encoding="utf-8").splitlines():
        if linha.startswith("["):
            chave = "32" if "Wow6432Node" in linha else "64"
            if "ImplicitLayers" not in linha:
                chave = "driver-" + chave
            continue
        if "OverlayVkLayer.json" in linha and "=dword:" in linha:
            saida[chave] = linha.rsplit(":", 1)[1]
    return saida


# ---------------------------------------------------------------------------
# 1. A leitura já separava as duas — é a ESCRITA que não separava
# ---------------------------------------------------------------------------


def test_a_leitura_ve_duas_entradas_distintas_com_o_mesmo_caminho(
    prefixo: Path,
) -> None:
    """Anticircularidade: sem duas entradas lidas, o resto do arquivo é vazio."""
    camadas = cv.ler_camadas(prefixo / "pfx" / "system.reg", prefixo=prefixo)
    assert len(camadas) == 2
    assert {c.caminho_windows for c in camadas} == {MANIFESTO}
    assert {c.chave for c in camadas} == set(cv.CHAVES_DE_CAMADAS)

    por_chave = {c.chave: c for c in camadas}
    de_64 = por_chave[r"Software\Khronos\Vulkan\ImplicitLayers"]
    de_32 = por_chave[r"Software\Wow6432Node\Khronos\Vulkan\ImplicitLayers"]
    assert de_64.ligada is True and de_64.e_sobra is True
    assert de_32.ligada is False and de_32.e_sobra is False


# ---------------------------------------------------------------------------
# 2. A mordida: curar não pode tocar a entrada que não é candidata
# ---------------------------------------------------------------------------


def test_o_mesmo_manifesto_nas_duas_chaves_nao_contamina_a_outra(
    prefixo: Path, tmp_path: Path
) -> None:
    """Só a entrada LIGADA muda. A vizinha, já desligada, fica no valor dela."""
    registro = prefixo / "pfx" / "system.reg"
    assert _valores(registro) == {"64": "00000000", "32": _VALOR_VIZINHO}

    resultado = cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo), forcar=True, home=tmp_path / "casa"
    )
    assert resultado.erro == ""
    assert resultado.desligadas == ("OverlayVkLayer.json",)

    depois = _valores(registro)
    assert depois["64"] == "00000001", "a entrada candidata tinha de ser desligada"
    assert depois["32"] == _VALOR_VIZINHO, (
        "a entrada da OUTRA chave não era candidata (e_sobra=False) e foi "
        f"escrita mesmo assim: {depois['32']} em vez de {_VALOR_VIZINHO}"
    )


def test_devolver_traz_as_duas_chaves_de_volta_byte_a_byte(
    prefixo: Path, tmp_path: Path
) -> None:
    """Reversibilidade é byte a byte, inclusive com caminho repetido."""
    registro = prefixo / "pfx" / "system.reg"
    casa = tmp_path / "casa"
    antes = registro.read_bytes()

    cv.aplicar_no_prefixo(cv.prefixo_de_jogo(prefixo), forcar=True, home=casa)
    assert registro.read_bytes() != antes, "a cura não fez nada — teste sem mordida"

    cv.aplicar_no_prefixo(cv.prefixo_de_jogo(prefixo), religar=True, home=casa)
    assert registro.read_bytes() == antes, (
        "devolver não restaurou o registro byte a byte — o valor da chave "
        f"vizinha voltou como {_valores(registro).get('32')!r}"
    )


def test_o_estado_guarda_uma_linha_por_chave_e_nao_uma_por_caminho(
    prefixo: Path, tmp_path: Path
) -> None:
    """O `valor_antes` de uma entrada não pode sobrescrever o da outra.

    É a causa-raiz do defeito: memória indexada por caminho guardava UMA linha
    para DUAS entradas, e o `valor_antes` do segundo apagava o do primeiro.
    """
    casa = tmp_path / "casa"
    cv.aplicar_no_prefixo(cv.prefixo_de_jogo(prefixo), forcar=True, home=casa)

    bruto = json.loads(
        cv.caminho_do_estado(casa).read_text(encoding="utf-8")
    )["prefixos"]["4242"]
    # Uma entrada só foi desligada (a outra já estava), então o estado tem uma
    # linha — mas a CHAVE dela tem de distinguir de qual das duas se trata.
    assert len(bruto) == 1
    (marca,) = bruto
    assert marca.startswith(r"Software\Khronos\Vulkan\ImplicitLayers|")
    assert marca.endswith(MANIFESTO)
    assert bruto[marca]["valor_antes"] == "00000000"


def test_a_marca_do_estado_separa_as_duas_chaves() -> None:
    """`chave_de_estado` é injetiva onde importa: mesma folha, chaves diferentes."""
    marcas = {cv.chave_de_estado(chave, MANIFESTO) for chave in cv.CHAVES_DE_CAMADAS}
    assert len(marcas) == 2
