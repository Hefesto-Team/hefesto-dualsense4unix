"""A janela do mapa põe o aparelho na entrada, e o desenho espera o "Aplicar".

CONEXÕES · MAPA 2D 01, tarefa ``MAPA-4`` (25/08/2026).

O GESTO É CLIQUE-EM-CLIQUE, E ISSO FOI DECIDIDO
------------------------------------------------

Decisão de quem coordena a leva, pelo que a sprint mediu: dois sinais contra
quatro, ``Gtk.Grid`` em dez arquivos desta casa contra ZERO precedente de
arrastar, teclado de graça contra inutilizável sem mouse, e — o que pesa mais —
um arrasto pela metade **não é um estado**, então a prova de tela dele não
existe. A palavra "arrastado" é dela, e ela reverte numa frase.

ONDE A REGRA DA CASA VENCEU O TEXTO DA SPRINT
-----------------------------------------------

A sprint pedia que "Tirar daqui" fizesse a chave **sumir** do rascunho. Isso
está errado, e o próprio ``utils/maquina.py`` diz por quê: *"``None`` presente
na declaração é uma escolha ('voltei para Não sei') e SOBRESCREVE. Só a
AUSÊNCIA da chave preserva o que havia."* Uma chave que some do rascunho é
exatamente o que manda a gravação **preservar** o que está no disco — e o
aparelho tirado voltaria no "Aplicar" seguinte.

Então tirar é escrever ``caminho: None``, e o teste cobra o que importa: depois
do "Aplicar", a entrada **não está no arquivo**. É a mesma exigência, medida no
lugar onde ela tem consequência.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: antes de qualquer import de `gi`.
exigir_gi_real("a janela do mapa 2D")

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.app.widgets.mapa_da_mesa import (
    JanelaDoMapaDaMesa,
    LogicaDoMapa,
    acumular_no_rascunho,
)
from hefesto_dualsense4unix.utils.maquina import (
    MapaDaMesa,
    caminho_da_maquina,
    carregar_maquina,
    gravar_maquina,
)
from tests.unit.test_mapa_a_bancada_de_mentira import bancada_de_agora, mapa_dela


class _Hospedeiro:
    """O mínimo que a janela toca no hospedeiro — o rascunho e a marca."""

    def __init__(self) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self.marcou = 0

    def _marcar_declaracao_por_aplicar(self) -> None:
        self.marcou += 1


def _janela(host: Any, mapa: MapaDaMesa | None = None) -> JanelaDoMapaDaMesa:
    """A janela sobre a bancada de mentira, sem `show`.

    Ela NÃO é mostrada: sob Xvfb não há gerenciador de janelas e uma
    `Gtk.Window` mostrada fica 1x1 para sempre (`COMO-OLHAR-A-TELA.md`). O que
    este teste exercita é o gesto, e sinal de botão não precisa de tela.
    """
    return JanelaDoMapaDaMesa(
        host, mapa_dela() if mapa is None else mapa, bancada_de_agora().censo()
    )


# --- 1. O gesto de dois tempos ----------------------------------------------


def test_colocar_e_tirar_deixa_o_rascunho_no_estado_anterior() -> None:
    """Escolhe o aparelho, clica na entrada, e o rascunho recebe o caminho.

    Mordida exercida em 25/08/2026: troquei o corpo de ``LogicaDoMapa.colocar``
    por um ``return False``. O rascunho ficou sem a entrada 10, e o teste
    reprovou dizendo que o clique não chegou a lugar nenhum.
    """
    host = _Hospedeiro()
    janela = _janela(host)

    # O DualSense por cabo, que na mesa dela está na entrada 9.
    janela.aparelhos["3-1.2"].clicked()
    assert janela.logica.escolhido == "3-1.2", "o primeiro tempo não escolheu nada"

    janela.quadrados["10"].clicked()

    pendente = host._maquina_pendente
    assert isinstance(pendente, dict)
    assert pendente["mapa"]["portas"]["10"]["caminho"] == "3-1.2", (
        f"o aparelho não chegou à entrada 10: {pendente['mapa']['portas']}"
    )
    assert janela.logica.escolhido == "", (
        "o aparelho continuou escolhido depois de colocado; o clique seguinte "
        "em outra entrada o moveria sem ela pedir"
    )
    assert host.marcou >= 1, (
        "o rodapé não foi avisado de que há escolha por aplicar; quem desenhar "
        "e clicar direto no X fecha a janela sem nunca ver o aviso"
    )

    # E ele sai de onde estava: um aparelho está em UM lugar.
    assert janela.logica.caminho_em("9") == "", (
        "o mesmo aparelho ficou em duas entradas ao mesmo tempo"
    )


def test_tirar_daqui_apaga_a_entrada_no_disco() -> None:
    """"Tirar daqui" escreve ``None``, e o ``None`` apaga o arquivo.

    Este é o teste que a sprint queria, medido onde ele tem consequência: não
    basta a chave sumir do rascunho — ela tem de sumir do ARQUIVO depois do
    "Aplicar". Chave ausente no rascunho faria o disco PRESERVAR o aparelho.

    Mordida exercida em 25/08/2026: troquei o ``_esvaziar`` por um
    ``del self.portas[numero]``, que é a versão "a chave some". O rascunho
    ficou bonito e o arquivo continuou com ``"9": {"caminho": "3-1.2"}`` depois
    do "Aplicar" — o aparelho ressuscitou, e o teste reprovou.
    """
    host = _Hospedeiro()
    janela = _janela(host)
    assert gravar_maquina({"mapa": mapa_dela().model_dump(mode="json")}) is True
    assert carregar_maquina().mapa.portas["9"].caminho == "3-1.2"

    janela.quadrados["9"].clicked()  # foca a entrada, sem aparelho escolhido
    janela.botao_tirar.clicked()

    declaracao = host._maquina_pendente
    assert isinstance(declaracao, dict)

    # O gesto do rodapé, sem o rodapé: a mesma gravação que ele faz.
    assert gravar_maquina(declaracao) is True

    documento = json.loads(caminho_da_maquina().read_text(encoding="utf-8"))
    assert "9" not in documento["mapa"]["portas"], (
        "a entrada esvaziada continuou no ARQUIVO depois do Aplicar: "
        f"{documento['mapa']['portas']}. É o que acontece quando o gesto de "
        "tirar apaga a chave do rascunho em vez de escrever None: a chave "
        "ausente manda a gravação preservar o que estava no disco"
    )
    assert documento["mapa"]["portas"]["13"]["caminho"] == "3-1.1.1", (
        "tirar UMA entrada levou as outras junto"
    )
    # E a forma que faz isso funcionar — o `None` explícito, não a ausência.
    assert declaracao["mapa"]["portas"]["9"]["caminho"] is None


def test_desenhar_sem_aplicar_nao_toca_o_disco(tmp_path: Path) -> None:
    """O desenho vive no rascunho até ela clicar em "Aplicar".

    Mordida: fazer ``acumular_no_rascunho`` chamar ``gravar_maquina``. O
    arquivo nasce sem ninguém ter aplicado nada, e o teste reprova — a janela
    passaria a ser a única coisa da aba que grava sozinha, e o "desfazer" que o
    rascunho dá de graça sumiria.
    """
    caminho = caminho_da_maquina()
    assert tmp_path in caminho.parents, f"{caminho} escapou do tmp da bancada"
    assert not caminho.exists()

    host = _Hospedeiro()
    janela = _janela(host)
    janela.aparelhos["4-4"].clicked()
    janela.quadrados["12"].clicked()

    assert not caminho.exists(), (
        "a janela do mapa gravou em disco sem ninguém ter clicado em Aplicar"
    )
    assert host._maquina_pendente is not None, "e nem no rascunho ela escreveu"


# --- 2. A extensão, que só existe porque ela disse ---------------------------


def test_tem_uma_extensao_aqui_cria_a_entrada_filha() -> None:
    """A entrada 12 ganha uma 12a, e a 12a **não** entra na fileira da face.

    Pôr a filha na fileira faria a fileira de sete do hub virar oito, e o
    desenho deixaria de bater com o metal.

    Mordida: acrescentar a filha à lista da face. A fileira cresce, e o teste
    reprova comparando a lista da face com a de antes.
    """
    host = _Hospedeiro()
    janela = _janela(host)
    fileira_antes = list(janela.logica.faces[2]["portas"])

    janela.quadrados["12"].clicked()
    janela.botao_extensao.clicked()

    assert janela.logica.filhas_de("12") == ["12a"]
    assert janela.logica.faces[2]["portas"] == fileira_antes, (
        "a entrada por extensão entrou na fileira da face: "
        f"{janela.logica.faces[2]['portas']}"
    )
    pendente = host._maquina_pendente
    assert isinstance(pendente, dict)
    assert pendente["mapa"]["portas"]["12a"]["filha_de"] == "12"
    assert "12a" in janela.quadrados, "a entrada nova não apareceu no desenho"


def test_a_segunda_extensao_da_mesma_entrada_ganha_outra_letra() -> None:
    """Duas extensões na mesma entrada são ``12a`` e ``12b``, nunca a mesma."""
    logica = LogicaDoMapa(mapa_dela())

    assert logica.acrescentar_extensao("12") == "12a"
    assert logica.acrescentar_extensao("12") == "12b"
    assert sorted(logica.filhas_de("12")) == ["12a", "12b"]


# --- 3. Faces: nenhuma nasce sozinha -----------------------------------------


def test_a_janela_de_quem_nunca_desenhou_nasce_sem_face_nenhuma() -> None:
    """Zero faces é estado legítimo, e o produto não inventa "Frente".

    É a regra do notebook: face inventada é a presunção que a
    ``ONDA0-Z7 · O AMBIENTE PRESUMIDO`` existe para caçar.

    Mordida: fazer ``LogicaDoMapa`` nascer com "Frente" e "Traseira" quando o
    mapa vem vazio. O teste reprova, e é ele que impede o produto de desenhar
    um gabinete que a pessoa não tem.
    """
    host = _Hospedeiro()
    janela = _janela(host, MapaDaMesa())

    assert janela.logica.faces == [], (
        f"a janela inventou faces para quem nunca desenhou: {janela.logica.faces}"
    )
    assert janela.quadrados == {}, "e inventou entradas também"
    assert host._maquina_pendente is None, (
        "abrir a janela sujou o rascunho sem ela ter clicado em nada; o rodapé "
        "passaria a ter o que Aplicar por ninguém ter feito nada"
    )


def test_acrescentar_face_pede_um_nome() -> None:
    """Face sem nome não nasce — um quadrado sem rótulo não se acha no metal."""
    logica = LogicaDoMapa(MapaDaMesa())

    assert logica.acrescentar_face("   ") is False
    assert logica.faces == []
    assert logica.acrescentar_face("Esquerda") is True
    assert logica.acrescentar_face("Direita") is True
    assert [face["nome"] for face in logica.faces] == ["Esquerda", "Direita"]


def test_a_entrada_nova_nunca_repete_um_numero_do_gabinete() -> None:
    """Os números são do metal: dois buracos não podem ter o mesmo.

    Mordida: numerar por face (``len(face["portas"]) + 1``). A segunda face
    passa a começar em 1, e o gabinete ganha duas entradas 1 — o mapa deixa de
    poder responder "onde está" com uma resposta só.
    """
    logica = LogicaDoMapa(MapaDaMesa())
    logica.acrescentar_face("Esquerda")
    logica.acrescentar_face("Direita")

    assert logica.acrescentar_entrada(0) == "1"
    assert logica.acrescentar_entrada(0) == "2"
    assert logica.acrescentar_entrada(1) == "3", (
        "a segunda face repetiu um número que a primeira já usava"
    )


def test_o_rascunho_do_mapa_passa_no_esquema() -> None:
    """O que a janela escreve tem de ser aceito pelo ``maquina.json``.

    Sem esta ponte o desenho dela morre no "Aplicar", com "não consegui
    gravar" — e o defeito só apareceria na mão dela.
    """
    host = _Hospedeiro()
    janela = _janela(host)
    janela.aparelhos["4-4"].clicked()
    janela.quadrados["12"].clicked()
    janela.quadrados["12"].clicked()
    janela.botao_extensao.clicked()

    pendente = host._maquina_pendente
    assert isinstance(pendente, dict)
    validado = MapaDaMesa.model_validate(pendente["mapa"])

    assert validado.portas["12"].caminho == "4-4"
    assert validado.portas["12a"].filha_de == "12"


def test_acumular_preserva_o_que_as_outras_secoes_declararam() -> None:
    """O mapa substitui o mapa e NÃO encosta em mesa, controles nem orçamento.

    Mordida: trocar o ``documento["mapa"] = ...`` por
    ``host._maquina_pendente = {"mapa": ...}``. A altura da antena que ela
    tinha acabado de declarar noutra seção some do rascunho, e o "Aplicar"
    grava só metade do que ela escolheu.
    """
    host = _Hospedeiro()
    host._maquina_pendente = {"mesa": {"altura_da_antena": "acima"}}

    acumular_no_rascunho(host, LogicaDoMapa(mapa_dela()))

    assert host._maquina_pendente["mesa"] == {"altura_da_antena": "acima"}, (
        "o desenho do mapa apagou o que outra seção tinha declarado: "
        f"{host._maquina_pendente}"
    )
    assert host._maquina_pendente["mapa"]["portas"]["9"]["caminho"] == "3-1.2"
