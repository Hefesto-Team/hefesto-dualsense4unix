"""NUMA-04 — lock único do ``controllers.json`` + cross-check no load.

Sprint 2026-07-19-sprint-numeracao-una.md, bloco de testes 12
("CONTROLLERS-LOCK"). Cobre os dois vetores do achado (lacuna 11 do mapa de
retomada):

1. Os dois registros (``ControllerIdentityRegistry`` de ``identity.py`` e
   ``ExternalIdentityRegistry`` de ``external_identity.py``) fazem
   read-modify-write no MESMO ``controllers.json``, cada um só com o próprio
   ``RLock`` de INSTÂNCIA — que não protege contra o OUTRO objeto escrevendo
   ao mesmo tempo. O lock de MÓDULO ``CONTROLLERS_FILE_LOCK`` (definido em
   ``identity.py``, IMPORTADO por ``external_identity.py`` — nunca um lock
   novo) fecha esse lost-update.
2. Corrupção HERDADA de um lost-update pretérito (antes do fix, ou de um
   arquivo escrito por outra versão): o MESMO slot aparecendo em ``slots``
   (DualSense) e ``externals`` no mesmo arquivo é resolvida UNILATERALMENTE
   a favor do DualSense no ``load`` — a entrada externa colidente é DROPADA
   (nunca realocada; a DualSense nunca é podada).

Determinizado: o teste de intercalação usa threads REAIS mas a ORDEM é
forçada por `threading.Event` (barreira) — sem a barreira, o resultado
dependeria da sorte do agendador do SO (proibido pela regra da casa); com
ela, a intercalação é SEMPRE a mesma e o resultado é invariante quanto à
ordem real de execução (a correção vem do lock, não de "quem chegou
primeiro"). Nenhum ``time.sleep`` real — só espera bloqueante em Event/Lock.

Hermético: ``config_dir`` monkeypatchado nos DOIS módulos (mesmo arquivo) +
``boot_id`` fixo — nada toca o ``~/.config`` real.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    CONTROLLERS_FILE_LOCK,
    ControllerIdentityRegistry,
)

#: MACs forjados (faixa aa:bb:cc — teste-guarda de anonimato; NUNCA 14:3a).
UNIQ_DS_A = "aabbcc000001"
UNIQ_DS_B = "aabbcc000002"
MAC_EXT_A = "aabbcc0000fe"
MAC_EXT_B = "aabbcc0000ff"

BOOT = "boot-teste-1"


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` isolado + ``boot_id`` fixo nos DOIS registros."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


def _arquivo(tmp: Path) -> dict[str, Any]:
    return json.loads((tmp / "controllers.json").read_text(encoding="utf-8"))


class TestLockCompartilhado:
    """``external_identity.py`` IMPORTA o lock de ``identity.py`` — nunca cria
    o seu (a fiação exigida pela spec, não um acidente de nomes iguais)."""

    def test_e_o_mesmo_objeto_nos_dois_modulos(self) -> None:
        assert ei_mod.CONTROLLERS_FILE_LOCK is CONTROLLERS_FILE_LOCK
        assert isinstance(CONTROLLERS_FILE_LOCK, type(threading.Lock()))


class TestLockSeguraOSpanCompleto:
    """O lock cobre o span INTEIRO read→``os.replace`` (save) e o read (load) —
    não só um pedaço. Falha-sem: no HEAD (antes do NUMA-04) não existe
    ``CONTROLLERS_FILE_LOCK`` nenhum para checar — o teste pega qualquer
    remoção futura do ``with`` que deixe uma fresta destampada."""

    def test_identity_save_mantem_lock_ate_o_replace(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import os as os_mod

        vistos: list[bool] = []
        original = os_mod.replace

        def espiao(src: str, dst: str) -> None:
            vistos.append(CONTROLLERS_FILE_LOCK.locked())
            original(src, dst)

        monkeypatch.setattr(os_mod, "replace", espiao)
        reg = ControllerIdentityRegistry()
        reg.slot_for(UNIQ_DS_A)
        reg.sync_connected({UNIQ_DS_A})
        assert vistos == [True], "os.replace rodou com o lock JÁ liberado"

    def test_external_save_mantem_lock_ate_o_replace(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import os as os_mod

        vistos: list[bool] = []
        original = os_mod.replace

        def espiao(src: str, dst: str) -> None:
            vistos.append(CONTROLLERS_FILE_LOCK.locked())
            original(src, dst)

        monkeypatch.setattr(os_mod, "replace", espiao)
        reg = ExternalIdentityRegistry()
        reg.slot_for(MAC_EXT_A, reserve=0)
        reg.sync_connected([MAC_EXT_A])
        assert vistos == [True], "os.replace rodou com o lock JÁ liberado"

    def test_identity_load_segura_o_lock_durante_o_read(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Precisa existir arquivo para o read acontecer de fato.
        criador = ControllerIdentityRegistry()
        criador.slot_for(UNIQ_DS_A)
        criador.sync_connected({UNIQ_DS_A})  # cria o arquivo
        vistos: list[bool] = []
        original = Path.read_text

        def espiao(self_path: Path, *a: Any, **kw: Any) -> str:
            if self_path.name == "controllers.json":
                vistos.append(CONTROLLERS_FILE_LOCK.locked())
            return original(self_path, *a, **kw)

        monkeypatch.setattr(Path, "read_text", espiao)
        ControllerIdentityRegistry().load()
        assert vistos == [True]

    def test_external_load_segura_o_lock_durante_o_read(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        criador = ExternalIdentityRegistry()
        criador.slot_for(MAC_EXT_A, reserve=0)
        criador.sync_connected([MAC_EXT_A])  # cria o arquivo
        vistos: list[bool] = []
        original = Path.read_text

        def espiao(self_path: Path, *a: Any, **kw: Any) -> str:
            if self_path.name == "controllers.json":
                vistos.append(CONTROLLERS_FILE_LOCK.locked())
            return original(self_path, *a, **kw)

        monkeypatch.setattr(Path, "read_text", espiao)
        ExternalIdentityRegistry().load()
        assert vistos == [True]


class TestRmwIntercaladoAmbosNamespacesSobrevivem:
    """O aceite literal do item 12: RMW intercalado dos dois registries não
    pode fazer nenhum namespace sumir (no HEAD, sem o lock compartilhado,
    um dos dois desaparece — verificado manualmente trocando o lock do lado
    externo por um separado antes desta leva; não repetir aqui: o teste já
    falha nesse cenário por construção, é o próprio propósito do lock)."""

    def test_rmw_intercalado_preserva_slots_e_externals(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        ds = ControllerIdentityRegistry()
        ds.slot_for(UNIQ_DS_A)  # marca sujo, save pendente

        ext = ExternalIdentityRegistry()
        ext.slot_for(MAC_EXT_A, reserve=0)  # marca sujo, save pendente

        ds_entrou_no_read = threading.Event()
        pode_prosseguir = threading.Event()
        pausado_uma_vez = {"sim": False}
        original_read_text = Path.read_text

        def read_text_com_barreira(self_path: Path, *a: Any, **kw: Any) -> str:
            # Pausa a PRIMEIRA leitura de controllers.json (a do DualSense,
            # que entra no read_text primeiro — garantido pelo wait abaixo
            # antes de a thread do externo sequer existir) DENTRO do lock:
            # se o lock protege de verdade, a thread do externo bloqueia no
            # próprio `.acquire()` até esta pausa liberar.
            if self_path.name == "controllers.json" and not pausado_uma_vez["sim"]:
                pausado_uma_vez["sim"] = True
                ds_entrou_no_read.set()
                assert pode_prosseguir.wait(timeout=5.0), "barreira nunca liberada"
            return original_read_text(self_path, *a, **kw)

        monkeypatch.setattr(Path, "read_text", read_text_com_barreira)

        erros: list[BaseException] = []

        def rodar_ds() -> None:
            try:
                ds.sync_connected({UNIQ_DS_A})
            except Exception as exc:  # pragma: no cover - defensivo
                erros.append(exc)

        def rodar_ext() -> None:
            try:
                ext.sync_connected([MAC_EXT_A])
            except Exception as exc:  # pragma: no cover - defensivo
                erros.append(exc)

        t_ds = threading.Thread(target=rodar_ds, name="ds-save")
        t_ds.start()
        assert ds_entrou_no_read.wait(timeout=5.0), "ds não entrou no read a tempo"

        # A thread do externo só existe (e só tenta o lock) DEPOIS que o
        # DualSense já está parado dentro da seção crítica — a intercalação
        # que no HEAD perde um dos dois namespaces.
        t_ext = threading.Thread(target=rodar_ext, name="ext-save")
        t_ext.start()

        pode_prosseguir.set()
        t_ds.join(timeout=5.0)
        t_ext.join(timeout=5.0)
        assert not t_ds.is_alive(), "thread do DualSense travou"
        assert not t_ext.is_alive(), "thread do externo travou"
        assert erros == []

        data = _arquivo(isolated_config)
        assert data["slots"] == {UNIQ_DS_A: 1}, "namespace do DualSense sumiu"
        assert data["externals"] == {MAC_EXT_A: 1}, "namespace externo sumiu"


class TestColisaoNoLoad:
    """Cross-check UNILATERAL: um slot presente nos DOIS namespaces do MESMO
    arquivo (corrupção herdada de um lost-update pretérito) resolve a favor
    do DualSense. Nunca realocação; nunca poda bilateral (a spec veta as
    duas explicitamente — juízes 1/3 e juiz 2)."""

    def _grava_arquivo_colidido(self, tmp: Path) -> None:
        (tmp / "controllers.json").write_text(
            json.dumps(
                {
                    "boot_id": BOOT,
                    "slots": {UNIQ_DS_A: 1},
                    "externals": {
                        MAC_EXT_A: 1,  # COLIDE com o slot 1 do DualSense
                        MAC_EXT_B: 2,  # não colide — sobrevive intacto
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_entrada_externa_colidente_e_dropada_com_warn(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._grava_arquivo_colidido(isolated_config)

        eventos: list[tuple[str, dict[str, Any]]] = []

        class _SpyLogger:
            def warning(self, evento: str, **kw: Any) -> None:
                eventos.append((evento, kw))

            def info(self, *_a: Any, **_kw: Any) -> None: ...
            def debug(self, *_a: Any, **_kw: Any) -> None: ...

        monkeypatch.setattr(ei_mod, "logger", _SpyLogger())

        ext = ExternalIdentityRegistry()
        ext.load()

        assert ext.snapshot() == {MAC_EXT_B: 2}, "o colidente deveria sumir"
        assert eventos == [
            ("controllers_json_colisao_descartada", {"slot": 1, "externo": MAC_EXT_A})
        ]

    def test_dualsense_fica_intacto_sem_realocacao(
        self, isolated_config: Path
    ) -> None:
        self._grava_arquivo_colidido(isolated_config)

        ds = ControllerIdentityRegistry()
        ds.load()
        # O DualSense nunca sabe da colisão nem muda de comportamento — ele
        # nem lê o namespace `externals`. Nenhuma realocação de slot.
        assert ds.snapshot() == {UNIQ_DS_A: 1}

    def test_colisao_nao_poda_bilateralmente(self, isolated_config: Path) -> None:
        """Veto do juiz 2: as DUAS entradas caindo renumeraria ambas — só a
        externa cai, a DualSense permanece intocada."""
        self._grava_arquivo_colidido(isolated_config)

        ds = ControllerIdentityRegistry()
        ds.load()
        ext = ExternalIdentityRegistry()
        ext.load()

        assert ds.snapshot() == {UNIQ_DS_A: 1}  # sobrevive
        assert ext.snapshot() == {MAC_EXT_B: 2}  # só o não-colidente sobrevive
        # E ninguém rouba o slot 1 de volta por realocação automática.
        assert 1 not in ext.snapshot().values()

    def test_arquivo_saneado_no_proximo_save(self, isolated_config: Path) -> None:
        """Depois do load com colisão, o próximo save do lado externo grava
        só o que sobreviveu — a entrada colidente nunca mais reaparece."""
        self._grava_arquivo_colidido(isolated_config)

        ext = ExternalIdentityRegistry()
        ext.load()
        # Nova atribuição para marcar sujo e disparar o save (reserve=1
        # espelha `_ds_reserve()` em produção: o DualSense detém o slot 1).
        assert ext.slot_for("aabbcc001234", reserve=1) == 3
        ext.sync_connected([MAC_EXT_B, "aabbcc001234"])

        data = _arquivo(isolated_config)
        assert MAC_EXT_A not in data["externals"], "colidente ressuscitou no save"
        assert data["externals"] == {MAC_EXT_B: 2, "aabbcc001234": 3}
        assert data["slots"] == {UNIQ_DS_A: 1}, "save externo preservou o outro lado"

    def test_sem_colisao_carrega_normalmente(
        self, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Falha-sem inverso: sem sobreposição de slot nenhum, o cross-check
        não descarta nada nem loga o WARN (regressão do comportamento são)."""
        (isolated_config / "controllers.json").write_text(
            json.dumps(
                {
                    "boot_id": BOOT,
                    "slots": {UNIQ_DS_A: 1},
                    "externals": {MAC_EXT_A: 2},
                }
            ),
            encoding="utf-8",
        )
        eventos: list[tuple[str, dict[str, Any]]] = []

        class _SpyLogger:
            def warning(self, evento: str, **kw: Any) -> None:
                eventos.append((evento, kw))

            def info(self, *_a: Any, **_kw: Any) -> None: ...
            def debug(self, *_a: Any, **_kw: Any) -> None: ...

        monkeypatch.setattr(ei_mod, "logger", _SpyLogger())
        ext = ExternalIdentityRegistry()
        ext.load()
        assert ext.snapshot() == {MAC_EXT_A: 2}
        assert eventos == []
