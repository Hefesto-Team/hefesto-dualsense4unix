"""Testes do registro de identidade MAC→slot de SESSÃO (COR-01).

Aceites do sprint 2026-07-16-sprint-cores-e-led-automaticos:
  - conectar A,B → slots 1,2 (menor livre, atribuição lazy na 1ª consulta);
  - desconectar A e reconectar → A volta ao 1 (reserva de sessão — D2);
  - restart do daemon E reboot da máquina preservam os slots — R-23
    (auditoria 25/07): o mapa é keyed por MAC e MAC não muda no reboot, então
    o `boot_id` deixou de matar o arquivo (era ele que renumerava a casa toda
    e alimentava "os controles se reenumeram e nunca sei o que é o quê"). A
    única renumeração AUTOMÁTICA que sobrou é a de SCHEMA
    (`CONTROLLERS_SCHEMA_VERSION` diferente = outra regra de numeração);
  - a expiração por "sessão esvaziou" foi REMOVIDA de propósito em R-15: era
    assimétrica (o registro dos externos nunca expirou) e fazia a cor/número
    trocarem de dono conforme a ordem de wake;
  - `sync_connected` ATRIBUI slot a quem conectou sem número — R-24: sem
    isso o registro ficava vazio até o provider de cor rodar, o piso lido
    pelos externos valia 0 e o Pro Nintendo tomava o slot 1 na frente dos
    DualSense ("não existe Controle 1");
  - vpad (MAC forjado 02:fe:...) JAMAIS ganha slot (D9);
  - key sem MAC 12-hex (path:...) ganha slot VOLÁTIL, nunca persistido (D9);
  - `sync_connected` RECONCILIA, ATRIBUI (R-24) e persiste: nem ele nem o
    `mark_disconnected` derrubam reserva (R-15).

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

#: A função REAL de leitura da âncora, capturada ANTES de qualquer fixture
#: monkeypatchá-la (R-23). Os 15 dublês de `_read_boot_id` espalhados pela
#: suíte faziam com que o caminho de I/O real nunca rodasse em teste — e era
#: justamente ele que falhava sem `/proc` (Flatpak/contêiner), renumerando a
#: casa a cada restart. Quem quiser exercitar a leitura de verdade repõe isto.
_READ_BOOT_ID_REAL = identity._read_boot_id

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


class TestAtribuicaoNoSync:
    """R-24: o tick lento numera quem conectou, sem esperar o provider de cor.

    Falha-sem: o único ponto de atribuição era o `slot_for` LAZY, chamado só
    pelo provider de cor (caminho de output do backend). Enquanto ele não
    rodava, `snapshot()` ficava vazio — e é esse snapshot que o registro dos
    EXTERNOS lê como piso (`_ds_reserve`). Piso 0 ⇒ o Pro Nintendo USB tomava
    o slot 1 e os dois DualSense herdavam 2 e 3, que é o "não existe Controle
    1" medido no `controllers.json` dela.
    """

    def test_sync_numera_quem_conectou(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        reg.sync_connected([UNIQ_A, UNIQ_B])
        assert reg.snapshot() == {UNIQ_A: 1, UNIQ_B: 2}

    def test_ordem_do_iteravel_manda_nao_o_hash(self, isolated_config: Path) -> None:
        """O lifecycle entrega em ordem de `describe_controllers` (primário
        primeiro) — numerar por hash de `set` faria o "Controle 1" sortear."""
        reg = ControllerIdentityRegistry()
        reg.sync_connected([UNIQ_B, UNIQ_A])
        assert reg.snapshot() == {UNIQ_B: 1, UNIQ_A: 2}

    def test_sync_nao_renumera_quem_ja_tem(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        assert reg.slot_for(UNIQ_B) == 1
        reg.sync_connected([UNIQ_A, UNIQ_B])
        assert reg.snapshot() == {UNIQ_B: 1, UNIQ_A: 2}

    def test_sync_respeita_a_reserva_dos_externos(self, isolated_config: Path) -> None:
        """A atribuição do sync passa pelo MESMO `used` do `slot_for` (espaço
        de numeração único, EXT-04) — nunca por uma segunda regra."""
        reg = ControllerIdentityRegistry()
        reg.set_external_reserve_provider(lambda: {1})
        reg.sync_connected([UNIQ_A])
        assert reg.snapshot() == {UNIQ_A: 2}

    def test_sync_nao_numera_vpad(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        reg.sync_connected(["02fe00000001", UNIQ_A])
        assert reg.snapshot() == {UNIQ_A: 1}  # D9: vpad nunca é Controle N

    def test_sync_persiste_o_que_atribuiu(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        reg.sync_connected([UNIQ_A, UNIQ_B])
        assert _arquivo(isolated_config)["slots"] == {UNIQ_A: 1, UNIQ_B: 2}


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

    def test_sessao_esvaziar_nao_expira_dentro_do_boot(
        self, isolated_config: Path
    ) -> None:
        """R-15: dentro do boot, número é do MAC — ninguém expira.

        TROCA DELIBERADA de contrato (auditoria 23/07). Este caso ASSERTAVA a
        expiração por "sessão esvaziou" (`test_sync_expira_ao_esvaziar`), que
        era o defeito: (a) assimétrica — só este registro expirava, o dos
        externos (`ExternalIdentityRegistry`) nunca expirou nada, então
        DualSense e externos renumeravam em momentos diferentes sobre o MESMO
        espaço de numeração; (b) o resultado dependia da ORDEM DE WAKE, não do
        MAC: desligar os dois DualSense para jantar e religar o roxo primeiro
        dava a ele o slot 1 (a cor e o número do branco). Quem renumera é o
        BOOT (o `boot_id` do arquivo) ou o gesto explícito "Renumerar agora".

        Cenário exato da queixa: os dois somem juntos e voltam em ORDEM
        INVERTIDA — cada um recupera o próprio número.
        """
        reg = ControllerIdentityRegistry()
        assert reg.slot_for(UNIQ_A) == 1
        assert reg.slot_for(UNIQ_B) == 2
        reg.sync_connected(set())  # os dois desligaram (nada expira)
        assert reg.snapshot() == {UNIQ_A: 1, UNIQ_B: 2}
        # Voltam na ordem INVERTIDA (B primeiro): ninguém rouba o 1.
        assert reg.slot_for(UNIQ_B) == 2
        assert reg.slot_for(UNIQ_A) == 1

    def test_mark_disconnected_sozinho_nao_expira(
        self, isolated_config: Path
    ) -> None:
        """Desconectar RESERVA o slot; nada aqui renumera (R-15).

        Antes do R-15 a reserva vivia "até o sync ver a sessão vazia"; agora
        vive o boot inteiro. O caso segue valendo como guarda de que o
        caminho quente por evento não mexe no mapa.
        """
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.mark_disconnected(UNIQ_A)
        assert reg.snapshot() == {UNIQ_A: 1}  # reserva viva até o sync ver
        assert reg.slot_for(UNIQ_A) == 1

    def test_sync_vazio_antes_de_qualquer_conexao_nao_expira(
        self, isolated_config: Path
    ) -> None:
        """O sync do boot (antes de o backend abrir handles) não pode expirar
        as entradas recém-carregadas do disco — o caso que motivou o antigo
        `_saw_connected` e que R-15 resolve por construção (ninguém expira).
        """
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

    def test_arquivo_de_outro_boot_restaura_os_mesmos_numeros(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R-23: REBOOT NÃO RENUMERA — troca de contrato deliberada (25/07).

        Este caso assertava o contrário (`test_arquivo_de_outro_boot_e_sessao
        _morta`: boot_id diferente ⇒ mapa descartado ⇒ renumera do 1). Era a
        causa direta da queixa "ao abrir os jogos ou o perfil, os controles se
        reenumeram e nunca sei o que é o quê": o mapa é keyed por MAC, e MAC
        não muda no reboot — o número é IDENTIDADE, não sessão. Quem renumera
        agora é o schema (arquivo de outra REGRA de numeração) ou o gesto
        explícito "Renumerar agora".
        """
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.slot_for(UNIQ_B)
        reg.sync_connected([UNIQ_A, UNIQ_B])

        monkeypatch.setattr(identity, "_read_boot_id", lambda: "boot-teste-2")
        reg2 = ControllerIdentityRegistry()
        reg2.load()
        assert reg2.snapshot() == {UNIQ_A: 1, UNIQ_B: 2}
        # E a ordem de wake do boot novo não troca dono de número nenhum.
        assert reg2.slot_for(UNIQ_B) == 2
        assert reg2.slot_for(UNIQ_A) == 1

    def test_schema_antigo_e_a_unica_renumeracao_automatica(
        self, isolated_config: Path
    ) -> None:
        """R-23: arquivo de outra REGRA de numeração é descartado UMA vez.

        É a válvula que impede a numeração torta já gravada na máquina (o
        externo segurando o slot 1 enquanto os DualSense exibiam 2 e 3) de
        virar eterna agora que nada mais expira. Sem o campo `version` (todo
        arquivo escrito antes do R-23) o load não restaura nada e a sessão
        seguinte numera do 1 com a regra nova — e já grava a versão.
        """
        (isolated_config / "controllers.json").write_text(
            json.dumps({"boot_id": "boot-teste-1", "slots": {UNIQ_A: 4}}),
            encoding="utf-8",
        )
        reg = ControllerIdentityRegistry()
        reg.load()
        assert reg.snapshot() == {}
        assert reg.slot_for(UNIQ_A) == 1
        reg.sync_connected([UNIQ_A])
        assert _arquivo(isolated_config)["version"] == (
            identity.CONTROLLERS_SCHEMA_VERSION
        )

        # E a partir daí o arquivo NOVO já é restaurado normalmente.
        reg2 = ControllerIdentityRegistry()
        reg2.load()
        assert reg2.snapshot() == {UNIQ_A: 1}

    def test_sessao_esvaziada_sobrevive_ao_restart_e_so_o_boot_renumera(
        self, isolated_config: Path
    ) -> None:
        """R-15: quem renumera é o BOOT — não "todo mundo desligou".

        TROCA DELIBERADA de contrato (par do caso acima; este slot era o
        `test_expiracao_regrava_o_arquivo_vazio`, que assertava o arquivo
        virar `{}` quando a sessão esvaziava). Agora: com todos desligados o
        arquivo CONTINUA com os slots, um restart do daemon os restaura, e só
        um `boot_id` diferente (máquina reiniciada) devolve a numeração ao 1.
        """
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.slot_for(UNIQ_B)
        reg.sync_connected({UNIQ_A, UNIQ_B})
        reg.sync_connected(set())  # todos desligados — reserva de boot
        assert _arquivo(isolated_config)["slots"] == {UNIQ_A: 1, UNIQ_B: 2}

        reg2 = ControllerIdentityRegistry()  # daemon reiniciou no MESMO boot
        reg2.load()
        assert reg2.slot_for(UNIQ_B) == 2  # o número é do MAC, não da ordem

    def test_boot_id_ilegivel_nao_derruba_a_numeracao(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R-23: âncora ilegível NÃO renumera — troca de contrato (25/07).

        Este caso assertava `snapshot() == {}` ("sem boot_id, renumera por
        conservadorismo"). Na prática era o oposto de conservador: em
        Flatpak/contêiner `/proc/sys/kernel/random/boot_id` simplesmente não
        existe, então TODO restart do daemon caía aqui e renumerava a casa
        inteira. A âncora não decide mais nada; quem decide é o schema.
        """
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.slot_for(UNIQ_B)
        reg.sync_connected([UNIQ_A, UNIQ_B])

        monkeypatch.setattr(identity, "_read_boot_id", lambda: None)
        monkeypatch.setattr(identity, "_read_machine_id", lambda: None)
        reg2 = ControllerIdentityRegistry()
        reg2.load()
        assert reg2.snapshot() == {UNIQ_A: 1, UNIQ_B: 2}

    def test_sem_proc_a_ancora_cai_no_machine_id_de_verdade(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exercita a LEITURA REAL da âncora sem `/proc` (R-23).

        Os 15 monkeypatches de `_read_boot_id` espalhados pela suíte faziam
        com que o caminho de I/O real NUNCA rodasse em teste — o modo
        Flatpak/contêiner (sem `/proc/sys/kernel/random/boot_id`) só era
        exercitado na máquina da usuária, e falhando. Aqui `open` é
        redirecionado para um sysfs falso: `/proc` some, `/etc/machine-id`
        existe, e a âncora tem de descer o degrau sem levantar.
        """
        monkeypatch.setattr(identity, "_read_boot_id", _READ_BOOT_ID_REAL)
        machine = isolated_config / "machine-id"
        machine.write_text("aabbcc0f0f0f\n", encoding="utf-8")
        real_open = open

        def fake_open(caminho, *a, **kw):  # type: ignore[no-untyped-def]
            if caminho == "/proc/sys/kernel/random/boot_id":
                raise OSError("sem /proc (contêiner)")
            if caminho in identity._MACHINE_ID_PATHS:
                return real_open(machine, *a, **kw)
            return real_open(caminho, *a, **kw)

        monkeypatch.setattr("builtins.open", fake_open)
        assert identity._read_boot_id() is None  # leitura REAL, não dublê
        assert identity._session_anchor() == "machine:aabbcc0f0f0f"

    def test_sem_proc_e_sem_machine_id_a_ancora_e_none_sem_levantar(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Último degrau: nenhuma fonte de âncora ⇒ `None`, e o load segue.

        Falha-sem (pré-R-23): `None` aqui abortava o `load` e renumerava tudo.
        """
        monkeypatch.setattr(identity, "_read_boot_id", _READ_BOOT_ID_REAL)
        real_open = open

        def fake_open(caminho, *a, **kw):  # type: ignore[no-untyped-def]
            if caminho == "/proc/sys/kernel/random/boot_id" or (
                caminho in identity._MACHINE_ID_PATHS
            ):
                raise OSError("nem /proc nem /etc")
            return real_open(caminho, *a, **kw)

        monkeypatch.setattr("builtins.open", fake_open)
        assert identity._session_anchor() is None

        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.sync_connected([UNIQ_A])  # grava com boot_id=None
        reg2 = ControllerIdentityRegistry()
        reg2.load()
        assert reg2.snapshot() == {UNIQ_A: 1}, "sem âncora, o número fica"

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
                    "version": identity.CONTROLLERS_SCHEMA_VERSION,
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

    def test_load_trunca_no_teto_e_mantem_os_slots_baixos(
        self, isolated_config: Path
    ) -> None:
        """R-23: nada expira mais, então o arquivo tem um TETO.

        Sem teto, um arquivo que só cresce (todo controle que já passou pela
        casa mantém o número para sempre) faria a numeração começar cada vez
        mais alto. Poda quem tem slot ALTO — quem tem slot baixo é quem a casa
        usa.
        """
        slots = {f"aabbcc{n:06d}": n for n in range(1, 25)}
        (isolated_config / "controllers.json").write_text(
            json.dumps(
                {
                    "version": identity.CONTROLLERS_SCHEMA_VERSION,
                    "boot_id": "boot-teste-1",
                    "slots": slots,
                }
            ),
            encoding="utf-8",
        )
        reg = ControllerIdentityRegistry()
        reg.load()
        restaurados = reg.snapshot()
        assert len(restaurados) == identity._MAX_PERSISTED_SLOTS
        assert max(restaurados.values()) == identity._MAX_PERSISTED_SLOTS
        assert restaurados["aabbcc000001"] == 1


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


class TestCompactRenumeracao:
    """`compact` (ONDA-U/U2/U10) — reatribuição EXPLÍCITA, distinta da lazy.

    Falha-sem: `ControllerIdentityRegistry` no HEAD não tem `compact` nenhum
    — `identity.renumber` não existiria como handler possível.
    """

    def test_reescreve_so_as_chaves_do_mapping(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)  # slot 1
        reg.slot_for(UNIQ_B)  # slot 2
        reg.compact({UNIQ_A: 3, UNIQ_B: 1})
        assert reg.snapshot() == {UNIQ_A: 3, UNIQ_B: 1}

    def test_chave_fora_do_registro_e_ignorada(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.compact({UNIQ_A: 5, "aabbcc00ffff": 9})
        assert reg.snapshot() == {UNIQ_A: 5}

    def test_persiste_no_disco_quando_muda(self, isolated_config: Path) -> None:
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.slot_for(UNIQ_B)
        reg.sync_connected({UNIQ_A, UNIQ_B})  # save inicial (1, 2)
        reg.compact({UNIQ_A: 2, UNIQ_B: 1})
        data = _arquivo(isolated_config)
        assert data["slots"] == {UNIQ_A: 2, UNIQ_B: 1}

    def test_sem_mudanca_nao_regrava(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_A)
        reg.sync_connected({UNIQ_A})
        chamou = {"sim": False}
        original = reg._save_locked

        def espiao() -> None:
            chamou["sim"] = True
            original()

        monkeypatch.setattr(reg, "_save_locked", espiao)
        reg.compact({UNIQ_A: 1})  # já é 1 — no-op
        assert chamou["sim"] is False


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
