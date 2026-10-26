"""O-BOTAO-QUE-TRAVA-A-NAVEGACAO-DOS-CONTROLES-01 — as réguas (26/10/2026).

O pedido: «Temos que ter um botão pra impedir a navegação interna dos controles. Vi que vira um
caos.» <!-- noqa-acento: citação literal --> A escolha foi a (c), as duas juntas:

* o botão na moldura de TODA aba, que escreve a ``ligada`` do mesmo ``navegacao_interna.flag``;
* destravada, só um controle navega por vez (quem mexe primeiro, pelo botão, pelo analógico ou
  pelo touchpad, até ficar parado ``PRAZO_DO_DONO_S``), no ``Navegador`` da janela.

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
from hefesto_dualsense4unix.interface import navegacao_interna as navj
from hefesto_dualsense4unix.utils import session

P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
P3 = "aa:bb:cc:00:00:03"
P4 = "aa:bb:cc:00:00:04"
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


def _toq(**contas: int) -> dict[str, int]:
    return {k: contas.get(k, 0) for k in ("r1", "l1", "x", "o", "quadrado", "triangulo", "cima",
                                          "baixo", "esquerda", "direita", "start")}


PARADO = {"lx": 128, "ly": 128}
INCLINADO = {"lx": 128 + navj.LIMIAR_DO_ANALOGICO + 20, "ly": 128}
DEDO = {"touchpad": {"touching": True, "x": 960, "y": 540, "width": 1920, "height": 1080}}


class _Janela:
    """O `Navegador` como o piloto o chama a cada tique, com a base já lida."""

    def __init__(self, *uniqs: str) -> None:
        self.relogio = _Relogio()
        self.n = navj.Navegador(relogio=self.relogio)
        self.contas = {u: _toq() for u in uniqs}
        self.n.atos(pagina=DEZ[1], dez=DEZ, toques=self.contas, ativa=True,
                    inputs={u: PARADO for u in uniqs})

    def tique(self, *, apertos: dict[str, dict[str, int]] | None = None,
              inputs: dict[str, dict[str, Any]] | None = None, ativa: bool = True,
              sem: frozenset[str] = frozenset(), mais: float = 0.1) -> list[navj.Ato]:
        self.relogio.agora += mais
        for uniq, botoes in (apertos or {}).items():
            for nome, n in botoes.items():
                self.contas[uniq][nome] += n
        entradas = {u: PARADO for u in self.contas}
        entradas.update(inputs or {})
        toques = {u: dict(c) for u, c in self.contas.items()}
        return self.n.atos(pagina=DEZ[1], dez=DEZ, toques=toques, ativa=ativa, inputs=entradas,
                           sem_selecao=sem)


def _de(atos: list[navj.Ato]) -> set[str]:
    return {a.uniq for a in atos if a.uniq}


def test_4_dois_controles_tocando_juntos_so_um_navega() -> None:
    j = _Janela(P1, P2)
    vistos: list[navj.Ato] = []
    for _ in range(5):
        vistos += j.tique(apertos={P1: {"baixo": 1, "r1": 1}, P2: {"baixo": 1, "r1": 1}})
    assert _de(vistos) == {P1}, f"o segundo controle mexeu na janela junto com o primeiro: {vistos}"
    assert sum(a.tipo == "passo" for a in vistos) == 5
    idas = [a.pagina for a in vistos if a.tipo == "ir"]
    assert idas == [DEZ[2]] * 5, f"o R1 do segundo andou a aba junto (uma aba por R1): {idas}"


def test_5_quem_mexe_primeiro_fica_com_a_navegacao_seja_qual_for_a_ordem() -> None:
    j = _Janela(P1, P2, P3)
    j.tique(apertos={P3: {"x": 1}})
    atos = j.tique(apertos={P1: {"x": 1}, P2: {"x": 1}, P3: {"x": 1}})
    assert _de(atos) == {P3}, atos


def test_6_o_toque_do_outro_ignorado_nao_volta_quando_o_dono_larga() -> None:
    j = _Janela(P1, P2)
    j.tique(apertos={P1: {"baixo": 1}, P2: {"baixo": 3}})
    atos = j.tique(mais=navj.PRAZO_DO_DONO_S + 0.5)
    assert atos == [], f"o que o segundo tocou sem ser o dono voltou depois: {atos}"


def test_7_parado_por_alguns_segundos_o_dono_larga_e_o_outro_assume() -> None:
    j = _Janela(P1, P2)
    j.tique(apertos={P1: {"baixo": 1}})
    assert _de(j.tique(apertos={P2: {"baixo": 1}}, mais=navj.PRAZO_DO_DONO_S - 0.5)) == set(), (
        "antes do prazo o dono segue sendo o primeiro")
    atos = j.tique(apertos={P2: {"baixo": 1}}, mais=1.0)
    assert _de(atos) == {P2}, f"passado o prazo, o segundo controle assume: {atos}"


def test_8_cada_toque_do_dono_renova_o_prazo_dele() -> None:
    j = _Janela(P1, P2)
    vistos: list[navj.Ato] = []
    for _ in range(4):
        vistos += j.tique(apertos={P1: {"direita": 1}, P2: {"direita": 1}},
                          mais=navj.PRAZO_DO_DONO_S - 0.5)
    assert _de(vistos) == {P1}, vistos


def test_9_sem_a_janela_na_frente_o_dono_se_zera() -> None:
    j = _Janela(P1, P2)
    j.tique(apertos={P1: {"baixo": 1}})
    j.tique(apertos={P1: {"baixo": 1}, P2: {"baixo": 1}}, ativa=False)
    atos = j.tique(apertos={P2: {"baixo": 1}})
    assert _de(atos) == {P2}, "voltou o foco, o primeiro a mexer é o dono de novo"


def test_10_um_controle_so_navega_como_antes() -> None:
    j = _Janela(P1)
    atos = j.tique(apertos={P1: {"cima": 2, "x": 1}})
    assert [a.tipo for a in atos] == ["passo", "passo", "x"], atos


def test_11_o_analogico_e_o_dedo_do_outro_nao_andam_a_selecao_do_dono() -> None:
    """A regra cobre as três fontes da navegação, não só os botões que o daemon conta."""
    j = _Janela(P1, P2, P3)
    j.tique(apertos={P1: {"baixo": 1}})
    atos = j.tique(inputs={P2: INCLINADO, P3: DEDO})
    assert atos == [], f"o analógico ou o dedo de quem não é dono andou a seleção: {atos}"
    j.tique(mais=navj.PRAZO_DO_DONO_S + 0.5)
    atos = j.tique(inputs={P2: INCLINADO, P3: DEDO})
    assert _de(atos) == {P2}, f"livre, o primeiro que mexe (o analógico do P2) assume: {atos}"


def test_12_quem_navega_pelo_analogico_ou_pelo_dedo_e_dono_e_segura_os_botoes_dos_outros() -> None:
    for como in (INCLINADO, DEDO):
        j = _Janela(P1, P2)
        assert _de(j.tique(inputs={P2: como})) == {P2}
        atos = j.tique(apertos={P1: {"baixo": 1, "x": 1, "r1": 1}}, inputs={P2: como})
        assert P1 not in _de(atos) and not any(a.tipo == "ir" for a in atos), (
            f"com o P2 navegando por {como}, o P1 mexeu na janela: {atos}")


def test_13_o_start_de_qualquer_controle_guarda_e_nao_toma_a_navegacao() -> None:
    j = _Janela(P1, P2)
    j.tique(apertos={P1: {"baixo": 1}})
    atos = j.tique(apertos={P2: {"start": 1}})
    assert navj.Ato("salvar") in atos, "o Start de quem não navega deixou de guardar (22/10)"
    atos = j.tique(apertos={P1: {"baixo": 1}})
    assert _de(atos) == {P1}, "o Start do P2 tomou a navegação do P1"


def test_14_o_dono_que_sai_libera_a_navegacao_na_hora() -> None:
    j = _Janela(P1, P2)
    j.tique(apertos={P1: {"baixo": 1}})
    del j.contas[P1]
    atos = j.n.atos(pagina=DEZ[1], dez=DEZ, toques={P2: _toq(baixo=1)}, ativa=True,
                    inputs={P2: PARADO})
    assert _de(atos) == {P2}, f"o dono saiu e o outro esperou o prazo: {atos}"


@pytest.mark.parametrize("quem", [P1, P2, P3, P4])
def test_15_de_p1_a_p4_qualquer_um_pode_ser_o_dono(quem: str) -> None:
    todos = (P1, P2, P3, P4)
    j = _Janela(*todos)
    j.tique(apertos={quem: {"baixo": 1}})
    atos = j.tique(apertos={u: {"baixo": 1} for u in todos}, inputs={u: INCLINADO for u in todos})
    assert _de(atos) == {quem}, atos


def test_16_quem_navega_o_pc_com_o_mouse_anda_a_aba_mas_o_cursor_dele_nao_toma_a_vez() -> None:
    j = _Janela(P1, P2)
    atos = j.tique(inputs={P1: INCLINADO}, sem=frozenset({P1}))
    assert atos == [], "o analógico de quem move o mouse do PC não é navegação da janela"
    atos = j.tique(apertos={P2: {"baixo": 1}}, inputs={P1: INCLINADO}, sem=frozenset({P1}))
    assert _de(atos) == {P2}, atos


def test_17_o_daemon_conta_os_toques_de_todos_e_a_regra_nao_mexe_na_ligada() -> None:
    """A regra é da janela: o daemon segue contando cada controle, e nada muda a ``ligada``."""
    interna = _interna(_Relogio())
    interna.contar({P1: {}, P2: {}})
    interna.contar({P1: {"r1": 1}, P2: {"r1": 1}})
    assert interna.toques()[P1]["r1"] == 1 and interna.toques()[P2]["r1"] == 1
    assert interna.bloco() == {"interna_ligada": True, "tipo": dono.TIPO_INTERNA, "foco": True}


def test_18_o_definir_grava_a_ligada_no_mesmo_arquivo_e_o_tipo_nao_muda() -> None:
    interna = _interna(_Relogio(), ligada=True)
    interna.definir(ligada=False)
    assert session.load_navegacao_interna() == (False, dono.TIPO_INTERNA)
    interna.definir(ligada=True)
    assert session.load_navegacao_interna() == (True, dono.TIPO_INTERNA)


def test_19_o_gesto_pede_o_contrario_do_que_a_tela_mostra() -> None:
    pac = _pacotes()
    travar = pac.gesto_da_pagina("01-jogar.html", "travar-navegacao")
    assert travar is not None, "a moldura de toda aba atende o gesto"
    ponte = _Ponte()
    travar(_contexto(pac, interna_ligada=True, tipo="interna"), {}, ponte)
    assert ponte.chamadas == [("navegacao.interna.set", {"ligada": False, "origin": "manual"})]
    ponte = _Ponte()
    travar(_contexto(pac, interna_ligada=False, tipo="interna"), {}, ponte)
    assert ponte.chamadas == [("navegacao.interna.set", {"ligada": True, "origin": "manual"})]


def test_20_o_gesto_e_o_mesmo_em_todas_as_dez_abas() -> None:
    pac = _pacotes()
    atendentes = {inspect.unwrap(g)
                  for g in (pac.gesto_da_pagina(aba, "travar-navegacao") for aba in DEZ)}
    assert len(atendentes) == 1 and None not in atendentes, atendentes
    assert ("*", "travar-navegacao") in pac.GESTOS
    assert not any(p != "*" and g == "travar-navegacao" for p, g in pac.GESTOS), (
        "o botão tem um escritor só: um segundo gesto por aba seria uma segunda flag")


def test_21_sem_o_bloco_do_daemon_o_gesto_recusa_em_vez_de_chutar() -> None:
    pac = _pacotes()
    travar = pac.gesto_da_pagina("06-navegacao.html", "travar-navegacao")
    ponte = _Ponte()
    with pytest.raises(RuntimeError, match="não respondeu"):
        travar(_contexto(pac), {}, ponte)
    assert ponte.chamadas == []


def test_22_o_daemon_que_cai_ou_recusa_deixa_a_navegacao_como_estava() -> None:
    pac = _pacotes()
    travar = pac.gesto_da_pagina("06-navegacao.html", "travar-navegacao")
    ctx = _contexto(pac, interna_ligada=True, tipo="interna")
    with pytest.raises(RuntimeError, match="como estava"):
        travar(ctx, {}, _Ponte(cai=True))
    with pytest.raises(RuntimeError, match="como estava"):
        travar(ctx, {}, _Ponte({"status": "erro"}))


def test_23_o_gesto_declara_o_que_grava() -> None:
    pac = _pacotes()
    assert pac.GESTOS_QUE_MEXEM[("*", "travar-navegacao")] == "navegacao.interna.set"


def test_24_no_nativo_o_botao_segue_vivo_porque_a_interna_e_da_janela() -> None:
    pac = _pacotes()
    estado = {"active_profile": "Régua", "navegacao": {"interna_ligada": True}}
    for aba in DEZ:
        assert pac.camada.recusa_no_nativo(aba, "travar-navegacao", estado) is None, aba
    assert frozenset({"travar-navegacao"}) == pac.camada.GESTOS_DA_MOLDURA


def test_25_o_topo_pinta_o_botao_apertado_so_quando_o_daemon_diz_travada() -> None:
    pac = _pacotes()
    campo = "navegacao-travada"
    assert pac.topo(_contexto(pac, interna_ligada=False, tipo="interna"))[campo] == "true"
    assert pac.topo(_contexto(pac, interna_ligada=True, tipo="interna"))[campo] == "false"
    assert pac.topo(_contexto(pac))[campo] == "false", "sem o bloco do daemon, o botão fica solto"


def test_26_a_moldura_traz_o_botao_pintado_pelo_campo_e_aciona_o_gesto() -> None:
    topo = (INTERFACE / "topo.html").read_text(encoding="utf-8")
    assert topo.count('data-gesto="travar-navegacao"') == 1
    assert 'data-campo="navegacao-travada"' in topo
    assert 'data-hef-atributo="aria-pressed"' in topo
    assert 'aria-label="Travar navegação"' in topo, "só o cadeado: o nome mora no aria-label"
    pac = _pacotes()
    assert "navegacao-travada" in pac.topo(_contexto(pac))


@pytest.mark.parametrize("aba", DEZ)
def test_27_o_desenho_de_toda_aba_traz_o_botao(aba: str) -> None:
    raiz = Path(hefesto_dualsense4unix.__file__).resolve().parents[2]
    pagina = (raiz / "mockup" / aba).read_text(encoding="utf-8")
    assert pagina.count('data-gesto="travar-navegacao"') == 1, (
        f"{aba} sem o botão da moldura (regere a aba: o topo.html entra por ela)")
