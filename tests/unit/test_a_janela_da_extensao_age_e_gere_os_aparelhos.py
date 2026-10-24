"""A janela da extensão age, gere os aparelhos e tem o controle livre.

A-JANELA-DA-EXTENSAO-GANHA-ACAO-APARELHOS-E-CONTROLE-LIVRE-01 (24/10/2026). O manifesto declara as
ações da janela, as ações de cada aparelho gerido e a opção ``livre``; o clique vai por
``mods.acao`` e o arrastar por ``mods.livre`` só à extensão dona, e a forma gravada no livre entra
na escolha dos botões daquela extensão e de nenhuma outra.

MORDIDAS (24/10/2026, executadas sobre a cura e devolvidas):

- o ``:alvo`` tirado do ``data-v`` do botão do aparelho reprova
  ``test_quatro_aparelhos_viram_quatro_linhas_e_o_testar_leva_o_alvo``;
- o compasso da porta solto (1000 por segundo no lugar de 20) reprova
  ``test_arrastar_um_segundo_sai_em_no_maximo_vinte_e_o_ultimo_e_o_soltar``.
"""

from __future__ import annotations

import asyncio
import copy
import functools
import json
import pathlib
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.mods.manifesto import (
    Manifesto,
    ManifestoRecusadoError,
    ler_manifesto,
)
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    _a07,
    _fonte,
    _instalar,
    ctx,
    lar,
)
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import (  # noqa: F401
    GESTO,
    _entrar,
    _porta,
    curto,
)

ESTADO = "publicar:acessorios.estado"
APARELHOS = [
    {"id": f"ap-{n}", "nome": f"Aparelho {n}", "estado": "ligado", "ligado": n != 4,
     "bateria": 20 * n, "forca": n / 10}
    for n in range(1, 5)
]
VIVO = {"ligado": True, "nivel": 3, "perfil": "Ondas", "aparelhos": APARELHOS, "serie": 1}
ACOES_DOS_APARELHOS = [{"id": "ligar", "rotulo": "Ligar", "icone": "ligar"},
                       {"id": "testar", "rotulo": "Testar", "icone": "testar"}]
TOQUES = {"id": "toques", "rotulo": "Toque de cada botão", "tipo": "por_botao",
          "grupo": "Toques", "botoes": ["cross", "circle"],
          "formas": {"Pulso": [[1.0, 0.2], [0.0, 0.2]], "Sem toque": []}}
LIVRE = {"id": "ao-vivo", "rotulo": "Ao vivo", "tipo": "livre"}


def _manifesto(**extra: Any) -> dict[str, Any]:
    return {"id": "toque", "nome": "Toque", "versao": "0.1", "api": ">=1,<3",  # noqa-acento: chave
            "licenca": "MIT", "tipos": ["tema"], "tema": {},  # noqa-acento: chave
            "permissoes": [ESTADO], **extra}  # noqa-acento: chave do manifesto


def _pecas(grupo: str | None = "Aparelhos") -> dict[str, Any]:
    geridos: dict[str, Any] = {"acoes": copy.deepcopy(ACOES_DOS_APARELHOS)}  # noqa-acento: contrato
    extra: dict[str, Any] = {"acoes": [{"id": "parear", "rotulo": "Parear",  # noqa-acento: contrato
                                        "grupo": "Aparelhos", "icone": "procurar"}],
                             "opcoes": copy.deepcopy([TOQUES, LIVRE])}  # noqa-acento: chave
    if grupo:
        geridos["grupo"] = grupo
    else:
        extra["agora"] = ["nivel", "aparelhos"]
    extra["aparelhos_acoes"] = geridos  # noqa-acento: contrato
    return extra


# -- 1. o manifesto ---------------------------------------------------------------------------


def test_o_manifesto_com_as_tres_pecas_valida() -> None:
    m = Manifesto.model_validate(_manifesto(**_pecas()))
    assert [a.id for a in m.acoes] == ["parear"]
    assert m.aparelhos_acoes is not None and m.aparelhos_acoes.grupo == "Aparelhos"
    assert m.opcao_livre is not None and m.opcao_livre.id == "ao-vivo"
    sem_grupo = Manifesto.model_validate(_manifesto(**_pecas(grupo=None)))
    assert sem_grupo.aparelhos_acoes is not None and sem_grupo.aparelhos_acoes.grupo is None


@pytest.mark.parametrize(("mexer", "frase"), [
    (lambda d: d.update(permissoes=[]),  # noqa-acento: chave do manifesto
     "pede a permissão publicar:acessorios.estado"),
    (lambda d: d["aparelhos_acoes"]["acoes"].append(  # noqa-acento: contrato
        {"id": "x", "rotulo": "X", "grupo": "Outra"}),
     "a ação do aparelho mora no cartão dele e não declara grupo"),
    (lambda d: d["opcoes"].append({**LIVRE, "id": "outro"}),  # noqa-acento: chave
     "mais de uma opção livre"),
    (lambda d: d["acoes"].append({"id": "parear", "rotulo": "De novo"}),  # noqa-acento: contrato
     "ação repetida"),
    (lambda d: d["aparelhos_acoes"].pop("grupo"),  # noqa-acento: contrato
     "agora não lista aparelhos"),
    (lambda d: d["acoes"][0].update(icone="foguete"),  # noqa-acento: contrato
     "acoes.0.icone"),
])
def test_o_manifesto_torto_e_recusado_com_a_frase(tmp_path, mexer, frase) -> None:
    bruto = _manifesto(**_pecas())
    mexer(bruto)
    (tmp_path / "hefesto-mod.json").write_text(json.dumps(bruto), encoding="utf-8")
    with pytest.raises(ManifestoRecusadoError) as recusa:
        ler_manifesto(tmp_path)
    assert frase in recusa.value.frase, recusa.value.frase


# -- 2. a ação chega só à extensão dela -------------------------------------------------------


def test_a_acao_chega_so_a_extensao_dela(curto) -> None:  # noqa: F811
    async def corrida() -> None:
        porta = await _porta(curto, EventBus())
        a = await _entrar(curto, "ficha-a", {"ligado": True})
        b = await _entrar(curto, "ficha-b", {"ligado": True})
        try:
            assert porta.acao("acessorios", "parear") is True
            chegou = await asyncio.to_thread(a.esperar_evento, 2.0)
            assert chegou is not None, "a extensão dona não recebeu a ação"
            assert chegou["params"]["nome"] == "extensao.acao"
            assert chegou["params"]["dados"] == {"mod": "acessorios", "acao": "parear",  # noqa-acento: contrato
                                                 "alvo": None}
            assert porta.acao("acessorios", "ligar", alvo="ap-2", valor=False) is True
            chave = await asyncio.to_thread(a.esperar_evento, 2.0)
            assert chave is not None and chave["params"]["dados"]["alvo"] == "ap-2"
            assert chave["params"]["dados"]["valor"] is False
            vazou = await asyncio.to_thread(b.esperar_evento, 0.4)
            assert vazou is None, f"a outra extensão recebeu a ação: {vazou}"
            assert porta.acao("ninguem", "parear") is False
        finally:
            a.fechar()
            b.fechar()
            await porta.parar()

    asyncio.run(corrida())


def _servico(supervisor: Any) -> Any:
    servico = SimpleNamespace(daemon=SimpleNamespace(_mods_supervisor=supervisor),
                              _mod_do_pedido=IpcHandlersMixin._mod_do_pedido)
    servico._manifesto_da_janela = functools.partial(IpcHandlersMixin._manifesto_da_janela,
                                                     servico)
    return servico


def _instalada(lugares: Any, **extra: Any) -> None:
    pasta = lugares.codigo / "toque"
    pasta.mkdir(parents=True)
    (pasta / "hefesto-mod.json").write_text(json.dumps(_manifesto(**extra)), encoding="utf-8")


def test_o_ipc_da_acao_so_leva_o_que_o_manifesto_declara(lar) -> None:  # noqa: F811
    _instalada(lar, **_pecas())
    enviadas: list[tuple[Any, ...]] = []

    def acao(mod: str, acao: str, *, alvo: str | None = None, valor: bool | None = None) -> bool:
        enviadas.append((mod, acao, alvo, valor))
        return True

    sup = SimpleNamespace(lugares=lar, porta=SimpleNamespace(acao=acao))
    servico = _servico(sup)

    def pedir(**params: Any) -> Any:
        return asyncio.run(IpcHandlersMixin._handle_mods_acao(servico, {"mod": "toque", **params}))

    def arrastar(**params: Any) -> Any:
        return asyncio.run(IpcHandlersMixin._handle_mods_livre(servico, {"mod": "toque", **params}))

    assert pedir(acao="parear") == {"enviada": True}
    assert pedir(acao="testar", alvo="ap-3") == {"enviada": True}
    assert pedir(acao="ligar", alvo="ap-4", valor=True) == {"enviada": True}
    assert enviadas == [("toque", "parear", None, None), ("toque", "testar", "ap-3", None),
                        ("toque", "ligar", "ap-4", True)]
    with pytest.raises(ValueError, match="não declara a ação «testar» na janela"):
        pedir(acao="testar")
    with pytest.raises(ValueError, match="não declara a ação «parear» nos aparelhos"):
        pedir(acao="parear", alvo="ap-1")
    with pytest.raises(ValueError, match="alvo"):
        pedir(acao="testar", alvo="x" * 41)
    assert len(enviadas) == 3, "um pedido recusado chegou à porta"
    arrastou: list[tuple[Any, ...]] = []
    sup.porta.livre = lambda mod, i, v, *, soltou: arrastou.append((mod, i, v, soltou)) or True
    assert arrastar(id="ao-vivo", valor=0.5) == {"enviado": True}
    with pytest.raises(ValueError, match="não declara o controle livre «outro»"):
        arrastar(id="outro", valor=0.5)
    with pytest.raises(ValueError, match="de 0 a 1"):
        arrastar(id="ao-vivo", valor=1.5)
    assert arrastou == [("toque", "ao-vivo", 0.5, False)]
    sem = asyncio.run(IpcHandlersMixin._handle_mods_acao(_servico(None), {"mod": "toque",
                                                                         "acao": "parear"}))  # noqa-acento: contrato
    assert sem == {"enviada": False}


# -- a janela -----------------------------------------------------------------------------


class _Ponte:
    """O ``p`` do gesto: ``mods.agora`` devolve o estado do teste e o resto é anotado."""

    def __init__(self, estado: dict[str, Any] | None = None, *, rodando: bool = True) -> None:
        self.estado = dict(estado or {})
        self.rodando = rodando
        self.chamadas: list[tuple[str, dict[str, Any]]] = []

    def resultado(self, metodo: str, **params: Any) -> Any:
        if metodo == "mods.agora":
            return {"mod": params.get("mod"), **self.estado}
        self.chamadas.append((metodo, params))
        return None

    def chamar_com_o_corpo(self, metodo: str, **params: Any) -> tuple[bool, str | None, Any]:
        self.chamadas.append((metodo, params))
        chave = "enviada" if metodo == "mods.acao" else "enviado"  # noqa-acento: contrato
        return True, None, {chave: self.rodando}

    def escolher_arquivo(self, *_: Any, **__: Any) -> str | None:
        return None


@pytest.fixture
def janela(lar, ctx, tmp_path, monkeypatch):  # noqa: F811
    """Instala extensões de tema com as peças e abre a janela de uma delas."""
    a07 = _a07()
    monkeypatch.setattr(a07, "_AGORA", a07._Agora())
    monkeypatch.setattr(a07, "_VIVA", a07._Viva())

    def instalar(mod_id: str = "toque", **extra: Any) -> None:
        _instalar(a07, ctx, _fonte(tmp_path, mod_id, nome=mod_id.title(),
                                   permissoes=(ESTADO,), extra=extra))

    def abrir(ponte: _Ponte, mod_id: str = "toque") -> dict[str, Any]:
        return a07.configurar_modificacao(ctx, {"v": mod_id}, ponte)

    return a07, instalar, abrir


def _data_v_do_testar(html: str, alvo: str) -> str:
    import re

    cartao = re.search(rf'data-alvo="{alvo}".*?(?=data-alvo="|$)', html, re.S)
    assert cartao, f"o aparelho {alvo} não tem cartão nem linha"
    botao = re.search(r'data-gesto="acao-da-modificacao" data-v="([^"]+:testar[^"]*)"',
                      cartao.group(0))
    assert botao, f"o aparelho {alvo} não tem o botão Testar"
    return botao.group(1)


@pytest.mark.parametrize("onde", ["aba", "coluna"])
@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_quatro_aparelhos_viram_quatro_linhas_e_o_testar_leva_o_alvo(janela, ctx, onde,  # noqa: F811
                                                                    n) -> None:
    """A matriz: a lista na aba do ``grupo`` ou na coluna «Agora», e o «Testar» de cada um dos
    quatro aparelhos (um deles desligado) leva o ``alvo`` dele, e só o dele."""
    a07, instalar, abrir = janela
    instalar(**_pecas(grupo="Aparelhos" if onde == "aba" else None))
    ponte = _Ponte(VIVO)
    carga = abrir(ponte)
    html = carga["blocos"]["#mod-janela"]
    if onde == "aba":
        assert html.count(" data-alvo=") == 4, "quatro aparelhos com id, quatro cartões"
        assert html.count('<div class="mj-ap fora"') == 1, "o desligado fica apagado"
        assert "#mod-aparelhos" in carga["blocos"], "o tique não repinta a lista"
    else:
        coluna = carga["blocos"]["#mod-agora"]
        assert coluna.count('class="ap mj-ap-linha') == 4, "quatro aparelhos, quatro linhas"
        assert f'data-dica="Aparelho {n}"' in coluna, "o nome cortado na coluna se lê na dica"
        html = coluna
    assert html.count('role="switch"') == 4, "cada aparelho tem a chave"
    data_v = _data_v_do_testar(html, f"ap-{n}")
    a07.acao_da_modificacao(ctx, {"v": data_v}, ponte)
    feitas = [p for m, p in ponte.chamadas if m == "mods.acao"]
    assert feitas == [{"mod": "toque", "acao": "testar", "alvo": f"ap-{n}"}], feitas  # noqa-acento: contrato


def test_a_chave_do_aparelho_pede_o_contrario_e_o_botao_diz_em_curso(janela, ctx) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(VIVO)
    abrir(ponte)
    a07.acao_da_modificacao(ctx, {"v": "toque:ligar:ap-4", "ligado": "1"}, ponte)
    a07.acao_da_modificacao(ctx, {"v": "toque:ligar:ap-1", "ligado": "0"}, ponte)
    a07.acao_da_modificacao(ctx, {"v": "toque:parear"}, ponte)
    feitas = [p for m, p in ponte.chamadas if m == "mods.acao"]
    assert feitas[0]["valor"] is True and feitas[1]["valor"] is False
    assert "alvo" not in feitas[2] and "valor" not in feitas[2]
    a07._AGORA.ler("toque", ponte)
    blocos = a07._com_os_aparelhos({"blocos": {}})["blocos"]
    assert "Em curso" in blocos["#mod-acoes-0"], "o «Parear» não diz que espera a extensão"
    assert blocos["#mod-aparelhos"].count("em-curso") == 2, "as duas chaves clicadas esperam"
    ponte.estado["serie"] = 2
    a07._AGORA.ler("toque", ponte)
    blocos = a07._com_os_aparelhos({"blocos": {}})["blocos"]
    assert "Em curso" not in blocos["#mod-acoes-0"], "o estado novo não tirou o «Em curso»"
    assert "em-curso" not in blocos["#mod-aparelhos"]


def test_a_acao_da_extensao_parada_recusa_dizendo(janela, ctx) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(VIVO, rodando=False)
    abrir(ponte)
    with pytest.raises(RuntimeError, match="não está rodando"):
        a07.acao_da_modificacao(ctx, {"v": "toque:parear"}, ponte)


# -- 4. o arrastar ----------------------------------------------------------------------------


def test_arrastar_um_segundo_sai_em_no_maximo_vinte_e_o_ultimo_e_o_soltar(curto) -> None:  # noqa: F811
    async def corrida() -> list[dict[str, Any]]:
        porta = await _porta(curto, EventBus())
        a = await _entrar(curto, "ficha-a", {"ligado": True})
        b = await _entrar(curto, "ficha-b", {"ligado": True})
        try:
            for n in range(60):
                porta.livre("acessorios", "ao-vivo", n / 59, soltou=n == 59)
                await asyncio.sleep(1 / 60)
            await asyncio.sleep(0.3)
            chegaram = []
            while (evento := await asyncio.to_thread(a.esperar_evento, 0.2)) is not None:
                chegaram.append(evento["params"])
            vazou = await asyncio.to_thread(b.esperar_evento, 0.2)
            assert vazou is None, f"a outra extensão recebeu o arrastar: {vazou}"
            return chegaram
        finally:
            a.fechar()
            b.fechar()
            await porta.parar()

    chegaram = asyncio.run(corrida())
    assert {c["nome"] for c in chegaram} == {"extensao.livre"}
    assert 5 <= len(chegaram) <= 20, f"{len(chegaram)} eventos num segundo de arrastar"
    ultimo = chegaram[-1]["dados"]
    assert ultimo == {"mod": "acessorios", "id": "ao-vivo", "valor": 1.0, "soltou": True}
    assert not any(c["dados"]["soltou"] for c in chegaram[:-1])


def test_o_arrastar_fora_de_ordem_cai_e_o_soltar_sempre_sai(janela, ctx) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(VIVO)
    abrir(ponte)

    def mover(valor: int, vivo: int, carimbo: float) -> None:
        resposta = a07.mover_o_livre_da_modificacao(
            ctx, {"v": "toque:ao-vivo", "valor": str(valor), "vivo": str(vivo),
                  "carimbo": str(carimbo), "evento": "input"}, ponte)
        assert resposta == {}, "o gesto vivo pintou"

    mover(30, 5, 100.0)
    mover(10, 4, 99.0)
    a07.soltar_o_livre_da_modificacao(
        ctx, {"v": "toque:ao-vivo", "valor": "40", "carimbo": "120", "evento": "change"}, ponte)
    mover(90, 6, 110.0)
    assert a07.soltar_o_livre_da_modificacao(
        ctx, {"v": "toque:ao-vivo", "valor": "40", "evento": "click"}, ponte) is None
    feitas = [(p["valor"], p["soltou"]) for m, p in ponte.chamadas if m == "mods.livre"]
    assert feitas == [(0.3, False), (0.4, True)], feitas


# -- 5. a forma gravada -----------------------------------------------------------------------


def _gravar(a07: Any, ctx: Any, ponte: _Ponte, mod_id: str = "toque") -> dict[str, Any]:  # noqa: F811
    a07.gravar_o_livre_da_modificacao(ctx, {"v": f"{mod_id}:ao-vivo"}, ponte)
    for n, valor in enumerate((20, 80, 50)):
        a07.mover_o_livre_da_modificacao(
            ctx, {"v": f"{mod_id}:ao-vivo", "valor": str(valor), "vivo": str(n + 1),
                  "carimbo": str(n + 1)}, ponte)
    return a07.gravar_o_livre_da_modificacao(ctx, {"v": f"{mod_id}:ao-vivo"}, ponte)


def test_a_forma_gravada_entra_nos_botoes_da_mesma_extensao_e_nao_na_outra(janela, ctx,  # noqa: F811
                                                                          lar) -> None:  # noqa: F811
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    a07, instalar, abrir = janela
    instalar(**_pecas())
    instalar("outra", **_pecas())
    ponte = _Ponte(VIVO)
    abrir(ponte)
    carga = _gravar(a07, ctx, ponte)
    assert "«Meu 1» gravada" in carga["recado"]
    html = carga["blocos"]["#mod-janela"]
    assert "<option>Meu 1</option>" in html, "a forma gravada não entrou na escolha do botão"
    assert 'data-v="toque:ao-vivo:Meu 1"' in html, "a forma gravada não tem o «x» de esquecer"
    a07.guardar_opcao_da_modificacao(
        ctx, {"v": "toque:toques:circle", "valor": "Meu 1", "evento": "change"}, ponte)
    a07.guardar_modificacao(ctx, {"v": "toque"}, ponte)
    toque = opcoes.ler(manifesto_instalado("toque", lugares=lar), lar)
    assert toque["toques"]["circle"] == "Meu 1"
    assert set(toque["ao-vivo"]) == {"Meu 1"} and len(toque["ao-vivo"]["Meu 1"]) <= 16

    outra = abrir(ponte, "outra")["blocos"]["#mod-janela"]
    assert "Meu 1" not in outra, "a forma de uma extensão apareceu na janela da outra"
    with pytest.raises(RuntimeError, match="forma declarada"):
        a07.guardar_opcao_da_modificacao(
            ctx, {"v": "outra:toques:circle", "valor": "Meu 1", "evento": "change"}, ponte)


def test_esquecer_a_forma_devolve_o_botao_ao_padrao(janela, ctx, lar) -> None:  # noqa: F811
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(VIVO)
    abrir(ponte)
    _gravar(a07, ctx, ponte)
    a07.guardar_opcao_da_modificacao(
        ctx, {"v": "toque:toques:cross", "valor": "Meu 1", "evento": "change"}, ponte)
    a07.guardar_modificacao(ctx, {"v": "toque"}, ponte)
    carga = a07.esquecer_a_forma_do_livre(ctx, {"v": "toque:ao-vivo:Meu 1"}, ponte)
    assert "Meu 1" not in carga["blocos"]["#mod-janela"].replace("«Meu 1»", "")
    a07.guardar_modificacao(ctx, {"v": "toque"}, ponte)
    valores = opcoes.ler(manifesto_instalado("toque", lugares=lar), lar)
    assert valores["ao-vivo"] == {} and valores["toques"]["cross"] == "Pulso"


def test_gravar_sem_arrastar_nao_cria_forma(janela, ctx) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(VIVO)
    abrir(ponte)
    a07.gravar_o_livre_da_modificacao(ctx, {"v": "toque:ao-vivo"}, ponte)
    carga = a07.gravar_o_livre_da_modificacao(ctx, {"v": "toque:ao-vivo"}, ponte)
    assert "Nada foi arrastado" in carga["recado"]
    assert "<option>Meu 1</option>" not in carga["blocos"]["#mod-janela"]


def test_os_passos_da_gravacao_cabem_na_forma() -> None:
    from hefesto_dualsense4unix.mods.manifesto import forma_valida

    a07 = _a07()
    amostras = [(0.0, 0.0)] + [(t / 10, (t % 7) / 6) for t in range(1, 2000)] + [(200.0, 0.5)]
    passos = a07.passos_da_gravacao(amostras)
    assert 1 <= len(passos) <= 16 and forma_valida("Meu 1", passos)
    assert sum(s for _f, s in passos) == pytest.approx(160.0, abs=0.2), "o teto é 160 s"
    curta = a07.passos_da_gravacao([(0.0, 0.0), (0.5, 1.0), (1.0, 1.0)])
    assert curta == [[0.0, 0.5], [1.0, 0.5]]
    assert a07.passos_da_gravacao([(0.0, 0.3), (2.0, 0.3)]) == []


def test_os_gestos_e_os_metodos_estao_declarados() -> None:
    import sys

    a07 = _a07()
    assert {"mods.acao", "mods.livre"} <= a07.METODOS  # noqa-acento: contrato
    novos = ("acao-da-modificacao", "mover-o-livre-da-modificacao",
             "soltar-o-livre-da-modificacao", "gravar-o-livre-da-modificacao",
             "esquecer-a-forma-do-livre")
    assert set(novos) <= set(a07.SEM_ECO)
    sys.path.insert(0, str(pathlib.Path(a07.__file__).parent))
    from hefesto_dualsense4unix.interface import pacotes

    pacotes._carregar_tudo()
    assert all(("07-lancadores.html", g) in pacotes.GESTOS for g in novos)
    assert ("07-lancadores.html", "mover-o-livre-da-modificacao") not in pacotes.GESTOS_QUE_MEXEM, (
        "o gesto vivo declarou gravação: a quarta porta o recusaria")
