"""MESA-NO-MEIO-DO-LOTE-01 — dois controles acendendo o MESMO jogador.

**O que ela viu, 27/08/2026**, com os quatro DualSense dela no rádio: dois
acendiam **jogador 1**, um acendia 2, outro acendia 3, e **ninguém acendia 4**.

O journal do daemon guardou a cena inteira, e ela fecha na aritmética. Às
15:36:18 saíram quatro ``gatilho_da_cor_escrito`` no mesmo lote, com os padrões
canônicos de player-LED (``core/led_control.py``)::

    key=<3º da fila>  players=(F, T, F, T, F)   -> jogador 2
    key=<2º da fila>  players=(F, F, T, F, F)   -> jogador 1
    key=<4º da fila>  players=(T, F, T, F, T)   -> jogador 3
    key=<1º da fila>  players=(F, F, T, F, F)   -> jogador 1   <- colisão

Quatro segundos antes (15:36:14) o mesmo lote saíra com **três** controles: o
1º da fila tinha caído do rádio. O handle dele voltou às 15:36:16 — **antes**
do próximo ``sync_connected``, que bate a cada 2 s.

## A causa, e ela é de ORDEM, não de conta

O provider de identidade (``make_auto_output_provider``) não é uma leitura
pura: ele ADMITE na mesa o controle que pergunta (atribuição lazy do R-14 §1).
E toda escrita de LED do backend é um LOTE — ``enviar_gatilho_da_cor`` resolve
``_merged_desired_for_key`` de várias chaves de uma vez, sob o mesmo
``_io_lock``.

Então: os TRÊS primeiros do lote foram numerados com a mesa de três (1, 2, 3);
o quarto, ao ser resolvido, entrou na mesa e foi numerado com a mesa de quatro
— e como ele é o primeiro da fila de chegada, o número dele é 1. Dois "jogador
1", ninguém no 4, e assim ficou por 28 minutos: a lâmpada só é reescrita quando
algo acontece.

## As duas curas, e a mordida de cada uma

1. **A mesa é assentada ANTES do primeiro número do lote**
   (``PyDualSenseController._assentar_mesa_locked``). É a causa raiz: a mesa
   deixa de se mexer no meio, e todos do lote leem a mesma tabela.
   — mordida em :class:`TestOLoteNaoNumeraComAMesaPelaMetade`.

   **SUBSTITUÍDO em 06/09/2026 (QUATRO-NA-MESA-01 §1).** A frase acima dizia
   que *"o provider de identidade não é uma leitura pura: ele ADMITE na mesa o
   controle que pergunta"* — e isso deixou de ser verdade, de propósito. Era
   essa autoadmissão o SEGUNDO escritor de ``_connected``: o tique de 2 s
   tirava da mesa quem piscou no rádio, a leitura de cor a 10 Hz devolvia, e o
   número dos outros três ia e voltava sem parar. Hoje o provider chama
   ``numero_da_lampada(autoridade_de_presenca=False)`` e quem readmite é só o
   tique. A mesa não pode mais se mexer no meio de um lote — não porque foi
   assentada antes, mas porque uma leitura não a move. O ``_assentar_mesa_locked``
   deixou de ter efeito sobre a presença e sobrevive só como apresentação de
   ESTREANTES (D1: um controle que nunca teve lugar na fila ganha o dele na
   primeira consulta).
2. **Quem o registro tem como AUSENTE não acende número de jogador**
   (``ControllerIdentityRegistry.numero_da_lampada``). O lugar GRAVADO do
   ausente responde *"que número ele teria se estivesse na mesa"* — é a
   resposta certa para um rótulo e a errada para uma lâmpada, porque é um
   número de outro espaço de numeração.
   — mordida em :class:`TestAusenteNaoAcendeNumero`.

E a trava anti-duplicata deixa de ser um degrau de saída (o ``usados`` do
co-op) e passa a ser ESTRUTURAL, no ponto único onde um endereço vira número
(``_numeros_da_mesa_locked``) — mordida em :class:`TestONumeroENaMesaEUnico`.

Nenhum endereço real: faixa forjada ``aa:bb:cc:…`` com os octetos 4 e 5
zerados, a mesma allowlist de ``tests/unit/test_anonimato_de_fixtures.py``. A
ORDEM reproduz a mesa dela; os bytes, não.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController
from hefesto_dualsense4unix.core.led_control import player_led_pattern
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
    make_auto_output_provider,
)
from tests.unit.test_backend_multi_controller import _FakeHandle, _null_evdev

# --- a mesa dela, mascarada -------------------------------------------------

#: Os quatro DualSense, na ordem da FILA GRAVADA do `controllers.json` dela
#: (rank 1..4). O primeiro é o que caiu e voltou.
KEYS = (
    "AA:BB:CC:00:00:01",
    "AA:BB:CC:00:00:02",
    "AA:BB:CC:00:00:03",
    "AA:BB:CC:00:00:04",
)
UNIQS = tuple(k.replace(":", "").lower() for k in KEYS)
CAIU_E_VOLTOU, SEGUNDO, TERCEIRO, QUARTO = UNIQS

BOOT = "boot-teste-mesa-no-meio-do-lote"


class Relogio:
    """Relógio monotônico de mentira — as ondas de chegada sem `sleep`."""

    def __init__(self, inicio: float = 1000.0) -> None:
        self.agora = inicio

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


@pytest.fixture
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`config_dir` em tmp — nenhum teste daqui toca o `controllers.json` dela."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


def mesa_de_quatro(relogio: Relogio) -> ControllerIdentityRegistry:
    """Os quatro na mesa, cada um na sua ONDA — a fila do momento é 1, 2, 3, 4.

    Um de cada vez, com intervalo maior que `JANELA_DE_ONDA_SEC`, porque é
    assim que ela pareia: um controle, depois o outro. Com todos na mesma onda
    o desempate seria o gravado, e o cenário do defeito ficaria indistinguível
    de um empate — que é outro caso, e não é este.
    """
    reg = ControllerIdentityRegistry(clock=relogio)
    na_mesa: list[str] = []
    for uniq in UNIQS:
        na_mesa.append(uniq)
        reg.sync_connected(list(na_mesa))
        relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)
    return reg


def backend_com_os_quatro() -> tuple[PyDualSenseController, dict[str, _FakeHandle]]:
    """Backend com os quatro handles abertos, na ordem da fila."""
    inst = PyDualSenseController(evdev_reader=_null_evdev())
    handles = {key: _FakeHandle() for key in KEYS}
    inst._handles = dict(handles)  # type: ignore[assignment]
    inst._primary_key = KEYS[0]
    return inst, handles


def o_link_caiu_e_voltou(
    reg: ControllerIdentityRegistry, inst: PyDualSenseController
) -> None:
    """A cena de 15:36, em duas linhas.

    O batimento vê TRÊS controles (o primeiro da fila caiu do rádio) e o
    handle do que caiu volta logo depois — antes do batimento seguinte, e
    por isso NO FIM do dict de handles, que é a ordem em que o lote resolve.
    """
    reg.sync_connected([SEGUNDO, TERCEIRO, QUARTO])
    voltou = inst._handles.pop(KEYS[0])
    inst._handles[KEYS[0]] = voltou


def o_tique_viu_todos(reg: ControllerIdentityRegistry) -> None:
    """O batimento seguinte do `lifecycle`, com os quatro de volta na mesa.

    QUATRO-NA-MESA-01 §1 (06/09/2026): readmitir passou a ser ato do TIQUE.
    A leitura de cor não readmite mais ninguém — era ela o segundo escritor
    de `_connected`, e é ela que fazia o número dos OUTROS piscar 10x por
    segundo enquanto um controle bouncava no rádio.
    """
    reg.sync_connected(list(UNIQS))


def padroes_do_lote(
    inst: PyDualSenseController,
) -> dict[str, tuple[bool, bool, bool, bool, bool] | None]:
    """O lote de escrita, como o backend o monta: uma passada, todas as chaves.

    É a forma EXATA de `enviar_gatilho_da_cor` e de `reassert_resolved_outputs`
    — a lista inteira resolvida sob o mesmo lock, antes de qualquer byte sair.
    """
    return {
        key: inst._merged_desired_for_key(key).player_leds for key in inst._handles
    }


class TestOLoteNaoNumeraComAMesaPelaMetade:
    """A causa raiz: a mesa não pode se mexer entre o 1º e o 4º do lote.

    **QUATRO-NA-MESA-01 §1, 06/09/2026 — o dono da READMISSÃO mudou, e as
    asserções daqui foram remedidas por isso.** Até esta data quem punha o
    controle de volta na mesa era a própria LEITURA de cor (o
    ``slot_for(assign=True)`` de dentro do provider), e era ela que fechava o
    buraco do "ninguém no 4" dentro do próprio lote. Só que essa mesma
    autoadmissão é o defeito 1 desta sprint: o tique de 2 s tirava, a leitura
    a 10 Hz devolvia, e o número dos OUTROS ia e voltava sem parar — *"quando
    um controle pisca, os outros trocam de cor e de número sozinhos"*.

    O que a cura preserva, e é a queixa dela inteira: **nenhum número se
    repete, em instante nenhum.** O que ela troca é o preenchimento do
    buraco: quem voltou fica **sem opinião** (``None`` — o contrato que o
    ``numero_da_lampada`` já publicava desde 27/08) até o TIQUE vê-lo, e aí
    a mesa fecha 1..4. Um buraco de ≤2 s no lugar de um pisca-pisca contínuo.
    """

    def test_quatro_controles_quatro_numeros(
        self, config_isolado: Path
    ) -> None:
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)
        inst, _ = backend_com_os_quatro()
        inst.set_auto_output_provider(make_auto_output_provider(reg))

        o_link_caiu_e_voltou(reg, inst)
        padroes = padroes_do_lote(inst)

        # A queixa dela, em uma linha: nenhum número pode se repetir.
        numerados = [v for v in padroes.values() if v is not None]
        assert len(set(numerados)) == len(numerados), (
            "dois controles no mesmo jogador: "
            f"{ {k: v for k, v in padroes.items()} }"
        )
        # E quem voltou não inventa número enquanto o tique não o vê: sem
        # opinião é o que impede o número dele de colidir com o de um presente.
        assert padroes[KEYS[0]] is None

        # O tique passa (≤2 s) e a mesa fecha 1..4 — sem buraco e sem colisão.
        o_tique_viu_todos(reg)
        padroes = padroes_do_lote(inst)
        assert set(padroes.values()) == {player_led_pattern(n) for n in (1, 2, 3, 4)}

    def test_quem_voltou_recupera_o_numero_que_era_dele(
        self, config_isolado: Path
    ) -> None:
        """Não basta não colidir: quem voltou é o 1º da fila e volta ao 1 (D2).

        Sem esta metade, "não repetir" seria satisfeito por qualquer permuta —
        inclusive mandando quem voltou para o fim da fila, que é o defeito de
        ORDEM DE WAKE que o R-15 arrancou em 23/07.
        """
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)
        inst, _ = backend_com_os_quatro()
        inst.set_auto_output_provider(make_auto_output_provider(reg))

        o_link_caiu_e_voltou(reg, inst)
        o_tique_viu_todos(reg)
        padroes = padroes_do_lote(inst)

        assert padroes[KEYS[0]] == player_led_pattern(1)
        assert padroes[KEYS[1]] == player_led_pattern(2)
        assert padroes[KEYS[2]] == player_led_pattern(3)
        assert padroes[KEYS[3]] == player_led_pattern(4)

    def test_a_cor_tambem_sai_de_uma_mesa_so(self, config_isolado: Path) -> None:
        """A colisão não é só do número: a cor sai do MESMO slot (COR-03).

        No journal dela a cor escapou porque vinha de um override por-uniq do
        perfil; com a paleta automática ligada, dois controles ficariam da
        mesma cor pelo mesmo caminho.
        """
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)
        inst, _ = backend_com_os_quatro()
        inst.set_auto_output_provider(make_auto_output_provider(reg))

        o_link_caiu_e_voltou(reg, inst)
        cores = [inst._merged_desired_for_key(key).led for key in inst._handles]

        # Na janela, quem voltou não tem cor automática (None = sem opinião);
        # os TRÊS que o tique viu têm três cores distintas. Contar o `None`
        # como uma quarta cor faria este teste passar sem medir nada.
        pintadas = [c for c in cores if c is not None]
        assert len(pintadas) == 3
        assert len(set(pintadas)) == 3, f"duas lightbars da mesma cor: {cores}"

        o_tique_viu_todos(reg)
        cores = [inst._merged_desired_for_key(key).led for key in inst._handles]
        assert len(set(cores)) == 4, f"duas lightbars da mesma cor: {cores}"


class TestAMesaEApresentadaNaOrdemDosHandles:
    """A cura não pode apresentar a mesa em ordem de HASH (R-24).

    Cicatriz da própria entrega: a primeira versão de `_assentar_mesa_locked`
    percorria o `frozenset` que usa para saber SE a mesa mudou. Dois controles
    VIRGENS (sem lugar na fila) passaram a receber lugar em ordem de hash, e o
    segundo da mesa nasceu Controle 1 — o defeito que o R-24 já tinha pago no
    `_sync_identity_registry`, com a mesma frase: *"nunca passar um `set`, que
    numeraria por hash"*.
    """

    def test_o_primario_ganha_o_primeiro_lugar_da_fila(
        self, config_isolado: Path
    ) -> None:
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        inst, _ = backend_com_os_quatro()
        inst.set_auto_output_provider(make_auto_output_provider(reg))

        # Ninguém tem lugar ainda: quem numera é a apresentação da mesa.
        inst._merged_desired_for_key(KEYS[0])

        assert reg.snapshot() == {u: i + 1 for i, u in enumerate(UNIQS)}


class TestAusenteNaoAcendeNumero:
    """A trava que faltava: o lugar GRAVADO nunca vira lâmpada."""

    def test_a_lampada_recusa_quem_nao_esta_na_mesa(
        self, config_isolado: Path
    ) -> None:
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)
        reg.sync_connected([SEGUNDO, TERCEIRO, QUARTO])

        # Quem está na mesa acende 1..3 — a contagem fecha sem o ausente.
        assert reg.numero_da_lampada(SEGUNDO, assign=False) == 1
        assert reg.numero_da_lampada(TERCEIRO, assign=False) == 2
        assert reg.numero_da_lampada(QUARTO, assign=False) == 3
        # E o ausente não acende NADA. Era aqui que ele acendia 1 — o mesmo
        # 1 que o segundo da fila já estava acendendo.
        assert reg.numero_da_lampada(CAIU_E_VOLTOU, assign=False) is None

    def test_a_pergunta_continua_respondida(self, config_isolado: Path) -> None:
        """`slot_for` NÃO muda: o rótulo do ausente continua sendo o dele.

        As duas respostas são verdadeiras, cada uma no seu domínio — o defeito
        era a lâmpada ler a do outro. Se `slot_for` também passasse a devolver
        None, a GUI perderia o "Controle 1" de um controle que só está
        desligado, que é decisão medida (NUM-01/D2) e não se apaga.
        """
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)
        reg.sync_connected([SEGUNDO, TERCEIRO, QUARTO])

        assert reg.slot_for(CAIU_E_VOLTOU, assign=False) == 1

    def test_com_assign_a_atribuicao_acontece_do_mesmo_jeito(
        self, config_isolado: Path
    ) -> None:
        """R-14 §1: atribuir lugar é IDENTIDADE, e continua acontecendo aqui.

        Sem isto, o piso que os externos leem (`_ds_reserve`) voltaria a
        mentir — o defeito "não existe Controle 1" da auditoria de 25/07.
        """
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        novo = "aabbcc0000fe"

        assert reg.numero_da_lampada(novo) == 1
        assert novo in reg.snapshot()
        assert novo in reg.snapshot_connected()


class TestONumeroENaMesaEUnico:
    """A trava anti-duplicata vira ESTRUTURAL, no ponto único da numeração."""

    def test_a_tabela_da_mesa_nunca_repete_numero(
        self, config_isolado: Path
    ) -> None:
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)

        tabela = reg.numeros_da_mesa()

        assert set(tabela) == set(UNIQS)
        assert sorted(tabela.values()) == [1, 2, 3, 4]

    def test_a_tabela_ignora_quem_saiu_da_mesa(self, config_isolado: Path) -> None:
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)
        reg.sync_connected([SEGUNDO, TERCEIRO, QUARTO])

        tabela = reg.numeros_da_mesa()

        assert CAIU_E_VOLTOU not in tabela
        assert sorted(tabela.values()) == [1, 2, 3]

    def test_a_lampada_e_a_tabela_dizem_a_mesma_coisa(
        self, config_isolado: Path
    ) -> None:
        """Uma fonte só: se as duas pudessem divergir, o defeito voltaria."""
        relogio = Relogio()
        reg = mesa_de_quatro(relogio)

        tabela = reg.numeros_da_mesa()

        for uniq in UNIQS:
            assert reg.numero_da_lampada(uniq, assign=False) == tabela[uniq]
