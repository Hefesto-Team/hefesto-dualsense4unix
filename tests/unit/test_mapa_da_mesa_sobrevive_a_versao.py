"""O mapa entra no ``maquina.json`` sem quebrar quem já declarou.

CONEXÕES · MAPA 2D 01, tarefa ``MAPA-1`` (25/08/2026). O gabinete dela vira um
campo novo do documento — e a ``version`` **não sobe**.

POR QUE NÃO SUBIR A VERSÃO É A MIGRAÇÃO INTEIRA
------------------------------------------------

``gravar_maquina_com_descartes`` recusa gravar quando a ``version`` em disco não
é a nossa, e ``carregar_maquina`` devolve documento VAZIO no mesmo caso. Trocar
``MAQUINA_SCHEMA_VERSION`` para ``2`` faria, na máquina de quem já declarou:

* toda leitura devolver "não sei" em mesa, controles e orçamento;
* toda gravação devolver ``gravou=False``, e o rodapé dizer "não gravei" para
  sempre.

Campo novo sem bump é a migração, e ela funciona nos dois sentidos — arquivo
antigo lido por código novo, e arquivo NOVO lido por código antigo. Os dois
sentidos são teste aqui.

A BANCADA
----------

Nenhum aparelho, nenhum MAC, nenhum serial. O ``config_dir`` é o isolado por
``_hefesto_fake_env``, e a fixture ``arquivo`` prova a cada teste que ele está
sob o ``tmp_path`` — sem essa prova, um defeito de caminho escreveria no
``~/.config`` dela.
"""
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

#: O gabinete dela, como ele vai ao disco. Três faces, quinze entradas na
#: fileira, e a ``15a`` que nasce de uma extensão plugada na ``15``.
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


# --- 1. O campo novo existe, e o disco o guarda -----------------------------


def test_o_mapa_vai_ao_disco_e_volta_igual(arquivo: Path) -> None:
    """Ida e volta do gabinete inteiro, face por face e entrada por entrada.

    Mordida: tirar ``mapa`` de ``MaquinaConfig``. ``_so_o_que_o_schema_conhece``
    deixa de reconhecer o campo, ``carregar_maquina().mapa`` some, e o teste
    reprova com ``AttributeError`` antes de chegar à comparação.
    """
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
        "caminho": "3-1.1.4",
        "filha_de": "15",
    }


def test_quem_nunca_desenhou_nao_carrega_mapa_nenhum_no_arquivo(
    arquivo: Path,
) -> None:
    """Silêncio não se escreve por extenso — nem como ``{"faces": []}``.

    Mordida: tirar a lista vazia de ``_podar``. O documento de quem só declarou
    a altura da antena passa a carregar um ``"mapa": {"faces": []}``, e o teste
    reprova nomeando a chave que sobrou.
    """
    assert gravar_maquina({"mesa": {"altura_da_antena": "acima"}}) is True

    documento = _documento(arquivo)

    assert "mapa" not in documento, (
        "quem nunca desenhou a mesa passou a carregar um mapa vazio em disco: "
        f"{documento.get('mapa')!r}"
    )
    assert carregar_maquina().mapa.faces == [], "o mapa ausente deixou de nascer vazio"


# --- 2. Arquivo NOVO lido por código ANTIGO ---------------------------------


def test_o_codigo_antigo_preserva_o_mapa(
    arquivo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uma versão que não conhece ``mapa`` lê, grava, e NÃO destrói o mapa.

    O binário antigo é simulado do jeito mais fiel que existe: tirando ``mapa``
    de ``MaquinaConfig.model_fields``, que é o dicionário de onde as DUAS
    guardas do módulo leem — a que tira o campo da validação
    (``_so_o_que_o_schema_conhece``) e a que copia verbatim de volta para o
    disco (``gravar_maquina_com_descartes``).

    Mordida: trocar o ``if campo not in MaquinaConfig.model_fields`` daquela
    cópia verbatim por um ``{}``. O mapa some do arquivo na primeira gravação
    do binário antigo, e o teste reprova dizendo qual chave sumiu.
    """
    assert gravar_maquina({"mapa": MAPA_DELA}) is True
    antes = _documento(arquivo)["mapa"]

    campos_sem_mapa = {
        nome: campo
        for nome, campo in MaquinaConfig.model_fields.items()
        if nome != "mapa"
    }
    monkeypatch.setattr(MaquinaConfig, "model_fields", campos_sem_mapa)

    # O binário antigo declara o que ELE conhece, sem saber que o mapa existe.
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


# --- 3. Arquivo ANTIGO lido por código NOVO ---------------------------------


def test_documento_da_v1_continua_sendo_lido(arquivo: Path) -> None:
    """A mordida do "não subir a versão", e ela é a tarefa inteira.

    Mordida exercida em 25/08/2026: troquei ``MAQUINA_SCHEMA_VERSION`` para
    ``2`` e ``MaquinaConfig.version`` para ``Literal[2] = 2``. Este teste
    reprovou nomeando ``mesa.altura_da_antena`` como o campo perdido — que é
    exatamente o que aconteceria na máquina de quem já declarou.
    """
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
    """O estrago para no campo ruim — mesa, controles e orçamento sobrevivem.

    Mordida: trocar o resgate campo-a-campo de ``carregar_maquina`` por um
    ``return MaquinaConfig()``. A altura da antena some junto com o mapa torto,
    e o teste reprova.
    """
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


# --- 4. As três regras de validação -----------------------------------------


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
    """Chave de dicionário sem validador herda lixo — a lição do ``radios``.

    Mordida: tirar o validador ``_caminho_e_o_nome_do_kernel``. Os seis casos
    entram no esquema, e o mapa passa a poder guardar um caminho que nunca vai
    casar com aparelho nenhum — um desenho que não aponta para lugar nenhum.
    """
    with pytest.raises(ValidationError):
        MaquinaConfig.model_validate(
            {"version": 1, "mapa": {"portas": {"1": {"caminho": caminho}}}}
        )


@pytest.mark.parametrize("numero", ["", "1234", "15ab", "15A", "9 ", "a"])
def test_numero_de_entrada_torto_nao_entra(numero: str) -> None:
    """Até três dígitos e uma letra. Sem teto, um arquivo torto vira mil quadrados.

    Mordida: tirar o validador de chave de ``MapaDaMesa.portas``. Os seis casos
    passam, e a janela desenha uma grade do tamanho do que estiver no arquivo.
    """
    with pytest.raises(ValidationError):
        MaquinaConfig.model_validate(
            {"version": 1, "mapa": {"portas": {numero: {"caminho": "1-3"}}}}
        )


def test_o_teto_de_faces_e_de_entradas_vale() -> None:
    """Oito faces e 64 entradas — e o teto é do desenho, não do gosto.

    Mordida: tirar os dois tetos. Um arquivo com 200 faces é aceito, e a janela
    do mapa nasce com 200 fileiras de quadrados.
    """
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
    # E o gabinete dela, que é o caso real mais cheio desta casa, passa.
    assert MaquinaConfig.model_validate({"version": 1, "mapa": MAPA_DELA})


def test_o_esquema_nao_aceita_campo_que_ninguem_conhece() -> None:
    """``extra="forbid"`` também no mapa — chave desconhecida é recusada.

    Mordida: tirar o ``model_config`` de ``PortaDeclarada``. Um ``"painel":
    "frente"`` gravado à mão por engano passa a entrar em silêncio, e vira um
    segundo dono do fato que a face já guarda.
    """
    with pytest.raises(ValidationError):
        MaquinaConfig.model_validate(
            {
                "version": 1,
                "mapa": {"portas": {"1": {"caminho": "1-3", "painel": "frente"}}},
            }
        )


def test_o_modulo_nao_resolve_o_config_dir_no_topo(tmp_path: Path) -> None:
    """Canário do caminho: o import LAZY de ``config_dir`` continua lazy.

    É a mesma cicatriz de ``app/gui_prefs.py:21``. Se algum dia o módulo
    resolver o diretório no topo, esta bateria inteira passa a escrever no
    ``~/.config`` dela e nenhum outro teste percebe.
    """
    assert tmp_path in modulo.caminho_da_maquina().parents
