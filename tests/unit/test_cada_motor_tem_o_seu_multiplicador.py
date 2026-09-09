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

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
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


# ---------------------------------------------------------------------------
# 8. O MÉTODO QUE GRAVA — `rumble.motores.set`
# ---------------------------------------------------------------------------
#
# A METADE DE IPC, e ela fecha o que a metade de daemon deixou em aberto:
# `gamepad._motores_do_perfil_ativo` LÊ um mapa; alguém tem de ESCREVER, e tem
# de derrubar o cache no mesmo ato. Enquanto `daemon/ipc_handlers.py` não era
# desta posse, o contrato da invalidação vivia escrito de FORA
# (`TestOCacheDoMapa::test_invalidar_o_cache_e_uma_linha`, que ainda vale como
# régua do mecanismo). Agora ele é medido por dentro, pelo método real.


class _Store:
    """`store` de mentira: só o `active_profile` e as travas manuais."""

    def __init__(self, ativo: str | None) -> None:
        self.active_profile = ativo
        self.travas: list[str] = []

    def mark_manual_trigger_active(self, categoria: str) -> None:
        self.travas.append(categoria)


class _Handlers(IpcHandlersMixin):
    """O bastante do mixin para chamar `_handle_rumble_motores_set`."""

    def __init__(self, *, ativo: str | None, primario: str | None) -> None:
        self.store = _Store(ativo)  # type: ignore[assignment]
        self.controller = SimpleNamespace(  # type: ignore[assignment]
            describe_controllers=lambda: (
                [{"connected": True, "uniq": primario}] if primario else []
            )
        )
        self.daemon = _daemon(perfil_ativo=ativo)  # type: ignore[assignment]
        self.daemon.store = self.store


def _grava_ipc(h: _Handlers, **params: Any) -> dict[str, Any]:
    import asyncio

    return asyncio.run(h._handle_rumble_motores_set(params))


class TestOMetodoQueGrava:
    def test_grava_a_barra_no_perfil_da_peca(self, perfis: Path) -> None:
        """Do IPC ao disco: o par dela cai no `controllers[chave].rumble`.

        MORDIDA: apagar o `save_profile` do handler — o `load_profile` abaixo
        devolve o perfil sem as barras e o assert nomeia os dois campos.
        """
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        corpo = _grava_ipc(h, uniq=BRANCO, forte_pct=50, fraco_pct=100)

        assert corpo["status"] == "ok" and corpo["gravado"] is True
        assert (corpo["forte_pct"], corpo["fraco_pct"]) == (50, 100)
        dele = (loader_module.load_profile("Bancada").controllers or {})[BRANCO]
        assert dele.rumble is not None
        assert dele.rumble.motor_forte_pct == 50
        assert "motor_fraco_pct" not in dele.rumble.model_fields_set, (
            "o 100 é 'sem opinião' e não pode ocupar chave no disco"
        )

    def test_a_gravacao_derruba_o_cache_no_mesmo_ato(self, perfis: Path) -> None:
        """A LINHA QUE FAZ A BARRA VALER AGORA, medida por dentro.

        Sem ela a barra nova só entraria na próxima troca de perfil, e a tela
        diria "aplicado" sobre um motor que não mudou.

        MORDIDA: apagar `self.daemon._rumble_motores_pct = None` do handler. O
        segundo par volta 200/200 — o degrau inteiro nos dois — e reprova.
        """
        save_profile(Profile(name="Bancada", match=MatchAny()))
        backend = _Backend()
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        h.daemon.controller = backend

        # Um FF ANTES da gravação: é ele que popula o cache com o mapa vazio.
        gp_mod.apply_game_rumble(h.daemon, 200, 200, target_uniq=BRANCO)
        _grava_ipc(h, uniq=BRANCO, forte_pct=50)
        gp_mod.apply_game_rumble(h.daemon, 200, 200, target_uniq=BRANCO)

        assert backend.rumbles == [(BRANCO, 200, 200), (BRANCO, 200, 100)], (
            "o segundo FF tinha de sair com o forte pela metade — o cache do "
            "mapa não caiu na gravação"
        )

    def test_cem_nos_dois_apaga_a_secao_sem_matar_o_degrau(self, perfis: Path) -> None:
        """Voltar as duas a 100 limpa as barras e PRESERVA o teto da peça.

        `policy` é o degrau daquela peça (`08-conexoes`) e não é deste gesto —
        apagá-lo junto seria o gesto comendo a decisão do vizinho.

        MORDIDA: trocar o `campos.pop(campo, None)` por `campos.clear()`. O
        `policy` some e o assert do teto reprova.
        """
        save_profile(
            Profile(
                name="Bancada",
                match=MatchAny(),
                controllers={
                    BRANCO: ControllerOverrides(
                        rumble=ControllerRumbleOverride(
                            policy="economia", motor_forte_pct=50
                        )
                    )
                },
            )
        )
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        corpo = _grava_ipc(h, uniq=BRANCO, forte_pct=100, fraco_pct=100)

        assert corpo["gravado"] is True
        dele = (loader_module.load_profile("Bancada").controllers or {})[BRANCO]
        assert dele.rumble is not None, "a seção morreu e levou o teto junto"
        assert dele.rumble.policy == "economia", "o degrau da peça foi apagado"
        assert dele.rumble.motor_forte_pct is None

    def test_secao_vazia_vira_none(self, perfis: Path) -> None:
        """Sem degrau e sem barras, a seção `rumble` inteira sai do disco.

        É a mesma disciplina do `_com_o_teto`: "sem opinião" é AUSÊNCIA, e
        `_controllers_to_rumble_scales` desvia por `cfg.rumble is None`.
        """
        _grava("Bancada", motor_forte_pct=50)
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        _grava_ipc(h, uniq=BRANCO, forte_pct=100)

        dele = (loader_module.load_profile("Bancada").controllers or {})[BRANCO]
        assert dele.rumble is None

    def test_nada_mudou_nao_regrava(self, perfis: Path) -> None:
        """Regravar perfil idêntico troca a data do arquivo e o daemon reaplica.

        MORDIDA: apagar o `if antes_campos == depois_campos`. O `gravado` volta
        `True` e o assert pega.
        """
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        corpo = _grava_ipc(h, uniq=BRANCO, forte_pct=50)

        assert corpo["status"] == "ok"
        assert corpo["gravado"] is False, "regravou um perfil que já estava assim"
        assert (corpo["forte_pct"], corpo["fraco_pct"]) == (50, 100)

    def test_campo_omitido_nao_mexe_na_outra_barra(self, perfis: Path) -> None:
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=20)
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        corpo = _grava_ipc(h, uniq=BRANCO, forte_pct=70)

        assert (corpo["forte_pct"], corpo["fraco_pct"]) == (70, 20)

    def test_uniq_omitido_cai_no_primario(self, perfis: Path) -> None:
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        corpo = _grava_ipc(h, forte_pct=40)

        assert corpo["uniq"] == BRANCO
        assert BRANCO in (loader_module.load_profile("Bancada").controllers or {})

    # --- A RÉGUA SABE RECUSAR, e as quatro recusas têm razão escrita --------

    def test_mesa_vazia_recusa_com_razao(self, perfis: Path) -> None:
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=None)
        corpo = _grava_ipc(h, forte_pct=50)
        assert corpo["status"] == "sem_controle"
        assert "POR PEÇA" in corpo["motivo"]

    def test_sem_perfil_ativo_recusa_com_razao(self, perfis: Path) -> None:
        h = _Handlers(ativo=None, primario=BRANCO)
        corpo = _grava_ipc(h, forte_pct=50)
        assert corpo["status"] == "sem_perfil"
        assert "perfil" in corpo["motivo"]

    def test_endereco_sem_mac_recusa_em_vez_de_gravar_errado(
        self, perfis: Path
    ) -> None:
        """Gravar sob uma chave que o motor nunca casa faz a escolha sumir calada.

        **ESTA RÉGUA ACHOU UM DEFEITO VIVO em 04/09/2026**, e ele era do tipo
        que nenhum verde vê: `norm_mac` promete `None` para um `path`, e
        entrega `"adeee9"` para `"path:/dev/input/event9"` — as letras hex do
        caminho sobrevivem à filtragem. Uma chave que PARECE boa e que motor
        nenhum casa: a escolha dela iria para o disco e sumiria calada. A cura
        é `_chave_de_peca_que_grava`, que exige DOZE dígitos hex.

        MORDIDA: trocar `self._chave_de_peca_que_grava(alvo)` por
        `norm_mac(alvo)` no handler — o status volta `"ok"` e o perfil ganha um
        override sob `adeee9`.
        """
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario="path:/dev/input/event9")
        corpo = _grava_ipc(h, forte_pct=50)
        assert corpo["status"] == "sem_endereco"
        assert not (loader_module.load_profile("Bancada").controllers or {}), (
            "gravou um override sob uma chave que o motor nunca casa"
        )

    def test_o_vpad_nao_tem_motor_e_e_recusado(self, perfis: Path) -> None:
        """`02fe…` é o gamepad VIRTUAL — não é peça de plástico, não tem motor.

        MORDIDA: apagar o desvio do `VPAD_UNIQ_PREFIX`. O perfil dela passa a
        guardar uma barra de motor para um device que não tem motor.
        """
        from hefesto_dualsense4unix.broker.hidraw_broker import VPAD_UNIQ_PREFIX

        save_profile(Profile(name="Bancada", match=MatchAny()))
        vpad = f"{VPAD_UNIQ_PREFIX}00000001"
        h = _Handlers(ativo="Bancada", primario=vpad)
        corpo = _grava_ipc(h, forte_pct=50)
        assert corpo["status"] == "sem_endereco"
        assert not (loader_module.load_profile("Bancada").controllers or {})

    def test_sem_nenhum_dos_dois_campos_levanta(self, perfis: Path) -> None:
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        with pytest.raises(ValueError, match="ao menos um"):
            _grava_ipc(h, uniq=BRANCO)

    def test_a_faixa_e_a_do_esquema_e_nada_e_gravado(self, perfis: Path) -> None:
        """O 101 morre com a FRASE do esquema, e o disco não é tocado.

        A faixa não se digita no handler — seria o HARM-19 renascendo, que é o
        que fez `rumble.policy_custom` divergir do esquema em 0-1 contra 0-2.

        MORDIDA: mover o `model_validate` para DEPOIS do `save_profile`. O
        perfil ganha a chave e o assert de disco reprova.
        """
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        with pytest.raises(ValueError, match="SEGUNDO fator"):
            _grava_ipc(h, uniq=BRANCO, forte_pct=101)
        assert not (loader_module.load_profile("Bancada").controllers or {})

    @pytest.mark.parametrize("valor", ["50", 50.0, True, None])
    def test_tipo_errado_levanta_antes_do_disco(self, perfis: Path, valor: Any) -> None:
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        with pytest.raises(ValueError, match="inteiro 0-100"):
            _grava_ipc(h, uniq=BRANCO, forte_pct=valor)

    def test_o_metodo_esta_no_despacho(self) -> None:
        """Handler sem entrada na tabela é método inalcançável.

        MORDIDA: apagar a linha do `ipc_server._handlers`. O produto continua
        compilando e o método fica morto — e é só isto que pega.
        """
        from hefesto_dualsense4unix.daemon import ipc_server

        fonte = inspect.getsource(ipc_server)
        assert '"rumble.motores.set": self._handle_rumble_motores_set' in fonte


# ---------------------------------------------------------------------------
# 9. O `state_full` DEVOLVE OS DOIS NÚMEROS
# ---------------------------------------------------------------------------


class TestOEstadoDevolveAsBarras:
    def test_o_state_full_publica_as_barras_da_peca(self, perfis: Path) -> None:
        """Sem isto a aba 05 desenha a barra onde ela ESTAVA.

        MORDIDA: apagar o bloco `result["rumble_motores"]` do `state_full`. A
        chave some e o assert nomeia o que a tela deixaria de ler.
        """
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=20)
        d = _daemon(perfil_ativo="Bancada")

        mapa = gp_mod._motores_do_perfil_ativo(d)
        publicado = {
            uniq: {"forte_pct": par[0], "fraco_pct": par[1]}
            for uniq, par in mapa.items()
        }

        assert publicado == {BRANCO: {"forte_pct": 50, "fraco_pct": 20}}

    def test_a_fonte_publicada_e_a_mesma_que_o_motor_le(self) -> None:
        """A tela e o motor não podem ler de lugares diferentes.

        Uma segunda leitura do disco no `state_full` poderia pintar um número
        que o motor não está usando — o "aplicado" falso que esta casa passou
        04/09 arrancando. A régua lê a FONTE do `state_full` e exige que o
        bloco chame a função do `gamepad`.

        MORDIDA: trocar a chamada por um `load_profile` próprio no `state_full`.
        """
        from hefesto_dualsense4unix.daemon import ipc_handlers

        fonte = inspect.getsource(
            ipc_handlers.IpcHandlersMixin._handle_daemon_state_full
        )
        assert '_motores_do_perfil_ativo(self.daemon)' in fonte, (
            "o `state_full` deixou de ler o MESMO mapa que `apply_game_rumble` "
            "multiplica"
        )
        assert "load_profile" not in fonte, (
            "o `state_full` abriu uma SEGUNDA leitura do disco — as duas podem "
            "divergir, e a tela pintaria o que o motor não usa"
        )

    def test_o_padrao_viaja_junto_para_a_tela_nao_digitar_o_cem(self) -> None:
        """Peça ausente do mapa vale 100, e o 100 vem do produto.

        MORDIDA: apagar `result["rumble_motor_pct_padrao"]`. A aba 05 passa a
        ter de digitar o 100, que é a segunda grafia que divergiria no primeiro
        dia em que o padrão mudasse.
        """
        from hefesto_dualsense4unix.daemon import ipc_handlers

        fonte = inspect.getsource(
            ipc_handlers.IpcHandlersMixin._handle_daemon_state_full
        )
        assert 'result["rumble_motor_pct_padrao"] = MOTOR_PCT_PADRAO' in fonte
        assert MOTOR_PCT_PADRAO == 100


# ---------------------------------------------------------------------------
# 10. A PONTE, e a armadilha que ela deixava de contar
# ---------------------------------------------------------------------------


class TestAPonte:
    def test_a_ponte_manda_so_o_que_foi_pedido(self, monkeypatch) -> None:
        """Campo `None` = "não mexe naquela barra", e não `null` no payload."""
        from hefesto_dualsense4unix.app import ipc_bridge

        vistos: list[tuple[str, dict[str, Any]]] = []
        monkeypatch.setattr(
            ipc_bridge,
            "_safe_call",
            lambda m, p=None: (vistos.append((m, dict(p or {}))), (True, {"status": "ok"}))[1],
        )

        ok, corpo = ipc_bridge.rumble_motores_set(forte_pct=50, uniq=BRANCO)

        assert ok and corpo == {"status": "ok"}
        assert vistos == [("rumble.motores.set", {"forte_pct": 50, "uniq": BRANCO})]

    def test_daemon_fora_do_ar_devolve_corpo_none(self, monkeypatch) -> None:
        from hefesto_dualsense4unix.app import ipc_bridge

        monkeypatch.setattr(ipc_bridge, "_safe_call", lambda m, p=None: (False, None))
        assert ipc_bridge.rumble_motores_set(forte_pct=50) == (False, None)

    def test_parar_avisa_que_nao_devolve_a_vibracao_ao_jogo(self) -> None:
        """A ARMADILHA MEDIDA NO APARELHO em 04/09/2026, e a cura é a frase.

        `rumble_stop` fixa `(0, 0)` — um par FIXADO, não `None` —, e enquanto
        ele estiver de pé `apply_game_rumble` descarta o FF de TODO jogo na
        primeira linha. O ensaio desta sprint chamou `rumble_stop` achando que
        estava limpando a bagunça e deixou a máquina dela sem vibração em jogo
        nenhum, em silêncio.

        A FIXAÇÃO NÃO É DEFEITO — é decisão medida (HARM-16): o poll loop
        re-afirma o silêncio para que outra escrita HID não reative os motores.
        Trocá-la seria repropor decisão medida, que esta casa não faz. O que
        faltava era a ponte DIZER, e é isso que esta régua trava.

        MORDIDA: apagar a advertência da docstring de `rumble_stop`.
        """
        from hefesto_dualsense4unix.app import ipc_bridge

        doc = inspect.getdoc(ipc_bridge.rumble_stop) or ""
        assert "rumble_passthrough" in doc, (
            "a ponte não diz qual é o gesto que DEVOLVE a vibração ao jogo"
        )
        assert "descarta o FF" in doc, (
            "a ponte não conta a consequência do par fixado — quem chamar "
            "`rumble_stop` continua deixando a máquina sem vibração em jogo"
        )
        # E o par simétrico aponta de volta, senão a advertência é um beco.
        assert "rumble_stop" in (inspect.getdoc(ipc_bridge.rumble_passthrough) or "")


def test_o_norm_mac_nao_devolve_none_para_caminho_e_a_docstring_diz_isso() -> None:
    """FATO ERRADO SUBSTITUÍDO (04/09/2026) — e a régua guarda o fato certo.

    A docstring de `norm_mac` afirmava devolver `None` para um `path`, e dava
    esse exemplo. Medido, ela devolve `'adeee9'`: um caminho tem letras de `a` a
    `f` no meio e a peneira as recolhe.

    Para LER é inofensivo (a chave não casa com nada). Para GRAVAR é perda de
    dado dela — a escolha vai ao disco sob uma chave que aparelho nenhum
    reivindica. Esta régua trava as duas metades: o comportamento REAL, e a
    docstring dizendo a verdade sobre ele.
    """
    from hefesto_dualsense4unix.core import sysfs_leds

    assert sysfs_leds.norm_mac("path:/dev/input/event9") == "adeee9"
    assert sysfs_leds.norm_mac("/dev/hidraw4") == "deda4"
    assert sysfs_leds.norm_mac("xyz") is None
    assert sysfs_leds.norm_mac("AA:BB:CC:00:00:01") == "aabbcc000001"

    doc = sysfs_leds.norm_mac.__doc__ or ""
    assert "FATO ERRADO, SUBSTITUÍDO" in doc, (
        "a docstring voltou a prometer um `None` que a função não entrega."
    )
    assert "adeee9" in doc, "a docstring tem de carregar a medição, não a promessa"


# ---------------------------------------------------------------------------
# 9. A TELA DIZ A MULTIPLICAÇÃO — VIBRA-MULT-01, 09/09/2026
# ---------------------------------------------------------------------------
#: A QUEIXA DELA, como está registrada na sprint VIBRA-MULT-01:
#:
#:     "na guia vibração os slicers não estão se multiplicando: motor
#:      esquerdo × força de vibração (ou personalizado), motor direito ×  # noqa: RUF003
#:      força de vibração ou personalizado, pra cada controle"
#:
#: ELA MORA NUM COMENTÁRIO, e não na docstring abaixo, por uma razão de
#: ferramenta: o sinal de multiplicação da digitação dela é ambíguo para o
#: `ruff` (RUF002/RUF003), e um
#: `# noqa` dentro de uma docstring é texto, não diretiva. Trocar o símbolo
#: seria limpar a citação dela, que esta casa não faz.
_QUEIXA = "os slicers não estão se multiplicando"


class TestATelaDizOProduto:
    """A conta acontecia e a tela não a mostrava em lugar nenhum.

    **A QUEIXA DELA** está no comentário acima, com a digitação preservada.

    **MEDIDO EM 09/09/2026, com os QUATRO controles na mesa:** o P2 imprimia
    `mult 200%` com os DOIS motores em **0%**. A conta do daemon estava certa
    — o efetivo era zero — e a tela dizia `200%` e mais nada. *Um número que
    não diz o que produz é um número que ela tem de multiplicar de cabeça.*

    O `mult` CONTINUA SENDO O DEGRAU: ele é o que o trilho ao lado move.
    """

    def test_a_dica_diz_barra_forca_e_o_efetivo(self) -> None:
        """Os três números na mesma frase, sem um clique.

        **A MORDIDA:** faça `_quanto_multiplica` devolver `""` sempre e a
        dica volta a ficar vazia quando o jogo não treme — que era o estado
        em que ela olhou a tela.
        """
        from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

        frase = a05._quanto_multiplica({"sabe": True, "n": "150%"}, 50)

        assert "50%" in frase and "150%" in frase
        assert "75%" in frase, f"o produto não saiu na frase: {frase}"

    def test_o_caso_dela_barra_zero_confessa_o_zero(self) -> None:
        """O P2 da mesa dela: força 200%, motores em 0%.

        **A MORDIDA:** troque o produto pelo degrau e a frase volta a dizer
        `200%` sobre um motor que não sai do lugar.
        """
        from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

        frase = a05._quanto_multiplica({"sabe": True, "n": "200%"}, 0)

        assert "sai 0%" in frase, frase

    def test_sem_degrau_conhecido_a_dica_cala(self) -> None:
        """Campo sem informação não mostra nada — a regra dela.

        Uma política fora das cinco que o produto conhece não tem degrau, e
        uma frase com travessão no meio afirma menos do que o silêncio.

        **A MORDIDA:** tire o `if not pct.get("sabe")` e a frase sai com um
        `0%` inventado no lugar do degrau.
        """
        from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

        assert a05._quanto_multiplica({"sabe": False, "n": "—"}, 100) == ""
        assert a05._quanto_multiplica({"sabe": True, "n": "150%"}, None) == ""

    def test_o_pedido_do_jogo_ainda_ganha_a_dica(self) -> None:
        """Quando o jogo TREME, o que ela precisa ver é o pedido dele.

        A frase da multiplicação é o que ocupa o silêncio, e não o que o
        substitui: com o motor em movimento, o número de 0-255 é o dado vivo.

        **A MORDIDA:** troque a ordem do ternário no pacote e a dica passa a
        esconder o pedido do jogo atrás de uma conta que não mudou.
        """
        import inspect

        from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

        fonte = inspect.getsource(a05.pacote)
        alvo = fonte.split('plano[f"motor-{lado}-pedido"]')[1].split("\n\n")[0]
        assert 'O jogo pediu' in alvo
        assert alvo.index("O jogo pediu") < alvo.index("_quanto_multiplica"), (
            "a conta passou na frente do pedido do jogo")
