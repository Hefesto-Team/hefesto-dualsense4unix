"""NUM-01 — quem está na mesa é 1..N (sprint 2026-07-25).

O relato medido: "ao usar o branco ele sempre liga no player 2 setado, ao
invés de ligar pela ordem correta — se ele conectou primeiro deveria ser o
player 1". O ``controllers.json`` dela, com UM controle ligado, dizia
``{"version": 2, "slots": {"<A>": 1, "<B>": 2}}``: o número 1 estava
RESERVADO a um endereço que não estava na mesa, e o único controle ligado
exibia 2.

A cura separa dois conceitos que eram o mesmo inteiro — IDENTIDADE (o
endereço, que carrega um LUGAR NA FILA de preferência) e POSIÇÃO NA MESA
(1..N entre os presentes, derivada). Este arquivo cobre os seis cenários de
validação da sprint mais o critério que os resume: **nunca deve existir um
jogador 2 sem jogador 1**.

Os dois requisitos que a sprint diz serem verdadeiros AO MESMO TEMPO — e que
antes se excluíam — têm caso próprio aqui:

- ESTABILIDADE (R-15/R-23): com os dois na mesa, cada um mantém o seu número
  entre sessões e entre boots; a ordem de wake não troca dono de nada;
- NATURALIDADE (NUM-01): sozinho na mesa, o controle é o jogador 1.

Herméticos: ``config_dir`` monkeypatchado nos DOIS módulos de registro (eles
dividem o MESMO arquivo) e ``boot_id`` fixo. MACs sempre na faixa forjada
``aa:bb:cc:*`` — teste-guarda de anonimato.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from hefesto_dualsense4unix.daemon.subsystems import external_identity as ei_mod
from hefesto_dualsense4unix.daemon.subsystems import identity as id_mod
from hefesto_dualsense4unix.daemon.subsystems.external_identity import (
    ExternalIdentityRegistry,
    ExternalLedSync,
)
from hefesto_dualsense4unix.daemon.subsystems.identity import (
    ControllerIdentityRegistry,
)

#: Os dois DualSense da casa (MACs forjados — faixa aa:bb:cc).
UNIQ_A = "aabbcc000001"  # o roxo
UNIQ_B = "aabbcc000002"  # o branco, o do relato
#: Um externo (Pro Nintendo / 8BitDo) para o cenário de mesa mista.
MAC_EXTERNO = "aabbcc0000fe"

BOOT = "boot-teste-num01"


@pytest.fixture
def config_isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """``config_dir`` em tmp + âncora fixa nos dois registros (mesmo arquivo)."""
    from hefesto_dualsense4unix.utils import xdg_paths

    def fake_config_dir(ensure: bool = False) -> Path:
        if ensure:
            tmp_path.mkdir(parents=True, exist_ok=True)
        return tmp_path

    monkeypatch.setattr(xdg_paths, "config_dir", fake_config_dir)
    monkeypatch.setattr(id_mod, "_read_boot_id", lambda: BOOT)
    monkeypatch.setattr(ei_mod, "_read_boot_id", lambda: BOOT)
    return tmp_path


def _arquivo(tmp: Path) -> dict[str, object]:
    return json.loads((tmp / "controllers.json").read_text(encoding="utf-8"))


def _fila(tmp: Path, kind: str = id_mod.KIND_DUALSENSE) -> dict[str, int]:
    """Endereço → lugar na fila, lidos do campo ``order`` (schema 3)."""
    entradas = _arquivo(tmp)[id_mod.ORDER_FIELD]
    assert isinstance(entradas, list)
    return {
        str(e["addr"]): int(e["rank"])
        for e in entradas
        if isinstance(e, dict) and e.get("kind") == kind
    }


def _mesa(reg: ControllerIdentityRegistry, *uniqs: str) -> dict[str, int | None]:
    """Números EXIBIDOS depois de reconciliar a mesa com ``uniqs``.

    Espelha o que o lifecycle faz a cada tick lento (``sync_connected`` com a
    ordem de ``describe_controllers``) e depois consulta como o provider de
    cor consulta — leitura pura, para a consulta não mexer na presença.
    """
    reg.sync_connected(list(uniqs))
    return {uniq: reg.slot_for(uniq, assign=False) for uniq in uniqs}


class TestOsSeisCenariosDaSprint:
    """A sequência de validação da sprint, na ordem, num registro só.

    Falha-sem (o estado medido): o passo 1 devolvia 2 para o controle sozinho
    na mesa, porque o lugar 1 pertencia a um endereço desligado e lugar era
    número.
    """

    def test_1_o_controle_sozinho_na_mesa_e_o_jogador_1(
        self, config_isolado: Path
    ) -> None:
        reg = ControllerIdentityRegistry()
        assert _mesa(reg, UNIQ_B) == {UNIQ_B: 1}

    def test_2_ligar_o_outro_nao_faz_ninguem_piscar(
        self, config_isolado: Path
    ) -> None:
        """B já estava na mesa; A chega e entra ATRÁS — B continua 1."""
        reg = ControllerIdentityRegistry()
        _mesa(reg, UNIQ_B)
        assert _mesa(reg, UNIQ_B, UNIQ_A) == {UNIQ_B: 1, UNIQ_A: 2}

    def test_3_desligar_o_primeiro_promove_quem_ficou(
        self, config_isolado: Path
    ) -> None:
        """A lacuna se fecha sozinha: é a "compactação automática" da sprint,
        que aqui não é um passo — é consequência de contar só os presentes."""
        reg = ControllerIdentityRegistry()
        _mesa(reg, UNIQ_B, UNIQ_A)
        assert _mesa(reg, UNIQ_A) == {UNIQ_A: 1}

    def test_4_religar_devolve_a_cada_um_a_sua_colocacao(
        self, config_isolado: Path
    ) -> None:
        """A ordem de preferência não mudou em nenhum dos passos acima: com
        os dois de volta, cada um recupera o número que era dele."""
        reg = ControllerIdentityRegistry()
        _mesa(reg, UNIQ_B, UNIQ_A)
        _mesa(reg, UNIQ_A)  # B saiu; A virou 1
        assert _mesa(reg, UNIQ_A, UNIQ_B) == {UNIQ_A: 2, UNIQ_B: 1}
        assert reg.snapshot() == {UNIQ_B: 1, UNIQ_A: 2}, "a fila nunca mudou"

    def test_5_restart_do_daemon_mantem_a_ordem(self, config_isolado: Path) -> None:
        """Restart = instância nova + ``load()``. R-23 continua de pé."""
        reg = ControllerIdentityRegistry()
        _mesa(reg, UNIQ_B, UNIQ_A)

        reiniciado = ControllerIdentityRegistry()
        reiniciado.load()
        assert _mesa(reiniciado, UNIQ_A, UNIQ_B) == {UNIQ_A: 2, UNIQ_B: 1}
        # E com um só ligado depois do restart ele é o jogador 1 — o
        # cruzamento exato dos dois requisitos da sprint.
        assert _mesa(reiniciado, UNIQ_A) == {UNIQ_A: 1}

    def test_6_reboot_da_maquina_mantem_a_ordem(
        self, config_isolado: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Âncora diferente = outro boot. Ela ANOTA, nunca decide (R-23)."""
        reg = ControllerIdentityRegistry()
        _mesa(reg, UNIQ_B, UNIQ_A)

        monkeypatch.setattr(id_mod, "_read_boot_id", lambda: "outro-boot")
        depois_do_reboot = ControllerIdentityRegistry()
        depois_do_reboot.load()
        assert depois_do_reboot.snapshot() == {UNIQ_B: 1, UNIQ_A: 2}
        assert _mesa(depois_do_reboot, UNIQ_A, UNIQ_B) == {UNIQ_A: 2, UNIQ_B: 1}


class TestOsDoisRequisitosJuntos:
    """A tabela da sprint: fila ``[A, B]`` persistida, três estados de mesa.

    É o caso que prova que a escolha "estabilidade OU naturalidade" acabou —
    a mesma fila gravada responde as duas perguntas.
    """

    def _com_fila_ab(self, tmp: Path) -> ControllerIdentityRegistry:
        semente = ControllerIdentityRegistry()
        semente.sync_connected([UNIQ_A, UNIQ_B])  # A chegou primeiro
        assert _fila(tmp) == {UNIQ_A: 1, UNIQ_B: 2}
        reg = ControllerIdentityRegistry()
        reg.load()
        return reg

    def test_os_dois_ligados_cada_um_mantem_o_seu(
        self, config_isolado: Path
    ) -> None:
        reg = self._com_fila_ab(config_isolado)
        assert _mesa(reg, UNIQ_A, UNIQ_B) == {UNIQ_A: 1, UNIQ_B: 2}

    def test_so_o_b_ligado_ele_e_o_jogador_1(self, config_isolado: Path) -> None:
        """O caso EXATO do relato — com a fila dizendo que A vem antes.

        Falha-sem: era aqui que saía 2, e era permanente (nada expirava e
        nada reivindicava um número vago).
        """
        reg = self._com_fila_ab(config_isolado)
        assert _mesa(reg, UNIQ_B) == {UNIQ_B: 1}
        assert reg.snapshot() == {UNIQ_A: 1, UNIQ_B: 2}, "sem mexer na fila"

    def test_os_dois_de_volta_voltam_ao_lugar(self, config_isolado: Path) -> None:
        reg = self._com_fila_ab(config_isolado)
        _mesa(reg, UNIQ_B)
        assert _mesa(reg, UNIQ_A, UNIQ_B) == {UNIQ_A: 1, UNIQ_B: 2}


class TestNuncaJogador2SemJogador1:
    """O critério que resume a sprint, inclusive na mesa MISTA.

    A contagem é da mesa inteira (DualSense + externos), então a prova tem de
    passar pelo registro dos externos também — é ele que o co-op e o LED de
    número dos aparelhos de terceiros consultam.
    """

    @staticmethod
    def _numeros(
        ds: ControllerIdentityRegistry,
        ext: ExternalIdentityRegistry,
        presentes_ds: list[str],
        presentes_ext: list[str],
    ) -> list[int]:
        ds.sync_connected(presentes_ds)
        ext.sync_connected(presentes_ext)
        piso = max(ds.snapshot().values(), default=0)
        numeros = [ds.slot_for(u, assign=False) for u in presentes_ds]
        numeros += [ext.slot_for(u, reserve=piso) for u in presentes_ext]
        return sorted(n for n in numeros if n is not None)

    def test_mesa_mista_ocupa_1_a_n_em_qualquer_combinacao(
        self, config_isolado: Path
    ) -> None:
        """Três controles registrados; toda combinação de presença exibe
        exatamente 1..N, sem buraco e sem repetição.

        Falha-sem: com o registro antigo, desligar o DualSense do lugar 1
        deixava a mesa exibindo 2 e 3 — "não existe Controle 1", medido ao
        vivo no arquivo dela.
        """
        ds = ControllerIdentityRegistry()
        ext = ExternalIdentityRegistry()
        ds.set_external_reserve_provider(lambda: set(ext.snapshot().values()))
        # Fiação de produção da EXIBIÇÃO: é o `ExternalLedSync` que casa os
        # dois registros nos dois sentidos (`_wire_presence_providers`).
        ExternalLedSync(SimpleNamespace(identity_registry=ds), ext)

        # Estado inicial: os dois DualSense e o externo, todos na mesa.
        assert self._numeros(ds, ext, [UNIQ_A, UNIQ_B], [MAC_EXTERNO]) == [1, 2, 3]

        combinacoes = [
            ([UNIQ_A, UNIQ_B], [MAC_EXTERNO]),
            ([UNIQ_A], [MAC_EXTERNO]),
            ([UNIQ_B], [MAC_EXTERNO]),
            ([UNIQ_A, UNIQ_B], []),
            ([UNIQ_B], []),
            ([], [MAC_EXTERNO]),
            ([UNIQ_A, UNIQ_B], [MAC_EXTERNO]),
        ]
        for presentes_ds, presentes_ext in combinacoes:
            numeros = self._numeros(ds, ext, presentes_ds, presentes_ext)
            esperado = list(range(1, len(presentes_ds) + len(presentes_ext) + 1))
            assert numeros == esperado, (
                f"mesa {presentes_ds}+{presentes_ext} exibiu {numeros}"
            )

    def test_externo_sozinho_na_mesa_e_o_jogador_1(
        self, config_isolado: Path
    ) -> None:
        """Vale para o Pro Nintendo/8BitDo também: ninguém aceita ser o
        jogador 2 de si mesmo, nem quem não é DualSense."""
        ds = ControllerIdentityRegistry()
        ext = ExternalIdentityRegistry()
        ExternalLedSync(SimpleNamespace(identity_registry=ds), ext)
        ds.sync_connected([UNIQ_A, UNIQ_B])
        piso = max(ds.snapshot().values())
        assert ext.slot_for(MAC_EXTERNO, reserve=piso) == 3

        ds.sync_connected([])  # os dois DualSense saíram
        ext.sync_connected([MAC_EXTERNO])
        assert ext.peek(MAC_EXTERNO) == 1
        assert ext.snapshot() == {MAC_EXTERNO: 3}, "o lugar na fila é o mesmo"


class TestRenumerarAgoraNaoEstragaOAusente:
    """Entrega 2 da sprint: o gesto de conserto perdeu o efeito colateral.

    O plano do ``identity.renumber`` continua o MESMO (presentes na frente,
    ausentes atrás — R-15); o que mudou é que os inteiros que ele escreve são
    LUGARES NA FILA. Empurrar o ausente para trás deixou de rebaixá-lo: o
    número dele volta a ser calculado quando ele voltar para a mesa.

    Falha-sem: com o número absoluto, este mesmo gesto gravava o ausente como
    "o segundo" para sempre — foi assim que o arquivo dela apareceu invertido
    dentro de uma única sessão do daemon.
    """

    def test_o_ausente_volta_no_numero_certo_depois_do_renumerar(
        self, config_isolado: Path
    ) -> None:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B])  # fila [A, B]
        ds.sync_connected([UNIQ_B])  # A saiu; B exibe 1

        renumerados = IpcHandlersMixin._renumber_locked(ds, None)
        # O plano põe o presente na frente: B passa ao lugar 1, A ao 2.
        assert renumerados == {UNIQ_B: 1, UNIQ_A: 2}
        assert ds.snapshot() == {UNIQ_B: 1, UNIQ_A: 2}
        assert ds.slot_for(UNIQ_B, assign=False) == 1

        # E o ausente NÃO foi rebaixado a "jogador 2 permanente": sozinho na
        # mesa ele é 1, e com os dois ele é o 2 (a fila que ela pediu).
        assert _mesa(ds, UNIQ_A) == {UNIQ_A: 1}
        assert _mesa(ds, UNIQ_A, UNIQ_B) == {UNIQ_A: 2, UNIQ_B: 1}

    def test_renumerar_nao_dropa_a_reserva_do_ausente(
        self, config_isolado: Path
    ) -> None:
        """D2 continua de pé: o ausente perde a fila, nunca a entrada."""
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        ds = ControllerIdentityRegistry()
        ds.sync_connected([UNIQ_A, UNIQ_B])
        ds.sync_connected([UNIQ_B])
        IpcHandlersMixin._renumber_locked(ds, None)
        assert UNIQ_A in ds.snapshot()


class TestMigracaoDoArquivoReal:
    """O bump de esquema é o que devolve a casa à numeração certa.

    O ``controllers.json`` da mantenedora (schema 2) grava NÚMERO ABSOLUTO:
    descartá-lo uma vez e renumerar na ordem de chegada é aceitável, e é
    exatamente para isso que o campo de versão existe (R-23).
    """

    def test_arquivo_schema_2_e_descartado_e_a_casa_renumera_na_chegada(
        self, config_isolado: Path
    ) -> None:
        (config_isolado / "controllers.json").write_text(
            json.dumps(
                {
                    "version": 2,
                    "boot_id": BOOT,
                    "slots": {UNIQ_A: 1, UNIQ_B: 2},
                    "externals": {MAC_EXTERNO: 3, "aabbcc0000ff": 4},
                }
            ),
            encoding="utf-8",
        )
        ds = ControllerIdentityRegistry()
        ds.load()
        ext = ExternalIdentityRegistry()
        ext.load()
        assert ds.snapshot() == {} and ext.snapshot() == {}

        # Primeira sessão do regime novo: só o branco está ligado, e ele é o
        # jogador 1 — o desfecho que o relato pedia.
        assert _mesa(ds, UNIQ_B) == {UNIQ_B: 1}
        assert _arquivo(config_isolado)["version"] == (
            id_mod.CONTROLLERS_SCHEMA_VERSION
        )
        assert _fila(config_isolado) == {UNIQ_B: 1}
        # E a numeração velha não pode ressuscitar por um save do outro lado.
        assert _fila(config_isolado, id_mod.KIND_EXTERNAL) == {}

    def test_a_casa_sem_arquivo_nenhum_nasce_no_1(
        self, config_isolado: Path
    ) -> None:
        ds = ControllerIdentityRegistry()
        ds.load()  # não existe arquivo — não levanta
        assert _mesa(ds, UNIQ_B) == {UNIQ_B: 1}
