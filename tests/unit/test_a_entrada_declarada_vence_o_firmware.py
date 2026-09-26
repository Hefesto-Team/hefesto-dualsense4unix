"""A entrada declarada vence o firmware — e o editor do mapa grava no disco dela.

O-MAPA-DAS-CONEXOES-NO-PRODUTO-01, 26/09/2026. A resposta dela, olhando a cor
do plástico: as duas entradas da frente são azuis (USB 3.0) e as 7 e 8 de trás
são pretas (USB 2.0). O ``maquina.json`` dizia USB 2.0 na frente, porque a
velocidade vinha do par SuperSpeed (``peer``) que a tabela ACPI da placa liga
a cada entrada — e a placa erra. A cura: o que ela declara no editor da entrada
vence o ``peer``, e um aparelho USB 3 enumerado na entrada vence os dois.

TUDO AQUI É DE MENTIRA E DE NINGUÉM: barramentos ``usb9``/``usb10``, caminhos
``9-*``/``10-*``, e o ``maquina.json`` no ``tmp_path`` que o ``conftest``
desvia. Nada da bancada dela entra no código: a declaração é dado de quem usa.

A MORDIDA (E2 da sprint): arranque a leitura do declarado — o ``declarada`` do
``_rapido_do_no`` ou o ``_o_que_ela_declarou_nas_entradas`` do
``arranjo_desta_maquina`` — e as réguas de baixo reprovam.
"""

from __future__ import annotations

import json
import re
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
from hefesto_dualsense4unix.integrations.entradas_do_gabinete import NoDeEntrada
from hefesto_dualsense4unix.interface import arranjo_desta_maquina, onde, pagina_do_mapa
from hefesto_dualsense4unix.utils.maquina import (
    FaceDeclarada,
    MapaDaMesa,
    MaquinaConfig,
    PortaDeclarada,
    caminho_da_maquina,
    carregar_maquina,
    gravar_maquina,
)

#: O barramento lento e o rápido de uma placa de mentira.
_LENTO, _RAPIDO = "usb9", "usb10"

#: As entradas de mentira, e o que o firmware liga a cada uma. A 1 é a da
#: frente: a placa não publicou o par SuperSpeed dela, então o firmware diz
#: USB 2.0. A 7 é a de trás: a placa diz que ela tem o lado rápido.
_NOS = {
    "1": [f"{_LENTO}-port4"],
    "5": [f"{_LENTO}-port5", f"{_RAPIDO}-port1"],
    "7": [f"{_LENTO}-port6", f"{_RAPIDO}-port2"],
}


def _censo(*aparelhos: Aparelho) -> Censo:
    return Censo(
        aparelhos=aparelhos,
        barramentos=(
            Barramento(no=f"/sys/{_LENTO}", nome_do_kernel=_LENTO, velocidade_mbps=480.0),
            Barramento(no=f"/sys/{_RAPIDO}", nome_do_kernel=_RAPIDO, velocidade_mbps=5000.0),
        ),
    )


def _aparelho(caminho: str, mbps: float = 480.0) -> Aparelho:
    return Aparelho(
        no=f"/sys/{caminho}", nome_do_kernel=caminho, produto="Aparelho de prova",
        especie="Teclado", classe="03", subclasse="01", protocolo="01",
        velocidade_mbps=mbps,
    )


def _mapa(**declarado: dict[str, Any]) -> MapaDaMesa:
    portas = {
        numero: PortaDeclarada(nos=nos, **declarado.get(f"e{numero}", {}))
        for numero, nos in _NOS.items()
    }
    return MapaDaMesa(
        faces=[FaceDeclarada(nome="Frente", portas=["1"], perto=True),
               FaceDeclarada(nome="Traseira", portas=["5", "7"])],
        portas=portas,
    )


def _usb(bancada: mapa_das_portas.Bancada) -> dict[str, int]:
    return {e.n: e.usb for f in bancada.mesa.faces for e in f.entradas}


# ── 1. a precedência: aparelho, ela, placa ───────────────────────────────


def test_a_velocidade_declarada_vence_o_par_do_firmware() -> None:
    """O ``peer`` diz 2.0 na frente e ela diz 3.0: vale o que ela disse.

    O CONTROLE vem primeiro, e é ele que impede o verde por vacuidade: sem
    declaração, a frente sai 2.0 e a de trás 3.0 — o firmware, como antes.
    """
    sem = _usb(mapa_das_portas.mesa_do_motor(_mapa(), _censo()))
    assert sem == {"1": 2, "5": 3, "7": 3}, f"o firmware de mentira não diz o que devia: {sem}"

    com = _usb(mapa_das_portas.mesa_do_motor(
        _mapa(e1={"usb": 3}, e7={"usb": 2}), _censo()))
    assert com["1"] == 3, "ela disse USB 3.0 na frente, e o par do firmware venceu"
    assert com["7"] == 2, "ela disse USB 2.0 atrás, e o par do firmware venceu"
    assert com["5"] == 3, "a entrada que ela não declarou mudou sozinha"


def test_o_aparelho_usb3_na_entrada_vence_a_declaracao() -> None:
    """Medição vence os dois: um aparelho a 5000M no lado rápido da 7."""
    bancada = mapa_das_portas.mesa_do_motor(
        _mapa(e7={"usb": 2}), _censo(_aparelho("10-2", 5000.0)))
    assert _usb(bancada)["7"] == 3
    assert mapa_das_portas.velocidade_da_entrada(False, 2, True) == (
        True, mapa_das_portas.USB_PELO_APARELHO)
    assert mapa_das_portas.velocidade_da_entrada(False, 3) == (
        True, mapa_das_portas.USB_DECLARADA)
    assert mapa_das_portas.velocidade_da_entrada(True, None) == (
        True, mapa_das_portas.USB_PELA_PLACA)
    assert mapa_das_portas.velocidade_da_entrada(None, None) == (None, "")


def test_o_arranjo_da_pagina_pinta_a_velocidade_que_ela_disse() -> None:
    """A página recebe o USB 3.0 da frente — é isso que a pinta de azul."""
    documento = MaquinaConfig(mapa=_mapa(e1={"usb": 3}))
    veio = arranjo_desta_maquina.arranjo(
        carregar=lambda: documento, ler_o_barramento=_censo)
    assert veio is not None
    usb = {p["n"]: p["usb"] for f in veio["faces"] for p in f["portas"]}
    assert usb["1"] == 3
    assert veio["declarado"]["1"] == {"usb": 3}


# ── 2. o editor grava no disco dela, e o produto lê de lá ────────────────


@pytest.fixture()
def disco(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta régua mora no ``tmp_path`` — conferido antes."""
    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    assert gravar_maquina({"mapa": _mapa().model_dump(mode="json")})
    return alvo


def test_declarar_hub_grava_e_a_face_do_hub_volta_ao_reler(disco: Path) -> None:
    """E1: «Hub» na 5 e «USB 2.0» na 7 gravam; relida, a página mostra os dois."""
    assert ee.declarar_a_ligacao("5", "hub").gravou
    assert ee.declarar_a_velocidade("7", 2).gravou

    bruto = json.loads(disco.read_text(encoding="utf-8"))
    assert bruto["mapa"]["portas"]["5"]["liga"] == "hub"
    assert bruto["mapa"]["portas"]["7"]["usb"] == 2
    assert bruto["mapa"]["portas"]["5"]["nos"] == _NOS["5"], (
        "declarar o hub apagou os nós que o Mapear tinha gravado")

    veio = arranjo_desta_maquina.arranjo(
        carregar=carregar_maquina, ler_o_barramento=_censo)
    assert veio is not None
    hub = ee.FACE_DO_HUB_DECLARADO.format(numero="5")
    faces = {f["nome"]: f for f in veio["faces"]}
    assert hub in faces, f"a face do hub não voltou ao reler: {sorted(faces)}"
    assert faces[hub]["daEntrada"] == "5"
    assert len(faces[hub]["portas"]) == arranjo_desta_maquina.ENTRADAS_DO_HUB_DECLARADO
    usb = {p["n"]: p["usb"] for f in veio["faces"] for p in f["portas"]}
    assert usb["7"] == 2, "a 7 não é preta no desenho, e ela disse USB 2.0"
    assert veio["declarado"]["5"] == {"liga": "hub"}

    # «Direto» desfaz, e a face some — sem apagar os nós da entrada
    assert ee.declarar_a_ligacao("5", None).gravou
    veio = arranjo_desta_maquina.arranjo(
        carregar=carregar_maquina, ler_o_barramento=_censo)
    assert veio is not None
    assert hub not in {f["nome"] for f in veio["faces"]}
    assert carregar_maquina().mapa.portas["5"].nos == _NOS["5"]


def test_o_extensor_declarado_vira_a_entrada_filha(disco: Path) -> None:
    assert ee.declarar_a_ligacao("1", "extensor").gravou
    veio = arranjo_desta_maquina.arranjo(
        carregar=carregar_maquina, ler_o_barramento=_censo)
    assert veio is not None
    frente = next(f for f in veio["faces"] if f["nome"] == "Frente")
    filho = frente["portas"][0].get("filho")
    assert filho is not None, "o extensor declarado não virou entrada-filha"
    assert filho["n"] == "1a" and filho["esticada"] is True
    assert filho["cabo"] == arranjo_desta_maquina.CABO_DECLARADO


def test_a_entrada_fora_do_mapa_nao_grava(disco: Path) -> None:
    """A do hub (``5.1``) e a do exemplo não têm número no disco dela."""
    antes = disco.read_bytes()
    for numero in ("5.1", "99"):
        with pytest.raises(ValueError):
            ee.declarar_a_ligacao(numero, "hub")
        with pytest.raises(ValueError):
            ee.declarar_a_velocidade(numero, 3)
    with pytest.raises(ValueError):
        ee.declarar_a_velocidade("7", 4)
    with pytest.raises(ValueError):
        ee.declarar_a_ligacao("7", "mesa")
    assert disco.read_bytes() == antes, "uma recusa escreveu no disco dela"


def test_os_dois_gestos_gravam_o_que_o_clique_diz(disco: Path) -> None:
    """O clique da página chega ao pacote e vai ao disco — «Direto» desfaz."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface import pacotes

    o_que_tem = pacotes.gesto_da_pagina(arranjo_desta_maquina.PAGINA, "entrada-o-que-tem")
    velocidade = pacotes.gesto_da_pagina(arranjo_desta_maquina.PAGINA, "entrada-velocidade")
    assert o_que_tem is not None and velocidade is not None, "o editor não tem dono"
    o_que_tem(None, {"entrada": "5", "liga": "hub"}, None)
    velocidade(None, {"entrada": "1", "usb": "3"}, None)
    portas = carregar_maquina().mapa.portas
    assert (portas["5"].liga, portas["1"].usb) == ("hub", 3)
    o_que_tem(None, {"entrada": "5", "liga": "direto"}, None)
    assert carregar_maquina().mapa.portas["5"].liga is None
    for clique in ({"liga": "hub"}, {"entrada": "5", "liga": ""}):
        with pytest.raises(ValueError):
            o_que_tem(None, clique, None)
    with pytest.raises(ValueError):
        velocidade(None, {"entrada": "1", "usb": ""}, None)


# ── 3. o Mapear diz de onde veio a velocidade e oferece o hub ────────────


def _no(no: str, aparelho: str = "", mbps: float = 480.0, par: str = "") -> NoDeEntrada:
    hub = no.rpartition("-port")[0]
    return NoDeEntrada(
        no=no, caminho_sysfs=f"/sys/{no}", hub=hub, numero=int(no.rpartition("port")[2]),
        estado="" if aparelho else "not attached", par=par, aparelho=aparelho,
        velocidade_mbps=mbps,
    )


def test_o_mapear_pinta_a_velocidade_declarada_e_oferece_o_hub() -> None:
    maquina = MaquinaConfig(mapa=_mapa(e1={"usb": 3}, e5={"liga": "hub"}, e7={"usb": 2}))
    entradas = (
        _no(f"{_LENTO}-port4"),
        _no(f"{_LENTO}-port5", par=f"{_RAPIDO}-port1"),
        _no(f"{_RAPIDO}-port1", mbps=5000.0, par=f"{_LENTO}-port5"),
        _no(f"{_LENTO}-port6", par=f"{_RAPIDO}-port2"),
        _no(f"{_RAPIDO}-port2", mbps=5000.0, par=f"{_LENTO}-port6"),
    )
    mapa = ee.ler_o_mapa(maquina=maquina, censo=_censo(), entradas=entradas,
                         adaptadores=(), medir_storm=False)
    por_numero = {p.numero: p for p in mapa.portas if p.numero}
    assert (por_numero["1"].usb, por_numero["1"].usb_de) == (
        mapa_das_portas.USB_3, mapa_das_portas.USB_DECLARADA)
    assert (por_numero["7"].usb, por_numero["7"].usb_de) == (
        mapa_das_portas.USB_2, mapa_das_portas.USB_DECLARADA)
    assert (por_numero["5"].usb, por_numero["5"].usb_de) == (
        mapa_das_portas.USB_3, mapa_das_portas.USB_PELA_PLACA)
    hub = ee.FACE_DO_HUB_DECLARADO.format(numero="5")
    assert hub in mapa.lugares, "o Mapear não oferece o hub que ela declarou"
    assert ee._face_aceita(hub, maquina), "o Mapear oferece o hub e recusa gravar nele"


# ── 4. a página e o produto desenham a MESMA coisa ───────────────────────


def test_a_pagina_e_o_produto_desenham_o_mesmo_hub_e_o_mesmo_extensor() -> None:
    """Antes de reler, quem desenha é o JavaScript; depois, o Python.

    Se as duas pontas disserem coisas diferentes, o que ela viu ao clicar
    muda sozinho quando a janela reabre.
    """
    pagina = pagina_do_mapa.pagina()
    prefixo = ee.FACE_DO_HUB_DECLARADO.format(numero="")
    assert f'"{prefixo}" + n' in pagina, "o hub da página tem outro nome"
    tamanho = arranjo_desta_maquina.ENTRADAS_DO_HUB_DECLARADO
    quatro = ", ".join(str(i) for i in range(1, tamanho + 1))
    assert f"[{quatro}].map(function (i)" in pagina, "o hub da página tem outro tamanho"
    assert f'cabo: "{arranjo_desta_maquina.CABO_DECLARADO}"' in pagina


def test_a_pagina_manda_os_dois_gestos_e_eles_tem_dono() -> None:
    """Os dois gestos do editor saem da página e chegam a quem grava."""
    pagina = pagina_do_mapa.pagina()
    produto = onde.pagina(arranjo_desta_maquina.PAGINA, publicado=True)
    assert produto.read_text(encoding="utf-8") == pagina_do_mapa.pagina(com_as_que_esperam=False)
    gestos = set(re.findall(r'gravaNaEntrada\(editando, "([a-z-]+)"\)', pagina))
    assert gestos == {"entrada-o-que-tem", "entrada-velocidade"}, gestos
    fonte = (Path(ee.__file__).parents[1] / "interface" / "pacotes"
             / "a12_mapa_das_portas.py").read_text(encoding="utf-8")
    for nome in gestos:
        assert f'@gesto(PAGINA, "{nome}"' in fonte, f"o gesto {nome} não tem dono"
    assert "GRAVA = Object.keys(DECLARADO);" in pagina, (
        "a página deixou de saber quais entradas o editor grava")


# ── 5. o clique na página chega ao disco — no WebKit, pela ponte do piloto ──
#
# As réguas de cima medem o gravador e o arranjo, e a de cima desta lê o
# JavaScript como TEXTO. Nenhuma clicava: a conferência de 26/09/2026 arrancou
# o `gravaNaEntrada` inteiro (o botão nunca leva o gesto) e o `_declarado`
# passou a mandar só as entradas que JÁ tinham declaração — o que deixa quem
# nunca declarou nada sem gravar coisa alguma —, e as dez passaram. Esta régua
# abre a página PUBLICADA num WebKit fora da tela, instala o BOOTSTRAP do
# piloto (o mesmo ouvinte de clique que o produto usa), entrega o arranjo,
# clica, leva cada mensagem ao pacote como o piloto leva, e relê.

_LER_A_PAGINA = r"""
(function(){
  const plugs = {};
  for (const p of document.querySelectorAll('.plug[data-porta]')) {
    plugs[p.dataset.porta] = p.classList.contains('v3');
  }
  const ed = document.getElementById('edita');
  const botoes = ed && !ed.hidden
    ? [...ed.querySelectorAll('button[data-liga],button[data-usb]')] : [];
  return JSON.stringify({
    faces: [...document.querySelectorAll('.face-cab h3')].map(h => h.textContent.trim()),
    v3: plugs,
    quando: !!document.getElementById('de-quando'),
    gestos: botoes.filter(b => b.dataset.gesto).map(
      b => b.dataset.gesto + ':' + (b.dataset.liga || b.dataset.usb) + '@' + b.dataset.entrada),
    apertados: botoes.filter(b => b.getAttribute('aria-pressed') === 'true').map(
      b => b.dataset.liga || b.dataset.usb),
  });
})()
"""


def _clicar(seletor: str) -> str:
    alvo = json.dumps(seletor)
    return (f"(function(){{const b=document.querySelector({alvo});"
            f"if(!b){{return 'sem ' + {alvo};}} b.click(); return 'clicou';}})()")


def _na_pagina(passos: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    """Abre a página publicada, instala o BOOTSTRAP e roda os ``passos`` em ordem.

    Devolve o que cada passo respondeu e as mensagens que a página mandou pelo
    canal do piloto. ``Gtk.OffscreenWindow``: sob Xvfb uma janela comum fica
    1x1, e ela tem UMA tela — janela de teste não nasce na frente dela.

    O canal é montado aqui, com o WebKit cru, e não pela ``PonteDaTela`` da
    janela GTK que está saindo (D-0609-GTK-LEVA-INTEIRA): o que a régua precisa
    é do nome que o BOOTSTRAP pronuncia, ``messageHandlers.hefesto``.
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
    ucm.register_script_message_handler("hefesto")  # a série 4.1 leva UM argumento
    ucm.connect("script-message-received::hefesto",
                lambda _u, r: mensagens.append(json.loads(r.get_js_value().to_string())))
    view = WebKit2.WebView.new_with_user_content_manager(ucm)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1200, 900)
    janela.add(view)
    janela.show_all()
    fila = [hefesto_vivo.BOOTSTRAP, *passos]

    def seguinte() -> bool:
        if not fila:
            # as mensagens do último clique atravessam a ponte depois da resposta
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
    return respostas[1:], mensagens


def _entregar() -> str:
    veio = arranjo_desta_maquina.arranjo(carregar=carregar_maquina, ler_o_barramento=_censo)
    assert veio is not None
    return f"window.hefestoArranjo({json.dumps(veio, ensure_ascii=False)})"


def test_o_clique_na_pagina_grava_e_a_pagina_relida_mostra(disco: Path) -> None:
    """E1 de ponta a ponta: clique → mensagem do piloto → pacote → disco → página.

    Quem NUNCA declarou nada é o caso que decide: nenhuma entrada do disco tem
    ``liga`` nem ``usb`` antes do primeiro clique.
    """
    from hefesto_dualsense4unix.interface import pacotes

    antes, mensagens = _na_pagina([
        _LER_A_PAGINA,
        _entregar(),
        _LER_A_PAGINA,
        _clicar('.plug[data-porta="5"]'),
        _LER_A_PAGINA,
        _clicar('#edita [data-liga="hub"]'),
        _clicar('.plug[data-porta="5.1"]'),
        _LER_A_PAGINA,
        _clicar('#edita [data-liga="extensor"]'),
        _clicar('.plug[data-porta="7"]'),
        _clicar('#edita [data-usb="2"]'),
    ])
    exemplo, _, entregue, _, editor_na_5, _, _, editor_na_51, _, _, _ = (
        json.loads(r) if r.startswith("{") else r for r in antes)
    assert exemplo["quando"], "o exemplo deixou de dizer que é exemplo"
    assert not entregue["quando"], "a leitura desta máquina ainda se anuncia no cabeçalho"
    assert entregue["v3"]["1"] is False, "o firmware de mentira diz USB 2.0 na frente"
    assert sorted(editor_na_5["gestos"]) == sorted([
        "entrada-o-que-tem:direto@5", "entrada-o-que-tem:hub@5",
        "entrada-o-que-tem:extensor@5", "entrada-velocidade:3@5",
        "entrada-velocidade:2@5"]), (
        f"a entrada do mapa dela não leva o gesto ao disco: {editor_na_5['gestos']}")
    assert editor_na_51["gestos"] == [], (
        "a entrada que o desenho monta (5.1) mandaria ao disco uma entrada "
        "que ela nunca mapeou")

    pedidos = [m for m in mensagens if m.get("gesto", "").startswith("entrada-")]
    assert [(m["gesto"], m.get("entrada")) for m in pedidos] == [
        ("entrada-o-que-tem", "5"), ("entrada-velocidade", "7")], pedidos
    for m in pedidos:
        de_onde = m["pagina"]  # noqa-acento: chave ASCII da mensagem do piloto
        dono = pacotes.gesto_da_pagina(de_onde, m["gesto"])
        assert dono is not None, f"{de_onde} · {m['gesto']} não tem dono"
        dono(None, m, None)
    portas = carregar_maquina().mapa.portas
    assert (portas["5"].liga, portas["7"].usb) == ("hub", 2)
    assert portas["5"].nos == _NOS["5"], "o clique apagou os nós que o Mapear gravou"

    depois, _ = _na_pagina([
        _entregar(),
        _LER_A_PAGINA,
        _clicar('.plug[data-porta="5"]'),
        _LER_A_PAGINA,
    ])
    relida, editor = json.loads(depois[1]), json.loads(depois[3])
    assert ee.FACE_DO_HUB_DECLARADO.format(numero="5") in relida["faces"], (
        f"o hub não voltou ao reler: {relida['faces']}")
    assert relida["v3"]["7"] is False, "a 7 relida não é preta, e ela disse USB 2.0"
    assert relida["v3"]["5.1"] is True and "5.1a" not in relida["v3"]
    assert "hub" in editor["apertados"], f"o editor da 5 relido: {editor['apertados']}"
