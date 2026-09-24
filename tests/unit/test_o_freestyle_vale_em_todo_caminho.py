"""O-MODO-FREESTYLE-03 — o perfil de fora do jogo vale em todo caminho, e nasce ligado.

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

A MATRIZ (regra dela, 23/09): os QUATRO controles — P1 e P3 no USB, P2 e P4 no BT —
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

#: A mesa dela: P1 e P3 no cabo, P2 e P4 no rádio — nunca só o P1, nunca um lado só.
MESA: tuple[tuple[str, str], ...] = (
    ("AA:BB:CC:00:00:01", "usb"),
    ("AA:BB:CC:00:00:02", "bt"),
    ("AA:BB:CC:00:00:03", "usb"),
    ("AA:BB:CC:00:00:04", "bt"),
)

#: O perfil de um jogo, com a regra de janela que o faz ser PULADO no boot
#: (RESTORE-ESCOPO-01). `steam_app_1599660` é o Sackboy na Steam.
JANELA_DO_JOGO = "steam_app_1599660"
JOGO = "Sackboy"

#: Os três caminhos da sessão que a sprint nomeia.
CAMINHOS = ("sessao-vazia", "sessao-com-perfil-de-janela", "sessao-com-o-freestyle")

#: Offsets do bloco de gatilho DENTRO do common: (modo, primeira das seis forças,
#: a sétima avulsa). Os mesmos da `test_paridade_transporte_gatilhos.py`.
OFFSETS_DO_GATILHO = {"right": (10, 11, 19), "left": (21, 22, 30)}


@pytest.fixture
def semeadura_ligada(monkeypatch: pytest.MonkeyPatch) -> None:
    """Liga a semeadura (o conftest a desliga) contra a FÁBRICA versionada."""
    monkeypatch.delenv(loader.SEED_SKIP_ENV_VAR, raising=False)
    monkeypatch.setattr(loader, "_seed_attempted", False)
    monkeypatch.setattr(loader, "_DEFAULT_SEED_SOURCE_DIRS", (FABRICA,))
    # O censo dos jogos não é assunto desta régua, e a máquina de quem roda a
    # suíte não pode decidir o resultado.
    monkeypatch.setattr(loader, "_talvez_semear_jogos", lambda: None)


class _FioDeMentira:
    """O `device` de um handle de bancada: guarda o que seria escrito, e só.

    A rota de luz do rádio escreve AVULSO pelo `writeReport` do handle
    (`_pintar_por_hidraw_bt`). Sem aparelho nenhum atrás, o fio responde que
    escreveu tudo — nunca um nó de verdade.
    """

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
    """Deixa o disco no caminho pedido. A semeadura já pôs o Freestyle lá."""
    loader.load_all_profiles()
    _o_jogo_de_janela()
    if caminho == "sessao-com-perfil-de-janela":
        session.save_last_profile(JOGO)
        session.save_active_marker(JOGO)
    elif caminho == "sessao-com-o-freestyle":
        session.save_last_profile(loader.NOME_DO_PADRAO)
        session.save_active_marker(loader.NOME_DO_PADRAO)


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


def _o_estado_do_boot(store: StateStore) -> tuple[str | None, str | None]:
    """O par que diz a verdade inteira (PERFIL-ADIADO-POR-JANELA-01)."""
    return store.active_profile, store.perfil_adiado_por_janela


# =============================================================================
# 1 e 3. O BOOT — os quatro controles, USB e BT, nos três caminhos
# =============================================================================

@pytest.mark.parametrize("caminho", CAMINHOS)
def test_o_boot_deixa_o_freestyle_valendo_nos_quatro_com_os_gatilhos_ligados(
    semeadura_ligada: None, fabrica_de_bancada: Any, caminho: str,
) -> None:
    """Em cada caminho da sessão, o Freestyle vale, e o gatilho chega RÍGIDO aos quatro.

    O caminho do perfil de janela é o achado 1: o boot o pula de propósito e,
    até esta sprint, ficava sem perfil até o jogo abrir — com o Modo Freestyle
    ligado (a trava da cena), sem troca nenhuma por janela comum.

    MORDIDAS:
    - tire o `_o_de_fora_do_jogo_enquanto_espera` do ramo `if pulado:` de
      `restore_last_profile` e a célula `sessao-com-perfil-de-janela` reprova
      com `active_profile` vazio;
    - devolva `"mode": "Off"` aos gatilhos do `freestyle.json` de fábrica e as
      três células reprovam no byte, nos quatro controles e nos dois transportes.
    """
    _prepara_a_sessao(caminho)
    controle, pecas = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()
    store.set_autoswitch_locked(True)

    _boot(controle, store)

    assert store.active_profile == loader.NOME_DO_PADRAO, (
        f"{caminho}: o boot terminou com {store.active_profile!r} valendo")
    nascimento = _o_gatilho_de_nascimento()
    assert nascimento[0] != int(off().mode)
    no_fio = {f"{mac} ({transporte})": _o_gatilho_no_fio(handle, envelope)
              for (mac, transporte), (handle, envelope) in zip(MESA, pecas, strict=True)}
    esperado = {chave: {"right": nascimento, "left": nascimento} for chave in no_fio}
    assert no_fio == esperado, f"{caminho}: o gatilho que chegou ao fio"


@pytest.mark.parametrize("sessao", [  # (noqa-acento): nome de parâmetro
    ("Apagado", "Apagado"),   # a sessão e o marcador apontam um perfil que ela apagou
    ("Sumido", "Apagado"),    # os dois divergem, e nenhum dos dois existe
    (JOGO, "Apagado"),        # o marcador órfão, e o session.json num perfil de janela
], ids=["os-dois-orfaos", "orfaos-diferentes", "marcador-orfao-e-sessao-de-janela"])
def test_a_sessao_que_nao_ativa_tambem_cai_no_freestyle(
    semeadura_ligada: None, fabrica_de_bancada: Any, sessao: tuple[str, str],
) -> None:
    """Os outros caminhos em que o boot terminava sem perfil: o nome não ativa.

    O marcador vence a divergência (`resolve_boot_profile`); quando ele não
    ativa, o boot cai no `session.json`; e quando nem este ativa — órfão, ou de
    janela —, até esta sprint o boot terminava sem perfil.

    MORDIDA: tire a última linha de `restore_last_profile`
    (`await _o_de_fora_do_jogo_enquanto_espera(tentados, motivo)`) e as três
    células reprovam.
    """
    ultimo, marcador = sessao
    _prepara_a_sessao("sessao-vazia")
    session.save_last_profile(ultimo)
    session.save_active_marker(marcador)
    controle, _ = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()

    _boot(controle, store)

    assert store.active_profile == loader.NOME_DO_PADRAO


def test_o_boot_nao_reescreve_a_escolha_dela(
    semeadura_ligada: None, fabrica_de_bancada: Any,
) -> None:
    """O Freestyle vale ENQUANTO espera: a sessão continua dizendo o jogo dela.

    Se o boot gravasse o Freestyle na sessão, o próximo boot não esperaria mais
    o Sackboy — a escolha dela sumiria por um reinício. `origin="system"` é o
    que segura: o marcador e o `session.json` só mudam por gesto manual.

    MORDIDA: troque o `origin="system"` de `_ativar` por `origin="manual"` e a
    sessão passa a dizer Freestyle.
    """
    _prepara_a_sessao("sessao-com-perfil-de-janela")
    controle, _ = _mesa_de_quatro(fabrica_de_bancada)

    _boot(controle, StateStore())

    assert (session.load_last_profile(), session.read_active_marker()) == (JOGO, JOGO)


def test_a_espera_do_perfil_de_janela_segue_o_contrato_dela(
    semeadura_ligada: None, fabrica_de_bancada: Any,
) -> None:
    """PERFIL-ADIADO-POR-JANELA-01: a espera só tem valor com `active_profile` vazio.

    A MEDIDA ANTES DE MEXER (a sprint pediu): nenhum leitor de tela lê a espera —
    ela não sai no `daemon.state_full` e nenhum pacote a pergunta. A tela diz o
    perfil pelo dono (`perfil.nome_do_ativo`): o daemon, depois o disco. Com o
    daemon calado ela lia o disco e dizia **Sackboy** sobre um controle sem perfil
    nenhum aplicado; com a cura o daemon diz Freestyle, que é o que está valendo.

    Os dois lados do contrato:
    - com o Freestyle no disco, o par é `("Freestyle", None)` — entrou;
    - sem ele (ela o apagou), o par é o de antes desta sprint, `(None, "Sackboy")`.

    MORDIDA: a mesma da primeira célula da matriz, e a primeira metade reprova.
    """
    from hefesto_dualsense4unix.interface import pacotes

    _prepara_a_sessao("sessao-com-perfil-de-janela")
    controle, _ = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()
    _boot(controle, store)
    assert _o_estado_do_boot(store) == (loader.NOME_DO_PADRAO, None)
    ctx = SimpleNamespace(state={"active_profile": store.active_profile}, mesa=[])
    assert pacotes.topo(ctx)["perfil"] == loader.NOME_DO_PADRAO

    (profiles_dir() / loader.ARQUIVO_DO_PADRAO).unlink()
    store = StateStore()
    _boot(controle, store)
    assert _o_estado_do_boot(store) == (None, JOGO)


def test_o_jogo_entra_por_cima_do_freestyle_com_o_modo_ligado(
    semeadura_ligada: None, fabrica_de_bancada: Any,
) -> None:
    """A cena inteira: o boot deixa o Freestyle, e o jogo que abre entra por cima.

    `D-2409-COM-O-FREESTYLE-O-JOGO-ENTRA-POR-CIMA` (LOCK-CEDE-01): com o Modo
    Freestyle ligado, a janela comum não troca o perfil — e a do jogo com perfil
    próprio troca. É o autoswitch real, com o `ProfileManager` real.

    MORDIDA: a mesma da primeira célula da matriz — sem o Freestyle no boot, a
    janela comum não tem perfil nenhum a segurar.
    """
    _prepara_a_sessao("sessao-com-perfil-de-janela")
    controle, _ = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()
    store.set_autoswitch_locked(True)
    _boot(controle, store)
    vigia = AutoSwitcher(manager=ProfileManager(controller=controle, store=store),
                         window_reader=lambda: {}, store=store)

    for t in (0.0, 0.6, 30.0):
        vigia._tick({"wm_class": "firefox", "wm_name": "Mozilla Firefox"}, t)
    assert store.active_profile == loader.NOME_DO_PADRAO

    for t in (31.0, 31.6):
        vigia._tick({"wm_class": JANELA_DO_JOGO, "wm_name": "Sackboy"}, t)
    assert _o_estado_do_boot(store) == (JOGO, None)


def test_o_freestyle_nao_entra_por_cima_do_jogo_que_ja_vale(
    semeadura_ligada: None, fabrica_de_bancada: Any,
) -> None:
    """O daemon reiniciado no meio da partida: o jogo já vale antes do controle chegar.

    O autoswitch roda antes do primeiro controle, e pode ter posto o Sackboy.
    O boot não troca isso pelo Freestyle — seria uma troca no meio do jogo,
    desfeita um tique depois pelo próprio autoswitch —, e não escreve nada no fio.

    MORDIDA: tire o `if isinstance(ja_vale, str) and ja_vale:` de
    `_o_de_fora_do_jogo_enquanto_espera` e o Freestyle entra por cima.
    """
    _prepara_a_sessao("sessao-com-perfil-de-janela")
    controle, pecas = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()
    store.set_active_profile(JOGO)

    _boot(controle, store)

    assert store.active_profile == JOGO
    assert all(h.device.quadros == [] for h, _ in pecas)


def test_o_freestyle_com_regra_de_janela_dela_espera_como_os_outros(
    semeadura_ligada: None, fabrica_de_bancada: Any,
) -> None:
    """Se ELA pôs no Freestyle uma regra de janela, ele é de janela também.

    A regra de cima (RESTORE-ESCOPO-01) vale para ele: o boot não o força sem a
    janela. O par volta a ser o de antes: sem perfil, esperando o Sackboy.

    MORDIDA: tire o `if _escopado_a_janela(fora_do_jogo): return` de
    `_o_de_fora_do_jogo_enquanto_espera` e o boot força o Freestyle dela.
    """
    _prepara_a_sessao("sessao-com-perfil-de-janela")
    arquivo = profiles_dir() / loader.ARQUIVO_DO_PADRAO
    dela = json.loads(arquivo.read_text(encoding="utf-8"))
    dela["match"] = {"type": "criteria", "window_class": ["firefox"]}
    arquivo.write_text(json.dumps(dela, indent=2), encoding="utf-8")
    controle, _ = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()

    _boot(controle, store)

    assert _o_estado_do_boot(store) == (None, JOGO)


def test_no_modo_nativo_o_boot_nao_aplica_perfil_nenhum(
    semeadura_ligada: None, fabrica_de_bancada: Any,
) -> None:
    """FEAT-NATIVE-MODE-01: o controle fica solto para o jogo, e o Freestyle não fura."""
    _prepara_a_sessao("sessao-com-perfil-de-janela")
    controle, pecas = _mesa_de_quatro(fabrica_de_bancada)
    store = StateStore()

    _boot(controle, store, nativo=True)

    assert _o_estado_do_boot(store) == (None, None)
    assert all(h.device.quadros == [] for h, _ in pecas)


# =============================================================================
# 2. O RODAPÉ — os três gestos perguntam ao mesmo dono
# =============================================================================

class _PonteDoRodape:
    """A ponte dos gestos do rodapé, com os dois contratos reais e nada mais.

    `apply_draft_detalhado` devolve o dicionário que o daemon devolve
    (`ipc_bridge.apply_draft_detalhado`), e `salvar_arquivo` o caminho que ela
    escolheu (`ponte.salvar_arquivo`, que o piloto substitui). Não há
    `__getattr__` que responda a qualquer coisa: um gesto que chame outro
    método reprova aqui, como reprovaria na janela.
    """

    def __init__(self, salva: str | None = None) -> None:
        self.enviados: list[dict[str, Any]] = []
        self.salvar_pedido: list[str] = []
        self._salva = salva

    def apply_draft_detalhado(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.enviados.append(payload)
        return {"status": "ok", "applied": sorted(payload), "failed": {}}

    def salvar_arquivo(self, titulo: str, sugestao: str = "", **_: Any) -> str | None:
        self.salvar_pedido.append(sugestao)
        return self._salva


def _ctx_sem_perfil() -> Any:
    """O daemon não diz quem está ativo, e a sessão está vazia."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    return Contexto(state={"connected": True, "active_profile": None},
                    mesa=[], conectados=[], estados={})


def _o_draft_do_freestyle() -> dict[str, Any]:
    from hefesto_dualsense4unix.app.draft_config import DraftConfig

    return dict(DraftConfig.from_profile(
        loader.load_profile(loader.NOME_DO_PADRAO)).to_ipc_dict())


@pytest.mark.parametrize("gesto", ["aplicar", "salvar", "exportar"])
def test_os_tres_gestos_sem_perfil_ativo_agem_no_freestyle(
    semeadura_ligada: None, tmp_path: Path, gesto: str,
) -> None:
    """Sem perfil valendo, os três botões agem onde o boot restauraria.

    Antes desta sprint o Salvar gravava no Freestyle (O-MODO-FREESTYLE-02) e o
    Aplicar e o Exportar recusavam — *"não há perfil ativo"* — com o Freestyle no
    disco. A dica de cada um diz o mesmo nome.

    MORDIDAS: devolva `perfil.nome_do_ativo(ctx.state)` à primeira linha do
    `aplicar` (ou do `exportar`) e a célula dele reprova; tire o
    `o_perfil_de_fora_do_jogo()` de `perfil_do_rodape` e as três reprovam.
    """
    from hefesto_dualsense4unix.interface import pacotes
    from hefesto_dualsense4unix.interface.pacotes import rodape

    loader.load_all_profiles()
    arquivo = profiles_dir() / loader.ARQUIVO_DO_PADRAO
    antes = arquivo.read_bytes()
    levado = tmp_path / "levado.json"
    ponte = _PonteDoRodape(salva=str(levado))
    ctx = _ctx_sem_perfil()

    getattr(rodape, gesto)(ctx, {}, ponte)

    if gesto == "aplicar":
        assert ponte.enviados == [_o_draft_do_freestyle()]
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


# =============================================================================
# 3. A FÁBRICA — nasce ligada, e só alcança a cópia de fábrica
# =============================================================================

def _gatilhos(dados: dict[str, Any]) -> dict[str, Any]:
    return dados.get("triggers") or {}


def test_a_fabrica_do_freestyle_nasce_com_o_gatilho_de_nascimento_do_produto() -> None:
    """Os dois lados do asset trazem o gatilho de nascimento do DONO, escrito.

    ESCRITO, e não ausente: um perfil sem a seção é lido pela aba Gatilhos como
    «Desligado» (`a03_gatilhos._do_lado`). E pelo DONO: se o padrão do produto
    mudar, esta régua pede o asset junto — e a lista das fábricas de antes ganha
    a versão que sai.
    """
    dados = json.loads(ASSET.read_text(encoding="utf-8"))
    esperado = {"mode": esquema.MODO_DE_NASCIMENTO_DO_GATILHO,
                "params": list(esquema.PARAMS_DE_NASCIMENTO_DO_GATILHO)}
    assert _gatilhos(dados) == {"left": esperado, "right": esperado}
    assert Profile.model_validate(dados).triggers.left.mode != "Off"


def test_a_lista_das_fabricas_de_antes_e_fechada() -> None:
    """Cinco versões, todas com os gatilhos em Off, e o asset de hoje fora dela.

    Com o asset de hoje dentro, a migração o trocaria por ele mesmo a cada
    disco novo e guardaria no histórico um arquivo que ninguém escreveu.
    """
    antigas = loader._FABRICAS_ANTERIORES_DO_FREESTYLE
    hoje = json.loads(ASSET.read_text(encoding="utf-8"))
    assert hoje not in antigas
    assert len({json.dumps(v, sort_keys=True) for v in antigas}) == len(antigas) == 5
    for versao in antigas:
        assert versao["name"] == loader.NOME_DO_PADRAO
        assert versao["match"] == {"type": "any"}
        assert {lado: g["mode"] for lado, g in _gatilhos(versao).items()} == {
            "left": "Off", "right": "Off"}
        Profile.model_validate(versao)


def _grava(pasta: Path, dados: dict[str, Any]) -> bytes:
    pasta.mkdir(parents=True, exist_ok=True)
    bruto = (json.dumps(dados, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (pasta / loader.ARQUIVO_DO_PADRAO).write_bytes(bruto)
    return bruto


def _copias(pasta: Path) -> list[bytes]:
    historico = pasta / loader.HISTORICO_DIR_NAME / loader.SLUG_DO_PADRAO
    return [c.read_bytes() for c in sorted(historico.glob("*.json"))]


@pytest.mark.parametrize("versao", range(5), ids=[  # (noqa-acento): nome de parâmetro
    "22-04-974c55869", "22-04-c2bd10f8e", "23-04-099e4f839",
    "28-06-00eb5eeb9", "20-07-4a9bb696e"])
def test_a_copia_de_fabrica_antiga_vira_a_de_hoje_e_tem_volta(
    semeadura_ligada: None, versao: int,
) -> None:
    """A cópia intocada de qualquer fábrica de antes nasce ligada na primeira carga.

    Os bytes antigos vão ao `.historico` ANTES da escrita, e o «restaurar do
    histórico» os devolve; a marca faz a segunda carga não fazer nada.

    MORDIDA: tire a chamada `o_freestyle_de_fabrica_nasce_ligado()` de
    `_maybe_seed_presets` e as cinco células reprovam com os gatilhos em Off.
    """
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
    """A cadeia inteira: a cópia de fábrica ainda com o nome antigo, numa carga só.

    As duas renomeações trocam o nome e mais nada; a fábrica nova vem DEPOIS
    delas no `_maybe_seed_presets`, e por isso alcança o que elas acabaram de
    renomear — a máquina de quem nunca mexeu no padrão sai com o gatilho ligado.
    """
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
    """Um byte de ajuste dela e ele deixa de ser fábrica: nem arquivo, nem histórico.

    MORDIDA: troque o `if dados not in _FABRICAS_ANTERIORES_DO_FREESTYLE` de
    `_levar_a_fabrica_nova` por `if False` e o disco dela vira o asset.
    """
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
    """O disco de quem atualizou em 24/09: o shell copiou a fábrica em Off ao lado dela.

    A renomeação da O-MODO-FREESTYLE-02 só cede o lugar a uma FÁBRICA; com o
    asset mudado, a de antes tem de continuar sendo fábrica — senão ficariam dois
    padrões, e o dela não viraria Freestyle.
    """
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
    """A MEDIDA QUE A SPRINT PEDIU: o install só copia o ausente, e a fábrica anda pelo Python.

    - máquina nova: o shell copia o asset de hoje, ligado;
    - a fábrica de antes (o shell de 24/09 já a copiou e registrou): o shell não
      toca, e a primeira carga do Python a leva ao asset de hoje;
    - o Freestyle dela: nem o shell nem o Python mudam um byte.
    """
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


# =============================================================================
# 4. A DICA DO SALVAR — segue o perfil ativo, curta e sem recado
# =============================================================================

def _ctx(nome: str) -> Any:
    return SimpleNamespace(state={"active_profile": nome}, mesa=[])


def _um_perfil(nome: str, match: dict[str, Any]) -> None:
    pasta = profiles_dir(ensure=True)
    (pasta / f"{nome.lower()}.json").write_text(json.dumps(
        {"name": nome, "version": 1, "priority": 10, "match": match}), encoding="utf-8")


#: O que a promessa de cada tipo NÃO pode dizer. Medir a ausência da frase falsa
#: é o que protege a cura; o texto de cada uma é do dono (`pacotes._QUANDO_VOLTA`).
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
    """Achado 4: *"volta sozinho toda vez que este jogo abrir"* só vale com regra de jogo.

    O `criteria` sem nenhum dos três campos nunca entra sozinho (é o `manual`
    escrito por acidente), e promete o que o manual promete.

    MORDIDA: faça `_tipo_do_perfil` devolver sempre `"jogo"` e as três células
    sem regra de jogo reprovam.
    """
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
    """O `fim.html` e a pintura sem perfil dizem a MESMA frase, e ela não promete jogo.

    É a regra do `_SEM_PERFIL`: a tela antes e depois da pintura diz a mesma
    coisa. O congelado prometia o jogo a qualquer perfil.

    MORDIDA: devolva ao `title` do `.r-salvar` no `fim.html` a cauda
    *"o que você salvar aqui volta sozinho toda vez que este jogo abrir."*.
    """
    from hefesto_dualsense4unix.interface import onde, pacotes

    congelado = _o_titulo_do_salvar((onde.AQUI / "fim.html").read_text(encoding="utf-8"))

    assert congelado == pacotes._dica_do_salvar("")
    assert PROMETE_O_JOGO not in congelado


#: As dez abas, pelo prefixo do arquivo.
DEZ = [f"{n:02d}-" for n in range(1, 11)]


@pytest.mark.parametrize("pagina", DEZ)  # (noqa-acento): nome de parâmetro
def test_a_bancada_das_dez_traz_o_rodape_novo(pagina: str) -> None:
    """O desenho de HOJE das dez abas: o rodapé regerado, sem a promessa do jogo.

    A BANCADA, não o publicado: quem publica é quem coordena, e a lacuna de
    publicação tem dono (`scripts/check_o_desenho_aprovado.py`).
    """
    from hefesto_dualsense4unix.interface import onde

    caminhos = sorted(onde.saida().glob(f"{pagina}*.html"))
    if not caminhos:
        pytest.skip(f"não há página na bancada para {pagina}")
    congelado = _o_titulo_do_salvar((onde.AQUI / "fim.html").read_text(encoding="utf-8"))

    assert _o_titulo_do_salvar(caminhos[0].read_text(encoding="utf-8")) == congelado
