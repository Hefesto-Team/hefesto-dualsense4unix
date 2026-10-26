"""O Parear da extensão mostra o andamento da busca.

O-PAREAR-DA-EXTENSAO-MOSTRA-O-ANDAMENTO-COMO-A-ABA-08-01 (26/10/2026). O usuário clicou Parear em
«Configurar · Lovense» e «funcionou mas sem nenhum indicativo de que ia conectar em algum momento».
A janela agora lê do estado que a extensão devolve (a conexão que diz «Procurando aparelhos»)
quando a busca começa e quando acaba: durante ela, a faixa «Procurando aparelhos» com os segundos
que faltam do prazo de 20 s; no fim, o aparelho que apareceu ou a razão de não ter achado nenhum.
Sem aparelho a faixa divide a linha do Parear (é a própria linha do aviso).

MORDIDAS (26/10/2026, executadas sobre a cura e devolvidas): o estado em curso arrancado (o
``ver`` que nunca devolve a busca) reprova a faixa da busca, a contagem e a janela aberta; o fim
sem o diff dos aparelhos reprova o «Achou»; a razão arrancada reprova a dica do fim sem achar; o
fim que nunca sai reprova a volta ao aviso.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Any

import pytest

from hefesto_dualsense4unix.interface import desenho_da_experimental as exp
from tests.unit.test_a_aba_lancadores_ganha_as_modificacoes import (  # noqa: F401
    ctx,
    lar,
)
from tests.unit.test_a_janela_da_extensao_age_e_gere_os_aparelhos import (  # noqa: F401
    VIVO,
    _Ponte,
    janela,
)
from tests.unit.test_a_linha_sem_aparelho_fica_a_direita_do_parear import (  # noqa: F401
    _ABRIR,
    SEM_APARELHOS,
    montada,
    no_webkit,
    pagina_fresca,
)
from tests.unit.test_a_lista_da_janela_configurar_nao_pula_ao_clicar_um_efeito import (
    ENDERECO,
    MOD,
    VISTAS,
)

BUSCANDO = {"id": "bluetooth", "tipo": "Bluetooth", "transporte": "bluetooth",
            "estado": "procurando", "motivo": exp.COMECO_DO_MOTIVO_DA_BUSCA + " aparelhos"}
QUIETA = {**BUSCANDO, "motivo": "Ligue o aparelho"}
FALHOU = {"id": "usb", "tipo": "Adaptador USB", "transporte": "usb", "estado": "falhou",
          "motivo": "O adaptador não abriu"}
NOVO = {"id": "ap-9", "nome": "Lush 3", "ligado": True, "estado": "ligado"}


def estado(conexao: dict[str, Any], aparelhos: list[dict[str, Any]] | None = None
           ) -> dict[str, Any]:
    return {exp.CHAVE_DAS_CONEXOES: [conexao], "aparelhos": aparelhos or []}


class Relogio:
    def __init__(self) -> None:
        self.t = 100.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def dono() -> tuple[exp.AndamentoDoPareamento, Relogio]:
    relogio = Relogio()
    return exp.AndamentoDoPareamento(relogio), relogio


def test_sem_busca_a_janela_nao_mostra_andamento(
        dono: tuple[exp.AndamentoDoPareamento, Relogio]) -> None:
    andamento, _ = dono
    visto = andamento.ver("lovense", estado(QUIETA))
    assert visto.fase == "" and visto.html(vazio=True) == ""


def test_a_busca_diz_os_segundos_que_faltam_do_prazo(
        dono: tuple[exp.AndamentoDoPareamento, Relogio]) -> None:
    andamento, relogio = dono
    primeiro = andamento.ver("lovense", estado(BUSCANDO))
    assert (primeiro.fase, primeiro.restam) == ("busca", 20)
    relogio.t += 7
    assert andamento.ver("lovense", estado(BUSCANDO)).restam == 13
    relogio.t += 30
    passado = andamento.ver("lovense", estado(BUSCANDO))
    assert passado.fase == "busca" and passado.restam is None
    assert "Procurando aparelhos" in passado.html(vazio=True)
    assert "mj-busca-resta" not in passado.html(vazio=True)


def test_o_fim_com_aparelho_novo_diz_o_nome_dele(
        dono: tuple[exp.AndamentoDoPareamento, Relogio]) -> None:
    andamento, relogio = dono
    andamento.ver("lovense", estado(BUSCANDO))
    relogio.t += 8
    fim = andamento.ver("lovense", estado(QUIETA, [NOVO]))
    assert fim.fase == "fim" and fim.achou == ("Lush 3",)
    assert "Achou Lush 3" in fim.html(vazio=False)


def test_quem_ja_estava_na_lista_nao_conta_como_achado(
        dono: tuple[exp.AndamentoDoPareamento, Relogio]) -> None:
    andamento, relogio = dono
    andamento.ver("lovense", estado(BUSCANDO, [NOVO]))
    relogio.t += 8
    fim = andamento.ver("lovense", estado(QUIETA, [NOVO]))
    assert fim.achou == () and "Não achou nenhum aparelho" in fim.html(vazio=False)


def test_o_fim_sem_achar_leva_a_razao_na_dica(
        dono: tuple[exp.AndamentoDoPareamento, Relogio]) -> None:
    andamento, relogio = dono
    andamento.ver("lovense", estado(BUSCANDO))
    relogio.t += 20
    cena = {exp.CHAVE_DAS_CONEXOES: [FALHOU, {**BUSCANDO, "estado": "desligado", "motivo": None}],
            "aparelhos": []}
    html = andamento.ver("lovense", cena).html(vazio=True)
    dica = re.search(r'data-dica="([^"]+)"', html)
    assert dica and "Adaptador USB: O adaptador não abriu" in dica.group(1), html
    assert "Bluetooth" not in dica.group(1), "só quem falhou ou procura entra na razão"
    sem_nada = exp.AndamentoDoPareamento(relogio)
    sem_nada.ver("x", estado(BUSCANDO))
    relogio.t += 5
    vazio = {exp.CHAVE_DAS_CONEXOES: [], "aparelhos": []}
    assert exp.SEM_RAZAO_DA_BUSCA in sem_nada.ver("x", vazio).html(vazio=True)


def test_o_fim_sai_da_tela_e_o_aviso_volta(
        dono: tuple[exp.AndamentoDoPareamento, Relogio]) -> None:
    andamento, relogio = dono
    andamento.ver("lovense", estado(BUSCANDO))
    relogio.t += 5
    assert andamento.ver("lovense", estado(QUIETA)).fase == "fim"
    relogio.t += exp.FIM_DA_BUSCA_VISIVEL_S + 1
    assert andamento.ver("lovense", estado(QUIETA)).fase == ""


def test_cada_extensao_tem_o_andamento_dela(
        dono: tuple[exp.AndamentoDoPareamento, Relogio]) -> None:
    andamento, _ = dono
    andamento.ver("a", estado(BUSCANDO))
    assert andamento.ver("b", estado(QUIETA)).fase == ""


def test_sem_aparelho_a_faixa_e_a_linha_do_aviso(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(exp, "ANDAMENTO_DO_PAREAR", exp.AndamentoDoPareamento(Relogio()))
    gestao = exp.Gestao("lovense", exp.AparelhosDaJanela(exp.ACOES_DO_DESENHO, "Aparelhos"),
                        estado(BUSCANDO))
    html = exp.aparelhos_geridos_html(gestao)
    assert 'class="mj-busca mj-ap-vazio mj-busca-busca"' in html
    assert exp.SEM_APARELHOS not in html


def test_com_aparelho_a_faixa_vem_antes_dos_cartoes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(exp, "ANDAMENTO_DO_PAREAR", exp.AndamentoDoPareamento(Relogio()))
    gestao = exp.Gestao("lovense", exp.AparelhosDaJanela(exp.ACOES_DO_DESENHO, "Aparelhos"),
                        estado(BUSCANDO, [NOVO]))
    html = exp.aparelhos_geridos_html(gestao)
    assert html.index("mj-busca") < html.index("mj-ap-cab") and "mj-ap-vazio" not in html


def test_a_janela_aberta_e_o_tique_mostram_a_busca_e_o_fim(
        janela: Any, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    relogio = Relogio()
    monkeypatch.setattr(exp, "ANDAMENTO_DO_PAREAR", exp.AndamentoDoPareamento(relogio))
    a07, _, _ = janela
    html = montada(janela, {**SEM_APARELHOS, exp.CHAVE_DAS_CONEXOES: [BUSCANDO]})
    assert "Procurando aparelhos" in html and exp.SEM_APARELHOS not in html
    ponte = _Ponte({**SEM_APARELHOS, exp.CHAVE_DAS_CONEXOES: [BUSCANDO], "serie": 2})
    a07._AGORA.ler(MOD, ponte)
    relogio.t += 6
    blocos = a07._com_os_aparelhos({"blocos": {}})["blocos"]
    assert "Procurando aparelhos" in blocos["#mod-aparelhos"]
    assert re.search(r"mj-busca-resta[^>]*>1[34] s<", blocos["#mod-aparelhos"])
    ponte.estado = {**VIVO, exp.CHAVE_DAS_CONEXOES: [QUIETA], "serie": 3}
    a07._AGORA.esquecer()
    a07._AGORA.ler(MOD, ponte)
    blocos = a07._com_os_aparelhos({"blocos": {}})["blocos"]
    assert "Achou" in blocos["#mod-aparelhos"] or "Não achou" in blocos["#mod-aparelhos"]
    assert "Procurando aparelhos" not in blocos["#mod-aparelhos"]


_LER = """(function(){
  const j = document.getElementById('mod-janela');
  const r = e => { if (!e) return null; const x = e.getBoundingClientRect();
    return {x: x.left, y: x.top, d: x.right, b: x.bottom, w: x.width, h: x.height}; };
  const fileira = j.querySelector('[id^="mod-acoes-"]');
  const busca = j.querySelector('.mj-busca');
  const cartao = j.querySelector('#mod-aparelhos .mj-ap');
  return JSON.stringify({botao: r(fileira.querySelector('.mj-acao')), fileira: r(fileira),
    busca: r(busca), texto: busca ? busca.textContent : '',
    dica: busca ? busca.dataset.dica || '' : '',
    cartao: r(cartao), janela: r(j.querySelector('.mj-abas')),
    corte: busca ? busca.scrollWidth > busca.clientWidth + 1 : false});
})()"""


@pytest.fixture
def cenas(janela: Any, pagina_fresca: pathlib.Path,  # noqa: F811
          monkeypatch: pytest.MonkeyPatch) -> dict[str, dict[str, Any]]:
    from hefesto_dualsense4unix.interface import hefesto_vivo

    relogio = Relogio()
    casos = {}
    for nome, antes, depois in (
            ("sem", None, {**SEM_APARELHOS, exp.CHAVE_DAS_CONEXOES: [QUIETA]}),
            ("busca", None, {**SEM_APARELHOS, exp.CHAVE_DAS_CONEXOES: [BUSCANDO]}),
            ("fim", {**SEM_APARELHOS, exp.CHAVE_DAS_CONEXOES: [BUSCANDO]},
             {**SEM_APARELHOS, exp.CHAVE_DAS_CONEXOES: [FALHOU]}),
            ("com", None, {**VIVO, exp.CHAVE_DAS_CONEXOES: [QUIETA]}),
            ("busca-com", None, {**VIVO, exp.CHAVE_DAS_CONEXOES: [BUSCANDO]})):
        monkeypatch.setattr(exp, "ANDAMENTO_DO_PAREAR", exp.AndamentoDoPareamento(relogio))
        if antes:
            montada(janela, antes)
        html = montada(janela, depois)
        for w, h in VISTAS:
            casos[f"{nome}@{w}x{h}"] = (w, h, [
                ["js", hefesto_vivo.BOOTSTRAP],
                ["js", _ABRIR % (json.dumps(ENDERECO), json.dumps(html))],
                ["espera", 0.3], ["js", _LER]])
    lidos = no_webkit(pagina_fresca, casos)
    saida = {}
    for caso, (_, abriu, lido) in lidos.items():
        assert abriu == "ok", (caso, abriu)
        saida[caso] = json.loads(lido)
    print(json.dumps(saida, ensure_ascii=False))
    return saida


def test_a_faixa_da_busca_divide_a_linha_do_parear_e_nada_se_move(
        cenas: dict[str, dict[str, Any]]) -> None:
    falhas = []
    for w, h in VISTAS:
        sem, busca, fim = (cenas[f"{n}@{w}x{h}"] for n in ("sem", "busca", "fim"))
        for nome, cena in (("busca", busca), ("fim", fim)):
            faixa, botao = cena["busca"], cena["botao"]
            if faixa is None:
                falhas.append(f"{w}x{h}: {nome} sem faixa")
                continue
            if faixa["x"] < botao["d"] - 0.5 or faixa["y"] >= botao["b"] - 0.5:
                falhas.append(f"{w}x{h}: a faixa do {nome} não está à direita do Parear: {faixa}")
            if abs((faixa["y"] + faixa["b"]) / 2 - (botao["y"] + botao["b"]) / 2) > 1.5:
                falhas.append(f"{w}x{h}: a faixa do {nome} não está no centro do botão")
            if cena["corte"]:
                falhas.append(f"{w}x{h}: a faixa do {nome} é cortada")
            for chave in ("botao", "fileira", "janela"):
                for lado in ("x", "y", "w", "h"):
                    if abs(sem[chave][lado] - cena[chave][lado]) > 0.5:
                        falhas.append(f"{w}x{h}: {chave}.{lado} muda {sem[chave][lado]:.1f} -> "
                                      f"{cena[chave][lado]:.1f} no {nome}")
        if "Procurando aparelhos" not in busca["texto"] or " s" not in busca["texto"]:
            falhas.append(f"{w}x{h}: a busca não diz o que faz nem o prazo: {busca['texto']!r}")
        if "Não achou" not in fim["texto"] or "Adaptador USB" not in fim["dica"]:
            falhas.append(f"{w}x{h}: o fim não diz a razão: {fim['texto']!r} {fim['dica']!r}")
    assert not falhas, "\n".join(falhas)


def test_com_aparelho_a_busca_entra_acima_dos_cartoes_sem_mexer_no_parear(
        cenas: dict[str, dict[str, Any]]) -> None:
    falhas = []
    for w, h in VISTAS:
        com, busca = cenas[f"com@{w}x{h}"], cenas[f"busca-com@{w}x{h}"]
        if busca["busca"] is None or busca["cartao"] is None:
            falhas.append(f"{w}x{h}: sem faixa ou sem cartão: {busca}")
            continue
        if busca["busca"]["b"] > busca["cartao"]["y"] + 0.5:
            falhas.append(f"{w}x{h}: a faixa não fica acima do cartão")
        for lado in ("x", "y", "w", "h"):
            if abs(com["botao"][lado] - busca["botao"][lado]) > 0.5:
                falhas.append(f"{w}x{h}: o Parear muda de {lado}")
    assert not falhas, "\n".join(falhas)
