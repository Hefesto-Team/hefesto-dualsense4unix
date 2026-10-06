"""O controle que pede para parear aparece, mesmo já conhecido.

O-CONTROLE-QUE-PEDE-PARA-PAREAR-APARECE-MESMO-JA-CONHECIDO-01 (05/10/2026). Ela segurou PS + Create
no «vermelho» com a janela aberta, e a aba 08 disse «0 controles». No BlueZ ele estava no ar na
Esquerda (RSSI de -56 a -62) com ``Paired`` verdadeiro e ``Connected`` falso: o controle perdeu a
chave, o BlueZ guarda a dele, e a lista «no ar» só trazia aparelho novo ou conectado.

A cura: a central publica o pedido (conhecido + desconectado + ouvido na varredura); a aba mostra
o cartão «Roxo quer conectar» com «Parear» e o ponto que pulsa no grupo do adaptador que o ouve;
com a janela aberta por ela, a central refaz o par sozinha no adaptador da janela.

TUDO É DE MENTIRA: o BlueZ é o ``radio_de_mentira`` (com o dono vivo de verdade por cima) ou
objetos montados à mão; nunca o BlueZ dela. Endereços na faixa forjada ``aa:bb:cc``.

AS MORDIDAS (feitas na sprint, uma de cada vez, com a cura devolvida e o md5 conferido): tirar o
``RSSI`` do critério (``ouvidos`` passa a ser todo objeto) reprova «sem sinal, nada»; tirar o
``_quem_pede_aqui`` da espera da escolha reprova a janela que pareia sozinha; tirar o
``_refazer_o_par_no_destino`` reprova a janela na mesma entrada do par velho; o ``Paired`` da
colheita no lugar do de agora (``_ainda_pareado`` em ``gesto_de_pareamento``) também; tirar o
grupo sem linha do Rádio reprova o ponto que pulsa.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import dicas_da_conexao as dicas
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from tests.unit import radio_de_mentira as rm
from tests.unit import test_o_parear_espera_o_clique as _base
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VARANDA, VERDE, VERMELHO

#: as fixtures do dublê da escolha dela (o dono vivo e a central reais sobre o mundo de mentira)
diario, relogio, mesa = _base.diario, _base.relogio, _base.mesa

ADAPTADORES = {SALA: "/org/bluez/hci7", QUARTO: "/org/bluez/hci8", VARANDA: "/org/bluez/hci9"}
QUATRO = (VERMELHO, AZUL, VERDE, ROXO)
CLASSES = {"dualsense": 0x002508, "xbox": 0x000508, "8bitdo": 0x000504}


def _adaptadores() -> tuple[bd.AdaptadorDoBluez, ...]:
    return tuple(bd.AdaptadorDoBluez(caminho=c, hci=c.rsplit("/", 1)[1], endereco=e)
                 for e, c in ADAPTADORES.items())


def _objeto(adaptador: str, aparelho: str, *, pareado: bool = False, conectado: bool = False,
            rssi: int | None = None, classe: int | None = CLASSES["dualsense"],
            icone: str = "", nome: str = "") -> bd.AparelhoDoBluez:
    caminho = ADAPTADORES[adaptador]
    return bd.AparelhoDoBluez(
        caminho=f"{caminho}/dev_{aparelho.upper().replace(':', '_')}", adaptador=caminho,
        endereco=aparelho, nome=nome, conectado=conectado, pareado=pareado,
        rssi=rssi, classe=classe, icone=icone)


# ───────────────────────── o sinal, na central ─────────────────────────


@pytest.mark.parametrize("controle", QUATRO)
@pytest.mark.parametrize(("velho", "ouve"), [(SALA, QUARTO), (QUARTO, QUARTO), (VARANDA, SALA)])
def test_conhecido_desconectado_e_ouvido_e_um_pedido(controle: str, velho: str, ouve: str) -> None:
    """De P1 a P4, em qualquer adaptador: o par velho num, o sinal noutro (ou no mesmo)."""
    objetos = [_objeto(velho, controle, pareado=True, nome="vermelho")]
    if ouve == velho:
        objetos = [_objeto(velho, controle, pareado=True, rssi=-58, nome="vermelho")]
    else:
        objetos.append(_objeto(ouve, controle, rssi=-58))
    (pedido,) = cr.pedidos_de_pareamento(_adaptadores(), objetos)
    assert (pedido.aparelho, pedido.adaptador, pedido.par_velho) == (controle, ouve, (velho,))
    assert pedido.rssi == -58 and pedido.nome == "vermelho"
    assert pedido.publicar()["ouvido_por"] == [ouve]


@pytest.mark.parametrize(("classe", "icone"), [
    (CLASSES["dualsense"], ""), (CLASSES["xbox"], ""), (CLASSES["8bitdo"], ""),
    (None, "input-gaming")], ids=["dualsense", "xbox", "8bitdo", "so-o-icone"])
def test_xbox_e_8bitdo_pedem_do_mesmo_jeito(classe: int | None, icone: str) -> None:
    objetos = [_objeto(SALA, VERMELHO, pareado=True, classe=classe, icone=icone),
               _objeto(QUARTO, VERMELHO, rssi=-60, classe=classe, icone=icone)]
    assert [p.aparelho for p in cr.pedidos_de_pareamento(_adaptadores(), objetos)] == [VERMELHO]


def test_sem_sinal_nada_aparece() -> None:
    """O controle desligado é conhecido e desconectado, mas a varredura não o ouve.

    MORDIDA: tire o ``RSSI`` do critério e este reprova."""
    objetos = [_objeto(SALA, VERMELHO, pareado=True), _objeto(QUARTO, VERMELHO)]
    assert cr.pedidos_de_pareamento(_adaptadores(), objetos) == ()


@pytest.mark.parametrize("caso", ["conectado", "novo", "celular", "movendo"])
def test_o_que_nao_e_pedido(caso: str) -> None:
    """Conectado em algum lugar; nunca pareado (é da lista do «Conectar»); não é controle; ou
    a central já o está movendo."""
    objetos = {
        "conectado": [_objeto(SALA, VERMELHO, pareado=True, conectado=True),
                      _objeto(QUARTO, VERMELHO, rssi=-50)],
        "novo": [_objeto(QUARTO, VERMELHO, rssi=-50)],
        "celular": [_objeto(SALA, VERMELHO, pareado=True, classe=0x5A020C),
                    _objeto(QUARTO, VERMELHO, rssi=-50, classe=0x5A020C)],
        "movendo": [_objeto(SALA, VERMELHO, pareado=True), _objeto(QUARTO, VERMELHO, rssi=-50)],
    }[caso]
    fora = [VERMELHO] if caso == "movendo" else []
    assert cr.pedidos_de_pareamento(_adaptadores(), objetos, fora=fora) == ()


def _o_vermelho_sem_a_chave(*, ouvido_em: str) -> rm.RadioDeMentira:
    """O vermelho com par velho na sala, que ELE esqueceu (``host=False``), e o azul no ar."""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, AZUL)
    mundo.pareado(SALA, VERMELHO, conectado=False, host=False, nome="vermelho")
    if ouvido_em != SALA:
        mundo.mesa[rm.HCIS[ouvido_em]][bd.ADAPTADOR]["Discovering"] = True
        mundo.segurar_ps_create(VERMELHO)
    _ouvir(mundo, ouvido_em, VERMELHO)
    return mundo


def _ouvir(mundo: rm.RadioDeMentira, adaptador: str, aparelho: str, rssi: int = -58) -> None:
    """A varredura ouve ``aparelho`` em ``adaptador``: o BlueZ põe o ``RSSI`` no objeto dele."""
    mundo._mudar(rm.no_de(adaptador, aparelho), bd.APARELHO, "RSSI", rssi)


def test_a_central_publica_o_pedido_pelo_dono_vivo(mesa: Any) -> None:
    mundo = _o_vermelho_sem_a_chave(ouvido_em=QUARTO)
    _dono, central = mesa(mundo)
    (pedido,) = central.publicar()["pedindo"]
    assert (pedido["aparelho"], pedido["adaptador"], pedido["par_velho"]) == (
        VERMELHO, QUARTO, [SALA])
    assert pedido["nome"] == "vermelho"


@pytest.mark.parametrize("destino", [QUARTO, SALA], ids=["outra-entrada", "a-do-par-velho"])
def test_com_a_janela_aberta_a_central_refaz_o_par_sozinha(
        mesa: Any, relogio: rm.Relogio, destino: str) -> None:
    """Ela abriu o «Conectar» e segurou PS + Create: sem outro clique, o par velho sai e o novo
    entra no adaptador da janela. Na mesma entrada do par velho, o objeto velho sai antes do
    ``Pair`` (sem isso o BlueZ responde «já existe» sobre a chave que o controle perdeu)."""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, AZUL)
    mundo.pareado(SALA, VERMELHO, conectado=False, host=False, nome="vermelho")
    _dono, central = mesa(mundo)

    def ela_segura() -> None:
        mundo.segurar_ps_create(VERMELHO)
        if mundo.objeto(destino, VERMELHO) is not None:
            _ouvir(mundo, destino, VERMELHO)

    relogio.agendar(2.0, ela_segura)
    # o controle segue anunciando: o BlueZ volta a achá-lo quando o objeto velho sai
    relogio.durante = lambda: (mundo.segurar_ps_create(VERMELHO)
                               if mundo.fisicos[VERMELHO].pareando else None)

    feito = central.conectar(destino)

    assert (feito.estado, feito.aparelho, feito.destino) == (cr.CHEGOU, VERMELHO, destino)
    assert [c for c, _a in mundo.metodos("Pair")] == [rm.no_de(destino, VERMELHO)]
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == destino
    if destino != SALA:
        velho = mundo.objeto(SALA, VERMELHO)
        assert velho is None or velho.get("Paired") is False, "o par velho ficou na sala"


def test_com_a_janela_aberta_o_conhecido_desligado_nao_e_escolhido(
        mesa: Any, relogio: rm.Relogio) -> None:
    """Sem o sinal (ela não segurou PS + Create), a janela acaba sem gesto e sem ``Pair``."""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, AZUL)
    mundo.pareado(SALA, VERMELHO, conectado=False, host=False)
    _dono, central = mesa(mundo)

    feito = central.conectar(QUARTO)

    assert mundo.metodos("Pair") == []
    assert (feito.estado, feito.motivo) == (cr.NAO_CHEGOU, cr.MOTIVO_SEM_GESTO)


# ───────────────────────── a tela ─────────────────────────


def _cena(nomes: tuple[str, ...] = ("Roxo",)) -> dict[str, Any]:
    lugares = [{"id": "AABBCC0000A1", "nome": "Esquerda", "entrada": "Entrada 4"},
               {"id": "AABBCC0000B2", "nome": "Meio", "entrada": ""}]
    return {"lugares": lugares, "aparelhos": [], "evitados": [], "canais_medidos": {},
            "vizinhos": [], "wifi": [], "portas": [],
            "pedindo": [{"aparelho": f"AABBCC00000{i + 1}", "lugar": lugares[i % 2]["id"],
                         "nome": nome} for i, nome in enumerate(nomes)]}


@pytest.mark.parametrize("nomes", [("Roxo",), ("Roxo", "Azul", "Verde", "Vermelho")],
                         ids=["um", "os-quatro"])
def test_o_cartao_vem_primeiro_com_o_ponto_que_pulsa_e_o_parear(nomes: tuple[str, ...]) -> None:
    cena = _cena(nomes)
    html = a08._html_das_dicas([], cena)
    cartoes = re.findall(r'<section class="cartao-dica.*?</section>', html, re.S)
    assert len(cartoes) == min(len(nomes), dicas.CARTOES_VISIVEIS)
    primeiro = cartoes[0]
    assert 'class="cd-pulso"' in primeiro and "Roxo quer conectar" in primeiro
    assert "Perto da Entrada 4" in primeiro
    assert 'class="cd-info"' not in primeiro and "cd-porque" not in primeiro, (
        "o cartão do pedido ganhou o ⓘ: o desenho aprovado é título, onde e «Parear»")
    botao = re.search(r'<button class="btn cd-botao"[^>]*>Parear</button>', primeiro)
    assert botao, primeiro
    assert 'data-gesto="parear-o-pedido"' in botao.group(0)
    assert 'data-alvo="AABBCC000001"' in botao.group(0)
    assert 'data-destino="AABBCC0000A1"' in botao.group(0)
    if len(nomes) > 1:
        assert "Perto do adaptador Meio" in cartoes[1]


def test_o_grupo_do_adaptador_que_ouve_aparece_com_o_ponto_mesmo_sem_linha() -> None:
    """MORDIDA: devolva o ``continue`` do grupo sem linha e este reprova."""
    html = a08.html_dos_canais(_cena())
    grupo = re.search(r'<div class="ar-grupo[^"]*" data-grupo="AABBCC0000A1">.*?</div>', html)
    assert grupo, html
    assert 'class="ar-pulso"' in grupo.group(0)
    assert f'title="{a08.PEDINDO_PARA_PAREAR}"' in grupo.group(0)
    assert 'data-grupo="AABBCC0000B2"' not in html, "o adaptador sem pedido e sem linha apareceu"


def test_a_tela_le_o_pedido_da_central_com_o_nome_dela() -> None:
    lugares = [{"id": "AABBCC0000A1"}]
    central = {"pedindo": [
        {"aparelho": "AA:BB:CC:00:00:01", "adaptador": "AA:BB:CC:00:00:A1", "nome": "roxo"},
        {"aparelho": "AA:BB:CC:00:00:02", "adaptador": "AA:BB:CC:00:00:A1",
         "nome": "DualSense Wireless Controller"},
        {"aparelho": "AA:BB:CC:00:00:03", "adaptador": "AA:BB:CC:00:00:FF", "nome": "Azul"}]}
    pedindo = a08._quem_pede_para_parear(central, lugares, ())
    assert pedindo == [
        {"aparelho": "AABBCC000001", "lugar": "AABBCC0000A1", "nome": "Roxo"},
        {"aparelho": "AABBCC000002", "lugar": "AABBCC0000A1", "nome": a08.CONTROLE_SEM_NOME}]


class _Ponte:
    def __init__(self) -> None:
        self.pedidos: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, **parametros: Any) -> dict[str, Any]:
        self.pedidos.append((metodo, parametros))
        return {"status": "ok"}


def test_o_parear_do_cartao_e_o_mover_da_central(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a08, "_CENA_NA_TELA", {**_cena(), "ocupado": False})
    monkeypatch.setattr(a08, "_ABERTO", {})
    ponte = _Ponte()
    feito = a08.parear_o_pedido(None, {"alvo": "AABBCC000001", "destino": "AABBCC0000A1"}, ponte)
    assert feito == {"armou": True}
    assert ponte.pedidos == [("radio.mover", {"destino": "AABBCC0000A1",
                                              "aparelho": "aa:bb:cc:00:00:01"})]
    with pytest.raises(ValueError):
        a08.parear_o_pedido(None, {"alvo": "AABBCC000009", "destino": "AABBCC0000A1"}, ponte)
