"""O controle livre ganha os modos «Soltar», «Segurar» e «Repetir».

O-LIVRE-GANHA-OS-MODOS-SOLTAR-SEGURAR-REPETIR-01 (24/10/2026). A opção ``livre`` do manifesto
aceita ``modos: true``; com ele, ``extensao.livre`` e ``mods.livre`` levam ``modo``, um de
``soltar``, ``segurar`` e ``repetir`` (``soltar`` por padrão), e sem ele o campo não vai. A janela
desenha os três botões na faixa só com ``modos``; o clique vai ao rascunho (quem grava é o
Guardar) e vale na hora: «Soltar» volta a barra a zero, «Segurar» a deixa onde parou e «Repetir»
toca em laço o trecho do último arrastar.

A matriz: com e sem ``modos``, os três modos e duas extensões na porta de verdade (o modo de uma
não chega à outra).

MORDIDAS (24/10/2026, executadas sobre a cura e devolvidas):

- o ``dados["modo"]`` tirado do ``Porta.livre`` reprova
  ``test_a_porta_leva_o_modo_so_a_extensao_dona`` (os três modos);
- o zero do «Soltar» tirado do ``_soltar_no_modo`` reprova
  ``test_soltar_volta_a_zero_segurar_fica_e_repetir_toca_o_trecho[soltar]``;
- o ``modo`` tirado do ``mods.livre`` que o arrastar da janela manda reprova
  ``test_o_clique_no_modo_acende_vai_ao_rascunho_e_o_guardar_grava`` (os três modos).
"""

from __future__ import annotations

import asyncio
import json
import pathlib
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.mods.manifesto import (
    MODOS_DO_LIVRE,
    Manifesto,
    ManifestoRecusadoError,
    ler_manifesto,
)
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import ctx, lar  # noqa: F401
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import (  # noqa: F401
    _entrar,
    _porta,
    curto,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    LIVRE,
    VIVO,
    _guardar_a_mao,
    _instalada,
    _lugares_de,
    _manifesto,
    _Ponte,
    _servico,
    janela,
)

COM_MODOS = {**LIVRE, "modos": True}


def _com(livre: dict[str, Any]) -> dict[str, Any]:
    return {"opcoes": [dict(livre)]}  # noqa-acento: chave do manifesto


# -- 1. o manifesto ---------------------------------------------------------------------------


def test_o_livre_com_modos_valida_e_sem_eles_nasce_sem() -> None:
    assert MODOS_DO_LIVRE == ("soltar", "segurar", "repetir")
    com = Manifesto.model_validate(_manifesto(**_com(COM_MODOS)))
    assert com.opcao_livre is not None and com.opcao_livre.modos is True
    sem = Manifesto.model_validate(_manifesto(**_com(LIVRE)))
    assert sem.opcao_livre is not None and sem.opcao_livre.modos is False


@pytest.mark.parametrize(("peca", "frase"), [
    ({"id": "ligado", "rotulo": "Ligado", "tipo": "ligado", "modos": True},
     "não é livre e declara modos"),
    ({**LIVRE, "modos": "sim"}, "modos"),
])
def test_modos_fora_do_livre_ou_que_nao_e_sim_ou_nao_e_recusado(
        tmp_path: pathlib.Path, peca: dict[str, Any], frase: str) -> None:
    (tmp_path / "hefesto-mod.json").write_text(json.dumps(_manifesto(**_com(peca))),
                                               encoding="utf-8")
    with pytest.raises(ManifestoRecusadoError) as recusa:
        ler_manifesto(tmp_path)
    assert frase in recusa.value.frase, recusa.value.frase


# -- 2. a porta: o modo vai só à extensão dona ------------------------------------------------


@pytest.mark.parametrize("modo", [*MODOS_DO_LIVRE, None])
def test_a_porta_leva_o_modo_so_a_extensao_dona(curto: pathlib.Path, modo: str | None) -> None:  # noqa: F811
    # D-2410-A-EXTENSAO-DECLARA-ACOES-E-O-CLIQUE-VAI-SO-A-ELA
    async def corrida() -> tuple[Any, Any, Any]:
        porta = await _porta(curto, EventBus())
        a = await _entrar(curto, "ficha-a", {"ligado": True})
        b = await _entrar(curto, "ficha-b", {"ligado": True})
        try:
            assert porta.livre("acessorios", "ao-vivo", 0.4, soltou=True, modo=modo) is True
            chegou = await asyncio.to_thread(a.esperar_evento, 2.0)
            assert porta.livre("outra", "ao-vivo", 0.7, soltou=True) is True
            da_outra = await asyncio.to_thread(b.esperar_evento, 2.0)
            vazou = await asyncio.to_thread(a.esperar_evento, 0.3)
            return chegou, da_outra, vazou
        finally:
            a.fechar()
            b.fechar()
            await porta.parar()

    chegou, da_outra, vazou = asyncio.run(corrida())
    assert chegou is not None and chegou["params"]["nome"] == "extensao.livre"
    esperado = {"mod": "acessorios", "id": "ao-vivo", "valor": 0.4, "soltou": True}
    assert chegou["params"]["dados"] == ({**esperado, "modo": modo} if modo else esperado)
    assert da_outra is not None and "modo" not in da_outra["params"]["dados"], (
        f"o modo de uma extensão chegou à outra: {da_outra}")
    assert vazou is None, f"o soltar da outra extensão chegou à dona: {vazou}"


# -- 3. o IPC: o modo só com ``modos`` --------------------------------------------------------


def _arrastar(lar: Any, livre: dict[str, Any]) -> tuple[Any, list[tuple[Any, ...]]]:  # noqa: F811
    _instalada(lar, **_com(livre))
    arrastou: list[tuple[Any, ...]] = []

    def porta_livre(mod: str, i: str, v: float, *, soltou: bool, **modo: Any) -> bool:
        arrastou.append((mod, i, v, soltou, modo))
        return True

    from types import SimpleNamespace

    servico = _servico(SimpleNamespace(lugares=lar, porta=SimpleNamespace(livre=porta_livre)))

    def pedir(**params: Any) -> Any:
        return asyncio.run(IpcHandlersMixin._handle_mods_livre(
            servico, {"mod": "toque", "id": "ao-vivo", "valor": 0.5, **params}))

    return pedir, arrastou


def test_o_ipc_com_modos_leva_o_modo_e_o_padrao_e_soltar(lar: Any) -> None:  # noqa: F811
    pedir, arrastou = _arrastar(lar, COM_MODOS)
    for modo in MODOS_DO_LIVRE:
        assert pedir(soltou=True, modo=modo) == {"enviado": True}
    assert pedir() == {"enviado": True}
    with pytest.raises(ValueError, match="soltar, segurar ou repetir"):
        pedir(modo="pular")
    assert [m for *_x, m in arrastou] == [{"modo": "soltar"}, {"modo": "segurar"},
                                          {"modo": "repetir"}, {"modo": "soltar"}]


def test_o_ipc_sem_modos_nao_leva_modo_e_recusa_o_que_chega(lar: Any) -> None:  # noqa: F811
    pedir, arrastou = _arrastar(lar, LIVRE)
    assert pedir(soltou=True) == {"enviado": True}
    with pytest.raises(ValueError, match="não declara os modos do controle livre"):
        pedir(modo="segurar")
    assert arrastou == [("toque", "ao-vivo", 0.5, True, {})], arrastou


# -- 4. as opções: o modo guardado, lido e herdado --------------------------------------------


def test_o_modo_se_le_com_padrao_e_o_torto_volta_a_soltar(tmp_path: pathlib.Path) -> None:
    from hefesto_dualsense4unix.mods import opcoes

    manifesto = Manifesto.model_validate(_manifesto(**_com(COM_MODOS)))
    lugares = _lugares_de(tmp_path)
    assert opcoes.ler(manifesto, lugares)["ao-vivo:modo"] == "soltar"
    for torto in ("pular", 3, None):
        _guardar_a_mao(lugares, "toque", {"ao-vivo:modo": torto})
        assert opcoes.ler(manifesto, lugares)["ao-vivo:modo"] == "soltar"
    assert opcoes.guardar(manifesto, "ao-vivo:modo", "repetir", lugares) == "repetir"
    assert opcoes.ler(manifesto, lugares)["ao-vivo:modo"] == "repetir"
    sem = Manifesto.model_validate(_manifesto(**_com(LIVRE)))
    assert "ao-vivo:modo" not in opcoes.ler(sem, lugares), "o livre sem modos ganhou modo"


def test_a_extensao_que_substitui_herda_o_modo(tmp_path: pathlib.Path) -> None:
    from hefesto_dualsense4unix.mods import opcoes

    manifesto = Manifesto.model_validate(_manifesto(**_com(COM_MODOS)))
    lugares = _lugares_de(tmp_path)
    _guardar_a_mao(lugares, "velha", {"ao-vivo:modo": "segurar"})
    assert opcoes.herdar(manifesto, ["velha"], lugares).get("ao-vivo:modo") == "segurar"
    assert opcoes.ler(manifesto, lugares)["ao-vivo:modo"] == "segurar"


# -- 5. a janela ------------------------------------------------------------------------------


def _modos_na_faixa(html: str) -> dict[str, bool]:
    """Os botões de modo que a faixa desenhou, e se cada um está aceso."""
    grupo = re.search(r'<span class="seg mj-modos"[^>]*>(.*?)</span>', html, re.S)
    if grupo is None:
        return {}
    return {m.group(2): bool(m.group(1)) for m in re.finditer(
        r'<button( class="on")? data-modo="(\w+)" data-gesto="modo-do-livre-da-modificacao"',
        grupo.group(1))}


def _mover(a07: Any, ctx: Any, ponte: _Ponte, valor: int, n: int,  # noqa: F811
           mod: str = "toque", evento: str = "input") -> None:
    o = {"v": f"{mod}:ao-vivo", "valor": str(valor), "vivo": str(n), "carimbo": str(n),
         "evento": evento}
    if evento == "input":
        a07.mover_o_livre_da_modificacao(ctx, o, ponte)
    else:
        a07.soltar_o_livre_da_modificacao(ctx, o, ponte)


def _livres(ponte: _Ponte) -> list[dict[str, Any]]:
    return [p for m, p in ponte.chamadas if m == "mods.livre"]


@pytest.mark.parametrize("modo", MODOS_DO_LIVRE)
def test_o_clique_no_modo_acende_vai_ao_rascunho_e_o_guardar_grava(
        janela: Any, ctx: Any, lar: Any, modo: str) -> None:  # noqa: F811
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    a07, instalar, abrir = janela
    instalar(**_com(COM_MODOS))
    ponte = _Ponte(VIVO)
    html = abrir(ponte)["blocos"]["#mod-janela"]
    assert _modos_na_faixa(html) == {"soltar": True, "segurar": False, "repetir": False}
    carga = a07.modo_do_livre_da_modificacao(ctx, {"v": f"toque:ao-vivo:{modo}"}, ponte)
    acesos = _modos_na_faixa(carga["blocos"]["#mod-janela"])
    assert acesos == {m: m == modo for m in MODOS_DO_LIVRE}, acesos
    assert _livres(ponte) == [], "o modo sem arrastar nenhum mandou soltar à extensão"
    guardado: Any = opcoes.ler(manifesto_instalado("toque", lugares=lar), lar)
    assert guardado["ao-vivo:modo"] == "soltar", "o clique gravou antes do Guardar"
    a07.guardar_modificacao(ctx, {"v": "toque"}, ponte)
    guardado = opcoes.ler(manifesto_instalado("toque", lugares=lar), lar)
    assert guardado["ao-vivo:modo"] == modo
    _mover(a07, ctx, ponte, 30, 1)
    _mover(a07, ctx, ponte, 40, 2, evento="change")
    assert [p.get("modo") for p in _livres(ponte)] == [modo, modo], _livres(ponte)


def test_a_extensao_sem_modos_nao_tem_os_botoes_nem_manda_modo(
        janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(**_com(LIVRE))
    instalar("outra", **_com(COM_MODOS))
    ponte = _Ponte(VIVO)
    assert _modos_na_faixa(abrir(ponte)["blocos"]["#mod-janela"]) == {}
    _mover(a07, ctx, ponte, 30, 1)
    _mover(a07, ctx, ponte, 40, 2, evento="change")
    assert all("modo" not in p for p in _livres(ponte)), _livres(ponte)
    with pytest.raises(RuntimeError, match="não tem modos"):
        a07.modo_do_livre_da_modificacao(ctx, {"v": "toque:ao-vivo:segurar"}, ponte)
    assert _modos_na_faixa(abrir(ponte, "outra")["blocos"]["#mod-janela"]) != {}
    with pytest.raises(RuntimeError, match="não é Soltar, Segurar nem Repetir"):
        a07.modo_do_livre_da_modificacao(ctx, {"v": "outra:ao-vivo:pular"}, ponte)


@pytest.fixture
def relogio(janela: Any, monkeypatch: pytest.MonkeyPatch) -> list[float]:  # noqa: F811
    """O relógio do ``_Viva``, na mão do teste."""
    agora = [1000.0]
    monkeypatch.setattr(janela[0].time, "monotonic", lambda: agora[0])
    return agora


def _arrastar_e_soltar(a07: Any, ctx: Any, ponte: _Ponte, relogio: list[float]) -> None:  # noqa: F811
    """De 0 a 100 em três passos de 0,1 s, e o soltar no 100."""
    for n, valor in enumerate((0, 50, 100), start=1):
        _mover(a07, ctx, ponte, valor, n)
        relogio[0] += 0.1
    _mover(a07, ctx, ponte, 100, 4, evento="change")


@pytest.mark.parametrize("modo", MODOS_DO_LIVRE)
def test_soltar_volta_a_zero_segurar_fica_e_repetir_toca_o_trecho(
        janela: Any, ctx: Any, relogio: list[float], modo: str) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(**_com(COM_MODOS))
    ponte = _Ponte(VIVO)
    abrir(ponte)
    a07.modo_do_livre_da_modificacao(ctx, {"v": f"toque:ao-vivo:{modo}"}, ponte)
    _arrastar_e_soltar(a07, ctx, ponte, relogio)
    vistos = []
    for _ in range(12):
        relogio[0] += 0.05
        vistos.append(a07._VIVA.ao_vivo("toque").valor)
    if modo == "soltar":
        assert set(vistos) == {0.0}, f"o «Soltar» não voltou a zero: {vistos}"
    elif modo == "segurar":
        assert set(vistos) == {1.0}, f"o «Segurar» não ficou onde parou: {vistos}"
    else:
        assert set(vistos) == {0.0, 0.5, 1.0}, f"o «Repetir» não tocou o trecho: {vistos}"
    soltou = _livres(ponte)[-1]
    assert soltou["soltou"] is True and soltou["modo"] == modo and soltou["valor"] == 1.0


def test_o_repetir_curto_demais_fica_como_o_segurar(
        janela: Any, ctx: Any, relogio: list[float]) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(**_com(COM_MODOS))
    ponte = _Ponte(VIVO)
    abrir(ponte)
    a07.modo_do_livre_da_modificacao(ctx, {"v": "toque:ao-vivo:repetir"}, ponte)
    _mover(a07, ctx, ponte, 70, 1)
    relogio[0] += a07.LACO_MINIMO_S / 2
    _mover(a07, ctx, ponte, 70, 2, evento="change")
    relogio[0] += 1.0
    assert a07._VIVA.ao_vivo("toque").valor == 0.7


def test_trocar_o_modo_depois_do_arrastar_vale_na_hora(
        janela: Any, ctx: Any, relogio: list[float]) -> None:  # noqa: F811
    """O «Repetir» em laço vira «Soltar»: a barra volta a zero e a extensão recebe o soltar com o
    modo novo; o «Segurar» depois deixa a barra no zero."""
    a07, instalar, abrir = janela
    instalar(**_com(COM_MODOS))
    ponte = _Ponte(VIVO)
    abrir(ponte)
    a07.modo_do_livre_da_modificacao(ctx, {"v": "toque:ao-vivo:repetir"}, ponte)
    _arrastar_e_soltar(a07, ctx, ponte, relogio)
    relogio[0] += 0.15
    antes = len(_livres(ponte))
    a07.modo_do_livre_da_modificacao(ctx, {"v": "toque:ao-vivo:soltar"}, ponte)
    troca = _livres(ponte)[antes:]
    assert len(troca) == 1 and troca[0]["soltou"] is True and troca[0]["modo"] == "soltar"
    assert troca[0]["valor"] == 0.5, "a troca não levou o valor de agora do laço"
    relogio[0] += 0.5
    assert a07._VIVA.ao_vivo("toque").valor == 0.0, "o laço continuou depois do «Soltar»"
    a07.modo_do_livre_da_modificacao(ctx, {"v": "toque:ao-vivo:soltar"}, ponte)
    assert len(_livres(ponte)) == antes + 1, "o mesmo modo de novo mandou outro soltar"


def test_o_gesto_do_modo_esta_declarado_sem_eco() -> None:
    import sys

    from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import _o_pacote

    a07 = _o_pacote()
    assert "modo-do-livre-da-modificacao" in a07.SEM_ECO
    sys.path.insert(0, str(pathlib.Path(a07.__file__).parent))
    from hefesto_dualsense4unix.interface import pacotes

    pacotes._carregar_tudo()
    assert ("07-lancadores.html", "modo-do-livre-da-modificacao") in pacotes.GESTOS
