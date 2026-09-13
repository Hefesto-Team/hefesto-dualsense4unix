#!/usr/bin/env python3
"""A TELA NÃO NARRA O GESTO QUE DEU CERTO — TELA-CALADA-01, 13/09/2026.

A palavra dela, com a foto do rodapé:

    *"essas frases de status que aparecem no rodapé isso não deveria estar
    aparecendo"* — *"em todas as abas da interface"*

O `71c69c57` tirou a TARJA. O recado ainda chegava por três portas: o CARTÃO
do controle, as FAIXAS `data-hef-recados` da 01 e da 05, e a ABA SEGUINTE.
Esta régua cobra as três, no piloto do produto, com a janela OCULTA:

1. **o sucesso não deposita.** Um gesto que volta com `{"recado": …}` não põe
   `.hef-recado` em lugar nenhum — nem na faixa da 01 (o recibo do
   «Reconectar»), nem no cartão da 02 — e a frase vai ao diário da janela como
   `[relato] <página> · <gesto>: <frase>`;
2. **a recusa fica, e só na página em que nasceu.** Recusa no 🎙 do p1 da 02,
   navega para a 03 (que tem o cartão do MESMO controle): zero recado na 03. De
   volta à 02 dentro dos 30 s, ela está lá — o filtro é da página, não uma
   borracha na navegação;
3. **o rodapé não devolve recado.** `rodape._recado` relata e devolve `None`;
   quem repõe o atalho da Steam é a carona, não a frase.

O QUE ESTA RÉGUA NÃO COBRA, e é medido e relatado na entrega: o item 4 da
sprint (recusa de gesto sem coluna não pousa em cartão). O pouso de uma recusa
é INVISÍVEL — o recorte do botão depois do pouso é byte a byte o de antes do
clique —, e a sprint manda parar nesse caso.

AS MORDIDAS:

* devolva o depósito de tom `sucesso` em `Piloto._deu_certo_dizendo` →
  reprovam os casos do sucesso (a faixa da 01, o cartão da 02 e o unitário do
  depósito);
* tire o filtro de página de `_recados_para_a_tela` → reprova
  `test_a_recusa_nao_segue_para_a_aba_seguinte`;
* devolva `{"recado": frase}` em `rodape._recado` → reprova o unitário do
  rodapé.
"""
from __future__ import annotations

import contextlib
import io
import json
import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: A MESA DUBLÊ, na faixa sintética da casa. Nada de MAC real em arquivo
#: versionado — há dois portões, e eles não perdoam.
UNIQ_P1 = "aa:bb:cc:00:00:01"
UNIQ_P2 = "aa:bb:cc:00:00:02"

#: O `uniq` NORMALIZADO, escrito à mão: a régua confere o VALOR que o produto
#: usa, e importar a mesma função dos dois lados faria os dois errarem juntos.
CHAVE_P1 = "aabbcc000001"

#: AS TRÊS FRASES DE PROVA. Únicas de propósito: a leitura procura cada uma no
#: TEXTO INTEIRO do documento, e não só nos nós de recado — uma frase que
#: chegasse à tela por outro caminho também reprova.
FRASES = {
    "reconectar": "regua-calada: os controles voltaram na ordem de antes",
    "mic": "regua-calada: o microfone ligou e o canal está mudo",
    "recusa": "regua-calada: o Hefesto não confirmou o mudo do microfone",
}

PAGINA_01 = "01-jogar.html"
PAGINA_02 = "02-controles.html"
PAGINA_03 = "03-gatilhos.html"
MIC_P1 = '[data-controle="p1"] [data-mudo="microfone"]'
RECONECTAR = 'button[data-gesto="reconectar"]'

#: QUANTO SE ESPERA DEPOIS DE A PÁGINA FICAR PRONTA: uma dúzia de tiques de
#: 100 ms, para a leitura ver o que a PINTURA põe, e não só o instante do clique.
ASSENTAR_MS = 1200

#: QUANTO SE ESPERA DEPOIS DO CLIQUE: o gesto é instantâneo, e 700 ms cobrem a
#: pintura na hora e seis tiques por cima dela.
DEPOIS_DO_CLIQUE_MS = 700


def _ctl(uniq: str, transporte: str, jogador: int) -> dict:
    return {"uniq": uniq, "connected": True, "transport": transporte,
            "player": jogador, "audio": {"mic_mudo": False}}


ESTADO = {
    "active_profile": "regua",
    "gamepad_emulation": {"flavor": "dualsense"},
    "controllers": [_ctl(UNIQ_P1, "usb", 1), _ctl(UNIQ_P2, "bt", 2)],
}

LER_A_TELA = r"""
(function(frases){
  const recados = [];
  for(const el of document.querySelectorAll('.hef-recado')){
    const c = el.closest('[data-controle],[data-uniq]');
    recados.push({
      chave: el.getAttribute('data-hef-recado') || '',
      texto: (el.textContent || '').trim(),
      tom: el.dataset.hefTom || '',
      na_faixa: !!el.closest('[data-hef-recados]'),
      dentro_de: c ? (c.dataset.controle || c.dataset.uniq || '') : '',
    });
  }
  const corpo = document.body ? (document.body.textContent || '') : '';
  const vistas = {};
  for(const k of Object.keys(frases)) vistas[k] = corpo.indexOf(frases[k]) >= 0;
  return JSON.stringify({
    aba: location.pathname.split('/').pop(),
    recados: recados,
    vistas: vistas,
    faixas: document.querySelectorAll('[data-hef-recados]').length,
    tem_p1: !!document.querySelector('[data-controle="p1"]'),
  });
})(%s)
"""

CLICAR = r"""
(function(sel){
  const b = document.querySelector(sel);
  if(!b) return 'NAO ACHEI ' + sel;
  b.click();
  return 'cliquei';
})(%s)
"""


#: O PERFIL ATIVO NO DISCO — mesma razão das réguas irmãs: a pintura da 02 lê o
#: perfil ativo, e um anotador sem arquivo mediria outro caminho.
@pytest.fixture(scope="module", autouse=True)
def _perfil_ativo_no_disco() -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    profiles_dir().mkdir(parents=True, exist_ok=True)
    if not (profiles_dir() / "regua.json").exists():
        loader.save_profile(Profile(name="regua", match=MatchManual()),
                            origem="regua")


@pytest.fixture(scope="module")
def medido() -> dict:
    """Abre o piloto DE VERDADE, oculto, e anda 01 → 02 → 03 → 02."""
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import GLib, Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")

    import argparse
    import time as _time

    import hefesto_vivo as hv

    # OS DUBLÊS SÃO DEVOLVIDOS NO FIM: `mesa_viva` e o registro `GESTOS` são
    # módulos compartilhados do produto, e deixá-los sujos entrega uma mesa de
    # mentira a todo vizinho que abrir um `Piloto` depois, no mesmo processo.
    chave_01 = (PAGINA_01, "reconectar")
    chave_02 = (PAGINA_02, "mudo")
    guardado_gestos = {k: hv.pacotes.GESTOS.get(k) for k in (chave_01, chave_02)}
    guardado_estado = hv.mesa_viva.estado_do_daemon
    hv.mesa_viva.estado_do_daemon = lambda *a, **k: ESTADO  # type: ignore[assignment]

    def reconectar_que_diz(ctx, o, p):
        return {"recado": FRASES["reconectar"]}

    def mudo_que_diz(ctx, o, p):
        return {"recado": FRASES["mic"]}

    def mudo_que_recusa(ctx, o, p):
        raise RuntimeError(FRASES["recusa"])

    hv.pacotes.GESTOS[chave_01] = reconectar_que_diz
    hv.pacotes.GESTOS[chave_02] = mudo_que_diz

    args = argparse.Namespace(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="",
        abre=PAGINA_01, prova_no_aparelho=False, entre=2500,
        espera=1200, incluir_perigosos=False, prova_clique="", sem_cor=True,
        prova_de_mockup=False, voltas_por_aba=8, teto_de_mockup=-1,
        sem_cravado=False, sem_selo=False,
    )
    piloto = hv.Piloto(args)
    fora: dict[str, object] = {}
    diario = io.StringIO()

    def ler(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = (f"ERRO {erro}" if erro is not None
                            else json.loads(str(valor)))
        return _leu

    def anotar(rotulo: str):
        def _leu(valor, erro):
            fora[rotulo] = f"ERRO {erro}" if erro is not None else str(valor)
        return _leu

    def ler_a_tela(rotulo: str) -> None:
        piloto.ponte.perguntar(LER_A_TELA % json.dumps(FRASES), ler(rotulo))

    def clicar(seletor: str, rotulo: str) -> None:
        piloto.ponte.perguntar(CLICAR % json.dumps(seletor), anotar(rotulo))

    def desfecho(chave: tuple[str, str]) -> list[str]:
        return list(piloto.desfechos.get(f"{chave[0]}:{chave[1]}", ()))

    def abrir(pagina: str, depois) -> bool:
        """Navega e só segue quando a página NOVA está pronta e assentou.

        A aba que o piloto guarda muda no fim da carga, e `pronto` cai e volta
        na instalação: esperar pelos dois é o que impede a leitura de medir a
        aba anterior.
        """
        piloto._ir(pagina)

        def espera() -> bool:
            if piloto.pagina != pagina or not piloto.pronto:
                return True
            GLib.timeout_add(ASSENTAR_MS, depois)
            return False

        GLib.timeout_add(200, espera)
        return False

    # ---- 1. a 01: o «Reconectar» volta com recado -----------------------
    def na_01() -> bool:
        if piloto.pagina != PAGINA_01 or not piloto.pronto:
            return True
        ler_a_tela("01-antes")
        clicar(RECONECTAR, "01-clique")
        GLib.timeout_add(DEPOIS_DO_CLIQUE_MS, leu_a_01)
        return False

    def leu_a_01() -> bool:
        ler_a_tela("01-depois")
        fora["01-desfecho"] = desfecho(chave_01)
        fora["01-deposito"] = sorted(piloto._recados)
        GLib.timeout_add(300, lambda: abrir(PAGINA_02, na_02))
        return False

    # ---- 2. a 02: sucesso com recado no cartão, depois a recusa ----------
    def na_02() -> bool:
        ler_a_tela("02-antes")
        clicar(MIC_P1, "02-clique-sucesso")
        GLib.timeout_add(DEPOIS_DO_CLIQUE_MS, leu_o_sucesso_da_02)
        return False

    def leu_o_sucesso_da_02() -> bool:
        ler_a_tela("02-depois-do-sucesso")
        fora["02-desfecho-sucesso"] = desfecho(chave_02)
        fora["02-deposito-sucesso"] = sorted(piloto._recados)
        GLib.timeout_add(300, a_recusa_da_02)
        return False

    def a_recusa_da_02() -> bool:
        hv.pacotes.GESTOS[chave_02] = mudo_que_recusa
        clicar(MIC_P1, "02-clique-recusa")
        GLib.timeout_add(DEPOIS_DO_CLIQUE_MS, leu_a_recusa_da_02)
        return False

    def leu_a_recusa_da_02() -> bool:
        ler_a_tela("02-com-a-recusa")
        fora["02-desfecho-recusa"] = desfecho(chave_02)
        GLib.timeout_add(300, lambda: abrir(PAGINA_03, na_03))
        return False

    # ---- 3. a 03: o cartão do MESMO controle, e a recusa não vem ---------
    def na_03() -> bool:
        ler_a_tela("03-depois-de-navegar")
        fora["03-deposito"] = sorted(piloto._recados)
        GLib.timeout_add(300, lambda: abrir(PAGINA_02, de_volta_na_02))
        return False

    # ---- 4. de volta à 02, dentro dos 30 s -------------------------------
    def de_volta_na_02() -> bool:
        ler_a_tela("02-de-volta")
        GLib.timeout_add(400, fim)
        return False

    def fim() -> bool:
        fora["diario"] = diario.getvalue()
        Gtk.main_quit()
        return False

    GLib.timeout_add(400, lambda: piloto._ir(args.abre))
    GLib.timeout_add(2000, na_01)
    # O RELÓGIO DE SEGURANÇA GUARDA O SEU `id` e é desarmado no `finally`: um
    # `timeout_add` pendente depois da fixture dispara DENTRO do laço do PRÓXIMO
    # teste de GUI do mesmo processo.
    guarda = GLib.timeout_add(60000, Gtk.main_quit)
    try:
        # O DIÁRIO DA JANELA É O `stderr` DO PROCESSO, e é para lá que o relato
        # do sucesso vai. O `redirect_stderr` troca `sys.stderr` enquanto o laço
        # roda — o `print(..., file=sys.stderr)` do piloto resolve o nome na hora
        # da chamada, então cai aqui.
        #
        # O LAÇO REENTRA ATÉ O ÚLTIMO PASSO: um `Gtk.main_quit` pendente de outro
        # teste de GUI do mesmo processo cai dentro deste `Gtk.main()` e o
        # encerra no meio (ver `test_o_recado_de_sucesso_pousa_no_cartao`).
        limite = _time.monotonic() + 60.0
        with contextlib.redirect_stderr(diario):
            while "diario" not in fora and _time.monotonic() < limite:
                Gtk.main()
    finally:
        GLib.source_remove(guarda)
        piloto.pronto = False
        piloto.tela.janela.destroy()
        hv.mesa_viva.estado_do_daemon = guardado_estado  # type: ignore[assignment]
        for k, velho in guardado_gestos.items():
            if velho is None:
                hv.pacotes.GESTOS.pop(k, None)
            else:
                hv.pacotes.GESTOS[k] = velho
    assert "diario" in fora, (
        f"o roteiro não chegou ao fim — o que voltou foi {sorted(fora)}. O "
        f"último passo é o `fim()`, e esperar por qualquer anterior deixa a "
        f"régua verde sobre uma medição pela metade.")
    return fora


def _leitura(medido: dict, rotulo: str) -> dict:
    leitura = medido[rotulo]
    assert isinstance(leitura, dict), f"{rotulo}: {leitura!r}"
    return leitura


# --------------------------------------------------------------------------
# 0. os cliques aconteceram e os gestos deram o desfecho pedido
# --------------------------------------------------------------------------
def test_os_tres_gestos_chegaram_ao_desfecho_pedido(medido: dict) -> None:
    """Sem isto, as réguas abaixo passariam sobre cliques que nunca saíram."""
    assert medido["01-clique"] == "cliquei", medido["01-clique"]
    assert medido["01-desfecho"] == ["aplicou", ""], medido["01-desfecho"]
    assert medido["02-clique-sucesso"] == "cliquei", medido["02-clique-sucesso"]
    assert medido["02-desfecho-sucesso"] == ["aplicou", ""], medido["02-desfecho-sucesso"]
    assert medido["02-clique-recusa"] == "cliquei", medido["02-clique-recusa"]
    classe, frase = medido["02-desfecho-recusa"]
    assert classe == "recusou dizendo" and FRASES["recusa"] in frase, (
        medido["02-desfecho-recusa"])


# --------------------------------------------------------------------------
# 1. o sucesso não deposita — nem faixa, nem cartão
# --------------------------------------------------------------------------
def test_o_recibo_do_reconectar_nao_escreve_na_faixa_da_01(medido: dict) -> None:
    """O «Reconectar» deu certo e a 01 inteira fica muda — faixa e cartão.

    A FAIXA SAIU DA PÁGINA — 13/09/2026, na costura com a
    JOGAR-A-FAIXA-QUE-PULA-01: o nó `recibo-do-reconectar` empurrava o botão, e
    a página deixou de declarar lugar de recado. Esta régua exigia a faixa como
    prova de que media alguma coisa; sem ela, um sucesso depositado cai no
    FALLBACK do `pintar_recados` — o cartão do P1 —, e por isso a leitura
    `recados` varre o documento inteiro, não só a faixa. A prova de que ainda
    mede é a mordida: devolver o `_depositar` do sucesso põe o recibo no cartão
    e reprova aqui e no depósito.
    """
    depois = _leitura(medido, "01-depois")
    assert depois["aba"] == PAGINA_01, depois["aba"]
    assert depois["faixas"] == 0, (
        "a 01 voltou a declarar faixa de recado — a JOGAR-A-FAIXA-QUE-PULA-01 a "
        "tirou porque o recibo empurrava o «Reconectar»")
    assert depois["recados"] == [], (
        f"o «Reconectar» deu certo e a tela ganhou recado: {depois['recados']!r}. "
        f"É a frase de status que ela mandou tirar, *em todas as abas*.")
    assert not depois["vistas"]["reconectar"], (
        "a frase do gesto que deu certo chegou ao texto da 01 por outro caminho")
    assert medido["01-deposito"] == [], (
        f"o sucesso entrou no depósito de recados: {medido['01-deposito']!r}")


def test_o_sucesso_da_02_nao_pousa_no_cartao(medido: dict) -> None:
    depois = _leitura(medido, "02-depois-do-sucesso")
    assert depois["tem_p1"], "a 02 sem o cartão do p1 — não há cartão a medir"
    assert depois["recados"] == [], (
        f"o 🎙 deu certo e o cartão do p1 ganhou recado: {depois['recados']!r}")
    assert not depois["vistas"]["mic"], (
        "a frase do gesto que deu certo chegou ao texto da 02 por outro caminho")
    assert medido["02-deposito-sucesso"] == [], medido["02-deposito-sucesso"]


def test_a_frase_do_sucesso_vai_ao_diario(medido: dict) -> None:
    """A frase não some: vai ao diário da janela, que é o `interface.log`."""
    diario = str(medido["diario"])
    for linha in (f"[relato] {PAGINA_01} · reconectar: {FRASES['reconectar']}",
                  f"[relato] {PAGINA_02} · mudo: {FRASES['mic']}"):
        assert linha in diario, (
            f"o relato {linha!r} não chegou ao diário — a frase do sucesso "
            f"sumiu inteira, e quem depura perde o que o gesto disse. "
            f"Diário: {diario[-800:]!r}")


# --------------------------------------------------------------------------
# 2. a recusa fica — e só na página em que nasceu
# --------------------------------------------------------------------------
def test_a_recusa_continua_no_cartao_de_quem_foi_clicado(medido: dict) -> None:
    """A recusa é o único aviso de que o clique NÃO valeu, e ela fica."""
    leitura = _leitura(medido, "02-com-a-recusa")
    assert [(r["chave"], r["dentro_de"], r["tom"]) for r in leitura["recados"]] == [
        (CHAVE_P1, "p1", "recusa")], leitura["recados"]
    assert FRASES["recusa"] in leitura["recados"][0]["texto"], leitura["recados"]


def test_a_recusa_nao_segue_para_a_aba_seguinte(medido: dict) -> None:
    """A 03 tem o cartão do MESMO controle — e a recusa da 02 não pousa nele.

    As duas primeiras asserções dão dente à terceira: a página é a 03, o cartão
    do p1 está nela, e a recusa continua no depósito. Sem o filtro de página,
    o tique a entregaria a esse cartão por até 30 s.
    """
    leitura = _leitura(medido, "03-depois-de-navegar")
    assert leitura["aba"] == PAGINA_03, leitura["aba"]
    assert leitura["tem_p1"], "a 03 sem o cartão do p1 — a régua passaria sobre nada"
    assert medido["03-deposito"] == [CHAVE_P1], (
        f"a recusa saiu do depósito ({medido['03-deposito']!r}) — sem ela lá, "
        f"o zero abaixo não prova o filtro")
    assert leitura["recados"] == [], (
        f"a recusa nascida na 02 reapareceu na 03: {leitura['recados']!r}")
    assert not leitura["vistas"]["recusa"], leitura


def test_a_recusa_volta_quando_ela_volta_a_pagina(medido: dict) -> None:
    """O filtro é da página, não uma borracha na navegação.

    Dentro dos 30 s dela, a recusa continua sendo daquela página: quem volta à
    02 a encontra no cartão do p1, como deixou.
    """
    leitura = _leitura(medido, "02-de-volta")
    assert leitura["aba"] == PAGINA_02, leitura["aba"]
    assert [(r["chave"], r["dentro_de"]) for r in leitura["recados"]] == [
        (CHAVE_P1, "p1")], leitura["recados"]


# --------------------------------------------------------------------------
# 3. as duas metades sem janela — o canal e o rodapé
# --------------------------------------------------------------------------
class _PilotoQueAnota:
    """Os dois vizinhos que `_deu_certo_dizendo` chama, anotando o que recebem.

    O `_depositar` daqui NÃO pinta nada — ele só registra. É o que torna a
    mordida binária: devolver o depósito do sucesso faz esta lista deixar de
    ser vazia.
    """

    def __init__(self) -> None:
        self.depositos: list[tuple] = []
        self.respostas: list[object] = []

    def _depositar(self, *args: object, **kwargs: object) -> None:
        self.depositos.append((args, kwargs))

    def _deu_certo(self, pagina: str, nome: str, resposta: object = None) -> bool:
        self.respostas.append(resposta)
        return False


def test_o_gesto_que_deu_certo_nao_deposita_e_relata(capsys) -> None:
    pytest.importorskip("gi", reason="o piloto importa o GTK")
    import hefesto_vivo as hv

    anotador = _PilotoQueAnota()
    volta = hv.Piloto._deu_certo_dizendo(
        anotador, PAGINA_02, "mudo", CHAVE_P1,
        {"recado": "  a frase do dono  ", "colunas": {"p1": {"x": "1"}}})
    assert volta is False
    assert anotador.depositos == [], (
        f"o sucesso foi depositado: {anotador.depositos!r} — é a porta do cartão e "
        f"da faixa que ela mandou fechar")
    # O `recado` continua SAINDO da carga antes da pintura: ele não é endereço.
    assert anotador.respostas == [{"colunas": {"p1": {"x": "1"}}}], anotador.respostas
    assert f"[relato] {PAGINA_02} · mudo: a frase do dono" in capsys.readouterr().err


def test_sem_frase_o_sucesso_nem_relata(capsys) -> None:
    pytest.importorskip("gi", reason="o piloto importa o GTK")
    import hefesto_vivo as hv

    anotador = _PilotoQueAnota()
    hv.Piloto._deu_certo_dizendo(anotador, PAGINA_02, "mudo", CHAVE_P1,
                                 {"recado": "   "})
    assert anotador.depositos == []
    assert anotador.respostas == [{}]
    assert "[relato]" not in capsys.readouterr().err


def test_o_rodape_nao_devolve_recado_e_relata(capsys) -> None:
    """`rodape._recado` devolve `None` e leva a notícia da carona ao diário."""
    from hefesto_dualsense4unix.interface.pacotes import rodape

    assert rodape._recado("  Reposto o atalho de inicialização: 3357650  ") is None
    err = capsys.readouterr().err
    assert "Reposto o atalho de inicialização: 3357650" in err, err
    assert rodape._recado("   ") is None
    assert "[relato]" not in capsys.readouterr().err
