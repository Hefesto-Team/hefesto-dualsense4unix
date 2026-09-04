"""VIBRACAO-POR-MOTOR-01 (04/09/2026) — a barra de cada motor MULTIPLICA o degrau.

A DECISÃO É DELA, E VEIO FORA DAS TRÊS OPÇÕES QUE EU OFERECI
-------------------------------------------------------------
Eu perguntei se arrastar a barra de um motor mandava o par ``rumble.set`` agora
ou virava leitura. As duas metades da pergunta estavam erradas — a barra não é
comando nem leitura, é **política**:

    *"os slcers do botão esquerdo e direito (forte e fraco) se multiplicam*
    *(interagem com os botões economia, moderado, máximo, se eu tiver 150% do*
    *perfil de vibração e as duas linhas estiverem 100 entao a vibração dos 2*
    *será 150%, mas se so a do motor fraco tiver 100 e a outrqa 50% então será*
    *150 em um e 75% no outro entende?"*
    <!-- noqa-acento: citação literal dela -->

A CONTA, com os números dela — e é o caso do primeiro teste deste arquivo::

    efetivo(motor) = degrau(coluna) x barra(motor)

    degrau 150 %, fraca 100 %, forte 100 %  ->  150 % e 150 %
    degrau 150 %, fraca 100 %, forte  50 %  ->  150 % e  75 %

O QUE CADA GRUPO VIGIA
-----------------------
1. **A conta dela**, com o par exato, do disco ao par escrito no controle —
   ``TestAContaDela``;
2. **o que NÃO muda** — sem barra escrita, sem endereço pedido, ou com as duas
   em 100, o par é byte-idêntico ao de antes desta sprint. Um arredondamento
   novo no caminho de quem não pediu nada é regressão silenciosa em catorze
   perfis (``TestOQueNaoMuda``);
3. **a composição com o TETO por controle** — a barra multiplica *antes*, o
   teto do card do cabo (``08-conexoes``) escala *depois*, dentro do backend.
   Os dois medidos JUNTOS, porque a sprint pede exatamente isso: a conta nova
   tem de compor com o teto sem apagá-lo (``TestCompoeComOTeto``);
4. **a borda do esquema** — 0 é escolha, 101 e -1 são recusa com razão
   (``TestABordaDoEsquema``);
5. **o cache do mapa** — memoizado pelo nome do perfil, e a linha que o
   invalida (``TestOCacheDoMapa``);
6. **a régua sabe RECUSAR** — as duas funções puras exercitadas com entrada
   sintética, nos dois sentidos (``TestARéguaSabeRecusar``);
7. **o degrau não escapa sozinho** — uma leitura por AST que reprova se
   ``apply_game_rumble`` voltar a chamar ``_game_rumble_mult`` direto, que é o
   jeito exato de a barra sumir sem nenhum teste ficar vermelho
   (``TestODegrauNaoEscapaSozinho``).

MORDIDA (o que arrancar para ver reprovar): em
``daemon/subsystems/gamepad._mults_por_motor``, troque o ``return`` por
``(degrau, degrau)`` — a barra some e o degrau vai inteiro nos dois motores. O
caso dela passa a sair ``(150, 150)`` onde tem de sair ``(150, 75)``, e
``TestAContaDela`` reprova nomeando os dois números.

Endereços de rádio: a máscara da casa (octetos 4 e 5 zerados), reusados do
banco de provas do backend — nunca o endereço de um aparelho real.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp_mod
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import _controllers_to_rumble_scales
from hefesto_dualsense4unix.profiles.schema import (
    MOTOR_PCT_MAX,
    MOTOR_PCT_PADRAO,
    ControllerOverrides,
    ControllerRumbleOverride,
    MatchAny,
    Profile,
    RumbleConfig,
    motores_dos_controles,
    pcts_dos_motores,
)
from tests.unit.test_backend_multi_controller import (
    KEY_1,
    KEY_2,
    UNIQ_1,
    UNIQ_2,
    _FakeHandle,
    _null_evdev,
)

#: Os dois controles dela, com a máscara da casa (octetos 4 e 5 zerados).
BRANCO = UNIQ_1
PRETO = UNIQ_2

#: O degrau "Máximo" — 150 %, e é o número da frase dela. NÃO se digita `1.5`:
#: quem manda na escada é `daemon.subsystems.rumble.RUMBLE_POLICY_MULT`, e uma
#: segunda cópia divergiria no primeiro dia em que o degrau mudasse (é o mesmo
#: HARM-19 que já custou uma tarde nesta casa).
def _degrau(nome: str) -> float:
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    return RUMBLE_POLICY_MULT[nome]


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado — o mesmo molde do `isolated_profiles_dir`."""
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


class _Backend:
    """Backend de mentira com a API por-uniq: guarda (uniq, weak, strong)."""

    def __init__(self, uniqs: tuple[str, ...] = (BRANCO, PRETO)) -> None:
        self._uniqs = list(uniqs)
        self.rumbles: list[tuple[str | None, int, int]] = []
        self.primary_uniq: str | None = uniqs[0] if uniqs else None

    def set_rumble_for(self, uniq: str, weak: int, strong: int) -> bool:
        if uniq not in self._uniqs:
            return False
        self.rumbles.append((uniq, weak, strong))
        return True

    def set_rumble(self, weak: int, strong: int) -> None:
        self.rumbles.append((None, weak, strong))


def _daemon(
    *,
    policy: str = "balanceado",
    perfil_ativo: str | None = None,
    battery: int = 80,
    controller: Any | None = None,
) -> Any:
    """Daemon de mentira — o mesmo molde do `test_vpad_ff_passthrough._make_daemon`,
    mais o `store.active_profile`, que é de onde o mapa por peça sai."""
    estado = SimpleNamespace(battery_pct=battery)
    return SimpleNamespace(
        config=SimpleNamespace(
            rumble_active=None,
            rumble_policy=policy,
            rumble_policy_custom_mult=0.7,
        ),
        controller=controller if controller is not None else _Backend(),
        store=SimpleNamespace(
            active_profile=perfil_ativo,
            snapshot=lambda: SimpleNamespace(controller=estado),
        ),
        _last_auto_mult=0.7,
        _last_auto_change_at=0.0,
    )


def _grava(nome: str, **barras: int | None) -> None:
    """Grava no disco um perfil com as barras do BRANCO, e só elas."""
    save_profile(
        Profile(
            name=nome,
            match=MatchAny(),
            controllers={
                BRANCO: ControllerOverrides(
                    rumble=ControllerRumbleOverride(
                        **{k: v for k, v in barras.items() if v is not None}
                    )
                )
            },
        )
    )


# ---------------------------------------------------------------------------
# 1. A CONTA DELA
# ---------------------------------------------------------------------------


class TestAContaDela:
    def test_degrau_150_fraca_100_forte_50_sai_150_e_75(self, perfis: Path) -> None:
        """O CASO EXATO DA FRASE DELA, do disco ao par escrito no controle.

        `weak` é o motor FRACO (o pequeno, `setRightMotor`) e `strong` é o
        FORTE (o grande, `setLeftMotor`) — a nomenclatura do pydualsense, e é
        por isso que a barra "forte" mexe no `strong` e não no `weak`.

        MORDIDA: `_mults_por_motor` devolvendo `(degrau, degrau)` faz o forte
        sair 150 em vez de 75, e o assert nomeia os dois números.
        """
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        backend = _Backend()
        d = _daemon(policy="max", perfil_ativo="Bancada", controller=backend)

        efetivo = gp_mod.apply_game_rumble(d, 100, 100, target_uniq=BRANCO)

        degrau = _degrau("max")
        esperado = (round(100 * degrau), round(100 * degrau * 0.5))
        assert efetivo == esperado, (
            f"o par efetivo saiu {efetivo}, e a conta dela pede {esperado}: "
            f"degrau {degrau:.0%} x barra fraca 100% no `weak`, e o MESMO "
            f"degrau x barra forte 50% no `strong`. Se os dois vieram iguais, "
            f"a barra não entrou na conta."
        )
        assert backend.rumbles == [(BRANCO, *esperado)]

    def test_a_outra_peca_da_mesa_nao_e_tocada(self, perfis: Path) -> None:
        """A barra do BRANCO não escala o PRETO — é por peça, não por mesa.

        MORDIDA: fazer `_pcts_dos_motores` ignorar o `target_uniq` e devolver
        o primeiro par do mapa. O PRETO passa a sair 75 no forte e reprova.
        """
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        backend = _Backend()
        d = _daemon(policy="max", perfil_ativo="Bancada", controller=backend)

        gp_mod.apply_game_rumble(d, 100, 100, target_uniq=PRETO)

        degrau = _degrau("max")
        inteiro = round(100 * degrau)
        assert backend.rumbles == [(PRETO, inteiro, inteiro)], (
            "a peça SEM opinião recebeu a barra da outra — a barra é por peça"
        )

    def test_zero_cala_um_motor_e_o_outro_continua(self, perfis: Path) -> None:
        """`0` é escolha, não ausência: um motor mudo e o outro inteiro.

        MORDIDA: trocar o `if valor is None` do esquema por `if not valor` —
        o zero passa a ser lido como "sem opinião" e este teste reprova com o
        motor fraco vibrando.
        """
        _grava("Bancada", motor_forte_pct=100, motor_fraco_pct=0)
        backend = _Backend()
        d = _daemon(perfil_ativo="Bancada", controller=backend)

        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=BRANCO)

        assert backend.rumbles == [(BRANCO, 0, 200)], (
            "o motor fraco tinha de sair MUDO (barra 0) e o forte inteiro"
        )


# ---------------------------------------------------------------------------
# 2. O QUE NÃO MUDA — e é metade da entrega
# ---------------------------------------------------------------------------


class TestOQueNaoMuda:
    def test_perfil_sem_barra_e_byte_identico_ao_de_antes(self, perfis: Path) -> None:
        """Catorze perfis no disco dela não têm as chaves novas. Nada muda neles.

        MORDIDA: fazer `pcts_dos_motores` devolver `(99, 99)` no caso `None`.
        O 200 vira 198 e este assert pega.
        """
        save_profile(Profile(name="Simples", match=MatchAny()))
        backend = _Backend()
        d = _daemon(perfil_ativo="Simples", controller=backend)

        gp_mod.apply_game_rumble(d, 200, 137, target_uniq=BRANCO)

        assert backend.rumbles == [(BRANCO, 200, 137)]

    def test_as_duas_em_cem_entregam_o_degrau_inteiro(self, perfis: Path) -> None:
        """A outra metade da frase dela: `150 · 100 · 100 → 150 e 150`."""
        _grava("Bancada", motor_forte_pct=100, motor_fraco_pct=100)
        backend = _Backend()
        d = _daemon(policy="max", perfil_ativo="Bancada", controller=backend)

        gp_mod.apply_game_rumble(d, 100, 100, target_uniq=BRANCO)

        inteiro = round(100 * _degrau("max"))
        assert backend.rumbles == [(BRANCO, inteiro, inteiro)]

    def test_sem_endereco_pedido_nao_ha_peca(self, perfis: Path) -> None:
        """`target_uniq is None` = ninguém nomeou peça → par neutro.

        Mesma disciplina do BROADCAST-PROIBIDO-01: sem endereço, aplicar a
        barra de UMA peça seria pôr a escolha do jogador 2 na mão do 1.

        MORDIDA: fazer `_pcts_dos_motores` cair no `primary_uniq` quando o
        alvo é `None`. Este caso passa a sair 50 no forte e reprova.
        """
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=50)
        registrados: list[tuple[int, int]] = []
        controller = SimpleNamespace(
            set_rumble=lambda weak, strong: registrados.append((weak, strong))
        )
        d = _daemon(perfil_ativo="Bancada", controller=controller)

        gp_mod.apply_game_rumble(d, 80, 90, target_uniq=None)

        assert registrados == [(80, 90)], "sem endereço não há peça, e nada escala"

    def test_perfil_ilegivel_nao_derruba_a_vibracao(
        self, perfis: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """JSON torto = mapa vazio, não jogo sem vibração.

        Vibração é caminho quente e transitório: levantar aqui trocaria um
        ajuste perdido por uma partida inteira muda.

        MORDIDA: tirar o `try/except` de `_motores_do_perfil_ativo` — a
        exceção sobe pelo `apply_game_rumble` e este teste vira erro.
        """

        def _explode(_nome: str) -> Any:
            raise ValueError("perfil torto")

        monkeypatch.setattr(loader_module, "load_profile", _explode)
        backend = _Backend()
        d = _daemon(perfil_ativo="Bancada", controller=backend)

        gp_mod.apply_game_rumble(d, 111, 222, target_uniq=BRANCO)

        assert backend.rumbles == [(BRANCO, 111, 222)]


# ---------------------------------------------------------------------------
# 3. A COMPOSIÇÃO COM O TETO POR CONTROLE — medidos JUNTOS
# ---------------------------------------------------------------------------


class TestCompoeComOTeto:
    """A sprint manda: *"a sua conta tem de compor com ele sem apagá-lo — meça
    os dois juntos antes de afirmar"*. Aqui os dois estão no MESMO perfil, na
    MESMA peça, e a medição percorre os dois andares: a barra no
    `apply_game_rumble` e o teto no `_escalar_rumble` do backend."""

    def test_a_barra_multiplica_e_o_teto_escala_depois(self, perfis: Path) -> None:
        """Barra 50 % no forte + teto "Economia" na mesma peça, e nenhum come o outro.

        MORDIDA: fazer `motores_dos_controles` devolver `{}` sempre — o forte
        deixa de perder a metade e o assert nomeia os dois números.
        """
        from hefesto_dualsense4unix.core.backend_pydualsense import (
            PyDualSenseController,
        )

        overrides = {
            BRANCO: ControllerOverrides(
                rumble=ControllerRumbleOverride(
                    policy="economia", motor_forte_pct=50, motor_fraco_pct=100
                )
            )
        }
        save_profile(
            Profile(
                name="Bancada",
                match=MatchAny(),
                rumble=RumbleConfig(policy="balanceado"),
                controllers=overrides,
            )
        )

        # ANDAR 1 — a barra, no caminho do FF do jogo.
        backend_falso = _Backend()
        d = _daemon(perfil_ativo="Bancada", controller=backend_falso)
        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=BRANCO)
        _, weak_pos_barra, strong_pos_barra = backend_falso.rumbles[0]
        assert (weak_pos_barra, strong_pos_barra) == (200, 100), (
            "a barra do motor forte não cortou a metade no primeiro andar"
        )

        # ANDAR 2 — o teto por controle, dentro do backend REAL. O fator é o
        # do produto (`_controllers_to_rumble_scales`), nunca digitado aqui.
        escalas = _controllers_to_rumble_scales(
            overrides, RumbleConfig(policy="balanceado")
        )
        assert BRANCO in escalas, (
            "o teto por controle sumiu do mapa — a barra APAGOU o teto, que é "
            "exatamente o que a sprint proíbe"
        )
        real = PyDualSenseController(evdev_reader=_null_evdev())
        h1, h2 = _FakeHandle(), _FakeHandle()
        real._handles = {KEY_1: h1, KEY_2: h2}
        real._primary_key = KEY_1
        real.set_rumble_scales(escalas)
        real.set_rumble_for(BRANCO, weak=weak_pos_barra, strong=strong_pos_barra)

        fator = escalas[BRANCO]
        assert h1.right_motor == [int(200 * fator)], "o teto não pegou o motor fraco"
        assert h1.left_motor == [int(100 * fator)], (
            "o motor forte tinha de chegar com a barra JÁ aplicada e o teto por "
            "cima — os dois fatores, na ordem degrau → barra → teto"
        )
        assert h2.right_motor == [] and h2.left_motor == []


# ---------------------------------------------------------------------------
# 4. A BORDA DO ESQUEMA
# ---------------------------------------------------------------------------


class TestABordaDoEsquema:
    @pytest.mark.parametrize("campo", ["motor_forte_pct", "motor_fraco_pct"])
    @pytest.mark.parametrize("valor", [101, -1, 1000])
    def test_fora_da_faixa_morre_no_load(self, campo: str, valor: int) -> None:
        """A recusa é na BORDA, e a mensagem EXPLICA — nunca o literal cru.

        MORDIDA: apagar o `_validate_barras_de_motor`. O 101 entra no disco e
        um motor passa a amplificar por uma porta que ninguém desenhou.
        """
        with pytest.raises(ValueError) as erro:
            ControllerRumbleOverride.model_validate({campo: valor})
        assert campo in str(erro.value)
        assert "SEGUNDO fator" in str(erro.value), (
            "a recusa tem de dizer POR QUE não passa de 100, senão é literal cru"
        )

    @pytest.mark.parametrize("valor", [0, 1, 50, MOTOR_PCT_MAX])
    def test_a_faixa_inteira_entra(self, valor: int) -> None:
        o = ControllerRumbleOverride(motor_forte_pct=valor, motor_fraco_pct=valor)
        assert pcts_dos_motores(o) == (valor, valor)

    def test_a_chave_nova_nao_aparece_em_perfil_que_nao_a_usa(
        self, perfis: Path
    ) -> None:
        """Downgrade continua possível: `exclude_unset` mantém o arquivo igual.

        Um `extra="forbid"` de um hefesto ANTIGO rejeitaria o perfil inteiro se
        `save` passasse a gravar `"motor_forte_pct": null` em todo override —
        é o defeito medido em PERFIL-02 e em SOM-02/E4.

        MORDIDA: trocar o `exclude_unset=True` do `_payload_do_perfil` por
        `exclude_unset=False`. As duas chaves aparecem e este assert pega.
        """
        import json

        caminho = save_profile(
            Profile(
                name="Velho",
                match=MatchAny(),
                controllers={
                    BRANCO: ControllerOverrides(
                        rumble=ControllerRumbleOverride(policy="max")
                    )
                },
            )
        )
        dele = json.loads(caminho.read_text())["controllers"][BRANCO]["rumble"]
        assert "motor_forte_pct" not in dele and "motor_fraco_pct" not in dele, (
            f"o override sem opinião ganhou chave nova no disco: {dele}"
        )


# ---------------------------------------------------------------------------
# 5. O CACHE DO MAPA
# ---------------------------------------------------------------------------


class TestOCacheDoMapa:
    def test_o_disco_e_lido_uma_vez_por_perfil(
        self, perfis: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O FF do jogo chega a centenas de Hz — o disco não pode ir junto.

        MORDIDA: apagar o `if isinstance(cache, tuple)` de
        `_motores_do_perfil_ativo`. As dez chamadas viram dez leituras e a
        contagem reprova.
        """
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        leituras: list[str] = []
        original = loader_module.load_profile

        def _contando(nome: str) -> Any:
            leituras.append(nome)
            return original(nome)

        monkeypatch.setattr(loader_module, "load_profile", _contando)
        d = _daemon(perfil_ativo="Bancada")
        for _ in range(10):
            gp_mod.apply_game_rumble(d, 100, 100, target_uniq=BRANCO)

        assert len(leituras) == 1, f"o disco foi lido {len(leituras)} vezes"

    def test_trocar_de_perfil_troca_o_mapa(self, perfis: Path) -> None:
        """O cache é chaveado pelo NOME do perfil ativo.

        MORDIDA: guardar só o mapa (sem o nome) no `_rumble_motores_pct`. O
        segundo perfil passa a herdar a barra do primeiro e reprova.
        """
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        save_profile(Profile(name="Limpo", match=MatchAny()))
        backend = _Backend()
        d = _daemon(perfil_ativo="Bancada", controller=backend)

        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=BRANCO)
        d.store.active_profile = "Limpo"
        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=BRANCO)

        assert backend.rumbles == [(BRANCO, 200, 100), (BRANCO, 200, 200)]

    def test_invalidar_o_cache_e_uma_linha(self, perfis: Path) -> None:
        """`daemon._rumble_motores_pct = None` faz a barra nova valer AGORA.

        É a linha que o método `rumble.motores.set` de `daemon/ipc_handlers.py`
        tem de rodar ao gravar — sem ela a barra nova só entra na próxima troca
        de perfil, e a tela diria "aplicado" sobre um motor que não mudou. Este
        teste é o CONTRATO daquela linha, escrito de fora, porque
        `ipc_handlers.py` não é da posse desta sprint.

        MORDIDA: fazer o cache ignorar o `None` (ex.: só recarregar quando o
        nome mudar). O segundo par volta 100 no forte e reprova.
        """
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        backend = _Backend()
        d = _daemon(perfil_ativo="Bancada", controller=backend)
        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=BRANCO)

        _grava("Bancada", motor_forte_pct=100, motor_fraco_pct=100)
        d._rumble_motores_pct = None  # a linha inteira
        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=BRANCO)

        assert backend.rumbles == [(BRANCO, 200, 100), (BRANCO, 200, 200)]

    def test_o_endereco_com_dois_pontos_casa_a_peca(self, perfis: Path) -> None:
        """`AA:BB:...` e `aabbcc...` são a MESMA peça — normalizar é a cura.

        Sem a normalização o mapa fica mudo e ninguém vê: o par sai o de
        sempre, e a tela diz "aplicado".

        MORDIDA: fazer `_chave_da_peca` devolver o argumento cru.
        """
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        backend = _Backend(uniqs=(KEY_1,))
        d = _daemon(perfil_ativo="Bancada", controller=backend)

        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=KEY_1)

        assert backend.rumbles == [(KEY_1, 200, 100)]


# ---------------------------------------------------------------------------
# 6. A RÉGUA SABE RECUSAR — as funções puras, nos dois sentidos
# ---------------------------------------------------------------------------


class TestARéguaSabeRecusar:
    def test_o_mapa_ignora_quem_nao_opinou(self) -> None:
        entrada = {
            BRANCO: ControllerOverrides(rumble=ControllerRumbleOverride(policy="max")),
            PRETO: ControllerOverrides(),
        }
        assert motores_dos_controles(entrada) == {}

    def test_o_mapa_ignora_quem_escreveu_cem_nos_dois(self) -> None:
        """`100/100` no disco é escolha, mas no APARELHO é o par neutro.

        Deixá-lo no mapa faria o consumidor distinguir dois casos que se
        comportam igual — e o irmão `_controllers_to_rumble_scales` já corta o
        `1.0` pela mesma razão.
        """
        entrada = {
            BRANCO: ControllerOverrides(
                rumble=ControllerRumbleOverride(
                    motor_forte_pct=MOTOR_PCT_PADRAO, motor_fraco_pct=MOTOR_PCT_PADRAO
                )
            )
        }
        assert motores_dos_controles(entrada) == {}

    def test_o_mapa_pega_quem_opinou(self) -> None:
        entrada = {
            BRANCO: ControllerOverrides(
                rumble=ControllerRumbleOverride(motor_forte_pct=50)
            ),
            PRETO: ControllerOverrides(
                rumble=ControllerRumbleOverride(motor_fraco_pct=0)
            ),
        }
        assert motores_dos_controles(entrada) == {BRANCO: (50, 100), PRETO: (100, 0)}

    def test_sem_secao_rumble_o_par_e_neutro(self) -> None:
        assert pcts_dos_motores(None) == (MOTOR_PCT_PADRAO, MOTOR_PCT_PADRAO)

    def test_mapa_vazio_e_none_dao_o_mesmo(self) -> None:
        assert motores_dos_controles(None) == {}
        assert motores_dos_controles({}) == {}


# ---------------------------------------------------------------------------
# 7. O DEGRAU NÃO ESCAPA SOZINHO
# ---------------------------------------------------------------------------


class TestODegrauNaoEscapaSozinho:
    """A multiplicação mora num lugar só, e é esta régua que impede o segundo.

    Se `apply_game_rumble` voltar a chamar `_game_rumble_mult` direto — que é o
    estado de antes desta sprint, e um merge desatento o restaura —, o degrau
    chega ao motor SEM a barra, e nenhum teste de valor fica vermelho quando o
    perfil da suíte não tem barra escrita. A leitura por AST pega a chamada.
    """

    def test_apply_game_rumble_passa_pelo_par(self) -> None:
        arvore = ast.parse(
            textwrap.dedent(inspect.getsource(gp_mod.apply_game_rumble))
        )
        chamadas = {
            no.func.id
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
        }
        assert "_mults_por_motor" in chamadas, (
            "`apply_game_rumble` deixou de compor o par por motor"
        )
        assert "_game_rumble_mult" not in chamadas, (
            "`apply_game_rumble` voltou a chamar o DEGRAU direto — o degrau vai "
            "ao motor sem a barra dela, e é o defeito que esta régua existe "
            "para não deixar voltar"
        )

    def test_o_par_e_o_degrau_vezes_a_barra(self, perfis: Path) -> None:
        """A conta, isolada da escrita: `_mults_por_motor` sozinho."""
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        d = _daemon(policy="max", perfil_ativo="Bancada")

        fraco, forte = gp_mod._mults_por_motor(d, 0.0, BRANCO)

        degrau = _degrau("max")
        assert fraco == pytest.approx(degrau)
        assert forte == pytest.approx(degrau * 0.5)
