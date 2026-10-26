"""«Visual novel» e «Adulto» são estilos da lista, não marcas à parte — 20/10/2026.

A AS-MARCAS-VISUAL-NOVEL-E-ADULTO-SE-SOMAM-AO-ESTILO-01 (09/10) somava as duas ao estilo; o
desenho de 12/10 as pôs na lista do estilo e nenhuma marca. Com as duas formas vivas, um perfil
seria «FPS com marca Adulto» e «estilo Adulto» ao mesmo tempo, e cada leitor teria de escolher.
Hoje `Profile.marcas` não existe: o perfil de fora que ainda o traz carrega, e a marca vira o
estilo quando o perfil não tem um.

MORDIDAS: devolva o campo `marcas` ao `Profile` e a régua do esquema reprova; tire o validador
`_a_marca_de_antes_vira_o_estilo` e o carregar do perfil antigo reprova; faça o editor da aba 10
mandar `marcas` e a régua do editor reprova.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest


from hefesto_dualsense4unix.app.actions import perfis_web
from hefesto_dualsense4unix.profiles import estilos_de_jogo, loader
from hefesto_dualsense4unix.profiles.schema import Profile

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
NOME = "Maid Life"

DO_EDITOR = (
    "src/hefesto_dualsense4unix/app/actions/perfis_web.py",
    "src/hefesto_dualsense4unix/interface/aba10.py",
    "scripts/tela/perfis_vivos.py",
    "src/hefesto_dualsense4unix/interface/pacotes/a10_perfis.py",
)


def _de_fora(**extra: Any) -> dict[str, Any]:
    return {"name": NOME, "match": {"type": "any"}, **extra}


def test_o_perfil_nao_tem_o_campo_nem_o_modulo_das_marcas() -> None:
    assert "marcas" not in Profile.model_fields
    assert not (SRC / "profiles" / "marcas_do_jogo.py").exists()
    quem_importa = [
        str(arquivo.relative_to(RAIZ)) for arquivo in sorted(SRC.rglob("*.py"))
        if "marcas_do_jogo" in arquivo.read_text(encoding="utf-8")
    ]
    assert quem_importa == [], f"alguém ainda cita o módulo das marcas: {quem_importa}"


@pytest.mark.parametrize("marca", ["adulto", "visual_novel"])
def test_a_marca_de_antes_vira_o_estilo_quando_o_perfil_nao_tem_um(marca: str) -> None:
    """A prova da D-2010-A-MARCA-DE-ANTES-VIRA-O-ESTILO."""
    perfil = Profile.model_validate(_de_fora(marcas=[marca]))
    assert perfil.estilo == marca
    assert estilos_de_jogo.POR_CHAVE[marca].rotulo
    assert "marcas" not in perfil.model_dump()


def test_o_estilo_escrito_vence_e_a_marca_cai() -> None:
    perfil = Profile.model_validate(_de_fora(estilo="fps", marcas=["adulto"]))
    assert perfil.estilo == "fps"
    assert "marcas" not in perfil.model_dump()


def test_a_marca_que_saiu_do_produto_nao_recusa_o_perfil() -> None:
    assert Profile.model_validate(_de_fora(marcas=["que_saiu"])).estilo is None
    assert Profile.model_validate(_de_fora(marcas=[["lista"], 3])).estilo is None
    assert Profile.model_validate(_de_fora(marcas="adulto")).estilo is None
    assert Profile.model_validate(_de_fora(marcas=None)).estilo is None


def test_o_arquivo_antigo_carrega_com_o_estilo_e_regrava_sem_a_marca() -> None:
    loader.save_profile(Profile.model_validate(_de_fora()), origem="régua")
    caminho = loader.arquivo_do_perfil(NOME)
    cru = json.loads(caminho.read_text(encoding="utf-8"))
    caminho.write_text(json.dumps({**cru, "marcas": ["visual_novel"]}), encoding="utf-8")

    lido = loader.load_profile(NOME)
    assert lido.estilo == "visual_novel"

    loader.save_profile(lido, origem="régua")
    regravado = json.loads(caminho.read_text(encoding="utf-8"))
    assert regravado["estilo"] == "visual_novel"
    assert "marcas" not in regravado


def _nomes_e_textos(fonte: str) -> set[str]:
    achados: set[str] = set()
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Name | ast.Attribute | ast.keyword | ast.arg):
            achados.add(getattr(no, "id", None) or getattr(no, "attr", None)
                        or getattr(no, "arg", None) or "")
        elif isinstance(no, ast.Constant) and isinstance(no.value, str):
            achados.add(no.value)
    return achados


def test_o_editor_da_aba_10_nao_manda_marcas_em_nenhum_gesto() -> None:
    for relativo in DO_EDITOR:
        usos = [x for x in _nomes_e_textos((RAIZ / relativo).read_text(encoding="utf-8"))
                if x in {"marcas", "marcas_do_jogo", "molde_dos_botoes"}]
        assert usos == [], f"{relativo} voltou a falar de marcas: {usos}"


def test_o_editor_mostra_o_estilo_novo_pelo_rotulo_da_lista() -> None:
    for chave, rotulo in (("visual_novel", "Visual novel"), ("adulto", "Adulto")):
        perfil = Profile.model_validate(_de_fora(estilo=chave))
        editor = perfis_web.pacote_da_aba([perfil], editado=perfil)["editor"]
        assert editor["estilo"] == rotulo
        assert "marcas" not in editor, "o editor voltou a mandar as marcas"
