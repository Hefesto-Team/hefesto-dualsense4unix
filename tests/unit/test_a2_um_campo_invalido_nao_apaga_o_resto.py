"""A2 — um campo que o schema recusa não pode apagar as outras declarações.

O defeito medido em 23/08/2026: ao pegar `ValidationError` lendo o disco,
`gravar_maquina` partia de um documento VAZIO, e a gravação seguinte reescrevia o
arquivo só com o que a pessoa acabara de declarar. Mesa, controles, orçamento e a
ponte de microfone sumiam em silêncio — e a tela respondia "gravado".

O caminho realista até o estado ruim não é editar o JSON à mão: basta um release
futuro alargar um `Literal` mantendo `version: 1` e alguém voltar de versão. Por
isso o último teste é um PORTÃO sobre o catálogo dos Literais — seis campos podem
disparar o defeito, e nenhum deles muda sem bump de `MAQUINA_SCHEMA_VERSION`.

Bancada: nenhum aparelho, nenhum MAC real (faixa forjada `aa:bb:cc:*`). O
`config_dir` é o isolado por `_hefesto_fake_env` (`tests/conftest.py`), e a
fixture `arquivo` prova a cada teste que ele está sob o `tmp_path`.
"""
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

#: Um rosto da faixa forjada, na forma em que a chave vai ao disco.
CHAVE_DE_HARDWARE = "aabbcc00beef"

#: O documento cheio que ela declarou ao longo de cinco sessões, com UM valor que
#: o schema recusa no meio — o `orcamento.teto` que uma versão futura
#: conheceria (T2, CONFIGURAÇÕES-FECHA-01: era `ambiente`, que saiu do
#: esquema por não ter escritor nem leitor).
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
    """A MORDIDA: o `orcamento` ruim sai sozinho; o resto sobrevive ao "Aplicar".

    MORDE: trocando `atual, descartados = _o_que_ainda_vale(bruto)` por
    `atual = MaquinaConfig()` em `gravar_maquina_com_descartes` — o arquivo
    depois da gravação fica com `mesa.altura_da_antena` e mais nada, e a
    asserção da `linha_de_visada` reprova.
    """
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
    """Chave de controle SINTETIZADA derruba `controles`, não a mesa.

    O `02` é o endereço que o `usb_probe_degrade` forja; ele nunca deveria estar
    em disco, e quando está é o campo `controles` inteiro que cai — mas só ele.

    MORDE: com `atual = MaquinaConfig()` no lugar do resgate, `mesa` some junto e
    a asserção da `altura_da_antena` reprova.
    """
    arquivo.write_text(
        json.dumps(
            {
                "version": 1,
                "mesa": {"altura_da_antena": "acima"},
                # Este MAC é INVÁLIDO de propósito: o primeiro octeto `02` tem
                # o bit "locally administered", e o validador da casa recusa
                # endereço sintetizado — é ele que faz esta subárvore ser
                # descartada enquanto as outras sobrevivem.
                #
                # ARMADILHA REGISTRADA (23/08/2026): o valor aqui era uma
                # sequência simples de dígitos, e o gancho de pré-commit
                # BLOQUEOU o commit — por coincidência ela continha, como
                # substring, um literal da lista de segredos desta máquina.
                # Nenhum segredo foi escrito; foi acaso, e o gancho fez
                # exatamente o trabalho dele.
                #
                # E houve uma SEGUNDA mordida, que é a parte que ensina: o
                # primeiro comentário escrito para explicar o caso CITAVA o
                # valor antigo, e o gancho bloqueou de novo — a citação
                # reintroduziu a coincidência. Por isso este texto descreve
                # sem reproduzir.
                #
                # A lição vale para todo dado de teste: **sequência casa com
                # qualquer coisa por acidente.** Prefira dígitos sem padrão.
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
    """O que não volta ao documento vira `maquina.json.invalido`, verbatim.

    MORDE: tirando a chamada de `_guardar_os_bytes_recusados` — o arquivo não
    nasce e a primeira asserção reprova, com o valor recusado irrecuperável.
    """
    bytes_de_antes = json.dumps(DOCUMENTO_COM_UM_CAMPO_RUIM, ensure_ascii=False)
    arquivo.write_text(bytes_de_antes, encoding="utf-8")

    assert gravar_maquina({"mesa": {"altura_da_antena": "abaixo"}})

    copia = arquivo.parent / (arquivo.name + ".invalido")
    assert copia.exists()
    assert copia.read_text(encoding="utf-8") == bytes_de_antes


def test_o_caminho_feliz_nao_ganhou_arquivo_nem_descarte(arquivo: Path) -> None:
    """Documento são: nada é descartado e nenhuma cópia é escrita.

    A hipótese tem de explicar o que já funcionava — um resgate que se ativasse
    sempre encheria `config_dir()` de cópias a cada clique dela.
    """
    assert gravar_maquina({"mesa": {"altura_da_antena": "acima"}})
    resultado = gravar_maquina_com_descartes({"orcamento": {"teto": "balanceado"}})

    assert resultado == (True, ())
    assert not (arquivo.parent / (arquivo.name + ".invalido")).exists()
    assert _documento(arquivo)["mesa"]["altura_da_antena"] == "acima"


def test_versao_desconhecida_continua_intocada(arquivo: Path) -> None:
    """O resgate não pode abrir a porta que a checagem de versão fecha.

    MORDE: movendo o resgate para ANTES do `return` da versão desconhecida — os
    bytes mudam e a última asserção reprova.
    """
    bytes_de_antes = '{"version": 99, "mesa": {"altura_da_antena": "voando"}}'
    arquivo.write_text(bytes_de_antes, encoding="utf-8")

    resultado = gravar_maquina_com_descartes({"orcamento": {"teto": "auto"}})

    assert resultado == (False, ())
    assert arquivo.read_text(encoding="utf-8") == bytes_de_antes
    assert not (arquivo.parent / (arquivo.name + ".invalido")).exists()


# ---------------------------------------------------------------------------
# O portão: alargar um Literal sem bump de versão é o caminho realista até o
# estado ruim, e é ele que este teste fecha.
# ---------------------------------------------------------------------------

_MODELOS = (
    MaquinaConfig,
    MesaDeclarada,
    ControleDeclarado,
    OrcamentoDeclarado,
    RadioDeclarado,
)

#: O catálogo COMPLETO dos `Literal` do módulo na v1. Seis campos além de
#: `version` — cada um deles é um valor que, alargado numa versão futura sem bump
#: e lido de volta por esta, derrubaria o campo inteiro.
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
    """Alargar um `Literal` na v1 é o que produz o documento que A2 cura.

    Um release futuro que aceite `orcamento.teto: "generosa"` mantendo
    `version: 1` escreve um arquivo que ESTA versão recusa — e quem voltar de
    versão perde o campo. O preço de aceitar isso é um número:
    `MAQUINA_SCHEMA_VERSION`.

    MORDE: acrescentando `"generosa"` ao `Literal` de `OrcamentoDeclarado.teto`
    — reprova mostrando o campo e os dois catálogos.
    """
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
