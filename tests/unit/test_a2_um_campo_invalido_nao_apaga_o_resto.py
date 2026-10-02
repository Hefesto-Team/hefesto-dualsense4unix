"""A2 — um campo que o schema recusa não pode apagar as outras declarações."""
from __future__ import annotations

import json
import types
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin

import pytest

from hefesto_dualsense4unix.utils.maquina import (
    MAQUINA_SCHEMA_VERSION,
    ControleDeclarado,
    MaquinaConfig,
    MesaDeclarada,
    OrcamentoDeclarado,
    RadioDeclarado,
    caminho_da_maquina,
    carregar_maquina,
    gravar_maquina,
    gravar_maquina_com_descartes,
)

CHAVE_DE_HARDWARE = "aabbcc00beef"

DOCUMENTO_COM_UM_CAMPO_RUIM: dict[str, Any] = {
    "version": 1,
    "mesa": {
        "altura_da_antena": "acima",
        "linha_de_visada": "com_gente",
        "radios": {"046d:c52b": {"tipo": "mouse", "apelido": "Unifying da TV"}},
    },
    "controles": {CHAVE_DE_HARDWARE: {"microfone": True, "cor": "Roxo"}},
    "orcamento": {"teto": "plasma"},
}


@pytest.fixture
def arquivo(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta bancada — e a prova de que ele não é o dela."""
    caminho = caminho_da_maquina()
    assert tmp_path in caminho.parents, f"{caminho} escapou do tmp da bancada"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return caminho


def _documento(arquivo: Path) -> dict[str, Any]:
    return dict(json.loads(arquivo.read_text(encoding="utf-8")))


def test_um_campo_invalido_nao_apaga_mesa_e_controles(
    arquivo: Path,
) -> None:
    """A MORDIDA: o `orcamento` ruim sai sozinho; o resto sobrevive ao "Aplicar"."""
    arquivo.write_text(
        json.dumps(DOCUMENTO_COM_UM_CAMPO_RUIM, ensure_ascii=False), encoding="utf-8"
    )

    assert gravar_maquina({"mesa": {"altura_da_antena": "abaixo"}})

    depois = _documento(arquivo)
    assert depois["mesa"]["altura_da_antena"] == "abaixo"
    assert depois["mesa"]["linha_de_visada"] == "com_gente"
    assert depois["mesa"]["radios"]["046d:c52b"]["tipo"] == "mouse"
    assert depois["controles"][CHAVE_DE_HARDWARE]["microfone"] is True
    assert depois["controles"][CHAVE_DE_HARDWARE]["cor"] == "Roxo"
    assert "orcamento" not in depois

    cfg = carregar_maquina()
    assert cfg.controles[CHAVE_DE_HARDWARE].microfone is True
    assert cfg.orcamento.teto is None


def test_o_estrago_para_na_subarvore_ruim(arquivo: Path) -> None:
    """Chave de controle SINTETIZADA derruba `controles`, não a mesa."""
    arquivo.write_text(
        json.dumps(
            {
                "version": 1,
                "mesa": {"altura_da_antena": "acima"},
                "controles": {"02fe000000d1": {"cor": "Branco"}},
            }
        ),
        encoding="utf-8",
    )

    resultado = gravar_maquina_com_descartes({"orcamento": {"teto": "max"}})

    assert resultado.gravou
    assert resultado.descartados == ("controles",)
    depois = _documento(arquivo)
    assert depois["mesa"]["altura_da_antena"] == "acima"
    assert depois["orcamento"]["teto"] == "max"
    assert "controles" not in depois


def test_os_bytes_recusados_ficam_no_arquivo_invalido(arquivo: Path) -> None:
    """O que não volta ao documento vira `maquina.json.invalido`, verbatim."""
    bytes_de_antes = json.dumps(DOCUMENTO_COM_UM_CAMPO_RUIM, ensure_ascii=False)
    arquivo.write_text(bytes_de_antes, encoding="utf-8")

    assert gravar_maquina({"mesa": {"altura_da_antena": "abaixo"}})

    copia = arquivo.parent / (arquivo.name + ".invalido")
    assert copia.exists()
    assert copia.read_text(encoding="utf-8") == bytes_de_antes


def test_o_caminho_feliz_nao_ganhou_arquivo_nem_descarte(arquivo: Path) -> None:
    """Documento são: nada é descartado e nenhuma cópia é escrita."""
    assert gravar_maquina({"mesa": {"altura_da_antena": "acima"}})
    resultado = gravar_maquina_com_descartes({"orcamento": {"teto": "balanceado"}})

    assert resultado == (True, ())
    assert not (arquivo.parent / (arquivo.name + ".invalido")).exists()
    assert _documento(arquivo)["mesa"]["altura_da_antena"] == "acima"


def test_versao_desconhecida_continua_intocada(arquivo: Path) -> None:
    """O resgate não pode abrir a porta que a checagem de versão fecha."""
    bytes_de_antes = '{"version": 99, "mesa": {"altura_da_antena": "voando"}}'
    arquivo.write_text(bytes_de_antes, encoding="utf-8")

    resultado = gravar_maquina_com_descartes({"orcamento": {"teto": "auto"}})

    assert resultado == (False, ())
    assert arquivo.read_text(encoding="utf-8") == bytes_de_antes
    assert not (arquivo.parent / (arquivo.name + ".invalido")).exists()


_MODELOS = (
    MaquinaConfig,
    MesaDeclarada,
    ControleDeclarado,
    OrcamentoDeclarado,
    RadioDeclarado,
)

CATALOGO_V1: dict[str, tuple[str, ...]] = {
    "MaquinaConfig.version": ("1",),
    "MesaDeclarada.altura_da_antena": ("acima", "abaixo"),
    "MesaDeclarada.linha_de_visada": ("livre", "com_gente"),
    "ControleDeclarado.modo": ("xinput", "dinput", "switch"),
    "ControleDeclarado.botoes": ("xbox", "nintendo"),
    "OrcamentoDeclarado.teto": ("economia", "balanceado", "max", "auto"),
    "RadioDeclarado.tipo": (
        "wifi",
        "teclado",
        "mouse",
        "webcam",
        "caixa_de_som",
        "outro",
    ),
}


def _valores_de_literal(anotacao: Any) -> tuple[str, ...]:
    """Os valores do `Literal`, atravessando o `| None` que todo campo tem."""
    origem = get_origin(anotacao)
    if origem is Literal:
        return tuple(str(valor) for valor in get_args(anotacao))
    if origem in (Union, types.UnionType):
        return tuple(
            valor for arg in get_args(anotacao) for valor in _valores_de_literal(arg)
        )
    return ()


def test_o_catalogo_dos_literais_nao_muda_sem_bump_de_versao() -> None:
    """Alargar um `Literal` na v1 é o que produz o documento que A2 cura."""
    vivo = {
        f"{modelo.__name__}.{nome}": valores
        for modelo in _MODELOS
        for nome, campo in modelo.model_fields.items()
        if (valores := _valores_de_literal(campo.annotation))
    }

    assert MAQUINA_SCHEMA_VERSION == 1, (
        "a versão do schema mudou: refaça o CATALOGO_V1 com o catálogo da nova"
    )
    assert vivo == CATALOGO_V1, (
        "o catálogo de valores mudou sem bump de MAQUINA_SCHEMA_VERSION — "
        "um arquivo escrito pela versão nova perde o campo ao ser lido por esta"
    )
