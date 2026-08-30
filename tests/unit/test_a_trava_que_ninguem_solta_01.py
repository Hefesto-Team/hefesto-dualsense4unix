"""A-TRAVA-QUE-NINGUÉM-SOLTA-01 — `led` e `audio` armavam e nada as soltava.

MEDIDO em 29/08/2026, contra o disco, com
`grep -rn 'mark_manual_trigger_active\\|clear_manual_trigger_active' src/`:

    | categoria | arma em                                | solta em                  |
    |-----------|----------------------------------------|---------------------------|
    | `trigger` | `ipc_handlers.py:1240` (`trigger.set`) | `:1298` (`trigger.reset`) |
    | `rumble`  | `:4222` e `:4329`                      | `:4302` e `:4370`         |
    | `led`     | `:1369` e `:1425`                      | **nenhum**                |
    | `audio`   | `:4674` (`_marcar_audio_manual`)       | **nenhum**                |

Enquanto QUALQUER categoria está armada o `AutoSwitcher` não reaplica perfil
por mudança de janela (`profiles/autoswitch.py:904`). Duas das quatro entravam
e não saíam: a única porta era ela trocar de perfil na mão — um gesto que a
pessoa não tem como saber que precisa fazer.

**O tamanho do defeito, e ele não é "trava o produto todo":** 4 episódios de
`autoswitch_suppressed_by_manual_override` em 7 dias no journal dela, e a
exceção do perfil de jogo (a única saída automática que existia) nunca precisou
agir — zero vezes.

A CURA é o teto de OCIOSIDADE (`MANUAL_OVERRIDE_STALE_AFTER_SEC`), irmão do
`MANUAL_PROFILE_LOCK_SEC` que esta casa já usava para o lock do `profile.switch`
("expira sozinho — não exige reset"). Ociosidade, e não idade: cada
`mark_manual_trigger_active` renova o carimbo, então enquanto ela mexe o teto
anda junto.

POR QUE ESTA RÉGUA ANDA COM O RELÓGIO. Uma régua que lê a trava UMA VEZ mede um
instante, não um comportamento — e o comportamento aqui É o tempo. Cada teste
abaixo percorre uma TRAJETÓRIA de instantes e afirma a curva inteira: quando a
trava tem de estar firme, quando tem de soltar, e que o gesto continua vencendo
o relógio.

A MORDIDA (executada em 29/08, números no relatório da sprint): apague as
chamadas de `_purgar_overrides_vencidos()` nas três leituras de
`daemon/state_store.py` e esta suíte fica VERMELHA — a trava volta a ser eterna.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from hefesto_dualsense4unix.daemon.state_store import (
    MANUAL_OVERRIDE_CATEGORIES,
    MANUAL_OVERRIDE_STALE_AFTER_SEC,
    StateStore,
)
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.autoswitch import AutoSwitcher
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController

TETO = MANUAL_OVERRIDE_STALE_AFTER_SEC
MINUTO = 60.0
HORA = 3600.0


class _Relogio:
    """Relógio monotônico que ANDA quando mandado — o instrumento desta régua.

    Substitui só o `time` visto de dentro de `daemon/state_store`, por
    `SimpleNamespace`: mexer no módulo `time` global mudaria o relógio do
    processo inteiro, inclusive o do `AutoSwitcher`, e a régua passaria a medir
    duas coisas ao mesmo tempo.
    """

    def __init__(self, inicio: float = 1_000.0) -> None:
        self.agora = inicio

    def monotonic(self) -> float:
        return self.agora

    def andar(self, segundos: float) -> float:
        self.agora += segundos
        return self.agora


@pytest.fixture()
def relogio(monkeypatch: pytest.MonkeyPatch) -> _Relogio:
    r = _Relogio()
    monkeypatch.setattr(
        "hefesto_dualsense4unix.daemon.state_store.time",
        SimpleNamespace(monotonic=r.monotonic),
    )
    return r


@pytest.fixture
def isolated_profiles_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "profiles"
    target.mkdir()

    def fake_profiles_dir(ensure: bool = False) -> Path:
        if ensure:
            target.mkdir(parents=True, exist_ok=True)
        return target

    monkeypatch.setattr(loader_module, "profiles_dir", fake_profiles_dir)
    return target


def _perfil(name: str) -> Profile:
    return Profile(
        name=name,
        match=MatchCriteria(window_class=[f"{name}_class"]),
        priority=10,
        leds=LedsConfig(lightbar=(10, 20, 30)),
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Off"), right=TriggerConfig(mode="Off")
        ),
    )


# --- a trajetória: a trava sem gesto que a solte NÃO é mais eterna ---------


@pytest.mark.parametrize("categoria", ["audio", "led"])
def test_a_trava_sem_par_solta_sozinha_e_a_curva_inteira_confere(
    relogio: _Relogio, categoria: str
) -> None:
    """O caso dela: mexeu no volume (ou na cor), e o relógio devolve a troca.

    `audio` e `led` são as duas categorias SEM chamador de
    `clear_manual_trigger_active` em `src/` — para elas, este teto é a única
    porta de saída que não depende de ela adivinhar um gesto.

    A curva afirmada, e não um instante dela: firme no começo, firme na véspera
    do teto, solta depois. O ponto em `TETO - MINUTO` é o que separa este teste
    de um que só espera tempo bastante.
    """
    store = StateStore()
    store.mark_manual_trigger_active(categoria)

    trajetoria: list[tuple[float, bool]] = []
    # Enquanto a opinião dela é recente, a trava tem de estar de pé — inclusive
    # nos primeiros segundos, que é a janela em que o ABAS-05 acontece.
    for salto in (0.0, 1.0, 30.0, MINUTO, 10 * MINUTO, HORA, TETO - MINUTO):
        relogio.agora = 1_000.0 + salto
        trajetoria.append((salto, store.manual_trigger_active))
    # Passado o teto de ociosidade, ela está calada há horas: solta.
    for salto in (TETO + 1.0, TETO + HORA):
        relogio.agora = 1_000.0 + salto
        trajetoria.append((salto, store.manual_trigger_active))

    armada_ate_o_teto = [ativa for salto, ativa in trajetoria if salto < TETO]
    solta_depois = [ativa for salto, ativa in trajetoria if salto > TETO]
    assert all(armada_ate_o_teto), (
        f"a trava de {categoria!r} soltou CEDO — trajetória: {trajetoria}"
    )
    assert not any(solta_depois), (
        f"a trava de {categoria!r} continua eterna — trajetória: {trajetoria}"
    )
    assert store.manual_override_categories == frozenset()


def test_a_trava_e_de_ociosidade_e_nao_de_idade(relogio: _Relogio) -> None:
    """Enquanto ela MEXE, o teto anda junto — e é isto que o torna seguro.

    Um teto por IDADE venceria no meio de uma sessão em que ela ainda está
    ajustando a cor, e o autoswitch reescreveria o que ela acabou de aplicar:
    o defeito que o ABAS-05 curou. Por OCIOSIDADE isso não pode acontecer —
    cada reafirmação empurra o vencimento para a frente.
    """
    store = StateStore()
    store.mark_manual_trigger_active("led")

    # Ela reafirma logo ANTES de cada vencimento, doze vezes. O passo sai do
    # próprio teto (nunca de um número digitado): se ela mudar a constante, o
    # teste continua medindo a mesma coisa.
    passo = TETO * 0.8
    for _ in range(12):
        relogio.andar(passo)
        assert store.manual_trigger_active is True
        store.mark_manual_trigger_active("led")  # o `led.set` seguinte

    decorrido = relogio.agora - 1_000.0
    assert decorrido > 5 * TETO, f"o relógio nem chegou perto: {decorrido}s"
    assert store.manual_trigger_active is True

    # Só quando ela se cala é que o teto vence — e conta do ÚLTIMO gesto.
    relogio.andar(TETO - MINUTO)
    assert store.manual_trigger_active is True, "contou da PRIMEIRA, não da última"
    relogio.andar(2 * MINUTO)
    assert store.manual_trigger_active is False


def test_cada_categoria_vence_no_seu_tempo(relogio: _Relogio) -> None:
    """O teto é POR CATEGORIA — a granularidade do ABAS-05 sobrevive a ele.

    Soltar as quatro de uma vez ao vencer a primeira apagaria um gatilho ou uma
    vibração deliberada de outra aba, que é a razão escrita da assinatura por
    categoria em `clear_manual_trigger_active`.
    """
    store = StateStore()
    store.mark_manual_trigger_active("led")  # t0
    relogio.andar(5 * HORA)
    store.mark_manual_trigger_active("trigger")  # t0 + 5 h

    relogio.andar(TETO - 4 * HORA)  # led calado há 6 h+; trigger, há 1 h+
    assert store.manual_override_categories == frozenset({"trigger"}), (
        "o vencimento de `led` levou `trigger` junto — é a regressão do ABAS-05"
    )
    assert store.manual_trigger_active is True

    relogio.andar(TETO)
    assert store.manual_override_categories == frozenset()


def test_o_gesto_continua_vencendo_o_relogio(relogio: _Relogio) -> None:
    """O teto é REDE, não substituto: quem tem gesto solta na hora, como sempre.

    `trigger.reset` e `rumble.passthrough` continuam soltando só a sua categoria
    no instante do clique, sem esperar teto nenhum.
    """
    store = StateStore()
    for categoria in sorted(MANUAL_OVERRIDE_CATEGORIES):
        store.mark_manual_trigger_active(categoria)

    relogio.andar(MINUTO)
    store.clear_manual_trigger_active("trigger")  # o botão "Desligar"
    assert store.manual_override_categories == frozenset({"led", "rumble", "audio"})

    store.clear_manual_trigger_active("rumble")  # o fim do "Testar motores"
    assert store.manual_override_categories == frozenset({"led", "audio"})

    # E a saída global (o `profile.switch`) continua limpando tudo na hora.
    store.clear_manual_trigger_active()
    assert store.manual_trigger_active is False


def test_o_snapshot_nao_diverge_da_trava(relogio: _Relogio) -> None:
    """As TRÊS leituras da trava contam a mesma história.

    `manual_trigger_active` decide se o autoswitch roda,
    `manual_override_categories` decide o que o `ProfileManager` pula, e o
    `snapshot` é o que a janela lê. Sem a purga nas três, o `state_full` diria
    "travado" depois de o autoswitch já ter voltado a agir — e o diagnóstico
    seguinte começaria de uma mentira.
    """
    store = StateStore()
    store.mark_manual_trigger_active("audio")
    assert store.snapshot().manual_trigger_active is True

    relogio.andar(TETO + MINUTO)
    assert store.snapshot().manual_trigger_active is False
    assert store.manual_trigger_active is False
    assert store.manual_override_categories == frozenset()


# --- o encontro com o resto do sistema ------------------------------------


def test_o_autoswitch_volta_a_agir_depois_do_teto(
    isolated_profiles_dir: Path,
    relogio: _Relogio,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prova que importa: o perfil que estava calado ENTRA.

    Medir só o `StateStore` seria "medir o artefato, nunca o encontro dele com
    o resto do sistema" — o padrão que a ENTREGA-QUE-NÃO-LIGOU-01 nomeia e que
    já deixou esta trava passar. Aqui quem responde é o `AutoSwitcher._activate`
    de verdade, com só `audio` armada: a categoria que o volume arma e que
    nenhum gesto do produto solta.
    """
    save_profile(_perfil("shooter"))
    fc = FakeController()
    fc.connect()
    store = StateStore()
    manager = ProfileManager(controller=fc, store=store)

    ativacoes: list[str] = []
    monkeypatch.setattr(
        manager,
        "activate",
        # `**_` porque o `AutoSwitcher` passa `origin=` — um duplo de assinatura
        # estreita transformaria "a trava soltou" em `autoswitch_activate_failed`
        # e a régua leria a própria falha como se fosse o defeito.
        lambda name, **_: ativacoes.append(name) or MagicMock(),
    )
    switcher = AutoSwitcher(manager=manager, window_reader=lambda: {}, store=store)

    store.mark_manual_trigger_active("audio")  # ela encostou no volume

    # Ela joga. A cada troca de janela o autoswitch é chamado e cala a boca —
    # como tem de calar, porque o ajuste dela é recente.
    for salto in (0.0, MINUTO, HORA, TETO - MINUTO):
        relogio.agora = 1_000.0 + salto
        switcher._activate("shooter", {"wm_class": "Doom"})
    assert ativacoes == [], f"o autoswitch pisou no ajuste dela: {ativacoes}"

    # Horas depois, sem ela ter dito mais nada sobre áudio, a próxima troca de
    # janela volta a valer. Nenhum byte foi mandado pelo teto: quem escreve
    # continua sendo a ativação de perfil.
    relogio.agora = 1_000.0 + TETO + MINUTO
    switcher._activate("shooter", {"wm_class": "Doom"})
    assert ativacoes == ["shooter"]


def test_o_manager_para_de_pular_a_secao_depois_do_teto(relogio: _Relogio) -> None:
    """E o `ProfileManager` volta a aplicar a seção que a trava silenciava.

    É o outro lado da mesma moeda: enquanto `led` está armada, a ativação
    reporta `ignorado_trava_manual` para a seção de luz (o vocabulário que a
    PERFIL-REESCRITO-NA-PARTIDA-01 publicou). Vencido o teto, ela some da lista
    de travadas.
    """
    store = StateStore()
    store.mark_manual_trigger_active("led")

    def travadas() -> frozenset[str]:
        return frozenset(getattr(store, "manual_override_categories", ()) or ())

    assert "led" in travadas()
    relogio.andar(TETO + MINUTO)
    assert travadas() == frozenset()


# --- a meta-régua: a régua LÊ, nunca digita -------------------------------


def test_a_regua_le_a_constante_em_vez_de_digitar_o_numero() -> None:
    """O número do teto é DELA, e mudar a linha não pode quebrar esta suíte.

    Onze réguas de 26/08 reprovaram a melhora em vez do defeito pela mesma
    forma: digitavam o que deviam LER. Esta afirma a FAIXA em que o valor é
    honesto — longo demais para causar o ABAS-05 (que acontece em segundos) e
    curto o bastante para não ser "eterno" —, não o valor.
    """
    assert TETO > 10 * MINUTO, (
        "teto curto demais: dispararia dentro da janela do ABAS-05, e o "
        "autoswitch reescreveria a cor que a aba acabou de aplicar"
    )
    assert TETO <= 24 * HORA, "teto de mais de um dia é o defeito, não a cura"
    assert frozenset({"trigger", "led", "rumble", "audio"}) == MANUAL_OVERRIDE_CATEGORIES


def test_o_teto_alcanca_todas_as_categorias(relogio: _Relogio) -> None:
    """Categoria nova nasce coberta — inclusive a que ninguém lembrar de soltar.

    Percorre `MANUAL_OVERRIDE_CATEGORIES`, a constante, e não uma lista à mão:
    é o que faz esta régua continuar valendo quando a quinta categoria chegar.
    """
    for categoria in sorted(MANUAL_OVERRIDE_CATEGORIES):
        store = StateStore()
        relogio.agora = 1_000.0
        store.mark_manual_trigger_active(categoria)
        assert store.manual_trigger_active is True, categoria
        relogio.andar(TETO + MINUTO)
        assert store.manual_trigger_active is False, (
            f"a categoria {categoria!r} não é alcançada pelo teto"
        )


def test_uma_trava_nunca_armada_nao_inventa_vencimento(relogio: _Relogio) -> None:
    """Store fresca não tem trava, e o relógio não muda isso."""
    store = StateStore()
    assert store.manual_trigger_active is False
    relogio.andar(10 * TETO)
    assert store.manual_trigger_active is False
    assert store.manual_override_categories == frozenset()


def test_categoria_desconhecida_continua_recusada(relogio: _Relogio) -> None:
    """O carimbo não afrouxou a validação: só as quatro entram."""
    store = StateStore()
    with pytest.raises(ValueError, match="categoria de override desconhecida"):
        store.mark_manual_trigger_active("giroscopio")
    assert store.manual_trigger_active is False


def test_o_par_de_cada_categoria_esta_declarado() -> None:
    """O censo que originou a sprint, virado régua — e ele LÊ o `src/`.

    Não afirma que `led`/`audio` têm clear (não têm, e é o defeito). Afirma o
    que está MEDIDO: as duas com gesto têm par, as duas sem gesto não têm, e é
    por isso que o teto existe. No dia em que a aba Iluminação ligar o "Voltar
    ao automático" ao daemon, este teste reprova e alguém vem aqui apagar a
    linha — que é o jeito desta casa de uma dívida não envelhecer calada.
    """
    import ast
    from pathlib import Path as _Path

    raiz = _Path(__file__).resolve().parents[2] / "src"
    marcadas: set[str] = set()
    limpas: set[str] = set()
    for arquivo in raiz.rglob("*.py"):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            alvo = no.func
            if not isinstance(alvo, ast.Attribute):
                continue
            if alvo.attr not in (
                "mark_manual_trigger_active",
                "clear_manual_trigger_active",
            ):
                continue
            for arg in no.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    destino = (
                        marcadas
                        if alvo.attr == "mark_manual_trigger_active"
                        else limpas
                    )
                    destino.add(arg.value)

    assert {"trigger", "led", "rumble", "audio"} <= marcadas, (
        f"alguma categoria deixou de ser armada em src/: {sorted(marcadas)}"
    )
    assert {"trigger", "rumble"} <= limpas, (
        "`trigger` ou `rumble` perdeu o gesto que a solta — o teto passaria a "
        f"ser a única porta delas também: {sorted(limpas)}"
    )
    sem_par = {"led", "audio"} - limpas
    assert sem_par == {"led", "audio"}, (
        f"{sorted({'led', 'audio'} - sem_par)} ganhou um `clear` em src/. "
        "Ótimo — agora confira se ele dispara no gesto CERTO (não no rascunho "
        "da aba, que roda antes de a cor sair do hardware) e atualize esta "
        "régua e o texto de `MANUAL_OVERRIDE_STALE_AFTER_SEC`."
    )

