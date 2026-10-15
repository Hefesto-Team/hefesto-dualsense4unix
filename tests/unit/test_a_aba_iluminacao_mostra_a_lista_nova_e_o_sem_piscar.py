"""A aba Iluminação mostra a lista nova e o «Sem piscar»
(A-ABA-ILUMINACAO-MOSTRA-A-LISTA-NOVA-E-O-SEM-PISCAR-01, 15/10/2026).

A linha «Efeito» tem oito opções, em grupos pelo que se vê (o desenho A, com uma lista suspensa em
cada controle), e uma frase de uma linha sob a lista diz o que a escolhida faz. O interruptor «Sem
piscar» é UM valor da declaração da máquina (`maquina.json`, `luz.sem_piscar`), o mesmo para os
quatro controles e as duas conexões: nenhum perfil ganha campo.

O lar é de mentira (o `conftest` desvia `HOME` e os `XDG_*`): o gesto grava o `maquina.json` de
verdade, dentro dele.

MORDIDAS (feitas à mão, 15/10/2026): tirar `sem_piscar` de `LuzDeclarada` reprova a gravação;
tirar o grupo «Que se move» ou o token `base:` da lista reprova a ordem; fazer o gesto da base
gravar uma cor fixa reprova a cor do controle. Trocar a cor sem levar o efeito junto
(`efeito=None` em `_guardar_a_cor_no_perfil`) reprova os quatro controles; dar cor ao arco-íris
reprova o que não leva cor.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

MOCKUP = RAIZ / "mockup" / "04-iluminacao.html"
JOGADORES = [f"aa:bb:cc:00:00:0{n}" for n in range(1, 5)]

#: O que a lista mostra, na ordem do desenho A: do mais calmo ao mais vivo, agrupado pelo que se vê.
ROTULOS_NA_ORDEM = ["Sem efeito", "Luz fixa", "Respirar", "Batida do coração", "Chama", "Maré",
                    "Piscar", "Arco-íris"]
VALORES_NA_ORDEM = ["sem-efeito", "luz-fixa", "base:respirar", "base:batimento", "base:chama",
                    "base:mare", "base:piscar", "base:arco-iris"]
GRUPOS_NA_ORDEM = ["Parado", "Que respira", "Que se move"]


def _ctx(n: int = 1) -> Any:
    import pacotes
    from hefesto_dualsense4unix.core.led_control import player_slot_color

    uniq = JOGADORES[n - 1]
    return pacotes.Contexto(
        state={"active_profile": ""},
        mesa=[{"pref": f"p{n}", "jogador": n, "uniq": uniq, "nome": "Régua", "via": "USB",
               "cor": "starlight-blue"}],
        conectados=[{"uniq": uniq, "connected": True, "transport": "usb", "index": n - 1,
                     "player": n, "lightbar_rgb": list(player_slot_color(n))}],
        estados={})


def _gesto(nome: str) -> Any:
    import pacotes

    gesto = pacotes.gesto_da_pagina("04-iluminacao.html", nome)
    assert gesto is not None, nome
    return gesto


class _Ponte:
    """O `machine_declare` do daemon, no que se mede: a declaração PARCIAL funde no disco."""

    def __init__(self) -> None:
        self.chamadas: list[dict[str, Any]] = []

    def machine_declare(self, declaracao: dict[str, Any]) -> tuple[bool, str | None]:
        from hefesto_dualsense4unix.utils.maquina import gravar_maquina_com_descartes

        self.chamadas.append(declaracao)
        gravar_maquina_com_descartes(declaracao)
        return True, None


def _options(html: str) -> list[tuple[str, str]]:
    return re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', html)


# ---------------------------------------------------------------- a lista tem as oito opções

def test_a_lista_tem_as_oito_opcoes_na_ordem_do_desenho() -> None:
    from pacotes import a04_iluminacao as a04

    html = a04.opcoes_do_efeito({})
    assert re.findall(r'<optgroup label="([^"]*)"', html) == GRUPOS_NA_ORDEM
    assert [v for v, _ in _options(html)] == VALORES_NA_ORDEM
    assert [r for _, r in _options(html)] == ROTULOS_NA_ORDEM
    for fora in ("Acende no gatilho", "Na batida"):
        assert fora not in html, "esses dois só entram pelo estilo, nunca pela lista"


def test_a_lista_leva_os_efeitos_que_a_pessoa_criou_depois_das_oito() -> None:
    from pacotes import a04_iluminacao as a04

    biblioteca = {"Alerta": {"nome": "Alerta", "base": "piscar",
                             "parametros": {"cores": "#FF0000", "ritmo": 6}}}
    html = a04.opcoes_do_efeito(biblioteca)
    assert 'optgroup label="Seus efeitos"' in html
    valores = [v for v, _ in _options(html)]
    assert valores[:8] == VALORES_NA_ORDEM and valores[8:] == ["piscar;FF0000;6"]


def test_toda_base_do_motor_esta_na_lista_e_tem_a_sua_frase() -> None:
    """Base nova no motor sem opção e sem frase na tela é a lista que mente."""
    from hefesto_dualsense4unix.profiles.schema import BASES_DA_LUZ
    from pacotes import a04_iluminacao as a04

    na_lista = {v.removeprefix("base:") for v in VALORES_NA_ORDEM if v.startswith("base:")}
    assert na_lista == set(BASES_DA_LUZ)
    assert set(a04.DICA_DA_BASE) == set(BASES_DA_LUZ) == set(a04.RITMO_DA_BASE)


def test_cada_frase_e_de_uma_linha_com_a_primeira_maiuscula() -> None:
    from pacotes import a04_iluminacao as a04

    frases = [a04.DICA_SEM_EFEITO, a04.DICA_LUZ_FIXA, a04.DICA_DO_EFEITO_CRIADO,
              *a04.DICA_DA_BASE.values()]
    assert len(set(frases)) == len(frases), "duas opções com a mesma frase não se distinguem"
    for frase in frases:
        assert frase[0].isupper() and frase.endswith("."), frase
        # A coluna tem 232px e a frase não quebra: com 40 a 60 letras ela saía cortada com
        # reticências no meio da palavra (medido na tela, 15/10/2026); 36 cabe inteira.
        assert "\n" not in frase and len(frase) <= 36, f"a frase não cabe na coluna: {frase}"
    for valor in VALORES_NA_ORDEM:
        assert a04.dica_do_efeito(valor)
    assert a04.dica_do_efeito("piscar;FF0000;6") == a04.DICA_DO_EFEITO_CRIADO


# ---------------------------------------------------------------- o desenho (mockup)

def _doc() -> str:
    bruto = MOCKUP.read_text(encoding="utf-8")
    sem_comentario = re.sub(r"<!--.*?-->", "", bruto, flags=re.S)
    return re.sub(r"<(style|script)\b[^>]*>.*?</\1>", "", sem_comentario, flags=re.S)


def test_o_desenho_tem_uma_lista_por_controle_com_as_oito_opcoes_e_a_frase() -> None:
    doc = _doc()
    listas = re.findall(r'<select class="g4-efeito".*?</select>', doc, flags=re.S)
    assert len(listas) == 4, "uma lista suspensa por controle, viva ou vazia"
    for lista in listas:
        assert re.findall(r'<optgroup label="([^"]*)"', lista)[:3] == GRUPOS_NA_ORDEM
        assert [v for v, _ in _options(lista)][:8] == VALORES_NA_ORDEM
        assert [r for _, r in _options(lista)][:8] == ROTULOS_NA_ORDEM
    assert doc.count('class="g4-dica-do-efeito"') == 4, "a frase de uma linha, uma por controle"


def test_o_desenho_tem_o_sem_piscar_uma_vez_e_desligado() -> None:
    doc = _doc()
    botoes = re.findall(r'<button class="sem-piscar"[^>]*>', doc)
    assert len(botoes) == 1, botoes
    botao = botoes[0]
    assert 'data-gesto="sem-piscar"' in botao and 'aria-pressed="false"' in botao
    assert 'data-pedido="ligar"' in botao, "desligado, o próximo clique pede ligar"
    assert 'data-campo="sem-piscar"' in botao and 'data-hef-atributo="aria-pressed"' in botao
    assert "Sem piscar</button>" in doc


# ---------------------------------------------------------------- o gesto da lista

@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_escolher_uma_base_grava_o_texto_com_a_cor_do_controle(n: int) -> None:
    """A cor é a do controle (a mesma que a coluna mostra); o ritmo, o com que a base nasce."""
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from hefesto_dualsense4unix.profiles.schema import ler_o_efeito_da_luz
    from pacotes import a04_iluminacao as a04

    uniq = JOGADORES[n - 1]
    chave = uniq.replace(":", "")
    cor_da_coluna = a04.pacote(_ctx(n))["colunas"][uniq]["hex"].lstrip("#").upper()
    assert re.fullmatch(r"[0-9A-F]{6}", cor_da_coluna), cor_da_coluna
    for base in ("respirar", "batimento", "chama", "mare", "piscar"):
        _gesto("efeito-da-luz")(_ctx(n), {"uniq": uniq, "valor": f"base:{base}"}, None)
        guardado = o_computador().controles[chave].leds.efeito
        assert guardado == f"{base};{cor_da_coluna};{a04.RITMO_DA_BASE[base]}", guardado
        assert ler_o_efeito_da_luz(guardado) is not None
        coluna = a04.pacote(_ctx(n))["colunas"][uniq]
        assert coluna[a04.CAMPO_DO_EFEITO] == f"base:{base}", "a lista volta na opção escolhida"
        assert coluna[a04.CAMPO_DA_DICA_DO_EFEITO] == a04.DICA_DA_BASE[base]


def test_o_arco_iris_nao_leva_cor_e_a_lista_o_reconhece() -> None:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from pacotes import a04_iluminacao as a04

    _gesto("efeito-da-luz")(_ctx(), {"uniq": JOGADORES[0], "valor": "base:arco-iris"}, None)
    assert o_computador().controles["aabbcc000001"].leds.efeito == "arco-iris;;7"
    assert a04.pacote(_ctx())["colunas"][JOGADORES[0]][a04.CAMPO_DO_EFEITO] == "base:arco-iris"


def test_o_efeito_com_outra_cor_nao_finge_ser_a_base() -> None:
    """A barra faz o que o texto diz: um respirar ciano não aparece como «Respirar» do controle."""
    from pacotes import a04_iluminacao as a04

    cru = {"leds": {"efeito": "respirar;00FFFF;2"}}
    assert a04.escolha_da_lista(cru, JOGADORES[0], 1.0, frozenset(), (255, 0, 0)) == \
        "respirar;00FFFF;2"
    assert a04.escolha_da_lista(cru, JOGADORES[0], 1.0, frozenset(), (0, 255, 255)) == \
        "base:respirar"
    # Um efeito que a pessoa criou com o mesmo texto da base continua sendo o dela.
    assert a04.escolha_da_lista(cru, JOGADORES[0], 1.0, frozenset({"respirar;00FFFF;2"}),
                                (0, 255, 255)) == "respirar;00FFFF;2"
    # E a lista oferece o texto que não é base, para nunca ficar em branco.
    assert 'value="respirar;00FFFF;2"' in a04.opcoes_do_efeito({}, "respirar;00FFFF;2",
                                                                (255, 0, 0))
    assert 'value="respirar;00FFFF;2"' not in a04.opcoes_do_efeito({}, "respirar;00FFFF;2",
                                                                   (0, 255, 255))


def test_uma_base_que_a_lista_nao_tem_e_recusada() -> None:
    with pytest.raises(ValueError, match="não tem a base"):
        _gesto("efeito-da-luz")(_ctx(), {"uniq": JOGADORES[0], "valor": "base:inventada"}, None)


def test_sem_efeito_e_luz_fixa_continuam_a_valer() -> None:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador

    _gesto("efeito-da-luz")(_ctx(), {"uniq": JOGADORES[0], "valor": "base:chama"}, None)
    _gesto("efeito-da-luz")(_ctx(), {"uniq": JOGADORES[0], "valor": "luz-fixa"}, None)
    dele = o_computador().controles.get("aabbcc000001")
    assert dele is None or dele.leds is None or dele.leds.efeito is None


# ---------------------------------------------------------------- o Sem piscar

def test_ligar_o_sem_piscar_grava_o_valor_global_e_a_leitura_devolve_ligado(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O valor mora no `maquina.json`; a leitura é a do motor (`schema.sem_piscar_da_mesa`)."""
    from hefesto_dualsense4unix.profiles import schema
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina
    from pacotes import a04_iluminacao as a04

    monkeypatch.setattr(schema, "_FONTE_DA_DECLARACAO", carregar_maquina)
    assert schema.sem_piscar_da_mesa() is False and a04.o_sem_piscar_de_agora() is False
    ponte = _Ponte()
    _gesto("sem-piscar")(_ctx(), {"pedido": "ligar"}, ponte)
    assert ponte.chamadas == [{"luz": {"sem_piscar": True}}]
    assert carregar_maquina().luz.sem_piscar is True
    assert schema.sem_piscar_da_mesa() is True, "o motor lê o que a tela gravou"
    assert a04.o_sem_piscar_de_agora() is True
    assert a04.pacote(_ctx())[a04.CAMPO_DO_SEM_PISCAR] == "sim"
    # Desligar volta a «sem opinião», que vale desligado.
    _gesto("sem-piscar")(_ctx(), {"pedido": "desligar"}, ponte)
    assert carregar_maquina().luz.sem_piscar is None
    assert schema.sem_piscar_da_mesa() is False and a04.o_sem_piscar_de_agora() is False
    assert a04.pacote(_ctx())[a04.CAMPO_DO_SEM_PISCAR] == ""


def test_o_sem_piscar_e_um_so_para_os_controles_e_nenhum_perfil_ganha_campo() -> None:
    from hefesto_dualsense4unix.profiles.schema import ControllerOverrides, LedsConfig, Profile
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    _gesto("sem-piscar")(_ctx(), {"pedido": "ligar"}, _Ponte())
    maquina = carregar_maquina()
    assert maquina.luz.sem_piscar is True and not maquina.controles, \
        "o valor não vira declaração de um controle"
    for modelo in (Profile, LedsConfig, ControllerOverrides):
        assert not [c for c in modelo.model_fields if "piscar" in c], modelo.__name__


def test_o_sem_piscar_sem_pedido_nao_vem_da_tela() -> None:
    with pytest.raises(ValueError, match="não disse se liga ou desliga"):
        _gesto("sem-piscar")(_ctx(), {}, _Ponte())


def test_o_sem_piscar_recusado_pelo_daemon_levanta() -> None:
    class _Recusa:
        def machine_declare(self, _declaracao: dict[str, Any]) -> tuple[bool, str | None]:
            return False, "O Hefesto não respondeu."

    with pytest.raises(RuntimeError, match="não respondeu"):
        _gesto("sem-piscar")(_ctx(), {"pedido": "ligar"}, _Recusa())


def test_o_sem_piscar_e_gesto_do_computador_e_clica_na_varredura() -> None:
    import pacotes

    assert pacotes.camada.CAMADA[("04-iluminacao.html", "sem-piscar")] == \
        pacotes.camada.COMPUTADOR
    from pacotes import a04_iluminacao as a04

    assert "machine_declare" in a04.PONTE and "machine.declare" in a04.METODOS
    provas = [p for p in a04.PROVAS if p["gesto"] == a04.GESTO_DO_SEM_PISCAR]
    assert provas and provas[0]["chama"][0][0] == "machine_declare"


# ---------------------------------------------------------------- a base segue a cor do controle

class _PonteDaCor:
    """O `led_set_detalhado` do daemon, no que o gesto `cor` lê: aplicado neste controle."""

    def __init__(self, uniq: str) -> None:
        self.uniq = uniq

    def led_set_detalhado(self, *_a: Any, **_k: Any) -> dict[str, Any]:
        return {"aplicado_em": [self.uniq], "guardado_em": []}


def _ctx_na_via(n: int, via: str, rgb: tuple[int, int, int] | None = None) -> Any:
    ctx = _ctx(n)
    ctx.conectados[0]["transport"] = via
    ctx.mesa[0]["via"] = via.upper()
    if rgb is not None:
        ctx.conectados[0]["lightbar_rgb"] = list(rgb)
    return ctx


@pytest.mark.parametrize(("n", "via"), [(1, "usb"), (2, "bt"), (3, "usb"), (4, "bt")])
def test_trocar_a_cor_leva_a_base_junto_no_cabo_e_no_radio(n: int, via: str) -> None:
    """A base nasce com a cor do controle; trocar a cor depois reescreve o efeito na cor nova.

    Sem isso a barra respirava a cor velha, a linha Cor dizia a nova e a lista pulava para «Seus
    efeitos».
    """
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from pacotes import a04_iluminacao as a04

    uniq = JOGADORES[n - 1]
    chave = uniq.replace(":", "")
    _gesto("efeito-da-luz")(_ctx_na_via(n, via), {"uniq": uniq, "valor": "base:respirar"}, None)
    a04.cor(_ctx_na_via(n, via), {"uniq": uniq, "hex": "FF8000"}, _PonteDaCor(uniq))
    leds = o_computador().controles[chave].leds
    assert tuple(leds.lightbar) == (255, 128, 0)
    assert leds.efeito == f"respirar;FF8000;{a04.RITMO_DA_BASE['respirar']}", leds.efeito
    coluna = a04.pacote(_ctx_na_via(n, via, (255, 128, 0)))["colunas"][uniq]
    assert coluna[a04.CAMPO_DO_EFEITO] == "base:respirar", "a lista continua na base"


def test_trocar_a_cor_nao_mexe_no_arco_iris_nem_no_efeito_criado() -> None:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from pacotes import a04_iluminacao as a04

    uniq, chave = JOGADORES[0], "aabbcc000001"
    for valor, guardado in (("base:arco-iris", "arco-iris;;7"),
                            ("respirar;00FFFF;4", "respirar;00FFFF;4")):
        _gesto("efeito-da-luz")(_ctx(), {"uniq": uniq, "valor": valor}, None)
        a04.cor(_ctx(), {"uniq": uniq, "hex": "FF8000"}, _PonteDaCor(uniq))
        assert o_computador().controles[chave].leds.efeito == guardado, valor


def test_trocar_a_cor_sem_efeito_nao_inventa_efeito() -> None:
    from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador
    from pacotes import a04_iluminacao as a04

    uniq = JOGADORES[0]
    a04.cor(_ctx(), {"uniq": uniq, "hex": "FF8000"}, _PonteDaCor(uniq))
    assert o_computador().controles["aabbcc000001"].leds.efeito is None
