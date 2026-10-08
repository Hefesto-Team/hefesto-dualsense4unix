"""O que as cinco réguas de A JANELA ABERTA NÃO GASTA O PROCESSADOR dividem.

O arquivo único levava 217 s sozinho (A-JANELA-ABERTA-CABE-NA-PARTE-01): o tempo é o do
relógio do produto, e cada cenário abre o piloto oculto de verdade. Partido em cinco, o
ajudante mora aqui, sem prefixo `test_` (como `bancada_das_ordens.py` e `mesa_do_mockup.py`),
e cada arquivo de teste traz só as fixtures dele. O `scripts/rodar-a-suite.sh` conta este
módulo como carga do WebKit (o `_gtk` o pede): quem o importa roda em processo próprio.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import itertools
import json
import pathlib
import shutil
import sys
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

FIXTURE = RAIZ / "tests/fixtures/state_full_quatro_controles.json"

MESAS = {1: (0,), 2: (0, 2), 4: (0, 1, 2, 3)}

TIQUES_POR_FASE = 40

#: O TETO de uma fase é este tanto de vezes o tempo nominal dela, que sai do
#: `TIQUE_MS` do produto (ver `_teto_da_fase_s`). Bater o teto não é pulo: a
#: fase anota a fome em `fora.famintas`, e o `_sem_fome` reprova com a causa
#: medida: a máquina, ou o produto quando o tique para com o laço andando.
VEZES_O_NOMINAL = 5

ASSENTAR_S = 0.6

ATRASO_NA_VOLTA_S = 0.12


def _estado_da_fixture(n: int) -> dict[str, Any]:
    d = json.loads(FIXTURE.read_text(encoding="utf-8"))
    d["controllers"] = [d["controllers"][i] for i in MESAS[n]]
    return d


class _Estado:
    """O `state_full` de mentira — conta as leituras e anda como pedirem.

    Ele entra no lugar de `mesa_viva.estado_do_daemon`, que é o `ler` que o
    `LeitorDoEstado` do piloto usa. Contar AQUI é contar as perguntas ao
    daemon, que é o que a janela escondida não pode fazer.
    """

    def __init__(self, n: int, anda: str = "") -> None:
        self.base = _estado_da_fixture(n)
        self.anda = anda
        self.leituras = 0
        self.passo = 0
        self.fixo: dict[str, Any] | None = None
        self.atraso_s = 0.0
        self._trava = threading.Lock()

    def __call__(self, *_a: Any, **_k: Any) -> dict[str, Any]:
        if self.atraso_s:
            time.sleep(self.atraso_s)
        with self._trava:
            self.leituras += 1
            self.passo += 1
            i = self.passo
        if self.fixo is not None:
            return self.fixo
        if not self.anda:
            return self.base
        st = copy.deepcopy(self.base)
        for k, c in enumerate(st["controllers"]):
            ent = c.setdefault("inputs", {})
            if "giro" in self.anda:
                ent["gyro"] = {eixo: round(((i * (3 + j) + k) % 31 - 15) / 10, 2)
                               for j, eixo in enumerate(("x", "y", "z"))}
            if "analogico" in self.anda:
                for j, eixo in enumerate(("lx", "ly", "rx", "ry")):
                    ent[eixo] = (i * 37 + 61 * j + 17 * k) % 256
        return st


class _PonteDeMentira:
    """A ponte do piloto com o daemon, sem daemon: anota cada pedido e devolve `{}`."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def __getattr__(self, nome: str) -> Any:
        if nome.startswith("_"):
            raise AttributeError(nome)

        def anotar(*_a: Any, **_k: Any) -> dict[str, Any]:
            self.chamadas.append(nome)
            return {}

        return anotar


def _carga_do_pedido(js: str) -> dict[str, Any] | None:
    """A carga que um `PEDIR_A_PINTURA` leva, ou `None` se o JS é outra coisa."""
    marca = "? window.__hef.pintar("
    if marca not in js:
        return None
    return dict(json.loads(js.split(marca, 1)[1].rsplit(") : -1", 1)[0]))


def _args(**extra: Any) -> argparse.Namespace:
    base = dict(
        oculta=True, segundos=0.0, passear=False, parada=900, foto="", abre="",
        prova_no_aparelho=False, entre=2500, espera=1200, incluir_perigosos=False,
        prova_clique="", sem_cor=True, sem_ondas=False, prova_de_mockup=False,
        voltas_por_aba=8, teto_de_mockup=-1, sem_cravado=False, sem_selo=False,
        conta_mutacoes=0)
    base.update(extra)
    return argparse.Namespace(**base)


def publicar_as_de_hoje(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """As páginas publicadas, com a 02 da BANCADA — a que o gerador faz hoje.

    Cada arquivo de teste a embrulha na fixture `publicado_de_hoje` do módulo dele."""
    from hefesto_dualsense4unix.interface import onde

    pasta = tmp_path_factory.mktemp("publicado-de-hoje")
    for p in onde.PUBLICADO.glob("*.html"):
        shutil.copy2(p, pasta / p.name)
    shutil.copy2(onde.pagina("02-controles.html"), pasta / "02-controles.html")
    return pasta


def _gtk() -> Any:
    gi = pytest.importorskip("gi", reason="a GUI precisa do PyGObject do sistema")
    gi.require_version("Gtk", "3.0")
    gi.require_version("WebKit2", "4.1")
    from gi.repository import Gtk

    if not Gtk.init_check(None)[0]:
        pytest.skip("sem sessão gráfica — o WebKit não abre")
    return Gtk


def _nominal_s(quantos: int) -> float:
    """Quanto `quantos` tiques duram na cadência do produto (`hv.TIQUE_MS`)."""
    import hefesto_vivo as hv

    return float(quantos * hv.TIQUE_MS) / 1000.0


def _teto_da_fase_s(fora: Any, quantos: int) -> float:
    """O teto de uma fase de `quantos` tiques: `VEZES_O_NOMINAL` o nominal dela."""
    proprio = getattr(fora, "teto_da_fase_s", None)
    return float(proprio) if proprio else VEZES_O_NOMINAL * _nominal_s(quantos)


def _maior_buraco(de: float, tiques: list[float], agora: float) -> float:
    """O maior intervalo sem tique na fase, contando da abertura dela até agora."""
    marcas = [de, *tiques, agora]
    return max((b - a for a, b in itertools.pairwise(marcas)), default=0.0)


def _fase(fora: Any, nome: str, de: float, quantos: int, teto_s: float, *,
          ate: float = float("inf"), agora: float | None = None) -> bool:
    """A fase `nome` acabou? Acaba quando junta `quantos` tiques em `[de, ate]`."""
    agora = time.monotonic() if agora is None else agora
    fora.fases[nome] = quantos
    tiques = [x.t for x in fora.ticks if de <= x.t <= ate]
    if len(tiques) >= quantos:
        return True
    if agora - de < teto_s:
        return False
    fora.famintas[nome] = (len(tiques), agora - de, _maior_buraco(de, tiques, agora))
    passos = getattr(fora, "passos", None)
    if passos is not None:
        fora.lacos[nome] = _maior_buraco(de, [p for p in passos if de <= p <= agora], agora)
    return True


def _virgula(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _o_tique_parou_com_o_laco_andando(buraco: float, laco: float | None) -> bool:
    """A fome é do PRODUTO? O tique e o `passo` do roteiro rodam no mesmo laço"""
    if laco is None:
        return False
    return buraco > 3 * max(laco, _nominal_s(1))


def _sem_fome(fora: Any, *nomes: str) -> None:
    """Reprova, com a causa escrita, se alguma destas fases bateu o teto."""
    for nome in nomes:
        if nome in fora.famintas:
            tiques, segundos, buraco = fora.famintas[nome]
            laco = getattr(fora, "lacos", {}).get(nome)
            if _o_tique_parou_com_o_laco_andando(buraco, laco):
                causa = (f"o laço do GTK andou (maior buraco dele: {_virgula(laco or 0.0)} "
                         "s) e o tique parou: é o produto, e não a máquina")
            else:
                causa = "o laço do GTK andou devagar demais para medir"
            raise AssertionError(
                f"a fase {nome} juntou {tiques} de {fora.fases[nome]} tiques em "
                f"{_virgula(segundos)} s (maior buraco: {_virgula(buraco)} s): {causa}")


def _correr(publicado: pathlib.Path, pagina: str, n: int, roteiro: Any, *,
            anda: str = "", teto_s: float | None = None,
            ajuste: Any = None, teto_da_fase_s: float | None = None) -> SimpleNamespace:
    """Roda o piloto oculto na página pedida, com `n` controles, e segue o `roteiro`."""
    gtk = _gtk()
    from gi.repository import GLib

    import hefesto_vivo as hv
    from hefesto_dualsense4unix.app import audio_saida
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as el
    from hefesto_dualsense4unix.integrations import ondas_de_som
    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02
    from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

    estado = _Estado(n, anda)
    fora = SimpleNamespace(ticks=[], pinturas=[], marcos={}, estado=estado,
                           pactl=[], ponte=_PonteDeMentira(), mudas=False,
                           avaliados={}, piloto=None, avisos=[], acabou=False,
                           comeco=0.0, fases={}, famintas={}, passos=[], lacos={},
                           teto_da_fase_s=teto_da_fase_s)
    if teto_s is None:
        teto_s = 8 * max(_teto_da_fase_s(fora, TIQUES_POR_FASE), _teto_da_espera_s()) + 30.0

    def pactl(argv: list[str]) -> str:
        fora.pactl.append((time.monotonic(), " ".join(argv)))
        return ""

    def pactl_da_eleicao(argv: list[str]) -> tuple[int, str]:
        fora.pactl.append((time.monotonic(), " ".join(argv)))
        return (1, "")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(hv.mesa_viva, "estado_do_daemon", estado)
        mp.setattr(hv, "ponte", fora.ponte)
        mp.setattr(onde, "PUBLICADO", publicado)
        mp.setattr(a02, "_ENDERECOS", None)
        mp.setattr(audio_saida, "rodar_leitura", pactl)
        mp.setattr(el, "_rodar", pactl_da_eleicao)
        mp.setattr(ondas_de_som, "_LIGADO", [False])
        mp.setattr(a02, "no_do_microfone",
                   lambda c: f"mic-{c.get('uniq')}" if isinstance(c, dict) else "")
        if ajuste is not None:
            ajuste(mp, hv)
        piloto = hv.Piloto(_args())
        fora.piloto = piloto
        original_perguntar = piloto.ponte.perguntar
        no_tique = [False]

        def perguntar(js: str, cb: Any) -> None:
            carga = _carga_do_pedido(js)
            if carga is not None:
                no_tique[0] = True
                fora.pinturas.append((time.monotonic(), carga, len(js)))
            original_perguntar(js, cb)

        piloto.ponte.perguntar = perguntar  # type: ignore[method-assign]
        tique_original = piloto._tique

        def tique() -> bool:
            if fora.acabou:
                return False
            no_tique[0] = False
            volta = tique_original()
            fora.ticks.append(SimpleNamespace(
                t=time.monotonic(), escondida=piloto._escondida, pintou=no_tique[0],
                leituras=estado.leituras, pactl=len(fora.pactl),
                batidas=fora.ponte.chamadas.count("rumble_set_checked"),
                externos=fora.ponte.chamadas.count("resultado"),
                ondas=len(ondas_de_som.o_de_sempre()._desejado)))
            return volta

        piloto._tique = tique  # type: ignore[method-assign]
        mudou_original = piloto._a_janela_mudou

        def a_janela_mudou(escondida: bool) -> None:
            if escondida != piloto._escondida:
                fora.avisos.append((time.monotonic(), escondida, estado.leituras))
            mudou_original(escondida)

        piloto._a_janela_mudou = a_janela_mudou  # type: ignore[method-assign]
        comeco = [0.0]

        def passo() -> bool:
            fora.passos.append(time.monotonic())
            if not piloto.pronto or not piloto.tela.na_aba:
                return True
            if piloto.pagina != pagina:
                if "indo" not in fora.marcos:
                    fora.marcos["indo"] = time.monotonic()
                    piloto._ir(pagina)
                return True
            if not comeco[0]:
                comeco[0] = fora.comeco = time.monotonic()
                a05._EM_TESTE.add(str(estado.base["controllers"][0]["uniq"]))
                a05._BATEU_EM.clear()
            if roteiro(fora, piloto, time.monotonic() - comeco[0]):
                return True
            with contextlib.suppress(SystemExit):
                try:
                    piloto._relatar()
                except SystemExit:
                    fora.mudas = True
            gtk.main_quit()
            return False

        guarda = GLib.timeout_add(int(teto_s * 1000), gtk.main_quit)
        GLib.timeout_add(50, passo)
        try:
            gtk.main()
        finally:
            fora.acabou = True
            piloto.pronto = False
            GLib.source_remove(guarda)
            a05.parar_o_teste()
            piloto._estado_vivo.parar()
            piloto.tela.janela.destroy()
            ondas_de_som.o_de_sempre().seguir({})
    assert comeco[0], f"a página {pagina} nunca ficou de pé"
    return fora


def _inteira(carga: dict[str, Any]) -> bool:
    """A carga inteira traz a FITA e o ALVO, que a diferença só traz se mudarem."""
    return "alvo" in carga and "fita" in carga


def _teto_da_espera_s() -> float:
    """O teto de uma ESPERA pelo produto (o `escondeu`, o `voltou`, uma leitura)."""
    return VEZES_O_NOMINAL * _nominal_s(TIQUES_POR_FASE)


def _roteiro_esconde_e_volta(fora: Any, piloto: Any, _t: float) -> bool:
    """40 tiques à vista, 40 escondida, 40 de volta — contados."""
    marcos = fora.marcos
    quantos = TIQUES_POR_FASE
    teto = _teto_da_fase_s(fora, quantos)
    if "esconde" not in marcos:
        if not _fase(fora, "à vista", fora.comeco, quantos, teto):
            return True
        marcos["esconde"] = time.monotonic()
        piloto.tela.janela.hide()
        return True
    if "mostra" not in marcos:
        if "escondeu" not in marcos:
            if piloto._escondida:
                marcos["escondeu"] = time.monotonic()
            elif time.monotonic() - marcos["esconde"] < _teto_da_espera_s():
                return True
            else:
                return _mostrar(fora, piloto)
        de, ate = _janela_escondida(fora)
        if not _fase(fora, "escondida", de, quantos, teto, ate=ate):
            return True
        return _mostrar(fora, piloto)
    if "voltou" not in marcos:
        if piloto._escondida or "escondeu" not in marcos:
            return bool(time.monotonic() - marcos["mostra"] < _teto_da_espera_s())
        marcos["voltou"] = time.monotonic()
    return not _fase(fora, "de volta", _janela_escondida(fora)[1], quantos, teto)


def _mostrar(fora: Any, piloto: Any) -> bool:
    """A volta: o daemon passa a demorar como o de verdade, e a janela reaparece."""
    fora.marcos["mostra"] = time.monotonic()
    fora.estado.atraso_s = ATRASO_NA_VOLTA_S
    piloto.tela.janela.show_all()
    return True


CENARIOS = [(p, n) for p in ("01-jogar.html", "02-controles.html", "08-conexoes.html")
            for n in (1, 2, 4)]


def _janela_escondida(fora: Any) -> tuple[float, float]:
    """A fase escondida, com UM dono: `(de, ate)`, para o roteiro contar e as"""
    de = fora.marcos["escondeu"] + ASSENTAR_S
    ate = next((t for t, escondida, _ in fora.avisos
                if not escondida and t >= fora.marcos["esconde"]),
               fora.marcos.get("mostra", float("inf")))
    return de, ate


def _entre(fora: Any, de: float, ate: float) -> list[Any]:
    return [x for x in fora.ticks if de <= x.t <= ate]


def _os_primeiros(fora: Any, de: float, quantos: int) -> list[Any]:
    """Os `quantos` primeiros tiques desde `de`: a fase que a régua cobra."""
    return [x for x in fora.ticks if x.t >= de][:quantos]


def _a_escondida_nao_trabalha(fora: Any) -> None:
    """As contas da R1 sobre a fase escondida de um cenário (ver a régua)."""
    assert "escondeu" in fora.marcos, (
        "a página nunca disse que estava escondida — o `hide()` da janela oculta "
        "não chegou ao `document.hidden`, ou o aviso não chegou ao piloto")
    _sem_fome(fora, "escondida")
    de, ate = _janela_escondida(fora)
    dentro = _entre(fora, de, ate)
    assert len(dentro) >= 25, f"poucos tiques escondidos para medir: {len(dentro)}"
    pinturas = [p for p in fora.pinturas if de <= p[0] <= ate]
    assert not pinturas, (
        f"{len(pinturas)} pintura(s) com a janela escondida em "
        f"{fora.pagina} com {fora.n} controle(s)")
    import hefesto_vivo as hv

    leituras = dentro[-1].leituras - dentro[0].leituras
    passo = hv.LeitorDoEstado.SEGUNDOS_ENTRE_LEITURAS_ESCONDIDA
    teto = int((dentro[-1].t - dentro[0].t) / passo) + 1
    assert leituras <= teto, (
        f"{leituras} leitura(s) do estado em {dentro[-1].t - dentro[0].t:.1f} s "
        f"com a janela escondida — o teto é uma a cada {passo} s ({teto})")
    pactl = [c for t, c in fora.pactl if de <= t <= ate]
    assert not pactl, f"`pactl` com a janela escondida: {pactl[:4]}"
    assert all(x.ondas == 0 for x in dentro), (
        "as ondas seguiram querendo nós com a janela escondida")


def _o_coracao_bate_escondido(fora: Any) -> None:
    _sem_fome(fora, "escondida")
    de, ate = _janela_escondida(fora)
    dentro = _entre(fora, de, ate)
    batidas = dentro[-1].batidas - dentro[0].batidas
    assert batidas >= 2, (
        f"{batidas} batida(s) do coração em {ate - de:.1f} s com a janela "
        "escondida e um teste de motor em curso")


def _com_carga(roteiro: Any, *, buraco_s: float = 0.0, lento_s: float = 0.0) -> Any:
    """O roteiro com a máquina ocupada, SEM carregar a máquina do usuário."""
    def com_carga(fora: Any, piloto: Any, t: float) -> bool:
        seguir = roteiro(fora, piloto, t)
        if buraco_s and "esconde" in fora.marcos and "buraco" not in fora.marcos:
            fora.marcos["buraco"] = time.monotonic()
            time.sleep(buraco_s)
        if lento_s and piloto._escondida:
            time.sleep(lento_s)
        return bool(seguir)

    return com_carga


CARGAS = {"buraco": {"buraco_s": 1.4}, "laco-lento": {"lento_s": 0.2}}


def cenarios_da(pagina: str) -> list[tuple[str, int]]:
    """Os cenários de `esconde_e_volta` que são desta página (1, 2 e 4 controles)."""
    return [c for c in CENARIOS if c[0] == pagina]


def ids_dos_cenarios(cenarios: list[tuple[str, int]]) -> list[str]:
    return [f"{p[:2]}-{n}-controles" for p, n in cenarios]


def esconde_e_volta_de(publicado: pathlib.Path, cenario: tuple[str, int]) -> SimpleNamespace:
    """O cenário: o piloto oculto na página, 40 tiques à vista, escondido e de volta."""
    pagina, n = cenario
    fora = _correr(publicado, pagina, n, _roteiro_esconde_e_volta)
    fora.pagina, fora.n = pagina, n
    return fora


def _a_volta_leva_a_carga_inteira(fora: Any) -> None:
    assert "voltou" in fora.marcos, "a página nunca disse que voltou à vista"
    _sem_fome(fora, "de volta")
    voltou, _, leituras_na_volta = next(
        a for a in fora.avisos if not a[1] and a[0] >= fora.marcos["esconde"])
    depois = [x for x in fora.ticks if x.t >= voltou and not x.escondida]
    primeiro = next((i for i, x in enumerate(depois) if x.pintou), None)
    assert primeiro is not None and primeiro < 3, (
        f"a primeira pintura da volta saiu no tique {primeiro} — o teto é 3")
    pintura = next(p for p in fora.pinturas if p[0] >= voltou)
    assert _inteira(pintura[1]), (
        f"a primeira pintura da volta não é a carga inteira: {sorted(pintura[1])}")
    assert depois[primeiro].leituras > leituras_na_volta, (
        "a volta pintou antes de o leitor trazer um estado novo")


def _trocar_de_aba_nao_e_esconder(fora: Any) -> None:
    antes = [a for a in fora.avisos if a[0] < fora.marcos["esconde"]]
    assert not antes, (
        f"{len(antes)} troca(s) de visibilidade antes de a janela se esconder, "
        f"indo para {fora.pagina}: {[(round(t - antes[0][0], 3), e) for t, e, _ in antes]}")
    trocas = [e for _, e, _ in fora.avisos]
    assert trocas == [True, False], f"as trocas da janela foram {trocas}"


def _parada_pinta_so_as_cargas_inteiras(fora: Any) -> None:
    _sem_fome(fora, "à vista")
    antes = [x for x in fora.ticks if fora.comeco <= x.t < fora.marcos["esconde"]]
    janela = antes[-TIQUES_POR_FASE:]
    assert len(janela) == TIQUES_POR_FASE, (
        f"{len(janela)} tiques à vista antes de esconder, e a fase junta "
        f"{TIQUES_POR_FASE}")
    pintaram = sum(1 for x in janela if x.pintou)
    assert pintaram <= 5, (
        f"{pintaram} pinturas em {len(janela)} tiques com o estado imóvel em "
        f"{fora.pagina} ({fora.n} controle(s)) — o tique voltou a mandar a carga "
        "inteira")


def _a_aba_quieta_nao_e_muda(fora: Any) -> None:
    _sem_fome(fora, "à vista", "de volta")
    assert not fora.mudas, f"o relato acusou {fora.pagina} de aba muda"
    assert fora.piloto.tiques.get(fora.pagina, 0) >= 60, fora.piloto.tiques
