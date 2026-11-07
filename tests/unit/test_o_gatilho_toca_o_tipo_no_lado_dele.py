"""O gatilho toca o tipo no lado dele (O-GATILHO-TOCA-O-TIPO-NO-LADO-DELE-01).

L2 no motor esquerdo, R2 no direito, ao apertar, em toda opção da aba Jogar, salvo o Nativo. A
régua por pares roda o ``TatoVivo``, o ``AtuadorDosMotores``, a saída de produção e o
``AltoFalanteSubsystem`` do produto com relógio falso; só o tocador e o motor do nó são dublês.
"""
from __future__ import annotations

from array import array
from collections.abc import Iterable
from itertools import combinations, product
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import ganho_da_haptica, lifecycle
from hefesto_dualsense4unix.daemon.subsystems import alto_falante as af
from hefesto_dualsense4unix.daemon.subsystems import padroes_de_vibracao as pv
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.profiles.estilos_de_jogo import ESTILOS

P = tuple(f"aa:bb:cc:00:00:{i:02x}" for i in range(1, 5))
CABO, RADIO_COM_PONTE, RADIO_SEM_PONTE = "cabo", "radio_com_ponte", "radio_sem_ponte"
CALADO, RUMBLE, ENDPOINT = "calado", "rumble", "endpoint"
SONY, XBOX, NINTENDO, STEAM, NAVEGACAO, NATIVO = (
    "dualsense", "xbox", "nintendo", "steam", "navegacao", "nativo")
DUALSENSE, EDGE, PRO, OITO_BITDO = "dualsense", "edge", "pro", "8bitdo"
APPID = 1196590
TIPOS = (pv.SEM_EFEITO, pv.DO_ESTILO, *pv.PADROES)
_RECEITA = tv.Receita(padroes_escolhidos=True)


class _Tocador:
    def __init__(self) -> None:
        self.lados: list[tuple[int, int]] = []

    def levar_os_lados(self, esquerdo: int, direito: int, *, sink: str, dono: str) -> None:
        self.lados.append((esquerdo, direito))


class _Backend:
    primary_uniq: str | None = None

    def __init__(self) -> None:
        self.rumble: list[tuple[str, int, int]] = []

    def set_rumble_for(self, uniq: str, fraco: int, forte: int) -> bool:
        self.rumble.append((uniq, fraco, forte))
        return True


def _pad(chip: str, *, jogo: str = CALADO) -> Any:
    backend = {SONY: "uhid", XBOX: "uinput", NINTENDO: "uinput"}.get(chip)
    if backend is None:
        return None
    visto = {"rumble": 0.1} if jogo == RUMBLE else {}
    if jogo == ENDPOINT:
        visto = {"audio_do_jogo": 0.1}
    return SimpleNamespace(backend=backend, game_open=True, visto_ha_s=visto)


class _Cabo:
    def __init__(self, donos: dict[str, str]) -> None:
        self.donos = donos

    def aparelhos(self) -> dict[str, Any]:
        return {m: SimpleNamespace(dono=d) for m, d in self.donos.items()}

    def leva_os_motores(self, _marca: str) -> bool:
        return True


class _Mesa:
    """Um daemon com os controles pedidos: cada um na conexão, no pad e na família dele."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, *, estilo: str | None = None, chip: str = SONY,
        conexoes: dict[str, str] | None = None, familias: dict[str, str] | None = None,
        forca: int = 80, jogo: str = CALADO, primario: str | None = None,
    ) -> None:
        conexoes = conexoes or {P[0]: CABO}
        familias = familias or {}
        monkeypatch.setattr(tv, "estilo_ativo", lambda _d: estilo)
        monkeypatch.setattr(tv, "_barras_dos_motores", lambda _d, _u: (100, 100))
        monkeypatch.setattr(ganho_da_haptica.GANHO, "pct", lambda _u: self.forca)
        self.forca = forca
        self.backend = _Backend()
        self.alto = af.AltoFalanteSubsystem()
        self.tocadores: dict[str, _Tocador] = {}
        self.no: list[tuple[str, int, int]] = []
        self._ligar_as_rotas(conexoes, familias, jogo)
        self.pads = {u: _pad(chip, jogo=jogo) for u in conexoes}
        primeiro = primario or next(iter(conexoes))
        self.backend.primary_uniq = primeiro
        jogadores = {
            u: SimpleNamespace(
                reader=SimpleNamespace(snapshot=lambda: None),
                vpad=self.pads[u], motion_reader=None,
                externo=familias.get(u) in (PRO, OITO_BITDO))
            for u in conexoes if u != primeiro
        }
        self.daemon = SimpleNamespace(
            controller=self.backend, _gamepad_device=self.pads[primeiro],
            _last_state=None, _motion_reader=None,
            _coop_manager=SimpleNamespace(_players=jogadores),
            _alto_falante_subsystem=self.alto,
            is_native_mode=lambda: chip in (STEAM, NATIVO),
            appid_em_cena=APPID,
        )
        self.tipos: dict[str, str | None] = {}
        self.jogo_aberto = True
        saida = tv.saida_dos_padroes(self.daemon)
        self.atuador = tv.AtuadorDosMotores(
            saida, lambda u: pv.padrao_que_vale(self.tipos.get(u), estilo),
            lambda _u: 1.0, lambda: estilo, saida.largar)
        self.motor = tv.TatoVivo([self.atuador])
        if chip == STEAM:
            self.motor.steam_input = frozenset({APPID})
        self.daemon._tato_vivo = self.motor
        monkeypatch.setattr(
            "hefesto_dualsense4unix.daemon.subsystems.gamepad.vibrar_o_externo",
            lambda _d, _m, u, fraco, forte: self.no.append((u, fraco, forte)) or (fraco, forte))

    def _ligar_as_rotas(
        self, conexoes: dict[str, str], familias: dict[str, str], jogo: str
    ) -> None:
        aparelhos: dict[str, str] = {}
        cabos: dict[str, str] = {}
        tocadores: dict[str, Any] = {}
        for uniq, conexao in conexoes.items():
            if familias.get(uniq) in (PRO, OITO_BITDO):
                continue
            marca = f"m{uniq[-2:]}"
            aparelhos[uniq] = marca
            nome = f"hefesto_haptica_{marca}"
            self.alto._endpoints[marca] = SimpleNamespace(module_id=1, nome=nome)
            self.tocadores[uniq] = tocadores[marca] = _Tocador()
            if conexao == CABO:
                cabos[marca] = uniq
            elif conexao == RADIO_COM_PONTE:
                self.alto._pontes[uniq] = SimpleNamespace(esta_de_pe=lambda: True)
                self.alto._leva_da_ponte = MappingProxyType(
                    {**self.alto._leva_da_ponte, uniq: True})
                self.alto._endpoint_da_ponte = MappingProxyType(
                    {**self.alto._endpoint_da_ponte, uniq: nome})
        self.alto._aparelho_de = MappingProxyType(aparelhos)
        self.alto._tocadores = MappingProxyType(tocadores)
        self.alto._cabo = _Cabo(cabos)
        if jogo == ENDPOINT:
            self.alto._aparelhos_com_jogo = frozenset(aparelhos.values())

    def estado_de(self, uniq: str) -> tv.EstadoDoCanal | None:
        for controle in tv.controles_do_daemon(self.daemon):
            if controle.uniq == uniq:
                return tv.estado_do_controle(controle, self.jogo_aberto, motores_no_audio=(
                    tv.rota_do_padrao(self.daemon, uniq) == pv.ROTA_AUDIO))
        return None

    def evento(self, uniq: str, lado: str, tipo: str = tv.TIPO_DEDO, t: float = 0.0) -> None:
        self.motor.anotar(tv.Evento(t, uniq, tipo, lado, 1.0))

    def correr(self, ate: float, desde: float = 0.0, receita: tv.Receita = _RECEITA) -> None:
        uniqs = tuple(c.uniq for c in tv.controles_do_daemon(self.daemon))
        t = desde
        while t <= ate + 1e-9:
            self.motor.tique(t, self.estado_de, receita, uniqs=uniqs)
            t += tv.INTERVALO_S

    def saidas(self, uniq: str) -> list[tuple[int, int]]:
        """O que foi tocado neste controle, como ``(esquerdo, direito)``, por qualquer saída."""
        tocador = self.tocadores.get(uniq)
        pcm = list(tocador.lados) if tocador is not None else []
        report = [(forte, fraco) for u, fraco, forte in self.backend.rumble if u == uniq]
        no = [(forte, fraco) for u, fraco, forte in self.no if u == uniq]
        return pcm + report + no


def _tocou(saidas: Iterable[tuple[int, int]]) -> tuple[bool, bool]:
    lista = list(saidas)
    return any(e for e, _d in lista), any(d for _e, d in lista)


def test_l2_vai_ao_motor_esquerdo_e_r2_ao_direito(monkeypatch: pytest.MonkeyPatch) -> None:
    for lado, esperado in ((tv.LADO_ESQUERDO, (True, False)), (tv.LADO_DIREITO, (False, True))):
        mesa = _Mesa(monkeypatch)
        mesa.tipos[P[0]] = "tranco"
        mesa.evento(P[0], lado)
        mesa.correr(1.0)
        assert _tocou(mesa.saidas(P[0])) == esperado


def test_l2_e_r2_juntos_tocam_os_dois_e_um_nao_corta_o_outro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.tipos[P[0]] = "batida"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    mesa.evento(P[0], tv.LADO_DIREITO, t=0.06)
    mesa.correr(1.5, desde=0.06)
    saidas = mesa.saidas(P[0])
    assert (255, 255) in saidas, "os dois lados tocam ao mesmo tempo"
    assert saidas[-1] == (0, 0), "os dois terminam em zero"


def test_o_mesmo_lado_nao_reinicia_enquanto_toca(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.tipos[P[0]] = "onda"
    mesa.evento(P[0], tv.LADO_DIREITO)
    mesa.correr(0.1)
    em_curso = dict(mesa.atuador._em_curso)
    mesa.evento(P[0], tv.LADO_DIREITO, t=0.12)
    mesa.correr(0.2, desde=0.12)
    assert mesa.atuador._em_curso[(P[0], pv.DIREITO)] is em_curso[(P[0], pv.DIREITO)]


@pytest.mark.parametrize("forma", sorted(pv.PADROES))
def test_cada_lado_projeta_a_forma_inteira(forma: str) -> None:
    projetada = pv.sequencia(forma, pv.DIREITO)
    assert projetada == tuple((ms, 0, max(e, d)) for ms, e, d in pv.PADROES[forma])
    assert pv.sequencia(forma, pv.ESQUERDO) == tuple((ms, d, e) for ms, e, d in projetada)


def test_o_ressoar_vale_igual_nos_dois_lados() -> None:
    assert pv.duracao_ms("ressoar") == sum(ms for ms, _e, d in pv.sequencia("ressoar", pv.DIREITO))
    assert [d for _ms, _e, d in pv.sequencia("ressoar", pv.DIREITO)] == [
        e for _ms, e, _d in pv.sequencia("ressoar", pv.ESQUERDO)]
    assert [d for _ms, _e, d in pv.sequencia("ressoar", pv.DIREITO)][:3] == [255, 200, 150]


def test_a_dica_do_ricochete_nao_promete_o_outro_lado() -> None:
    """No gatilho o Ricochete toca num motor só: a tela diz o que o aparelho faz."""
    assert "lado" not in pv.DICAS["ricochete"]
    assert not any(d for _ms, _e, d in pv.sequencia("ricochete", pv.ESQUERDO))


def test_o_coice_toca_ao_soltar_e_no_lado_do_gatilho(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.tipos[P[0]] = "coice"
    mesa.evento(P[0], tv.LADO_DIREITO)
    mesa.correr(0.2)
    assert mesa.saidas(P[0]) == []
    mesa.evento(P[0], tv.LADO_DIREITO, tv.TIPO_SOLTA, 0.21)
    mesa.correr(1.0, desde=0.21)
    assert _tocou(mesa.saidas(P[0])) == (False, True)


@pytest.mark.parametrize("estilo", ["fps", "acao", "terror"])  # (noqa-acento)
def test_o_estilo_de_rajada_toca_no_aperto(
    estilo: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    mesa = _Mesa(monkeypatch, estilo=estilo)
    mesa.tipos[P[0]] = "ressoar"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(0.05, receita=tv.Receita(padroes_escolhidos=True, gatilho_no_ritmo=True))
    assert mesa.saidas(P[0]), "o aperto tocou"


def test_a_regra_de_soltura_do_estilo_fica(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, estilo="furtivo")
    mesa.tipos[P[0]] = "onda"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(0.2)
    assert mesa.saidas(P[0]) == []


def test_o_padrao_nao_troca_o_nivel_do_rumble() -> None:
    relogio = {"t": 10.0}
    tocador = eh.TocadorDoRumble("m", argv_de=lambda _s, _r: [], relogio=lambda: relogio["t"])
    try:
        tocador.levar(100, 200, sink="s", dono="d")
        tocador.levar_os_lados(255, 0, sink="s", dono="d")
        assert tocador.nivel == (100, 200)
        assert tocador.lados == (255, 0)
    finally:
        tocador.parar()


def _canais(bloco: bytes) -> tuple[array[float], array[float]]:
    quadros = array("f")
    quadros.frombytes(bloco)
    return quadros[2::4], quadros[3::4]


def _energia(canal: array[float]) -> float:
    return float(sum(x * x for x in canal))


def test_o_bloco_soma_cada_lado_no_canal_dele_por_cima_do_rumble() -> None:
    relogio = {"t": 10.0}
    tocador = eh.TocadorDoRumble("m", argv_de=lambda _s, _r: [], relogio=lambda: relogio["t"])
    try:
        sem = tocador.proximo_bloco((60, 60), (60, 60), 0)
        tocador.levar_os_lados(255, 0, sink="s", dono="d")
        tocador.proximo_bloco((60, 60), (60, 60), 0)
        com = tocador.proximo_bloco((60, 60), (60, 60), 0)
    finally:
        tocador.parar()
    assert _energia(_canais(com)[0]) > 2 * _energia(_canais(sem)[0]), "o esquerdo somou"
    assert _energia(_canais(com)[1]) == pytest.approx(_energia(_canais(sem)[1])), "o direito fica"


def test_o_lado_sem_quem_o_renove_cala_sozinho() -> None:
    relogio = {"t": 10.0}
    tocador = eh.TocadorDoRumble("m", argv_de=lambda _s, _r: [], relogio=lambda: relogio["t"])
    try:
        tocador.levar_os_lados(255, 255, sink="s", dono="d")
        assert tocador.lados == (255, 255)
        relogio["t"] += eh.VALIDADE_DOS_LADOS_S
        assert tocador.lados == (0, 0)
    finally:
        tocador.parar()


def test_no_cabo_o_padrao_sai_pelo_pcm_e_nunca_pelo_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(1.0)
    assert mesa.tocadores[P[0]].lados and not mesa.backend.rumble, (
        "o bit do motor cala o PCM: o padrão não pode ir direto ao set_rumble_for")


def test_no_radio_com_ponte_o_padrao_sai_pelo_pcm(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, conexoes={P[0]: RADIO_COM_PONTE})
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_DIREITO)
    mesa.correr(1.0)
    assert mesa.tocadores[P[0]].lados and not mesa.backend.rumble


def test_no_radio_sem_ponte_cai_no_report(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, conexoes={P[0]: RADIO_SEM_PONTE})
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_DIREITO)
    mesa.correr(1.0)
    assert mesa.backend.rumble and not mesa.tocadores[P[0]].lados


def test_pelo_pcm_o_rumble_do_jogo_nao_cala_o_padrao(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, jogo=RUMBLE)
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(1.0)
    assert _tocou(mesa.saidas(P[0])) == (True, False)
    assert mesa.motor.contadores["soltos_ao_jogo"] == 0


def test_pelo_report_o_jogo_manda_e_o_padrao_cede(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, conexoes={P[0]: RADIO_SEM_PONTE}, jogo=RUMBLE)
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(1.0)
    assert mesa.saidas(P[0]) == []
    assert mesa.motor.contadores["recusas_do_jogo"] == 1


def test_com_o_jogo_no_endpoint_segue_a_porta_do_rumble(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, jogo=ENDPOINT)
    assert not mesa.alto._quer_a_haptica_fina(P[0])
    assert mesa.alto.rota_do_padrao(P[0]) == pv.ROTA_AUDIO
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    assert mesa.tocadores[P[0]].lados


@pytest.mark.parametrize("via", [CABO, RADIO_COM_PONTE, RADIO_SEM_PONTE])
def test_forca_zero_cala_e_nao_cai_para_o_motor(
    via: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    mesa = _Mesa(monkeypatch, conexoes={P[0]: via}, forca=0)
    assert mesa.alto.rota_do_padrao(P[0]) == pv.ROTA_CALADA
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(1.0)
    assert mesa.saidas(P[0]) == []


@pytest.mark.parametrize(("forca", "esperado"), [(1.0, 255), (0.6, 153), (0.35, 89)])
def test_a_forca_do_padrao_e_as_barras_so_multiplicam(
    forca: float, esperado: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    mesa = _Mesa(monkeypatch)
    mesa.atuador._forca_de = lambda _u: forca
    monkeypatch.setattr(tv, "_barras_dos_motores", lambda _d, _u: (50, 100))
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    assert mesa.tocadores[P[0]].lados[0] == (round(esperado * 0.5), 0)


@pytest.mark.parametrize(("estilo", "chip", "esperado"), [
    (None, SONY, lifecycle.MODO_DUALSENSE),
    (None, XBOX, lifecycle.MODO_XBOX),
    (None, NINTENDO, lifecycle.MODO_XBOX),
    (None, STEAM, lifecycle.MODO_STEAM_INPUT),
    (None, NAVEGACAO, lifecycle.MODO_NAVEGACAO),
    (None, NATIVO, lifecycle.MODO_NATIVO),
    ("nativo", SONY, lifecycle.MODO_NATIVO),
    ("nativo", XBOX, lifecycle.MODO_NATIVO),
    ("fps", NATIVO, lifecycle.MODO_NATIVO),
])
def test_o_nativo_e_uma_pergunta_so(estilo: str | None, chip: str, esperado: str) -> None:
    daemon = SimpleNamespace(is_native_mode=lambda: chip in (STEAM, NATIVO), appid_em_cena=APPID)
    lista = frozenset({APPID}) if chip == STEAM else frozenset()
    assert lifecycle.modo_do_controle(
        daemon, _pad(chip), estilo=estilo, steam_input=lista) == esperado


def test_o_modo_chega_a_todos_pelo_controle(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, chip=NAVEGACAO, conexoes=dict.fromkeys(P[:2], CABO))
    assert {c.modo for c in tv.controles_do_daemon(mesa.daemon)} == {lifecycle.MODO_NAVEGACAO}
    assert mesa.estado_de(P[1]).modo == lifecycle.MODO_NAVEGACAO


def test_o_steam_input_nao_escreve_no_fisico_e_toca_pelo_pcm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pelo_audio = _Mesa(monkeypatch, chip=STEAM)
    pelo_audio.tipos[P[0]] = "tranco"
    pelo_audio.evento(P[0], tv.LADO_ESQUERDO)
    pelo_audio.correr(1.0)
    assert pelo_audio.tocadores[P[0]].lados and not pelo_audio.backend.rumble
    sem_audio = _Mesa(monkeypatch, chip=STEAM, conexoes={P[0]: RADIO_SEM_PONTE})
    sem_audio.tipos[P[0]] = "tranco"
    sem_audio.evento(P[0], tv.LADO_ESQUERDO)
    sem_audio.correr(1.0)
    assert sem_audio.saidas(P[0]) == [], "a Steam é dona do físico: o report não entra"
    assert not lifecycle.o_hefesto_fala_no_modo(lifecycle.MODO_STEAM_INPUT)


def test_a_lista_do_steam_input_se_le_fora_do_tique(monkeypatch: pytest.MonkeyPatch) -> None:
    lidas: list[int] = []

    def ler() -> set[int]:
        lidas.append(1)
        return {APPID}

    monkeypatch.setattr("hefesto_dualsense4unix.daemon.launch_env.steam_input_appids", ler)
    monkeypatch.setattr(tv, "receita_ativa", lambda _d: _RECEITA)
    motor = tv.TatoVivo([])
    daemon = SimpleNamespace(is_native_mode=lambda: True)
    passo = tv.Passo(daemon, motor)
    passo.tique_do_laco(1.0)
    assert motor.ligado and lidas == []
    passo.andar_o_diario(1.0)
    assert lidas == [1] and motor.steam_input == frozenset({APPID})


def test_o_motor_do_controle_de_fora_vai_pelo_no(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(
        monkeypatch, conexoes={P[0]: CABO, P[1]: RADIO_SEM_PONTE}, familias={P[1]: PRO},
        primario=P[0])
    mesa.tipos[P[1]] = "tranco"
    mesa.evento(P[1], tv.LADO_ESQUERDO)
    mesa.correr(1.0)
    assert mesa.no and not mesa.backend.rumble
    assert mesa.no[0] == (P[1], 0, 255)


def _subir_a_ponte(mesa: _Mesa, uniq: str) -> None:
    marca = mesa.alto._aparelho_de[uniq]
    mesa.alto._pontes[uniq] = SimpleNamespace(esta_de_pe=lambda: True)
    mesa.alto._leva_da_ponte = MappingProxyType({uniq: True})
    mesa.alto._endpoint_da_ponte = MappingProxyType({uniq: f"hefesto_haptica_{marca}"})


@pytest.mark.parametrize("troca", ["ponte", "forca"])
def test_a_rota_que_muda_no_meio_do_padrao_nao_prende_o_motor(
    troca: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    mesa = _Mesa(monkeypatch, conexoes={P[0]: RADIO_SEM_PONTE})
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    assert mesa.backend.rumble[-1] == (P[0], 0, 255)
    if troca == "ponte":
        _subir_a_ponte(mesa, P[0])
    else:
        mesa.forca = 0
    mesa.correr(1.0, desde=0.06)
    assert mesa.backend.rumble[-1] == (P[0], 0, 0), "o motor ficou no último passo"


@pytest.mark.parametrize(("familia", "ligacao"), [(PRO, RADIO_SEM_PONTE), (OITO_BITDO, CABO)])
def test_forca_zero_no_meio_do_padrao_tambem_solta_o_no(
    familia: str, ligacao: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    mesa = _Mesa(
        monkeypatch, conexoes={P[0]: CABO, P[1]: ligacao}, familias={P[1]: familia}, primario=P[0])
    mesa.tipos[P[1]] = "tranco"
    mesa.evento(P[1], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    mesa.forca = 0
    mesa.correr(1.0, desde=0.06)
    assert mesa.no[-1] == (P[1], 0, 0)


def test_o_jogo_que_toma_o_no_de_fora_cala_o_efeito_do_padrao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O efeito do padrão é outro que o do jogo: o zero do jogo nunca o alcança."""
    mesa = _Mesa(
        monkeypatch, conexoes={P[0]: CABO, P[1]: RADIO_SEM_PONTE}, familias={P[1]: PRO},
        primario=P[0])
    mesa.pads[P[1]] = mesa.daemon._coop_manager._players[P[1]].vpad = _pad(SONY)
    mesa.tipos[P[1]] = "tranco"
    mesa.evento(P[1], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    assert mesa.no[-1] == (P[1], 0, 255)
    mesa.pads[P[1]].visto_ha_s = {"rumble": 0.1}
    mesa.correr(0.2, desde=0.06)
    assert mesa.motor.contadores["soltos_ao_jogo"] == 1
    assert mesa.no[-1] == (P[1], 0, 0)


def test_o_jogo_que_toma_o_report_nao_leva_zero_por_cima(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, conexoes={P[0]: RADIO_SEM_PONTE})
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    escritas = len(mesa.backend.rumble)
    mesa.pads[P[0]].visto_ha_s = {"rumble": 0.1}
    mesa.correr(0.2, desde=0.06)
    assert mesa.motor.contadores["soltos_ao_jogo"] == 1
    assert len(mesa.backend.rumble) == escritas


def _o_modo_cala(mesa: _Mesa, muda: str) -> None:
    if muda == NATIVO:
        mesa.daemon.is_native_mode = lambda: True
    else:
        mesa.jogo_aberto = False


@pytest.mark.parametrize("muda", [NATIVO, "jogo_fechou"])
def test_o_modo_que_cala_no_meio_do_padrao_zera_o_report(
    muda: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Quem deixou o motor ligado o desliga: ali não há jogo para mandar o zero dele."""
    mesa = _Mesa(monkeypatch, conexoes={P[0]: RADIO_SEM_PONTE})
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    assert mesa.backend.rumble[-1] == (P[0], 0, 255)
    _o_modo_cala(mesa, muda)
    mesa.correr(0.2, desde=0.06)
    assert mesa.backend.rumble[-1] == (P[0], 0, 0), "o motor ficou no último passo"
    assert not mesa.motor.pendentes


@pytest.mark.parametrize("muda", [NATIVO, "jogo_fechou"])
def test_o_modo_que_cala_no_meio_do_padrao_zera_o_no_de_fora(
    muda: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    mesa = _Mesa(
        monkeypatch, conexoes={P[0]: CABO, P[1]: RADIO_SEM_PONTE}, familias={P[1]: PRO},
        primario=P[0])
    mesa.pads[P[1]] = mesa.daemon._coop_manager._players[P[1]].vpad = _pad(SONY)
    mesa.tipos[P[1]] = "tranco"
    mesa.evento(P[1], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    assert mesa.no[-1] == (P[1], 0, 255)
    _o_modo_cala(mesa, muda)
    mesa.correr(0.2, desde=0.06)
    assert mesa.no[-1] == (P[1], 0, 0)


@pytest.mark.parametrize("muda", [NATIVO, "jogo_fechou"])
def test_o_modo_que_cala_no_meio_do_padrao_zera_o_lado_do_pcm(
    muda: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    mesa = _Mesa(monkeypatch, conexoes={P[0]: CABO})
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    assert mesa.tocadores[P[0]].lados[-1] == (255, 0)
    _o_modo_cala(mesa, muda)
    mesa.correr(0.2, desde=0.06)
    assert mesa.tocadores[P[0]].lados[-1] == (0, 0)
    assert not mesa.backend.rumble


def test_o_zero_nao_vai_ao_report_que_o_padrao_nao_ligou(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No Steam Input o físico é da Steam: a ponte que cai no meio não vira escrita no report."""
    mesa = _Mesa(monkeypatch, chip=STEAM, conexoes={P[0]: RADIO_COM_PONTE})
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    assert mesa.tocadores[P[0]].lados[-1] == (255, 0)
    mesa.alto._pontes.pop(P[0])
    mesa.correr(0.2, desde=0.06)
    assert not mesa.motor.pendentes
    assert not mesa.backend.rumble


def test_a_forca_do_controle_multiplica_no_report(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad

    monkeypatch.setattr(gamepad, "_game_rumble_mult", lambda _d, _t, _u: 0.5)
    monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: False)
    mesa = _Mesa(monkeypatch, conexoes={P[0]: RADIO_SEM_PONTE})
    monkeypatch.setattr(tv, "_barras_dos_motores", lambda _d, _u: (50, 100))
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    assert mesa.backend.rumble[-1] == (P[0], 0, round(255 * 0.5 * 0.5))


def test_na_economia_a_forca_nao_conta_duas_vezes(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad

    monkeypatch.setattr(gamepad, "_game_rumble_mult", lambda _d, _t, _u: 0.3)
    monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: True)
    mesa = _Mesa(monkeypatch, conexoes={P[0]: RADIO_SEM_PONTE})
    mesa.atuador._forca_de = lambda _u: tv.FORCA_NA_ECONOMIA
    mesa.tipos[P[0]] = "tranco"
    mesa.evento(P[0], tv.LADO_ESQUERDO)
    mesa.correr(0.05)
    assert mesa.backend.rumble[-1] == (P[0], 0, round(255 * tv.FORCA_NA_ECONOMIA))


def test_o_zl_digital_do_pro_chega_ao_evento_do_dedo() -> None:
    """A síntese de ``BTN_TL2`` vira ``l2_raw``, e a borda do dedo o vê como L2."""
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

    leitor = EvdevReader.__new__(EvdevReader)
    leitor._snapshot = SimpleNamespace(l2_raw=0, r2_raw=0)
    leitor._sintetizar_l2 = leitor._sintetizar_r2 = True
    leitor._with = lambda **k: SimpleNamespace(**{**vars(leitor._snapshot), **k})
    leitor._sintetizar_gatilho("l2_btn", 1)
    jogador = SimpleNamespace(
        reader=SimpleNamespace(snapshot=lambda: leitor._snapshot), vpad=None,
        motion_reader=None, externo=True)
    daemon = SimpleNamespace(_coop_manager=SimpleNamespace(_players={P[1]: jogador}))
    [controle] = tv.controles_do_daemon(daemon)
    [evento] = tv.BordaDoDedo().ver(controle.uniq, controle.l2, controle.r2, 0.0)
    assert (evento.tipo, evento.lado, evento.uniq) == (tv.TIPO_DEDO, tv.LADO_ESQUERDO, P[1])


OPCOES = (*(e.chave for e in ESTILOS), "personalizado", None)
CHIPS = (SONY, XBOX, NINTENDO, STEAM, NAVEGACAO, NATIVO)
CONEXOES = (CABO, RADIO_COM_PONTE, RADIO_SEM_PONTE)
FAMILIAS = (DUALSENSE, EDGE, PRO, OITO_BITDO)
JOGOS = (CALADO, RUMBLE, ENDPOINT)
LADOS = (tv.LADO_ESQUERDO, tv.LADO_DIREITO)
EIXOS = (OPCOES, CHIPS, CONEXOES, FAMILIAS, TIPOS, JOGOS, LADOS)


def _casos_por_pares() -> list[tuple[Any, ...]]:
    """Todo par de valores de todo par de eixos, num conjunto pequeno de casos."""
    faltam = {
        (i, a, j, b)
        for (i, xs), (j, ys) in combinations(enumerate(EIXOS), 2)
        for a, b in product(xs, ys)
    }
    casos: list[tuple[Any, ...]] = []
    while faltam:
        i, a, j, b = next(iter(sorted(faltam, key=str)))
        caso: list[Any] = [eixo[0] for eixo in EIXOS]
        caso[i], caso[j] = a, b
        for k, eixo in enumerate(EIXOS):
            if k in (i, j):
                continue
            caso[k] = max(eixo, key=lambda v: sum(
                (min(k, m), v if k < m else caso[m], max(k, m), caso[m] if k < m else v) in faltam
                for m in range(len(EIXOS)) if m != k))
        tupla = tuple(caso)
        faltam -= {
            (m, tupla[m], n, tupla[n]) for m, n in combinations(range(len(EIXOS)), 2)
        }
        casos.append(tupla)
    return casos


CASOS = _casos_por_pares()


def _o_que_se_espera(
    estilo: str | None, chip: str, via: str, familia: str, tipo: str, jogo: str,
) -> tuple[str | None, bool]:
    """O padrão que vale e se ele sai: a tabela da sprint, escrita sem olhar o atuador."""
    padrao = pv.padrao_que_vale(tipo, estilo)
    if estilo == "nativo" or chip == NATIVO or padrao is None:
        return padrao, False
    de_fora = familia in (PRO, OITO_BITDO)
    audio = via != RADIO_SEM_PONTE and not de_fora
    if chip == STEAM and not audio:
        return padrao, False
    if not audio and jogo == RUMBLE and _pad(chip) is not None:
        return padrao, False
    return padrao, True


def test_a_regua_por_pares_e_pequena_e_cobre_todos_os_pares() -> None:
    assert len(CASOS) < 400
    for (i, xs), (j, ys) in combinations(enumerate(EIXOS), 2):
        vistos = {(c[i], c[j]) for c in CASOS}
        assert set(product(xs, ys)) <= vistos


@pytest.mark.parametrize(
    ("estilo", "chip", "via", "familia", "tipo", "jogo", "lado"), CASOS)
def test_todo_par_de_opcao_chip_conexao_familia_tipo_e_jogo(
    estilo: str | None, chip: str, via: str, familia: str, tipo: str, jogo: str, lado: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    alvo = P[1]
    mesa = _Mesa(
        monkeypatch, estilo=estilo, chip=chip, conexoes={P[0]: CABO, alvo: via},
        familias={alvo: familia}, jogo=jogo, primario=P[0])
    mesa.tipos[alvo] = tipo
    padrao, sai = _o_que_se_espera(estilo, chip, via, familia, tipo, jogo)
    regra = padrao is not None and pv.na_soltura_do_estilo(padrao, estilo)
    do_lado_do_som = padrao in pv.DO_LADO_DO_SOM
    if padrao in pv.NA_SOLTURA:
        mesa.evento(alvo, lado)
        mesa.correr(0.05)
        assert mesa.saidas(alvo) == [], "só toca ao soltar"
        mesa.evento(alvo, lado, tv.TIPO_SOLTA, 0.06)
        mesa.correr(3.0, desde=0.06)
    elif regra:
        mesa.evento(alvo, lado)
        mesa.correr(3.0)
        assert mesa.saidas(alvo) == []
        return
    elif do_lado_do_som:
        mesa.evento(alvo, lado, tv.TIPO_SOM)
        mesa.correr(3.0)
    else:
        mesa.evento(alvo, lado)
        mesa.correr(3.0)
    tocado = _tocou(mesa.saidas(alvo))
    if not sai:
        assert tocado == (False, False), "nada toca"
        return
    assert tocado == (lado == tv.LADO_ESQUERDO, lado == tv.LADO_DIREITO), "o lado certo"
    assert mesa.saidas(alvo)[-1] == (0, 0), "acaba em zero"
    assert mesa.saidas(P[0]) == [], "não vaza para o outro controle"


MESAS = (
    (CABO, CABO, CABO, CABO),
    (CABO, CABO, CABO, RADIO_COM_PONTE),
    (RADIO_SEM_PONTE, CABO, RADIO_COM_PONTE, CABO),
    (CABO, RADIO_COM_PONTE, RADIO_COM_PONTE, RADIO_SEM_PONTE),
    (RADIO_COM_PONTE, RADIO_SEM_PONTE, RADIO_COM_PONTE, RADIO_SEM_PONTE),
)
TIPOS_DA_MESA = ("tranco", "batida", "ressoar", "ricochete")


@pytest.mark.parametrize("mesa_de", MESAS)
@pytest.mark.parametrize(
    "presentes", [P, (P[2],), P[1:], (P[0], P[2]), (P[3], P[1])],
    ids=["os-quatro", "so-o-p3", "p1-ausente", "buraco", "ordem-trocada"])
def test_o_tipo_de_um_nao_vaza_para_outro(
    mesa_de: tuple[str, ...], presentes: tuple[str, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    conexoes = {u: mesa_de[P.index(u)] for u in presentes}
    mesa = _Mesa(monkeypatch, conexoes=conexoes)
    tipos = dict(zip(P, TIPOS_DA_MESA, strict=True))
    for uniq in presentes:
        mesa.tipos[uniq] = tipos[uniq]
        mesa.evento(uniq, tv.LADO_ESQUERDO if P.index(uniq) % 2 else tv.LADO_DIREITO)
    mesa.correr(3.0)
    for uniq in presentes:
        lado = pv.ESQUERDO if P.index(uniq) % 2 else pv.DIREITO
        valores = [e if lado == pv.ESQUERDO else d for e, d in mesa.saidas(uniq)]
        passos = [max(e, d) for _ms, e, d in pv.sequencia(tipos[uniq], lado)]
        assert valores == [v for i, v in enumerate(passos) if i == 0 or v != passos[i - 1]], (
            uniq, tipos[uniq])
