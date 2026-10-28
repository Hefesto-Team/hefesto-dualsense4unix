"""O mapa do controle pisca o botão que o controle escolhido aperta, mostra a troca e diz qual
controle mostra.

MORDIDAS: pintar o pisca com o controle errado, esquecer a troca no valor da linha, tirar o
endereço de um lado, soltar a peça do desenho quando a linha pisca, tirar o `@media` que encolhe
o chip na vista estreita (reprova sob a DejaVu) ou impor `.chip{width:40px}` (o `vaza` reprova
nas três vistas, e o Range sozinho também) reprovam. A passada `larga` põe um pixel a mais por
letra, que cobre a distância medida entre duas letras comuns do sistema (Noto e DejaVu, ≈0,9 px):
voltar as colunas dos lados a 292 e 252 px, ou a ação de baixo a uma linha só, reprova na mesa e no
rootfs do 26.04."""
from __future__ import annotations

import csv
import importlib.util
import json
import pathlib
import re
import sys
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.hefesto_vivo`, que carrega o GTK")

from hefesto_dualsense4unix.interface import hefesto_vivo, mesa_viva, monta, onde, pacotes
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13
from hefesto_dualsense4unix.interface.frases_que_ela_baniu import sem_o_mudo
from hefesto_dualsense4unix.interface.pacotes import perfil

RAIZ = pathlib.Path(__file__).resolve().parents[2]
PAGINA = a13.PAGINA

UNIQS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03",
         "aa:bb:cc:00:00:04")
APERTA = {1: ["cross"], 3: ["triangle", "l3"]}
ACENDE_P1 = {"cross"}
ACENDE_P3 = {"triangle", "l3"}


def _declaradas() -> set[str]:
    alvo = RAIZ / "scripts/check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("check_desenho_do_mapa_vivo", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_do_mapa_vivo"] = mod
    spec.loader.exec_module(mod)
    return set(mod.declaradas())


def _a_pagina() -> pathlib.Path:
    return onde.pagina(PAGINA, publicado=PAGINA not in _declaradas())


def _contexto(escolhido: str = "") -> pacotes.Contexto:
    mesa, conectados = [], []
    for n, uniq in enumerate(UNIQS, start=1):
        via = "USB" if n == 1 else "BT"
        mesa.append({"pref": f"p{n}", "jogador": n, "uniq": uniq, "cor": "",
                     "nome": "Não sei", "via": via, "transporte": via.lower(),
                     "conectado": True})
        conectados.append({"uniq": uniq, "connected": True, "is_primary": n == 1,
                           "transport": via.lower(), "player_slot": n,
                           "inputs": {"buttons": APERTA.get(n, [])}})
    return pacotes.Contexto(state={"active_profile": "regua", "controllers": conectados},
                            mesa=mesa, conectados=conectados, estados={},
                            escolhido=escolhido)


def _acesos(escolhido: str) -> set[str]:
    """As linhas que piscam: o botão que o controle escolhido está apertando agora."""
    carga = pacotes.pacote_da_pagina(PAGINA, _contexto(escolhido)) or {}
    return {k[len("estado-"):] for k, v in carga["mesa"].items()
            if k.startswith("estado-") and "pisca" in str(v).split()}


@pytest.fixture
def com_troca(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """O perfil ativo com o Triângulo trocado pela Cruz — a fala do usuário, na régua."""
    p = {"name": "regua", "remapeamento": {"triangle": "cross"}}
    monkeypatch.setattr(perfil, "ativo", lambda _nome=None: dict(p))
    return p


def test_o_pisca_e_do_controle_escolhido() -> None:
    assert _acesos("p3") == ACENDE_P3, (
        f"com o P3 escolhido acendeu {_acesos('p3')}; o P3 aperta {ACENDE_P3}")
    assert _acesos("p1") == ACENDE_P1


def test_sem_escolha_e_o_primeiro_da_mesa() -> None:
    """O contexto que não disse cai no primeiro da mesa, como a fita das abas."""
    assert _acesos("") == ACENDE_P1


def _nome_da_peca(pid: str) -> str:
    linhas = [x for x in (RAIZ / "docs/data/pecas-do-dualsense.csv").read_text(
        encoding="utf-8").splitlines() if x and not x.startswith("#")]
    return next(p["nome"] for p in csv.DictReader(linhas) if p["id"] == pid)


def test_a_troca_aparece_no_valor_da_linha_com_o_nome_da_peca(com_troca: dict[str, Any]) -> None:
    mapa = (pacotes.pacote_da_pagina(PAGINA, _contexto("p1")) or {})["mesa"]
    destino = com_troca["remapeamento"]["triangle"]
    assert mapa["val-triangle"] == _nome_da_peca(destino), mapa["val-triangle"]
    assert "muda" in str(mapa["estado-triangle"]).split()
    assert mapa["atual-triangle"] == f"troca:{destino}"
    assert not str(mapa["atual-cross"]).startswith("troca:"), "a Cruz não tem troca"


def test_o_endereco_existe_dos_dois_lados() -> None:
    texto = _a_pagina().read_text(encoding="utf-8")
    sem_script = sem_o_mudo(texto)
    na_pagina = set(re.findall(r'data-campo="([^"]+)"', sem_script))
    carga = pacotes.pacote_da_pagina(PAGINA, _contexto("p1")) or {}
    no_pacote = set(carga["mesa"])
    assert no_pacote - na_pagina == set(), (
        f"o pacote pinta o que a página ({_a_pagina().parent.name}) não tem: "
        f"{sorted(no_pacote - na_pagina)}")
    assert na_pagina - no_pacote == set(), (
        f"a página tem endereço sem dono no pacote: {sorted(na_pagina - no_pacote)}")
    for seletor in carga["blocos"]:
        nome = re.fullmatch(r'\[data-bloco="([^"]+)"\]', seletor)
        if nome:
            assert f'data-bloco="{nome.group(1)}"' in texto, seletor
        else:
            ident = re.fullmatch(r"#([\w-]+)", seletor)
            assert ident and f'id="{ident.group(1)}"' in texto, seletor


def test_o_chip_do_mapa_e_o_gesto_da_fita_das_abas() -> None:
    gesto = pacotes.gesto_da_pagina(PAGINA, monta.GESTO_DA_FITA)
    assert gesto is not None, "o chip do mapa não tem quem o atenda"
    assert gesto is pacotes.gesto_da_pagina("06-navegacao.html", monta.GESTO_DA_FITA), (
        "o mapa tem uma escolha própria: a fita deixou de ser uma só")
    bloco = (pacotes.pacote_da_pagina(PAGINA, _contexto("p1")) or {})["blocos"]
    chips = "".join(bloco.values())
    for n in range(1, 5):
        assert f'data-gesto="{monta.GESTO_DA_FITA}" data-pref="p{n}"' in chips, chips


@pytest.fixture
def escolha_limpa() -> Any:
    mod = sys.modules[pacotes.gesto_da_pagina(PAGINA, monta.GESTO_DA_FITA).__module__]
    antes = mod.ESCOLHA_DA_FITA.uniq
    yield mod
    mod.ESCOLHA_DA_FITA.uniq = antes


def test_a_escolha_feita_no_mapa_chega_ao_contexto_das_abas(escolha_limpa: Any) -> None:
    mod = escolha_limpa
    st = _contexto().state

    class _Piloto:
        def __init__(self) -> None:
            self.leitor = mesa_viva.LeitorDeCor(ligado=False)
            self._externos: list[dict[str, Any]] = []

    def montar() -> pacotes.Contexto:
        ctx, _ = mod.Piloto._contexto(_Piloto(), st, perguntar=False)
        return ctx

    gesto = pacotes.gesto_da_pagina(PAGINA, monta.GESTO_DA_FITA)
    gesto(montar(), {"pref": "p3"}, None)
    assert montar().escolhido == "p3"


MEDIDA = r"""
(function(){
  const fill = s => { const e = document.querySelector(s);
                      return e ? getComputedStyle(e).fill : null; };
  const linha = b => document.querySelector('.b2[data-b="' + b + '"]');
  return JSON.stringify({
    texto_tri: ((linha('triangle') || {}).querySelector('.b2-val') || {}).textContent,
    estado_tri: (linha('triangle') || {}).dataset.estado,
    estado_cruz: (linha('cross') || {}).dataset.estado,
    peca_tri: fill('#mp-triangle .peca'), peca_cruz: fill('#mp-cross .peca'),
    chips: document.querySelectorAll('.mc-chips .chip').length
  });
})()
"""
ROSA = "rgb(255, 121, 198)"


def _no_webkit(cargas: list[Any]) -> list[dict[str, Any]]:
    """Abre a página, instala a ponte e mede depois de cada carga pintada."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre (rode com xvfb-run -a)")

    saiu: list[str] = []
    fila = list(cargas)
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(1600, 900)
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def proxima() -> None:
        if not fila:
            Gtk.main_quit()
            return
        carga = fila.pop(0)
        pedido = carga if isinstance(carga, str) else hefesto_vivo.PEDIR_A_PINTURA.replace(
            "CARGA", json.dumps(carga, ensure_ascii=False))
        view.evaluate_javascript(pedido, -1, None, None, None, pintou)

    def mediu(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(f"ERRO na medida: {e}")
        proxima()

    def pintou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO na pintura: {e}")
            Gtk.main_quit()
            return
        GLib.timeout_add(150, lambda: (v.evaluate_javascript(
            MEDIDA, -1, None, None, None, mediu), False)[1])

    def instalou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:
            saiu.append(f"ERRO no bootstrap: {e}")
            Gtk.main_quit()
            return
        proxima()

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hefesto_vivo.BOOTSTRAP, -1, None, None, None, instalou)

    view.connect("load-changed", carregou)
    view.load_uri(_a_pagina().as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(saiu) == len(cargas), f"o WebKit não respondeu: {saiu}"
    assert not any(s.startswith("ERRO") for s in saiu), saiu
    return [json.loads(s) for s in saiu]


def _carga(escolhido: str) -> dict[str, Any]:
    ctx = _contexto(escolhido)
    return pacotes.normalizar(pacotes.pacote_da_pagina(PAGINA, ctx) or {},
                              {u: f"p{n}" for n, u in enumerate(UNIQS, start=1)})


def test_o_pisca_e_a_troca_aparecem_no_desenho(com_troca: dict[str, Any]) -> None:
    """A linha do Triângulo diz o destino e a peça dele pinta rosa quando o P3 o aperta."""
    com_p3, com_p1 = _no_webkit([_carga("p3"), _carga("p1")])
    destino = _nome_da_peca(com_troca["remapeamento"]["triangle"])
    assert com_p3["texto_tri"] == destino, com_p3
    assert "pisca" in com_p3["estado_tri"].split() and "pisca" not in com_p3["estado_cruz"].split()
    assert com_p3["peca_tri"] == ROSA, com_p3
    assert com_p1["peca_tri"] != ROSA and com_p1["peca_cruz"] == ROSA, com_p1


VISTAS_DO_MAPA = {"dela": (1918, 840), "ladrilhada": (1212, 809), "estreita": (860, 809)}

CHIPS = r"""
(function(){
  return JSON.stringify(Array.from(
      document.querySelectorAll('[data-bloco="controles-do-mapa"] .chip')).map(b => {
    const r = b.getBoundingClientRect(), bloco = b.closest('.mc-chips').getBoundingClientRect();
    const caixa = document.querySelector('.cx').getBoundingClientRect();
    // o texto se mede também pelo Range do conteúdo, que tem de caber dentro da borda do chip:
    // é a caixa do próprio texto, e não o que o <button> diz da rolagem dele
    const rg = document.createRange(); rg.selectNodeContents(b);
    const t = rg.getBoundingClientRect();
    return {texto: (b.textContent || '').trim(),
            vaza: b.scrollHeight > b.clientHeight + 1 || b.scrollWidth > b.clientWidth + 1
                  || t.left < r.left + 1 || t.right > r.right - 1
                  || t.top < r.top - 1 || t.bottom > r.bottom + 1,
            fora: r.right > Math.min(bloco.right, caixa.right, window.innerWidth) + 1
                  || r.left < bloco.left - 1};
  }));
})()
"""


def _mede_na_vista(js: str, largura: int, altura: int,
                  pagina: pathlib.Path | None = None) -> Any:
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk, WebKit2

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre (rode com xvfb-run -a)")
    saiu: list[str] = []
    janela = Gtk.OffscreenWindow()
    janela.set_default_size(largura, altura)
    view = WebKit2.WebView()
    view.set_size_request(largura, altura)
    janela.add(view)
    janela.show_all()

    def mediu(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:
            saiu.append(f"ERRO na medida: {e}")
        Gtk.main_quit()

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            GLib.timeout_add(300, lambda: (v.evaluate_javascript(
                js, -1, None, None, None, mediu), False)[1])

    view.connect("load-changed", carregou)
    view.load_uri((pagina or _a_pagina()).as_uri())
    guarda = GLib.timeout_add(20000, Gtk.main_quit)
    try:
        Gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert len(saiu) == 1 and not saiu[0].startswith("ERRO"), f"o WebKit não respondeu: {saiu}"
    return json.loads(saiu[0])


LETRA = {"comum": "", "larga": "*{letter-spacing:1px !important}"}


def _na_letra(js: str, vista: str, letra: str) -> Any:
    """A medida com a letra do computador, ou com um pixel a mais por letra posto pelo teste."""
    envolta = (
        "(function(){var s=document.createElement('style');"
        f"s.textContent={json.dumps(LETRA[letra])};document.head.appendChild(s);"
        "document.body.offsetWidth;"
        "return JSON.stringify({entreletra: getComputedStyle(document.body).letterSpacing,"
        f" medida: JSON.parse({js.strip()})}});}})()"
    )
    saiu = _mede_na_vista(envolta, *VISTAS_DO_MAPA[vista])
    if letra == "larga":
        assert saiu["entreletra"] == "1px", f"o pixel a mais não pegou: {saiu['entreletra']}"
    return saiu["medida"]


@pytest.mark.parametrize("letra", LETRA)
@pytest.mark.parametrize("vista", sorted(VISTAS_DO_MAPA))
def test_o_nome_do_controle_cabe_no_chip_em_toda_janela(vista: str, letra: str) -> None:
    """8 (conferência final, 02/10/2026): os chips levam o nome do controle

    Prova da D-1810-O-CHIP-DO-MAPA-EM-UMA-LINHA-COMPACTA-NA-VISTA-ESTREITA e da
    D-2710-O-MAPA-DO-CONTROLE-TEM-FOLGA-PARA-A-LETRA-DO-SISTEMA, também na letra larga.
    """
    chips = list(_na_letra(CHIPS, vista, letra))
    assert len(chips) >= 3, f"a página não tem os chips do «Controle»: {chips}"
    ruins = [c for c in chips if c["vaza"] or c["fora"]]
    assert ruins == [], (
        f"na janela {vista}, letra {letra}, o nome vaza do chip ou sai do bloco: {ruins}")


CENTRO = r"""
(function(){
  const R = e => e.getBoundingClientRect();
  const lados = document.querySelectorAll('.mc-mapa > .mc-lado');
  const c = R(document.querySelector('.mc-centro')), esq = R(lados[0]), dir = R(lados[1]);
  const dentro = e => { const r = R(e); return r.left >= c.left - 1 && r.right <= c.right + 1; };
  return JSON.stringify({
    // o centro não pode entrar na coluna de um lado, nem os botões do centro sair dele
    cruza: c.left < esq.right - 1 || c.right > dir.left + 1,
    baixo: Array.from(document.querySelectorAll('.mc-baixo .b2'))
        .map(b => ({b: b.dataset.b, dentro: dentro(b)})),
    desenho: dentro(document.querySelector('.mc-desenho .ds'))
  });
})()
"""

NOMES_DO_EXEMPLO = ("Cosmic Red", "Starlight Blue", "Galactic Purple", "White")


def _pagina_com_nomes_longos(destino: pathlib.Path) -> pathlib.Path:
    """A mesma página, com os quatro nomes de exemplo trocados por nomes de 32 caracteres."""
    texto = _a_pagina().read_text(encoding="utf-8")
    for n, nome in enumerate(NOMES_DO_EXEMPLO):
        longo = f"{nome} " + "ABCD"[n] * (32 - len(nome) - 1)
        assert len(longo) == 32
        marca = f'>{nome} <span class="pt">'
        assert texto.count(marca) == 1, f"a página não tem o chip de exemplo {nome!r}"
        texto = texto.replace(marca, f'>{longo} <span class="pt">')
    pagina = destino / "mapa-com-nomes-longos.html"
    pagina.write_text(texto, encoding="utf-8")
    return pagina


CHIPS_E_A_DICA = r"""
(function(){
  const caixa = document.querySelector('.cx').getBoundingClientRect();
  return JSON.stringify(Array.from(
      document.querySelectorAll('[data-bloco="controles-do-mapa"] .chip')).map(b => {
    const r = b.getBoundingClientRect(), bloco = b.closest('.mc-chips').getBoundingClientRect();
    const corta = b.scrollWidth > b.clientWidth + 1;
    // o ponteiro passa pelo chip: a base põe o texto inteiro na dica de quem a reticência corta
    b.dispatchEvent(new MouseEvent('mousemove', {bubbles: true}));
    return {texto: (b.textContent || '').replace(/\s+/g, ' ').trim(), corta: corta,
            reticencia: getComputedStyle(b).textOverflow === 'ellipsis',
            dica: b.dataset.dica || '',
            fora: r.right > Math.min(bloco.right, caixa.right, window.innerWidth) + 1
                  || r.left < bloco.left - 1 || r.left < caixa.left - 1};
  }));
})()
"""


@pytest.mark.parametrize("vista", sorted(VISTAS_DO_MAPA))
def test_o_centro_do_mapa_cabe_entre_as_colunas_em_toda_janela(vista: str) -> None:
    """O-CHIP-DO-MAPA-CABE-A-860-PX-01: a 860 px o centro cruzava a coluna do lado."""
    medida = _mede_na_vista(CENTRO, *VISTAS_DO_MAPA[vista])
    assert not medida["cruza"], (
        f"na janela {vista}, o centro do mapa entra na coluna de um lado: {medida}")
    assert {b["b"] for b in medida["baixo"]} >= {"tp_toque", "tp_meio", "ps"}, medida
    fora = [b["b"] for b in medida["baixo"] if not b["dentro"]]
    assert fora == [], f"na janela {vista}, estes botões saem da coluna do meio: {fora}"
    assert medida["desenho"], f"na janela {vista}, o desenho do controle sai da coluna do meio"


@pytest.mark.parametrize("vista", sorted(VISTAS_DO_MAPA))
def test_o_nome_comprido_do_controle_corta_no_chip_e_leva_o_nome_na_dica(
        vista: str, tmp_path: pathlib.Path) -> None:
    """O-CHIP-DO-MAPA-CABE-A-860-PX-01: quatro nomes de 32 caracteres não saem do chip."""
    pagina = _pagina_com_nomes_longos(tmp_path)
    chips = list(_mede_na_vista(CHIPS_E_A_DICA, *VISTAS_DO_MAPA[vista], pagina))
    assert len(chips) == 4, chips
    fora = [c["texto"] for c in chips if c["fora"]]
    assert fora == [], (
        f"na janela {vista}, o chip de nome comprido sai do bloco ou da caixa: {fora}")
    sem_corte = [c["texto"] for c in chips if not c["reticencia"]]
    assert sem_corte == [], f"o chip não corta com reticências: {sem_corte}"
    if vista != "dela":
        assert all(c["corta"] for c in chips), (
            f"na janela {vista} nenhum nome devia caber inteiro: {chips}")
    cortados = [c for c in chips if c["corta"]]
    sem_dica = [c["texto"] for c in cortados if c["dica"] != c["texto"]]
    assert sem_dica == [], f"o nome cortado não leva o texto inteiro na dica: {sem_dica}"


FOLGA_DOS_CHIPS = r"""
(function(){
  return JSON.stringify(Array.from(
      document.querySelectorAll('[data-bloco="controles-do-mapa"] .chip')).map(b => {
    const rg = document.createRange(); rg.selectNodeContents(b);
    const cs = getComputedStyle(b), r = b.getBoundingClientRect();
    // a caixa de dentro (sem borda nem margem interna) menos a largura real do texto, sem
    // tolerância: a reticência aparece com um centésimo de pixel de sobra, e o `scrollWidth`
    // inteiro não vê
    const caixa = r.width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)
                  - parseFloat(cs.borderLeftWidth) - parseFloat(cs.borderRightWidth);
    return {texto: (b.textContent || '').trim(), folga: caixa - rg.getBoundingClientRect().width};
  }));
})()
"""


@pytest.mark.parametrize("letra", LETRA)
@pytest.mark.parametrize("vista", sorted(VISTAS_DO_MAPA))
def test_o_nome_de_exemplo_nao_ganha_reticencia_por_um_pixel_quebrado(
        vista: str, letra: str) -> None:
    """O corte do nome comprido não pega o nome de exemplo: o texto cabe na caixa de dentro.

    Prova da D-2710-O-MAPA-DO-CONTROLE-TEM-FOLGA-PARA-A-LETRA-DO-SISTEMA, também na letra larga.
    """
    chips = list(_na_letra(FOLGA_DOS_CHIPS, vista, letra))
    assert len(chips) == 4, chips
    apertados = [(c["texto"], round(c["folga"], 3)) for c in chips if c["folga"] < 0]
    assert apertados == [], (
        f"na janela {vista}, letra {letra}, o texto passa da caixa de dentro do chip: {apertados}")


ACOES = r"""
(function(){
  return JSON.stringify(Array.from(document.querySelectorAll('.mc-mapa .b2')).map(b => {
    const v = b.querySelector('.b2-val'), cs = getComputedStyle(v);
    const rg = document.createRange(); rg.selectNodeContents(v);
    // a largura do texto contra a caixa de dentro do campo: o corte do `overflow` não aparece no
    // `scrollWidth` de quem é `flex`, e a reticência só se desenha fora dele
    const livre = v.getBoundingClientRect().width - parseFloat(cs.paddingLeft)
                  - parseFloat(cs.paddingRight);
    return {b: b.dataset.b, lado: !!b.closest('.mc-lado'), texto: (v.textContent || '').trim(),
            corta: rg.getBoundingClientRect().width > livre + 0.5,
            reticencia: cs.textOverflow === 'ellipsis' && cs.display !== 'flex'};
  }));
})()
"""


@pytest.mark.parametrize("letra", LETRA)
@pytest.mark.parametrize("vista", sorted(VISTAS_DO_MAPA))
def test_a_acao_de_cada_linha_se_le_em_toda_janela(vista: str, letra: str) -> None:
    """O-CHIP-DO-MAPA-CABE-A-860-PX-01: dar o centro ao controle não pode tirar a ação das colunas
    dos lados. Com as laterais a 200 px, a 860 px dezessete ações saíam cortadas a seco.

    Prova da D-2310-A-ACAO-DO-MAPA-SE-LE-INTEIRA-NA-VISTA-ESTREITA e da
    D-2710-O-MAPA-DO-CONTROLE-TEM-FOLGA-PARA-A-LETRA-DO-SISTEMA, também na letra larga.
    """
    linhas = list(_na_letra(ACOES, vista, letra))
    assert len(linhas) == 23, linhas
    do_lado = [x["texto"] for x in linhas if x["lado"] and x["corta"]]
    assert do_lado == [], (
        f"na janela {vista}, letra {letra}, a ação da linha do lado sai cortada: {do_lado}")
    if vista == "estreita":
        cortadas = [x["texto"] for x in linhas if x["corta"]]
        assert cortadas == [], f"na janela {vista}, letra {letra}, a ação sai cortada: {cortadas}"
    a_seco = [x["texto"] for x in linhas if x["corta"] and not x["reticencia"]]
    assert a_seco == [], f"na janela {vista}, a ação corta sem reticências: {a_seco}"
