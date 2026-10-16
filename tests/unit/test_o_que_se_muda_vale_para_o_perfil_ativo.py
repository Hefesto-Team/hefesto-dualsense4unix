"""O que se muda vale para o perfil ativo (O-ESCOPO-SAI-DAS-ABAS-01, D-0610-O-ESCOPO-SAI-DAS-ABAS).

O «Só neste jogo / Voltar ao do PC» saiu das abas: o que ela muda vale para o
perfil ativo, o do jogo aberto, ou o do computador sem jogo. O jogo guarda só o
campo que mudou; o resto do cartão segue vindo do computador.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

import hefesto_dualsense4unix
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.profiles import o_padrao_do_computador as opc
from hefesto_dualsense4unix.profiles.loader import load_profile, save_profile
from hefesto_dualsense4unix.profiles.schema import Profile
from hefesto_dualsense4unix.utils import maquina as m

CONTROLES = ["aabbcc000001", "aabbcc000002", "aabbcc000003", "aabbcc000004"]
CARTOES_POR_CONTROLE = [c for c, s in opc.SECOES.items() if s.por_controle]
CARTOES_GLOBAIS = [c for c, s in opc.SECOES.items() if not s.por_controle]


def _perfil(nome: str = "Jogo X", **campos: Any) -> Profile:
    return Profile.model_validate(
        {"name": nome, "match": {"type": "criteria", "window_class": [nome.lower()]},
         **campos})


def _computador(documento: dict[str, Any]) -> None:
    assert m.gravar_o_computador(documento)


def _campo_do_cartao(cartao: str, uniq: str) -> dict[str, Any]:
    """Um campo que muda no cartão, na forma de ``opc.gravar``."""
    campos: dict[str, dict[str, Any]] = {
        "luz": {"leds": {"lightbar_brightness": 0.4}},
        "vibracao": {"rumble": {"motor_forte_pct": 40}},
        "som": {"speaker": {"volume": 55}},
        "sensores": {"sensores": {"giroscopio": False}},
        "mouse": {"mouse": {"enabled": False, "speed": 9, "scroll_speed": 3}},
        "teclado": {"teclado_emulado": True},
        "acessibilidade": {  # (noqa-acento)
            "ativacao": {"alternar": ["l1"], "repique_ms": 120},  # (noqa-acento)
            "analogicos": {"zona_morta": 20, "curva": "precisa"},  # (noqa-acento)
        },
    }
    return campos[cartao]


@pytest.mark.parametrize("uniq", CONTROLES)
@pytest.mark.parametrize("cartao", CARTOES_POR_CONTROLE)
def test_jogo_sem_escolha_propria_grava_no_jogo_em_cada_controle(
    cartao: str, uniq: str
) -> None:
    """Linha 1 da tabela: o jogo aberto sem escolha própria. Antes, ia ao ``maquina.json``."""
    save_profile(_perfil())
    campos = _campo_do_cartao(cartao, uniq)
    assert opc.onde_grava(cartao, load_profile("Jogo X")) == opc.JOGO
    assert opc.gravar(cartao, campos, uniq=uniq, perfil_ativo="Jogo X") == opc.JOGO
    assert opc.sobrepoe(load_profile("Jogo X"), cartao, uniq)
    assert opc.computador_vazio(opc.o_computador())


@pytest.mark.parametrize("uniq", CONTROLES)
def test_jogo_com_escolha_propria_num_controle_e_o_outro_controle_vao_ao_jogo(
    uniq: str
) -> None:
    """Linhas 2 e 3: com escolha própria no controle 01, e no mesmo jogo, em qualquer outro."""
    save_profile(_perfil(controllers={
        CONTROLES[0]: {"leds": {"lightbar": [9, 9, 9]}}}))
    assert opc.onde_grava("luz", load_profile("Jogo X")) == opc.JOGO
    onde_foi = opc.gravar("luz", {"leds": {"lightbar": [1, 2, 3]}}, uniq=uniq,
                          perfil_ativo="Jogo X")
    assert onde_foi == opc.JOGO
    jogo = load_profile("Jogo X")
    assert jogo.controllers[opc.chave_no_perfil(jogo, uniq)].leds.lightbar == (1, 2, 3)
    assert opc.computador_vazio(opc.o_computador())


def test_freestyle_e_nenhum_perfil_vao_ao_computador() -> None:
    # A decisão D-0610-O-ESCOPO-SAI-DAS-ABAS.
    """Linha 4: sem jogo aberto o que se muda vale para o PC."""
    save_profile(Profile.model_validate({"name": "Freestyle", "match": {"type": "any"}}))
    freestyle = load_profile("Freestyle")
    antes = Path(save_profile(freestyle)).read_bytes()
    assert opc.onde_grava("luz", freestyle) == opc.COMPUTADOR
    assert opc.onde_grava("luz", None) == opc.COMPUTADOR
    assert opc.gravar("luz", {"leds": {"lightbar": [1, 2, 3]}}, uniq=CONTROLES[1],
                      perfil_ativo="Freestyle") == opc.COMPUTADOR
    assert opc.gravar("luz", {"leds": {"lightbar_brightness": 0.5}}, uniq=CONTROLES[1],
                      perfil_ativo=None) == opc.COMPUTADOR
    assert Path(save_profile(freestyle)).read_bytes() == antes
    assert opc.o_computador().controles[CONTROLES[1]].leds.lightbar == (1, 2, 3)


@pytest.mark.parametrize("cartao", CARTOES_GLOBAIS)
def test_cartao_do_computador_inteiro_segue_a_mesma_regra(cartao: str) -> None:
    """Mouse e teclado (sem controle) também: jogo aberto grava no jogo."""
    save_profile(_perfil())
    assert opc.gravar(cartao, _campo_do_cartao(cartao, ""), perfil_ativo="Jogo X") == opc.JOGO
    assert opc.computador_vazio(opc.o_computador())


@pytest.mark.parametrize("uniq", CONTROLES)
def test_so_o_campo_mudado_vai_ao_jogo(uniq: str) -> None:
    # A decisão D-0610-O-ESCOPO-SAI-DAS-ABAS.
    """O jogo não copia o cartão: o resto da luz segue vindo do computador."""
    _computador({"global": {"leds": {"lightbar": [10, 20, 200]}},
                 "controles": {uniq: {"leds": {"lightbar": [0, 255, 0]}}}})
    save_profile(_perfil())
    brilho = 0.4

    def muda(perfil: Profile) -> Profile:
        cru = perfil.model_dump(mode="json", exclude_unset=True)
        controles = dict(cru.get("controllers") or {})
        entrada = dict(controles.get(uniq) or {})
        entrada["leds"] = {**dict(entrada.get("leds") or {}), "lightbar_brightness": brilho}
        controles[uniq] = entrada
        cru["controllers"] = controles
        return Profile.model_validate(cru)

    onde_foi, _novo = opc.gravar_pelo_gesto("luz", "Jogo X", muda, uniq=uniq)
    assert onde_foi == opc.JOGO
    jogo = load_profile("Jogo X")
    entrada = jogo.controllers[opc.chave_no_perfil(jogo, uniq)]
    assert entrada.leds.model_fields_set == {"lightbar_brightness"}, entrada.leds
    assert not opc.escolhas_globais_do_jogo(jogo, "leds"), "a cor global do PC desceu ao jogo"
    vale = opc.perfil_que_vale(jogo, opc.o_computador())
    assert vale.controllers[opc.chave_no_perfil(vale, uniq)].leds.lightbar == (0, 255, 0)
    assert opc.o_computador().controles[uniq].leds.model_fields_set == {"lightbar"}


def test_o_valor_falso_tambem_e_mudanca_e_vai_ao_jogo() -> None:
    """Desligar o teclado (``False``) e esvaziar as teclas (``{}``) são mudanças de verdade.

    A MORDIDA: faça ``_diferenca_de_secao`` devolver ``{}`` em vez de ``_IGUAL``
    para «igual» (ou leia o falso como «nada mudou») e o teclado desligado
    volta a ser o de ontem, calado.
    """
    save_profile(_perfil(teclado_emulado=True, key_bindings={"cross": ["KEY_ENTER"]}))

    def _desliga(vista: Profile) -> Profile:
        return vista.model_copy(update={"teclado_emulado": False, "key_bindings": {}})

    opc.gravar_pelo_gesto("teclado", "Jogo X", _desliga, origem="regua")
    jogo = load_profile("Jogo X")
    assert jogo.teclado_emulado is False
    assert not jogo.key_bindings
    assert opc.computador_vazio(opc.o_computador())
    assert opc._diferenca_de_secao("teclado_emulado", True, True) is opc._IGUAL


def test_perfil_e_maquina_de_antes_valem_o_mesmo_e_nao_se_reescrevem() -> None:
    """Migração sem perda: nenhum arquivo muda no primeiro arranque desta regra."""
    _computador({"global": {"leds": {"lightbar": [10, 20, 200]}, "teclado_emulado": True},
                 "controles": {CONTROLES[1]: {"rumble": {"motor_forte_pct": 40}}}})
    caminho = save_profile(_perfil(controllers={
        CONTROLES[0]: {"leds": {"lightbar": [9, 9, 9]}}}))
    livre = save_profile(Profile.model_validate({"name": "Freestyle", "match": {"type": "any"}}))
    maquina = m.caminho_da_maquina()
    antes = (caminho.read_bytes(), livre.read_bytes(), maquina.read_bytes())
    vale_antes = opc.perfil_que_vale(load_profile("Jogo X"), opc.o_computador())
    for nome in ("Jogo X", "Freestyle"):
        for cartao in opc.SECOES:
            opc.onde_grava(cartao, load_profile(nome))
    vale_depois = opc.perfil_que_vale(load_profile("Jogo X"), opc.o_computador())
    assert vale_depois == vale_antes
    assert (caminho.read_bytes(), livre.read_bytes(), maquina.read_bytes()) == antes


def test_onde_grava_recusa_cartao_que_nao_existe() -> None:
    with pytest.raises(KeyError):
        opc.onde_grava("nao-existe", None)


# ---------------------------------------------------------------- o escopo saiu

def _pacotes() -> Any:
    interface = str(Path(hefesto_dualsense4unix.__file__).parent / "interface")
    if interface not in sys.path:
        sys.path.insert(0, interface)
    import pacotes

    pacotes._carregar_tudo()
    return pacotes


def test_o_escopo_saiu_do_codigo() -> None:
    """Sem as funções, os gestos e a peça da marca: nenhum caminho leva o jogo a «Só neste jogo»."""
    for nome in ("so_neste_jogo", "pode_so_neste_jogo", "perfil_so_neste_jogo", "marca"):
        assert not hasattr(opc, nome), f"{nome} voltou ao o_padrao_do_computador"
    with pytest.raises(ImportError):
        __import__("hefesto_dualsense4unix.interface.marca_da_camada")
    pac = _pacotes()
    for gesto in ("so-neste-jogo", "voltar-ao-do-computador"):
        assert ("*", gesto) not in pac.GESTOS
        assert not any(g == gesto for _p, g in pac.camada.CAMADA)


@pytest.mark.parametrize("aba", ["02-controles.html", "04-iluminacao.html",
                                    "05-vibracao.html", "06-navegacao.html"])
def test_o_desenho_das_quatro_abas_nao_traz_o_chip(aba: str) -> None:
    """O desenho (``mockup/``) não tem «Só neste jogo», «Voltar ao do PC» nem a marca."""
    texto = onde.pagina(aba, publicado=False).read_text(encoding="utf-8")
    for resto in ("Só neste jogo", "Voltar ao do PC", "so-neste-jogo",
                  "voltar-ao-do-computador", 'class="camada', "camada-dono"):
        assert resto not in texto, f"{aba} ainda traz {resto!r}"
