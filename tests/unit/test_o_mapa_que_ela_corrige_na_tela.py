"""O mapa que ela corrige, NA TELA — o WebKit fora da tela, com o gesto de verdade.

O-MAPA-QUE-ELA-CORRIGE-01, 26/09/2026. O pedido dela, com o mapa aberto:

*«me referi as portas renomear, trocar elas de lugar no meapemento identificar
onde fica o hub e afins. corrigir quando for 2.0 e tal.»*
<!-- noqa-acento: citação literal dela -->

Esta régua abre a página PUBLICADA num ``WebKit2.WebView`` dentro de um
``Gtk.OffscreenWindow`` (nunca na tela dela), instala o BOOTSTRAP do piloto e
faz o papel do piloto na volta do clique: acha a mensagem que a página mandou,
roda o gesto de verdade (``pacotes.gesto_da_pagina``) contra um
``maquina.json`` no ``tmp_path`` e um barramento de mentira, entrega o arranjo
que ele devolveu e pousa o botão (``window.__hef.voltouDoVoo``) — na ordem do
piloto: primeiro o arranjo, depois o pouso.

TUDO AQUI É DE MENTIRA E DE NINGUÉM: barramento ``usb9``, caminhos ``9-*``,
seriais que não são endereço de nada.

AS MORDIDAS:

* passo 0 — devolva a pintura local do clique do editor (tire o
  ``if (ub && ub.hasAttribute("data-gesto")) return;``): o botão da recusa
  nasce apertado e a piscada não acha ninguém
  (``test_a_recusa_nao_aperta_o_botao_e_pisca_nele``).
"""

from __future__ import annotations

import gc
import json
from collections.abc import Callable
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
from hefesto_dualsense4unix.integrations.lugar_declarado import Recibo
from hefesto_dualsense4unix.interface import arranjo_desta_maquina, onde
from hefesto_dualsense4unix.utils.maquina import (
    FaceDeclarada,
    MapaDaMesa,
    PortaDeclarada,
    caminho_da_maquina,
    carregar_maquina,
    gravar_maquina,
)

# ── o barramento de mentira ──────────────────────────────────────────────

_TRIPLA_TECLADO = ("03", "01", "01")
_TRIPLA_MOUSE = ("03", "01", "02")
_TRIPLA_BT = ("e0", "01", "01")


def _aparelho(caminho: str, vid: str, pid: str, especie: str,
              tripla: tuple[str, str, str], mbps: float = 480.0) -> Aparelho:
    return Aparelho(
        no=f"/sys/de-mentira/{vid}{pid}", nome_do_kernel=caminho, vid=vid, pid=pid,
        produto=f"{especie} de prova", especie=especie, classe=tripla[0],
        subclasse=tripla[1], protocolo=tripla[2], velocidade_mbps=mbps,
    )


def _teclado(caminho: str) -> Aparelho:
    return _aparelho(caminho, "1111", "0001", "Teclado", _TRIPLA_TECLADO)


def _mouse(caminho: str) -> Aparelho:
    return _aparelho(caminho, "3333", "0003", "Mouse", _TRIPLA_MOUSE)


def _dongle(caminho: str) -> Aparelho:
    return _aparelho(caminho, "2222", "0002", "Bluetooth", _TRIPLA_BT)


def _censo(*aparelhos: Aparelho) -> Censo:
    return Censo(
        aparelhos=aparelhos,
        barramentos=(Barramento(no="/sys/usb9", nome_do_kernel="usb9",
                                velocidade_mbps=480.0),),
    )


def _mapa() -> MapaDaMesa:
    """Duas na frente, quatro atrás, todas com o caminho amarrado."""
    return MapaDaMesa(
        faces=[FaceDeclarada(nome="Frente", portas=["1", "2"], perto=True),
               FaceDeclarada(nome="Traseira", portas=["3", "4", "5", "6"])],
        portas={n: PortaDeclarada(caminho=f"9-{n}", nos=[f"usb9-port{n}"])
                for n in ("1", "2", "3", "4", "5", "6")},
    )


#: O que está plugado em cada régua desta página (o teclado na 1, o mouse na 5).
_PLUGADOS = (_teclado("9-1"), _mouse("9-5"))


@pytest.fixture()
def disco(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """O ``maquina.json`` no ``tmp_path`` (conferido) e o barramento de mentira.

    O gesto relê a máquina pelas portas de sempre: o barramento é trocado no
    módulo que o arranjo importa na hora, e nenhum ``/sys`` de verdade é lido.
    """
    from hefesto_dualsense4unix.integrations import censo_do_barramento

    alvo = caminho_da_maquina()
    assert alvo.is_relative_to(tmp_path), f"o maquina.json da régua não está desviado: {alvo}"
    assert gravar_maquina({"mapa": _mapa().model_dump(mode="json")})
    monkeypatch.setattr(censo_do_barramento, "ler_o_barramento", lambda: _censo(*_PLUGADOS))
    monkeypatch.setattr(mapa_das_portas, "serial_do_no", lambda _no: "")
    return alvo


def _aberta() -> dict[str, Any]:
    dado = arranjo_desta_maquina.para_a_pagina(
        carregar=carregar_maquina, ler_o_barramento=lambda: _censo(*_PLUGADOS),
        ler_o_serial=lambda _no: "")
    assert dado is not None
    return dado


# ── a página no WebKit, com o piloto de mentira na volta do clique ──────

Passo = str | Callable[[list[dict[str, Any]]], str | None]


def _na_pagina(passos: list[Passo]) -> tuple[list[Any], list[dict[str, Any]]]:
    """A página publicada num WebKit fora da tela; o lixo recolhido no fio do GTK."""
    try:
        return _na_pagina_sem_recolher(passos)
    finally:
        gc.collect()
        from gi.repository import Gtk

        while Gtk.events_pending():
            Gtk.main_iteration_do(False)


def _na_pagina_sem_recolher(passos: list[Passo]) -> tuple[list[Any], list[dict[str, Any]]]:
    """Cada passo é um JavaScript, ou uma função das mensagens que devolve um
    (``None`` = ainda não: tenta de novo em 50 ms, até 3 s)."""
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
    fila: list[Passo] = [hefesto_vivo.BOOTSTRAP, *passos]
    tentativas = {"n": 0}

    def seguinte() -> bool:
        if not fila:
            GLib.timeout_add(300, lambda: (Gtk.main_quit(), False)[1])
            return False
        passo = fila[0]
        if callable(passo):
            js = passo(mensagens)
            if js is None:
                tentativas["n"] += 1
                if tentativas["n"] < 60:
                    GLib.timeout_add(50, seguinte)
                    return False
                js = "'o piloto de mentira não achou a mensagem'"
        else:
            js = passo
        fila.pop(0)
        tentativas["n"] = 0

        def respondeu(v: Any, res: Any, _u: Any = None) -> None:
            try:
                respostas.append(v.evaluate_javascript_finish(res).to_string())
            except Exception as erro:  # a exceção É a resposta do passo
                respostas.append(f"ERRO {erro}")
            GLib.timeout_add(30, seguinte)

        view.evaluate_javascript(js, -1, None, None, None, respondeu, None)
        return False

    def carregou(_v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            seguinte()

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina(arranjo_desta_maquina.PAGINA, publicado=True).as_uri())
    guarda = GLib.timeout_add(40000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(respostas) == len(passos) + 1, f"o WebKit parou no meio: {respostas}"
    assert respostas[0] == "ok", f"o BOOTSTRAP do piloto não instalou: {respostas[0]}"
    lidas = [json.loads(r) if r.startswith(("{", "[")) else r for r in respostas[1:]]
    return lidas, mensagens


def _js(dado: dict[str, Any], como: str = "") -> str:
    return arranjo_desta_maquina.js_da_entrega(dado, como=como)


def _clicar(seletor: str) -> str:
    alvo = json.dumps(seletor)
    return (f"(function(){{const b=document.querySelector({alvo});"
            f"if(!b){{return 'sem ' + {alvo};}} b.click(); return 'clicou';}})()")


def _mudar(seletor: str, valor: str) -> str:
    """O campo recebe o valor e dispara o ``change``, como a mão."""
    alvo, v = json.dumps(seletor), json.dumps(valor)
    return (f"(function(){{const c=document.querySelector({alvo});"
            f"if(!c){{return 'sem ' + {alvo};}} c.value={v};"
            f"c.dispatchEvent(new Event('change', {{bubbles: true}})); return 'mudou';}})()")


def _o_piloto_responde(
    gesto: str, *, evento: str = ""
) -> Callable[[list[dict[str, Any]]], str | None]:
    """O papel do piloto na volta do clique: o gesto de verdade, o arranjo que
    ele devolveu pela porta da página e o pouso do botão (``hefesto_vivo._gesto``)."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")
    from hefesto_dualsense4unix.interface import pacotes

    def responder(mensagens: list[dict[str, Any]]) -> str | None:
        achadas = [m for m in mensagens if m.get("gesto") == gesto
                   and (not evento or m.get("evento") == evento)]
        if not achadas:
            return None
        o = achadas[-1]
        mensagens.remove(o)
        dono = pacotes.gesto_da_pagina(arranjo_desta_maquina.PAGINA, gesto)
        assert dono is not None, f"o gesto {gesto!r} não tem dono"
        voo = json.dumps(str(o.get("voo") or ""))
        try:
            resposta = dono(None, o, None)
        except (RuntimeError, ValueError):
            return f"window.__hef.voltouDoVoo({voo}, false)"
        partes = []
        if isinstance(resposta, dict):
            if arranjo_desta_maquina.CHAVE_DEPOIS_DE_GRAVAR in resposta:
                partes.append(_js(resposta[arranjo_desta_maquina.CHAVE_DEPOIS_DE_GRAVAR],
                                  como=arranjo_desta_maquina.COMO_GRAVOU))
            if resposta.get("armou"):
                partes.append(f"window.__hef.voltouDoVoo({voo}, null)")
                return ";".join(partes)
        partes.append(f"window.__hef.voltouDoVoo({voo}, true)")
        return ";".join(partes)

    return responder


def _o_botao(seletor: str) -> str:
    alvo = json.dumps(seletor)
    return (f"(function(){{const b=document.querySelector({alvo});"
            f"if(!b) return JSON.stringify({{existe: false}});"
            f"return JSON.stringify({{existe: true, classe: b.className,"
            f" apertado: b.getAttribute('aria-pressed'),"
            f" voo: b.getAttribute('data-hef-voo') || ''}});}})()")


_O_EDITOR = r"""
(function(){
  const ed = document.getElementById('edita');
  if (!ed || ed.hidden) return JSON.stringify({aberto: false});
  return JSON.stringify({
    aberto: true,
    cabecalho: (ed.querySelector('.edita-cab') || {innerText: ''}).innerText
      .replace(/\s+/g, ' ').trim(),
    texto: ed.innerText.replace(/\s+/g, ' ').trim(),
    apertados: [...ed.querySelectorAll('button[aria-pressed="true"]')].map(
      b => b.dataset.liga || b.dataset.usb),
  });
})()
"""


# ── passo 0: a tela espera o disco ───────────────────────────────────────


def test_a_recusa_nao_aperta_o_botao_e_pisca_nele(
    disco: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Um gravador que recusa: o «USB 3.0» NÃO fica apertado, e pisca a recusa.

    Antes da cura a página apertava o botão na hora (a pintura local), e a
    piscada procurava um botão que a repintura já tinha trocado: a recusa era
    invisível, e a tela afirmava o que o disco não tinha.
    """
    monkeypatch.setattr(ee, "declarar_a_velocidade",
                        lambda numero, usb, **_k: Recibo(False, "disco"))
    antes = disco.read_bytes()
    lidas, _ = _na_pagina([
        _js(_aberta()),
        _clicar('.plug[data-porta="2"]'),
        _clicar('#edita [data-usb="3"][data-gesto="entrada-velocidade"]'),
        _o_botao('#edita [data-usb="3"]'),
        _o_piloto_responde("entrada-velocidade"),
        _o_botao('#edita [data-usb="3"]'),
        _O_EDITOR,
    ])
    clicado, em_voo, _pouso, depois, editor = lidas[1], lidas[3], lidas[4], lidas[5], lidas[6]
    assert clicado == "clicou", "o «USB 3.0» da entrada 2 não leva o gesto ao disco"
    assert em_voo["existe"] and em_voo["voo"], (
        f"o botão clicado não ficou em voo — a página o repintou: {em_voo}")
    assert em_voo["apertado"] == "false", (
        f"a página apertou o botão antes do disco responder: {em_voo}")
    assert depois["existe"] and "hef-recusou" in depois["classe"], (
        f"a recusa não piscou no botão clicado: {depois}")
    assert depois["apertado"] == "false", f"a recusa deixou o botão apertado: {depois}"
    assert editor["aberto"], "a recusa fechou o editor"
    assert disco.read_bytes() == antes, "a recusa escreveu no disco"


def test_o_que_grava_aparece_apertado_depois_da_entrega(disco: Path) -> None:
    """O gravador de verdade: o «USB 3.0» aparece apertado quando o disco
    responde, com o editor aberto na MESMA entrada, e o plugue azul."""
    lidas, _ = _na_pagina([
        _js(_aberta()),
        _clicar('.plug[data-porta="2"]'),
        _clicar('#edita [data-usb="3"]'),
        _o_botao('#edita [data-usb="3"]'),
        _o_piloto_responde("entrada-velocidade"),
        _O_EDITOR,
        "String(document.querySelector('.plug[data-porta=\"2\"]').classList.contains('v3'))",
    ])
    em_voo, editor, azul = lidas[3], lidas[5], lidas[6]
    assert em_voo["apertado"] == "false", "a página apertou antes do disco"
    assert carregar_maquina().mapa.portas["2"].usb == 3, "o gesto não gravou"
    assert editor["aberto"], "a volta da gravação fechou o editor"
    assert "Entrada 2" in editor["cabecalho"], editor
    assert "3" in editor["apertados"], f"o disco diz USB 3.0 e o botão não está apertado: {editor}"
    assert azul == "true", "o plugue da entrada 2 não ficou azul"


def test_no_exemplo_a_pintura_continua_local() -> None:
    """Sem produto não há disco: o clique pinta na hora, como sempre pintou."""
    lidas, mensagens = _na_pagina([
        _clicar('.plug[data-porta="2"]'),
        _clicar('#edita [data-usb="3"]'),
        _O_EDITOR,
    ])
    assert "3" in lidas[2]["apertados"], lidas[2]
    assert not [m for m in mensagens if str(m.get("gesto", "")).startswith("entrada-")], (
        f"o exemplo mandou gesto ao disco: {mensagens}")


def test_a_entrega_depois_de_gravar_e_um_modo_proprio() -> None:
    """``como="gravou"`` não é o reexame, e o dono recusa um modo que não existe."""
    dado = {"quando": "x", "aparelhos": [], "faces": [], "mapa": {}, "leituras": {}}
    js = arranjo_desta_maquina.js_da_entrega(dado, como=arranjo_desta_maquina.COMO_GRAVOU)
    assert js.endswith(', "gravou")'), js
    assert arranjo_desta_maquina.js_da_entrega(dado, reexame=True).endswith(", true)")
    with pytest.raises(ValueError):
        arranjo_desta_maquina.js_da_entrega(dado, como="qualquer")


class _PontePronta:
    """A ponte do piloto, respondendo na hora o que a régua mandar."""

    def __init__(self, resposta: str = "ok") -> None:
        self.perguntas: list[str] = []
        self.resposta = resposta

    def perguntar(self, js: str, volta: Any) -> None:
        self.perguntas.append(js)
        volta(self.resposta, None)


def test_o_piloto_entrega_a_volta_da_gravacao_sem_mudar_o_modo() -> None:
    """A resposta do editor traz o arranjo relido: ele sai da carga e vai à
    página como «gravou», e nunca como o reexame."""
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa o piloto, que carrega o GTK")
    from hefesto_dualsense4unix.interface import hefesto_vivo

    class _Piloto:
        _arranjo_entregue = hefesto_vivo.Piloto._arranjo_entregue
        _entregar = hefesto_vivo.Piloto._entregar

        def __init__(self) -> None:
            self.pagina = arranjo_desta_maquina.PAGINA
            self.ponte = _PontePronta()
            self.cegueiras: list[str] = []

    dado = {"quando": "x", "aparelhos": [], "faces": [], "mapa": {}, "leituras": {}}
    piloto = _Piloto()
    chave = arranjo_desta_maquina.CHAVE_DEPOIS_DE_GRAVAR
    resto = hefesto_vivo.Piloto._o_arranjo_relido(
        piloto, arranjo_desta_maquina.PAGINA, {chave: dado, "outro": 1})
    assert resto == {"outro": 1}, "o arranjo relido ficou na carga da pintura"
    assert piloto.ponte.perguntas == [
        arranjo_desta_maquina.js_da_entrega(dado, como=arranjo_desta_maquina.COMO_GRAVOU)]


def test_o_mapa_recarregado_reinstala_a_ponte_e_recebe_o_arranjo() -> None:
    """O «Recarregar» do menu do WebKit carrega a MESMA página: sem a ponte no
    documento novo, o piloto instala de novo (e o arranjo vem com a instalação).

    MEDIDO no lar de mentira em 26/09/2026, antes da cura: 24 olhadas em 7 s,
    e o cabeçalho continuava «Leitura de Exemplo». A MORDIDA: tire a chamada
    ``self._a_mesma_recarregou(nova)`` do ``_carregou`` — nada é reinstalado.
    """
    from tests.conftest import exigir_gi_real

    exigir_gi_real("importa o piloto, que carrega o GTK")
    import gi

    gi.require_version("WebKit2", "4.1")
    from gi.repository import WebKit2

    from hefesto_dualsense4unix.interface import hefesto_vivo

    uri = onde.pagina(arranjo_desta_maquina.PAGINA, publicado=True).as_uri()

    class _View:
        def get_uri(self) -> str:
            return uri

    class _Piloto:
        _a_mesma_recarregou = hefesto_vivo.Piloto._a_mesma_recarregou

        def __init__(self, pagina: str, resposta: str) -> None:
            self.view = _View()
            self.pagina = pagina
            self.pronto = True
            self.visitadas: list[str] = [pagina]
            self.ponte = _PontePronta(resposta)
            self.instalou = 0

        def _antes_de_instalar(self) -> None:
            self.instalou += 1

    sem_ponte = _Piloto(arranjo_desta_maquina.PAGINA, "false")
    hefesto_vivo.Piloto._carregou(sem_ponte, None, WebKit2.LoadEvent.FINISHED)
    assert sem_ponte.instalou == 1 and not sem_ponte.pronto, (
        "o mapa recarregado ficou sem a ponte e sem o arranjo — a página vira o exemplo")

    com_ponte = _Piloto(arranjo_desta_maquina.PAGINA, "true")
    hefesto_vivo.Piloto._carregou(com_ponte, None, WebKit2.LoadEvent.FINISHED)
    assert com_ponte.instalou == 0 and com_ponte.pronto, (
        "a primeira carga que confirma depois da instalação instalou duas vezes")
