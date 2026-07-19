"""Testes do registro de identidade MAC→slot de SESSÃO (COR-01).

Aceites do sprint 2026-07-16-sprint-cores-e-led-automaticos:
  - conectar A,B → slots 1,2 (menor livre, atribuição lazy na 1ª consulta);
  - desconectar A e reconectar → A volta ao 1 (reserva de sessão — D2);
  - restart do daemon com controles presentes preserva os slots
    (persistência atômica em controllers.json, keyed pelo boot_id);
  - sessão nova só-com-B → B vira slot 1 (reservas expiram ao esvaziar E
    arquivo de outro boot é sessão morta — D2);
  - vpad (MAC forjado 02:fe:...) JAMAIS ganha slot (D9);
  - key sem MAC 12-hex (path:...) ganha slot VOLÁTIL, nunca persistido (D9);
  - `sync_connected` expira as reservas ao esvaziar (e só ele — flap entre
    ticks não derruba reserva).

Herméticos: `config_dir` é monkeypatchado em `utils.xdg_paths` (o registro o
importa LAZY, padrão `save_active_marker`) e o boot_id é fixado por
monkeypatch de `identity._read_boot_id` — nada toca o ~/.config real.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.subsystems import identity
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
    get_identity_registry,
    reset_identity_registry,
)

#: MACs forjados (faixa aa:bb:cc — teste-guarda de anonimato; NUNCA 14:3a).
UNIQ_A = "aabbcc000001"
UNIQ_B = "aabbcc000002"
UNIQ_C = "aabbcc000003"


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """config_dir isolado + boot_id fixo — registro 100% hermético."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(identity, "_read_boot_id", lambda: "boot-teste-1")
    return tmp_path


def _arquivo(tmp: Path) -> dict[str, object]:
    return json.loads((tmp / "controllers.json").read_text(encoding="utf-8"))


class TestAtribuicaoDeSlots:
    def test_a_b_ganham_1_e_2(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        assert reg.slot_for(UNIQ_A) == 1
        assert reg.slot_for(UNIQ_B) == 2
        # Idempotente: consultar de novo não realoca.
        assert reg.slot_for(UNIQ_A) == 1

    def test_assign_false_so_consulta(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        assert reg.slot_for(UNIQ_A, assign=False) is None  # nada atribuído
        assert reg.snapshot() == {}
        reg.slot_for(UNIQ_A)
        assert reg.slot_for(UNIQ_A, assign=False) == 1  # leitura pura

    def test_mac_com_separadores_canoniza(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        assert reg.slot_for("AA:BB:CC:00:00:01") == 1
        # A grafia canônica é o MESMO controle.
        assert reg.slot_for(UNIQ_A) == 1

    def test_uniq_vazio_ou_none_sem_slot(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        assert reg.slot_for(None) is None
        assert reg.slot_for("") is None
        assert reg.snapshot() == {}


class TestReservaDeSessao:
    def test_replug_recupera_o_numero(self, isolated_config: Path) -> None:
        """Desconectar A reserva o slot 1 ao MAC; reconectar recupera (D2)."""
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.slot_for(UNIQ_B)
        reg.mark_disconnected(UNIQ_A)
        # B segue conectado — a sessão NÃO esvaziou; reserva de A vale.
        reg.sync_connected({UNIQ_B})
        assert reg.slot_for(UNIQ_A) == 1  # A volta ao 1, não vira 3

    def test_reserva_ocupa_o_numero_para_terceiros(
        self, isolated_config: Path
    ) -> None:
        """Um C novo NUNCA rouba o slot reservado de A (sem LRU — cortado)."""
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.slot_for(UNIQ_B)
        reg.sync_connected({UNIQ_B})  # A desconectou (reserva)
        assert reg.slot_for(UNIQ_C) == 3  # 1 está reservado a A

    def test_sync_expira_ao_esvaziar(self, isolated_config: Path) -> None:
        """Zero controles conectados = sessão esvaziou → reservas expiram (D2)."""
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.slot_for(UNIQ_B)
        reg.sync_connected(set())  # sessão esvaziou
        assert reg.snapshot() == {}
        # "Sessão nova só-com-B → B=1" (o aceite literal do sprint).
        assert reg.slot_for(UNIQ_B) == 1

    def test_mark_disconnected_sozinho_nao_expira(
        self, isolated_config: Path
    ) -> None:
        """A expiração é do sync (tick lento) — flap entre ticks preserva."""
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.mark_disconnected(UNIQ_A)
        assert reg.snapshot() == {UNIQ_A: 1}  # reserva viva até o sync ver
        assert reg.slot_for(UNIQ_A) == 1

    def test_sync_vazio_antes_de_qualquer_conexao_nao_expira(
        self, isolated_config: Path
    ) -> None:
        """O sync do boot (antes de o backend abrir handles) não pode expirar
        as entradas recém-carregadas do disco — só a TRANSIÇÃO para vazio."""
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.slot_for(UNIQ_B)
        reg.sync_connected({UNIQ_A, UNIQ_B})  # persiste
        reg2 = ControllerIdentityRegistry()
        reg2.load()
        reg2.sync_connected(set())  # boot: backend ainda sem handles
        assert reg2.snapshot() == {UNIQ_A: 1, UNIQ_B: 2}  # reservas intactas
        assert reg2.slot_for(UNIQ_A) == 1


class TestGuardasVpadEVolatil:
    def test_vpad_02fe_jamais_ganha_slot(self, isolated_config: Path) -> None:
        """D9: o MAC forjado do vpad uhid nunca é 'Controle N'."""
        reg = ControllerIdentityRegistry()
        assert reg.slot_for("02fe00000001") is None
        assert reg.slot_for("02:fe:00:00:00:02") is None
        assert reg.snapshot() == {}
        # E não entra nem pelo sync (não conta como sessão viva).
        reg.sync_connected({"02fe00000001"})
        assert reg.snapshot() == {}

    def test_key_path_ganha_slot_volatil_nao_persistido(
        self, isolated_config: Path
    ) -> None:
        """D9: key sem MAC numera na sessão mas NUNCA vai ao disco."""
        reg = ControllerIdentityRegistry()
        assert reg.slot_for("path:/dev/input/event5") == 1
        assert reg.slot_for(UNIQ_A) == 2
        reg.sync_connected({"path:/dev/input/event5", UNIQ_A})
        data = _arquivo(isolated_config)
        assert data["slots"] == {UNIQ_A: 2}  # o volátil ficou de fora

    def test_path_com_hex_espalhado_nao_vira_pseudo_mac(
        self, isolated_config: Path
    ) -> None:
        """Um path com 12+ chars hex espalhados segue VOLÁTIL (regex estrita,
        não o norm_mac permissivo) — e volátil sozinho nem gera arquivo."""
        reg = ControllerIdentityRegistry()
        # 14 chars hex espalhados num path (12 contíguos na faixa forjada
        # aa:bb:cc — guarda de anonimato das fixtures).
        chave = "/dev/aabbcc123456/ee"
        assert reg.slot_for(chave) == 1
        reg.sync_connected({chave})
        # Nada persistível mudou → nenhum controllers.json é criado.
        assert not (isolated_config / "controllers.json").exists()
        # Com um MAC junto, o save roda e o volátil segue de fora.
        reg.slot_for(UNIQ_A)
        reg.sync_connected({chave, UNIQ_A})
        assert _arquivo(isolated_config)["slots"] == {UNIQ_A: 2}


class TestPersistencia:
    def test_restart_com_controles_presentes_preserva(
        self, isolated_config: Path
    ) -> None:
        """Aceite: restart do daemon com controles plugados mantém os números."""
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.slot_for(UNIQ_B)
        reg.sync_connected({UNIQ_A, UNIQ_B})  # save no tick lento

        reg2 = ControllerIdentityRegistry()  # "daemon reiniciou"
        reg2.load()
        reg2.sync_connected({UNIQ_A, UNIQ_B})  # controles seguem presentes
        assert reg2.slot_for(UNIQ_B) == 2
        assert reg2.slot_for(UNIQ_A) == 1

    def test_escrita_atomica_json_valido(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.sync_connected({UNIQ_A})
        data = _arquivo(isolated_config)
        assert data["boot_id"] == "boot-teste-1"
        assert data["slots"] == {UNIQ_A: 1}
        # Sem lixo de tmp deixado para trás (mkstemp + os.replace).
        sobras = [p.name for p in isolated_config.iterdir() if p.name.startswith(".controllers_")]
        assert sobras == []

    def test_arquivo_de_outro_boot_e_sessao_morta(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """D2: reservas não sobrevivem ao reboot da máquina — o daemon que
        morreu sem observar o esvaziamento não ressuscita a numeração."""
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.slot_for(UNIQ_B)
        reg.sync_connected({UNIQ_A, UNIQ_B})

        monkeypatch.setattr(identity, "_read_boot_id", lambda: "boot-teste-2")
        reg2 = ControllerIdentityRegistry()
        reg2.load()
        assert reg2.snapshot() == {}
        assert reg2.slot_for(UNIQ_B) == 1  # sessão nova renumera do 1

    def test_expiracao_regrava_o_arquivo_vazio(self, isolated_config: Path) -> None:
        """A sessão esvaziar em runtime também limpa o disco — um restart
        posterior não ressuscita nada."""
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.slot_for(UNIQ_B)
        reg.sync_connected({UNIQ_A, UNIQ_B})
        reg.sync_connected(set())  # esvaziou
        assert _arquivo(isolated_config)["slots"] == {}

        reg2 = ControllerIdentityRegistry()
        reg2.load()
        assert reg2.slot_for(UNIQ_B) == 1

    def test_boot_id_ilegivel_nao_restaura(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem boot_id não dá para provar que a sessão é a mesma — o
        conservador é renumerar (D2), nunca restaurar no chute."""
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.sync_connected({UNIQ_A})
        monkeypatch.setattr(identity, "_read_boot_id", lambda: None)
        reg2 = ControllerIdentityRegistry()
        reg2.load()
        assert reg2.snapshot() == {}

    def test_arquivo_corrompido_nao_derruba(self, isolated_config: Path) -> None:
        (isolated_config / "controllers.json").write_text(
            "{lixo", encoding="utf-8"
        )
        reg = ControllerIdentityRegistry()
        reg.load()  # não levanta
        assert reg.slot_for(UNIQ_A) == 1

    def test_load_descarta_entrada_degenerada(self, isolated_config: Path) -> None:
        """Slots duplicados/inválidos no disco não corrompem a numeração."""
        (isolated_config / "controllers.json").write_text(
            json.dumps(
                {
                    "boot_id": "boot-teste-1",
                    "slots": {
                        UNIQ_A: 1,
                        UNIQ_B: 1,  # duplicata de slot: 1º ganha
                        UNIQ_C: 0,  # slot inválido
                        "02fe00000009": 4,  # vpad jamais
                        "path:/dev/x": 5,  # volátil jamais deveria estar aqui
                    },
                }
            ),
            encoding="utf-8",
        )
        reg = ControllerIdentityRegistry()
        reg.load()
        assert reg.snapshot() == {UNIQ_A: 1}


class TestReservaExternaCompartilhada:
    """EXT-04: numeração global ÚNICA — o registro dos DualSense pula os slots
    já detidos pelos EXTERNOS (provider injetado por `_wire_external_registry`).

    Sem isto, um DualSense que conecta DEPOIS de um externo já numerado
    reivindicava o slot do externo → duas frentes acendiam o mesmo 'Controle
    N' no co-op misto.
    """

    def test_provider_none_e_comportamento_historico(
        self, isolated_config: Path
    ) -> None:
        """Sem provider (FakeController) numera só pelos próprios _slots."""
        reg = ControllerIdentityRegistry()
        assert reg._extra_reserved is None
        assert reg.slot_for(UNIQ_A) == 1
        assert reg.slot_for(UNIQ_B) == 2

    def test_ds_novo_pula_slot_reservado_por_externo(
        self, isolated_config: Path
    ) -> None:
        """2 DualSense (1,2) + 1 externo detendo o slot 3: um 3º DualSense
        conectando DEPOIS recebe 4, NUNCA o 3 do externo."""
        reg = ControllerIdentityRegistry()
        externos = {3}
        reg.set_external_reserve_provider(lambda: set(externos))
        assert reg.slot_for(UNIQ_A) == 1
        assert reg.slot_for(UNIQ_B) == 2
        # O menor livre PRÓPRIO seria 3, mas o externo o detém.
        assert reg.slot_for(UNIQ_C) == 4

    def test_caso_minimo_1ds_externo_2ds(self, isolated_config: Path) -> None:
        """O caso mais simples do achado: 1 DS=1, externo=2, 2º DS não vira 2."""
        reg = ControllerIdentityRegistry()
        reg.set_external_reserve_provider(lambda: {2})
        assert reg.slot_for(UNIQ_A) == 1
        assert reg.slot_for(UNIQ_B) == 3  # pula o 2 do externo

    def test_nao_renumera_quem_ja_tem_slot(self, isolated_config: Path) -> None:
        """A união externa só afeta atribuições NOVAS — jamais mexe num slot
        já dado, mesmo que o externo passe a reservá-lo (estabilidade vence)."""
        reg = ControllerIdentityRegistry()
        assert reg.slot_for(UNIQ_A) == 1  # atribuído ANTES de haver reserva
        reg.set_external_reserve_provider(lambda: {1})  # externo "reivindica" 1
        assert reg.slot_for(UNIQ_A) == 1  # A continua 1 (leitura do existente)

    def test_provider_que_explode_cai_no_historico(
        self, isolated_config: Path
    ) -> None:
        """Provider quebrado nunca derruba a atribuição (contextlib.suppress)."""
        reg = ControllerIdentityRegistry()

        def explode() -> set[int]:
            raise RuntimeError("registry externo indisponível")

        reg.set_external_reserve_provider(explode)
        assert reg.slot_for(UNIQ_A) == 1
        assert reg.slot_for(UNIQ_B) == 2


class TestConfiguracaoDoAuto:
    def test_defaults(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        assert reg.auto_enabled is True
        assert reg.auto_brightness == 1.0

    def test_configure_parcial_preserva_o_resto(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        reg.configure(enabled=False)
        assert reg.auto_enabled is False
        assert reg.auto_brightness == 1.0
        reg.configure(brightness=0.4)
        assert reg.auto_enabled is False
        assert reg.auto_brightness == 0.4

    def test_brightness_com_clamp(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        reg.configure(brightness=7.0)
        assert reg.auto_brightness == 1.0
        reg.configure(brightness=-1.0)
        assert reg.auto_brightness == 0.0


class TestSingleton:
    def test_get_devolve_a_mesma_instancia(self) -> None:
        reset_identity_registry()
        try:
            a = get_identity_registry()
            b = get_identity_registry()
            assert a is b
        finally:
            reset_identity_registry()

    def test_reset_descarta(self) -> None:
        reset_identity_registry()
        try:
            a = get_identity_registry()
            reset_identity_registry()
            assert get_identity_registry() is not a
        finally:
            reset_identity_registry()
