"""O X da janela da extensão não desfaz o modo já gravado, e a recusa da extensão aparece.

O-CANCELAR-DA-JANELA-DESFAZ-O-MODO-E-A-RECUSA-APARECE-01 (25/10/2026) fazia o Cancelar, o X, o Esc
e o reabrir devolverem à extensão o modo guardado, porque o modo esperava o Guardar no rascunho.
Desde 28/10/2026 (D-2810-TODA-ESCOLHA-DA-JANELA-DA-EXTENSAO-GRAVA-NA-HORA) o modo grava no clique:
o X (o Cancelar saiu com o Guardar) e o reabrir não mandam nada, e a janela e a barra seguem o
modo escolhido. O modo que a
extensão recusa volta na janela e na barra, e a recusa vai à mesma borda e ao mesmo diário dos
outros gestos. Na porta, o controle de um aparelho com o id de uma ação dos aparelhos é recusado
nomeando o id: o clique dos dois chega à extensão com a mesma forma (a ação e o alvo), e o serviço
o tomava pela ação declarada.

MORDIDAS (25/10/2026 e 28/10/2026, executadas sobre a cura e devolvidas):

- o ``_guardar_a_opcao_da_modificacao`` tirado do ``modo_do_livre_da_modificacao`` reprova
  ``test_o_modo_trocado_grava_e_o_cancelar_e_o_reabrir_nao_o_desfazem`` (o soltar do guardado);
- o ``mudar_o_modo`` que não volta ao modo de antes na recusa reprova a recusa (a barra e a janela);
- o gesto do modo que ignora a resposta reprova a recusa (nada levanta);
- o X sem o ``data-gesto`` reprova o HTML e o WebKit;
- a porta sem a conferência do id da ação reprova os três casos dela, e o supervisor que não passa
  as ações à porta reprova o caso dele.
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import re
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.protocolo_do_ipc import CODE_INVALID_PARAMS
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from hefesto_dualsense4unix.mods.porta import Porta, RecusaError, estado_dos_acessorios
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import ctx, lar  # noqa: F401
from tests.unit.test_a_coluna_agora_e_o_parar_tudo_vem_do_servico import (  # noqa: F401
    P1,
    _Extensao,
    curto,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    ACOES_DOS_APARELHOS,
    ESTADO,
    VIVO,
    _Ponte,
    janela,
)
from tests.unit.test_o_livre_ganha_os_modos import (  # noqa: F401
    COM_MODOS,
    _arrastar_e_soltar,
    _com,
    _livres,
    _modos_na_faixa,
    relogio,
)
from hefesto_dualsense4unix.interface.desenho_da_experimental import janela_pintada

CANCELAR = "cancelar-modificacao"


class _PonteQueRecusa(_Ponte):
    """A ponte do teste: o serviço recusa o ``mods.livre`` enquanto ``recusa`` tem a frase."""

    recusa: str | None = None

    def chamar_com_o_corpo(self, metodo: str, **params: Any) -> tuple[bool, str | None, Any]:
        if self.recusa and metodo == "mods.livre":
            self.chamadas.append((metodo, params))
            return False, self.recusa, None
        return super().chamar_com_o_corpo(metodo, **params)


def _acesos(modo: str) -> dict[str, bool]:
    return {m: m == modo for m in ("soltar", "segurar", "repetir")}


def _cancelar(a07: Any, ctx: Any, ponte: _Ponte) -> dict[str, Any]:  # noqa: F811
    """O X fecha no primeiro gesto: não há rascunho a descartar."""
    carga = dict(a07.cancelar_modificacao(ctx, {"v": "toque"}, ponte))
    assert "armou" not in carga, "o X armou um Descartar"
    return carga


@pytest.mark.parametrize("como", ["cancelar", "reabrir"])
def test_o_modo_trocado_grava_e_o_cancelar_e_o_reabrir_nao_o_desfazem(
        janela: Any, ctx: Any, lar: Any, relogio: list[float], como: str) -> None:  # noqa: F811
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    a07, instalar, abrir = janela
    instalar(**_com(COM_MODOS))
    ponte = _Ponte(VIVO)
    abrir(ponte)
    _arrastar_e_soltar(a07, ctx, ponte, relogio)
    a07.modo_do_livre_da_modificacao(ctx, {"v": "toque:ao-vivo:segurar"}, ponte)
    guardado = opcoes.ler(manifesto_instalado("toque", lugares=lar), lar)
    assert guardado["ao-vivo:modo"] == "segurar", "o modo esperou o Guardar"
    antes = len(_livres(ponte))
    carga = _cancelar(a07, ctx, ponte) if como == "cancelar" else abrir(ponte)
    assert _livres(ponte)[antes:] == [], f"o {como} desfez o modo gravado"
    assert _modos_na_faixa(janela_pintada(carga["blocos"])) == _acesos("segurar")
    assert a07._VIVA.modo == "segurar", "a barra largou o modo gravado"


def test_o_x_sem_troca_ou_depois_da_troca_nao_manda_nada(
        janela: Any, ctx: Any, relogio: list[float]) -> None:  # noqa: F811
    a07, instalar, abrir = janela
    instalar(**_com(COM_MODOS))
    ponte = _Ponte(VIVO)
    abrir(ponte)
    _arrastar_e_soltar(a07, ctx, ponte, relogio)
    antes = len(_livres(ponte))
    _cancelar(a07, ctx, ponte)
    assert len(_livres(ponte)) == antes, "o X sem troca mandou soltar à extensão"
    a07.modo_do_livre_da_modificacao(ctx, {"v": "toque:ao-vivo:repetir"}, ponte)
    antes = len(_livres(ponte))
    carga = _cancelar(a07, ctx, ponte)
    assert len(_livres(ponte)) == antes, "o X depois da troca desfez o que foi gravado"
    assert _modos_na_faixa(janela_pintada(carga["blocos"])) == _acesos("repetir")


def _o_modo_guardado(lar: Any) -> Any:  # noqa: F811
    from hefesto_dualsense4unix.mods import opcoes
    from hefesto_dualsense4unix.mods.instalador import manifesto_instalado

    return opcoes.ler(manifesto_instalado("toque", lugares=lar), lar)["ao-vivo:modo"]


def test_o_modo_recusado_volta_na_janela_e_na_barra_e_a_recusa_aparece(
        janela: Any, ctx: Any, lar: Any, relogio: list[float]) -> None:  # noqa: F811
    """Prova da D-2510-A-RECUSA-DO-MODO-DEVOLVE-A-BARRA."""
    frase = "A extensão recusou o modo."
    a07, instalar, abrir = janela
    instalar(**_com(COM_MODOS))
    ponte = _PonteQueRecusa(VIVO)
    abrir(ponte)
    a07.modo_do_livre_da_modificacao(ctx, {"v": "toque:ao-vivo:segurar"}, ponte)
    _arrastar_e_soltar(a07, ctx, ponte, relogio)
    ponte.recusa = frase
    with pytest.raises(RuntimeError, match=frase):
        a07.modo_do_livre_da_modificacao(ctx, {"v": "toque:ao-vivo:soltar"}, ponte)
    assert a07._VIVA.modo == "segurar", "o modo recusado ficou valendo na barra"
    assert _o_modo_guardado(lar) == "segurar", "o modo recusado foi gravado"
    assert _modos_na_faixa(a07._MEXIDA.html_mod) == _acesos("segurar")
    relogio[0] += 0.5
    assert a07._VIVA.ao_vivo("toque").valor == 1.0, "a barra fez o «Soltar» que a extensão recusou"


def _fechos(html: str) -> list[str]:
    """As etiquetas de fecho da janela: só o X, sem rodapé de Cancelar e Guardar."""
    return re.findall(r'<a class="(?:btn|tn-x)" href="#"[^>]*>(?:Cancelar|Guardar|\u00d7)</a>',
                      html)


@pytest.mark.parametrize("arranjo", ["com o livre", "simples"])
def test_o_x_da_janela_leva_o_gesto_e_e_o_unico_fecho(
        janela: Any, ctx: Any, arranjo: str) -> None:  # noqa: F811
    _a07, instalar, abrir = janela
    opcao = {"id": "telefone", "rotulo": "Telefone", "tipo": "ligado",
             "padrao": False}  # (noqa-acento)
    instalar(**(_com(COM_MODOS) if arranjo == "com o livre" else {
        "opcoes": [opcao]}))  # (noqa-acento)
    html = abrir(_Ponte(VIVO))["blocos"]["#mod-janela"]
    fechos = _fechos(html)
    assert len(fechos) == 1 and "tn-x" in fechos[0], fechos
    assert "guardar-modificacao" not in html and 'id="mod-rodape"' not in html
    for fecho in fechos:
        assert f'data-gesto="{CANCELAR}" data-v="toque"' in fecho, fecho


def test_o_gesto_do_cancelar_esta_declarado_sem_eco() -> None:
    from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import _o_pacote

    assert CANCELAR in _o_pacote().SEM_ECO


_FECHAR = """(function(h, como){
  const j = document.getElementById('mod-janela');
  j.innerHTML = h;
  const tela = j.closest('.tela-nova');
  location.hash = '#' + tela.id;
  const vistos = [];
  const ouvir = e => { const g = e.target.closest && e.target.closest('[data-gesto]');
    vistos.push(g ? g.dataset.gesto + '|' + g.dataset.v : ''); };
  document.addEventListener('click', ouvir, true);
  if (como === 'esc') {
    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
  } else {
    j.querySelector('a.tn-x').click();
  }
  document.removeEventListener('click', ouvir, true);
  return JSON.stringify({vistos: vistos, aberta: getComputedStyle(tela).display !== 'none'});
})(%s, %s)"""


def test_no_webkit_o_esc_e_o_x_mandam_o_gesto_e_fecham(
        janela: Any, ctx: Any) -> None:  # noqa: F811
    """O HTML da janela posto no desenho, num WebKit de verdade: o Esc clica o X, e o X clica a
    si; os dois levam o gesto, e a janela fecha."""
    from tests.unit.test_o_aparelho_da_extensao_diz_os_controles_dele import VISTAS, rodar_no_webkit

    _a07, instalar, abrir = janela
    instalar(**_com(COM_MODOS))
    html = abrir(_Ponte(VIVO))["blocos"]["#mod-janela"]
    w, h = VISTAS[1]
    passos = [["js", _FECHAR % (json.dumps(html), json.dumps(como))] for como in ("esc", "x")]
    lidos = rodar_no_webkit({"janela": (w, h, passos)})
    for como, bruto in zip(("esc", "x"), lidos["janela"], strict=True):
        lido = json.loads(bruto)
        assert lido["vistos"] == [f"{CANCELAR}|toque"], f"{como}: {lido}"
        assert lido["aberta"] is False, f"{como}: a janela ficou aberta"


ACOES = frozenset(a["id"] for a in ACOES_DOS_APARELHOS)


def _com_o_controle(controle_id: str) -> dict[str, Any]:
    return {"aparelhos": [{"id": "lampada-1", "nome": "Lâmpada", "controles": [
        {"id": controle_id, "tipo": "chave", "valor": False}]}]}


@pytest.mark.parametrize("controle_id", sorted(ACOES))
def test_o_controle_com_o_id_de_uma_acao_dos_aparelhos_e_recusado_nomeando_o_id(
        controle_id: str) -> None:
    """Prova da D-2510-O-CONTROLE-NAO-REPETE-O-ID-DE-UMA-ACAO."""
    with pytest.raises(RecusaError) as recusa:
        estado_dos_acessorios("toque", _com_o_controle(controle_id), acoes_dos_aparelhos=ACOES)
    assert recusa.value.codigo == CODE_INVALID_PARAMS
    assert f"«{controle_id}»" in recusa.value.frase, recusa.value.frase


def test_o_controle_de_id_proprio_passa_e_sem_acoes_declaradas_tambem() -> None:
    certo = estado_dos_acessorios("toque", _com_o_controle("acesa"), acoes_dos_aparelhos=ACOES)
    assert certo["aparelhos"][0]["controles"][0]["id"] == "acesa"
    assert estado_dos_acessorios("toque", _com_o_controle("testar"))["aparelhos"]


def test_a_porta_recusa_o_estado_so_da_extensao_que_declara_a_acao(curto: pathlib.Path) -> None:  # noqa: F811
    async def corrida() -> None:
        async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
            return {"status": "ok"}

        porta = Porta(curto / "mods.sock", EventBus(), escritor=escritor,
                      o_jogo_escreve=lambda uniq, canal: False, uniq_do_posto=lambda: P1)
        await porta.iniciar()
        porta.registrar("ficha-a", "toque", os.getpid(), [ESTADO],
                        acoes_dos_aparelhos=tuple(sorted(ACOES)))
        porta.registrar("ficha-b", "outra", os.getpid(), [ESTADO])
        try:
            for ficha, recusa in (("ficha-a", True), ("ficha-b", False)):
                ext = _Extensao(curto / "mods.sock")
                try:
                    await asyncio.to_thread(ext.pedir, "mod.ola", {"ficha": ficha})
                    resposta = await asyncio.to_thread(
                        ext.pedir, "acessorios.estado", _com_o_controle("testar"))
                finally:
                    ext.fechar()
                if recusa:
                    assert resposta["error"]["code"] == CODE_INVALID_PARAMS, resposta
                    assert "«testar»" in resposta["error"]["message"], resposta
                else:
                    assert resposta.get("result") == {"recebido": True}, resposta
        finally:
            await porta.parar()

    asyncio.run(corrida())


def test_o_supervisor_passa_a_porta_as_acoes_dos_aparelhos(
        tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.mods import supervisor as sup
    from hefesto_dualsense4unix.mods.instalador import Lugares

    lugares = Lugares(codigo=tmp_path / "codigo", dados=tmp_path / "dados",  # (noqa-acento)
                      registro=tmp_path / "mods.json", estado=tmp_path / "estado.json")
    (lugares.codigo / "toque").mkdir(parents=True)
    manifesto = Manifesto.model_validate({
        "id": "toque", "nome": "Toque", "versao": "0.1", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"],
        "processo": {"executar": ["python3", "mod.py"]},
        "permissoes": [ESTADO],  # (noqa-acento)
        "agora": ["aparelhos"],
        "aparelhos_acoes": {"acoes": ACOES_DOS_APARELHOS}})  # (noqa-acento)

    async def abrir_de_mentira(*_argv: Any, **_kw: Any) -> Any:
        saida = asyncio.StreamReader()
        saida.feed_eof()
        return SimpleNamespace(pid=os.getpid(), stdout=saida, returncode=None)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", abrir_de_mentira)

    async def corrida() -> frozenset[str]:
        async def escritor(metodo: str, pedido: dict[str, Any]) -> Any:
            return {"status": "ok"}

        supervisor = sup.Supervisor(EventBus(), escritor=escritor,
                                    o_jogo_escreve=lambda uniq, canal: False,
                                    uniq_do_posto=lambda: P1, lugares=lugares,
                                    porta=tmp_path / "m.sock", procurar_bwrap=False)
        vigiada = sup._Vigiada("toque")
        await supervisor._abrir(vigiada, manifesto, tmp_path / "diario.log")
        assert vigiada.copia is not None
        await vigiada.copia
        acoes: frozenset[str] = supervisor.porta._fichas[vigiada.ficha].acoes_dos_aparelhos
        return acoes

    assert asyncio.run(corrida()) == ACOES
