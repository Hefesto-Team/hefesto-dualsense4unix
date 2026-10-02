"""O mapa entra no ``maquina.json`` sem quebrar quem já declarou."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.utils import maquina as modulo
from hefesto_dualsense4unix.utils.maquina import (
    MAQUINA_SCHEMA_VERSION,
    MaquinaConfig,
    caminho_da_maquina,
    carregar_maquina,
    gravar_maquina,
)

MAPA_DELA: dict[str, Any] = {
    "faces": [
        {"nome": "Frente", "portas": ["1", "2"]},
        {"nome": "Traseira", "portas": ["3", "4", "5", "6", "7", "8"]},
        {"nome": "Hub", "portas": ["9", "10", "11", "12", "13", "14", "15"]},
    ],
    "portas": {
        "1": {"caminho": "1-3"},
        "2": {"caminho": "1-6"},
        "4": {"caminho": "3-1"},
        "9": {"caminho": "3-1.2"},
        "13": {"caminho": "3-1.1.1"},
        "15a": {"caminho": "3-1.1.4", "filha_de": "15"},
    },
}


@pytest.fixture
def arquivo(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta bancada — e a prova de que ele não é o dela."""
    caminho = caminho_da_maquina()
    assert tmp_path in caminho.parents, f"{caminho} escapou do tmp da bancada"
    return caminho


def _documento(arquivo: Path) -> dict[str, Any]:
    return dict(json.loads(arquivo.read_text(encoding="utf-8")))


def test_o_mapa_vai_ao_disco_e_volta_igual(arquivo: Path) -> None:
    """Ida e volta do gabinete inteiro, face por face e entrada por entrada."""
    assert gravar_maquina({"mapa": MAPA_DELA}) is True

    lido = carregar_maquina().mapa

    assert [face.nome for face in lido.faces] == ["Frente", "Traseira", "Hub"]
    assert lido.faces[2].portas == ["9", "10", "11", "12", "13", "14", "15"]
    assert lido.portas["15a"].caminho == "3-1.1.4"
    assert lido.portas["15a"].filha_de == "15", (
        "a entrada por extensão perdeu de quem ela é filha; sem isso o produto "
        "volta a dizer que o dongle está na porta do hub, que é onde ele NÃO "
        "está — o defeito que a extensão inteira existe para curar"
    )
    assert _documento(arquivo)["mapa"]["portas"]["15a"] == {
        "filha_de": "15",
        "nos": ["3-1.1-port4"],
    }


def test_quem_nunca_desenhou_nao_carrega_mapa_nenhum_no_arquivo(
    arquivo: Path,
) -> None:
    """Silêncio não se escreve por extenso — nem como ``{"faces": []}``."""
    assert gravar_maquina({"mesa": {"altura_da_antena": "acima"}}) is True

    documento = _documento(arquivo)

    assert "mapa" not in documento, (
        "quem nunca desenhou a mesa passou a carregar um mapa vazio em disco: "
        f"{documento.get('mapa')!r}"
    )
    assert carregar_maquina().mapa.faces == [], "o mapa ausente deixou de nascer vazio"


def test_o_codigo_antigo_preserva_o_mapa(
    arquivo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uma versão que não conhece ``mapa`` lê, grava, e NÃO destrói o mapa."""
    assert gravar_maquina({"mapa": MAPA_DELA}) is True
    antes = _documento(arquivo)["mapa"]

    campos_sem_mapa = {
        nome: campo
        for nome, campo in MaquinaConfig.model_fields.items()
        if nome != "mapa"
    }
    monkeypatch.setattr(MaquinaConfig, "model_fields", campos_sem_mapa)

    assert gravar_maquina({"mesa": {"linha_de_visada": "livre"}}) is True

    documento = _documento(arquivo)
    assert "mapa" in documento, (
        "a versão que não conhece o campo APAGOU o desenho dela na primeira "
        "gravação; um upgrade e um downgrade custariam o gabinete inteiro"
    )
    assert documento["mapa"] == antes, (
        f"o mapa voltou diferente do disco: {documento['mapa']!r} != {antes!r}"
    )
    assert documento["mesa"]["linha_de_visada"] == "livre"


def test_documento_da_v1_continua_sendo_lido(arquivo: Path) -> None:
    """A mordida do "não subir a versão", e ela é a tarefa inteira."""
    arquivo.write_text(
        json.dumps(
            {
                "version": 1,
                "mesa": {"altura_da_antena": "acima", "linha_de_visada": "livre"},
            }
        ),
        encoding="utf-8",
    )

    lido = carregar_maquina()

    assert lido.mesa.altura_da_antena == "acima", (
        "o documento da v1 deixou de ser lido: mesa.altura_da_antena voltou "
        f"como {lido.mesa.altura_da_antena!r}, e não como a pessoa declarou. "
        "É o que acontece na máquina de quem já declarou quando a versão sobe"
    )
    assert MAQUINA_SCHEMA_VERSION == 1, (
        "a versão do esquema subiu. Todo documento já gravado por aí passa a "
        "ser ilegível, e a gravação passa a dizer 'não gravei' para sempre — "
        "campo novo SEM bump é a migração"
    )
    assert lido.mapa.faces == [], "o mapa ausente devia nascer vazio, não sumir"


def test_mapa_corrompido_nao_leva_a_mesa_junto(arquivo: Path) -> None:
    """O estrago para no campo ruim — mesa, controles e orçamento sobrevivem."""
    arquivo.write_text(
        json.dumps(
            {
                "version": 1,
                "mesa": {"altura_da_antena": "abaixo"},
                "mapa": {"portas": {"15a": {"caminho": "um caminho torto"}}},
            }
        ),
        encoding="utf-8",
    )

    lido = carregar_maquina()

    assert lido.mesa.altura_da_antena == "abaixo", (
        "um mapa torto levou junto a declaração da mesa; o resgate campo-a-"
        "campo deixou de valer para o campo novo"
    )
    assert lido.mapa.portas == {}, "o mapa torto entrou mesmo assim"


_QUINZE: dict[str, Any] = {
    "faces": [
        {"nome": "Frente", "portas": ["1", "2"], "perto": True, "alto": False},
        {"nome": "Traseira", "portas": ["3", "4", "5", "6", "7", "8"],
         "perto": False, "alto": False},
        {"nome": "Hub", "portas": [str(n) for n in range(9, 16)],
         "perto": False, "alto": True},
    ],
    "portas": {str(n): {"caminho": f"9-{n}"} for n in range(1, 16)},
}


def _com_o_campo(numero: str, **campos: Any) -> dict[str, Any]:
    documento = json.loads(json.dumps({"version": 1, "mapa": _QUINZE}))
    documento["mapa"]["portas"][numero].update(campos)
    documento["mesa"] = {"altura_da_antena": "acima"}
    return documento


def test_o_campo_desconhecido_numa_entrada_nao_leva_o_mapa_junto(arquivo: Path) -> None:
    arquivo.write_text(json.dumps(_com_o_campo("3", campo_do_futuro=1)), encoding="utf-8")

    lido = carregar_maquina()

    assert len(lido.mapa.portas) == 15, (
        f"o campo novo da entrada 3 levou o mapa junto: {sorted(lido.mapa.portas)}")
    assert [f.nome for f in lido.mapa.faces] == ["Frente", "Traseira", "Hub"]
    assert lido.mapa.portas["3"].caminho == "9-3", "a entrada 3 perdeu o que era dela"
    assert lido.mesa.altura_da_antena == "acima"


def test_o_nome_comprido_demais_perde_so_o_nome(arquivo: Path) -> None:
    arquivo.write_text(json.dumps(_com_o_campo("3", nome="x" * 200)), encoding="utf-8")

    lido = carregar_maquina()

    assert len(lido.mapa.portas) == 15, sorted(lido.mapa.portas)
    assert lido.mapa.portas["3"].caminho == "9-3"
    assert getattr(lido.mapa.portas["3"], "nome", None) is None


def test_a_gravacao_de_um_campo_novo_nao_apaga_o_mapa_do_disco(arquivo: Path) -> None:
    """O código de hoje grava por cima de um documento com o campo de amanhã:"""
    arquivo.write_text(json.dumps(_com_o_campo("3", campo_do_futuro=1)), encoding="utf-8")

    resultado = modulo.gravar_maquina_com_descartes({"mesa": {"linha_de_visada": "livre"}})

    assert resultado.gravou
    documento = _documento(arquivo)
    assert len(documento["mapa"]["portas"]) == 15, sorted(documento["mapa"]["portas"])
    assert "campo_do_futuro" not in documento["mapa"]["portas"]["3"]
    assert (arquivo.parent / (arquivo.name + ".invalido")).exists()


@pytest.mark.parametrize(
    "caminho",
    [
        "um caminho torto",
        "3-1-1-4",
        "3.1.1.4",
        "-1",
        "3-",
        "/sys/bus/usb/devices/3-1.1.4",
    ],
)
def test_caminho_que_nao_e_do_kernel_nao_entra(caminho: str) -> None:
    """Chave de dicionário sem validador herda lixo — a lição do ``radios``."""
    with pytest.raises(ValidationError):
        MaquinaConfig.model_validate(
            {"version": 1, "mapa": {"portas": {"1": {"caminho": caminho}}}}
        )


@pytest.mark.parametrize("numero", ["", "1234", "15ab", "15A", "9 ", "a"])
def test_numero_de_entrada_torto_nao_entra(numero: str) -> None:
    """Até três dígitos e uma letra. Sem teto, um arquivo torto vira mil quadrados."""
    with pytest.raises(ValidationError):
        MaquinaConfig.model_validate(
            {"version": 1, "mapa": {"portas": {numero: {"caminho": "1-3"}}}}
        )


def test_o_teto_de_faces_e_de_entradas_vale() -> None:
    """Oito faces e 64 entradas — e o teto é do desenho, não do gosto."""
    with pytest.raises(ValidationError):
        MaquinaConfig.model_validate(
            {
                "version": 1,
                "mapa": {"faces": [{"nome": f"F{n}"} for n in range(9)]},
            }
        )
    with pytest.raises(ValidationError):
        MaquinaConfig.model_validate(
            {
                "version": 1,
                "mapa": {
                    "faces": [
                        {"nome": "Muitas", "portas": [str(n) for n in range(65)]}
                    ]
                },
            }
        )
    assert MaquinaConfig.model_validate({"version": 1, "mapa": MAPA_DELA})


def test_o_esquema_nao_aceita_campo_que_ninguem_conhece() -> None:
    """``extra="forbid"`` também no mapa — chave desconhecida é recusada."""
    with pytest.raises(ValidationError):
        MaquinaConfig.model_validate(
            {
                "version": 1,
                "mapa": {"portas": {"1": {"caminho": "1-3", "painel": "frente"}}},
            }
        )


def test_o_modulo_nao_resolve_o_config_dir_no_topo(tmp_path: Path) -> None:
    """Canário do caminho: o import LAZY de ``config_dir`` continua lazy.

    É a mesma cicatriz de ``app/gui_prefs.py:13``. Se algum dia o módulo
    resolver o diretório no topo, esta bateria inteira passa a escrever no
    ``~/.config`` dela e nenhum outro teste percebe.
    """
    assert tmp_path in modulo.caminho_da_maquina().parents
