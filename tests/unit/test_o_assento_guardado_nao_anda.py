"""O-ASSENTO-GUARDADO-NAO-ANDA-01 — enquanto o lugar está guardado, ninguém troca de número.

A linha 17 das 21 dela (06/09/2026) é o critério de aceitação: *"o P2 sai por
20 segundos, volta como P2, e os outros três não trocam de número"*. Decidida
em 24/09/2026 por delegação (``D-2409-O-ASSENTO-GUARDADO-NAO-ANDA``): dentro
do prazo do lugar guardado ninguém anda; passado o prazo, a NUM-01 volta (um
até N entre quem está na mesa).

As classes são as de produção: o registro de identidade, o backend com quatro
handles (o P1 e o P2 no cabo, o P3 e o P4 no rádio, como na bancada), o
provider da camada automática, a leitura do IPC, o registro dos externos com a
ponte de presença de verdade, o co-op e o plano do jogo. O único dublê é o
handle do ``pydualsense`` (o mesmo ``_FakeHandle`` da suíte) e o relógio.

As três medidas que a sprint pede, e onde cada uma morde:

1. **os quatro com o P2 fora a 20 s** — na tela (``numeros_da_mesa`` e o
   ``player_slot`` do IPC) e no aparelho (o padrão de lâmpadas e a cor que o
   backend resolve), com o P2 no cabo e no rádio;
2. **a volta dele**, como P2;
3. **depois do prazo**, a NUM-01 de volta: os três fecham 1..3.

A MORDIDA: com ``_guardar_o_lugar_locked`` arrancado (a saída não guarda
nada), :class:`TestALinha17` reprova já na primeira asserção do P3.

Nenhum endereço real: faixa forjada ``aa:bb:cc:…`` com os octetos 4 e 5
zerados, a mesma allowlist de ``tests/unit/test_anonimato_de_fixtures.py``.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.core.backend_pydualsense import (
    PRIMARIO_RESERVA_SEC,
    PyDualSenseController,
)
from hefesto_dualsense4unix.core.led_control import (
    player_led_pattern,
    player_slot_color,
)
from hefesto_dualsense4unix.daemon.ipc_handlers import (
    IpcHandlersMixin,
    _NumeroAlvoAusenteError,
    _NumeroForaDaMesaError,
)
from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.coop import (
    CoopManager,
    planejar_a_ordem,
)
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
    ExternalLedSync,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
    make_auto_output_provider,
    prazo_do_lugar_guardado,
)
from tests.unit.test_backend_multi_controller import _FakeHandle, _null_evdev

#: A bancada dela: o P1 e o P2 no cabo, o P3 e o P4 no rádio.
KEYS = (
    "AA:BB:CC:00:00:01",
    "AA:BB:CC:00:00:02",
    "AA:BB:CC:00:00:03",
    "AA:BB:CC:00:00:04",
)
TRANSPORTE = ("USB", "USB", "BT", "BT")
UNIQS = tuple(k.replace(":", "").lower() for k in KEYS)
P1, P2, P3, P4 = UNIQS
#: Um externo (Pro Nintendo / 8BitDo) para a mesa mista.
EXTERNO = "aabbcc0000fe"

BOOT = "boot-teste-o-assento-guardado"

#: O gesto da linha 17: o P2 fica fora vinte segundos.
VINTE_SEGUNDOS = 20.0


class Relogio:
    """Relógio monotônico de mentira — o prazo sem `sleep`."""

    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos

    def passar_o_prazo(self) -> None:
        self.avancar(prazo_do_lugar_guardado() + 1.0)


@pytest.fixture
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`config_dir` em tmp — nada aqui toca o `controllers.json` dela."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


class Mesa:
    """A mesa de quatro com as peças de produção, e os gestos dela."""

    def __init__(self, transportes: tuple[str, ...] = TRANSPORTE) -> None:
        self.transportes = transportes
        self.relogio = Relogio()
        self.reg = ControllerIdentityRegistry(clock=self.relogio)
        self.backend = PyDualSenseController(evdev_reader=_null_evdev())
        self.handles = {
            key: _FakeHandle(transport_name=nome)
            for key, nome in zip(KEYS, transportes, strict=True)
        }
        self.backend._handles = {}  # type: ignore[assignment]
        self.backend.set_auto_output_provider(make_auto_output_provider(self.reg))
        # Ela liga um de cada vez, com mais que uma onda entre um e outro.
        for key in KEYS:
            self.backend._handles[key] = self.handles[key]  # type: ignore[index]
            self.tique()
            self.relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)
        self.backend._primary_key = KEYS[0]
        # A adoção pinta: é o gatilho da cor que solta as lâmpadas.
        self.reg.liberar_as_lampadas()

    def tique(self) -> None:
        """O `_sync_identity_registry` do lifecycle, pela descrição do backend."""
        self.reg.sync_connected(
            [
                str(info["uniq"])
                for info in self.backend.describe_controllers()
                if info.get("connected") and isinstance(info.get("uniq"), str)
            ]
        )

    def sai(self, indice: int) -> None:
        """O controle sai: no cabo o handle fecha; no rádio ele fica, sem link.

        São as duas formas reais — o `connect()` recolhe o handle do cabo no
        hotplug, e o do rádio sobrevive até ≤30 s com `connected` falso.
        """
        key = KEYS[indice]
        if self.transportes[indice] == "USB":
            del self.backend._handles[key]  # type: ignore[attr-defined]
        else:
            self.handles[key].connected = False
        self.tique()

    def volta(self, indice: int) -> None:
        key = KEYS[indice]
        self.handles[key].connected = True
        self.backend._handles[key] = self.handles[key]  # type: ignore[index]
        self.tique()

    def tela(self) -> dict[str, int]:
        """O que a TELA lê: a mesa de agora."""
        return self.reg.numeros_da_mesa()

    def player_slot(self, uniq: str) -> int | None:
        """O `player_slot` que o `state_full` publica — o chip da fita."""
        handlers = IpcHandlersMixin.__new__(IpcHandlersMixin)
        handlers.daemon = SimpleNamespace(identity_registry=self.reg)  # type: ignore[attr-defined]
        return handlers._player_slot_for(uniq)

    def aparelho(self) -> dict[str, tuple[object, object]]:
        """O que o backend resolve para cada aparelho: (lâmpadas, cor da barra)."""
        fora: dict[str, tuple[object, object]] = {}
        for key in self.backend._handles:  # type: ignore[attr-defined]
            if not self.handles[key].connected:
                continue
            saida = self.backend._merged_desired_for_key(key)
            fora[self.backend._key_to_uniq(key) or key] = (saida.player_leds, saida.led)
        return fora


def lampada(numero: int) -> tuple[object, object]:
    return (player_led_pattern(numero), player_slot_color(numero))


TRANSPORTES_DO_P2 = pytest.mark.parametrize(
    "transporte_do_p2", ["USB", "BT"], ids=["p2-no-cabo", "p2-no-radio"]
)


@pytest.mark.usefixtures("config_isolado")
class TestALinha17:
    """A linha 17 dela, literal: o P2 sai por 20 s, volta P2, ninguém anda."""

    @staticmethod
    def _mesa(transporte_do_p2: str) -> Mesa:
        # A linha 17 pede o P2 no RÁDIO; a matriz dela pede os dois.
        return Mesa(("USB", transporte_do_p2, "BT", "BT"))

    @TRANSPORTES_DO_P2
    def test_o_p2_fora_a_20_s_os_outros_tres_nao_andam(
        self, transporte_do_p2: str
    ) -> None:
        mesa = self._mesa(transporte_do_p2)
        mesa.sai(1)
        mesa.relogio.avancar(VINTE_SEGUNDOS)
        mesa.tique()

        assert mesa.tela() == {P1: 1, P3: 3, P4: 4}, "a tela fechou a fila"
        assert [mesa.player_slot(u) for u in (P1, P3, P4)] == [1, 3, 4]
        # O gatilho da cor pode disparar no meio (uma conexão, um jogo): a
        # liberação não tem mudança a soltar, e o aparelho fica onde estava.
        mesa.reg.liberar_as_lampadas()
        assert mesa.aparelho() == {P1: lampada(1), P3: lampada(3), P4: lampada(4)}

    @TRANSPORTES_DO_P2
    def test_o_p2_volta_como_p2(
        self, transporte_do_p2: str
    ) -> None:
        mesa = self._mesa(transporte_do_p2)
        mesa.sai(1)
        mesa.relogio.avancar(VINTE_SEGUNDOS)
        mesa.volta(1)

        assert mesa.tela() == {P1: 1, P2: 2, P3: 3, P4: 4}
        assert mesa.aparelho() == {
            P1: lampada(1), P2: lampada(2), P3: lampada(3), P4: lampada(4)
        }

    @TRANSPORTES_DO_P2
    def test_depois_do_prazo_a_num01_volta(
        self, transporte_do_p2: str
    ) -> None:
        mesa = self._mesa(transporte_do_p2)
        mesa.sai(1)
        mesa.relogio.passar_o_prazo()
        mesa.tique()

        assert mesa.tela() == {P1: 1, P3: 2, P4: 3}, "o prazo passou e a fila não fechou"
        # As lâmpadas esperam a cor (APARELHO-NAO-SE-CONTRADIZ-01): até o
        # gatilho, o aparelho segue com o número de antes…
        assert mesa.aparelho()[P4] == lampada(4)
        # …e a liberação move os dois juntos.
        mesa.reg.liberar_as_lampadas()
        assert mesa.aparelho() == {P1: lampada(1), P3: lampada(2), P4: lampada(3)}

        # E quem volta depois do prazo continua recuperando o dele (D2).
        mesa.volta(1)
        assert mesa.tela() == {P1: 1, P2: 2, P3: 3, P4: 4}

    def test_o_prazo_e_o_do_posto_de_primario(self) -> None:
        """UM dono: o posto do P1 e o lugar dos quatro são a mesma promessa."""
        assert prazo_do_lugar_guardado() == PRIMARIO_RESERVA_SEC
        assert prazo_do_lugar_guardado() > VINTE_SEGUNDOS, (
            "a linha 17 mede 20 s — o prazo tem de cobrir o gesto dela")


@pytest.mark.usefixtures("config_isolado")
class TestOsQuatroLugares:
    """Nunca só o P2: quem quer que saia, no cabo ou no rádio, ninguém anda."""

    @pytest.mark.parametrize("quem_sai", [0, 1, 2, 3], ids=["p1", "p2", "p3", "p4"])
    def test_dentro_do_prazo_ninguem_anda_e_depois_a_fila_fecha(
        self, quem_sai: int
    ) -> None:
        mesa = Mesa()
        mesa.sai(quem_sai)
        mesa.relogio.avancar(VINTE_SEGUNDOS)
        mesa.tique()

        ficaram = [u for i, u in enumerate(UNIQS) if i != quem_sai]
        assert mesa.tela() == {u: UNIQS.index(u) + 1 for u in ficaram}
        assert mesa.reg.slot_for(UNIQS[quem_sai], assign=False) == quem_sai + 1, (
            "o lugar guardado é o dele")

        mesa.relogio.passar_o_prazo()
        assert mesa.tela() == {u: n for n, u in enumerate(ficaram, start=1)}

    def test_quatro_saem_e_o_primeiro_a_voltar_nao_rouba_o_1(self) -> None:
        """A mesa inteira desligada: quem volta dentro do prazo volta ao seu."""
        mesa = Mesa()
        for indice in range(4):
            mesa.sai(indice)
        mesa.relogio.avancar(VINTE_SEGUNDOS)
        mesa.volta(2)
        assert mesa.tela() == {P3: 3}


@pytest.mark.usefixtures("config_isolado")
class TestAMesaMista:
    """A fila é uma só: DualSense e externos guardam o lugar um do outro."""

    @staticmethod
    def _mista(relogio: Relogio) -> tuple[ControllerIdentityRegistry, ExternalIdentityRegistry]:
        ds = ControllerIdentityRegistry(clock=relogio)
        ext = ExternalIdentityRegistry(clock=relogio)
        # A ponte de presença do produto, nos dois sentidos.
        ExternalLedSync(SimpleNamespace(identity_registry=ds), ext)
        ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))
        ds.sync_connected([P1, P2])
        relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)
        piso = max(ds.snapshot().values())
        assert ext.slot_for(EXTERNO, reserve=piso) == 3
        ext.sync_connected([EXTERNO])
        return ds, ext

    def test_o_dualsense_sai_e_o_externo_nao_anda(self) -> None:
        relogio = Relogio()
        ds, ext = self._mista(relogio)
        ds.sync_connected([P1])
        relogio.avancar(VINTE_SEGUNDOS)
        assert ext.peek(EXTERNO) == 3, "o externo andou com o P2 fora"

        relogio.passar_o_prazo()
        assert ext.peek(EXTERNO) == 2

    def test_o_externo_sai_e_o_dualsense_depois_dele_nao_anda(self) -> None:
        relogio = Relogio()
        ds, ext = self._mista(relogio)
        ds.sync_connected([P1, P2, P3])  # o P3 chega DEPOIS do externo
        assert ds.numeros_da_mesa()[P3] == 4
        ext.sync_connected([])
        relogio.avancar(VINTE_SEGUNDOS)
        assert ds.numeros_da_mesa()[P3] == 4, "o DualSense andou com o externo fora"

        relogio.passar_o_prazo()
        assert ds.numeros_da_mesa()[P3] == 3


@pytest.mark.usefixtures("config_isolado")
class TestQuemNaoGuardaLugar:
    """Sem identidade estável não há promessa a honrar (D9/MODO-01)."""

    def test_o_controle_sem_mac_nao_guarda_lugar(self) -> None:
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        sem_mac = "/dev/hidraw7"
        reg.sync_connected([P1, sem_mac])
        relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)
        reg.sync_connected([P1, sem_mac, P3])
        reg.sync_connected([P1, P3])
        assert reg.numeros_da_mesa() == {P1: 1, P3: 2}
        assert reg.guardados() == {}


@pytest.mark.usefixtures("config_isolado")
class TestOGestoDelaTrocaSobreOQueElaVe:
    """O clique dela é TROCA sobre o que ela vê — e ela vê o buraco.

    A regra é de 28/08, e está na aba 04 com todas as letras: *"os dois
    trocam, os outros não se mexem"*. A primeira escrita desta sprint soltava
    o lugar guardado no clique, e a troca saía sobre uma mesa fechada que ela
    não estava vendo — pedir o 3 para o P4 mandava o P3 para o 2, e o 4 que a
    aba oferecia ao P3 voltava recusado como fora da mesa. Conferência de
    24/09/2026.
    """

    def test_o_3_para_o_p4_troca_o_p3_e_o_p4_e_mais_ninguem(self) -> None:
        mesa = Mesa()
        mesa.sai(1)
        assert mesa.tela() == {P1: 1, P3: 3, P4: 4}

        IpcHandlersMixin._set_number_locked(mesa.reg, None, P4, 3)

        assert mesa.tela() == {P1: 1, P3: 4, P4: 3}, "a troca não foi a da tela"
        assert P2 in mesa.reg.guardados(), "o clique fechou o lugar de quem saiu"

    def test_o_4_que_um_ligado_tem_e_troca_e_nao_recusa(self) -> None:
        """A aba desenha o 4 do P4 como troca; o daemon não pode recusá-lo."""
        mesa = Mesa()
        mesa.sai(1)

        IpcHandlersMixin._set_number_locked(mesa.reg, None, P3, 4)

        assert mesa.tela() == {P1: 1, P3: 4, P4: 3}

    def test_o_lugar_vazio_e_troca_com_quem_saiu(self) -> None:
        """O 2 vazio: o P4 senta nele, o P3 não anda, e o P2 volta com o 4."""
        mesa = Mesa()
        mesa.sai(1)

        IpcHandlersMixin._set_number_locked(mesa.reg, None, P4, 2)

        assert mesa.tela() == {P1: 1, P3: 3, P4: 2}, "alguém além do P4 andou"
        mesa.volta(1)
        assert mesa.tela() == {P1: 1, P2: 4, P3: 3, P4: 2}

    def test_o_numero_que_so_o_lugar_guardado_tem_acima_da_conta_e_recusado(
        self,
    ) -> None:
        """O mesmo cinza da aba: acima dos ligados e sem ligado que o tenha."""
        mesa = Mesa()
        mesa.sai(3)  # o P4 sai: o 4 é só do lugar guardado dele

        with pytest.raises(_NumeroForaDaMesaError):
            IpcHandlersMixin._set_number_locked(mesa.reg, None, P1, 4)

        assert mesa.tela() == {P1: 1, P2: 2, P3: 3}
        assert P4 in mesa.reg.guardados()

    def test_quem_saiu_nao_e_alvo_do_clique(self) -> None:
        """O lugar guardado é assento, não coluna: quem saiu não recebe número."""
        mesa = Mesa()
        mesa.sai(1)

        with pytest.raises(_NumeroAlvoAusenteError):
            IpcHandlersMixin._set_number_locked(mesa.reg, None, P2, 1)

        assert mesa.tela() == {P1: 1, P3: 3, P4: 4}

    def test_a_troca_sobrevive_ao_congelamento_da_mesa(self) -> None:
        """A mesa estável congela 4 s depois; a escolha dela fica."""
        mesa = Mesa()
        mesa.sai(1)
        IpcHandlersMixin._set_number_locked(mesa.reg, None, P4, 3)

        mesa.relogio.avancar(id_mod.JANELA_MESA_ESTAVEL_SEC + 1.0)
        mesa.tique()

        assert mesa.tela() == {P1: 1, P3: 4, P4: 3}

    def test_a_troca_com_o_externo_guardado(self) -> None:
        """A fila é uma só: o lugar guardado de um externo também é assento."""
        relogio = Relogio()
        ds, ext = TestAMesaMista._mista(relogio)
        ds.sync_connected([P1, P2, P3])  # o P3 chega depois do externo
        ext.sync_connected([])  # e o externo sai
        assert ds.numeros_da_mesa()[P3] == 4

        IpcHandlersMixin._set_number_locked(ds, ext, P3, 3)

        assert ds.numeros_da_mesa()[P3] == 3, "ela pediu o 3 e a tela mostra outro"
        ext.sync_connected([EXTERNO])
        assert ext.peek(EXTERNO) == 4, "o externo não voltou para o lugar trocado"

    def test_a_troca_de_dois_nao_mexe_em_quem_esta_atras_do_externo_guardado(
        self,
    ) -> None:
        """O P1 e o P2 trocam; o P3, atrás do lugar guardado do externo, fica."""
        relogio = Relogio()
        ds, ext = TestAMesaMista._mista(relogio)
        ds.sync_connected([P1, P2, P3])
        ext.sync_connected([])
        assert ds.numeros_da_mesa() == {P1: 1, P2: 2, P3: 4}

        IpcHandlersMixin._set_number_locked(ds, ext, P2, 1)

        assert ds.numeros_da_mesa() == {P1: 2, P2: 1, P3: 4}, "o P3 andou"

    def test_renumerar_solta_o_lugar_guardado(self) -> None:
        """O "Renumerar agora" é fechar a fila por vontade dela."""
        mesa = Mesa()
        mesa.sai(1)

        IpcHandlersMixin._renumber_locked(mesa.reg, None)

        assert mesa.tela() == {P1: 1, P3: 2, P4: 3}
        assert mesa.reg.guardados() == {}

    def test_renumerar_solta_tambem_o_lugar_do_externo(self) -> None:
        relogio = Relogio()
        ds, ext = TestAMesaMista._mista(relogio)
        ds.sync_connected([P1, P2, P3])
        ext.sync_connected([])

        IpcHandlersMixin._renumber_locked(ds, ext)

        assert ds.numeros_da_mesa()[P3] == 3
        assert ext.lugares_da_mesa() == set(), "o lugar do externo ficou guardado"


@pytest.mark.usefixtures("config_isolado")
class TestGenteNovaRefazAMesa:
    """Quem chega e não é dono de lugar guardado refaz a mesa (um até N).

    Conferência de 24/09/2026. Segurar o novo atrás do buraco quebrava o que a
    NUM-01 protegia: com os quatro na mesa, o P2 sai e outro controle chega —
    o novo nascia 5 (cinco lâmpadas, barra amarela) numa mesa de quatro, e a
    tela, que tem quatro cartões, voltava a contar por posição. A sprint manda
    não mudar o que o lugar vazio quebra.
    """

    NOVO_KEY = "AA:BB:CC:00:00:05"
    NOVO = "aabbcc000005"

    def _chega_o_novo(self, mesa: Mesa, *, tique: bool = True) -> None:
        mesa.handles[self.NOVO_KEY] = _FakeHandle(transport_name="BT")
        mesa.backend._handles[self.NOVO_KEY] = mesa.handles[self.NOVO_KEY]  # type: ignore[index]
        if tique:
            mesa.tique()

    @pytest.mark.parametrize("quem_sai", [0, 1, 2, 3], ids=["p1", "p2", "p3", "p4"])
    def test_a_mesa_cheia_nao_da_o_5_a_quem_chega(self, quem_sai: int) -> None:
        mesa = Mesa()
        mesa.sai(quem_sai)
        mesa.relogio.avancar(5.0)
        self._chega_o_novo(mesa)

        tela = mesa.tela()
        assert sorted(tela.values()) == [1, 2, 3, 4], f"a mesa não fechou: {tela}"
        assert tela[self.NOVO] == 4
        assert mesa.reg.guardados() == {}
        # E o aparelho, depois do gatilho da cor, acende o 4 — não o 5.
        mesa.reg.liberar_as_lampadas()
        assert mesa.aparelho()[self.NOVO] == lampada(4)

    def test_o_novo_que_o_provider_poe_antes_do_tique_que_ve_a_saida(self) -> None:
        """A troca de controle entre dois tiques: o provider de cor põe o novo
        na mesa antes de o tique lento ver a saída — e mesmo assim ninguém
        guarda lugar para o que saiu."""
        mesa = Mesa()
        del mesa.backend._handles[KEYS[1]]  # type: ignore[attr-defined]
        self._chega_o_novo(mesa, tique=False)
        mesa.backend._merged_desired_for_key(self.NOVO_KEY)  # o provider de cor
        mesa.tique()

        assert mesa.tela() == {P1: 1, P3: 2, P4: 3, self.NOVO: 4}
        assert mesa.reg.guardados() == {}

    def test_o_novo_que_o_provider_poe_com_o_lugar_ja_guardado(self) -> None:
        """O hotplug do novo pinta antes do tique: a mesa se refaz ali mesmo."""
        mesa = Mesa()
        mesa.sai(1)
        assert P2 in mesa.reg.guardados()
        self._chega_o_novo(mesa, tique=False)

        mesa.backend._merged_desired_for_key(self.NOVO_KEY)  # o provider de cor

        assert mesa.tela() == {P1: 1, P3: 2, P4: 3, self.NOVO: 4}
        assert mesa.reg.guardados() == {}

    def test_o_controle_sem_serial_que_volta_nao_e_gente_nova(self) -> None:
        """O crachá (O-CONTROLE-SEM-MAC-01) só se resolve no tique lento: o
        provider de cor vê primeiro o caminho cru do P2 que voltou, e isso não
        pode soltar o lugar de ninguém — nem o dele."""
        relogio = Relogio()
        reg = ControllerIdentityRegistry(clock=relogio)
        cru = "/dev/hidraw9"
        reg.set_cracha_provider(lambda u: KEYS[1] if u == cru else None)
        mesa: list[str] = []
        for uniq in (P1, cru, P3, P4):
            mesa.append(uniq)
            reg.sync_connected(mesa)
            relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)
        assert reg.numeros_da_mesa() == {P1: 1, P2: 2, P3: 3, P4: 4}

        reg.sync_connected([P1, P3, P4])  # o P2 sai
        reg.slot_for(cru, autoridade_de_presenca=False)  # e volta pelo provider

        numeros = reg.numeros_da_mesa()
        assert (numeros[P3], numeros[P4]) == (3, 4), "o caminho cru soltou o lugar"
        reg.sync_connected([P1, cru, P3, P4])  # o tique resolve o crachá
        assert reg.numeros_da_mesa() == {P1: 1, P2: 2, P3: 3, P4: 4}

    def test_quem_so_volta_nao_e_gente_nova(self) -> None:
        mesa = Mesa()
        mesa.sai(1)
        mesa.sai(2)
        mesa.relogio.avancar(5.0)
        mesa.volta(2)

        assert mesa.tela() == {P1: 1, P3: 3, P4: 4}, "a volta do P3 soltou o lugar do P2"
        assert P2 in mesa.reg.guardados()

    def test_o_externo_novo_refaz_a_mesa_dos_dualsense(self) -> None:
        relogio = Relogio()
        ds = ControllerIdentityRegistry(clock=relogio)
        ext = ExternalIdentityRegistry(clock=relogio)
        ExternalLedSync(SimpleNamespace(identity_registry=ds), ext)
        ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))
        ds.sync_connected([P1, P2, P3])
        relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)
        ds.sync_connected([P1, P3])
        assert ds.numeros_da_mesa() == {P1: 1, P3: 3}

        ext.sync_connected([EXTERNO])
        ext.slot_for(EXTERNO, reserve=max(ds.snapshot().values()))

        assert ds.numeros_da_mesa() == {P1: 1, P3: 2}
        assert ext.peek(EXTERNO) == 3, "o externo novo nasceu atrás do buraco"

    def test_o_dualsense_novo_refaz_a_mesa_dos_externos(self) -> None:
        relogio = Relogio()
        ds, ext = TestAMesaMista._mista(relogio)
        ext.sync_connected([])  # o externo sai: lugar 3 guardado
        relogio.avancar(id_mod.JANELA_DE_ONDA_SEC * 2)

        ds.sync_connected([P1, P2, P3])

        assert ds.numeros_da_mesa()[P3] == 3, "o DualSense novo nasceu atrás do buraco"
        assert ext.lugares_da_mesa() == set()


@pytest.mark.usefixtures("config_isolado")
class TestOJogoNaoPerdeOControleDeQuemFicou:
    """O que a NUM-01 podia proteger, medido antes de mudar: o vpad do jogo.

    O jogo vê a mesa pelos vpads, e o co-op os recria quando a ordem das
    cartas não bate (``planejar_a_ordem``). Um buraco na carta continua em
    ordem — então o lugar guardado não derruba o controle de ninguém.
    """

    VPAD_DO_P1 = "vpad-do-p1"

    @staticmethod
    def _cartas(reg: ControllerIdentityRegistry, *uniqs: str) -> dict[str, int]:
        coop = CoopManager.__new__(CoopManager)
        coop._daemon = SimpleNamespace(identity_registry=reg)  # type: ignore[attr-defined]
        return {u: coop._numero_da_carta(u) for u in uniqs}  # type: ignore[misc]

    def test_o_p2_sai_com_o_jogo_aberto_e_ninguem_e_recriado(self) -> None:
        mesa = Mesa()
        mesa.sai(1)
        cartas = self._cartas(mesa.reg, P1, P3, P4)
        cartas[self.VPAD_DO_P1] = cartas.pop(P1)
        # Com o jogo aberto o SDL não renumera: o vpad do P2 morreu e o lugar
        # 1 do jogo ficou livre.
        sentados = {0: self.VPAD_DO_P1, 2: P3, 3: P4}
        assert planejar_a_ordem(sentados, cartas) == ([], True)

        mesa.volta(1)
        cartas = {self.VPAD_DO_P1: 1, **self._cartas(mesa.reg, P2, P3, P4)}
        assert planejar_a_ordem(sentados, cartas, [P2]) == ([], True), (
            "o P2 volta no lugar dele sem derrubar o P3 nem o P4")

    def test_o_p1_sai_e_o_vpad_do_p1_segue_com_quem_ficou(self) -> None:
        """Com o P1 fora o backend passa o vpad do P1 ao P2 (COOP-QUE-NAO-
        DESMONTA-01); a carta do vpad passa a ser a do P2, e a ordem fecha."""
        mesa = Mesa()
        mesa.sai(0)
        cartas = self._cartas(mesa.reg, P2, P3, P4)
        cartas[self.VPAD_DO_P1] = cartas.pop(P2)
        assert cartas == {self.VPAD_DO_P1: 2, P3: 3, P4: 4}
        sentados = {0: self.VPAD_DO_P1, 2: P3, 3: P4}
        assert planejar_a_ordem(sentados, cartas) == ([], True)
