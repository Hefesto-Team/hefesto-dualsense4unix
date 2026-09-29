"""A JANELA ABERTA NÃO GASTA O PROCESSADOR — A-JANELA-ABERTA-NAO-GASTA-O-PROCESSADOR-01.

O NÚMERO É DELA, do diário do usuário: a janela ficou aberta 10 h em 25/09/2026
e gastou 3h29min de CPU, 35% de um núcleo, com ela só olhando ou nem isso. Na
banca (o piloto oculto, o daemon de mentira, o `/proc` a cada segundo), a 02 à
vista gastava 61% e escondida 47%. As causas, medidas:

* a folha `posicao-css`, trocada INTEIRA a cada tique, refazia o estilo da
  página e repintava a janela toda, dez vezes por segundo;
* o tique mandava a carga inteira (15 KB na 02) a cada 100 ms, parada ou não;
* o funil passava a carga inteira em 26 buscas de palavra banida por tique;
* a renovação da camada 1 rodava 21 `pactl` a cada 2 s, e 29 com fonte nativa;
* com a janela escondida, tudo isso seguia igual.

AS RÉGUAS CONTAM, E NÃO MEDEM CPU: CPU na suíte seria vermelho de carga. O que
elas contam é o que gera o CPU — pinturas, leituras, `pactl`, mutações de folha.
A banca no tempo, com os números de processador, é de quem coordena
(`docs/process/estudos/2026-09-25-a-janela-aberta-nao-gasta-o-processador/`).

    R1  janela escondida não trabalha, no tempo (01, 02 e 08; 1, 2 e 4 controles)
    R2  só vai o que mudou; e a forma (fita, bloco, molde) leva a carga inteira
    R3  a verdade volta: a carga inteira de 1 em 1 s repõe o `<select>` recusado
    R4  o funil lê cada texto uma vez, e o valor que é só a palavra é denunciado
    R5  nenhuma folha endereçada muda no tique, e o pontinho anda pelo alvo
    R6  a renovação da camada 1 roda cada `pactl` uma vez por dono
    R7  a janela de 10 h não acumula custos

A MORDIDA de cada uma está no docstring dela. A janela é OCULTA e nasce no Xvfb
da suíte: ela tem UMA tela. Nenhuma régua daqui fala com o daemon, com o
servidor de som ou com o broker: a ponte, o estado e os `pactl` são dublês.
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

#: A mesa de quatro da casa, com endereços da faixa sintética (`aa:bb:cc`).
FIXTURE = RAIZ / "tests/fixtures/state_full_quatro_controles.json"

#: Quais controles da fixture entram: 1 é o P1 no USB; 2 são o P1 no USB e o P3
#: no BT; 4 são dois no USB e dois no BT — os mesmos da banca.
MESAS = {1: (0,), 2: (0, 2), 4: (0, 1, 2, 3)}

#: CADA FASE ACABA POR CONTAGEM, e o relógio só serve de teto
#: (A-JANELA-ESCONDIDA-MEDE-SOB-CARGA-01, 28/09/2026). As réguas cobram tiques;
#: um roteiro que avançasse pelo relógio juntaria menos tiques na mesma janela
#: com a máquina ocupada, e a pré-condição cairia sem o produto mudar — foi a
#: reprovação da suíte de 28/09 («poucos tiques escondidos para medir: 21»).
TIQUES_POR_FASE = 40

#: O TETO de uma fase é este tanto de vezes o tempo nominal dela, que sai do
#: `TIQUE_MS` do produto (ver `_teto_da_fase_s`). Bater o teto não é pulo: a
#: fase anota a fome em `fora.famintas`, e a régua que a lê reprova dizendo que
#: foi a máquina.
VEZES_O_NOMINAL = 5

#: A folga para a janela assentar numa troca (a mensagem da página chega pelo
#: laço do GTK, e uma leitura pode estar no meio quando o fio pausa).
ASSENTAR_S = 0.6

#: NA VOLTA, O DAEMON DEMORA um tique e pouco para responder. Com a leitura
#: instantânea do dublê, o fio que acorda na volta responde antes do primeiro
#: tique, e a régua não veria o tique que pintasse o estado de antes de
#: esconder (a mordida do `_esperando_o_estado_novo` passava verde).
ATRASO_NA_VOLTA_S = 0.12


# ===========================================================================
# A bancada: o piloto de verdade, oculto, com dublês nas quatro bordas
# ===========================================================================
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
        #: Quanto cada leitura DEMORA, como o daemon de verdade. A leitura só
        #: conta quando volta: é a resposta que o tique pode pintar.
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


@pytest.fixture(scope="module")
def publicado_de_hoje(tmp_path_factory: pytest.TempPathFactory) -> pathlib.Path:
    """As páginas publicadas, com a 02 da BANCADA — a que o gerador faz hoje.

    A 02 publicada só recebe o alvo `posicao` quando quem coordena publica a
    aba. Até lá, medir o produto contra ela seria medir a página velha. As
    outras nove são as publicadas, copiadas como estão.
    """
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
    """O teto de uma fase de `quantos` tiques: `VEZES_O_NOMINAL` o nominal dela.

    O cenário pode pedir um teto próprio (`fora.teto_da_fase_s`): é assim que a
    régua do teto prova que a fome se anota e a mensagem diz que foi a máquina.
    """
    proprio = getattr(fora, "teto_da_fase_s", None)
    return float(proprio) if proprio else VEZES_O_NOMINAL * _nominal_s(quantos)


def _maior_buraco(de: float, tiques: list[float], agora: float) -> float:
    """O maior intervalo sem tique na fase, contando da abertura dela até agora."""
    marcas = [de, *tiques, agora]
    return max((b - a for a, b in itertools.pairwise(marcas)), default=0.0)


def _fase(fora: Any, nome: str, de: float, quantos: int, teto_s: float, *,
          ate: float = float("inf"), agora: float | None = None) -> bool:
    """A fase `nome` acabou? Acaba quando junta `quantos` tiques em `[de, ate]`.

    O relógio só serve de TETO: passados `teto_s` desde `de` sem juntar, a fase
    acaba com fome, e anota `fora.famintas[nome] = (tiques, segundos,
    maior_buraco)`. A régua que lê a fase reprova com a causa escrita
    (`_sem_fome`), e não pula: pulo não é verde nesta casa.

    O LAÇO TAMBÉM SE ANOTA, em `fora.lacos[nome]`: o maior intervalo sem
    `passo` do roteiro na mesma fase. É ele que separa a máquina do produto
    (ver `_sem_fome`); sem `fora.passos`, não se anota nada, e a causa não se
    afirma.
    """
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
    """A fome é do PRODUTO? O tique e o `passo` do roteiro rodam no mesmo laço
    do GTK: com a máquina ocupada, os dois param juntos, e o maior buraco de um
    fica perto do outro. Se o laço seguiu andando e só o tique sumiu (o `_tique`
    que devolve `False` desliga o próprio relógio), o buraco dos tiques passa
    de três vezes o do laço, e de três tiques nominais.
    """
    if laco is None:
        return False
    return buraco > 3 * max(laco, _nominal_s(1))


def _sem_fome(fora: Any, *nomes: str) -> None:
    """Reprova, com a causa escrita, se alguma destas fases bateu o teto.

    A causa é a que a medida sustenta: o laço do GTK devagar (a máquina), ou o
    tique parado com o laço andando (o produto). Chamar de máquina o produto
    que parou mandaria repetir a corrida em vez de olhar o `_tique`.
    """
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
    """Roda o piloto oculto na página pedida, com `n` controles, e segue o `roteiro`.

    O roteiro recebe `(fora, piloto, agora)` a cada 50 ms depois de a página
    estar de pé, e devolve `False` quando acabou. `fora` é o registro: cada
    tique, cada pintura (com a carga), as leituras e os `pactl`; `fora.comeco`
    é o instante em que a página ficou de pé, de onde a primeira fase conta.

    O TETO DO CENÁRIO é maior que a soma dos tetos das fases e das esperas (o
    roteiro de teto maior, o `esconde_e_volta`, soma três fases e duas esperas;
    o dos pontinhos, cinco fases e uma espera): ele só pega o roteiro que nunca
    acaba, e nunca corta uma fase que ainda pode juntar os tiques. Vale também
    com o teto de fase do cenário, porque as esperas guardam o teto delas.
    """
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
        # O MICROFONE DE CADA CONTROLE TEM NÓ, para as ondas terem o que seguir
        # e soltar: sem isto a régua da janela escondida mediria um conjunto
        # que já nasceu vazio.
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
            # O PILOTO DE UM CENÁRIO QUE ACABOU NÃO TIQUETAQUEIA NO SEGUINTE: o
            # relógio dele é do laço do GTK, que é um só para o módulo inteiro.
            # Vivo, ele rodaria o pacote da aba dele (e o `pactl` da 02) no
            # meio da medição do cenário seguinte.
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
            # CADA TROCA, com as leituras no INSTANTE do aviso, e não no
            # primeiro tique depois: o fio pode trazer a resposta nova antes
            # de o tique rodar. O aviso que não muda nada (a página que nasce
            # dizendo `vista`) não é troca.
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
                # O TESTE DE MOTOR EM CURSO — o coração que tem de seguir batendo.
                a05._EM_TESTE[0] = str(estado.base["controllers"][0]["uniq"])
                a05._BATEU_EM[0] = 0.0
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
    """O teto de uma ESPERA pelo produto (o `escondeu`, o `voltou`, uma leitura).

    Espera não junta tiques e não tem fome: se o teto passa, é o produto que não
    respondeu, e a régua dele reprova no que faltou. Sem teto, a mordida do
    `_a_janela_mudou` penduraria o roteiro em vez de reprovar.
    """
    return VEZES_O_NOMINAL * _nominal_s(TIQUES_POR_FASE)


def _roteiro_esconde_e_volta(fora: Any, piloto: Any, _t: float) -> bool:
    """40 tiques à vista, 40 escondida, 40 de volta — contados.

    Cada fase acaba quando junta os tiques, e o relógio só serve de teto
    (`_fase`). Entre as fases, a espera pelo aviso da página (`escondeu`,
    `voltou`) tem o seu teto.
    """
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
                # A PÁGINA NUNCA DISSE QUE SE ESCONDEU: volta sem a fase
                # escondida, e a R1 reprova no marco que faltou.
                return _mostrar(fora, piloto)
        de, ate = _janela_escondida(fora)
        if not _fase(fora, "escondida", de, quantos, teto, ate=ate):
            return True
        return _mostrar(fora, piloto)
    if "voltou" not in marcos:
        if piloto._escondida or "escondeu" not in marcos:
            # A janela nunca se escondeu (a mordida do `_a_janela_mudou`) ou
            # nunca voltou: espera o teto e acaba. A régua reprova no marco.
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


@pytest.fixture(scope="module", params=CENARIOS,
                ids=[f"{p[:2]}-{n}-controles" for p, n in CENARIOS])
def esconde_e_volta(request: pytest.FixtureRequest,
                    publicado_de_hoje: pathlib.Path) -> SimpleNamespace:
    pagina, n = request.param
    fora = _correr(publicado_de_hoje, pagina, n, _roteiro_esconde_e_volta)
    fora.pagina, fora.n = pagina, n
    return fora


def _janela_escondida(fora: Any) -> tuple[float, float]:
    """A fase escondida, com UM dono: `(de, ate)`, para o roteiro contar e as
    réguas medirem a mesma janela.

    Começa no `escondeu` mais o `ASSENTAR_S`. Acaba no INSTANTE em que a página
    disse `vista` de novo, pelo aviso anotado: o roteiro vê a volta até 50 ms
    depois, e o fio lê já na volta, então o tique que pinta o estado novo
    cairia dentro da fase escondida se ela terminasse na marca do roteiro.
    Antes da volta, a fase não tem fim.
    """
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


# ===========================================================================
# R1 — JANELA ESCONDIDA NÃO TRABALHA, NO TEMPO
# ===========================================================================
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
    # ESCONDIDA, O FIO LÊ DE SEGUNDO EM SEGUNDO, e não dez vezes por segundo:
    # é o que mantém o contexto do coração com a mesa de agora (ver
    # `test_r1_o_coracao_nao_bate_por_quem_saiu_escondido`). O teto é de
    # RELÓGIO porque o fio é de relógio: ele lê pelo tempo, não pelo tique.
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


def test_r1_a_janela_escondida_nao_pinta_nem_pergunta(esconde_e_volta: Any) -> None:
    """Escondida, zero pintura, zero `pactl` e uma leitura do estado por segundo.

    A janela minimizada é o caso em que ela joga. O WebKit já parava de
    desenhar, mas o tique seguia montando a carga e mandando-a, dez vezes por
    segundo: 47% de um núcleo na banca, com a tela parada.

    AS TRÊS MORDIDAS, cada uma numa conta diferente:

    * faça `_a_janela_mudou` voltar logo na primeira linha: o `_escondida`
      nunca vira `True`, o roteiro não marca o `escondeu`, e a régua reprova
      na pré-condição (a página nunca disse que estava escondida);
    * tire o `self._escondida or` do `if` do `_tique`: a página volta a pintar
      escondida, e a régua reprova nas pinturas;
    * deixe o `LeitorDoEstado.pausar` sem efeito: a leitura volta a ~10 por
      segundo, e a régua reprova no teto de leituras.
    """
    _a_escondida_nao_trabalha(esconde_e_volta)


def _o_coracao_bate_escondido(fora: Any) -> None:
    _sem_fome(fora, "escondida")
    de, ate = _janela_escondida(fora)
    dentro = _entre(fora, de, ate)
    batidas = dentro[-1].batidas - dentro[0].batidas
    assert batidas >= 2, (
        f"{batidas} batida(s) do coração em {ate - de:.1f} s com a janela "
        "escondida e um teste de motor em curso")


def test_r1_o_coracao_segue_batendo_escondido(esconde_e_volta: Any) -> None:
    """Esconder não é largar: o teste de motor em curso segue batendo.

    O coração é de 1 em 1 s (`a05_vibracao.SEGUNDOS_ENTRE_BATIMENTOS`); em
    40 tiques escondida são três ou quatro batidas. Sem elas o teto do
    daemon soltaria o teste que ela deixou ligado.

    MORDIDA: tire o `bater_os_coracoes` do ramo da janela escondida no
    `_tique` e as batidas param de contar aqui.
    """
    _o_coracao_bate_escondido(esconde_e_volta)


# ===========================================================================
# R1 SOB CARGA — a máquina ocupada não derruba a pré-condição
# ===========================================================================
def _com_carga(roteiro: Any, *, buraco_s: float = 0.0, lento_s: float = 0.0) -> Any:
    """O roteiro com a máquina ocupada, SEM carregar a máquina dela.

    `buraco_s`: o laço do GTK para uma vez, logo depois do `hide()` — é o buraco
    da suíte de 28/09 (uns 1,4 s sem tique e sem passo). `lento_s`: o laço anda
    devagar, um `sleep` a cada passo, só com a janela escondida.
    """
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


@pytest.fixture(scope="module", params=sorted(CARGAS))
def sob_carga(request: pytest.FixtureRequest,
              publicado_de_hoje: pathlib.Path) -> SimpleNamespace:
    """A 08 com um controle — o cenário que reprovou em 28/09 —, com a carga pedida."""
    fora = _correr(publicado_de_hoje, "08-conexoes.html", 1,
                   _com_carga(_roteiro_esconde_e_volta, **CARGAS[request.param]))
    fora.pagina, fora.n, fora.carga = "08-conexoes.html", 1, request.param
    return fora


def test_r1_sob_carga_a_janela_escondida_mede_o_mesmo(sob_carga: Any) -> None:
    """Com o laço do GTK parado ou lento, a R1 e o coração continuam verdes.

    A PROVA DE QUE A CARGA PEGOU vem junto: a janela de relógio do roteiro de
    28/09 (a fase escondida acabava 40 tiques NOMINAIS depois do `hide()`)
    teria juntado menos de 25 tiques neste mesmo cenário. Sem isso, a régua
    ficaria verde sobre uma carga que não atrasou nada.

    MORDIDA: devolva o roteiro de relógio (a fase escondida acabando no
    `hide()` mais `_nominal_s(TIQUES_POR_FASE)`) e esta régua reprova em
    «poucos tiques escondidos para medir», que é a reprovação de 28/09.
    """
    fora = sob_carga
    _a_escondida_nao_trabalha(fora)
    _o_coracao_bate_escondido(fora)
    de, _ate = _janela_escondida(fora)
    relogio = _entre(fora, de, fora.marcos["esconde"] + _nominal_s(TIQUES_POR_FASE))
    assert len(relogio) < 25, (
        f"a carga {fora.carga!r} não atrasou o laço: o relógio de 28/09 teria "
        f"juntado {len(relogio)} tiques, e esta régua não provaria nada")


@pytest.fixture(scope="module")
def sob_carga_com_teto_curto(publicado_de_hoje: pathlib.Path) -> SimpleNamespace:
    """O buraco de 28/09 com um teto de fase de 1 s: a fase escondida passa fome."""
    fora = _correr(publicado_de_hoje, "08-conexoes.html", 1,
                   _com_carga(_roteiro_esconde_e_volta, **CARGAS["buraco"]),
                   teto_da_fase_s=1.0)
    fora.pagina, fora.n = "08-conexoes.html", 1
    return fora


def test_r1_o_teto_batido_diz_que_foi_a_maquina(sob_carga_com_teto_curto: Any) -> None:
    """A fase que bate o teto anota a fome, e a R1 reprova dizendo a causa.

    Vermelho, e não pulo: pulo não é verde nesta casa. E vermelho com a causa
    escrita, para ninguém ler a máquina lenta como produto quebrado.

    MORDIDA: faça o `_fase` acabar no teto sem anotar em `fora.famintas` e
    esta régua reprova: a fome some, e a R1 cairia no piso de 25 sem dizer que
    foi a máquina.
    """
    fora = sob_carga_com_teto_curto
    tiques, segundos, _buraco = fora.famintas["escondida"]
    assert tiques < TIQUES_POR_FASE and segundos >= 1.0, fora.famintas
    with pytest.raises(AssertionError, match=(
            r"a fase escondida juntou \d+ de 40 tiques em \d+,\d s \(maior buraco: "
            r"\d+,\d s\): o laço do GTK andou devagar demais para medir")):
        _a_escondida_nao_trabalha(fora)


def test_a_fase_junta_os_tiques_e_anota_a_fome() -> None:
    """O `_fase` sem GTK, com tiques sintéticos: junta, espera, e passa fome.

    MORDIDA: faça o `_fase` contar pelo relógio (`agora - de >= teto_s` antes
    de contar os tiques) e a fase cheia deixa de acabar ao juntar.
    """
    fora = SimpleNamespace(ticks=[SimpleNamespace(t=10.0 + 0.1 * i) for i in range(30)],
                           fases={}, famintas={})
    assert _fase(fora, "cheia", 10.0, 20, 5.0, agora=11.0), "juntou 20 e não acabou"
    assert not _fase(fora, "juntando", 10.0, 40, 5.0, agora=13.0), (
        "acabou antes de juntar e antes do teto")
    assert not _fase(fora, "fechada", 10.0, 20, 5.0, ate=11.0, agora=11.5), (
        "contou tique fora da janela da fase")
    fora.ticks.append(SimpleNamespace(t=15.0))
    assert _fase(fora, "faminta", 10.0, 40, 5.0, agora=15.5), "o teto não acabou a fase"
    assert not {"cheia", "juntando", "fechada"} & set(fora.famintas), fora.famintas
    tiques, segundos, buraco = fora.famintas["faminta"]
    assert (tiques, segundos) == (31, 5.5) and buraco == pytest.approx(2.1), fora.famintas
    _sem_fome(fora, "cheia", "juntando")
    with pytest.raises(AssertionError, match=(
            r"a fase faminta juntou 31 de 40 tiques em 5,5 s \(maior buraco: 2,1 s\): "
            r"o laço do GTK andou devagar demais para medir")):
        _sem_fome(fora, "cheia", "faminta")


def test_a_fome_do_produto_nao_se_le_como_maquina() -> None:
    """O tique que PARA com o laço andando é o produto, e a régua diz isso.

    O `_tique` que devolve `False` desliga o próprio relógio: a fase passa
    fome com o laço do GTK folgado. Chamar isso de máquina lenta mandaria
    repetir a corrida, que é o contrário da cura desta régua. E a máquina lenta
    de verdade (o laço parado junto com o tique) continua dita como máquina.

    MORDIDA: faça o `_o_tique_parou_com_o_laco_andando` devolver sempre `False`
    e a fome do produto volta a se ler como máquina.
    """
    passos = [10.0 + 0.2 * i for i in range(51)]
    parou = SimpleNamespace(ticks=[SimpleNamespace(t=10.0 + 0.1 * i) for i in range(3)],
                            fases={}, famintas={}, passos=passos, lacos={})
    assert _fase(parou, "escondida", 10.0, 40, 10.0, agora=20.0)
    with pytest.raises(AssertionError, match=(
            r"a fase escondida juntou 3 de 40 tiques em 10,0 s \(maior buraco: 9,8 s\): "
            r"o laço do GTK andou \(maior buraco dele: 0,2 s\) e o tique parou: é o "
            r"produto, e não a máquina")):
        _sem_fome(parou, "escondida")
    # A MÁQUINA LENTA: o laço para junto com o tique, de 1,4 s em 1,4 s.
    marcas = [10.0 + 1.4 * i for i in range(8)]
    lenta = SimpleNamespace(ticks=[SimpleNamespace(t=t) for t in marcas],
                            fases={}, famintas={}, passos=list(marcas), lacos={})
    assert _fase(lenta, "escondida", 10.0, 40, 10.0, agora=20.0)
    with pytest.raises(AssertionError, match="o laço do GTK andou devagar demais"):
        _sem_fome(lenta, "escondida")


#: Quantos tiques a régua de quem saiu conta depois do `de` dela.
TIQUES_DEPOIS_DE_SAIR = 20


def _depois_de_sair(fora: Any) -> float:
    """De onde a régua de quem saiu conta: uma leitura escondida e um batimento
    de folga depois da saída. É de RELÓGIO porque o fio escondido é de relógio
    (lê de `SEGUNDOS_ENTRE_LEITURAS_ESCONDIDA` em
    `SEGUNDOS_ENTRE_LEITURAS_ESCONDIDA`)."""
    import hefesto_vivo as hv

    return float(fora.marcos["saiu"] + 2 * hv.LeitorDoEstado.SEGUNDOS_ENTRE_LEITURAS_ESCONDIDA)


def _roteiro_o_controle_sai_escondido(fora: Any, piloto: Any, _t: float) -> bool:
    """10 tiques à vista; a janela se esconde; escondida, o controle do teste
    sai, e a fase junta 20 tiques depois do `_depois_de_sair`."""
    marcos = fora.marcos
    if "esconde" not in marcos:
        if not _fase(fora, "antes de esconder", fora.comeco, 10, _teto_da_fase_s(fora, 10)):
            return True
        marcos["esconde"] = time.monotonic()
        piloto.tela.janela.hide()
        return True
    if "saiu" not in marcos:
        if not piloto._escondida:
            return bool(time.monotonic() - marcos["esconde"] < _teto_da_espera_s())
        # O CONTROLE EM TESTE É O PRIMEIRO DA MESA (ver `_correr`), e o outro
        # fica: é nele que o par sem endereço cairia.
        st = copy.deepcopy(fora.estado.base)
        st["controllers"] = st["controllers"][1:]
        fora.estado.fixo = st
        marcos["saiu"] = time.monotonic()
        return True
    quantos = TIQUES_DEPOIS_DE_SAIR
    return not _fase(fora, "depois de sair", _depois_de_sair(fora), quantos,
                     _teto_da_fase_s(fora, quantos))


@pytest.fixture(scope="module")
def o_controle_sai_escondido(publicado_de_hoje: pathlib.Path) -> SimpleNamespace:
    return _correr(publicado_de_hoje, "02-controles.html", 2,
                   _roteiro_o_controle_sai_escondido)


def test_r1_o_coracao_nao_bate_por_quem_saiu_escondido(
        o_controle_sai_escondido: Any) -> None:
    """Escondida, o controle do teste de motor sai da mesa: o coração para.

    O coração bate com o CONTEXTO do tique, e a guarda dele é o controle estar
    na mesa (`a05_vibracao._bater_o_coracao_do_teste`): quem saiu tem o teste
    parado. Com o fio do estado parado e o contexto de antes de esconder, o
    teste de quem saiu seguia batendo — e o `rumble.set` não leva endereço: o
    par cai no controle que ficou, que vibra até a janela voltar à vista.
    Escondida, o fio lê de segundo em segundo, e o contexto anda com ele.

    MORDIDA: faça o fio parar de ler com a janela escondida (o `_laco` esperar
    o `retomar()` sem ler), ou tire `_o_contexto_anda_escondido` do ramo da
    janela escondida no `_tique`, e as batidas seguem depois da saída.
    """
    fora = o_controle_sai_escondido
    assert "saiu" in fora.marcos, "a janela nunca se escondeu para o controle sair"
    _sem_fome(fora, "antes de esconder", "depois de sair")
    depois = [x for x in fora.ticks if x.t >= _depois_de_sair(fora)]
    assert len(depois) >= TIQUES_DEPOIS_DE_SAIR, (
        f"poucos tiques depois da saída: {len(depois)}")
    assert all(x.escondida for x in depois), "a janela voltou à vista no meio"
    batidas = depois[-1].batidas - depois[0].batidas
    assert batidas == 0, (
        f"{batidas} batida(s) do coração por um controle que saiu da mesa com a "
        "janela escondida — o par cairia no controle que ficou")
    # O CONTEXTO ANDA SEM AS PERGUNTAS DO TIQUE: com a janela escondida não se
    # pede o inventário dos externos (`controller.list`, 10-40 ms e um
    # subprocess no daemon). MORDIDA: `perguntar=True` no contexto escondido.
    escondida = [x for x in fora.ticks if x.t >= fora.marcos["saiu"]]
    externos = escondida[-1].externos - escondida[0].externos
    assert externos == 0, (
        f"{externos} pergunta(s) do inventário dos externos com a janela escondida")


def test_r1_na_volta_a_carga_vai_inteira_e_com_estado_novo(esconde_e_volta: Any) -> None:
    """Na volta, a primeira pintura é inteira, e sai em até 3 tiques, depois
    de o leitor trazer uma resposta NOVA.

    A conta das leituras é a do INSTANTE do aviso (o dublê do `_a_janela_mudou`
    a anota), porque o fio pode trazer a resposta antes do primeiro tique.

    MORDIDA: tire o `_esquecer_a_pintura(self)` de `_a_janela_mudou` e a primeira
    pintura da volta passa a ser uma diferença (ou nenhuma, com a mesa parada).
    Tire o `_esperando_o_estado_novo()` do `_tique` e ela sai com o estado de
    antes de esconder.
    """
    fora = esconde_e_volta
    assert "voltou" in fora.marcos, "a página nunca disse que voltou à vista"
    _sem_fome(fora, "de volta")
    # O INSTANTE DO AVISO, e não o do roteiro, que o vê até 50 ms depois: o
    # tique que pintasse o estado velho cairia antes da marca e sairia da conta.
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


def test_r1_trocar_de_aba_nao_e_esconder(esconde_e_volta: Any) -> None:
    """A janela só se esconde quando a janela se esconde: a troca de aba não conta.

    O documento que sai passa a `hidden` antes de morrer. Sem a marca do
    `pagehide`, a ida da 01 para a 02 e para a 08 (o piloto abre na 01)
    pausava o fio e escrevia no diário `[janela] escondida` — e a linha que
    ela vai ler depois de minimizar, na máquina dela, não provaria nada.

    MORDIDA: tire o `if(!window.__hefSaindo)` do ouvinte do BOOTSTRAP e a
    troca de aba vira um par escondida/vista antes do `hide()`.
    """
    fora = esconde_e_volta
    antes = [a for a in fora.avisos if a[0] < fora.marcos["esconde"]]
    assert not antes, (
        f"{len(antes)} troca(s) de visibilidade antes de a janela se esconder, "
        f"indo para {fora.pagina}: {[(round(t - antes[0][0], 3), e) for t, e, _ in antes]}")
    trocas = [e for _, e, _ in fora.avisos]
    assert trocas == [True, False], f"as trocas da janela foram {trocas}"


# ===========================================================================
# R2 — SÓ VAI O QUE MUDOU
# ===========================================================================
def test_r2_parada_a_aba_pinta_so_as_cargas_inteiras(esconde_e_volta: Any) -> None:
    """Com o estado imóvel, os 40 tiques à vista dão no máximo 5 pinturas.

    São as cargas inteiras de 1 em 1 s. Antes desta cura eram 40, de 15 KB
    cada na 02. A janela são os ÚLTIMOS 40 tiques da página antes do
    `esconde`, contados: exatamente 40, e não os que couberam em 4 s.

    MORDIDA: faça `_o_que_mandar` devolver sempre `carga` e são 40.
    """
    fora = esconde_e_volta
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


def test_r2_a_aba_quieta_nao_e_aba_muda(esconde_e_volta: Any) -> None:
    """O detector de aba muda do `_relatar` não acusa a aba parada.

    O tique sem nada a mandar CONTA em `tiques`; a aba pintou na chegada.

    MORDIDA: tire o `self.tiques[...] += 1` do ramo sem diferença e a aba
    parada fica com poucos tiques; tire a pintura inteira da chegada e ela
    vira muda.
    """
    fora = esconde_e_volta
    _sem_fome(fora, "à vista", "de volta")
    assert not fora.mudas, f"o relato acusou {fora.pagina} de aba muda"
    assert fora.piloto.tiques.get(fora.pagina, 0) >= 60, fora.piloto.tiques


@pytest.fixture(scope="module")
def so_o_giro(publicado_de_hoje: pathlib.Path) -> SimpleNamespace:
    """A 02 com dois controles e só o giroscópio mexendo: 15 tiques para a
    página assentar, e 40 medindo."""
    def roteiro(fora: Any, _piloto: Any, _t: float) -> bool:
        if "medindo" not in fora.marcos:
            if _fase(fora, "aquecendo", fora.comeco, 15, _teto_da_fase_s(fora, 15)):
                fora.marcos["medindo"] = time.monotonic()
            return True
        return not _fase(fora, "giro", fora.marcos["medindo"], TIQUES_POR_FASE,
                         _teto_da_fase_s(fora, TIQUES_POR_FASE))

    return _correr(publicado_de_hoje, "02-controles.html", 2, roteiro, anda="giro")


def test_r2_so_o_giro_mexe_e_so_o_giro_vai(so_o_giro: Any) -> None:
    """Toda pintura que não é inteira leva só as chaves do giroscópio.

    MORDIDA: faça `_o_que_mudou` devolver a carga inteira e as ~40 pinturas
    passam a levar tudo.
    """
    _sem_fome(so_o_giro, "aquecendo", "giro")
    de = so_o_giro.marcos["medindo"]
    ate = _os_primeiros(so_o_giro, de, TIQUES_POR_FASE)[-1].t
    pinturas = [c for t, c, _ in so_o_giro.pinturas if de <= t <= ate]
    assert len(pinturas) >= 25, f"o giro mexeu e só {len(pinturas)} pinturas saíram"
    inteiras = [c for c in pinturas if _inteira(c)]
    assert len(inteiras) <= 5, f"{len(inteiras)} cargas inteiras em 40 tiques"
    outras: set[str] = set()
    for c in pinturas:
        if _inteira(c):
            continue
        assert set(c) <= {"colunas"}, f"a diferença levou {sorted(c)}"
        for campos in c["colunas"].values():
            outras |= {k for k in campos if not k.startswith("giro")}
    assert not outras, f"só o giro mexeu e a diferença levou {sorted(outras)}"


@pytest.fixture(scope="module")
def um_controle_chega(publicado_de_hoje: pathlib.Path) -> SimpleNamespace:
    """A 01 com um controle; depois de 20 tiques chega o segundo, e a fase
    conta mais 20.

    SEM A CARGA INTEIRA DE 1 s: ela cairia na mesma fase da chegada (a página
    abre, e a cada 10 tiques vem uma) e a régua ficaria verde sem a cura da
    forma. Aqui a única inteira depois da primeira é a que a forma pede.
    """
    def roteiro(fora: Any, _piloto: Any, _t: float) -> bool:
        if "chegou" not in fora.marcos:
            if _fase(fora, "antes de chegar", fora.comeco, 20, _teto_da_fase_s(fora, 20)):
                fora.marcos["chegou"] = time.monotonic()
                fora.estado.fixo = _estado_da_fixture(2)
            return True
        return not _fase(fora, "chegada", fora.marcos["chegou"], 20,
                         _teto_da_fase_s(fora, 20))

    def sem_a_inteira_de_1_s(mp: pytest.MonkeyPatch, hv: Any) -> None:
        mp.setattr(hv.Piloto, "TIQUES_ENTRE_CARGAS_INTEIRAS", 10**6)

    return _correr(publicado_de_hoje, "01-jogar.html", 1, roteiro,
                   ajuste=sem_a_inteira_de_1_s)


def test_r2_o_controle_que_chega_leva_a_carga_inteira(um_controle_chega: Any) -> None:
    """A forma mudou (a fita, os lugares): o tique que a vê manda tudo.

    A fita troca o nó inteiro e o `pintar` escreve os campos, os lugares e as
    marcas DEPOIS, no mesmo passe. Por diferença, o nó novo ficaria até 1 s
    com o valor do desenho, e o lugar novo marcado como vazio.

    MORDIDA: faça `_a_diferenca_muda_a_forma` devolver `False` e esta pintura
    vira uma diferença (a fita e os lugares, sem os campos).
    """
    fora = um_controle_chega
    _sem_fome(fora, "antes de chegar", "chegada")
    chegou = fora.marcos["chegou"]
    inteira_antes = next(c for t, c, _ in fora.pinturas if _inteira(c))
    depois = [c for t, c, _ in fora.pinturas
              if t >= chegou and len(c.get("ocupados") or []) == 2]
    assert depois, "o segundo controle nunca chegou à tela"
    primeira = depois[0]
    assert _inteira(primeira), (
        f"o controle chegou numa diferença: {sorted(primeira)}")
    assert set(primeira["mesa"]) >= set(inteira_antes["mesa"]), (
        "a carga do controle que chega não levou os campos da mesa")


# ===========================================================================
# As réguas de uma peça só: o `_o_que_mandar` do produto, o BOOTSTRAP no WebKit
# ===========================================================================
def _mandador(moldes: frozenset[str] = frozenset()) -> Any:
    """O `Piloto._o_que_mandar` DO PRODUTO, num objeto com só o que ele lê."""
    import hefesto_vivo as hv

    eu = SimpleNamespace(_pintada=None, _ate_a_inteira=0,
                         TIQUES_ENTRE_CARGAS_INTEIRAS=hv.Piloto.TIQUES_ENTRE_CARGAS_INTEIRAS,
                         _moldes_da_pagina=lambda: moldes)
    return eu, hv.Piloto._o_que_mandar.__get__(eu)


def test_r2_a_diferenca_desce_chave_a_chave() -> None:
    """A diferença desce `mesa`, `colunas` por controle, `blocos` e `marcas`."""
    _eu, mandar = _mandador()
    um = {"mesa": {"a": "1", "b": "2"}, "colunas": {"p1": {"x": "1", "y": "2"}},
          "vazios": ["p2"], "fita": "<f>", "alvo": "", "marcas": {"navega": ["p1"]}}
    assert mandar(um) == um
    dois = copy.deepcopy(um)
    dois["mesa"]["b"] = "3"
    dois["colunas"]["p1"]["y"] = 3
    assert mandar(dois) == {"mesa": {"b": "3"}, "colunas": {"p1": {"y": 3}}}
    assert mandar(copy.deepcopy(dois)) == {}
    tres = copy.deepcopy(dois)
    tres["colunas"]["p1"]["y"] = "3"
    assert mandar(tres) == {"colunas": {"p1": {"y": "3"}}}, (
        "o número 3 e o texto '3' foram lidos como o mesmo valor")


def test_r2_a_carga_inteira_sai_a_cada_dez_tiques() -> None:
    """Parada, a aba recebe a carga inteira de 10 em 10 tiques, e nada entre elas."""
    _eu, mandar = _mandador()
    carga = {"mesa": {"a": "1"}, "fita": "", "alvo": ""}
    saidas = [mandar(copy.deepcopy(carga)) for _ in range(40)]
    assert [i for i, s in enumerate(saidas) if s] == [0, 10, 20, 30]


def test_r2_a_lista_do_molde_leva_a_carga_inteira() -> None:
    """A lista que um molde conta mudou: carga inteira, no mesmo tique.

    MORDIDA: tire o ramo dos moldes de `_a_diferenca_muda_a_forma`.
    """
    _eu, mandar = _mandador(frozenset({"achado"}))
    um = {"mesa": {"achado": ["a"], "nome": "x"}, "fita": "", "alvo": ""}
    mandar(um)
    dois = {"mesa": {"achado": ["a", "b"], "nome": "x"}, "fita": "", "alvo": ""}
    assert mandar(dois) == dois
    tres = {"mesa": {"achado": ["a", "b"], "nome": "y"}, "fita": "", "alvo": ""}
    assert mandar(tres) == {"mesa": {"nome": "y"}}


ROTEIRO_DE_PASSOS = r"""
(function(){
  const fora = [];
  const alvo = document.createElement('div');
  alvo.id = 'regua-janela';
  document.body.appendChild(alvo);
  alvo.innerHTML = MONTAGEM;
  for(const passo of PASSOS){
    const el = document.querySelector(passo.onde || 'body');
    if(passo.faz === 'foco'){ el.focus(); el.value = passo.valor; }
    if(passo.faz === 'solta'){ el.blur(); }
    if(passo.carga && Object.keys(passo.carga).length){ window.__hef.pintar(passo.carga); }
    const lido = document.querySelector(passo.ler);
    fora.push(lido ? (('value' in lido && lido.tagName !== 'DIV' && lido.tagName !== 'B')
                      ? lido.value : lido.textContent) : null);
  }
  return JSON.stringify(fora);
})()
"""


def _passos_no_webkit(montagem: str, passos: list[dict[str, Any]]) -> list[Any]:
    """Roda o BOOTSTRAP de verdade numa página publicada e aplica os passos."""
    gtk = _gtk()
    from gi.repository import GLib, WebKit2

    import hefesto_vivo as hv
    from hefesto_dualsense4unix.interface import onde

    roteiro = (ROTEIRO_DE_PASSOS.replace("MONTAGEM", json.dumps(montagem))
               .replace("PASSOS", json.dumps(passos, ensure_ascii=False)))
    saiu: list[str] = []
    janela = gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover — só quando o roteiro quebra
            saiu.append(f"ERRO {e}")
        gtk.main_quit()

    def bootou(v: Any, res: Any) -> None:
        try:
            v.evaluate_javascript_finish(res)
        except Exception as e:  # pragma: no cover
            saiu.append(f"ERRO no BOOTSTRAP: {e}")
            gtk.main_quit()
            return
        v.evaluate_javascript(roteiro, -1, None, None, None, guardou)

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hv.BOOTSTRAP, -1, None, None, None, bootou)

    view.connect("load-changed", carregou)
    view.load_uri(onde.pagina("01-jogar.html", publicado=True).as_uri())
    guarda = GLib.timeout_add(30000, gtk.main_quit)
    try:
        gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu and not saiu[0].startswith("ERRO"), saiu
    return list(json.loads(saiu[0]))


def test_r2_o_no_novo_do_bloco_sai_com_os_campos_no_mesmo_tique() -> None:
    """O bloco troca o nó, e o campo de dentro dele sai com o valor vivo.

    O campo não mudou de valor — quem mudou foi o bloco em volta. Por
    diferença, ele não iria, e o nó novo mostraria o valor que o bloco trouxe
    até a próxima carga inteira.

    MORDIDA: tire o `"blocos" in dif` de `_a_diferenca_muda_a_forma` e o nó
    novo termina o tique com `do desenho`.
    """
    _eu, mandar = _mandador()
    bloco1 = '<b data-campo="regua-vivo">do desenho</b>'
    bloco2 = '<b data-campo="regua-vivo">do desenho</b><i>mais um</i>'
    c1 = {"blocos": {"#regua-bloco": bloco1}, "mesa": {"regua-vivo": "vivo"},
          "fita": "", "alvo": ""}
    c2 = {"blocos": {"#regua-bloco": bloco2}, "mesa": {"regua-vivo": "vivo"},
          "fita": "", "alvo": ""}
    passos = [{"carga": mandar(c1), "ler": '#regua-bloco [data-campo="regua-vivo"]'},
              {"carga": mandar(c2), "ler": '#regua-bloco [data-campo="regua-vivo"]'}]
    lidos = _passos_no_webkit('<div id="regua-bloco"></div>', passos)
    assert lidos == ["vivo", "vivo"], (
        f"o nó que o bloco trouxe terminou o tique com {lidos[-1]!r}")


# ===========================================================================
# R3 — A VERDADE VOLTA
# ===========================================================================
def test_r3_o_select_recusado_volta_ao_valor_do_daemon() -> None:
    """Com o foco nele, o `<select>` não é pintado; quando o foco sai, a carga
    inteira de 1 s devolve o valor do daemon em até 10 tiques.

    APAGAR A MEMÓRIA NA MENSAGEM NÃO BASTA: quando a mensagem do clique chega,
    o campo ainda está com o foco e o `pintar` o pula (`sob_o_dedo`). Depois
    que o foco sai, nada mais muda — e só a carga inteira repõe a verdade.

    MORDIDA: ponha `TIQUES_ENTRE_CARGAS_INTEIRAS` num número enorme e o valor
    recusado fica na tela para sempre.
    """
    _eu, mandar = _mandador()
    carga = {"mesa": {"regua-escolha": "a"}, "fita": "", "alvo": ""}
    sel = '#regua-janela select'
    passos: list[dict[str, Any]] = [{"carga": mandar(copy.deepcopy(carga)), "ler": sel}]
    passos.append({"faz": "foco", "onde": sel, "valor": "b",
                   "carga": mandar(copy.deepcopy(carga)), "ler": sel})
    passos.append({"faz": "solta", "onde": sel,
                   "carga": mandar(copy.deepcopy(carga)), "ler": sel})
    for _ in range(10):
        passos.append({"carga": mandar(copy.deepcopy(carga)), "ler": sel})
    montagem = ('<select data-campo="regua-escolha" data-hef-alvo="valor">'
                '<option>a</option><option>b</option></select>')
    lidos = _passos_no_webkit(montagem, passos)
    assert lidos[0] == "a" and lidos[1] == "b", lidos
    assert lidos[-1] == "a", (
        f"o valor que o daemon recusou ficou na tela: {lidos}")


# ===========================================================================
# R4 — O FUNIL LÊ CADA TEXTO UMA VEZ
# ===========================================================================
@pytest.fixture
def funil(monkeypatch: pytest.MonkeyPatch) -> Any:
    import hefesto_vivo as hv
    from hefesto_dualsense4unix.interface import frases_que_ela_baniu as fb

    chamadas: list[str] = []
    real = fb.primeiro_trecho_banido

    def contar(texto: str) -> str | None:
        chamadas.append(texto)
        return real(texto)

    monkeypatch.setattr(fb, "primeiro_trecho_banido", contar)
    monkeypatch.setattr(hv, "_TEXTOS_LIDOS_PELO_FUNIL", {})
    monkeypatch.setattr(hv, "_BANIDAS_JA_DENUNCIADAS", set())
    return SimpleNamespace(hv=hv, chamadas=chamadas)


def test_r4_a_mesma_carga_cem_vezes_le_cada_texto_uma_vez(funil: Any) -> None:
    """Cem tiques com a mesma carga: uma leitura por texto distinto.

    MORDIDA: tire a memória (`_TEXTOS_LIDOS_PELO_FUNIL`) e são 100 vezes os textos.
    """
    carga = {"mesa": {f"c{i}": f"valor {i % 30}" for i in range(120)},
             "colunas": {"p1": {"x": "valor 1", "n": 3, "b": True, "z": None}},
             "fita": "<div>fita</div>", "vazios": ["p2", "p3"]}
    for _ in range(100):
        funil.hv._json(carga)
    distintos = {json.dumps(v, ensure_ascii=False)
                 for v in [*carga["mesa"].values(), "valor 1", "<div>fita</div>", "p2", "p3"]}
    assert len(funil.chamadas) == len(distintos), (
        f"{len(funil.chamadas)} leituras para {len(distintos)} textos distintos")


def test_r4_a_palavra_num_campo_que_mudou_e_denunciada_uma_vez(
        funil: Any, capsys: pytest.CaptureFixture[str]) -> None:
    """A frase com a palavra banida sai no diário UMA vez, e não por tique.

    MORDIDA: tire o funil do `_json` e a palavra passa calada.
    """
    for i in range(50):
        funil.hv._json({"mesa": {"a": f"tique {i}", "b": "a mesa do jogo"}})
    erro = capsys.readouterr().err
    assert erro.count("[texto banido]") == 1, erro


def test_r4_o_valor_que_e_so_a_palavra_e_denunciado(
        funil: Any, capsys: pytest.CaptureFixture[str]) -> None:
    """`"Mesa"` sozinho num campo: lido serializado, com as aspas, não passa.

    Cru, ele cairia na exceção `texto.strip() == palavra` de
    `palavra_banida_em` — que existe para a CHAVE do pacote.

    MORDIDA: passe o valor cru (sem o `json.dumps`) ao funil e esta passa
    calada.
    """
    funil.hv._json({"mesa": {"x": "Mesa"}})
    assert "[texto banido] 'mesa'" in capsys.readouterr().err


def test_r4_o_funil_devolve_o_mesmo_json(funil: Any) -> None:
    """O que vai ao WebView é o mesmo `json.dumps` de sempre."""
    carga = {"mesa": {"a": "é", "b": [1, None, "x"]}, "fita": ""}
    assert funil.hv._json(carga) == json.dumps(carga, ensure_ascii=False, default=str)


# ===========================================================================
# R5 — NENHUMA FOLHA ENDEREÇADA MUDA NO TIQUE, E O PONTINHO ANDA PELO ALVO
# ===========================================================================
OBSERVAR_AS_FOLHAS = r"""
(function(){
  window.__reguaFolhas = {folhas: 0, pontinhos: 0};
  const obs = new MutationObserver(function(regs){
    for(const r of regs){
      const el = r.target.nodeType === 1 ? r.target : r.target.parentElement;
      if(el && el.closest && el.closest('style[data-campo]')) window.__reguaFolhas.folhas++;
      else if(el && el.dataset && el.dataset.hefAlvo === 'posicao')
        window.__reguaFolhas.pontinhos++;
    }
  });
  obs.observe(document.documentElement, {attributes: true, childList: true,
    characterData: true, subtree: true});
  return 'ok';
})()
"""

LER_AS_FOLHAS = "JSON.stringify(window.__reguaFolhas || {})"

#: ONDE CADA PONTINHO ESTÁ, em por cento do quadro dele: o `left` e o `top`
#: CALCULADOS pela folha, que é a regra `left:var(--hef-x,50.2%)`. Cada cartão
#: sai do desenho por um instante (`display:none`) para a leitura: fora da
#: tela o valor calculado volta em por cento, exato, e não em pixels
#: arredondados pelo layout. A variável inválida (o `—` escrito cru) volta
#: `auto`, e a régua a lê como `null`.
ONDE_ESTAO = r"""
(function(){
  function pct(el, eixo){
    const v = getComputedStyle(el)[eixo === 'x' ? 'left' : 'top'];
    return v.endsWith('%') ? parseFloat(v) : null;
  }
  const fora = {};
  for(const pref of ['p1', 'p2', 'p3', 'p4']){
    const ctl = document.querySelector('.ctl[data-controle="' + pref + '"]');
    if(!ctl) continue;
    const antes = ctl.style.display;
    ctl.style.display = 'none';
    const els = {
      'ana-e': ctl.querySelector('.stick[data-stick="l"] .p'),
      'ana-d': ctl.querySelector('.stick[data-stick="r"] .p'),
      'touch': ctl.querySelector('.touch .ponto-1'),
      'touch2': ctl.querySelector('.touch .ponto-2')};
    fora[pref] = {};
    for(const k of Object.keys(els)){
      const el = els[k];
      fora[pref][k] = el ? [pct(el, 'x'), pct(el, 'y')] : null;
    }
    ctl.style.display = antes;
  }
  return JSON.stringify(fora);
})()
"""


def _perguntar_e_guardar(piloto: Any, js: str, fora: Any, chave: str) -> None:
    def guardou(valor: Any, erro: Any) -> None:
        fora.avaliados[chave] = erro or json.loads(str(valor))

    piloto.tela.ponte.perguntar(js, guardou)


def _ctl_fixo(c: dict[str, Any], inputs: Any) -> dict[str, Any]:
    novo = copy.deepcopy(c)
    novo["inputs"] = inputs
    return novo


def _dois_dedos(x1: int, y1: int, x2: int, y2: int) -> dict[str, Any]:
    return {"touching": True, "x": x1, "y": y1, "width": 1920, "height": 1080,
            "pontos": [{"slot": 0, "x": x1, "y": y1, "id": 1},
                       {"slot": 1, "x": x2, "y": y2, "id": 2}]}


def _por_assento(estado: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """`{"p1": controle, …}` — o assento é o `player_slot`, não a ordem da lista.

    Na fixture da casa o P1 é o SEGUNDO da lista (`player_slot` 1) e o
    primeiro da lista senta no P4: uma régua que lesse a ordem mediria o
    assento errado.
    """
    return {f"p{c['player_slot']}": c for c in estado["controllers"]}


#: As fases do roteiro dos pontinhos, na ordem: as réguas R5 as leem.
FASES_DOS_PONTINHOS = ("antes de observar", "andando", "até os extremos",
                       "até o vazio", "o vazio parado")


@pytest.fixture(scope="module")
def os_pontinhos(publicado_de_hoje: pathlib.Path) -> SimpleNamespace:
    """A 02 com quatro controles: 10 tiques de chegada, 40 com os analógicos andando, depois
    três estados fixos — os extremos, e o lugar do P4 que fica vazio —, de 20
    tiques cada."""
    base = _estado_da_fixture(4)
    assento = _por_assento(base)
    extremos = copy.deepcopy(base)
    extremos["controllers"] = [
        _ctl_fixo(assento["p1"], {"lx": 0, "ly": 0, "rx": 255, "ry": 255,
                                  "touchpad": _dois_dedos(0, 0, 1920, 1080)}),
        _ctl_fixo(assento["p2"], None),
        _ctl_fixo(assento["p3"], {"lx": 255, "ly": 255, "rx": 0, "ry": 0,
                                  "touchpad": _dois_dedos(1920, 1080, 0, 0)}),
        _ctl_fixo(assento["p4"], {"lx": 128, "ly": 128, "rx": 128, "ry": 128,
                                  "touchpad": {"touching": False, "x": 0, "y": 0,
                                               "width": 1920, "height": 1080}}),
    ]
    sem_o_quarto = copy.deepcopy(extremos)
    sem_o_quarto["controllers"] = extremos["controllers"][:3]

    def observar(fora: Any, piloto: Any) -> None:
        piloto.tela.ponte.perguntar(OBSERVAR_AS_FOLHAS, lambda *_a: None)

    def leu_andando(fora: Any, piloto: Any) -> None:
        _perguntar_e_guardar(piloto, LER_AS_FOLHAS, fora, "andando")
        fora.estado.fixo = extremos

    def leu_os_extremos(fora: Any, piloto: Any) -> None:
        _perguntar_e_guardar(piloto, ONDE_ESTAO, fora, "extremos")
        fora.estado.fixo = sem_o_quarto

    def leu_o_vazio(fora: Any, piloto: Any) -> None:
        _perguntar_e_guardar(piloto, ONDE_ESTAO, fora, "vazio")
        _perguntar_e_guardar(piloto, LER_AS_FOLHAS, fora, "vazio-antes")

    def leu_o_vazio_depois(fora: Any, piloto: Any) -> None:
        _perguntar_e_guardar(piloto, LER_AS_FOLHAS, fora, "vazio-depois")

    #: Cada etapa: o marco, a fase que o precede, quantos tiques ela junta, e o
    #: que o roteiro faz ao fim dela. As fases são as `FASES_DOS_PONTINHOS`.
    etapas = [("observa", FASES_DOS_PONTINHOS[0], 10, observar),
              ("leu-andando", FASES_DOS_PONTINHOS[1], TIQUES_POR_FASE, leu_andando),
              ("extremos", FASES_DOS_PONTINHOS[2], 20, leu_os_extremos),
              ("vazio", FASES_DOS_PONTINHOS[3], 20, leu_o_vazio),
              ("vazio-depois", FASES_DOS_PONTINHOS[4], 20, leu_o_vazio_depois)]

    def roteiro(fora: Any, piloto: Any, _t: float) -> bool:
        de = fora.comeco
        for marco, fase, quantos, fazer in etapas:
            if marco in fora.marcos:
                de = fora.marcos[marco]
                continue
            if _fase(fora, fase, de, quantos, _teto_da_fase_s(fora, quantos)):
                fora.marcos[marco] = time.monotonic()
                fazer(fora, piloto)
            return True
        # A ÚLTIMA LEITURA É UMA ESPERA: acaba quando a resposta chega.
        return ("vazio-depois" not in fora.avaliados
                and time.monotonic() - de < _teto_da_espera_s())

    return _correr(publicado_de_hoje, "02-controles.html", 4, roteiro, anda="analogico")


def test_r5_nenhuma_folha_enderecada_muda_no_tique(os_pontinhos: Any) -> None:
    """40 tiques com os analógicos andando nos quatro assentos: zero mutação
    em qualquer `<style data-campo>`, e os pontinhos mudando pelo alvo.

    MORDIDA: a folha `posicao-css` de volta (o produto de `dca12170b`) dá uma
    mutação de folha por tique.
    """
    _sem_fome(os_pontinhos, *FASES_DOS_PONTINHOS[:2])
    lido = os_pontinhos.avaliados.get("andando")
    assert isinstance(lido, dict), f"a régua não leu o observador: {lido}"
    assert lido["folhas"] == 0, f"{lido['folhas']} mutação(ões) em folha endereçada"
    assert lido["pontinhos"] >= 20, (
        f"os pontinhos só mudaram {lido['pontinhos']} vez(es) com os analógicos "
        "andando — a régua ficaria verde sobre um pontinho parado")


def _perto(lido: list[float | None] | None, x: float, y: float) -> bool:
    return (lido is not None and None not in lido
            and abs(float(lido[0] or 0) - x) < 0.05 and abs(float(lido[1] or 0) - y) < 0.05)


def test_r5_o_pontinho_vai_aos_extremos_e_volta_ao_repouso(os_pontinhos: Any) -> None:
    """`lx=0` é 0%, `lx=255` é 100%, sem leitura é 50,2% — nos quatro assentos
    e nos dois dedos do touchpad.

    MORDIDA: tire o ramo `posicao` do `escrever` do BOOTSTRAP e os pontinhos
    ficam onde o desenho os cravou (ou no repouso).
    """
    _sem_fome(os_pontinhos, *FASES_DOS_PONTINHOS[:3])
    onde = os_pontinhos.avaliados.get("extremos")
    assert isinstance(onde, dict), f"a régua não leu os pontinhos: {onde}"
    repouso = {k: (50.2, 50.2) for k in ("ana-e", "ana-d", "touch", "touch2")}
    esperado = {
        "p1": {"ana-e": (0, 0), "ana-d": (100, 100), "touch": (0, 0), "touch2": (100, 100)},
        "p2": repouso,
        "p3": {"ana-e": (100, 100), "ana-d": (0, 0), "touch": (100, 100), "touch2": (0, 0)},
        "p4": repouso,
    }
    errados = {f"{p}/{k}": (onde.get(p) or {}).get(k)
               for p, alvos in esperado.items() for k, (x, y) in alvos.items()
               if not _perto((onde.get(p) or {}).get(k), x, y)}
    assert not errados, f"pontinhos fora do lugar: {errados}"


def test_r5_o_lugar_vazio_volta_ao_repouso_e_nao_soma_pintura(os_pontinhos: Any) -> None:
    """O P4 sai da mesa: os pontinhos dele voltam a 50,2% e param de mudar.

    MORDIDA: faça o ramo `posicao` escrever o travessão (`--hef-x:—`) em vez
    de tirar as variáveis e a regra invalida: o `left` volta `auto`.
    """
    _sem_fome(os_pontinhos, *FASES_DOS_PONTINHOS)
    onde = os_pontinhos.avaliados.get("vazio")
    assert isinstance(onde, dict), onde
    for k in ("ana-e", "ana-d", "touch", "touch2"):
        assert _perto(onde["p4"][k], 50.2, 50.2), f"p4/{k} = {onde['p4'][k]}"
    antes = os_pontinhos.avaliados.get("vazio-antes") or {}
    depois = os_pontinhos.avaliados.get("vazio-depois") or {}
    assert depois.get("pontinhos") == antes.get("pontinhos"), (
        f"com os três que ficaram parados, os pontinhos seguiram mudando: "
        f"{antes} → {depois}")


def _pagina_virgem_e_lida(pagina: pathlib.Path) -> list[list[Any]]:
    """O `LER_CAMPOS` do piloto sobre a página VIRGEM — sem BOOTSTRAP."""
    gtk = _gtk()
    from gi.repository import GLib, WebKit2

    import hefesto_vivo as hv

    saiu: list[str] = []
    janela = gtk.OffscreenWindow()
    view = WebKit2.WebView()
    janela.add(view)
    janela.show_all()

    def guardou(v: Any, res: Any) -> None:
        try:
            saiu.append(v.evaluate_javascript_finish(res).to_string())
        except Exception as e:  # pragma: no cover
            saiu.append(f"ERRO {e}")
        gtk.main_quit()

    def carregou(v: Any, evento: Any) -> None:
        if evento == WebKit2.LoadEvent.FINISHED:
            v.evaluate_javascript(hv.LER_CAMPOS, -1, None, None, None, guardou)

    view.connect("load-changed", carregou)
    view.load_uri(pagina.as_uri())
    guarda = GLib.timeout_add(30000, gtk.main_quit)
    try:
        gtk.main()
    finally:
        GLib.source_remove(guarda)
        janela.destroy()
    assert saiu and not saiu[0].startswith("ERRO"), saiu
    return list(json.loads(saiu[0]))


def test_r5_a_prova_do_mockup_le_o_alvo_nos_dois_lados() -> None:
    """O arquivo e a tela dizem o MESMO de cada pontinho, antes de pintar.

    É o contrato da `--prova-de-mockup`: o `LER_CAMPOS` (a tela) e o
    `regua_do_mockup._campo` (o arquivo) na mesma língua, `x,y` ou vazio.

    MORDIDA: tire o ramo `posicao` do `LER_CAMPOS` (a tela lê o texto vazio do
    `<span>`), ou o de `regua_do_mockup._campo` (o arquivo lê vazio): os dois
    lados deixam de casar.
    """
    from hefesto_dualsense4unix.interface import onde, regua_do_mockup

    pagina = onde.pagina("02-controles.html")
    tela = [(ln[0], ln[1], ln[3]) for ln in _pagina_virgem_e_lida(pagina)
            if ln[2] == "posicao"]
    arquivo = [(c.chave, c.dono, c.valor)
               for c in regua_do_mockup._campos_cravados(pagina.read_text(encoding="utf-8"))
               if c.alvo == "posicao"]
    assert len(tela) == 16, f"a tela tem {len(tela)} pontinhos com o alvo `posicao`"
    assert tela == arquivo, f"a tela e o arquivo discordam:\n{tela}\n{arquivo}"
    assert ("pos-ana-e", "p1", "23.5,78.4") in tela


# ===========================================================================
# R6 — A CAMADA 1 RODA CADA `pactl` UMA VEZ POR RENOVAÇÃO
# ===========================================================================
UNIQS = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03",
         "aa:bb:cc:00:00:04")
SINKS_CURTOS = (
    "101\thefesto_som_000002\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n"
    "103\talsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40\tPipeWire\ts16le 4ch 48000Hz\tSUSPENDED\n")
NO_NATIVO = ("alsa_input.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
             "Controller-00.analog-stereo")
FONTE_NATIVA = f"55\t{NO_NATIVO}\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n"
#: A leitura LONGA da mesma fonte: o `sysfs.path` leva ao USB, o `alsa.card` à placa.
FONTE_NATIVA_LONGA = (
    "Source #55\n"
    f"\tName: {NO_NATIVO}\n"
    "\tProperties:\n"
    '\t\tsysfs.path = "/devices/pci0000:00/usb1/1-2/1-2:1.0/sound/card3"\n'
    '\t\talsa.card = "3"\n')


@pytest.fixture
def renovacao(monkeypatch: pytest.MonkeyPatch) -> Any:
    """UMA renovação da camada 1, pela thread do produto, com os dois donos dublados.

    `subprocess.run` e `Popen` ficam armados para levantar: nenhum `pactl` real
    roda. Os caches da 02 voltam como estavam no fim.

    TRÊS MESAS DE SOM (`conta.nativa`):

    * ``""`` — só as fontes da ponte, nenhuma nativa (o rádio);
    * ``"sem-casamento"`` — há fonte nativa, e a leitura longa volta vazia: o
      casamento por USB não se monta e ninguém é dono dela. É o dublê da
      contestação, o dos 29;
    * ``"casada"`` — a fonte nativa é do P1: a leitura longa traz o
      `sysfs.path` e a placa, e o censo de USB (dublado, sem `/sys`) põe os
      dois no mesmo dispositivo. É a que exercita o `list sources` e o
      `amixer` do ganho.
    """
    import subprocess

    from hefesto_dualsense4unix.app import audio_saida
    from hefesto_dualsense4unix.integrations import eleicao_de_microfone as el
    from hefesto_dualsense4unix.integrations import usb_pai
    from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

    def fora_da_suite(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("um comando REAL rodou na renovação")

    monkeypatch.setattr(subprocess, "run", fora_da_suite)
    monkeypatch.setattr(subprocess, "Popen", fora_da_suite)
    monkeypatch.setattr(usb_pai, "usb_pai_por_uniq",
                        lambda uniqs, **_k: {u: ("1-2" if u == UNIQS[0] else "")
                                             for u in uniqs})
    monkeypatch.setattr(usb_pai, "usb_pai_por_no",
                        lambda por_no, **_k: {n: ("1-2" if v else "")
                                              for n, v in por_no.items()})
    conta = SimpleNamespace(audio=[], eleicao=[], nativa="")

    def saida(argv: list[str]) -> str:
        k = " ".join(argv)
        if k == "pactl list sinks short":
            return SINKS_CURTOS
        if k == "pactl list sources short":
            return FONTE_NATIVA if conta.nativa else ""
        if k == "pactl list sources":
            return FONTE_NATIVA_LONGA if conta.nativa == "casada" else ""
        return ""

    def rodar_leitura(argv: list[str]) -> str:
        conta.audio.append(" ".join(argv))
        return saida(argv)

    def rodar_da_eleicao(argv: list[str]) -> tuple[int, str]:
        conta.eleicao.append(" ".join(argv))
        return (0, saida(argv).strip())

    monkeypatch.setattr(audio_saida, "rodar_leitura", rodar_leitura)
    monkeypatch.setattr(el, "_rodar", rodar_da_eleicao)
    monkeypatch.setattr(audio_saida, "regra_nunca_dorme_instalada", lambda: True)
    guardado = [(d, dict(d)) for d in a02._POR_CONTROLE]
    quando, selo, regra = a02._CAMADA_1_QUANDO[0], a02._CAMADA_1_SELO[0], a02._REGRA_DO_SONO[0]

    def renovar(n: int) -> SimpleNamespace:
        conta.audio.clear()
        conta.eleicao.clear()
        a02._CAMADA_1_QUANDO[0] = 0.0
        a02._CAMADA_1_EM_VOO[0] = False
        mesa = UNIQS[:n]
        a02._camada_1(tuple((u, None) for u in mesa), mesa)
        fim = time.time() + 10
        while a02._CAMADA_1_EM_VOO[0] and time.time() < fim:
            time.sleep(0.01)
        assert not a02._CAMADA_1_EM_VOO[0], "a renovação não pousou em 10 s"
        return conta

    yield SimpleNamespace(renovar=renovar, conta=conta, a02=a02, el=el)
    for d, antes in guardado:
        d.clear()
        d.update(antes)
    a02._CAMADA_1_QUANDO[0], a02._CAMADA_1_SELO[0] = quando, selo
    a02._REGRA_DO_SONO[0] = regra


@pytest.mark.parametrize(("n", "nativa", "esperado"), [
    (1, "", 4), (2, "", 4), (4, "", 4), (4, "sem-casamento", 5), (4, "casada", 7)])
def test_r6_cada_pactl_uma_vez_por_dono(renovacao: Any, n: int, nativa: str,
                                         esperado: int) -> None:
    """Uma chamada por `argv` e por dono em cada renovação.

    Com quatro controles e sem fonte nativa são 4 (eram 21). Com a fonte
    nativa da contestação, que ninguém casa, são 5 (eram 29: a sprint
    escreveu 6, e o sexto seria o `list sources` do ganho, que só roda
    quando a fonte tem dono). Com a fonte casada ao P1 são 7 (eram 31): o
    `list sources` e o `amixer` do ganho entram, uma vez cada.

    MORDIDA: tire o `with _uma_leitura_por_volta()` do `renovar` e voltam as
    21, as 29 e as 31.
    """
    renovacao.conta.nativa = nativa
    conta = renovacao.renovar(n)
    total = len(conta.audio) + len(conta.eleicao)
    assert total == esperado, (
        f"{total} chamadas numa renovação com {n} controle(s) (nativa={nativa!r}): "
        f"audio={conta.audio} eleicao={conta.eleicao}")
    assert len(set(conta.audio)) == len(conta.audio)
    assert len(set(conta.eleicao)) == len(conta.eleicao)


def test_r6_a_eleicao_roda_pelo_dono_dela(renovacao: Any) -> None:
    """A memória da eleição embrulha o `_rodar` DELA, e não o de `audio_saida`.

    As réguas dublam os dois separadamente; uma memória que chamasse
    `audio_saida` no lugar da eleição passaria por cima do dublê do `_rodar` e,
    na suíte sem dublê, rodaria o `pactl` dela.

    MORDIDA: faça o `_ler` da eleição chamar `audio_saida.rodar_leitura` e o
    dublê do `_rodar` deixa de ser chamado.
    """
    renovacao.conta.nativa = "casada"
    conta = renovacao.renovar(4)
    assert "pactl list sources short" in conta.eleicao, conta.eleicao
    assert "pactl list sources" in conta.eleicao, conta.eleicao
    assert "pactl list sources" in conta.audio, conta.audio
    assert "amixer -c 3 scontents" in conta.audio, conta.audio


def test_r6_fora_da_renovacao_nada_muda(renovacao: Any) -> None:
    """Sem a renovação ligada, cada pergunta à eleição roda de novo.

    O daemon e os gestos perguntam à eleição fora da 02, e para eles uma
    resposta de dois segundos atrás seria estado velho.
    """
    renovacao.conta.nativa = "casada"
    el = renovacao.el
    el.microfone_nativo_no_ar(UNIQS[0], list(UNIQS[:1]))
    el.microfone_nativo_no_ar(UNIQS[0], list(UNIQS[:1]))
    assert renovacao.conta.eleicao.count("pactl list sources short") == 2


def test_r6_o_duble_da_funcao_publica_continua_alcancando(
        renovacao: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """O dublê de `fonte_nativa_do_controle` (o das réguas do ganho) é lido.

    As assinaturas públicas da eleição não mudaram, e a 02 continua chamando a
    função pelo módulo, na hora.
    """
    el = renovacao.el
    monkeypatch.setattr(el, "fonte_nativa_do_controle",
                        lambda uniq, _mesa: "" if uniq == UNIQS[1] else None)
    lido = renovacao.a02._ler_o_ganho(UNIQS[:2])
    assert lido == {UNIQS[1]: None}, lido


# ===========================================================================
# R7 — A JANELA DE 10 H NÃO ACUMULA
# ===========================================================================
def test_r7_cem_mil_tiques_guardam_so_os_ultimos(publicado_de_hoje: pathlib.Path) -> None:
    """100 mil custos de tique guardam no máximo 6.000 — 10 min de tique.

    O tique acrescenta ao MESMO contêiner (conferido depois de tiques de
    verdade), e ele tem teto.

    MORDIDA: volte `custos` e `custo_do_ipc` a `list` e ficam 100 mil.
    """
    def roteiro(fora: Any, _piloto: Any, _t: float) -> bool:
        return not _fase(fora, "dos custos", fora.comeco, 10, _teto_da_fase_s(fora, 10))

    fora = _correr(publicado_de_hoje, "01-jogar.html", 1, roteiro)
    _sem_fome(fora, "dos custos")
    piloto = fora.piloto
    assert len(piloto.custos) >= 5 and len(piloto.custo_do_ipc) >= 5
    for i in range(100_000):
        piloto.custos.append(float(i))
        piloto.custo_do_ipc.append(float(i))
    # O TETO É LIDO DO PRODUTO, e não digitado: o que a régua cobra é que ele
    # exista e fique abaixo dos tiques simulados, senão ela não morderia.
    teto = piloto.CUSTOS_GUARDADOS
    assert 0 < teto < 100_000, f"teto {teto}: a régua não morderia com ele"
    assert len(piloto.custos) <= teto and len(piloto.custo_do_ipc) <= teto, (
        f"{len(piloto.custos)} custos guardados — a janela de 10 h acumula")
    assert piloto.custos[-1] == 99_999.0
