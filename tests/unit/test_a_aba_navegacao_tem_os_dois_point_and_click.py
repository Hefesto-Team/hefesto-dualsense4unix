"""Os dois point and click da Navegação: o perfil que a aba escolhe e a velocidade que funciona.

Absorve A-ABA-NAVEGACAO-TEM-OS-DOIS-POINT-AND-CLICK-E-A-VELOCIDADE-QUE-FUNCIONA-01. A página não
diz «sem efeito hoje», não tem número de passo sem gesto fora da Acessibilidade, e os dois donos do
R3 (o clique e a direção) são duas linhas do mesmo desenho. O «Perfil de point and click» lista os
moldes do produto e guarda a escolha no perfil ativo (sem jogo, o `maquina.json`). A barra
do cursor e a da rolagem gravam o valor absoluto em `mouse.speed` e `mouse.scroll_speed`,
lido de volta do disco.

MORDIDAS: devolver o «sem efeito hoje», um `bignum` sem gesto fora da Acessibilidade, um
molde fora do select, o gesto que não grava a escolha ou a velocidade ao `mouse.speed` reprovam.
"""

from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.utils import maquina as m

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup" / "06-navegacao.html"
PUBLICADAS = RAIZ / "src/hefesto_dualsense4unix/interface/paginas"
PUBLICADA = PUBLICADAS / "06-navegacao.html"


def _sem_estilo(caminho: pathlib.Path) -> str:
    bruto = caminho.read_text(encoding="utf-8")
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", bruto, flags=re.S)


def test_nenhuma_pagina_diz_sem_efeito_hoje() -> None:
    assert "sem efeito hoje" not in _sem_estilo(MOCKUP)
    publicada = _sem_estilo(PUBLICADA)
    if 'data-gesto="quem-navega"' not in publicada:
        pytest.skip("a página publicada ainda é a de antes: o `--publicar` é da costura")
    assert "sem efeito hoje" not in publicada


def test_fora_da_acessibilidade_todo_numero_tem_gesto() -> None:
    doc = _sem_estilo(MOCKUP)
    fora = doc[:doc.index('id="acessibilidade"')]
    assert "bignum" not in fora, "um número de passo sem gesto voltou à tela"
    barras = re.findall(r'<input class="trilho"[^>]*data-gesto="([a-z-]+)"', fora)
    assert barras == ["vel-cursor", "vel-rolagem"], barras


def test_o_clique_e_a_direcao_do_r3_sao_duas_linhas_do_mesmo_desenho() -> None:
    doc = _sem_estilo(MOCKUP)
    for linha in ("r3", "r3_direcao", "l3", "l3_direcao"):
        assert f'data-gesto="linha-de-botao" data-linha="{linha}"' in doc, linha
    direcao = re.search(r'data-linha="r3_direcao".*?</select>', doc, flags=re.S)
    assert direcao and re.search(r"<option selected>Rolagem</option>", direcao.group(0)), (
        "a direção do R3 não diz «Rolagem», a palavra do desenho e do mapa do controle")


def test_o_select_do_point_and_click_traz_os_moldes_do_produto() -> None:
    doc = _sem_estilo(MOCKUP)
    seletor = re.search(r'data-gesto="point-and-click-perfil".*?</select>', doc, flags=re.S)
    assert seletor
    moldes = re.findall(r'<option value="molde:([a-z_]+)"[^>]*>([^<]+)</option>', seletor.group(0))
    assert moldes == [(x.chave, x.nome) for x in loader.MOLDES_DE_PERFIL], moldes


def _pacote() -> Any:
    import hefesto_dualsense4unix

    interface = str(pathlib.Path(hefesto_dualsense4unix.__file__).parent / "interface")
    if interface not in sys.path:
        sys.path.insert(0, interface)
    import pacotes
    import pacotes.a06_navegacao as a06

    a06._A_MAQUINA = None
    return pacotes, a06


class _Ponte:
    def __init__(self) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, **params: Any) -> dict[str, Any]:
        self.chamadas.append((metodo, dict(params)))
        return {"status": "ok"}

    def __getattr__(self, nome: str) -> Any:
        def registrar(*_a: Any, **_k: Any) -> Any:
            return True
        return registrar


@pytest.mark.parametrize("molde", loader.MOLDES_DE_PERFIL, ids=lambda x: x.chave)
def test_escolher_um_molde_grava_no_computador_e_a_tela_le_de_volta(molde: Any) -> None:
    pacotes, a06 = _pacote()
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    fn = pacotes.gesto_da_pagina("06-navegacao.html", "point-and-click-perfil")
    fn(ctx, {"valor": f"molde:{molde.chave}"}, _Ponte())
    a06._A_MAQUINA = None
    assert m.carregar_maquina().computador.global_.mouse.point_and_click == f"molde:{molde.chave}"
    assert a06.pacote(ctx)["mesa"]["point-and-click-perfil"] == f"molde:{molde.chave}"


def test_a_escolha_recusa_molde_que_nao_existe_e_valor_solto() -> None:
    pacotes, _a06 = _pacote()
    ctx = pacotes.Contexto(state={}, mesa=[], conectados=[], estados={})
    fn = pacotes.gesto_da_pagina("06-navegacao.html", "point-and-click-perfil")
    for ruim in ("molde:inexistente", "Point and click", "perfil:", ""):
        with pytest.raises(ValueError):
            fn(ctx, {"valor": ruim}, _Ponte())


def test_a_velocidade_grava_o_valor_absoluto_no_computador_e_o_disco_diz_o_mesmo() -> None:
    """Prova da D-1510-O-TECLADO-GANHA-O-SEMPRE-E-A-VELOCIDADE-E-ABSOLUTA."""
    from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc

    pacotes, _a06 = _pacote()
    vivo = {"mouse_emulation": {"enabled": True, "speed": 6, "scroll_speed": 1}}
    ctx = pacotes.Contexto(state=vivo, mesa=[], conectados=[], estados={})
    ponte = _Ponte()
    pacotes.gesto_da_pagina("06-navegacao.html", "vel-cursor")(ctx, {"valor": "9"}, ponte)
    assert opc.velocidades_do_computador()[0] == 9
    depois = {"mouse_emulation": {"enabled": True, "speed": 9, "scroll_speed": 1}}
    ctx = pacotes.Contexto(state=depois, mesa=[], conectados=[], estados={})
    pacotes.gesto_da_pagina("06-navegacao.html", "vel-rolagem")(ctx, {"valor": "3"}, ponte)
    assert opc.velocidades_do_computador() == (9, 3)
    assert ("mouse.emulation.set", {"speed": 9, "origin": "manual"}) in ponte.chamadas


def test_com_escolha_propria_no_perfil_a_velocidade_vai_para_o_perfil() -> None:
    pacotes, _a06 = _pacote()
    loader.save_profile(Profile.model_validate({
        "name": "regua", "match": {"type": "manual"},
        "mouse": {"enabled": True, "speed": 5, "scroll_speed": 2}}), origem="regua")
    ctx = pacotes.Contexto(state={"active_profile": "regua"}, mesa=[], conectados=[], estados={})
    ponte = _Ponte()
    pacotes.gesto_da_pagina("06-navegacao.html", "vel-cursor")(ctx, {"valor": "9"}, ponte)
    pacotes.gesto_da_pagina("06-navegacao.html", "vel-rolagem")(ctx, {"valor": "3"}, ponte)
    gravado = loader.load_profile("regua")
    assert gravado.mouse is not None
    assert (gravado.mouse.speed, gravado.mouse.scroll_speed) == (9, 3)


def test_com_jogo_ativo_a_escolha_vai_ao_perfil_e_a_lista_mostra_a_que_o_servico_aplica() -> None:
    pacotes, a06 = _pacote()
    loader.save_profile(Profile.model_validate({
        "name": "regua", "match": {"type": "manual"},
        "mouse": {"enabled": True, "speed": 5, "scroll_speed": 2}}), origem="regua")
    ctx = pacotes.Contexto(state={"active_profile": "regua"}, mesa=[], conectados=[], estados={})
    fn = pacotes.gesto_da_pagina("06-navegacao.html", "point-and-click-perfil")
    fn(ctx, {"valor": "molde:visual_novel"}, _Ponte())
    gravado = loader.load_profile("regua")
    assert gravado.mouse is not None and gravado.mouse.point_and_click == "molde:visual_novel"
    a06._A_MAQUINA = None
    assert a06.pacote(ctx)["mesa"]["point-and-click-perfil"] == "molde:visual_novel"
