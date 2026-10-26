"""A janela da extensão age, gere os aparelhos e tem o controle livre.

A-JANELA-DA-EXTENSAO-GANHA-ACAO-APARELHOS-E-CONTROLE-LIVRE-01 (24/10/2026). O manifesto declara as
ações da janela, as ações de cada aparelho gerido e a opção ``livre``; o clique vai por
``mods.acao`` e o arrastar por ``mods.livre`` só à extensão dona, e a forma gravada no livre entra
na escolha dos botões daquela extensão e de nenhuma outra.

MORDIDAS (24/10/2026, executadas sobre a cura e devolvidas):

- o ``:alvo`` tirado do ``data-v`` do botão do aparelho reprova
  ``test_quatro_aparelhos_viram_quatro_linhas_e_o_testar_leva_o_alvo``;
- o compasso da porta solto (1000 por segundo no lugar de 20) reprova
  ``test_arrastar_um_segundo_sai_em_no_maximo_vinte_e_o_ultimo_e_o_soltar``;
- o teto do «Em curso» tirado da conta do ``esperando`` reprova
  ``test_o_em_curso_sai_no_teto_mesmo_sem_a_serie_subir``;
- o ``aria-pressed`` tirado do «Gravar» reprova
  ``test_o_gravar_aceso_continua_gravar_e_se_diz_apertado``;
- a chave desenhada pedindo o mesmo estado (``data-ligado`` invertido) reprova
  ``test_a_chave_do_aparelho_pede_o_contrario_e_o_botao_diz_em_curso``.
- o ``isinstance(f, str)`` tirado do filtro do ``ler`` reprova
  ``test_o_botao_editado_a_mao_com_forma_que_nao_e_texto_cai_no_padrao_sem_levantar`` (o
  ``TypeError`` sobe);
- o ``herdar`` sem as formas do ``livre`` reprova
  ``test_a_extensao_que_substitui_herda_o_botao_com_a_forma_gravada``.
"""

from __future__ import annotations

import asyncio
import copy
import functools
import json
import pathlib
from types import SimpleNamespace
from collections.abc import Callable
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

_o_pacote: Callable[[], Any] = _a07
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
    return {"id": "toque", "nome": "Toque", "versao": "0.1", "api": ">=1,<3",  # (noqa-acento)
            "licenca": "MIT", "tipos": ["tema"], "tema": {},
            "permissoes": [ESTADO], **extra}  # (noqa-acento)


def _pecas(grupo: str | None = "Aparelhos") -> dict[str, Any]:
    geridos: dict[str, Any] = {"acoes": copy.deepcopy(ACOES_DOS_APARELHOS)}  # (noqa-acento)
    extra: dict[str, Any] = {"acoes": [{"id": "parear", "rotulo": "Parear",  # (noqa-acento)
                                        "grupo": "Aparelhos", "icone": "procurar"}],
                             "opcoes": copy.deepcopy([TOQUES, LIVRE])}  # (noqa-acento)
    if grupo:
        geridos["grupo"] = grupo
    else:
        extra["agora"] = ["nivel", "aparelhos"]
    extra["aparelhos_acoes"] = geridos
    return extra


def test_o_manifesto_com_as_tres_pecas_valida() -> None:
    m = Manifesto.model_validate(_manifesto(**_pecas()))
    assert [a.id for a in m.acoes] == ["parear"]
    assert m.aparelhos_acoes is not None and m.aparelhos_acoes.grupo == "Aparelhos"
    assert m.opcao_livre is not None and m.opcao_livre.id == "ao-vivo"
    sem_grupo = Manifesto.model_validate(_manifesto(**_pecas(grupo=None)))
    assert sem_grupo.aparelhos_acoes is not None and sem_grupo.aparelhos_acoes.grupo is None


@pytest.mark.parametrize(("mexer", "frase"), [
    (lambda d: d.update(permissoes=[]),
     "pede a permissão publicar:acessorios.estado"),
    (lambda d: d["aparelhos_acoes"]["acoes"].append(  # (noqa-acento)
        {"id": "x", "rotulo": "X", "grupo": "Outra"}),
     "a ação do aparelho mora no cartão dele e não declara grupo"),
    (lambda d: d["opcoes"].append({**LIVRE, "id": "outro"}),  # (noqa-acento)
     "mais de uma opção livre"),
    (lambda d: d["acoes"].append({"id": "parear", "rotulo": "De novo"}),  # (noqa-acento)
     "ação repetida"),
    (lambda d: d["aparelhos_acoes"].pop("grupo"),
     "agora não lista aparelhos"),
    (lambda d: d["acoes"][0].update(icone="foguete"),  # (noqa-acento)
     "acoes.0.icone"),
])
def test_o_manifesto_torto_e_recusado_com_a_frase(
        tmp_path: pathlib.Path, mexer: Any, frase: str) -> None:
    bruto = _manifesto(**_pecas())
    mexer(bruto)
    (tmp_path / "hefesto-mod.json").write_text(json.dumps(bruto), encoding="utf-8")
    with pytest.raises(ManifestoRecusadoError) as recusa:
        ler_manifesto(tmp_path)
    assert frase in recusa.value.frase, recusa.value.frase


def test_a_acao_chega_so_a_extensao_dela(curto: pathlib.Path) -> None:  # noqa: F811
    """Prova da D-2410-A-EXTENSAO-DECLARA-ACOES-E-O-CLIQUE-VAI-SO-A-ELA."""
    async def corrida() -> None:
        porta = await _porta(curto, EventBus())
        a = await _entrar(curto, "ficha-a", {"ligado": True})
        b = await _entrar(curto, "ficha-b", {"ligado": True})
        try:
            assert porta.acao("acessorios", "parear") is True
            chegou = await asyncio.to_thread(a.esperar_evento, 2.0)
            assert chegou is not None, "a extensão dona não recebeu a ação"
            assert chegou["params"]["nome"] == "extensao.acao"
            assert chegou["params"]["dados"] == {"mod": "acessorios",
                                                 "acao": "parear",  # (noqa-acento)
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
    servico: Any = SimpleNamespace(daemon=SimpleNamespace(_mods_supervisor=supervisor),
                              _mod_do_pedido=IpcHandlersMixin._mod_do_pedido)
    servico._manifesto_da_janela = functools.partial(IpcHandlersMixin._manifesto_da_janela,
                                                     servico)
    return servico


def _instalada(lugares: Any, **extra: Any) -> None:
    pasta = lugares.codigo / "toque"
    pasta.mkdir(parents=True)
    (pasta / "hefesto-mod.json").write_text(json.dumps(_manifesto(**extra)), encoding="utf-8")


def test_o_ipc_da_acao_so_leva_o_que_o_manifesto_declara(lar: Any) -> None:  # noqa: F811
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

    def livre(mod: str, i: str, v: float, *, soltou: bool) -> bool:
        arrastou.append((mod, i, v, soltou))
        return True

    sup.porta.livre = livre
    assert arrastar(id="ao-vivo", valor=0.5) == {"enviado": True}
    with pytest.raises(ValueError, match="não declara o controle livre «outro»"):
        arrastar(id="outro", valor=0.5)
    with pytest.raises(ValueError, match="de 0 a 1"):
        arrastar(id="ao-vivo", valor=1.5)
    assert arrastou == [("toque", "ao-vivo", 0.5, False)]
    sem = asyncio.run(IpcHandlersMixin._handle_mods_acao(
        _servico(None), {"mod": "toque", "acao": "parear"}))  # (noqa-acento)
    assert sem == {"enviada": False}


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
        chave = "enviada" if metodo == "mods.acao" else "enviado"
        return True, None, {chave: self.rodando}

    def escolher_arquivo(self, *_: Any, **__: Any) -> str | None:
        return None


@pytest.fixture
def janela(lar: Any, ctx: Any, tmp_path: pathlib.Path,  # noqa: F811
           monkeypatch: pytest.MonkeyPatch) -> Any:
    """Instala extensões de tema com as peças e abre a janela de uma delas."""
    a07 = _o_pacote()
    monkeypatch.setattr(a07, "_AGORA", a07._Agora())
    monkeypatch.setattr(a07, "_VIVA", a07._Viva())

    def instalar(mod_id: str = "toque", **extra: Any) -> None:
        _instalar(a07, ctx, _fonte(tmp_path, mod_id, nome=mod_id.title(),
                                   permissoes=(ESTADO,), extra=extra))

    def abrir(ponte: _Ponte, mod_id: str = "toque") -> dict[str, Any]:
        return dict(a07.configurar_modificacao(ctx, {"v": mod_id}, ponte))

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
def test_quatro_aparelhos_viram_quatro_linhas_e_o_testar_leva_o_alvo(
        janela: Any, ctx: Any, onde: str, n: int) -> None:  # noqa: F811
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
    assert feitas == [
        {"mod": "toque", "acao": "testar", "alvo": f"ap-{n}"}], feitas  # (noqa-acento)


def test_a_chave_do_aparelho_pede_o_contrario_e_o_botao_diz_em_curso(janela: Any, ctx: Any) -> None:  # noqa: F811
    import re

    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(VIVO)
    html = abrir(ponte)["blocos"]["#mod-janela"]

    def clique_da_chave(alvo: str) -> dict[str, str]:
        """O que o clique na chave do aparelho manda, lido da chave que a janela desenhou."""
        chave = re.search(rf'role="switch"[^>]*data-v="toque:ligar:{alvo}" data-ligado="(\d)"',
                          html)
        assert chave, f"a chave do {alvo} não foi desenhada"
        return {"v": f"toque:ligar:{alvo}", "ligado": chave.group(1)}

    a07.acao_da_modificacao(ctx, clique_da_chave("ap-4"), ponte)
    a07.acao_da_modificacao(ctx, clique_da_chave("ap-1"), ponte)
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


def test_o_em_curso_sai_no_teto_mesmo_sem_a_serie_subir(
        janela: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    """A extensão que não devolve estado nenhum não deixa o botão preso em «Em curso».

    Prova da D-2410-O-BOTAO-DA-ACAO-DIZ-EM-CURSO-ATE-A-SERIE-SUBIR.
    """
    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(VIVO)
    abrir(ponte)
    relogio = [1000.0]
    monkeypatch.setattr(a07.time, "monotonic", lambda: relogio[0])
    a07.acao_da_modificacao(ctx, {"v": "toque:parear"}, ponte)
    a07._AGORA.ler("toque", ponte)
    relogio[0] += a07.TETO_DO_EM_CURSO_S - 0.5
    assert "Em curso" in a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-acoes-0"]
    relogio[0] += 1.0
    assert "Em curso" not in a07._com_os_aparelhos({"blocos": {}})["blocos"]["#mod-acoes-0"], (
        "sem a série subir, o «Em curso» passou do teto")


def test_a_acao_da_extensao_parada_recusa_dizendo(janela: Any, ctx: Any) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(VIVO, rodando=False)
    abrir(ponte)
    with pytest.raises(RuntimeError, match="não está rodando"):
        a07.acao_da_modificacao(ctx, {"v": "toque:parear"}, ponte)


def test_arrastar_um_segundo_sai_em_no_maximo_vinte_e_o_ultimo_e_o_soltar(
        curto: pathlib.Path) -> None:  # noqa: F811
    """Prova da D-2410-O-CONTROLE-LIVRE-SAI-A-VINTE-POR-SEGUNDO-E-O-SOLTAR-NA-HORA."""
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


def test_o_arrastar_fora_de_ordem_cai_e_o_soltar_sempre_sai(janela: Any, ctx: Any) -> None:  # noqa: F811
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


def _gravar(a07: Any, ctx: Any, ponte: _Ponte, mod_id: str = "toque") -> dict[str, Any]:  # noqa: F811
    a07.gravar_o_livre_da_modificacao(ctx, {"v": f"{mod_id}:ao-vivo"}, ponte)
    for n, valor in enumerate((20, 80, 50)):
        a07.mover_o_livre_da_modificacao(
            ctx, {"v": f"{mod_id}:ao-vivo", "valor": str(valor), "vivo": str(n + 1),
                  "carimbo": str(n + 1)}, ponte)
    return dict(a07.gravar_o_livre_da_modificacao(ctx, {"v": f"{mod_id}:ao-vivo"}, ponte))


def test_a_forma_gravada_entra_nos_botoes_da_mesma_extensao_e_nao_na_outra(
        janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
    """Prova da D-2410-A-FORMA-GRAVADA-VALE-SO-NA-MESMA-EXTENSAO."""
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
    toque: Any = opcoes.ler(manifesto_instalado("toque", lugares=lar), lar)
    assert toque["toques"]["circle"] == "Meu 1"
    assert set(toque["ao-vivo"]) == {"Meu 1"} and len(toque["ao-vivo"]["Meu 1"]) <= 16

    outra = abrir(ponte, "outra")["blocos"]["#mod-janela"]
    assert "Meu 1" not in outra, "a forma de uma extensão apareceu na janela da outra"
    with pytest.raises(RuntimeError, match="forma declarada"):
        a07.guardar_opcao_da_modificacao(
            ctx, {"v": "outra:toques:circle", "valor": "Meu 1", "evento": "change"}, ponte)


def test_esquecer_a_forma_devolve_o_botao_ao_padrao(
        janela: Any, ctx: Any, lar: Any) -> None:  # noqa: F811
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
    valores: Any = opcoes.ler(manifesto_instalado("toque", lugares=lar), lar)
    assert valores["ao-vivo"] == {} and valores["toques"]["cross"] == "Pulso"


def _lugares_de(tmp_path: pathlib.Path) -> Any:
    from hefesto_dualsense4unix.mods.instalador import Lugares

    return Lugares(codigo=tmp_path / "codigo", dados=tmp_path / "dados",  # (noqa-acento)
                   registro=tmp_path / "registro.json", estado=tmp_path / "estado.json")


def _guardar_a_mao(lugares: Any, mod_id: str, valores: dict[str, Any]) -> None:
    from hefesto_dualsense4unix.mods import opcoes

    destino = opcoes.caminho(mod_id, lugares)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(valores), encoding="utf-8")


def test_o_botao_editado_a_mao_com_forma_que_nao_e_texto_cai_no_padrao_sem_levantar(
        tmp_path: pathlib.Path) -> None:
    """O ``ler`` nunca levanta: a forma de um botão que não é texto (o ``opcoes.json`` editado a
    mão) volta ao padrão daquele botão, e os outros ficam.

    Prova da D-2410-A-FORMA-DO-BOTAO-QUE-NAO-E-TEXTO-VOLTA-AO-PADRAO.
    """
    from hefesto_dualsense4unix.mods import opcoes

    manifesto = Manifesto.model_validate(_manifesto(**_pecas()))
    lugares = _lugares_de(tmp_path)
    for torta in (["Pulso"], {"Pulso": 1}):
        _guardar_a_mao(lugares, "toque", {"toques": {"cross": torta, "circle": "Sem toque"}})
        valores = opcoes.ler(manifesto, lugares)
        assert valores["toques"] == {"cross": "Pulso", "circle": "Sem toque"}, valores


def test_a_extensao_que_substitui_herda_o_botao_com_a_forma_gravada(
        tmp_path: pathlib.Path) -> None:
    """A extensão nova herda a forma gravada no ``livre`` da antiga E o botão que a escolheu.

    Prova da D-2410-A-EXTENSAO-QUE-SUBSTITUI-HERDA-A-FORMA-GRAVADA.
    """
    from hefesto_dualsense4unix.mods import opcoes

    manifesto = Manifesto.model_validate(_manifesto(**_pecas()))
    lugares = _lugares_de(tmp_path)
    _guardar_a_mao(lugares, "velha", {"ao-vivo": {"Meu 1": [[0.5, 1.0]]},
                                      "toques": {"cross": "Meu 1", "circle": "Sem toque"}})
    herdadas = opcoes.herdar(manifesto, ["velha"], lugares)
    assert herdadas.get("toques") == {"cross": "Meu 1", "circle": "Sem toque"}, herdadas
    valores: Any = opcoes.ler(manifesto, lugares)
    assert valores["toques"]["cross"] == "Meu 1" and set(valores["ao-vivo"]) == {"Meu 1"}


def test_o_gravar_aceso_continua_gravar_e_se_diz_apertado(janela: Any, ctx: Any) -> None:  # noqa: F811
    """O arranjo C: o «Gravar» aceso é o mesmo botão, vermelho e apertado; ele não promete guardar,
    porque quem grava no disco é o Guardar da janela."""
    import re

    a07, instalar, abrir = janela
    instalar(**_pecas())
    ponte = _Ponte(VIVO)
    abrir(ponte)

    def botao(carga: dict[str, Any]) -> str:
        achado = re.search(r'<button class="([^"]*)" data-gesto="gravar-o-livre-da-modificacao"'
                           r'[^>]*>(.*?)</button>', carga["blocos"]["#mod-janela"], re.S)
        assert achado, "a faixa não tem o «Gravar»"
        return achado.group(0)

    aceso = botao(a07.gravar_o_livre_da_modificacao(ctx, {"v": "toque:ao-vivo"}, ponte))
    assert 'aria-pressed="true"' in aceso and "mj-gravar on" in aceso, aceso
    assert aceso.endswith("Gravar</button>"), f"o botão aceso trocou o rótulo: {aceso}"
    apagado = botao(a07.gravar_o_livre_da_modificacao(ctx, {"v": "toque:ao-vivo"}, ponte))
    assert 'aria-pressed="false"' in apagado and "mj-gravar on" not in apagado, apagado


def test_gravar_sem_arrastar_nao_cria_forma(janela: Any, ctx: Any) -> None:  # noqa: F811
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

    a07 = _o_pacote()
    amostras = [(0.0, 0.0)] + [(t / 10, (t % 7) / 6) for t in range(1, 2000)] + [(200.0, 0.5)]
    passos = a07.passos_da_gravacao(amostras)
    assert 1 <= len(passos) <= 16 and forma_valida("Meu 1", passos)
    assert sum(s for _f, s in passos) == pytest.approx(160.0, abs=0.2), "o teto é 160 s"
    curta = a07.passos_da_gravacao([(0.0, 0.0), (0.5, 1.0), (1.0, 1.0)])
    assert curta == [[0.0, 0.5], [1.0, 0.5]]
    assert a07.passos_da_gravacao([(0.0, 0.3), (2.0, 0.3)]) == []


def test_os_gestos_e_os_metodos_estao_declarados() -> None:
    import sys

    a07 = _o_pacote()
    assert {"mods.acao", "mods.livre"} <= a07.METODOS
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
