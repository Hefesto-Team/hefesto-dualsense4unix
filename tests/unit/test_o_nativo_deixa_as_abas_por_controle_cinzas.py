"""O Modo Nativo deixa as quatro abas por controle cinzas, e a recusa é da camada.

DESLIGAR-O-HEFESTO-DEVOLVE-O-CONTROLE-AO-LINUX-01, itens 4 e 5 (09/10/2026, opção a).
Com o Hefesto desligado o jogo é o dono do controle, e Jogar (com a seção Controles, desde
28/10/2026), Gatilhos, Iluminação e Vibração mostram os controles sem deixar mexer no que o
Hefesto não aplica.

DUAS METADES, e nenhuma prova a outra:

1. **A recusa (sem navegador).** Todo gesto registrado nas quatro abas, e o rodapé
   (Aplicar, Salvar, Importar) despachado por elas, recusa no Nativo sem uma só chamada ao
   daemon, e a recusa vem do decorador `@gesto` (`pacotes.camada`), não de um `if` na tela.
   Ficam vivos só os de `VIVOS_NO_NATIVO` e o Exportar, que só grava um arquivo.
2. **A tela (Chrome de verdade).** Com `body.nativo`, o motor responde por `elementFromPoint`:
   nenhum gesto das quatro abas recebe clique fora dos vivos, a fita é uma camada muda e o
   quadro mostra «O jogo manda». O cartão com a máscara saiu da Jogar em 28/10/2026. Sem o
   `nativo` a mesma página oferece tudo (a cura não pode ser
   «cinza para sempre»).

A MORDIDA (feita em 09/10/2026, md5 antes e depois):
 (i)   tire a guarda do decorador (`guardado` devolve `fn` direto) → reprovam as recusas;
 (ii)  esvazie `VIVOS_NO_NATIVO` → reprova o gesto vivo e a lista de seletores do CSS;
 (iii) apague `CSS_DO_NATIVO` (monta.py) → reprova o motor, com o gesto nomeado.
"""
from __future__ import annotations

import contextlib
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import hefesto_dualsense4unix
from tests.conftest import GI_REAL_DISPONIVEL

RAIZ = Path(__file__).resolve().parents[2]
INTERFACE = Path(hefesto_dualsense4unix.__file__).parent / "interface"
CHROME = Path("/usr/bin/google-chrome")
UM = "aa:bb:cc:00:00:01"

AS_QUATRO = ("01-jogar.html", "03-gatilhos.html", "04-iluminacao.html", "05-vibracao.html")


def _pacotes() -> Any:
    if str(INTERFACE) not in sys.path:
        sys.path.insert(0, str(INTERFACE))
    import pacotes

    pacotes._carregar_tudo()
    return pacotes


def _camada() -> Any:
    _pacotes()
    import pacotes.camada as camada

    return camada


class _Dubla:
    """O daemon de mentira: guarda cada chamada que chega, de qualquer jeito."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def __call__(self, metodo: str, **_: Any) -> dict[str, Any]:
        self.chamadas.append(metodo)
        return {"status": "ok"}

    def __getattr__(self, nome: str) -> Any:
        def chama(*_a: Any, **_k: Any) -> dict[str, Any]:
            self.chamadas.append(nome)
            return {"status": "ok", "ok": True}

        return chama


def _ctx(nativo: bool) -> Any:
    pacotes = _pacotes()
    c = {"uniq": UM, "player": 1, "transport": "usb", "transporte": "usb",
         "is_primary": True, "jogador": 1}
    state: dict[str, Any] = {"native_mode": bool(nativo),
                             "gamepad_emulation": {"enabled": False}}
    return pacotes.Contexto(state=state, mesa=[c], conectados=[c])


ENTRADA = {"uniq": UM, "player": 1, "valor": 50, "v": 50, "texto": "x", "campo": "x",
           "lado": "esquerdo", "modo": "x", "mascara": "Xbox 360", "toque": "cursor"}


def _gestos_das_quatro() -> list[tuple[str, str]]:
    pacotes = _pacotes()
    return sorted((p, n) for (p, n) in pacotes.GESTOS if p in AS_QUATRO)


def test_ha_gestos_nas_quatro_abas() -> None:
    """A régua não pode passar por não ter o que medir."""
    achados = _gestos_das_quatro()
    assert len(achados) >= 40, (
        f"só {len(achados)} gestos nas quatro abas — o registro não carregou?")


def test_no_nativo_nenhum_gesto_das_quatro_abas_chega_ao_daemon() -> None:
    pacotes = _pacotes()
    camada = _camada()
    chegaram: list[str] = []
    for pagina, nome in _gestos_das_quatro():
        if (pagina, nome) in camada.VIVOS_NO_NATIVO:
            continue
        ipc = _Dubla()
        with contextlib.suppress(Exception):
            pacotes.GESTOS[(pagina, nome)](_ctx(True), dict(ENTRADA), ipc)
        if ipc.chamadas:
            chegaram.append(f"{pagina} · {nome} → {ipc.chamadas[:2]}")
    assert not chegaram, (
        "no Nativo estes gestos ainda chegam ao daemon (a recusa é da camada, "
        "`@gesto` em pacotes/__init__.py): " + "; ".join(chegaram))


def test_no_nativo_cada_gesto_recusa_pela_camada_com_a_frase() -> None:
    """Recusa = RuntimeError com a frase da camada, e é o decorador que a levanta."""
    pacotes = _pacotes()
    camada = _camada()
    for pagina, nome in _gestos_das_quatro():
        if (pagina, nome) in camada.VIVOS_NO_NATIVO or nome in camada.RODAPE_VIVO_NO_NATIVO:
            continue
        frase = camada.recusa_no_nativo(pagina, nome, _ctx(True).state)
        if camada.CAMADA.get((pagina, nome)) == camada.JANELA:
            assert frase is None, f"{pagina} · {nome} é só da janela e não recusa"
            continue
        assert frase, f"{pagina} · {nome}: a camada não recusa no Nativo"
        fn = pacotes.GESTOS[(pagina, nome)]
        assert hasattr(fn, "__wrapped__"), (
            f"{pagina} · {nome}: o gesto registrado não passa pela guarda do decorador")
        with pytest.raises(RuntimeError) as erro:
            fn(_ctx(True), dict(ENTRADA), _Dubla())
        assert str(erro.value) == frase, (
            f"{pagina} · {nome}: a frase da recusa não é a da camada ({erro.value!r})")


def test_fora_do_nativo_a_camada_deixa_passar() -> None:
    camada = _camada()
    for pagina, nome in _gestos_das_quatro():
        assert camada.recusa_no_nativo(pagina, nome, _ctx(False).state) is None, (
            f"{pagina} · {nome} recusa FORA do Nativo")
    assert camada.recusa_no_nativo("01-jogar.html", "hefesto", _ctx(True).state) is None
    assert camada.recusa_no_nativo("01-jogar.html", "reconectar", _ctx(True).state) is None


def test_as_outras_cinco_abas_seguem_vivas_no_nativo() -> None:
    """Conexões, Sistema, Navegação, Lançadores e Perfis são do computador."""
    camada = _camada()
    for pagina in ("06-navegacao.html", "07-lancadores.html", "08-conexoes.html",
                   "09-sistema.html", "10-perfis.html"):
        for nome in ("aplicar", "salvar", "qualquer"):
            assert camada.recusa_no_nativo(pagina, nome, _ctx(True).state) is None


def test_o_rodape_despachado_pelas_quatro_abas_recusa_no_nativo() -> None:
    """Aplicar, Salvar e Importar mandam o perfil ao controle: recusam; o Exportar segue."""
    pacotes = _pacotes()
    for pagina in AS_QUATRO:
        for nome in ("aplicar", "salvar", "importar"):
            ipc = _Dubla()
            fn = pacotes.gesto_da_pagina(pagina, nome)
            assert fn is not None
            with pytest.raises(RuntimeError):
                fn(_ctx(True), dict(ENTRADA), ipc)
            assert not ipc.chamadas, f"{pagina} · {nome} chegou ao daemon: {ipc.chamadas}"
        assert pacotes.gesto_da_pagina(pagina, "exportar") is not None
    for pagina in ("06-navegacao.html", "10-perfis.html"):
        for nome in ("aplicar", "salvar", "importar", "exportar"):
            assert pacotes.gesto_da_pagina(pagina, nome) is pacotes.GESTOS[("*", nome)], (
                f"{pagina} · {nome} passou a recusar fora das quatro abas")


def test_o_topo_manda_o_nativo_para_o_corpo() -> None:
    pacotes = _pacotes()
    assert pacotes.topo(_ctx(True))["nativo"] == "sim"
    assert pacotes.topo(_ctx(False))["nativo"] == "nao"  # (noqa-acento)


def test_os_vivos_do_css_sao_os_da_camada() -> None:
    """Os seletores do `CSS_DO_NATIVO` e a tabela `VIVOS_NO_NATIVO` dizem a mesma lista."""
    sys.path.insert(0, str(INTERFACE))
    try:
        import monta
    finally:
        sys.path.remove(str(INTERFACE))
    camada = _camada()
    do_css = set(re.findall(r"\[data-gesto=([a-z-]+)\]", monta.CSS_DO_NATIVO))
    da_tabela = {nome for (_p, nome) in camada.VIVOS_NO_NATIVO}
    assert do_css == da_tabela, f"CSS {sorted(do_css)} ≠ camada {sorted(da_tabela)}"
    assert len(da_tabela) >= 4


O_QUE_O_MOTOR_DESENHA = r"""
(nativo) => {
  document.body.classList.toggle('nativo', !!nativo);
  const SEL = '[data-gesto],[data-modo],[data-hef-gesto],[data-papel],[data-forca],' +
    '[data-player],[data-sensor],[data-rota],[data-mudo],[data-mic-modo],[data-v],' +
    '.r-aplicar,.r-salvar,.r-importar,.r-exportar';
  const nome = (el) => el.dataset.gesto || el.dataset.hefGesto || el.dataset.papel ||
    el.dataset.modo || el.dataset.forca || el.dataset.player || el.dataset.sensor ||
    el.dataset.rota || el.dataset.mudo || el.dataset.micModo || el.dataset.v ||
    el.className;
  const oferecido = (el) => {
    const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if (!(r.width > 0 && r.height > 0) || cs.visibility === 'hidden'
        || cs.pointerEvents === 'none') return false;
    const em = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    return !!em && (em === el || el.contains(em));
  };
  const gestos = [];
  for (const el of document.querySelectorAll(SEL)) {
    if (el.closest('.fita')) continue;
    gestos.push({nome: nome(el), tag: el.tagName, oferecido: oferecido(el),
                 texto: (el.textContent || '').trim().slice(0, 24)});
  }
  const visivel = (el) => { const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.display !== 'none' && cs.visibility !== 'hidden'; };
  const chipsDaFita = Array.from(document.querySelectorAll('.fita .chip')).map((c) => {
    const r = c.getBoundingClientRect();
    const em = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    return {clicavel: !!em && (em === c || c.contains(em)),
            quem: em ? em.className : ''};
  });
  const trava = Array.from(document.querySelectorAll('.trava-nativo')).filter(visivel)
    .map((e) => e.textContent.trim());
  const camadaDaFita = Array.from(document.querySelectorAll('.fita .so-no-nativo'))
    .filter(visivel).length;
  return {gestos, chipsDaFita, trava, camadaDaFita,
          corpo: document.body.className};
}
"""


@pytest.fixture(scope="module")
def paginas(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """As quatro páginas montadas pelo gerador de verdade, numa bancada de mentira."""
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    if not GI_REAL_DISPONIVEL:
        pytest.skip("sem o PyGObject real — os geradores das abas são do lado GTK")
    destino = tmp_path_factory.mktemp("nativo")
    for arq in (RAIZ / "mockup").glob("*.html"):
        (destino / arq.name).write_text(arq.read_text(encoding="utf-8"), encoding="utf-8")
    env = dict(os.environ, HEFESTO_BANCADA=str(destino),
               PYTHONPATH=str(RAIZ / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""))
    for n in ("01", "03", "04", "05"):
        feito = subprocess.run([sys.executable, f"aba{n}.py"], cwd=INTERFACE, env=env,
                               capture_output=True, text=True, timeout=300)
        assert feito.returncode == 0, f"aba{n}.py: {feito.stdout[-300:]} {feito.stderr[-300:]}"
    return {p: destino / p for p in AS_QUATRO}


@pytest.fixture(scope="module")
def medido(paginas: dict[str, Path]) -> dict[str, dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    sys.path.insert(0, str(RAIZ / "scripts"))
    try:
        import chrome_sem_rede
    finally:
        sys.path.remove(str(RAIZ / "scripts"))
    saida: dict[str, dict[str, Any]] = {}
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            for pagina, arquivo in paginas.items():
                pg, _ = chrome_sem_rede.abrir_sem_rede(
                    navegador, arquivo.as_uri(), largura=1280, altura=900)
                saida[pagina] = {"nativo": pg.evaluate(O_QUE_O_MOTOR_DESENHA, True),
                                 "normal": pg.evaluate(O_QUE_O_MOTOR_DESENHA, False)}
        finally:
            navegador.close()
    return saida


def test_no_nativo_o_motor_nao_entrega_clique_a_gesto_nenhum(medido: dict[str, Any]) -> None:
    camada = _camada()
    vivos = {n for (_p, n) in camada.VIVOS_NO_NATIVO} | set(camada.RODAPE_VIVO_NO_NATIVO)
    vivos |= {"r-exportar"}
    for pagina, m in medido.items():
        pegam = sorted({g["nome"] for g in m["nativo"]["gestos"]
                        if g["oferecido"] and g["nome"] not in vivos})
        assert not pegam, f"{pagina}: no Nativo o Chrome ainda entrega clique a {pegam}"
        assert len(m["nativo"]["gestos"]) >= 5, f"{pagina}: poucos gestos para medir"
        assert "nativo" in m["nativo"]["corpo"]


def test_fora_do_nativo_as_mesmas_paginas_oferecem_gestos(medido: dict[str, Any]) -> None:
    """O par: a cura não é «cinza para sempre»."""
    for pagina, m in medido.items():
        oferecidos = [g for g in m["normal"]["gestos"] if g["oferecido"]]
        assert len(oferecidos) >= 3, f"{pagina}: fora do Nativo quase nada se oferece"
        assert not m["normal"]["trava"] and m["normal"]["camadaDaFita"] == 0


def test_os_vivos_da_jogar_recebem_clique_no_nativo(medido: dict[str, Any]) -> None:
    vivos = {g["nome"] for g in medido["01-jogar.html"]["nativo"]["gestos"] if g["oferecido"]}
    assert {"cadeado", "hefesto", "reconectar"} <= vivos, f"vivos oferecidos: {sorted(vivos)}"


def test_no_nativo_a_fita_e_uma_camada_muda(medido: dict[str, Any]) -> None:
    for pagina, m in medido.items():
        n = m["nativo"]
        assert n["camadaDaFita"] == 1, f"{pagina}: a camada da fita não aparece no Nativo"
        assert n["chipsDaFita"], f"{pagina}: sem chips na fita para medir"
        for chip in n["chipsDaFita"]:
            assert not chip["clicavel"], f"{pagina}: um chip da fita ainda recebe clique"
            assert "so-no-nativo" in chip["quem"]


def test_no_nativo_as_tres_abas_de_ajuste_dizem_que_o_jogo_manda(medido: dict[str, Any]) -> None:
    for pagina in AS_QUATRO[1:]:
        assert medido[pagina]["nativo"]["trava"] == ["O jogo manda"], (
            f"{pagina}: a trava «O jogo manda» não aparece no Nativo")
