"""ELO-MUDO-01/E1 — o lançamento ATIVA o perfil, e não arma duas seções.

O DEFEITO, MEDIDO EM 22/08/2026 com o jogo dela aberto. O daemon sabia o nome
do jogo, resolvia o perfil por appid, e aplicava **duas seções de oito**: a
supressão e — só fora da allowlist — o `mode`. Gatilho, luz, vibração, som e
microfone esperavam o autoswitch, que espera a CLASSE DA JANELA. Ela respondeu
`unknown` por 21 minutos seguidos (`reason="sem_foco_x"`, `useful_age_sec=1276`)
com o jogo aberto, o perfil certo no disco e o `match` casando.

A queixa dela, com estas palavras: *"o perfil do sackboy não tá aplicando as
features das abas que eu seto e clico em salvar, como as abas de rumble,
gatilhos e deve ter outras"*. Nenhum elo estava quebrado — ninguém chamava a
ativação.

E o caminho da ALLOWLIST era ainda mais curto: `return` antes de tudo. Isso
contraria a decisão registrada dela — *"a allowlist do Steam Input NÃO é 'o
Hefesto sai da frente'. É o contrário: permitir a allowlist faz o Hefesto
continuar funcionando, com a saída sendo xbox ou DualSense e as features que ela
marcou."* O que a allowlist pula é a **disputa pelo controle** — máscara, grab,
vpad, que é o `mode`. Não a cor, o gatilho, o volume nem a vibração.

O que este portão cobra:

1. o lançamento chama a ATIVAÇÃO, e não só os dois appliers;
2. chama **também na allowlist**, e nela o `mode` continua sendo pulado;
3. `origin="launch"` — não fura o lock manual de 30 s (R-03) e não grava
   `session.json` (só `origin="manual"` grava);
4. o relatório da ativação **sobe no retorno**, nos dois caminhos. Sem isso
   `armado: True` continuaria sendo resposta de TRANSPORTE: diz que o modo foi
   pedido e cala sobre as outras sete seções;
5. ativação que falha **não derruba o arming** — o modo é o que põe o controle
   na mão dela;
6. e ela roda **uma vez por lançamento**, não a 1 Hz enquanto o jogo carrega.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    Profile,
    ProfileModeConfig,
)

APPID = 1599660  # Sackboy: A Big Adventure — o jogo da medição


def _marker(tmp_path: Path, *, appid: int, epoch: int) -> Path:
    (tmp_path / "last_run").write_text(
        f"appid={appid}\nepoch={epoch}\npid=1\n", encoding="utf-8"
    )
    return tmp_path


def _perfil(nome: str = "Sackboy") -> Profile:
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        priority=97,
        mode=ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense", coop=True),
    )


class _DaemonFalso:
    def __init__(self) -> None:
        self.aplicados: list[tuple[Any, Any, str]] = []
        self.suprimidos: list[tuple[bool, Any, str]] = []
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor="xbox"
        )
        self._gamepad_device = SimpleNamespace(backend="uinput")
        self._coop_manager = None
        self.controller = SimpleNamespace()

    def is_native_mode(self) -> bool:
        return False

    def apply_profile_mode(
        self, mode: Any, *, profile: Any = None, origin: str = "autoswitch"
    ) -> str:
        self.aplicados.append((mode, profile, origin))
        return "aplicado"

    def apply_profile_suppression(
        self, desired: bool, *, profile: Any = None, origin: str = "autoswitch"
    ) -> str:
        self.suprimidos.append((desired, profile, origin))
        return "aplicado"


class _GerenteEspiao:
    """Substitui o `ProfileManager` e anota o que a ativação recebeu.

    Ele PREENCHE o relatório com as oito seções, como o de verdade faz — sem
    isso o teste do item 4 passaria com o relatório vazio, que é justamente o
    estado que o defeito produzia.
    """

    chamadas: ClassVar[list[tuple[str, str]]] = []
    relatorios: ClassVar[list[dict[str, str]]] = []
    levanta: bool = False

    SECOES: ClassVar[tuple[str, ...]] = (
        "triggers",
        "leds",
        "rumble",
        "mouse",
        "keyboard",
        "mic",
        "speaker",
        "mode",
    )

    construidos: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        type(self).construidos.append(kwargs)

    def activate(
        self, nome: str, *, origin: str = "manual", relatorio: Any = None
    ) -> Any:
        type(self).chamadas.append((nome, origin))
        if type(self).levanta:
            raise RuntimeError("o disco não tem esse perfil")
        if relatorio is not None:
            for secao in self.SECOES:
                relatorio[secao] = "aplicado"
            type(self).relatorios.append(dict(relatorio))
        return None


@pytest.fixture
def espiao(monkeypatch: pytest.MonkeyPatch) -> type[_GerenteEspiao]:
    _GerenteEspiao.chamadas = []
    _GerenteEspiao.relatorios = []
    _GerenteEspiao.construidos = []
    _GerenteEspiao.levanta = False
    from hefesto_dualsense4unix.profiles import manager as m

    monkeypatch.setattr(m, "gerente_do_daemon", lambda daemon, **kw: _GerenteEspiao(**kw))
    return _GerenteEspiao


@pytest.fixture
def env_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    return tmp_path


def _armar(
    env_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    na_allowlist: bool = False,
    now: float = 1001.0,
    epoch: int = 1000,
) -> tuple[_DaemonFalso, Any]:
    _marker(env_dir, appid=APPID, epoch=epoch)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, _perfil())])
    monkeypatch.setattr(
        le, "steam_input_appids", lambda: ({APPID} if na_allowlist else set())
    )
    daemon = _DaemonFalso()
    return daemon, le.arm_launch_profile(daemon, base_dir=env_dir, now=now)


# --- 1 e 3. A ativação acontece, com a origem certa -------------------------


def test_o_lancamento_chama_a_ativacao_do_perfil(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch, espiao: type[_GerenteEspiao]
) -> None:
    """Mordida: apagar a chamada de `_ativar_o_perfil_do_lancamento`."""
    _daemon, resultado = _armar(env_dir, monkeypatch)

    assert resultado is not None and resultado["armado"] is True
    assert espiao.chamadas == [("Sackboy", "launch")], (
        "o lançamento não ativou o perfil. Sem isto o produto aplica duas "
        "seções de oito e as outras seis esperam a classe da janela, que "
        "respondeu `unknown` por 21 minutos na medição de 22/08"
    )


def test_a_origem_e_launch_e_nao_manual(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch, espiao: type[_GerenteEspiao]
) -> None:
    """`manual` furaria o lock de 30 s e gravaria `session.json`.

    As duas coisas são erradas para uma ativação automática: a primeira
    atropelaria um gesto dela de segundos atrás; a segunda faria o jogo de hoje
    decidir qual perfil abre no boot de amanhã.

    Mordida: trocar `origin="launch"` por `origin="manual"`.
    """
    _armar(env_dir, monkeypatch)
    assert [origem for _nome, origem in espiao.chamadas] == ["launch"]


# --- 2. A allowlist NÃO tira o Hefesto da frente ----------------------------


def test_na_allowlist_o_perfil_e_ativado_do_mesmo_jeito(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch, espiao: type[_GerenteEspiao]
) -> None:
    """A decisão dela, em código.

    Mordida: mover a chamada para DEPOIS do `if na_allowlist: return`.
    """
    _daemon, resultado = _armar(env_dir, monkeypatch, na_allowlist=True)

    assert resultado is not None
    assert resultado["motivo"] == "allowlist_steam_input"
    assert espiao.chamadas == [("Sackboy", "launch")], (
        "a allowlist voltou a tirar o Hefesto da frente. A decisão dela é a "
        "oposta: o que a allowlist pula é a disputa pelo controle (máscara, "
        "grab, vpad), não a cor, o gatilho, o volume nem a vibração"
    )


def test_na_allowlist_o_modo_continua_pulado(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch, espiao: type[_GerenteEspiao]
) -> None:
    """A outra metade: ativar o perfil não pode ressuscitar a disputa pelo vpad.

    **SÃO DOIS CAMINHOS ATÉ O MESMO APPLIER, e a primeira versão deste teste
    vigiava um só** — medido ao vivo em 22/08/2026, no primeiro ensaio no daemon
    dela. O `return` do ramo da allowlist pula o `apply_profile_mode` que o
    arming chama DIRETO (`daemon.aplicados`, abaixo), e o teste passava verde
    por causa disso. Mas a ativação tem o seu, dentro do `apply_emulation`, e
    ele armou o modo pelo caminho de dentro: o journal trouxe
    `launch_arm_pulado_allowlist_steam_input ... ativacao={... 'mode':
    'aplicado' ...}` — a allowlist sendo pulada e cumprida na mesma linha.

    A cura é passar `mode_applier=None` à fábrica nesse ramo, e a régua deste
    teste passou a ser a CONSTRUÇÃO do gerente, que é onde a decisão mora.

    Mordida: tirar o `return` do ramo da allowlist, ou tirar o
    `mode_applier=None` da construção.
    """
    daemon, _resultado = _armar(env_dir, monkeypatch, na_allowlist=True)

    assert daemon.aplicados == [], (
        "o `mode` foi armado pelo caminho de FORA (o applier direto do arming)"
    )
    assert espiao.construidos == [{"store": None, "mode_applier": None}], (
        "o gerente da allowlist nasceu com `mode_applier` — a ativação vai "
        "armar o modo pelo caminho de DENTRO, que é a mesma disputa pelo "
        f"controle que ela decidiu pular. Construído com: {espiao.construidos}"
    )
    assert len(daemon.suprimidos) == 1, "a supressão continua valendo nos dois lados"


def test_fora_da_allowlist_o_gerente_nasce_com_o_mode_applier(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch, espiao: type[_GerenteEspiao]
) -> None:
    """A contraparte: desarmar o modo é exceção da allowlist, não regra.

    Sem este par, `mode_applier=None` para todo mundo passaria no teste acima e
    o perfil deixaria de armar o modo em TODO jogo — a cura virando o defeito.

    Mordida: passar `mode_applier=None` incondicionalmente.
    """
    _armar(env_dir, monkeypatch, na_allowlist=False)

    assert espiao.construidos == [{"store": None}], (
        f"o gerente fora da allowlist não pode nascer capado: {espiao.construidos}"
    )


# --- 4. O relatório sobe, nos dois caminhos ---------------------------------


@pytest.mark.parametrize("na_allowlist", [False, True])
def test_o_relatorio_da_ativacao_sobe_no_retorno(
    env_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    espiao: type[_GerenteEspiao],
    na_allowlist: bool,
) -> None:
    """Sem ele, `armado: True` é resposta de TRANSPORTE.

    Mordida: apagar a chave do payload de um dos dois dicionários de retorno.
    """
    _daemon, resultado = _armar(env_dir, monkeypatch, na_allowlist=na_allowlist)

    assert resultado is not None
    entrou = resultado.get("ativacao")  # chave de payload (noqa-acento)
    assert isinstance(entrou, dict) and entrou, (
        "o retorno do arming não carrega o que a ativação fez. Quem pergunta "
        "'o perfil entrou?' continua tendo de adivinhar pelo aparelho"
    )
    assert set(entrou) == set(_GerenteEspiao.SECOES)


# --- 5. Falhar na ativação não derruba o arming -----------------------------


def test_ativacao_que_levanta_nao_impede_o_arming_do_modo(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch, espiao: type[_GerenteEspiao]
) -> None:
    """O modo é o que põe o controle na mão dela — ele não pode cair junto.

    Mordida: tirar o `try/except` de `_ativar_o_perfil_do_lancamento`.
    """
    espiao.levanta = True
    daemon, resultado = _armar(env_dir, monkeypatch)

    assert resultado is not None and resultado["armado"] is True
    assert len(daemon.aplicados) == 1, "o modo deixou de ser armado por causa da falha"
    assert resultado["ativacao"] == {}, (  # chave de payload (noqa-acento)
        "relatório vazio é o que uma exceção deixa; um relatório cheio de "
        "`ignorado_*` conta outra história, e as duas precisam ser distinguíveis"
    )


# --- 6. Uma vez por lançamento ----------------------------------------------


def test_a_ativacao_roda_uma_vez_so_por_lancamento(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch, espiao: type[_GerenteEspiao]
) -> None:
    """A reconciliação anda a 1 Hz. Sem a guarda, seria uma ativação por segundo
    durante o carregamento inteiro do jogo — e cada uma reescreve gatilho e LED.

    Mordida: apagar o gate do `_launch_armed_for` no topo do arming.
    """
    _marker(env_dir, appid=APPID, epoch=1000)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, _perfil())])
    monkeypatch.setattr(le, "steam_input_appids", set)
    daemon = _DaemonFalso()

    for instante in (1001.0, 1002.0, 1003.0):
        le.arm_launch_profile(daemon, base_dir=env_dir, now=instante)

    assert len(espiao.chamadas) == 1


# --- A fábrica do gerente ---------------------------------------------------


def test_a_fabrica_cobre_todo_applier_que_o_gerente_aceita() -> None:
    """A régua é o `ProfileManager`, e NÃO a própria lista da fábrica.

    Medido em 22/08/2026, escrevendo este arquivo: a primeira versão deste teste
    iterava `APPLIERS_DO_DAEMON` para conferir `APPLIERS_DO_DAEMON`. Arrancar um
    par da lista fazia o teste passar — ele conferia o instrumento contra si
    mesmo. Nesta casa o instrumento mente mais que o produto, e a regra é
    validar a régua contra uma contagem independente antes de acreditar nela.

    A contagem independente são os campos do próprio `ProfileManager`: todo
    campo cujo nome termina em `_applier` é uma seção que o gerente sabe
    aplicar, e cada um precisa de alguém que o injete. Um applier novo no
    dataclass e esquecido na fábrica reprova aqui.

    Mordida: tirar um par de `APPLIERS_DO_DAEMON`.
    """
    import dataclasses

    from hefesto_dualsense4unix.profiles.manager import (
        APPLIERS_DO_DAEMON,
        ProfileManager,
    )

    do_gerente = {
        campo.name
        for campo in dataclasses.fields(ProfileManager)
        if campo.name.endswith("_applier")
    }
    da_fabrica = {parametro for parametro, _atributo in APPLIERS_DO_DAEMON}

    assert do_gerente, "a régua quebrou: o gerente não tem campo `_applier` nenhum"
    assert do_gerente == da_fabrica, (
        "a fábrica e o gerente discordam. Faltando na fábrica: "
        f"{sorted(do_gerente - da_fabrica)}; sobrando: "
        f"{sorted(da_fabrica - do_gerente)}. Applier ausente NÃO levanta — a "
        "seção é ignorada em silêncio, e o defeito só aparece no aparelho dela."
    )


def test_a_fabrica_injeta_o_que_o_daemon_tem() -> None:
    """E o que ela promete injetar, ela injeta mesmo.

    O teste acima cobre a LISTA; este cobre a CONSTRUÇÃO. Os dois juntos são o
    par: um diz que nenhuma seção ficou de fora do contrato, o outro que o
    contrato é cumprido.

    Mordida: trocar o laço de injeção por um `pass`.
    """
    from hefesto_dualsense4unix.profiles.manager import (
        APPLIERS_DO_DAEMON,
        gerente_do_daemon,
    )

    class _DaemonComTudo:
        controller = SimpleNamespace()
        _keyboard_device = None

    daemon = _DaemonComTudo()
    marcadores: dict[str, object] = {}
    for _parametro, atributo in APPLIERS_DO_DAEMON:
        marcador = object()
        marcadores[atributo] = marcador
        setattr(daemon, atributo, marcador)

    gerente = gerente_do_daemon(daemon)

    for parametro, atributo in APPLIERS_DO_DAEMON:
        assert getattr(gerente, parametro) is marcadores[atributo], (
            f"a fábrica não injetou {parametro}"
        )
    assert gerente.keyboard_device_provider is not None, (
        "o provider do teclado é lazy de propósito: o gerente nasce antes de o "
        "teclado subir, e capturar a referência agora congelaria None"
    )


def test_daemon_sem_o_applier_nao_derruba_a_construcao() -> None:
    """Contrato declarado: `getattr` com default `None`, sempre.

    Esta função é chamada por dublês da suíte e por rotas de CLI que não têm
    daemon nenhum. Um atributo ausente ali não pode derrubar a ativação — a
    seção volta a ser ignorada, que é o comportamento histórico.

    Mordida: trocar o `getattr(daemon, atributo, None)` por acesso direto.
    """
    from hefesto_dualsense4unix.profiles.manager import gerente_do_daemon

    class _DaemonPelado:
        controller = SimpleNamespace()

    gerente = gerente_do_daemon(_DaemonPelado())
    assert gerente.mic_applier is None
