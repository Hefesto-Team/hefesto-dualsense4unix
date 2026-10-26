"""O-BOTAO-QUE-TRAVA-A-NAVEGACAO-DOS-CONTROLES-01 — as réguas (26/10/2026).

O pedido: «Temos que ter um botão pra impedir a navegação interna dos controles. Vi que vira um
caos.» <!-- noqa-acento: citação literal --> A escolha foi a (c), as duas juntas:

* o botão na moldura de TODA aba, que escreve a ``ligada`` do mesmo ``navegacao_interna.flag``;
* destravada, só um controle navega por vez (quem toca primeiro, até ficar parado
  ``PRAZO_DO_DONO_S``).

O lar é de mentira pelo ``tests/conftest.py``: a flag que o ``definir`` grava cai no ``tmp``.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any

import pytest

import hefesto_dualsense4unix
from hefesto_dualsense4unix.daemon.subsystems import navegacao_interna as dono
from hefesto_dualsense4unix.utils import session

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
P3 = "aa:bb:cc:00:00:03"
INTERFACE = Path(hefesto_dualsense4unix.__file__).parent / "interface"
DEZ = ("01-jogar.html", "02-controles.html", "03-gatilhos.html", "04-iluminacao.html",
       "05-vibracao.html", "06-navegacao.html", "07-lancadores.html", "08-conexoes.html",
       "09-sistema.html", "10-perfis.html")


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


def _interna(relogio: _Relogio, *, ligada: bool = True, foco: bool = True) -> dono.NavegacaoInterna:
    n = dono.NavegacaoInterna(ligada=ligada, tipo=dono.TIPO_INTERNA, relogio=relogio)
    if foco:
        n.declarar_foco(True)
    return n


def _pacotes() -> Any:
    """Os pacotes como o piloto os importa (o ``interface/`` no caminho)."""
    if str(INTERFACE) not in sys.path:
        sys.path.insert(0, str(INTERFACE))
    import pacotes

    pacotes._carregar_tudo()
    return pacotes


class _Ponte:
    """O carimbo do IPC que anota o que o gesto pede e responde o que a régua mandar."""

    def __init__(self, resposta: Any = None, *, cai: bool = False) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []
        self._resposta = {"status": "ok"} if resposta is None else resposta
        self._cai = cai

    def resultado(self, metodo: str, **parametros: Any) -> Any:
        self.chamadas.append((metodo, parametros))
        if self._cai:
            raise RuntimeError("sem daemon")
        return self._resposta


def _contexto(pac: Any, **bloco_da_navegacao: Any) -> Any:
    estado: dict[str, Any] = {"active_profile": "Régua"}
    if bloco_da_navegacao:
        estado["navegacao"] = dict(bloco_da_navegacao)
    return pac.Contexto(state=estado, mesa=[], conectados=[], estados={})


# 1 ─ Travada: nada se conta e nada se rouba ───────────────────────────────────


def test_1_travada_com_o_foco_vivo_a_interna_nao_age_e_o_jogo_fica_com_tudo() -> None:
    relogio = _Relogio()
    interna = _interna(relogio, ligada=False)
    assert interna.foco_vivo() is True
    assert interna.age() is False
    botoes = frozenset({"cross", "r1", "l1", "dpad_down", "options", "l2_btn"})
    assert interna.roubar(botoes) == botoes, "travada, nenhum botão sai do jogo"
    assert interna.calar_o_alt_tab(botoes, mouse_ligado=True) == botoes
    assert interna.calar_o_alt_tab(botoes, mouse_ligado=False) == botoes


def test_2_travada_nenhum_toque_se_conta_de_nenhum_controle() -> None:
    interna = _interna(_Relogio(), ligada=False)
    interna.contar({P1: {"r1": 0}, P2: {"dpad_down": 0}})
    interna.contar({P1: {"r1": 9, "cross": 4}, P2: {"dpad_down": 7, "options": 2}})
    assert all(not any(t.values()) for t in interna.toques().values()), interna.toques()


def test_3_destravar_devolve_a_interna_e_a_trava_nao_deixa_toque_para_tras() -> None:
    interna = _interna(_Relogio(), ligada=False)
    interna.contar({P1: {"r1": 0}})
    interna.contar({P1: {"r1": 5}})
    interna.definir(ligada=True)
    assert interna.age() is True
    assert interna.roubar(frozenset({"r1", "l2_btn"})) == frozenset({"l2_btn"})
    interna.contar({P1: {"r1": 6}})
    assert interna.toques()[P1]["r1"] == 1, "os cinco toques de quando estava travada não voltam"


# 2 ─ Um controle navega por vez ──────────────────────────────────────────────


def test_4_dois_uniq_tocando_juntos_dao_os_toques_so_de_um() -> None:
    interna = _interna(_Relogio())
    interna.contar({P1: {}, P2: {}})
    for n in range(1, 6):
        interna.contar({P1: {"dpad_down": n, "r1": n}, P2: {"dpad_down": n, "r1": n}})
    toques = interna.toques()
    assert toques[P1]["baixo"] == 5 and toques[P1]["r1"] == 5, toques
    assert toques[P2]["baixo"] == 0 and toques[P2]["r1"] == 0, (
        f"o segundo controle mexeu na janela junto com o primeiro: {toques[P2]}")


def test_5_quem_toca_primeiro_fica_com_a_navegacao_seja_qual_for_a_ordem_da_leitura() -> None:
    interna = _interna(_Relogio())
    interna.contar({P1: {}, P2: {}, P3: {}})
    interna.contar({P3: {"cross": 1}, P1: {"cross": 0}, P2: {"cross": 0}})
    interna.contar({P1: {"cross": 1}, P2: {"cross": 1}, P3: {"cross": 2}})
    toques = interna.toques()
    assert toques[P3]["x"] == 2, toques
    assert toques[P1]["x"] == 0 and toques[P2]["x"] == 0, toques


def test_6_o_toque_do_outro_ignorado_nao_volta_quando_o_dono_larga() -> None:
    relogio = _Relogio()
    interna = _interna(relogio)
    interna.contar({P1: {}, P2: {}})
    interna.contar({P1: {"r1": 1}, P2: {"r1": 3}})
    relogio.agora += dono.PRAZO_DO_DONO_S + 0.5
    interna.declarar_foco(True)
    interna.contar({P1: {"r1": 1}, P2: {"r1": 3}})
    assert interna.toques()[P2]["r1"] == 0, "o que o segundo tocou sem ser o dono ficou perdido"


def test_7_parado_por_alguns_segundos_o_dono_largou_e_o_outro_assume() -> None:
    relogio = _Relogio()
    interna = _interna(relogio)
    interna.contar({P1: {}, P2: {}})
    interna.contar({P1: {"r1": 1}, P2: {"r1": 0}})
    relogio.agora += dono.PRAZO_DO_DONO_S - 0.5
    interna.declarar_foco(True)
    interna.contar({P1: {"r1": 1}, P2: {"r1": 1}})
    assert interna.toques()[P2]["r1"] == 0, "antes do prazo o dono segue sendo o primeiro"
    relogio.agora += 1.0
    interna.declarar_foco(True)
    interna.contar({P1: {"r1": 1}, P2: {"r1": 2}})
    toques = interna.toques()
    assert toques[P2]["r1"] == 1, f"passado o prazo, o segundo controle assume: {toques}"
    assert toques[P1]["r1"] == 1


def test_8_cada_toque_do_dono_renova_o_prazo_dele() -> None:
    relogio = _Relogio()
    interna = _interna(relogio)
    interna.contar({P1: {}, P2: {}})
    for n in range(1, 5):
        relogio.agora += dono.PRAZO_DO_DONO_S - 0.5
        interna.declarar_foco(True)
        interna.contar({P1: {"r1": n}, P2: {"r1": n}})
    toques = interna.toques()
    assert toques[P1]["r1"] == 4 and toques[P2]["r1"] == 0, toques


def test_9_sem_a_janela_na_frente_o_dono_se_zera() -> None:
    relogio = _Relogio()
    interna = _interna(relogio)
    interna.contar({P1: {}, P2: {}})
    interna.contar({P1: {"r1": 1}, P2: {"r1": 0}})
    interna.declarar_foco(False)
    interna.contar({P1: {"r1": 2}, P2: {"r1": 1}})
    interna.declarar_foco(True)
    interna.contar({P1: {"r1": 2}, P2: {"r1": 2}})
    assert interna.toques()[P2]["r1"] == 1, "voltou o foco, o primeiro a tocar é o dono de novo"


def test_10_um_controle_so_navega_como_antes() -> None:
    interna = _interna(_Relogio())
    interna.contar({P1: {}})
    interna.contar({P1: {"dpad_up": 2, "options": 1}})
    assert interna.toques()[P1]["cima"] == 2 and interna.toques()[P1]["start"] == 1


def test_11_a_regra_do_dono_nao_mexe_no_tipo_nem_na_ligada() -> None:
    interna = _interna(_Relogio())
    interna.contar({P1: {}, P2: {}})
    interna.contar({P1: {"r1": 1}, P2: {"r1": 1}})
    assert interna.ligada is True and interna.tipo == dono.TIPO_INTERNA
    assert interna.bloco() == {"interna_ligada": True, "tipo": dono.TIPO_INTERNA, "foco": True}


# 3 ─ O botão escreve a MESMA flag ─────────────────────────────────────────────


def test_12_o_definir_grava_a_ligada_no_mesmo_arquivo_e_o_tipo_nao_muda() -> None:
    interna = _interna(_Relogio(), ligada=True)
    interna.definir(ligada=False)
    assert session.load_navegacao_interna() == (False, dono.TIPO_INTERNA)
    interna.definir(ligada=True)
    assert session.load_navegacao_interna() == (True, dono.TIPO_INTERNA)


def test_13_o_gesto_pede_o_contrario_do_que_a_tela_mostra() -> None:
    pac = _pacotes()
    travar = pac.gesto_da_pagina("01-jogar.html", "travar-navegacao")
    assert travar is not None, "a moldura de toda aba atende o gesto"
    ponte = _Ponte()
    travar(_contexto(pac, interna_ligada=True, tipo="interna"), {}, ponte)
    assert ponte.chamadas == [("navegacao.interna.set", {"ligada": False, "origin": "manual"})]
    ponte = _Ponte()
    travar(_contexto(pac, interna_ligada=False, tipo="interna"), {}, ponte)
    assert ponte.chamadas == [("navegacao.interna.set", {"ligada": True, "origin": "manual"})]


def test_14_o_gesto_e_o_mesmo_em_todas_as_dez_abas() -> None:
    pac = _pacotes()
    atendentes = {inspect.unwrap(g)
                  for g in (pac.gesto_da_pagina(aba, "travar-navegacao") for aba in DEZ)}
    assert len(atendentes) == 1 and None not in atendentes, atendentes
    assert ("*", "travar-navegacao") in pac.GESTOS
    assert not any(p != "*" and g == "travar-navegacao" for p, g in pac.GESTOS), (
        "o botão tem um escritor só: um segundo gesto por aba seria uma segunda flag")


def test_15_sem_o_bloco_do_daemon_o_gesto_recusa_em_vez_de_chutar() -> None:
    pac = _pacotes()
    travar = pac.gesto_da_pagina("06-navegacao.html", "travar-navegacao")
    ponte = _Ponte()
    with pytest.raises(RuntimeError, match="não respondeu"):
        travar(_contexto(pac), {}, ponte)
    assert ponte.chamadas == []


def test_16_o_daemon_que_cai_ou_recusa_deixa_a_navegacao_como_estava() -> None:
    pac = _pacotes()
    travar = pac.gesto_da_pagina("06-navegacao.html", "travar-navegacao")
    ctx = _contexto(pac, interna_ligada=True, tipo="interna")
    with pytest.raises(RuntimeError, match="como estava"):
        travar(ctx, {}, _Ponte(cai=True))
    with pytest.raises(RuntimeError, match="como estava"):
        travar(ctx, {}, _Ponte({"status": "erro"}))


def test_17_o_gesto_declara_o_que_grava() -> None:
    pac = _pacotes()
    assert pac.GESTOS_QUE_MEXEM[("*", "travar-navegacao")] == "navegacao.interna.set"


def test_18_no_nativo_o_botao_segue_vivo_porque_a_interna_e_da_janela() -> None:
    pac = _pacotes()
    estado = {"active_profile": "Régua", "navegacao": {"interna_ligada": True}}
    for aba in DEZ:
        assert pac.camada.recusa_no_nativo(aba, "travar-navegacao", estado) is None, aba
    assert frozenset({"travar-navegacao"}) == pac.camada.GESTOS_DA_MOLDURA


# 4 ─ A tela: o campo pintado e o botão na moldura de toda aba ────────────────────


def test_19_o_topo_pinta_o_botao_apertado_so_quando_o_daemon_diz_travada() -> None:
    pac = _pacotes()
    campo = "navegacao-travada"
    assert pac.topo(_contexto(pac, interna_ligada=False, tipo="interna"))[campo] == "true"
    assert pac.topo(_contexto(pac, interna_ligada=True, tipo="interna"))[campo] == "false"
    assert pac.topo(_contexto(pac))[campo] == "false", "sem o bloco do daemon, o botão fica solto"


def test_20_a_moldura_traz_o_botao_pintado_pelo_campo_e_aciona_o_gesto() -> None:
    topo = (INTERFACE / "topo.html").read_text(encoding="utf-8")
    assert topo.count('data-gesto="travar-navegacao"') == 1
    assert 'data-campo="navegacao-travada"' in topo
    assert 'data-hef-atributo="aria-pressed"' in topo
    pac = _pacotes()
    assert "navegacao-travada" in pac.topo(_contexto(pac))


@pytest.mark.parametrize("aba", DEZ)
def test_21_o_desenho_de_toda_aba_traz_o_botao(aba: str) -> None:
    raiz = Path(hefesto_dualsense4unix.__file__).resolve().parents[2]
    pagina = (raiz / "mockup" / aba).read_text(encoding="utf-8")
    assert pagina.count('data-gesto="travar-navegacao"') == 1, (
        f"{aba} sem o botão da moldura (regere a aba: o topo.html entra por ela)")
