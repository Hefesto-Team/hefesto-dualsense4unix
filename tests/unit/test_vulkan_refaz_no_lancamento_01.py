"""O gancho de lançamento REFAZ a cura das camadas Vulkan — e o botão continua mandando.

VULKAN-REFAZ-01 (16/09/2026). O módulo `camadas_vulkan` prometia, no próprio
docstring, que *"se ainda assim um `wineserver` sobrescrever, a mudança se perde
e o próximo lançamento a refaz"*. **Seiscentas linhas abaixo, o código dizia o
contrário**, e a colisão é o defeito que este arquivo trava.

A regra 2 de `aplicar_no_prefixo` (pedido dela de 09/08/2026) dizia: *"religar
por fora também conta como escolha — se o registro mostra LIGADA uma camada que
NÓS desligamos, alguém a religou sem passar por aqui; marque `manter` e saia"*.
A premissa era que só uma PESSOA poderia ter religado. Ela é falsa: o Wine
mantém o registro do prefixo em MEMÓRIA e o regrava ao sair, devolvendo a
camada a `dword:00000000` sozinho — **byte por byte o mesmo** que uma edição à
mão do `system.reg`. Os dois casos são indistinguíveis no registro, e o
desempate caía sempre no lado que aposentava a cura: um prefixo curado uma vez
e reaberto uma vez ganhava `manter` PERMANENTE e nunca mais era curado.

Decisão dela, 16/09/2026, textual: *"Refazer sempre no lançamento; só o botão
devolver é permanente. O botão vira a única voz de escolha e o wineserver perde
o voto."* Com a restrição dura que veio junto: **sem adicionar nada novo na
interface** — o botão «devolver» já existia, e nenhuma tela mudou.

O que cada bloco trava:

1. **o gancho refaz** — camada que reaparece ligada é desligada de novo;
2. **o botão continua permanente** — `manter` vindo de `religar=True` é
   respeitado por quantos lançamentos vierem;
3. **o botão continua vencendo** — `forcar=True` limpa o `manter` e desliga;
4. **o estado antigo destrava** — `religada-por-fora` já gravado na máquina de
   quem usou o produto entre 09/08 e 16/09 deixa de travar o gancho, **sem**
   derrubar junto o `religada` que veio do botão. Este é o bloco que separa os
   dois `manter` que convivem no arquivo de estado real dela.

O estado real dela em 16/09/2026 às 01:31 tem DUAS camadas do Epic Online
Services no appid 1599660 com `{"feito": "religada", "escolha": "manter"}` —
gravadas pelo BOTÃO. Essas são escolha de verdade e o bloco 4 prova que
continuam respeitadas.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

#: O overlay do Epic, que é a sobra real que originou o módulo.
EPIC = r"C:\Program Files (x86)\Epic Games\EOSOverlayVkLayer-Win64.json"

#: A chave de 64 bits, como o `system.reg` a escreve (desescapada).
CHAVE64 = "Software\\Khronos\\Vulkan\\ImplicitLayers"

_CABECALHO = "WINE REGISTRY Version 2\n;; All keys relative to REGISTRY\\\\Machine\n\n"


def _registro(dword: str = "00000000") -> str:
    """Um `system.reg` com o driver do Wine e UMA sobra do Epic.

    O driver entra sempre, na chave dele: nenhum teste daqui pode rodar contra
    um registro mais fácil que o da máquina dela.
    """
    return "\n".join(
        [
            _CABECALHO,
            "[Software\\\\Khronos\\\\Vulkan\\\\Drivers] 1774238072",
            '"C:\\\\windows\\\\system32\\\\winevulkan.json"=dword:00000000',
            "",
            "[Software\\\\Khronos\\\\Vulkan\\\\ImplicitLayers] 1783894861",
            f'"{cv._escapar(EPIC)}"=dword:{dword}',
            "",
        ]
    )


@pytest.fixture()
def prefixo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um `compatdata/222` com a sobra do Epic LIGADA, e um XDG de mentira."""
    raiz = tmp_path / "steamapps" / "compatdata" / "222"
    (raiz / "pfx").mkdir(parents=True)
    (raiz / "pfx" / "system.reg").write_text(_registro(), encoding="utf-8")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return raiz


@pytest.fixture()
def casa(tmp_path: Path) -> Path:
    """A casa onde o estado é gravado. Sempre explícita, nunca o HOME real."""
    return tmp_path / "casa"


def _texto(prefixo: Path) -> str:
    return (prefixo / "pfx" / "system.reg").read_text(encoding="utf-8")


def _estado_bruto(casa: Path) -> dict:
    """Lê o JSON do estado sem passar pelo módulo — régua independente."""
    return json.loads(_estado_cru(casa))


def _estado_cru(casa: Path) -> str:
    """O texto do arquivo de estado, sem interpretar nada."""
    return cv.caminho_do_estado(casa).read_text(encoding="utf-8")


def _plantar_estado(casa: Path, feito: str, escolha: str = "manter") -> None:
    """Grava à mão um estado como o de uma máquina que já usou o produto.

    Escreve pelo `gravar_estado` do módulo para que a forma do arquivo (o
    `formato`, o envelope `prefixos`) seja a real, e não uma imitação que
    envelhece sozinha.
    """
    marca = cv.chave_de_estado(CHAVE64, EPIC)
    cv.gravar_estado(
        {
            "222": {
                marca: {
                    "feito": feito,
                    "escolha": escolha,
                    "quando": "2026-09-16T01:31:43",
                }
            }
        },
        casa,
    )


# ---------------------------------------------------------------------------
# 1. O gancho REFAZ — é a decisão (c) dela, e é o ponto inteiro
# ---------------------------------------------------------------------------


def test_a_camada_que_reaparece_ligada_e_desligada_de_novo(
    prefixo: Path, casa: Path
) -> None:
    """O wineserver regravou o registro; o lançamento seguinte tem de curar de novo."""
    primeiro = cv.curar_um_prefixo(prefixo, appid="222", home=casa)
    assert primeiro.desligadas == ("EOSOverlayVkLayer-Win64.json",)
    assert "dword:00000001" in _texto(prefixo)

    # O `wineserver` regrava o que tinha em memória: a camada volta a LIGADA.
    (prefixo / "pfx" / "system.reg").write_text(_registro("00000000"), encoding="utf-8")

    segundo = cv.curar_um_prefixo(prefixo, appid="222", home=casa)
    assert segundo.desligadas == ("EOSOverlayVkLayer-Win64.json",), (
        "o gancho aceitou a volta como escolha dela — é exatamente o defeito "
        "que a decisão dela de 16/09/2026 mandou matar"
    )
    assert segundo.respeitadas == ()
    assert "dword:00000001" in _texto(prefixo)


def test_refazer_dez_vezes_nunca_grava_manter(prefixo: Path, casa: Path) -> None:
    """A cura tem de aguentar o ciclo inteiro sem se aposentar por cansaço.

    Um `manter` gravado por engano em QUALQUER volta encerra a cura para
    sempre; por isso a régua vive no tempo, e não num instante só.
    """
    for volta in range(10):
        (prefixo / "pfx" / "system.reg").write_text(
            _registro("00000000"), encoding="utf-8"
        )
        resultado = cv.curar_um_prefixo(prefixo, appid="222", home=casa)
        assert resultado.desligadas == ("EOSOverlayVkLayer-Win64.json",), (
            f"a cura parou de ser refeita na volta {volta}"
        )

    marca = cv.chave_de_estado(CHAVE64, EPIC)
    gravado = _estado_bruto(casa)["prefixos"]["222"][marca]
    assert gravado["feito"] == "desligada"
    assert "escolha" not in gravado, (
        "o gancho gravou escolha dela sem ela ter tocado em botão nenhum"
    )


def test_o_valor_antes_continua_o_de_antes_da_nossa_escrita(
    prefixo: Path, casa: Path
) -> None:
    """Refazer não pode estragar o caminho de volta: devolver segue byte a byte."""
    original = (prefixo / "pfx" / "system.reg").read_bytes()
    cv.curar_um_prefixo(prefixo, appid="222", home=casa)
    (prefixo / "pfx" / "system.reg").write_text(_registro("00000000"), encoding="utf-8")
    cv.curar_um_prefixo(prefixo, appid="222", home=casa)

    devolvido = cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo, appid="222"), religar=True, home=casa
    )
    assert devolvido.religadas == ("EOSOverlayVkLayer-Win64.json",)
    assert (prefixo / "pfx" / "system.reg").read_bytes() == original, (
        "a segunda cura perdeu o `valor_antes` e devolver não recompõe o registro"
    )


# ---------------------------------------------------------------------------
# 2. O BOTÃO continua sendo permanente — a única voz de escolha
# ---------------------------------------------------------------------------


def test_o_manter_vindo_do_botao_e_respeitado(prefixo: Path, casa: Path) -> None:
    """Ela clicou em «devolver»: nenhum lançamento pode desfazer isso."""
    cv.curar_um_prefixo(prefixo, appid="222", home=casa)
    cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo, appid="222"), religar=True, home=casa
    )

    resultado = cv.curar_um_prefixo(prefixo, appid="222", home=casa)
    assert resultado.desligadas == ()
    assert resultado.respeitadas == ("EOSOverlayVkLayer-Win64.json",)
    assert "dword:00000000" in _texto(prefixo)


def test_o_botao_aguenta_lancamentos_seguidos(prefixo: Path, casa: Path) -> None:
    """Permanente quer dizer permanente — não "sobrevive ao primeiro lançamento"."""
    cv.curar_um_prefixo(prefixo, appid="222", home=casa)
    cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo, appid="222"), religar=True, home=casa
    )

    for volta in range(5):
        resultado = cv.curar_um_prefixo(prefixo, appid="222", home=casa)
        assert resultado.desligadas == (), f"a escolha dela caiu na volta {volta}"
    assert "dword:00000000" in _texto(prefixo)


# ---------------------------------------------------------------------------
# 3. `forcar=True` continua limpando o `manter` — regra dela de 09/08/2026
# ---------------------------------------------------------------------------


def test_o_botao_forcar_limpa_o_manter_e_desliga(prefixo: Path, casa: Path) -> None:
    """A vontade da tela prevalece: o clique explícito vence a memória."""
    cv.curar_um_prefixo(prefixo, appid="222", home=casa)
    cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo, appid="222"), religar=True, home=casa
    )

    forcado = cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo, appid="222"), forcar=True, home=casa
    )
    assert forcado.desligadas == ("EOSOverlayVkLayer-Win64.json",)
    assert forcado.respeitadas == ()
    assert "dword:00000001" in _texto(prefixo)

    marca = cv.chave_de_estado(CHAVE64, EPIC)
    gravado = _estado_bruto(casa)["prefixos"]["222"][marca]
    assert gravado["feito"] == "desligada"
    assert "escolha" not in gravado, "o `manter` sobreviveu ao gesto explícito dela"


# ---------------------------------------------------------------------------
# 4. O estado JÁ GRAVADO: `religada-por-fora` destrava, `religada` fica
# ---------------------------------------------------------------------------


def test_o_estado_antigo_com_religada_por_fora_deixa_de_travar(
    prefixo: Path, casa: Path
) -> None:
    """A linha que a regra caduca escreveu não prova escolha nenhuma.

    Ela nasceu de uma inferência que o registro não sustenta, então o gancho
    passa a ignorá-la — sem reescrever o arquivo do usuário para isso.
    """
    _plantar_estado(casa, feito="religada-por-fora")

    resultado = cv.curar_um_prefixo(prefixo, appid="222", home=casa)
    assert resultado.desligadas == ("EOSOverlayVkLayer-Win64.json",), (
        "o `manter` forjado pela regra caduca continua aposentando a cura"
    )
    assert "dword:00000001" in _texto(prefixo)


def test_o_estado_antigo_com_religada_do_botao_continua_valendo(
    prefixo: Path, casa: Path
) -> None:
    """As DUAS camadas do Epic no estado real dela têm `feito: religada`.

    Foram gravadas às 01:31 de 16/09/2026 pelo BOTÃO, e são escolha de verdade.
    Se a cura da regra caduca as alcançasse junto, ela desfaria na primeira
    abertura de jogo o que ela acabara de pedir.
    """
    _plantar_estado(casa, feito="religada")

    resultado = cv.curar_um_prefixo(prefixo, appid="222", home=casa)
    assert resultado.desligadas == (), (
        "a escolha dela, gravada pelo botão, foi desfeita pelo gancho"
    )
    assert resultado.respeitadas == ("EOSOverlayVkLayer-Win64.json",)
    assert "dword:00000000" in _texto(prefixo)


def test_o_campo_feito_e_o_que_separa_os_dois_manter(casa: Path) -> None:
    """A régua da distinção, isolada: mesmo `escolha`, veredictos opostos.

    É o que permite conviver com o estado já gravado sem migração — o `feito`
    já carrega quem escreveu a linha.
    """
    do_botao = {"feito": "religada", "escolha": "manter"}
    da_regra_caduca = {"feito": "religada-por-fora", "escolha": "manter"}

    assert cv._e_escolha_dela(do_botao) is True
    assert cv._e_escolha_dela(da_regra_caduca) is False
    assert cv._e_escolha_dela({"feito": "desligada"}) is False
    assert cv._e_escolha_dela({}) is False


def test_nada_mais_escreve_o_marcador_caduco(prefixo: Path, casa: Path) -> None:
    """O `religada-por-fora` só pode existir no passado, nunca ser criado hoje.

    **A CONFERÊNCIA É FASE A FASE, e isso é conserto de uma régua que NÃO
    MORDIA** — medido em 16/09/2026, arrancando a cura de propósito. A primeira
    versão deste caso olhava o estado só NO FIM, depois de um `forcar=True`; só
    que o `forcar` regrava a linha com `feito: desligada` e **apagava o
    marcador antes da asserção chegar nele**. Com a regra 2 de volta no lugar,
    o teste passava igual: dava verde sobre o defeito que existe para pegar.

    Quem escreveria o marcador é o GANCHO, então é logo depois de cada passada
    do gancho que se olha — e não no fim, quando outro caminho já cobriu o
    rastro.
    """
    for volta in range(3):
        (prefixo / "pfx" / "system.reg").write_text(
            _registro("00000000"), encoding="utf-8"
        )
        cv.curar_um_prefixo(prefixo, appid="222", home=casa)
        assert cv._FEITO_CADUCO not in _estado_cru(casa), (
            f"o gancho gravou o marcador aposentado na volta {volta}"
        )

    cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo, appid="222"), religar=True, home=casa
    )
    assert cv._FEITO_CADUCO not in _estado_cru(casa), "o «devolver» gravou o marcador"

    cv.aplicar_no_prefixo(
        cv.prefixo_de_jogo(prefixo, appid="222"), forcar=True, home=casa
    )
    assert cv._FEITO_CADUCO not in _estado_cru(casa), "o «tirar» gravou o marcador"


# ---------------------------------------------------------------------------
# 5. A restrição dura dela: NADA novo na interface
# ---------------------------------------------------------------------------


def test_a_interface_nao_ganhou_gesto_novo_por_causa_disto() -> None:
    """*"sem adicionar nada novo na interface"* — ela, 16/09/2026.

    O caminho de volta continua sendo o botão «devolver» que já existia, pelo
    gesto `procurar-camadas`. Esta régua trava a tentação de resolver a decisão
    dela com mais um controle na tela.
    """
    aba = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "hefesto_dualsense4unix"
        / "interface"
        / "pacotes"
        / "a09_sistema.py"
    )
    texto = aba.read_text(encoding="utf-8")
    gestos = texto.count('@gesto("09-sistema.html", "procurar-camadas"')
    assert gestos == 1, f"o gesto das camadas deixou de ser um só: {gestos}"
    # A CHAMADA GANHOU UM ARGUMENTO em 21/09/2026 (`excluir=`, a lista de
    # exclusão do Hefesto), e a régua olha os DOIS que ela protege, não a
    # linha inteira digitada.
    chamada = re.search(r"cv\.curar_todos\(([^)]*)\)", texto)
    assert chamada is not None, "o botão não chama mais o curar_todos"
    assert re.search(r"\bforcar=True\b", chamada.group(1)), (
        "o botão parou de forçar; a regra dela de 09/08/2026 caiu junto"
    )
    assert re.search(r"\breligar=devolver\b", chamada.group(1)), chamada.group(1)
