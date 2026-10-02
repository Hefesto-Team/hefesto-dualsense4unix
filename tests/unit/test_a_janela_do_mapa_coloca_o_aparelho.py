"""A janela do mapa põe o aparelho na entrada, e o desenho espera o "Aplicar"."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

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
    """A janela sobre a bancada de mentira, sem `show`."""
    return JanelaDoMapaDaMesa(
        host, mapa_dela() if mapa is None else mapa, bancada_de_agora().censo()
    )


def test_colocar_e_tirar_deixa_o_rascunho_no_estado_anterior() -> None:
    """Escolhe o aparelho, clica na entrada, e o rascunho recebe o caminho."""
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

    assert janela.logica.caminho_em("9") == "", (
        "o mesmo aparelho ficou em duas entradas ao mesmo tempo"
    )


def test_tirar_daqui_apaga_a_entrada_no_disco() -> None:
    """"Tirar daqui" escreve ``None``, e o ``None`` apaga o arquivo."""
    host = _Hospedeiro()
    janela = _janela(host)
    assert gravar_maquina({"mapa": mapa_dela().model_dump(mode="json")}) is True
    assert carregar_maquina().mapa.portas["9"].caminho == "3-1.2"

    janela.quadrados["9"].clicked()
    janela.botao_tirar.clicked()

    declaracao = host._maquina_pendente
    assert isinstance(declaracao, dict)

    assert gravar_maquina(declaracao) is True

    documento = json.loads(caminho_da_maquina().read_text(encoding="utf-8"))
    assert "9" not in documento["mapa"]["portas"], (
        "a entrada esvaziada continuou no ARQUIVO depois do Aplicar: "
        f"{documento['mapa']['portas']}. É o que acontece quando o gesto de "
        "tirar apaga a chave do rascunho em vez de escrever None: a chave "
        "ausente manda a gravação preservar o que estava no disco"
    )
    assert documento["mapa"]["portas"]["13"]["nos"] == ["3-1.1-port1"], (
        "tirar UMA entrada levou as outras junto"
    )
    assert declaracao["mapa"]["portas"]["9"]["caminho"] is None


def test_desenhar_sem_aplicar_nao_toca_o_disco(tmp_path: Path) -> None:
    """O desenho vive no rascunho até ela clicar em "Aplicar"."""
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


def test_tem_uma_extensao_aqui_cria_a_entrada_filha() -> None:
    """A entrada 12 ganha uma 12a, e a 12a **não** entra na fileira da face."""
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


def test_a_janela_de_quem_nunca_desenhou_nasce_sem_face_nenhuma() -> None:
    """Zero faces é estado legítimo, e o produto não inventa "Frente"."""
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
    """Os números são do metal: dois buracos não podem ter o mesmo."""
    logica = LogicaDoMapa(MapaDaMesa())
    logica.acrescentar_face("Esquerda")
    logica.acrescentar_face("Direita")

    assert logica.acrescentar_entrada(0) == "1"
    assert logica.acrescentar_entrada(0) == "2"
    assert logica.acrescentar_entrada(1) == "3", (
        "a segunda face repetiu um número que a primeira já usava"
    )


def test_o_rascunho_do_mapa_passa_no_esquema() -> None:
    """O que a janela escreve tem de ser aceito pelo ``maquina.json``."""
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
    """O mapa substitui o mapa e NÃO encosta em mesa, controles nem orçamento."""
    host = _Hospedeiro()
    host._maquina_pendente = {"mesa": {"altura_da_antena": "acima"}}

    acumular_no_rascunho(host, LogicaDoMapa(mapa_dela()))

    assert host._maquina_pendente["mesa"] == {"altura_da_antena": "acima"}, (
        "o desenho do mapa apagou o que outra seção tinha declarado: "
        f"{host._maquina_pendente}"
    )
    assert host._maquina_pendente["mapa"]["portas"]["9"]["caminho"] == "3-1.2"
