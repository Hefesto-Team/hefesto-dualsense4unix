"""O estado REAL da máquina dela em 23/08/2026, e a cura tem de conviver com ele.

ENGASGO-VULKAN-01. Para medir o A/B, os dois manifestos do Epic foram
renomeados **à mão** no prefixo do Sackboy (appid 1599660):

    EOSOverlayVkLayer-Win64.json  ->  EOSOverlayVkLayer-Win64.json.desligado
    EOSOverlayVkLayer-Win32.json  ->  EOSOverlayVkLayer-Win32.json.desligado

O `system.reg` NÃO mudou: as duas entradas continuam lá, nas duas chaves, em
`dword:00000000` — que é **LIGADA**. Conferido no arquivo de verdade nesta
data, com `grep`, antes de escrever este teste.

É um estado meio-termo que engana fácil, e por isso tem portão próprio:

- pelo **registro**, a camada está ligada e é candidata — e é ela que volta a
  carregar no instante em que alguém desfizer a renomeação;
- pelo **disco**, ela é inerte agora, porque o carregador Vulkan não acha o
  manifesto no caminho registrado.

Dizer só "ligada" seria mentira de instrumento; dizer só "desligada" seria
pior, porque esconderia que a volta é um `mv` de distância. E a instrução foi
explícita: **não desfazer** o que ela deixou — a cura age no registro, nunca no
arquivo dela.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions.emulation_actions import frase_do_censo
from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

#: Os dois caminhos como estão no `system.reg` dela (a pasta longa do EOS foi
#: encurtada; o que morde é o nome do manifesto e as DUAS larguras).
WIN64 = (
    r"C:\Program Files (x86)\Epic Games\Epic Online Services"
    r"\managedArtifacts\98bc04bc842e4906993fd6d6644ffb8d"
    r"\EOSOverlayVkLayer-Win64.json"
)
WIN32 = WIN64.replace("Win64", "Win32")

#: O sufixo que ela usou. É o nome real no disco — não `-para-medir`, não
#: `.disabled`.
SUFIXO_DELA = ".desligado"


@pytest.fixture()
def prefixo_dela(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`compatdata/1599660` no estado exato em que a máquina dela está."""
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
    # Os manifestos EXISTEM, mas com o sufixo dela — que é o ponto todo.
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


# ---------------------------------------------------------------------------
# 1. A leitura conta a verdade inteira: viva no registro, ausente no disco
# ---------------------------------------------------------------------------


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


def test_o_produto_diz_pendurada_e_nao_ligada_seco(prefixo_dela: Path) -> None:
    """A frase da tela não pode achatar os dois estados num só."""
    prefixo = cv.prefixo_de_jogo(prefixo_dela, appid="1599660")
    texto, tem_sobra, _tem_devolucao = frase_do_censo([prefixo])
    assert tem_sobra is True
    assert "o arquivo não está no disco" in texto
    for linha in texto.splitlines():
        if "EOSOverlayVkLayer" in linha:
            assert not linha.rstrip().endswith("— ligada"), (
                "camada sem manifesto no disco descrita como 'ligada' seco: " + linha
            )


# ---------------------------------------------------------------------------
# 2. A cura age no REGISTRO — e não encosta no que ela renomeou
# ---------------------------------------------------------------------------


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
    # O driver, na chave dele, intocado.
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


# ---------------------------------------------------------------------------
# 3. O gancho de lançamento não briga com a escolha dela
# ---------------------------------------------------------------------------


def test_o_lancamento_seguinte_nao_desfaz_a_devolucao_dela(
    prefixo_dela: Path, tmp_path: Path
) -> None:
    """Ela clicou em devolver; abrir o jogo de novo não pode desligar outra vez."""
    casa = tmp_path / "casa"
    cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo_dela, appid="1599660"), forcar=True, home=casa
    )
    cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo_dela, appid="1599660"), religar=True, home=casa
    )

    # É por aqui que o `hefesto-launch.sh` entra, e ele nunca força.
    resultado = cv.curar_um_prefixo(prefixo_dela, appid="1599660", home=casa)
    assert resultado.desligadas == ()
    assert sorted(resultado.respeitadas) == [
        "EOSOverlayVkLayer-Win32.json",
        "EOSOverlayVkLayer-Win64.json",
    ]
    texto = (prefixo_dela / "pfx" / "system.reg").read_text(encoding="utf-8")
    assert texto.count("=dword:00000001") == 0
