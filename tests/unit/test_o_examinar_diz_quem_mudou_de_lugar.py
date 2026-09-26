"""O «Examinar» diz quem mudou de lugar, o hub não cabe onde há aparelho direto,
e a ponta do extensor grava.

O-MAPA-DAS-CONEXOES-NO-PRODUTO-02, 26/09/2026. A conferência da 01 mediu três
buracos no mapa das conexões publicado:

1. o «Examinar» dizia sempre «Nada Mudou de Lugar»: as duas leituras nasciam
   iguais, o gesto não tinha por onde entregar outra, e o ``id`` do aparelho
   era o caminho de barramento, que é justamente o que muda quando ele muda
   de entrada («Estava em undefined»);
2. com um dongle direto na 5, declarar «Hub» na 5 desenhava um hub que não
   pode estar ali, e a Sugestão mandava o dongle «da Entrada 5 para a 5.1»;
3. o que ela declarava nas entradas desenhadas sumia ao reabrir, sem aviso.

TUDO AQUI É DE MENTIRA E DE NINGUÉM: barramento ``usb9``, caminhos ``9-*``,
seriais que não são endereço de nada, e o ``maquina.json`` no ``tmp_path``
que o ``conftest`` desvia.

AS MORDIDAS, uma por cura (arranque, veja reprovar, devolva):

* ``identidades`` devolvendo o caminho como ``id`` → caem as réguas da
  identidade e o reexame na página («Estava em» some);
* o ``if (doProduto()) return;`` do clique do «Examinar» → a página pinta o
  reexame antes de a leitura nova chegar, e diz «Nada Mudou de Lugar»;
* o ``!doHubDesenhado(p)`` do ``planejar`` → a Sugestão volta a mandar o
  dongle para a 5.1;
* o ramo do «Hub» cinza no editor → o «Hub» volta a levar o gesto ao disco;
* o ramo da ponta no ``_declarar_na_entrada`` → a ponta volta a recusar.

E AS DA CONFERÊNCIA (26/09/2026), cada uma sem régua que a pegasse:

* o ``parados`` de ``identidades`` → o gêmeo que chega (ou sai) faz o
  reexame dizer que o aparelho parado «mudou de lugar»;
* o modelo fora da semente do caminho → outro modelo que chega no caminho de
  quem saiu herda o ``id`` dele, e o reexame não o vê chegar;
* o ``examinaNoProduto()`` do «Já movi» das Sugestões → no produto o botão
  fica morto (a página não pinta, e o piloto não é chamado);
* o ``mapaDaTela`` do ``hefestoArranjo`` → o reexame joga fora o que ela
  ensinou nesta tela;
* o ``quem.classe !== "hub"`` do «Hub» cinza → o hub de verdade na entrada
  também apaga o «Hub».
"""

from __future__ import annotations

import gc
import json
import re
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import entrada_a_entrada as ee
from hefesto_dualsense4unix.integrations import mapa_das_portas
from hefesto_dualsense4unix.integrations.censo_do_barramento import (
    Aparelho,
    Barramento,
    Censo,
)
from hefesto_dualsense4unix.interface import arranjo_desta_maquina, onde
from hefesto_dualsense4unix.utils.maquina import (
    FaceDeclarada,
    MapaDaMesa,
    PortaDeclarada,
    caminho_da_maquina,
    carregar_maquina,
    gravar_maquina,
)

# ── os dublês ─────────────────────────────────────────────────────────────

_TRIPLA_TECLADO = ("03", "01", "01")
_TRIPLA_BT = ("e0", "01", "01")

#: Os seriais de mentira, por nó. Não são endereço de nada — e a régua
#: confere que nenhum deles chega à página.
_SERIAIS = {
    "/sys/de-mentira/teclado": "SERIE-DE-PROVA-TECLADO",
    "/sys/de-mentira/dongle": "SERIE-DE-PROVA-DONGLE",
}


def _serial(no: str) -> str:
    return _SERIAIS.get(no, "")


def _aparelho(
    no: str, caminho: str, vid: str, pid: str, especie: str,
    tripla: tuple[str, str, str], produto: str = "Aparelho de prova",
) -> Aparelho:
    return Aparelho(
        no=no, nome_do_kernel=caminho, vid=vid, pid=pid, produto=produto,
        especie=especie, classe=tripla[0], subclasse=tripla[1],
        protocolo=tripla[2], velocidade_mbps=480.0,
    )


def _teclado(caminho: str) -> Aparelho:
    return _aparelho("/sys/de-mentira/teclado", caminho, "1111", "0001",
                     "Teclado", _TRIPLA_TECLADO, "Teclado de prova")


def _dongle(caminho: str) -> Aparelho:
    return _aparelho("/sys/de-mentira/dongle", caminho, "2222", "0002",
                     "Bluetooth", _TRIPLA_BT, "Dongle de prova")


def _censo(*aparelhos: Aparelho) -> Censo:
    return Censo(
        aparelhos=aparelhos,
        barramentos=(Barramento(no="/sys/usb9", nome_do_kernel="usb9",
                                velocidade_mbps=480.0),),
    )


def _mapa(**declarado: dict[str, Any]) -> MapaDaMesa:
    """Duas na frente, três atrás; a 1, a 2 e a 5 com o caminho amarrado."""
    caminhos = {"1": "9-1", "2": "9-2", "3": None, "4": None, "5": "9-5"}
    return MapaDaMesa(
        faces=[FaceDeclarada(nome="Frente", portas=["1", "2"], perto=True),
               FaceDeclarada(nome="Traseira", portas=["3", "4", "5"])],
        portas={
            numero: PortaDeclarada(caminho=caminho, **declarado.get(f"e{numero}", {}))
            for numero, caminho in caminhos.items()
        },
    )


@pytest.fixture()
def disco(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta régua mora no ``tmp_path`` — conferido antes."""
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    assert gravar_maquina({"mapa": _mapa().model_dump(mode="json")})
    return alvo


def _ler(*aparelhos: Aparelho, reexame: bool = False) -> dict[str, Any]:
    fontes: dict[str, Any] = {
        "carregar": carregar_maquina,
        "ler_o_barramento": lambda: _censo(*aparelhos),
        "ler_o_serial": _serial,
    }
    dado = (arranjo_desta_maquina.reexaminar(**fontes) if reexame
            else arranjo_desta_maquina.para_a_pagina(**fontes))
    assert dado is not None
    return dado


# ── 1. a identidade do aparelho não é o caminho ──────────────────────────


def test_o_aparelho_que_muda_de_entrada_continua_sendo_ele() -> None:
    """O serial (e o modelo, quando ele é o único) atravessa a mudança."""
    antes = arranjo_desta_maquina.identidades(
        [_teclado("9-1"), _dongle("9-5")], _serial)
    depois = arranjo_desta_maquina.identidades(
        [_teclado("9-2"), _dongle("9-5")], _serial)
    assert antes["9-1"] == depois["9-2"], (
        "o teclado mudou de entrada e virou outro aparelho — o reexame diria "
        "«Estava em undefined»")
    assert antes["9-5"] == depois["9-5"]
    assert antes["9-1"] != antes["9-5"]

    sem_serial = [
        _aparelho("/sys/x/a", "9-3", "3333", "0003", "Mouse", ("03", "01", "02")),
    ]
    um = arranjo_desta_maquina.identidades(sem_serial, _serial)["9-3"]
    movido = [_aparelho("/sys/x/a", "9-4", "3333", "0003", "Mouse", ("03", "01", "02"))]
    assert arranjo_desta_maquina.identidades(movido, _serial)["9-4"] == um, (
        "o único receptor daquele modelo, sem serial, deixou de ser reconhecido")


def test_dois_iguais_sem_serial_nao_viram_um_so() -> None:
    """Dois do mesmo modelo sem serial: o caminho separa, nunca o chute."""
    gemeos = [
        _aparelho("/sys/x/a", "9-3", "3333", "0003", "Mouse", ("03", "01", "02")),
        _aparelho("/sys/x/b", "9-4", "3333", "0003", "Mouse", ("03", "01", "02")),
    ]
    ids = arranjo_desta_maquina.identidades(gemeos, _serial)
    assert ids["9-3"] != ids["9-4"], "dois aparelhos viraram o mesmo na página"

    mesmo_serial = [
        _aparelho("/sys/de-mentira/teclado", "9-3", "1111", "0001", "Teclado", _TRIPLA_TECLADO),
        _aparelho("/sys/de-mentira/teclado", "9-4", "1111", "0001", "Teclado", _TRIPLA_TECLADO),
    ]
    ids = arranjo_desta_maquina.identidades(mesmo_serial, _serial)
    assert ids["9-3"] != ids["9-4"], "o serial de fábrica repetido juntou dois aparelhos"


def _mouse(no: str, caminho: str, vid: str = "3333", pid: str = "0003") -> Aparelho:
    return _aparelho(no, caminho, vid, pid, "Mouse", ("03", "01", "02"), "Mouse de prova")


def _mudaram(dado: dict[str, Any]) -> dict[str, tuple[str | None, str]]:
    """``id -> (antes, agora)`` de quem o reexame da página listaria."""
    antes, agora = (dado["leituras"][k]["caminho"] for k in ("antes", "agora"))
    return {i: (antes.get(i), c) for i, c in agora.items() if antes.get(i) != c}


def test_o_gemeo_que_chega_nao_move_quem_ficou(disco: Path) -> None:
    """Sem serial, o gêmeo que chega ou sai não move quem não se mexeu.

    O único mouse daquele modelo tem o ``id`` do modelo; quando chega o gêmeo,
    o modelo deixa de separar os dois, e a semente de quem ficou na 9-3 virava
    o caminho: o reexame dizia «Agora Está em 9-3» de quem não saiu dali.
    """
    _ler(_mouse("/sys/x/a", "9-3"))
    chegou = _ler(_mouse("/sys/x/a", "9-3"), _mouse("/sys/x/b", "9-4"), reexame=True)
    assert [c for _a, c in _mudaram(chegou).values()] == ["9-4"], (
        "o mouse que ficou na 9-3 foi listado como quem mudou de lugar: "
        f"{_mudaram(chegou)}")
    saiu = _ler(_mouse("/sys/x/a", "9-3"), reexame=True)
    assert _mudaram(saiu) == {}, f"o gêmeo saiu e o que ficou «mudou»: {_mudaram(saiu)}"
    # e o único, quando se move, continua reconhecido pelo modelo
    movido = _ler(_mouse("/sys/x/a", "9-5"), reexame=True)
    assert list(_mudaram(movido).values()) == [("9-3", "9-5")], _mudaram(movido)


def test_outro_modelo_no_caminho_de_quem_saiu_e_outro_aparelho(disco: Path) -> None:
    """Dois gêmeos saem e dois de outro modelo chegam: um deles, no mesmo caminho."""
    _ler(_mouse("/sys/x/a", "9-3"), _mouse("/sys/x/b", "9-4"))
    trocou = _ler(_mouse("/sys/x/c", "9-3", "4444", "0004"),
                  _mouse("/sys/x/d", "9-5", "4444", "0004"), reexame=True)
    assert sorted(c for _a, c in _mudaram(trocou).values()) == ["9-3", "9-5"], (
        "o aparelho de outro modelo que chegou na 9-3 herdou o id de quem saiu "
        f"dali, e o reexame não o viu chegar: {_mudaram(trocou)}")


def test_o_serial_nao_chega_a_pagina(disco: Path) -> None:
    """O ``id`` é um resumo com sal: nem o serial, nem o resumo sem sal."""
    import hashlib

    dado = _ler(_teclado("9-1"), _dongle("9-5"))
    corpo = json.dumps(dado, ensure_ascii=False)
    for serial in _SERIAIS.values():
        assert serial not in corpo, f"o serial {serial!r} foi à página"
        for semente in (serial, f"serial|1111:0001|{serial}", f"serial|2222:0002|{serial}"):
            cru = hashlib.blake2s(semente.encode(), digest_size=8).hexdigest()
            assert cru not in corpo, "o id é refazível sem o sal do processo"
    ids = {a["id"] for a in dado["aparelhos"]}
    assert all(i.startswith("ap-") for i in ids), ids
    assert set(dado["leituras"]["agora"]["caminho"]) == ids


# ── 2. o «Examinar» relê, e o «antes» é o que a página tinha ─────────────


def test_o_reexame_leva_a_leitura_anterior(disco: Path) -> None:
    aberta = _ler(_teclado("9-1"), _dongle("9-5"))
    assert aberta["leituras"]["antes"]["caminho"] == aberta["leituras"]["agora"]["caminho"], (
        "na abertura só existe uma leitura, e inventar outra mostraria movimentos")

    relida = _ler(_teclado("9-2"), _dongle("9-5"), reexame=True)
    teclado = next(a["id"] for a in relida["aparelhos"] if a["tipo"] == "Teclado")
    assert relida["leituras"]["antes"]["caminho"][teclado] == "9-1"
    assert relida["leituras"]["agora"]["caminho"][teclado] == "9-2"
    assert relida["leituras"]["antes"]["rotulo"] == arranjo_desta_maquina.ROTULO_DA_ANTERIOR

    # o próximo «Examinar» compara com ESTA, não com a da abertura
    outra = _ler(_teclado("9-2"), _dongle("9-5"), reexame=True)
    assert outra["leituras"]["antes"]["caminho"] == outra["leituras"]["agora"]["caminho"]


def test_o_gesto_reexaminar_devolve_o_arranjo_na_chave_da_entrega(
    disco: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O gesto lê pelas portas de sempre (aqui, de mentira) e não grava nada."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.integrations import censo_do_barramento
    from hefesto_dualsense4unix.interface import pacotes

    monkeypatch.setattr(censo_do_barramento, "ler_o_barramento",
                        lambda: _censo(_teclado("9-2")))
    monkeypatch.setattr(mapa_das_portas, "serial_do_no", _serial)
    reexaminar = pacotes.gesto_da_pagina(arranjo_desta_maquina.PAGINA, "reexaminar")
    assert reexaminar is not None, "o «Examinar» não tem dono"
    assert (arranjo_desta_maquina.PAGINA, "reexaminar") not in pacotes.GESTOS_QUE_MEXEM
    antes = disco.read_bytes()
    resposta = reexaminar(None, {}, None)
    assert disco.read_bytes() == antes, "o «Examinar» escreveu no disco dela"
    dado = resposta[arranjo_desta_maquina.CHAVE_DA_ENTREGA]
    assert dado["aparelhos"] and dado["leituras"]["agora"]["caminho"]

    assert gravar_maquina({"mapa": {"faces": []}})
    with pytest.raises(RuntimeError):
        reexaminar(None, {}, None)


def test_o_piloto_tira_o_arranjo_da_resposta_e_entrega_como_reexame() -> None:
    """A volta do gesto: o arranjo sai da carga e vai pela porta da abertura."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa o piloto, que carrega o GTK")
    from gi.repository import GLib

    from hefesto_dualsense4unix.interface import hefesto_vivo

    perguntas: list[str] = []

    def rodar_o_laco() -> None:
        contexto = GLib.MainContext.default()
        while contexto.iteration(False):
            pass

    class _Ponte:
        def perguntar(self, js: str, volta: Any) -> None:
            perguntas.append(js)

    class _Piloto:
        _arranjo_entregue = hefesto_vivo.Piloto._arranjo_entregue
        _entregar = hefesto_vivo.Piloto._entregar

        def __init__(self) -> None:
            self.pagina = arranjo_desta_maquina.PAGINA
            self.ponte = _Ponte()
            self.cegueiras: list[str] = []

    dado = {"quando": "x", "aparelhos": [], "faces": [], "mapa": {}, "leituras": {}}
    chave = arranjo_desta_maquina.CHAVE_DA_ENTREGA
    resto = hefesto_vivo.Piloto._o_arranjo_relido(
        _Piloto(), arranjo_desta_maquina.PAGINA, {chave: dado, "outro": 1})
    assert resto == {"outro": 1}, "o arranjo ficou na carga da pintura"
    rodar_o_laco()
    assert perguntas == [arranjo_desta_maquina.js_da_entrega(dado, reexame=True)]
    assert perguntas[0].endswith(", true)"), perguntas[0]

    outra = _Piloto()
    outra.pagina = "08-conexoes.html"
    hefesto_vivo.Piloto._o_arranjo_relido(
        outra, arranjo_desta_maquina.PAGINA, {chave: dado})
    rodar_o_laco()
    assert len(perguntas) == 1, "o arranjo foi entregue a outra página"
    # noutra página a chave é campo dela: segue para a pintura, inteira
    de_outra = {chave: "campo da 08", "outro": 2}
    assert hefesto_vivo.Piloto._o_arranjo_relido(
        outra, "08-conexoes.html", de_outra) is de_outra, (
        "o piloto comeu a chave de outra página como se fosse o arranjo do mapa")
    rodar_o_laco()
    assert len(perguntas) == 1, "o piloto tentou entregar um arranjo a outra página"

    # e é a volta do gesto que tira o arranjo da resposta, antes da pintura
    import inspect

    fonte = inspect.getsource(hefesto_vivo.Piloto._gesto)
    assert _A_VOLTA_DO_GESTO.search(fonte), (
        "o arranjo relido não sai da resposta antes de ela ir à pintura")


def test_a_primeira_entrega_nao_le_no_fio_da_janela(monkeypatch: pytest.MonkeyPatch) -> None:
    """A abertura lê o ``/sys`` num fio próprio e volta pelo laço do GTK."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa o piloto, que carrega o GTK")
    from gi.repository import GLib

    from hefesto_dualsense4unix.interface import hefesto_vivo

    quem_leu: list[threading.Thread] = []
    leu = threading.Event()
    dado = {"quando": "x", "aparelhos": [], "faces": [], "mapa": {}, "leituras": {}}

    def para_a_pagina() -> dict[str, Any]:
        quem_leu.append(threading.current_thread())
        leu.set()
        return dado

    monkeypatch.setattr(arranjo_desta_maquina, "para_a_pagina", para_a_pagina)
    perguntas: list[str] = []

    class _Ponte:
        def perguntar(self, js: str, volta: Any) -> None:
            perguntas.append(js)

    class _Piloto:
        _arranjo_entregue = hefesto_vivo.Piloto._arranjo_entregue
        _entregar = hefesto_vivo.Piloto._entregar

        def __init__(self) -> None:
            self.pagina = arranjo_desta_maquina.PAGINA
            self.ponte = _Ponte()
            self.cegueiras: list[str] = []

    hefesto_vivo.Piloto._entregar_o_arranjo(_Piloto())
    assert leu.wait(5), "a leitura não aconteceu"
    assert quem_leu[0] is not threading.main_thread(), (
        "o arranjo foi lido no fio da janela — o kernel enumerando um aparelho "
        "a congela por segundos")
    contexto = GLib.MainContext.default()
    for _ in range(200):
        if perguntas:
            break
        contexto.iteration(False)
        leu.wait(0.01)
    assert perguntas == [arranjo_desta_maquina.js_da_entrega(dado)], perguntas


#: A volta do gesto no piloto, como o `_gesto` a escreve: os nomes são
#: variáveis do código dele.
_A_VOLTA_DO_GESTO = re.compile(
    r"_deu_certo_dizendo\(\s*pagina, nome, alvo, "  # noqa-acento: código do piloto
    r"self\._o_arranjo_relido\(pagina, r\)\)")  # noqa-acento: código do piloto


# ── 3. a ponta do extensor grava; a entrada do hub desenhado não ─────────


def test_a_ponta_do_extensor_grava_como_a_entrada_filha(disco: Path) -> None:
    with pytest.raises(ValueError):
        ee.declarar_a_velocidade("3a", 2)  # a 3 não tem extensor
    assert ee.declarar_a_ligacao("3", "extensor").gravou
    assert ee.declarar_a_velocidade("3a", 2).gravou
    assert ee.declarar_a_ligacao("3a", "hub").gravou
    ponta = carregar_maquina().mapa.portas["3a"]
    assert (ponta.filha_de, ponta.usb, ponta.liga) == ("3", 2, "hub")

    dado = _ler(_teclado("9-1"))
    assert dado["declarado"]["3a"] == {"liga": "hub", "usb": 2}
    traseira = next(f for f in dado["faces"] if f["nome"] == "Traseira")
    tres = next(p for p in traseira["portas"] if p["n"] == "3")
    assert tres["filho"]["n"] == "3a" and tres["filho"]["usb"] == 2
    hub = ee.FACE_DO_HUB_DECLARADO.format(numero="3a")
    assert hub in {f["nome"] for f in dado["faces"]}, "o hub na ponta não voltou ao reler"

    for numero in ("3aa", "5.1", "3a.1"):
        with pytest.raises(ValueError):
            ee.declarar_a_velocidade(numero, 3)

    # «Direto» na 3: a ponta que só o editor escreveu sai junto
    assert ee.declarar_a_ligacao("3", None).gravou
    assert "3a" not in carregar_maquina().mapa.portas
    dado = _ler(_teclado("9-1"))
    assert "3a" not in dado["declarado"]
    assert hub not in {f["nome"] for f in dado["faces"]}


def test_a_ponta_herda_a_velocidade_de_quem_a_hospeda(disco: Path) -> None:
    """Declarar só o «Hub» na ponta não a pinta de USB 2.0 ao reler."""
    assert ee.declarar_a_velocidade("3", 3).gravou
    assert ee.declarar_a_ligacao("3", "extensor").gravou
    antes = _ler()
    assert ee.declarar_a_ligacao("3a", "hub").gravou
    depois = _ler()

    def ponta(dado: dict[str, Any]) -> int:
        traseira = next(f for f in dado["faces"] if f["nome"] == "Traseira")
        return next(p for p in traseira["portas"] if p["n"] == "3")["filho"]["usb"]

    assert ponta(antes) == ponta(depois) == 3


def test_a_ponta_com_aparelho_mapeado_nao_sai_com_o_direto(disco: Path) -> None:
    """A filha que o Mapear amarrou (caminho) é dado do Mapear, e fica."""
    mapa = _mapa(e3={"liga": "extensor"})
    mapa.portas["3a"] = PortaDeclarada(caminho="9-7", filha_de="3")
    assert gravar_maquina({"mapa": mapa.model_dump(mode="json")})
    assert ee.declarar_a_ligacao("3", None).gravou
    assert carregar_maquina().mapa.portas["3a"].caminho == "9-7"


# ── 4. a página, no WebKit, pela ponte do piloto ─────────────────────────

_LER = r"""
(function(){
  const plugs = {};
  for (const p of document.querySelectorAll('.plug[data-porta]')) {
    plugs[p.dataset.porta] = p.classList.contains('v3');
  }
  const ed = document.getElementById('edita');
  const botoes = ed && !ed.hidden
    ? [...ed.querySelectorAll('button[data-liga],button[data-usb]')] : [];
  const hub = botoes.filter(b => b.dataset.liga === 'hub')[0];
  const painel = document.getElementById('painel');
  const pressionado = document.querySelector('.modo[aria-pressed="true"]');
  return JSON.stringify({
    v3: plugs,
    faces: [...document.querySelectorAll('.face-cab h3')].map(h => h.textContent.trim()),
    editor: !!(ed && !ed.hidden),
    linhas: ed && !ed.hidden ? ed.querySelectorAll('.edita-linha').length : 0,
    gestos: botoes.filter(b => b.dataset.gesto).map(
      b => b.dataset.gesto + ':' + (b.dataset.liga || b.dataset.usb) + '@' + b.dataset.entrada),
    hub: hub ? {classe: hub.className, cinza: hub.getAttribute('aria-disabled'),
                dica: hub.getAttribute('title'), gesto: hub.dataset.gesto || ''} : null,
    apertados: botoes.filter(b => b.getAttribute('aria-pressed') === 'true').map(
      b => b.dataset.liga || b.dataset.usb),
    modo: pressionado ? pressionado.dataset.modo : '',
    painel: painel ? painel.innerText.replace(/\s+/g, ' ').trim() : '',
    examinar: (document.querySelector('.topo #reexaminar') || {dataset: {}}).dataset.gesto || '',
  });
})()
"""


def _clicar(seletor: str) -> str:
    alvo = json.dumps(seletor)
    return (f"(function(){{const b=document.querySelector({alvo});"
            f"if(!b){{return 'sem ' + {alvo};}} b.click(); return 'clicou';}})()")


def _na_pagina(passos: list[str]) -> tuple[list[Any], list[dict[str, Any]]]:
    """A página publicada num WebKit fora da tela (``_na_pagina_sem_recolher``),
    e o lixo do WebKit recolhido aqui, no fio do GTK.

    Deixado para o coletor, ele era recolhido no fio de outro teste (medido no
    CI de 26/09: ``Garbage-collecting`` no ``sensor_hub._loop_manutencao``), e o
    GTK abortava o processo inteiro com ``Fatal Python error: Aborted``.
    """
    try:
        return _na_pagina_sem_recolher(passos)
    finally:
        gc.collect()
        from gi.repository import Gtk

        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


def _na_pagina_sem_recolher(passos: list[str]) -> tuple[list[Any], list[dict[str, Any]]]:
    """A página PUBLICADA num WebKit fora da tela, com o BOOTSTRAP do piloto.

    Devolve o que cada passo respondeu (JSON já lido) e as mensagens que a
    página mandou pelo canal do piloto. ``Gtk.OffscreenWindow``: janela de
    teste não nasce na tela dela.
    """
    from tests.conftest import exigir_gi_real

    exigir_gi_real("abre a página num WebKit")
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    from hefesto_dualsense4unix.interface import hefesto_vivo

    mensagens: list[dict[str, Any]] = []
    respostas: list[str] = []
    ucm = WebKit2.UserContentManager()
    ucm.register_script_message_handler("hefesto")
    ucm.connect("script-message-received::hefesto",
                lambda _u, r: mensagens.append(json.loads(r.get_js_value().to_string())))
    view = WebKit2.WebView.new_with_user_content_manager(ucm)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1400, 1000)
    janela.add(view)
    janela.show_all()
    fila = [hefesto_vivo.BOOTSTRAP, *passos]

    def seguinte() -> bool:
        if not fila:
            GLib.timeout_add(400, lambda: (Gtk.main_quit(), False)[1])
            return False
        js = fila.pop(0)

        def respondeu(v: Any, res: Any, _u: Any = None) -> None:
            try:
                respostas.append(v.evaluate_javascript_finish(res).to_string())
            except Exception as erro:  # a exceção É a resposta do passo
                respostas.append(f"ERRO {erro}")
            GLib.idle_add(seguinte)

        view.evaluate_javascript(js, -1, None, None, None, respondeu, None)
        return False

    def carregou(_v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            seguinte()

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(arranjo_desta_maquina.PAGINA, publicado=True).as_uri())
    guarda = GLib.timeout_add(30000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(respostas) == len(passos) + 1, f"o WebKit parou no meio: {respostas}"
    assert respostas[0] == "ok", f"o BOOTSTRAP do piloto não instalou: {respostas[0]}"
    lidas = [json.loads(r) if r.startswith("{") else r for r in respostas[1:]]
    return lidas, mensagens


def _js(dado: dict[str, Any], reexame: bool = False) -> str:
    return arranjo_desta_maquina.js_da_entrega(dado, reexame=reexame)


def _hub(caminho: str) -> Aparelho:
    return replace(_aparelho("/sys/x/hub", caminho, "5555", "0005", "Hub",
                             ("09", "00", "00"), "Hub de prova"), e_hub=True)


def _webcam(caminho: str) -> Aparelho:
    return _aparelho("/sys/x/webcam", caminho, "4444", "0004", "Webcam",
                     ("0e", "01", "00"), "Webcam de prova")


def test_o_examinar_na_pagina_diz_quem_mudou_de_lugar(disco: Path) -> None:
    """O teclado sai da 1 e vai para a 2, e uma webcam chega no hub.

    O «Examinar» diz os dois, com o caminho e a entrada: o teclado «estava»
    na 1; a webcam não estava em lugar nenhum («Estava em undefined» era o
    que a página dizia de quem chegou), e ela está no hub — a região se acha
    pela classe, não pelo `id` "hub" do exemplo.
    """
    aberta = _ler(_teclado("9-1"), _dongle("9-5"), _hub("9-3"))
    relida = _ler(_teclado("9-2"), _dongle("9-5"), _hub("9-3"), _webcam("9-3.1"),
                  reexame=True)
    lidas, mensagens = _na_pagina([
        _LER,
        _js(aberta),
        _LER,
        _clicar(".topo #reexaminar"),
        _LER,
        _js(relida, reexame=True),
        _LER,
    ])
    exemplo, _, entregue, _, no_clique, entrega, depois = lidas
    assert exemplo["examinar"] == "", "no exemplo o «Examinar» não tem o que pedir ao produto"
    assert entregue["examinar"] == "reexaminar", "o «Examinar» do produto não leva o gesto"
    pedidos = [m for m in mensagens if m.get("gesto") == "reexaminar"]
    assert len(pedidos) == 1, f"o clique não chegou ao piloto: {mensagens}"
    assert no_clique["modo"] != "reexame" and "Nada Mudou" not in no_clique["painel"], (
        "a página pintou o reexame antes de a leitura nova chegar: " + no_clique["painel"])
    assert entrega == "ok", entrega
    texto = depois["painel"]
    assert "2 Aparelhos Mudaram de Lugar" in texto and "Nada Mudou" not in texto, texto
    assert re.search(r"Estava em 9-1 \(Entrada 1\), Agora Está em 9-2 \(Entrada 2\)", texto), texto
    assert "undefined" not in texto.lower(), texto
    assert "Agora Está em 9-3.1" in texto, texto
    assert "Por Que 1 Ficou Sem Entrada" in texto, texto
    assert "Está no Hub" in texto and "Direto no Gabinete" not in texto, (
        "a webcam está no hub, e o reexame a põe direto no gabinete: " + texto)
    assert "Dongle" not in texto, "o dongle não saiu da 5, e o reexame o acusa"


def test_o_ja_movi_das_sugestoes_tambem_rele(disco: Path) -> None:
    """O «Já movi» das Sugestões é o mesmo «Examinar»: no produto, leva o gesto."""
    aberta = _ler(_teclado("9-1"), _dongle("9-5"), _webcam("9-4"))
    lidas, mensagens = _na_pagina([
        _js(aberta),
        _clicar('.modo[data-modo="ideal"]'),
        _LER_O_JA_MOVI,
        _clicar("#painel #reexaminar"),
        _LER,
    ])
    ja_movi, depois = lidas[2], lidas[4]
    assert ja_movi == "reexaminar", (
        f"no produto o «Já movi» não leva o gesto, e fica morto: {ja_movi!r}")
    assert [m for m in mensagens if m.get("gesto") == "reexaminar"], (
        f"o clique no «Já movi» não chegou ao piloto: {mensagens}")
    assert depois["modo"] == "ideal" and "Nada Mudou" not in depois["painel"], (
        "o «Já movi» pintou o reexame antes de a leitura nova chegar")


def test_o_reexame_guarda_o_que_ela_ensinou_na_tela(disco: Path) -> None:
    """Ela ensina que a webcam está na 4, e o «Examinar» não desfaz isso."""
    aberta = _ler(_teclado("9-1"), _dongle("9-5"), _webcam("9-4"))
    relida = _ler(_teclado("9-2"), _dongle("9-5"), _webcam("9-4"), reexame=True)
    webcam = next(a["id"] for a in aberta["aparelhos"] if a["tipo"] == "Webcam")
    lidas, _ = _na_pagina([
        _js(aberta),
        _clicar(f'.chip[data-ap="{webcam}"]'),
        _clicar('.plug[data-porta="4"]'),
        _LER,
        _js(relida, reexame=True),
        _LER,
        _clicar("#voltar-leitura"),
        _LER,
    ])
    ensinado, reexame, fechado = lidas[3], lidas[5], lidas[7]
    assert "4 de 5 Entradas Mapeadas" in ensinado["painel"], ensinado["painel"]
    assert "Webcam" not in reexame["painel"], (
        "a webcam não saiu da 4, e o reexame a lista: " + reexame["painel"])
    assert "4 de 5 Entradas Mapeadas" in fechado["painel"], (
        "o «Examinar» jogou fora o que ela ensinou nesta tela: " + fechado["painel"])
    assert "Fora do Mapa" not in fechado["painel"], fechado["painel"]


def test_o_hub_de_verdade_na_entrada_nao_apaga_o_hub(disco: Path) -> None:
    """Um hub direto na 3 é hub: ali o «Hub» continua oferecido, e grava."""
    mapa = _mapa()
    mapa.portas["3"] = PortaDeclarada(caminho="9-3")
    assert gravar_maquina({"mapa": mapa.model_dump(mode="json")})
    aberta = _ler(_teclado("9-1"), _hub("9-3"))
    lidas, _ = _na_pagina([_js(aberta), _clicar('.plug[data-porta="3"]'), _LER])
    hub = lidas[2]["hub"]
    assert hub is not None and hub["cinza"] is None, (
        f"o hub de verdade na 3 apagou o «Hub»: {hub}")
    assert hub["gesto"] == "entrada-o-que-tem", hub


#: O gesto do «Já movi» das Sugestões — o segundo botão com o id `reexaminar`.
_LER_O_JA_MOVI = (
    "(function(){const b=document.querySelector('#painel #reexaminar');"
    "return b ? (b.dataset.gesto || '') : 'sem o botão';})()")


def test_o_examinar_do_exemplo_continua_na_pagina() -> None:
    """Sem a leitura desta máquina, o reexame é o das duas leituras do exemplo."""
    lidas, mensagens = _na_pagina([_clicar(".topo #reexaminar"), _LER])
    painel = lidas[1]["painel"]
    assert "Mudou de Lugar" in painel or "Mudaram de Lugar" in painel, painel
    assert not [m for m in mensagens if m.get("gesto") == "reexaminar"], (
        "o exemplo pediu ao produto uma leitura que ele não tem")


def test_o_hub_fica_cinza_onde_ha_um_aparelho_direto(disco: Path) -> None:
    """Dongle direto na 5: o «Hub» da 5 é cinza, diz por quê, e não grava."""
    aberta = _ler(_teclado("9-1"), _dongle("9-5"))
    lidas, mensagens = _na_pagina([
        _js(aberta),
        _clicar('.plug[data-porta="5"]'),
        _LER,
        _clicar('#edita [data-liga="hub"]'),
        _LER,
        _clicar('.plug[data-porta="3"]'),
        _LER,
    ])
    _, _, na_5, _, depois, _, na_3 = lidas
    assert na_5["hub"] is not None, na_5
    assert na_5["hub"]["cinza"] == "true" and "apagado" in na_5["hub"]["classe"], na_5["hub"]
    assert na_5["hub"]["dica"] == "Bluetooth Está Direto Nesta Entrada", na_5["hub"]
    assert na_5["hub"]["gesto"] == "", "o «Hub» cinza leva o gesto ao disco"
    assert not [m for m in mensagens if m.get("liga") == "hub"], mensagens
    assert ee.FACE_DO_HUB_DECLARADO.format(numero="5") not in depois["faces"]
    assert carregar_maquina().mapa.portas["5"].liga is None
    # a entrada vazia continua oferecendo o hub
    assert na_3["hub"] is not None and na_3["hub"]["cinza"] is None, na_3["hub"]
    assert na_3["hub"]["gesto"] == "entrada-o-que-tem"


def test_a_sugestao_nunca_manda_para_dentro_do_hub_desenhado(disco: Path) -> None:
    """O caso medido: dongle direto na 5 e hub declarado na 5 (antes da cura)."""
    assert ee.declarar_a_ligacao("5", "hub").gravou
    aberta = _ler(_teclado("9-1"), _dongle("9-5"))
    hub = ee.FACE_DO_HUB_DECLARADO.format(numero="5")
    assert hub in {f["nome"] for f in aberta["faces"]}
    lidas, _ = _na_pagina([
        _js(aberta),
        _clicar('.modo[data-modo="ideal"]'),
        _LER,
    ])
    sugestoes = lidas[2]["painel"]
    assert lidas[2]["modo"] == "ideal", lidas[2]
    assert not re.search(r"para a 5\.\d", sugestoes, re.I), (
        "a Sugestão mandou um aparelho para dentro do hub desenhado: " + sugestoes)


def test_a_ponta_grava_pela_pagina_e_a_entrada_do_hub_nao_abre(disco: Path) -> None:
    """Extensor na 3 → a ponta 3a leva o gesto; hub na 4 → a 4.1 não edita.

    A 3 não tem nó gravado, e a velocidade dela é USB 2.0: a ponta herda isso.
    Ela diz USB 3.0 na ponta, e é o azul da ponta relida que prova o disco.
    """
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface import pacotes

    aberta = _ler(_teclado("9-1"))
    lidas, mensagens = _na_pagina([
        _js(aberta),
        _clicar('.plug[data-porta="3"]'),
        _clicar('#edita [data-liga="extensor"]'),
        _clicar('.plug[data-porta="3a"]'),
        _LER,
        _clicar('#edita [data-usb="3"]'),
        _clicar('.plug[data-porta="4"]'),
        _clicar('#edita [data-liga="hub"]'),
        _clicar('.plug[data-porta="4.1"]'),
        _LER,
    ])
    na_ponta, na_hub = lidas[4], lidas[9]
    assert "entrada-velocidade:3@3a" in na_ponta["gestos"], na_ponta["gestos"]
    assert na_ponta["v3"]["3a"] is False, "a ponta de uma entrada USB 2.0 nasceu azul"
    assert na_hub["editor"] is False, "a entrada do hub desenhado abriu o editor sem gravar"
    pedidos = [m for m in mensagens if m.get("gesto", "").startswith("entrada-")]
    assert [(m["gesto"], m.get("entrada")) for m in pedidos] == [
        ("entrada-o-que-tem", "3"), ("entrada-velocidade", "3a"),
        ("entrada-o-que-tem", "4")], pedidos
    for m in pedidos:
        de_onde = m["pagina"]  # noqa-acento: chave ASCII da mensagem do piloto
        dono = pacotes.gesto_da_pagina(de_onde, m["gesto"])
        assert dono is not None
        dono(None, m, None)
    assert carregar_maquina().mapa.portas["3a"].usb == 3

    relida, _ = _na_pagina([
        _js(_ler(_teclado("9-1"))),
        _clicar('.plug[data-porta="3a"]'),
        _LER,
    ])
    assert relida[2]["v3"]["3a"] is True, "a ponta relida não é azul, e ela disse USB 3.0"
    assert relida[2]["v3"]["3"] is False, "a mãe mudou de velocidade junto com a ponta"
    assert "3" in relida[2]["apertados"], relida[2]
