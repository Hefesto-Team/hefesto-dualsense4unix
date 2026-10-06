"""O-CONTROLE-SEM-MAC-01 — o usuário que a mesa desta casa não tem."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hefesto_dualsense4unix.daemon.subsystems import identity
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    FRASE_SEM_CRACHA,
    ControllerIdentityRegistry,
)

CRACHA_X = "aa:bb:cc:0a:7f:31"
CRACHA_X_CANON = "aabbcc0a7f31"
CRACHA_Y = "aa:bb:cc:5d:e2:94"
CRACHA_Y_CANON = "aabbcc5de294"
COM_SERIAL = "aabbcc31f80e"

PATH_1 = "/dev/hidraw7"
PATH_2 = "/dev/hidraw3"


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` isolado + âncora fixa — registro 100% hermético."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(identity, "_read_boot_id", lambda: "boot-teste-sem-mac")
    return tmp_path


def _fila_no_disco(tmp: Path) -> dict[str, int]:
    """Endereço → lugar, lidos do ``order`` do ``controllers.json``."""
    arquivo = tmp / "controllers.json"
    if not arquivo.exists():
        return {}
    entradas = json.loads(arquivo.read_text(encoding="utf-8"))[identity.ORDER_FIELD]
    return {
        str(e["addr"]): int(e["rank"])
        for e in entradas
        if isinstance(e, dict) and e.get("kind") == identity.KIND_DUALSENSE
    }


def _cracha_fixo(mapa: dict[str, str]):
    """Dublê do aparelho: path → o endereço que o feature 0x09 devolveria."""

    def provider(uniq: str) -> str | None:
        return mapa.get(uniq)

    return provider


class TestOSemSerialGanhaSlotPersistivel:
    """Entrega 1: quando o serial falta, o segundo conduíte assume."""

    def test_o_cracha_da_a_key_e_o_lugar_atravessa_o_restart(
        self, isolated_config: Path
    ) -> None:
        """O lugar do sem-serial chega ao DISCO e volta de lá."""
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(_cracha_fixo({PATH_1: CRACHA_X}))
        reg.sync_connected([PATH_1])

        assert reg.snapshot() == {CRACHA_X_CANON: 1}
        assert reg.slot_for(PATH_1) == 1
        assert _fila_no_disco(isolated_config) == {CRACHA_X_CANON: 1}

        depois = ControllerIdentityRegistry()
        depois.load()
        assert depois.snapshot() == {CRACHA_X_CANON: 1}

    def test_a_forma_da_key_nova_e_a_da_key_velha(
        self, isolated_config: Path
    ) -> None:
        """12 hex canônicos, e é requisito — não economia de código."""
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(_cracha_fixo({PATH_1: CRACHA_X}))
        reg.sync_connected([PATH_1])
        (key,) = reg.snapshot()
        assert len(key) == 12
        assert all(c in "0123456789abcdef" for c in key)

    def test_o_cracha_em_qualquer_grafia_canoniza(
        self, isolated_config: Path
    ) -> None:
        """O provider devolve o que o aparelho der; a canonização é daqui."""
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(_cracha_fixo({PATH_1: CRACHA_X.upper()}))
        reg.sync_connected([PATH_1])
        assert reg.snapshot() == {CRACHA_X_CANON: 1}

    def test_cracha_que_nao_e_endereco_e_recusado(
        self, isolated_config: Path
    ) -> None:
        """Um provider que devolve lixo não vira identidade nem por engano."""
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(_cracha_fixo({PATH_1: "nao-sou-um-endereco"}))
        reg.sync_connected([PATH_1])
        assert reg.snapshot() == {PATH_1: 1}
        assert _fila_no_disco(isolated_config) == {}
        assert reg.avisos_sem_cracha() == [
            {"uniq": PATH_1, "frase": FRASE_SEM_CRACHA}
        ]


class TestOPathContinuaNaoSendoIdentidade:
    """Entrega 1, a metade que D9 protege — e a mordida que mais importa."""

    def test_mesmo_cracha_outro_path_cai_na_mesma_entrada(
        self, isolated_config: Path
    ) -> None:
        """O aparelho é o mesmo; o nó do sistema mudou (é o que o boot faz)."""
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(_cracha_fixo({PATH_1: CRACHA_X}))
        reg.sync_connected([PATH_1])
        assert reg.snapshot() == {CRACHA_X_CANON: 1}

        depois = ControllerIdentityRegistry()
        depois.load()
        depois.set_cracha_provider(_cracha_fixo({PATH_2: CRACHA_X}))
        depois.sync_connected([PATH_2])

        assert depois.snapshot() == {CRACHA_X_CANON: 1}
        assert depois.slot_for(PATH_2) == 1

    def test_dois_aparelhos_sem_serial_nao_se_confundem(
        self, isolated_config: Path
    ) -> None:
        """Crachás diferentes são controles diferentes, ainda que sem serial."""
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(
            _cracha_fixo({PATH_1: CRACHA_X, PATH_2: CRACHA_Y})
        )
        reg.sync_connected([PATH_1, PATH_2])
        assert reg.snapshot() == {CRACHA_X_CANON: 1, CRACHA_Y_CANON: 2}
        assert reg.slot_for(PATH_1) == 1
        assert reg.slot_for(PATH_2) == 2


class TestADesistenciaEAnunciada:
    """Entrega 2: perder configuração calado é o defeito."""

    def test_sem_cracha_nenhum_slot_volatil_e_a_frase(
        self, isolated_config: Path
    ) -> None:
        """As DUAS metades, e nenhuma delas sozinha basta."""
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(_cracha_fixo({}))
        reg.sync_connected([PATH_1])

        assert reg.snapshot() == {PATH_1: 1}
        assert _fila_no_disco(isolated_config) == {}
        assert reg.avisos_sem_cracha() == [
            {"uniq": PATH_1, "frase": FRASE_SEM_CRACHA}
        ]

    def test_a_frase_e_a_decidida_por_ela(self) -> None:
        """Texto que vai à tela um dia é do usuário, e é literal.
        (D-0609-A-FRASE-DO-CONTROLE-SEM-CRACHA)
        """
        assert FRASE_SEM_CRACHA == (
            "Este controle não tem identificação estável: o Hefesto não vai "
            "lembrar dele no próximo jogo."
        )
        baixo = FRASE_SEM_CRACHA.lower()
        for proibida in ("mac", "uniq", "hidraw", "mesa", "path"):
            assert proibida not in baixo

    def test_quem_tem_cracha_nao_aparece_no_aviso(
        self, isolated_config: Path
    ) -> None:
        """Aviso é para quem a casa desistiu — não para todo sem-serial."""
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(
            _cracha_fixo({PATH_1: CRACHA_X})
        )
        reg.sync_connected([PATH_1, PATH_2])
        assert reg.avisos_sem_cracha() == [
            {"uniq": PATH_2, "frase": FRASE_SEM_CRACHA}
        ]

    def test_o_provider_que_levanta_nao_derruba_o_tique(
        self, isolated_config: Path
    ) -> None:
        """Aparelho mudo é desistência, não exceção no laço do daemon."""

        def explode(uniq: str) -> str | None:
            raise OSError("hidraw sumiu entre o enumerate e a leitura")

        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(explode)
        reg.sync_connected([PATH_1])
        assert reg.snapshot() == {PATH_1: 1}
        assert reg.avisos_sem_cracha() == [
            {"uniq": PATH_1, "frase": FRASE_SEM_CRACHA}
        ]


class TestOCrachaNuncaVenceOSerial:
    """Entrega 3: trocar a chave de quem já é lembrado apaga a memória."""

    def test_quem_tem_serial_cai_na_entrada_de_sempre(
        self, isolated_config: Path
    ) -> None:
        """Byte a byte a MESMA key de antes desta sprint."""
        provider_chamado: list[str] = []

        def provider(uniq: str) -> str | None:
            provider_chamado.append(uniq)
            return CRACHA_Y

        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(provider)
        reg.sync_connected([COM_SERIAL])

        assert reg.snapshot() == {COM_SERIAL: 1}
        assert _fila_no_disco(isolated_config) == {COM_SERIAL: 1}
        assert provider_chamado == []

    def test_a_fila_gravada_de_antes_continua_valendo(
        self, isolated_config: Path
    ) -> None:
        """Um disco escrito ANTES desta sprint volta intacto."""
        (isolated_config / "controllers.json").write_text(
            json.dumps(
                {
                    "version": identity.CONTROLLERS_SCHEMA_VERSION,
                    "boot_id": "boot-teste-sem-mac",
                    identity.ORDER_FIELD: [
                        {
                            "addr": COM_SERIAL,
                            "kind": identity.KIND_DUALSENSE,
                            "rank": 1,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(_cracha_fixo({PATH_1: CRACHA_X}))
        reg.load()
        assert reg.snapshot() == {COM_SERIAL: 1}
        reg.sync_connected([COM_SERIAL, PATH_1])
        assert reg.snapshot() == {COM_SERIAL: 1, CRACHA_X_CANON: 2}


class TestOVpadContinuaSemSlot:
    """Entrega 3, a guarda D9 que a porta nova não pode furar."""

    def test_vpad_nao_ganha_slot_nem_pela_porta_nova(
        self, isolated_config: Path
    ) -> None:
        """Um crachá que devolve o MAC forjado ``02:fe:...`` é RECUSADO."""
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(_cracha_fixo({PATH_1: "02:fe:00:00:00:07"}))
        reg.sync_connected([PATH_1])
        assert "02fe000007" not in reg.snapshot()
        assert reg.snapshot() == {PATH_1: 1}
        assert reg.avisos_sem_cracha() == [
            {"uniq": PATH_1, "frase": FRASE_SEM_CRACHA}
        ]

    def test_vpad_com_serial_proprio_continua_sem_slot(
        self, isolated_config: Path
    ) -> None:
        """O caminho velho de D9 não foi tocado."""
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(_cracha_fixo({}))
        assert reg.slot_for("02fe00000001") is None
        reg.sync_connected(["02fe00000001"])
        assert reg.snapshot() == {}


class TestOCrachaESquecidoNaSaida:
    """Dívida do próprio mecanismo: o cache é indexado por um path."""

    def test_path_reocupado_por_outro_aparelho_nao_herda_a_identidade(
        self, isolated_config: Path
    ) -> None:
        """Interromper a identificação é aceitável; CORROMPÊ-LA não é."""
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(_cracha_fixo({PATH_1: CRACHA_X}))
        reg.sync_connected([PATH_1])
        assert reg.snapshot() == {CRACHA_X_CANON: 1}

        reg.sync_connected([])
        reg.set_cracha_provider(_cracha_fixo({PATH_1: CRACHA_Y}))
        reg.sync_connected([PATH_1])

        assert reg.slot_for(PATH_1) == reg.slot_for(CRACHA_Y_CANON)
        assert CRACHA_Y_CANON in reg.snapshot()
        assert reg.snapshot() == {CRACHA_X_CANON: 1, CRACHA_Y_CANON: 2}

    def test_o_aviso_tambem_e_solto_na_saida(
        self, isolated_config: Path
    ) -> None:
        """Aviso de quem não está mais na mesa é ruído na coluna Atenção."""
        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(_cracha_fixo({}))
        reg.sync_connected([PATH_1])
        assert reg.avisos_sem_cracha() != []
        reg.sync_connected([])
        assert reg.avisos_sem_cracha() == []


class TestOCaminhoQuenteNaoFalaComOAparelho:
    """A promessa da docstring da classe: ``slot_for`` sem I/O."""

    def test_slot_for_nunca_chama_o_provider(
        self, isolated_config: Path
    ) -> None:
        """Ele roda sob o ``_io_lock`` do backend, uma vez por controle por"""
        chamadas: list[str] = []

        def provider(uniq: str) -> str | None:
            chamadas.append(uniq)
            return CRACHA_X

        reg = ControllerIdentityRegistry()
        reg.set_cracha_provider(provider)
        for _ in range(20):
            reg.slot_for(PATH_1)
            reg.numero_da_lampada(PATH_1)
        assert chamadas == []

        reg.sync_connected([PATH_1])
        reg.sync_connected([PATH_1])
        reg.sync_connected([PATH_1])
        assert chamadas == [PATH_1]

    def test_sem_provider_fiado_o_registro_e_o_de_sempre(
        self, isolated_config: Path
    ) -> None:
        """O segundo conduíte é ADITIVO: sem fiação, nada muda."""
        reg = ControllerIdentityRegistry()
        assert reg.slot_for(PATH_1) == 1
        reg.sync_connected([PATH_1, COM_SERIAL])
        assert reg.snapshot() == {PATH_1: 1, COM_SERIAL: 2}
        assert _fila_no_disco(isolated_config) == {COM_SERIAL: 2}
