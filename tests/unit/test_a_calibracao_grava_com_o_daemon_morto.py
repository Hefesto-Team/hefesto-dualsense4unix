"""A calibração grava com o daemon PARADO — e é a única forma honesta.

`utils/maquina.gravar_rascunho_da_mesa` nasceu em 24/08/2026 escrita para isto e
ficou com **zero chamadores**: o único escritor de produção do `maquina.json` é
o handler `machine.declare`, atrás do IPC. Com o daemon parado, tudo o que ela
declarasse ia embora sem aviso.

`integrations/lugar_declarado.py` é o chamador que faltava (CAL-2). Estes testes
provam as duas metades: o disco muda com o IPC morto, e o caminho da gravação
**não conhece IPC nenhum**.

POR QUE O SOCKET É O INSTRUMENTO
---------------------------------

O IPC desta casa é um socket unix (`cli/ipc_client.py:67`). Derrubar
`socket.socket` e `asyncio.open_unix_connection` é "o IPC recusando tudo" no
sentido literal: qualquer tentativa de falar com o daemon levanta. Se a
gravação ainda acontece, ela não passou por lá — e a régua não depende de eu
adivinhar o nome do módulo cliente certo.

O `maquina.json` deste teste é o do `tmp_path`: a fixture `_hefesto_fake_env`
(`tests/conftest.py`) isola `XDG_CONFIG_HOME` por teste, e `caminho_da_maquina`
resolve `config_dir()` na hora da chamada.
"""
from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import lugar_declarado
from hefesto_dualsense4unix.integrations.lugar_declarado import (
    MOTIVO_SCHEMA_RECUSOU,
    MOTIVO_VERSAO_ESTRANHA,
    declarar_a_mesa,
)
from hefesto_dualsense4unix.utils.maquina import caminho_da_maquina, carregar_maquina

#: A frase que a tela mostra HOJE quando o daemon está parado. Ela é o preço da
#: ausência de chamador, e é o que a mordida imprime ao reprovar. **Não é texto
#: de produto deste módulo** — a dona única do texto da aba é a
#: `CONFIGURACOES-O-LEXICO-01`; aqui ela é só a evidência do defeito.
FRASE_DO_DEFEITO = (
    "O Hefesto está desligado — não gravei o que você declarou"
)


@pytest.fixture
def ipc_morto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todo caminho de IPC recusa. Se algo tentar falar com o daemon, levanta."""

    def recusa(*_: object, **__: object) -> None:
        raise ConnectionRefusedError("o daemon está parado — este teste exige isso")

    monkeypatch.setattr(socket, "socket", recusa)
    monkeypatch.setattr(asyncio, "open_unix_connection", recusa)


def test_grava_sem_ipc(ipc_morto: None) -> None:
    """Com o IPC recusando tudo, a resposta dela chega ao disco.

    Mordida: arranquei a chamada a `gravar_rascunho_da_mesa` e devolvi
    `Recibo(False, ...)` no lugar — o jeito que o produto se comporta hoje, com
    a gravação só por `machine.declare`. O arquivo não apareceu e o teste
    reprovou imprimindo a frase que a tela mostraria.
    """
    alvo: Path = caminho_da_maquina()
    antes = alvo.read_bytes() if alvo.exists() else b""

    recibo = declarar_a_mesa({"altura_da_antena": "acima"})

    # O DISCO primeiro: é ele que a mordida derruba, e é a frase dele que
    # precisa aparecer na reprovação.
    assert alvo.exists(), (
        f"nada foi gravado com o daemon parado — a tela diria: {FRASE_DO_DEFEITO!r}"
    )
    assert alvo.read_bytes() != antes, (
        f"o `maquina.json` não mudou — a tela diria: {FRASE_DO_DEFEITO!r}"
    )
    assert carregar_maquina().mesa.altura_da_antena == "acima"
    assert recibo.gravou is True and recibo.motivo == ""


def test_cada_resposta_vai_ao_disco_e_nenhuma_apaga_a_anterior(
    ipc_morto: None,
) -> None:
    """Grava a CADA resposta (R28), e a fusão não apaga o que já estava lá.

    Matar o processo no meio da cerimônia não pode custar nada — é o que torna
    o `[Já chega por hoje]` honesto (§4.4).
    """
    alvo = caminho_da_maquina()

    assert declarar_a_mesa({"altura_da_antena": "abaixo"}).gravou
    primeiro = alvo.read_bytes()
    assert declarar_a_mesa({"linha_de_visada": "com_gente"}).gravou

    assert alvo.read_bytes() != primeiro
    mesa = carregar_maquina().mesa
    assert mesa.altura_da_antena == "abaixo"
    assert mesa.linha_de_visada == "com_gente"


def test_versao_estranha_recusa_com_motivo_e_nao_destroi_os_bytes(
    ipc_morto: None,
) -> None:
    """Arquivo de uma versão futura não é lido nem sobrescrito.

    Escolha de alguém não se destrói para registrar outra — a regra é de
    `gravar_maquina_com_descartes`, e o chamador tem de devolver o motivo em vez
    de mentir "gravei".
    """
    alvo = caminho_da_maquina()
    alvo.write_text(json.dumps({"version": 99, "mesa": {}}), encoding="utf-8")
    antes = alvo.read_bytes()

    recibo = declarar_a_mesa({"altura_da_antena": "acima"})

    assert recibo.gravou is False
    assert recibo.motivo == MOTIVO_VERSAO_ESTRANHA
    assert alvo.read_bytes() == antes


def test_declaracao_invalida_recusa_em_vez_de_levantar(ipc_morto: None) -> None:
    """Quem chama é um handler de clique: uma exceção ali leva o passo junto.

    Mordida: tirei o `except ValueError` e o teste virou `ValidationError` —
    que na janela é a cerimônia inteira caindo em cima da resposta que a pessoa
    acabou de dar.
    """
    recibo = declarar_a_mesa({"altura_da_antena": "no meio"})

    assert recibo.gravou is False
    assert recibo.motivo == MOTIVO_SCHEMA_RECUSOU


def test_o_caminho_da_gravacao_nao_conhece_ipc() -> None:
    """Portão de import: o módulo não fala com o daemon, nem por engano.

    Um `import` de conveniência acrescentado meses depois reintroduziria o
    defeito inteiro sem que teste nenhum acima reprovasse — eles todos passam
    com o socket derrubado, e um caminho novo poderia simplesmente não usá-lo.
    """
    fonte = Path(lugar_declarado.__file__).read_text(encoding="utf-8")
    linhas_de_codigo = [
        linha
        for linha in fonte.splitlines()
        if linha.startswith(("import ", "from "))
    ]

    proibidos = [
        linha
        for linha in linhas_de_codigo
        if any(marca in linha for marca in ("ipc", "socket", "asyncio", "daemon"))
    ]
    assert proibidos == [], f"o chamador voltou a depender do daemon: {proibidos}"
