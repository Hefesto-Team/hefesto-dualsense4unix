"""O receptor 2.4G na aba Conexões — O-RECEPTOR-2-4G-SE-RECONHECE-E-DIZ-QUANDO-SOFRE-01.

A cena é de mentira; o que se mede é o HTML que a aba recebe, o gesto que a página manda e o
cartão que sai. Nenhum evdev, nenhum ``maquina.json`` de verdade: a gravação da banda é injetada.

MORDIDAS, uma por vez: o botão «Descobrir» da linha sem faixa; o selo da saúde na linha; o passo
do gesto; a gravação da banda achada; o cartão «Teclado errando»; a etiqueta do painel.
"""

from __future__ import annotations

import re
import time
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real
from tests.unit import radio_de_mentira as rm  # noqa: F401  (a guarda do BlueZ da suíte)

exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import receptor_sem_fio as rx
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

ADAPTADOR = "AA:BB:CC:00:00:0A"


def _cena(vizinhos: list[dict[str, Any]]) -> dict[str, Any]:
    lug = {"id": "L1", "lugar": "L1", "nome": "Esquerda", "entrada": "Entrada 15",
           "sabido": True, "face": "", "hub": False, "varrendo": False, "junto": "",
           "usb3": False, "conectando": False, "chegou": [], "quedas": []}
    return {
        "lido": True, "lugares": [lug], "aparelhos": [], "enlaces": {}, "evitados": [],
        "canais_medidos": {"L1": True}, "vizinhos": vizinhos, "wifi": [], "portas": [],
        "pedido": None, "proposta": None, "ocupado": False, "aberto": None, "perto": [],
        "procurando": a08.PROCURAR_DESLIGADO,
    }


def _receptor(ident: str, tipo: str, *, banda: list[int] | None = None,
              saude: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"id": ident, "tipo": tipo, "nome": tipo.capitalize(), "sugestao": "",
            "sugestao_tipo": "", "no": "", "lido": "", "produto": "", "receptor": True,
            "banda": banda, "saude": saude}


def _saude(presas: int = 0, buracos: int = 0, lendo: bool = True) -> dict[str, Any]:
    return {"teclas_presas": presas, "buracos": buracos, "janela_s": 3600, "lendo": lendo}


def _linha(html: str, ident: str) -> str:
    achada = re.search(rf'<div class="ar-linha" data-id="{ident}".*?</div></div>', html, re.S)
    assert achada, ident
    return achada.group(0)


@pytest.fixture(autouse=True)
def _descoberta_limpa() -> Any:
    a08._DESCOBERTA.cancelar()
    gravados: list[Any] = []
    antes = a08._GRAVAR_A_BANDA, a08._reler_a_declaracao
    a08._GRAVAR_A_BANDA = gravados.append  # type: ignore[assignment]
    a08._reler_a_declaracao = lambda: None  # type: ignore[assignment]
    a08._gravados_da_banda = gravados  # type: ignore[attr-defined]
    yield gravados
    a08._GRAVAR_A_BANDA, a08._reler_a_declaracao = antes
    a08._DESCOBERTA.cancelar()


# --- 1. a linha: a faixa do que ainda não foi descoberto traz o gesto ---------------------------


def test_o_receptor_sem_faixa_diz_que_nao_foi_descoberto_e_traz_o_botao_descobrir() -> None:
    html = a08.html_dos_canais(_cena([_receptor("aaaa:bbbb", "mouse")]))
    linha = _linha(html, "aaaa:bbbb")
    assert "ainda não foi descoberta" in linha
    # o ponto vazado é o próprio «Descobrir» (desenho aprovado de 05/10/2026)
    assert re.search(r'<button class="ar-selo  sem" type="button" '
                     r'data-gesto="receptor-descobrir" data-alvo="aaaa:bbbb" '
                     r'title="Faixa ainda não descoberta · clique para descobrir"', linha)
    faixa = linha.split('class="ar-faixa')[1].split("ar-estado")[0]
    assert "<button" not in faixa, "o gesto não mora dentro da figura da faixa"


def test_o_receptor_com_a_faixa_medida_pinta_a_banda_e_diz_descoberto() -> None:
    html = a08.html_dos_canais(_cena([_receptor("aaaa:bbbb", "teclado", banda=[18, 35])]))
    linha = _linha(html, "aaaa:bbbb")
    assert linha.count('class="b"') >= 17 and "receptor-descobrir" not in linha


def test_o_selo_do_teclado_diz_as_teclas_presas_e_o_do_mouse_diz_sem_falhas() -> None:
    cena = _cena([_receptor("aaaa:bbbb", "teclado", banda=[18, 35], saude=_saude(presas=3)),
                  _receptor("cccc:dddd", "mouse", saude=_saude())])
    html = a08.html_dos_canais(cena)
    teclado, mouse = _linha(html, "aaaa:bbbb"), _linha(html, "cccc:dddd")
    assert '<span class="ar-selo sofrendo"' in teclado and "3 teclas presas" in teclado
    assert "em 1 h" in teclado
    assert 'class="ar-selo boa sem"' in mouse and "Sem falhas" in mouse


def test_sem_leitura_do_evdev_a_linha_nao_inventa_selo() -> None:
    cena = _cena([_receptor("aaaa:bbbb", "teclado", saude=None),
                  _receptor("cccc:dddd", "mouse", saude=_saude(lendo=False))])
    html = a08.html_dos_canais(cena)
    for ident in ("aaaa:bbbb", "cccc:dddd"):
        assert not re.search(r"ar-selo (boa|apertada|sofrendo)", _linha(html, ident)), ident


def test_o_receptor_sem_tipo_declarado_tambem_ganha_o_descobrir() -> None:
    html = a08.html_dos_canais(_cena([_receptor("aaaa:bbbb", "")]))
    assert "receptor-descobrir" in _linha(html, "aaaa:bbbb")


# --- 2. o gesto guiado --------------------------------------------------------------------------


def _clicar(chave: str = "aaaa:bbbb") -> None:
    a08.receptor_descobrir(SimpleNamespace(), {"alvo": chave}, None)  # type: ignore[arg-type]


def _na_tela(*receptores: dict[str, Any], tirado: dict[str, Any] | None = None) -> dict[str, Any]:
    cena = _cena(list(receptores))
    cena["descobrindo_ausente"] = tirado
    a08._CENA_NA_TELA.clear()
    a08._CENA_NA_TELA.update(cena)
    return cena


def test_o_gesto_anda_pelo_censo_e_a_linha_fica_na_tela_com_o_receptor_tirado() -> None:
    """O único clique é o «Descobrir»: tirar e pôr o receptor é o que anda os passos."""
    mouse = _receptor("aaaa:bbbb", "mouse")
    cena = _na_tela(mouse)
    _clicar()
    html = _linha(a08.html_dos_canais(cena), "aaaa:bbbb")
    assert "Tire o receptor da porta" in html and "Já tirei" not in html
    assert "ar-descobrir" not in html
    _clicar()  # segundo clique: não anda nada
    assert a08._DESCOBERTA.passo == rx.PASSO_TIRE
    # o receptor SAIU: a linha dele some do censo, e o gesto a mantém para dizer o passo
    a08._andar_a_descoberta({}, time.monotonic(), False)
    assert a08._DESCOBERTA.passo == rx.PASSO_MEDINDO_SEM
    fora = _cena([])
    fora["descobrindo_ausente"] = mouse
    html = _linha(a08.html_dos_canais(fora), "aaaa:bbbb")
    assert "Medindo sem ele…" in html and "ar-descobrir" not in html
    a08._andar_a_descoberta({}, a08._DESCOBERTA.desde + rx.ESPERA_DA_MEDIDA_S, False)
    assert a08._DESCOBERTA.passo == rx.PASSO_PONHA
    html = _linha(a08.html_dos_canais(fora), "aaaa:bbbb")
    assert "Ponha o receptor de volta" in html and "Já pus" not in html
    a08._andar_a_descoberta({}, a08._DESCOBERTA.desde + 1, True)
    assert a08._DESCOBERTA.passo == rx.PASSO_MEDINDO_COM


def test_a_linha_do_receptor_tirado_so_existe_enquanto_o_gesto_esta_em_curso() -> None:
    a08._DESCOBERTA.cancelar()
    assert a08._o_receptor_tirado([]) is None
    a08._VISTO_NO_GESTO["aaaa:bbbb"] = _receptor("aaaa:bbbb", "mouse")
    a08._DESCOBERTA.iniciar("aaaa:bbbb", 0.0)
    assert a08._o_receptor_tirado([])["id"] == "aaaa:bbbb"  # type: ignore[index]
    assert a08._o_receptor_tirado([_receptor("aaaa:bbbb", "mouse")]) is None


def test_a_cena_inteira_anda_o_gesto_pelo_censo_e_guarda_a_linha_do_receptor_tirado(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Do censo de mentira até a linha: o receptor sai da mesa e o gesto o segue sem clique."""
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa, RadioUsb
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig
    from hefesto_dualsense4unix.interface import pacotes

    for nome in ("_FUNDO", "_ABERTO", "_CENA_NA_TELA", "_NIVEL_NA_TELA", "_VISTO_NO_GESTO"):
        monkeypatch.setattr(a08, nome, {})
    monkeypatch.setattr(a08, "LER_NA_HORA", True)
    receptor = RadioUsb(no="3-1.4", vid="aaaa", pid="bbbb", busnum=3, devpath="1.4")
    na_mesa: dict[str, Any] = {"mesa": Mesa(radios=(receptor,))}
    monkeypatch.setattr(a08, "_mesa_do_radio", lambda recarregar=False: na_mesa["mesa"])
    monkeypatch.setattr(a08, "_ler_o_bluez", lambda: ((), ()))
    monkeypatch.setattr(a08, "_ler_a_maquina", lambda: (MaquinaConfig(), {}))
    monkeypatch.setattr(a08, "_ler_o_historico", lambda: {})
    monkeypatch.setattr(a08, "_ler_o_wifi", lambda: None)
    monkeypatch.setattr(a08, "_ler_os_zumbis", lambda: {})

    def _cena_agora() -> dict[str, Any]:
        contexto = pacotes.Contexto(state={"controllers": []}, mesa=[], conectados=[])
        return a08.cena_do_radio(contexto)

    a08._DESCOBERTA.iniciar("aaaa:bbbb", time.monotonic())
    cena = _cena_agora()
    assert a08._DESCOBERTA.passo == rx.PASSO_TIRE and cena["descobrindo_ausente"] is None
    na_mesa["mesa"] = Mesa()  # o receptor saiu da porta
    cena = _cena_agora()
    assert a08._DESCOBERTA.passo == rx.PASSO_MEDINDO_SEM, "o censo anda o passo, sem clique"
    assert cena["descobrindo_ausente"]["id"] == "aaaa:bbbb"
    assert [o.id for o, _r in a08._os_outros_radios(cena)] == ["aaaa:bbbb"], "a linha segue na tela"
    na_mesa["mesa"] = Mesa(radios=(receptor,))  # voltou antes de a medida acabar
    cena = _cena_agora()
    assert a08._DESCOBERTA.passo == rx.PASSO_TIRE and cena["descobrindo_ausente"] is None


def test_o_censo_da_porta_se_rele_so_enquanto_o_gesto_anda(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Com a leitura de VERDADE (`_mesa_do_radio`, lida uma vez e no «Examinar»): o gesto em curso
    relê a porta, e o receptor tirado faz o passo andar; sem gesto, nenhuma releitura a mais."""
    from hefesto_dualsense4unix.integrations import mesa_de_radio
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa, RadioUsb
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    for nome in ("_FUNDO", "_ABERTO", "_CENA_NA_TELA", "_NIVEL_NA_TELA", "_VISTO_NO_GESTO"):
        monkeypatch.setattr(a08, nome, {})
    monkeypatch.setattr(a08, "LER_NA_HORA", True)
    monkeypatch.setattr(a08, "RELER_A_PORTA_NO_GESTO_S", 0.0)
    monkeypatch.setattr(a08, "_MESA_DO_RADIO", None)
    receptor = RadioUsb(no="3-1.4", vid="aaaa", pid="bbbb", busnum=3, devpath="1.4")
    na_porta: dict[str, Any] = {"mesa": Mesa(radios=(receptor,)), "leituras": 0}

    def ler_a_mesa(**_k: Any) -> Any:
        na_porta["leituras"] += 1
        return na_porta["mesa"]

    monkeypatch.setattr(mesa_de_radio, "ler_a_mesa", ler_a_mesa)
    monkeypatch.setattr(a08, "_ler_o_bluez", lambda: ((), ()))
    monkeypatch.setattr(a08, "_ler_a_maquina", lambda: (MaquinaConfig(), {}))
    monkeypatch.setattr(a08, "_ler_o_historico", lambda: {})
    monkeypatch.setattr(a08, "_ler_o_wifi", lambda: None)
    monkeypatch.setattr(a08, "_ler_os_zumbis", lambda: {})

    def _cena_agora() -> dict[str, Any]:
        contexto = pacotes.Contexto(state={"controllers": []}, mesa=[], conectados=[])
        return a08.cena_do_radio(contexto)

    a08._DESCOBERTA.cancelar()
    _cena_agora()
    _cena_agora()
    assert na_porta["leituras"] == 1, "sem gesto, a porta é lida uma vez (o «Examinar» relê)"
    a08._DESCOBERTA.iniciar("aaaa:bbbb", time.monotonic())
    _cena_agora()
    assert a08._DESCOBERTA.passo == rx.PASSO_TIRE
    na_porta["mesa"] = Mesa()  # ela tirou o receptor
    _cena_agora()
    assert a08._DESCOBERTA.passo == rx.PASSO_MEDINDO_SEM, (
        "a porta lida uma vez não viu o receptor sair: o gesto ficaria no «Tire» até se desfazer")
    a08._DESCOBERTA.cancelar()


def test_so_o_receptor_que_esta_na_tela_se_descobre() -> None:
    a08._CENA_NA_TELA.clear()
    a08._CENA_NA_TELA.update(_cena([_receptor("aaaa:bbbb", "mouse")]))
    with pytest.raises(ValueError, match="não é um receptor que está na tela"):
        _clicar("ffff:0000")
    a08._CENA_NA_TELA.update(_cena([{**_receptor("aaaa:bbbb", "mouse"), "receptor": False}]))
    with pytest.raises(ValueError, match="não é um receptor"):
        _clicar("aaaa:bbbb")


def _evitados(*canais: int) -> dict[str, Any]:
    return {ADAPTADOR: {"canais_evitados": list(canais)}}


def test_a_banda_achada_e_guardada_uma_vez_com_o_dia(_descoberta_limpa: list[Any]) -> None:
    _na_tela(_receptor("aaaa:bbbb", "mouse"))
    _clicar()  # tire
    a08._andar_a_descoberta({}, 1.0, False)  # o receptor saiu: mede sem ele
    desde = a08._DESCOBERTA.desde
    sem = _evitados(*range(49, 71))
    a08._andar_a_descoberta(sem, desde + rx.ESPERA_DA_MEDIDA_S, False)
    assert a08._DESCOBERTA.passo == rx.PASSO_PONHA
    a08._andar_a_descoberta(sem, desde + rx.ESPERA_DA_MEDIDA_S + 1, True)  # voltou: mede com ele
    desde = a08._DESCOBERTA.desde
    com = _evitados(*range(49, 71), *range(18, 35))
    a08._andar_a_descoberta(com, desde + rx.ESPERA_DA_MEDIDA_S, True)
    a08._andar_a_descoberta(com, desde + rx.ESPERA_DA_MEDIDA_S + 2, True)
    assert a08._DESCOBERTA.passo == rx.PASSO_ACHOU
    assert len(_descoberta_limpa) == 1, "guarda uma vez só"
    (declaracao,) = _descoberta_limpa
    corpo = declaracao["radios"]["aaaa:bbbb"]
    assert corpo["banda"] == [18, 35] and re.fullmatch(r"\d{4}-\d{2}-\d{2}", corpo["banda_em"])


def test_nao_achar_a_faixa_nao_grava_nada_e_a_linha_oferece_de_novo(
        _descoberta_limpa: list[Any]) -> None:
    cena = _na_tela(_receptor("aaaa:bbbb", "mouse"))
    _clicar()
    a08._andar_a_descoberta({}, 1.0, False)
    a08._andar_a_descoberta(_evitados(), a08._DESCOBERTA.desde + rx.ESPERA_DA_MEDIDA_S, False)
    a08._andar_a_descoberta(_evitados(), a08._DESCOBERTA.desde + 1, True)
    a08._andar_a_descoberta(_evitados(), a08._DESCOBERTA.desde + rx.ESPERA_DA_MEDIDA_S, True)
    assert a08._DESCOBERTA.passo == rx.PASSO_NADA and _descoberta_limpa == []
    linha = _linha(a08.html_dos_canais(cena), "aaaa:bbbb")
    assert a08.FAIXA_NAO_ACHADA in linha and 'data-gesto="receptor-descobrir"' in linha


def test_a_banda_declarada_se_le_do_maquina_json() -> None:
    declaracao = SimpleNamespace(mesa=SimpleNamespace(radios={
        "aaaa:bbbb": SimpleNamespace(banda=[18, 35]), "cccc:dddd": SimpleNamespace(banda=None)}))
    assert a08._banda_declarada(declaracao, "aaaa:bbbb") == [18, 35]
    assert a08._banda_declarada(declaracao, "cccc:dddd") is None
    assert a08._banda_declarada(declaracao, "0000:1111") is None
    assert a08._banda_declarada(None, "aaaa:bbbb") is None


# --- 3. o cartão «Teclado errando» ----------------------------------------------------------------


def test_o_teclado_que_sofre_vira_o_cartao_teclado_errando_com_um_botao() -> None:
    cena = _cena([_receptor("aaaa:bbbb", "teclado", saude=_saude(presas=3))])
    (dica,) = a08._a_dica_do_receptor(cena)
    assert dica.titulo == "Teclado errando" and dica.chave == "receptor-sofrendo:teclado"
    assert "possível interferência" in dica.porque and "confirmada" not in dica.porque
    assert dica.detalhe == "3 teclas presas em 1 h"
    painel = a08._o_painel_das_dicas([], cena)
    assert [d.titulo for d in painel.visiveis] == ["Teclado errando"]


def test_uma_tecla_presa_so_aperta_e_nao_vira_cartao() -> None:
    cena = _cena([_receptor("aaaa:bbbb", "teclado", saude=_saude(presas=1)),
                  _receptor("cccc:dddd", "mouse", saude=_saude(buracos=3)),
                  _receptor("eeee:ffff", "mouse", saude=None)])
    assert a08._a_dica_do_receptor(cena) == []


def test_o_mouse_que_engasga_vira_o_cartao_mouse_engasgando() -> None:
    cena = _cena([_receptor("cccc:dddd", "mouse", saude=_saude(buracos=25))])
    (dica,) = a08._a_dica_do_receptor(cena)
    assert dica.titulo == "Mouse engasgando"


# --- 4. o painel do aparelho e o contrato da tela -------------------------------------------------


def test_o_painel_diz_receptor_24g_como_primeira_etiqueta() -> None:
    from hefesto_dualsense4unix.integrations.censo_do_barramento import Aparelho
    from hefesto_dualsense4unix.interface import arranjo_desta_maquina as adm

    receptor = Aparelho(no="/s/1-6", nome_do_kernel="1-6", vid="aaaa", pid="bbbb",
                        velocidade_mbps=12.0, especie="Mouse", receptor=True)
    comum = Aparelho(no="/s/1-7", nome_do_kernel="1-7", velocidade_mbps=12.0, especie="Mouse")
    assert adm._etiquetas_do_aparelho(receptor, None)[:2] == ["receptor 2.4G", "USB 2.0"]
    assert adm._etiquetas_do_aparelho(comum, None)[:1] == ["Mouse"]
    corpo = adm._aparelho(SimpleNamespace(tipo="Mouse", nome="x", classe="mouse"), "x",
                          do_censo=receptor)
    assert corpo["receptor"] is True


def test_o_gesto_esta_registrado_e_diz_porque_nao_tem_eco() -> None:
    from hefesto_dualsense4unix.interface.pacotes import gesto_da_pagina

    # pelo nome, e não por identidade: a suíte importa os pacotes também como `pacotes` (o
    # caminho do piloto), e o registro fica com a função da última importação.
    fn = gesto_da_pagina("08-conexoes.html", "receptor-descobrir")
    assert fn is not None and fn.__name__ == "receptor_descobrir", fn
    assert fn.__module__.rsplit(".", 1)[-1] == "a08_conexoes", fn.__module__
    assert "receptor-descobrir" in a08.RAZAO_DO_SEM_ECO


def test_o_vizinho_da_cena_so_e_receptor_quando_o_censo_diz(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.integrations.censo_do_barramento import Aparelho, Censo

    censo = Censo(aparelhos=(
        Aparelho(no="/s/1-6", nome_do_kernel="1-6", receptor=True),
        Aparelho(no="/s/1-7", nome_do_kernel="1-7")))
    monkeypatch.setattr(a08, "_censo", lambda recarregar=False: censo)
    assert a08._e_um_receptor("/s/1-6") is True
    assert a08._e_um_receptor("/s/1-7") is False
    assert a08._e_um_receptor("") is False


def test_o_mockup_traz_o_exemplo_do_desenho_do_receptor() -> None:
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[2]
    pagina = (raiz / "mockup/08-conexoes.html").read_text(encoding="utf-8")
    assert 'data-gesto="receptor-descobrir"' in pagina and "3 teclas presas" in pagina
    # o painel único do Mapa (05/10/2026) não traz mais o «Descobrir a faixa»: o ponto vazado
    # da aba Conexões é o gesto
