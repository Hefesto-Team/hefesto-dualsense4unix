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
2. chama **também na allowlist**, e nela a MÁSCARA do perfil chega enquanto o
   `kind` continua pulado (ALLOWLIST-SO-A-MASCARA-01 — o comportamento do
   embrulho está no par deste arquivo,
   `test_a_mascara_atravessa_a_allowlist.py`; aqui mede-se a fiação);
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


def _perfil(nome: str = "Sackboy", *, kind: str = "gamepad") -> Profile:
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        priority=97,
        mode=ProfileModeConfig(kind=kind, gamepad_flavor="dualsense", coop=True),
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

    **E ele CHAMA o `mode_applier`, como o `ProfileManager.activate` chama**
    (22/08/2026). A versão anterior só anotava os kwargs da construção, e por
    isso mediu a FIAÇÃO e não o EFEITO: com `mode_applier=None` a régua dizia
    "o modo está pulado" sem nunca ter perguntado o que o applier faria. Foi
    assim que a allowlist passou horas REMOVENDO a máscara do perfil enquanto o
    portão ficava verde. A fábrica de verdade injeta
    `daemon.apply_profile_mode` quando o chamador não sobrescreve — o dublê
    reproduz isso, senão o ramo de fora da allowlist ficaria mudo aqui.
    """

    chamadas: ClassVar[list[tuple[str, str]]] = []
    relatorios: ClassVar[list[dict[str, str]]] = []
    modo_devolvido: ClassVar[list[str]] = []
    perfil: ClassVar[Any] = None
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

    def __init__(self, daemon: Any = None, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.daemon = daemon
        type(self).construidos.append(kwargs)

    def activate(
        self, nome: str, *, origin: str = "manual", relatorio: Any = None
    ) -> Any:
        type(self).chamadas.append((nome, origin))
        if type(self).levanta:
            raise RuntimeError("o disco não tem esse perfil")
        applier = self.kwargs.get(
            "mode_applier", getattr(self.daemon, "apply_profile_mode", None)
        )
        perfil = type(self).perfil
        if applier is not None and perfil is not None:
            type(self).modo_devolvido.append(
                str(applier(getattr(perfil, "mode", None), profile=perfil, origin=origin))
            )
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
    _GerenteEspiao.modo_devolvido = []
    _GerenteEspiao.perfil = None
    _GerenteEspiao.levanta = False
    from hefesto_dualsense4unix.profiles import manager as m

    monkeypatch.setattr(
        m, "gerente_do_daemon", lambda daemon, **kw: _GerenteEspiao(daemon, **kw)
    )
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
    kind: str = "gamepad",
) -> tuple[_DaemonFalso, Any]:
    _marker(env_dir, appid=APPID, epoch=epoch)
    perfil = _perfil(kind=kind)
    _GerenteEspiao.perfil = perfil
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [(APPID, perfil)])
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


def test_na_allowlist_a_mascara_do_perfil_chega(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch, espiao: type[_GerenteEspiao]
) -> None:
    """ALLOWLIST-SO-A-MASCARA-01 — a metade que a medição de 22/08 derrubou.

    **SÃO DOIS CAMINHOS ATÉ O MESMO APPLIER.** O `return` do ramo da allowlist
    pula o `apply_profile_mode` que o arming chama DIRETO; a ativação tem o
    seu, dentro do `apply_emulation`. Este teste cobra o de DENTRO: com o
    Sackboy marcado, o perfil pede `gamepad_flavor="dualsense"` e a máscara
    tem de chegar.

    Por algumas horas de 22/08 a cura foi `mode_applier=None`, e ela está
    refutada pela medição no daemon dela: `active_profile="Sackboy"`,
    `mode_from_profile=null`, quatro vpads uinput e `flavor="xbox"` — marcar o
    jogo REMOVIA touchpad, giroscópio e acelerômetro em vez de preservá-los.

    Mordida: trocar o embrulho de volta por `mode_applier=None`.
    """
    daemon, _resultado = _armar(env_dir, monkeypatch, na_allowlist=True)

    assert espiao.chamadas == [("Sackboy", "launch")]
    assert len(daemon.aplicados) == 1, (
        "a máscara do perfil não chegou ao `apply_profile_mode`. Com o físico "
        "escondido o vpad é o único dispositivo do jogo, e um vpad Xbox não "
        f"tem touchpad, giroscópio nem acelerômetro. Aplicados: {daemon.aplicados}"
    )
    mode, profile, origin = daemon.aplicados[0]
    assert getattr(mode, "gamepad_flavor", None) == "dualsense"
    assert getattr(profile, "name", None) == "Sackboy" and origin == "launch"
    assert espiao.modo_devolvido == ["aplicado"], (
        "o veredito do applier não subiu pelo embrulho — o relatório da "
        "ativação volta a não distinguir aplicado de adiado"
    )
    assert len(daemon.suprimidos) == 1, "a supressão continua valendo nos dois lados"


def test_na_allowlist_o_kind_continua_pulado(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch, espiao: type[_GerenteEspiao]
) -> None:
    """A outra metade: ativar o perfil não pode ressuscitar a disputa pelo vpad.

    Um perfil `kind="native"` marcado na allowlist pediria o release total —
    largar o físico e desligar o vpad. Isso é disputa pelo controle, e é
    exatamente o que a allowlist existe para pular.

    Mordida: apagar o `if kind != "gamepad"` de `_mode_applier_so_a_mascara`.
    """
    daemon, resultado = _armar(env_dir, monkeypatch, na_allowlist=True, kind="native")

    assert resultado is not None and resultado["motivo"] == "allowlist_steam_input"
    assert espiao.chamadas == [("Sackboy", "launch")], (
        "as outras sete seções continuam valendo na allowlist"
    )
    assert daemon.aplicados == [], (
        f"o `kind` atravessou a allowlist: {daemon.aplicados}"
    )
    assert espiao.modo_devolvido == [le.IGNORADO_DISPUTA_DA_ALLOWLIST]


def test_fora_da_allowlist_nada_muda(
    env_dir: Path, monkeypatch: pytest.MonkeyPatch, espiao: type[_GerenteEspiao]
) -> None:
    """A contraparte: o embrulho é exceção da allowlist, não regra.

    Sem este par, embrulhar todo mundo passaria nos dois testes acima e o
    perfil deixaria de armar o modo em TODO jogo que a máscara ainda não
    estivesse de pé — a cura virando o defeito.

    Mordida: passar o embrulho incondicionalmente.
    """
    _armar(env_dir, monkeypatch, na_allowlist=False)

    assert espiao.construidos == [{"store": None}], (
        "fora da allowlist o gerente nasce da fábrica limpa, com o "
        f"`apply_profile_mode` do daemon: {espiao.construidos}"
    )
    assert espiao.modo_devolvido == ["aplicado"], (
        "a ativação de fora da allowlist deixou de aplicar o modo"
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
    entrou = resultado.get("ativacao")  # chave de payload (noqa-acento) identificador
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
    assert resultado["ativacao"] == {}, (  # chave de payload (noqa-acento) identificador
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
