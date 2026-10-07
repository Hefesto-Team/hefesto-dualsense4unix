"""O-MODO-FREESTYLE-03 — o perfil de fora do jogo vale em todo caminho, e nasce ligado.

NOTA DATADA — 01/10/2026 (`D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`, a fala do usuário de
29/09): o Freestyle deixou de ser o perfil de fora do jogo. Desligado, ele não
vale em lugar nenhum; fora do jogo vale a escolha do usuário, que o boot restaura com
regra de janela ou sem (a RESTORE-ESCOPO-01 saiu). Os achados 1 e 2 abaixo
mudaram de propósito: o boot restaura a escolha do usuário, a máquina nova nasce com o
botão aceso (e é ali que o Freestyle vale no boot), e o rodapé sem perfil age na
escolha do usuário, e não no Freestyle. As réguas do contrato novo estão em
`test_o_hefesto_abre_na_escolha.py` e
`test_o_freestyle_desligado_nunca_e_o_perfil_ativo.py`; os achados 3 a 5 seguem.

A conferência da O-MODO-FREESTYLE-02 deixou cinco achados, e os cinco são do mesmo
dono: o perfil de fora do jogo. Esta régua os mede um a um; cada cura tem a sua
célula, e arrancá-la reprova aquela célula (a mordida está no docstring de cada
teste):

1. **o boot** com a sessão apontando um perfil de janela — e os outros caminhos em
   que o boot terminava sem perfil — vale o Freestyle enquanto o jogo não abre
   (`connection.restore_last_profile`);
2. **o Aplicar e o Exportar** sem perfil ativo caem no Freestyle, como o Salvar, pelo
   mesmo dono (`rodape.perfil_do_rodape`);
3. **o Freestyle de fábrica nasce com os gatilhos ligados**, e a fábrica nova só
   alcança a cópia de fábrica (`assets/profiles_default/freestyle.json`,
   `loader.o_freestyle_de_fabrica_nasce_ligado`);
4. **a dica do Salvar** segue o perfil ativo (`pacotes._dica_do_salvar`, `fim.html`);
5. **o diálogo do «Restaurar»** que dizia «Personalizado» — a régua dele é a
   `test_gui_review_fixes.py::test_restore_dialog_nao_cita_navegacao`.

A MATRIZ (regra, 23/09): os QUATRO controles — P1 e P3 no USB, P2 e P4 no BT —
no backend REAL (`PyDualSenseController`, handles de bancada sem aparelho nenhum
atrás), com o boot real, nos três caminhos da sessão: vazia, com um perfil de
janela, com o Freestyle. O gatilho se mede no BYTE do report de cada transporte
(0x02 no cabo, 0x31 no rádio), pelo mesmo envelope que a
`test_paridade_transporte_gatilhos.py` usa.

Os `uniq` são sintéticos (regra da casa: fixture usa faixa forjada).
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.trigger_effects import build_from_name, off
from hefesto_dualsense4unix.daemon import connection
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles import schema as esquema
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile
from hefesto_dualsense4unix.utils import session
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

from tests.conftest import EnvelopeDeTransporte, envelope_de

RAIZ = Path(__file__).resolve().parents[2]
FABRICA = RAIZ / "assets" / "profiles_default"
ASSET = FABRICA / "freestyle.json"

MESA: tuple[tuple[str, str], ...] = (
    ("AA:BB:CC:00:00:01", "usb"),
    ("AA:BB:CC:00:00:02", "bt"),
    ("AA:BB:CC:00:00:03", "usb"),
    ("AA:BB:CC:00:00:04", "bt"),
)

JANELA_DO_JOGO = "steam_app_1599660"
JOGO = "Sackboy"

CAMINHOS = ("sessao-vazia", "sessao-com-perfil-de-janela", "sessao-com-o-freestyle",
            "sessao-vazia-com-perfil-de-jogo")

OFFSETS_DO_GATILHO = {"right": (10, 11, 19), "left": (21, 22, 30)}


@pytest.fixture
def semeadura_ligada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liga a semeadura (o conftest a desliga) contra a FÁBRICA versionada."""
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", (FABRICA,))
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)


class _FioDeMentira:
    """O `device` de um handle de bancada: guarda o que seria escrito, e só."""

    def __init__(self) -> None:
        self.quadros: list[bytes] = []

    def write(self, quadro: bytes) -> int:
        self.quadros.append(bytes(quadro))
        return len(quadro)


def _mesa_de_quatro(
    fabrica_de_bancada: Any,
) -> tuple[PyDualSenseController, list[tuple[Any, EnvelopeDeTransporte]]]:
    """O backend REAL com os quatro handles de bancada, dois em cada transporte."""
    ctl = PyDualSenseController()
    pecas: list[tuple[Any, EnvelopeDeTransporte]] = []
    for mac, transporte in MESA:
        envelope = envelope_de(transporte)
        handle = fabrica_de_bancada(envelope)
        handle.device = _FioDeMentira()
        ctl._handles[mac] = handle
        pecas.append((handle, envelope))
    return ctl, pecas


async def _bloqueante(fn: Any, *args: Any) -> Any:
    return fn(*args)


def _boot(controle: Any, store: StateStore, *, nativo: bool = False) -> None:
    """O `restore_last_profile` de verdade, com o executor inline."""
    asyncio.run(connection.restore_last_profile(SimpleNamespace(  # type: ignore[arg-type]
        controller=controle, store=store, _run_blocking=_bloqueante,
        _native_mode=nativo)))


def _o_jogo_de_janela() -> None:
    loader.save_profile(Profile(name=JOGO,
                                match=MatchCriteria(window_class=[JANELA_DO_JOGO]),
                                priority=80))


def _prepara_a_sessao(caminho: str) -> None:
    """Deixa o disco no caminho pedido, e só então semeia."""
    if caminho != "sessao-vazia":
        _o_jogo_de_janela()
    if caminho == "sessao-com-perfil-de-janela":
        session.save_last_profile(JOGO)
        session.save_active_marker(JOGO)
    elif caminho == "sessao-com-o-freestyle":
        session.save_last_profile(loader.NOME_DO_PADRAO)
        session.save_active_marker(loader.NOME_DO_PADRAO)
    loader.load_all_profiles()


def _o_gatilho_no_fio(handle: Any, envelope: EnvelopeDeTransporte) -> dict[str, tuple[int, ...]]:
    """(modo, sete forças) de cada lado, lidos do report que o handle monta."""
    report = handle.prepareReport()
    assert envelope.problemas_do_envelope(report) == [], envelope.nome
    common = envelope.extrair_common(report)
    lidos: dict[str, tuple[int, ...]] = {}
    for lado, (modo, forcas, setima) in OFFSETS_DO_GATILHO.items():
        lidos[lado] = (common[modo], *common[forcas:forcas + 6], common[setima])
    return lidos


def _o_gatilho_de_nascimento() -> tuple[int, ...]:
    """O que o gatilho de nascimento do produto põe no fio — lido do DONO."""
    efeito = build_from_name(esquema.MODO_DE_NASCIMENTO_DO_GATILHO,
                             list(esquema.PARAMS_DE_NASCIMENTO_DO_GATILHO))
    return (int(efeito.mode), *efeito.forces)


VALE_NO_BOOT = {
    "sessao-vazia": (loader.NOME_DO_PADRAO, True),
    "sessao-com-perfil-de-janela": (JOGO, False),
    "sessao-com-o-freestyle": (None, False),
    "sessao-vazia-com-perfil-de-jogo": (None, False),
}


@pytest.mark.parametrize("caminho", CAMINHOS)
def test_o_boot_deixa_valendo_o_que_ela_escolheu_nos_quatro(
    semeadura_ligada: None, fabrica_de_bancada: Any, caminho: str,
) -> None:
    """Em cada caminho da sessão, vale o que o usuário escolheu, e o gatilho chega aos quatro."""
    _prepara_a_sessao(caminho)
    controle, pecas = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()
    store.set_freestyle_ligado(session.load_freestyle_ligado())

    _boot(controle, store)

    esperado_nome, aceso = VALE_NO_BOOT[caminho]
    assert (store.active_profile, store.freestyle_ligado) == (esperado_nome, aceso), (
        f"{caminho}: o boot terminou com {store.active_profile!r} valendo")
    if esperado_nome is None:
        assert all(h.device.quadros == [] for h, _ in pecas), "sem escolha, nada vai ao fio"
        return
    nascimento = _o_gatilho_de_nascimento()
    assert nascimento[0] != int(off().mode)
    no_fio = {f"{mac} ({transporte})": _o_gatilho_no_fio(handle, envelope)
              for (mac, transporte), (handle, envelope) in zip(MESA, pecas, strict=True)}
    esperado = {chave: {"right": nascimento, "left": nascimento} for chave in no_fio}
    assert no_fio == esperado, f"{caminho}: o gatilho que chegou ao fio"


def test_o_boot_nao_reescreve_a_escolha_dela(
    semeadura_ligada: None, fabrica_de_bancada: Any,
) -> None:
    """O boot restaura a escolha sem regravá-la: a sessão continua dizendo o jogo do usuário."""
    _prepara_a_sessao("sessao-com-perfil-de-janela")
    controle, _ = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()

    _boot(controle, store)

    import time

    assert (session.load_last_profile(), session.read_active_marker()) == (JOGO, JOGO)
    assert not store.manual_profile_lock_active(time.monotonic()), (
        "o boot armou a trava da troca à mão: ele virou escolha dela")


def test_com_o_modo_ligado_o_jogo_nao_entra_e_desligado_entra(
    semeadura_ligada: None, fabrica_de_bancada: Any,
) -> None:
    """A cena inteira: o botão aceso, nada o troca; apagado, o jogo entra."""
    _prepara_a_sessao("sessao-com-o-freestyle")
    controle, _ = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()
    _boot(controle, store)
    gerente = ProfileManager(controller=controle, store=store)

    gerente.activate(loader.NOME_DO_PADRAO, origin="manual")
    assert store.freestyle_ligado is True, "o «Ativar» do Freestyle liga o modo"
    vigia = AutoSwitcher(manager=gerente, window_reader=lambda: {}, store=store)

    for t in (0.0, 0.6, 30.0):
        vigia._tick({"wm_class": "firefox", "wm_name": "Mozilla Firefox"}, t)
    for t in (31.0, 31.6, 60.0):
        vigia._tick({"wm_class": JANELA_DO_JOGO, "wm_name": "Sackboy"}, t)
    assert store.active_profile == loader.NOME_DO_PADRAO

    gerente.apagar_o_freestyle(None)
    assert (store.active_profile, store.freestyle_ligado) == (None, False)
    for t in (61.0, 61.6):
        vigia._tick({"wm_class": JANELA_DO_JOGO, "wm_name": "Sackboy"}, t)
    assert store.active_profile == JOGO


@pytest.mark.parametrize("caminho", ["sessao-vazia", "sessao-com-o-freestyle"])
def test_o_boot_nao_entra_por_cima_do_jogo_que_ja_vale(
    semeadura_ligada: None, fabrica_de_bancada: Any, caminho: str,
) -> None:
    """O daemon reiniciado no meio da partida: o jogo já vale antes do controle chegar.

    O autoswitch roda antes do primeiro controle, e pode ter posto o Sackboy.
    O boot não troca isso pelo que o usuário escolheu — seria uma troca no meio do
    jogo, desfeita um tique depois pelo próprio autoswitch —, e não escreve nada
    no fio. Vale na máquina nova (o Freestyle aceso) e com «sem escolha».

    MORDIDA: tire de `restore_last_profile` o `if isinstance(ja_vale, str) and
    ja_vale and not mesmo_slug(...)` e a célula `sessao-vazia` reprova.
    """
    _prepara_a_sessao(caminho)
    controle, pecas = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()
    store.set_active_profile(JOGO)

    _boot(controle, store)

    assert store.active_profile == JOGO
    assert all(h.device.quadros == [] for h, _ in pecas)


def test_no_modo_nativo_o_boot_nao_aplica_perfil_nenhum(
    semeadura_ligada: None, fabrica_de_bancada: Any,
) -> None:
    """FEAT-NATIVE-MODE-01: o controle fica solto para o jogo, e a escolha não fura."""
    _prepara_a_sessao("sessao-com-perfil-de-janela")
    controle, pecas = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()

    _boot(controle, store, nativo=True)

    assert store.active_profile is None
    assert all(h.device.quadros == [] for h, _ in pecas)


class _PonteDoRodape:
    """A ponte dos gestos do rodapé, com os dois contratos reais e nada mais."""

    def __init__(self, salva: str | None = None) -> None:
        self.enviados: list[str] = []
        self.salvar_pedido: list[str] = []
        self._salva = salva

    def profile_reaplicar(self, nome: str) -> dict[str, Any]:
        self.enviados.append(nome)
        return {"active_profile": nome, "mode_aplicado": True, "secoes": {}}

    def salvar_arquivo(self, titulo: str, sugestao: str = "", **_: Any) -> str | None:
        self.salvar_pedido.append(sugestao)
        return self._salva

    def chamar(self, metodo: str, timeout: float | None = None, **params: Any) -> bool:
        return True

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        return {"status": "ok"}


def _ctx_sem_perfil() -> Any:
    """O daemon não diz quem está ativo, e a sessão está vazia."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    return Contexto(state={"connected": True, "active_profile": None},
                    mesa=[], conectados=[], estados={})


@pytest.mark.parametrize("gesto", ["aplicar", "salvar", "exportar"])
def test_os_tres_gestos_sem_perfil_ativo_agem_no_freestyle(
    semeadura_ligada: None, tmp_path: Path, gesto: str,
) -> None:
    """Sem perfil valendo, os três botões agem na escolha do usuário.

    Na máquina nova a escolha é o Freestyle aceso (a semeadura acende o botão,
    `D-2909-O-HEFESTO-ABRE-NA-ESCOLHA-DELA`, item 7), e a dica de cada um diz o
    mesmo nome. NOTA DATADA — 01/10/2026: até aqui o rodapé caía no Freestyle
    quando nada valia, com o botão apagado também; isso saiu (item 10), e a
    recusa de «sem escolha» é a de `test_o_freestyle_desligado_nunca_e_o_perfil_ativo.py`.

    MORDIDAS: devolva `perfil.nome_do_ativo(ctx.state)` à primeira linha do
    `aplicar` (ou do `exportar`) e a célula dele reprova; tire a migração da
    escolha da semeadura e as três reprovam.
    """
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import rodape

    loader.load_all_profiles()
    assert session.load_freestyle_ligado() is True, "a máquina nova nasce acesa"
    arquivo = profiles_dir() / loader.ARQUIVO_DO_PADRAO
    antes = arquivo.read_bytes()
    levado = tmp_path / "levado.json"
    ponte = _PonteDoRodape(salva=str(levado))
    ctx = _ctx_sem_perfil()

    getattr(rodape, gesto)(ctx, {}, ponte)

    if gesto == "aplicar":
        assert ponte.enviados == [loader.NOME_DO_PADRAO]
        assert arquivo.read_bytes() == antes, "o Aplicar não grava"
    elif gesto == "salvar":
        assert json.loads(arquivo.read_text(encoding="utf-8"))["name"] == "Freestyle"
        historico = profiles_dir() / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PADRAO
        assert [c.read_bytes() for c in sorted(historico.glob("*.json"))] == [antes]
    else:
        assert levado.read_bytes() == antes
        assert ponte.salvar_pedido[0].endswith(f"hefesto-{loader.ARQUIVO_DO_PADRAO}")
    dicas = pacotes.topo(ctx)
    assert "no perfil Freestyle" in dicas["rodape.salvar"]
    assert "o perfil Freestyle" in dicas["rodape.exportar"]


@pytest.mark.parametrize("gesto", ["aplicar", "salvar", "exportar"])
def test_sem_freestyle_no_disco_os_tres_recusam_dizendo(
    semeadura_ligada: None, tmp_path: Path, gesto: str,
) -> None:
    """Ela apagou o Freestyle: nenhum dos três inventa perfil, nem toca o disco."""
    from hefesto_dualsense4unix.interface.pacotes import rodape

    loader.load_all_profiles()
    (profiles_dir() / loader.ARQUIVO_DO_PADRAO).unlink()
    levado = tmp_path / "levado.json"
    ponte = _PonteDoRodape(salva=str(levado))

    with pytest.raises(ValueError, match="não há perfil ativo"):
        getattr(rodape, gesto)(_ctx_sem_perfil(), {}, ponte)

    assert ponte.enviados == [] and ponte.salvar_pedido == []
    assert not levado.exists()
    assert list(profiles_dir().glob("*.json")) == []


def _gatilhos(dados: dict[str, Any]) -> dict[str, Any]:
    return dados.get("triggers") or {}


def test_a_fabrica_do_freestyle_nasce_com_o_gatilho_de_nascimento_do_produto() -> None:
    """Os dois lados do asset trazem o gatilho de nascimento do DONO, escrito."""
    dados = json.loads(ASSET.read_text(encoding="utf-8"))
    esperado = {"mode": esquema.MODO_DE_NASCIMENTO_DO_GATILHO,
                "params": list(esquema.PARAMS_DE_NASCIMENTO_DO_GATILHO)}
    assert _gatilhos(dados) == {"left": esperado, "right": esperado}
    assert Profile.model_validate(dados).triggers.left.mode != "Off"


def test_a_lista_das_fabricas_de_antes_e_fechada() -> None:
    """Seis versões, e o asset de hoje fora dela."""
    antigas = loader._FABRICAS_ANTERIORES_DO_FREESTYLE
    hoje = json.loads(ASSET.read_text(encoding="utf-8"))
    assert hoje not in antigas
    assert len({json.dumps(v, sort_keys=True) for v in antigas}) == len(antigas) == 6
    nascimento = esquema.MODO_DE_NASCIMENTO_DO_GATILHO
    modos = [{lado: g["mode"] for lado, g in _gatilhos(v).items()} for v in antigas]
    assert modos == [{"left": "Off", "right": "Off"}] * 5 + [
        {"left": nascimento, "right": nascimento}]
    for versao in antigas:
        assert versao["name"] == loader.NOME_DO_PADRAO
        assert versao["match"] == {"type": "any"}
        Profile.model_validate(versao)


def _grava(pasta: Path, dados: dict[str, Any]) -> bytes:
    pasta.mkdir(parents=True, exist_ok=True)
    bruto = (json.dumps(dados, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (pasta / loader.ARQUIVO_DO_PADRAO).write_bytes(bruto)
    return bruto


def _copias(pasta: Path) -> list[bytes]:
    historico = pasta / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PADRAO
    return [c.read_bytes() for c in sorted(historico.glob("*.json"))]


@pytest.mark.parametrize("versao", range(6), ids=[  # (noqa-acento): nome de parâmetro
    "22-04-fe27e7b2a", "22-04-d08b5995d", "23-04-34503c512",
    "28-06-425429a7e", "20-07-c81846696", "24-09-o-modo-freestyle-03"])
def test_a_copia_de_fabrica_antiga_vira_a_de_hoje_e_tem_volta(
    semeadura_ligada: None, versao: int,
) -> None:
    """A cópia intocada de qualquer fábrica de antes nasce ligada na primeira carga."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava(pasta, loader._FABRICAS_ANTERIORES_DO_FREESTYLE[versao])
    (pasta / loader.SEED_MARKER_NAME).write_text("freestyle.json\n", encoding="utf-8")

    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]

    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == ASSET.read_bytes()
    assert _copias(pasta) == [bruto]
    assert loader.o_freestyle_de_fabrica_nasce_ligado() is None, "não é one-shot"

    loader.restaurar_do_historico(loader.SLUG_DO_PADRAO)
    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == bruto
    assert loader.o_freestyle_de_fabrica_nasce_ligado() is None, (
        "a volta que ela pediu foi desfeita pela migração")


@pytest.mark.parametrize("arquivo_antigo", ["meu_perfil.json", "personalizado.json"])
def test_a_fabrica_de_antes_com_o_nome_de_antes_chega_a_de_hoje_numa_carga(
    semeadura_ligada: None, arquivo_antigo: str,
) -> None:
    """A cadeia inteira: a cópia de fábrica ainda com o nome antigo, numa carga só."""
    pasta = profiles_dir(ensure=True)
    nome_antigo = "meu_perfil" if arquivo_antigo == "meu_perfil.json" else "Personalizado"
    velha = dict(loader._FABRICAS_ANTERIORES_DO_FREESTYLE[4], name=nome_antigo)
    (pasta / arquivo_antigo).write_text(json.dumps(velha, indent=2), encoding="utf-8")

    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]

    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == ASSET.read_bytes()
    assert not (pasta / arquivo_antigo).exists()


def _o_freestyle_dela() -> dict[str, Any]:
    """A fábrica de 24/09 com UM ajuste dela: a cor do P1 por controle."""
    dela = json.loads(json.dumps(loader._FABRICAS_ANTERIORES_DO_FREESTYLE[4]))
    dela["controllers"] = {"AA:BB:CC:00:00:01": {"leds": {"lightbar": [255, 0, 128]}}}
    return dela


def test_o_freestyle_dela_nao_muda(semeadura_ligada: None) -> None:
    """Um byte de ajuste dela e ele deixa de ser fábrica: nem arquivo, nem histórico."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava(pasta, _o_freestyle_dela())
    (pasta / loader.SEED_MARKER_NAME).write_text("freestyle.json\n", encoding="utf-8")

    loader.load_all_profiles()

    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == bruto
    assert _copias(pasta) == []


def test_sem_a_copia_no_historico_nada_muda_e_a_proxima_carga_tenta(
    semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ordem: sem os bytes antigos guardados, a fábrica nova não entra."""
    pasta = profiles_dir(ensure=True)
    bruto = _grava(pasta, loader._FABRICAS_ANTERIORES_DO_FREESTYLE[4])
    monkeypatch.setattr(loader, "_arquivar_versao", lambda *a, **k: None)

    assert loader.o_freestyle_de_fabrica_nasce_ligado() is None

    assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == bruto
    assert not (pasta / loader._FREESTYLE_DE_FABRICA_NASCE_LIGADO_MARKER).exists()


def test_o_personalizado_dela_vence_a_fabrica_de_antes_que_o_shell_copiou(
    semeadura_ligada: None,
) -> None:
    """O disco de quem atualizou em 24/09: o shell copiou a fábrica em Off ao lado dela."""
    pasta = profiles_dir(ensure=True)
    _grava(pasta, loader._FABRICAS_ANTERIORES_DO_FREESTYLE[4])
    dela = dict(_o_freestyle_dela(), name="Personalizado")
    (pasta / loader.ARQUIVO_DO_PERSONALIZADO).write_text(
        json.dumps(dela, ensure_ascii=False, indent=2), encoding="utf-8")

    assert [p.name for p in loader.load_all_profiles()] == ["Freestyle"]

    gravado = json.loads((pasta / loader.ARQUIVO_DO_PADRAO).read_text(encoding="utf-8"))
    assert gravado["controllers"] == dela["controllers"]
    assert not (pasta / loader.ARQUIVO_DO_PERSONALIZADO).exists()


def _install_profiles(home: Path) -> subprocess.CompletedProcess[str]:
    """O `scripts/install_profiles.sh` de VERDADE, num HOME de mentira."""
    return subprocess.run(
        ["bash", str(RAIZ / "scripts" / "install_profiles.sh"), str(RAIZ)],
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        capture_output=True, text=True, check=False, timeout=60,
    )


@pytest.mark.parametrize("disco", ["maquina-nova", "fabrica-de-antes", "o-dela"])
def test_o_que_o_install_faz_num_disco_que_ja_tem_o_freestyle(
    tmp_path: Path, semeadura_ligada: None, monkeypatch: pytest.MonkeyPatch, disco: str,
) -> None:
    """A MEDIDA QUE A SPRINT PEDIU: o install só copia o ausente, e a fábrica anda pelo Python."""
    home = tmp_path / "home"
    pasta = home / ".config" / "hefesto-dualsense4unix" / "profiles"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    assert profiles_dir() == pasta
    bruto = b""
    if disco != "maquina-nova":
        dados = (loader._FABRICAS_ANTERIORES_DO_FREESTYLE[4] if disco == "fabrica-de-antes"
                 else _o_freestyle_dela())
        bruto = _grava(pasta, dados)
        (pasta / loader.SEED_MARKER_NAME).write_text("freestyle.json\n", encoding="utf-8")

    feito = _install_profiles(home)

    assert feito.returncode == 0, feito.stderr
    depois_do_shell = (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes()
    assert depois_do_shell == (ASSET.read_bytes() if disco == "maquina-nova" else bruto)

    loader.load_all_profiles()

    final = (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes()
    assert final == (bruto if disco == "o-dela" else ASSET.read_bytes())


def _ctx(nome: str) -> Any:
    return SimpleNamespace(state={"active_profile": nome}, mesa=[])


def _um_perfil(nome: str, match: dict[str, Any]) -> None:
    pasta = profiles_dir(ensure=True)
    (pasta / f"{nome.lower()}.json").write_text(json.dumps(
        {"name": nome, "version": 1, "priority": 10, "match": match}), encoding="utf-8")


PROMETE_O_JOGO = "este jogo abrir"


@pytest.mark.parametrize(("match", "de_jogo"), [
    ({"type": "criteria", "window_class": [JANELA_DO_JOGO]}, True),
    ({"type": "criteria", "process_name": ["sackboy.exe"]}, True),
    ({"type": "criteria", "window_title_regex": "Sackboy"}, True),
    ({"type": "any"}, False),
    ({"type": "manual"}, False),
    ({"type": "criteria"}, False),
], ids=["janela", "processo", "titulo", "todos", "manual", "criteria-vazio"])
def test_a_dica_do_salvar_so_promete_o_jogo_a_perfil_de_jogo(
    match: dict[str, Any], de_jogo: bool,
) -> None:
    """Achado 4: *"volta sozinho toda vez que este jogo abrir"* só vale com regra de jogo."""
    from hefesto_dualsense4unix.interface import pacotes

    _um_perfil("Alvo", match)
    dica = pacotes.topo(_ctx("Alvo"))["rodape.salvar"]

    assert dica.startswith("Grava no perfil Alvo. É onde a mudança vai cair: "), dica
    assert (PROMETE_O_JOGO in dica) is de_jogo, dica
    assert "\n" not in dica and len(dica) <= 120, "curta"


def test_a_dica_do_freestyle_diz_onde_ele_vale(semeadura_ligada: None) -> None:
    """O achado da conferência, com o Freestyle de verdade e sem perfil ativo."""
    from hefesto_dualsense4unix.interface import pacotes

    loader.load_all_profiles()
    dica = pacotes.topo(_ctx(""))["rodape.salvar"]

    assert dica.startswith("Grava no perfil Freestyle. É onde a mudança vai cair: ")
    assert PROMETE_O_JOGO not in dica
    assert "fora do jogo" in dica


def test_perfil_que_nao_se_le_nao_ganha_promessa() -> None:
    """O nome que o daemon diz e o disco não tem: grava, e é onde cai — e só."""
    from hefesto_dualsense4unix.interface import pacotes

    dica = pacotes.topo(_ctx("Fantasma"))["rodape.salvar"]

    assert dica.startswith("Grava no perfil Fantasma. ")
    assert dica.endswith("É onde a mudança vai cair."), dica


def _o_titulo_do_salvar(html: str) -> str:
    achado = re.search(r'<button class="r-salvar"[^>]*?title="([^"]*)"', html, re.S)
    assert achado, "o botão do Salvar sumiu do rodapé"
    return achado.group(1)


def test_o_rodape_congelado_diz_o_mesmo_que_a_tela_pinta_sem_perfil() -> None:
    """O `fim.html` e a pintura sem perfil dizem a MESMA frase, e ela não promete jogo."""
    from hefesto_dualsense4unix.interface import onde, pacotes

    congelado = _o_titulo_do_salvar((onde.AQUI / "fim.html").read_text(encoding="utf-8"))

    assert congelado == pacotes._dica_do_salvar("")
    assert PROMETE_O_JOGO not in congelado


DEZ = [f"{n:02d}-" for n in range(1, 11)]


@pytest.mark.parametrize("pagina", DEZ)  # (noqa-acento): nome de parâmetro
def test_a_bancada_das_dez_traz_o_rodape_novo(pagina: str) -> None:
    """O desenho de HOJE das dez abas: o rodapé regerado, sem a promessa do jogo."""
    from hefesto_dualsense4unix.interface import onde

    caminhos = sorted(onde.saida().glob(f"{pagina}*.html"))
    if not caminhos:
        pytest.skip(f"não há página na bancada para {pagina}")
    congelado = _o_titulo_do_salvar((onde.AQUI / "fim.html").read_text(encoding="utf-8"))

    assert _o_titulo_do_salvar(caminhos[0].read_text(encoding="utf-8")) == congelado
