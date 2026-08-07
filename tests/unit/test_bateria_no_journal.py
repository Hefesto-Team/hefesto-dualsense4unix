"""O daemon grava a bateria no journal — entrega 1 do PROTOCOLO de 07/08/2026.

Documento:
``docs/process/estudos/2026-08-07-PROTOCOLO-o-controle-que-cai-sozinho.md``.

O defeito que estes testes trancam, MEDIDO em 07/08: o daemon lia a carga a cada
tique e **não escrevia uma linha**, então a hipótese mais forte para as nove
quedas de link (a carga acabando) era indecidível por falta de instrumento.

Cinco contratos, e cada um tem uma mordida escrita no docstring da classe:

1. a **faixa** e a **máscara** são funções puras e previsíveis;
2. a **cadência** escreve na mudança e cala no repouso — uma sessão inteira de
   16 h cabe em dezenas de linhas, não em milhares;
3. a **queda** sempre deixa a última carga conhecida, com a idade dela;
4. o **endereço nunca sai cru** — nem na amostra, nem na queda;
5. a **fiação** existe: o poll loop sonda e a borda de desconexão registra.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.daemon.battery_journal import (
    FAIXAS,
    INTERVALO_ANCORA_S,
    INTERVALO_SONDA_S,
    JANELA_DEDUP_QUEDA_S,
    PREFIXO_NO_KERNEL,
    SEM_ENDERECO,
    DiarioDaBateria,
    faixa_de,
    ler_no_do_kernel,
    mascarar_endereco,
)
from tests.unit.test_docs_mac_anonimato import (
    MAC_COMPLETO_RE,
    _OUIS_REAIS_OCTETOS,
    _partes,
)

# --------------------------------------------------------------------------
# Fixtures de endereço
# --------------------------------------------------------------------------

#: Sufixo INVENTADO. Ele só vira "forma de MAC" quando colado ao OUI real em
#: tempo de execução — escrever o endereço inteiro aqui faria os DOIS portões de
#: anonimato reprovarem este arquivo, que é exatamente o ponto do teste.
_SUFIXO_DE_FIXTURE = "c31af7"


def _uniq_realista() -> str:
    """Endereço com OUI REAL desta bancada, montado em tempo de execução.

    É o formato que o produto gera: 12 dígitos hex colados, como o ``uniq`` sai
    do backend e do ``controllers.json``. Usar um OUI real importa: é ele que o
    portão do repositório reconhece, e é contra o portão que a mordida do MAC
    é medida.
    """
    return "".join(_OUIS_REAIS_OCTETOS[0]) + _SUFIXO_DE_FIXTURE


def _texto_de_registros(registros: list[dict[str, Any]]) -> str:
    """Tudo o que foi para o journal, num texto só — chave e valor."""
    return "\n".join(
        " ".join(f"{k}={v}" for k, v in sorted(reg.items())) for reg in registros
    )


def _macs_sem_mascara(texto: str) -> list[str]:
    """Endereços de hardware REAL sem a máscara da casa, pelo regex do portão."""
    achados = []
    for m in MAC_COMPLETO_RE.finditer(texto):
        _oui, oct4, oct5 = _partes(m)
        if oct4 == "00" and oct5 == "00":
            continue
        achados.append(m.group(0))
    return achados


def _no_do_kernel(raiz: Path, uniq: str, capacity: str, status: str) -> Path:
    """Cria um nó de bateria falso, com o mesmo nome que o driver usa."""
    digitos = uniq.lower()
    endereco = ":".join(digitos[i : i + 2] for i in range(0, 12, 2))
    no = raiz / f"{PREFIXO_NO_KERNEL}{endereco}"
    no.mkdir(parents=True, exist_ok=True)
    (no / "capacity").write_text(capacity, encoding="utf-8")
    (no / "status").write_text(status, encoding="utf-8")
    return no


def _descreve(uniq: str, pct: int | None, *, conectado: bool = True) -> dict[str, Any]:
    """Uma entrada de ``describe_controllers()`` como o backend a devolve."""
    return {
        "index": 0,
        "connected": conectado,
        "transport": "bt",
        "is_primary": True,
        "uniq": uniq,
        "battery_pct": pct,
    }


# --------------------------------------------------------------------------
# 1. Faixa e máscara
# --------------------------------------------------------------------------


class TestFaixaEMascara:
    """Mordida: mude uma fronteira de :data:`FAIXAS` e os limites reprovam."""

    @pytest.mark.parametrize(
        ("pct", "esperado"),
        [
            (100, 100),
            (95, 90),
            (41, 40),
            (40, 40),
            (39, 30),
            (20, 20),
            (19, 15),
            (5, 5),
            (4, 0),
            (0, 0),
        ],
    )
    def test_faixa_e_a_maior_fronteira_menor_ou_igual(
        self, pct: int, esperado: int
    ) -> None:
        assert faixa_de(pct) == esperado

    def test_sem_leitura_nao_tem_faixa(self) -> None:
        assert faixa_de(None) is None

    def test_todo_degrau_do_hardware_cruza_uma_fronteira(self) -> None:
        """O ``hid-playstation`` reporta 5, 15, 25 … 95 — nenhum degrau se perde.

        Se alguém trocar as faixas por deciles puros, 5→15 e 15→25 passariam a
        cair na MESMA faixa e a descida final ficaria invisível, que é
        justamente o trecho da curva que decide a Q-1 do protocolo.
        """
        degraus = [0, *range(5, 100, 10), 100]
        faixas = [faixa_de(d) for d in degraus]
        assert len(set(faixas)) == len(faixas), f"degraus colapsados: {faixas}"

    def test_mascara_zera_os_octetos_4_e_5(self) -> None:
        mascarado = mascarar_endereco(_uniq_realista())
        octetos = mascarado.split(":")
        assert octetos[3] == "00" and octetos[4] == "00"
        # O que a análise precisa sobrevive: fabricante e último octeto.
        assert octetos[:3] == list(_OUIS_REAIS_OCTETOS[0])
        assert octetos[5] == _SUFIXO_DE_FIXTURE[-2:]

    def test_mascara_aceita_as_duas_grafias(self) -> None:
        colado = _uniq_realista()
        com_separador = ":".join(colado[i : i + 2] for i in range(0, 12, 2))
        assert mascarar_endereco(colado) == mascarar_endereco(com_separador)

    @pytest.mark.parametrize("valor", [None, "", "/dev/hidraw3", "deda4", "zz"])
    def test_sem_endereco_reconhecivel_nao_inventa_identidade(
        self, valor: str | None
    ) -> None:
        assert mascarar_endereco(valor) == SEM_ENDERECO

    def test_a_mascara_passa_pelo_portao_do_repositorio(self) -> None:
        assert _macs_sem_mascara(mascarar_endereco(_uniq_realista())) == []
        # E a fixture crua REPROVA — senão o portão acima não provaria nada.
        assert _macs_sem_mascara(_uniq_realista()) != []


# --------------------------------------------------------------------------
# 2. O nó do kernel
# --------------------------------------------------------------------------


class TestNoDoKernel:
    """Mordida: apague o ``except OSError`` do leitor e a ausência vira exceção."""

    def test_le_capacidade_e_status(self, tmp_path: Path) -> None:
        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "5\n", "Charging\n")
        assert ler_no_do_kernel(uniq, raiz=tmp_path) == (5, "Charging")

    def test_no_ausente_nao_levanta(self, tmp_path: Path) -> None:
        assert ler_no_do_kernel(_uniq_realista(), raiz=tmp_path) == (None, None)

    def test_capacidade_ilegivel_vira_ausencia(self, tmp_path: Path) -> None:
        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "vazio", "Discharging")
        assert ler_no_do_kernel(uniq, raiz=tmp_path) == (None, "Discharging")

    def test_endereco_invalido_nao_vira_caminho(self, tmp_path: Path) -> None:
        assert ler_no_do_kernel("/dev/hidraw3", raiz=tmp_path) == (None, None)


# --------------------------------------------------------------------------
# 3. A cadência
# --------------------------------------------------------------------------


class TestCadencia:
    """Mordida: troque o gate por ``return True`` e a sessão de 16 h estoura.

    Arranque o gate de :data:`INTERVALO_SONDA_S` (ou o ``motivo is None`` do
    diário) e ``test_sessao_de_dezesseis_horas_cabe_em_dezenas_de_linhas``
    reprova com milhares de linhas — que é a poluição de journal que a decisão
    de cadência existe para evitar.
    """

    def _diario(self, tmp_path: Path) -> DiarioDaBateria:
        return DiarioDaBateria(raiz=tmp_path)

    def test_primeira_leitura_abre_a_curva(self, tmp_path: Path) -> None:
        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "95", "Discharging")
        diario = self._diario(tmp_path)
        with structlog.testing.capture_logs() as registros:
            escritas = diario.observar([_descreve(uniq, 90)], 1000.0)
        assert escritas == 1
        assert registros[0]["event"] == "bateria_amostra"
        assert registros[0]["motivo"] == "abertura"
        # As DUAS réguas na mesma linha — regra da casa: todo instrumento
        # declara contra o que mede.
        assert registros[0]["pct_kernel"] == 95
        assert registros[0]["pct_handle"] == 90
        assert registros[0]["fonte"] == "kernel"

    def test_dentro_do_intervalo_nem_sonda(self, tmp_path: Path) -> None:
        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "95", "Discharging")
        diario = self._diario(tmp_path)
        diario.observar([_descreve(uniq, 90)], 1000.0)
        _no_do_kernel(tmp_path, uniq, "5", "Discharging")
        with structlog.testing.capture_logs() as registros:
            escritas = diario.observar([_descreve(uniq, 5)], 1000.0 + 1.0)
        assert escritas == 0 and registros == []

    def test_repouso_nao_escreve(self, tmp_path: Path) -> None:
        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "95", "Discharging")
        diario = self._diario(tmp_path)
        diario.observar([_descreve(uniq, 90)], 1000.0)
        with structlog.testing.capture_logs() as registros:
            escritas = diario.observar(
                [_descreve(uniq, 90)], 1000.0 + INTERVALO_SONDA_S
            )
        assert escritas == 0 and registros == []

    def test_queda_de_faixa_escreve_com_a_borda(self, tmp_path: Path) -> None:
        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "15", "Discharging")
        diario = self._diario(tmp_path)
        diario.observar([_descreve(uniq, 15)], 1000.0)
        _no_do_kernel(tmp_path, uniq, "5", "Discharging")
        with structlog.testing.capture_logs() as registros:
            diario.observar([_descreve(uniq, 5)], 1000.0 + INTERVALO_SONDA_S)
        assert registros[0]["motivo"] == "faixa"
        assert registros[0]["borda"] == "queda"
        assert registros[0]["faixa"] == 5

    def test_subida_de_faixa_escreve_com_a_borda(self, tmp_path: Path) -> None:
        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "5", "Charging")
        diario = self._diario(tmp_path)
        diario.observar([_descreve(uniq, 5)], 1000.0)
        _no_do_kernel(tmp_path, uniq, "15", "Charging")
        with structlog.testing.capture_logs() as registros:
            diario.observar([_descreve(uniq, 15)], 1000.0 + INTERVALO_SONDA_S)
        assert registros[0]["motivo"] == "faixa"
        assert registros[0]["borda"] == "subida"

    def test_borda_do_cabo_escreve_mesmo_sem_mudar_de_faixa(
        self, tmp_path: Path
    ) -> None:
        """O cabo entrando é o dado que separa "acabou" de "caiu"."""
        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "5", "Discharging")
        diario = self._diario(tmp_path)
        diario.observar([_descreve(uniq, 5)], 1000.0)
        _no_do_kernel(tmp_path, uniq, "5", "Charging")
        with structlog.testing.capture_logs() as registros:
            diario.observar([_descreve(uniq, 5)], 1000.0 + INTERVALO_SONDA_S)
        assert registros[0]["motivo"] == "status"
        assert registros[0]["borda"] == "subida"
        assert registros[0]["status"] == "Charging"

    def test_ancora_prova_que_o_instrumento_seguia_vivo(
        self, tmp_path: Path
    ) -> None:
        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "95", "Discharging")
        diario = self._diario(tmp_path)
        agora = 1000.0
        diario.observar([_descreve(uniq, 95)], agora)
        # Meia hora de curva reta: nada muda, e mesmo assim uma âncora sai.
        vistos: list[dict[str, Any]] = []
        with structlog.testing.capture_logs() as registros:
            passos = int(INTERVALO_ANCORA_S / INTERVALO_SONDA_S) + 1
            for i in range(1, passos + 1):
                diario.observar([_descreve(uniq, 95)], agora + i * INTERVALO_SONDA_S)
            vistos = list(registros)
        assert len(vistos) == 1, "a âncora tem de ser UMA por meia hora"
        assert vistos[0]["motivo"] == "ancora"

    def test_sessao_de_dezesseis_horas_cabe_em_dezenas_de_linhas(
        self, tmp_path: Path
    ) -> None:
        """A descida inteira de 100% a 0% em 16 h, sondada a cada 30 s.

        São 1.920 sondas. Se cada uma virasse linha, o journal ganharia ~2 mil
        entradas por sessão e a bateria sumiria no ruído — o motivo declarado
        para NÃO registrar a cada tique.
        """
        uniq = _uniq_realista()
        diario = self._diario(tmp_path)
        agora = 1000.0
        sondas = int(16 * 3600 / INTERVALO_SONDA_S)
        degraus = [100, *range(95, 0, -10), 0]
        with structlog.testing.capture_logs() as registros:
            for i in range(sondas):
                # A carga cai um degrau do hardware a cada fatia da sessão.
                pct = degraus[min(i * len(degraus) // sondas, len(degraus) - 1)]
                _no_do_kernel(tmp_path, uniq, str(pct), "Discharging")
                diario.observar([_descreve(uniq, pct)], agora + i * INTERVALO_SONDA_S)
            escritas = len(registros)
        assert escritas <= 60, f"cadência poluindo o journal: {escritas} linhas"
        assert escritas >= len(degraus), "a curva inteira não pode caber numa linha"

    def test_sem_uniq_nao_escreve_linha_orfa(self, tmp_path: Path) -> None:
        """Sem endereço não há nó do kernel nem identidade entre sondas."""
        diario = self._diario(tmp_path)
        with structlog.testing.capture_logs() as registros:
            escritas = diario.observar([_descreve(None, 50)], 1000.0)  # type: ignore[arg-type]
        assert escritas == 0 and registros == []

    def test_sem_nenhuma_regua_nao_afirma_nada(self, tmp_path: Path) -> None:
        """Nó ausente e handle mudo: não há o que dizer, e não se inventa 0%."""
        diario = self._diario(tmp_path)
        with structlog.testing.capture_logs() as registros:
            escritas = diario.observar([_descreve(_uniq_realista(), None)], 1000.0)
        assert escritas == 0 and registros == []

    def test_sem_no_do_kernel_a_regua_e_o_handle(self, tmp_path: Path) -> None:
        diario = self._diario(tmp_path)
        with structlog.testing.capture_logs() as registros:
            diario.observar([_descreve(_uniq_realista(), 42)], 1000.0)
        assert registros[0]["fonte"] == "handle"
        assert registros[0]["pct_kernel"] is None
        assert registros[0]["pct_handle"] == 42


# --------------------------------------------------------------------------
# 4. A queda
# --------------------------------------------------------------------------


class TestQueda:
    """Mordida: tire a chamada de ``registrar_queda`` da borda de desconexão
    (``daemon/connection.py``) e ``test_borda_de_desconexao_registra_a_carga``
    reprova — a queda volta a ser um carimbo de hora sem carga ao lado."""

    def test_ultima_carga_conhecida_com_a_idade(self, tmp_path: Path) -> None:
        uniq = _uniq_realista()
        no = _no_do_kernel(tmp_path, uniq, "5", "Discharging")
        diario = DiarioDaBateria(raiz=tmp_path)
        diario.observar([_descreve(uniq, 5)], 1000.0)
        # O nó do kernel some junto com o controle — sobra o cache.
        (no / "capacity").unlink()
        (no / "status").unlink()
        no.rmdir()
        with structlog.testing.capture_logs() as registros:
            escritas = diario.registrar_queda("probe_offline", 1042.0)
        assert escritas == 1
        assert registros[0]["event"] == "bateria_na_queda"
        assert registros[0]["pct_kernel"] == 5
        assert registros[0]["status"] == "Discharging"
        assert registros[0]["idade_s"] == 42.0
        assert registros[0]["motivo"] == "probe_offline"

    def test_no_vivo_na_queda_vale_mais_que_o_cache(self, tmp_path: Path) -> None:
        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "15", "Discharging")
        diario = DiarioDaBateria(raiz=tmp_path)
        diario.observar([_descreve(uniq, 15)], 1000.0)
        _no_do_kernel(tmp_path, uniq, "5", "Discharging")
        with structlog.testing.capture_logs() as registros:
            diario.registrar_queda("probe_offline", 1029.0)
        assert registros[0]["pct_kernel"] == 5, "leitura fresca ignorada"
        assert registros[0]["idade_s"] == 0.0

    def test_queda_sem_leitura_nenhuma_nao_fica_calada(self, tmp_path: Path) -> None:
        diario = DiarioDaBateria(raiz=tmp_path)
        with structlog.testing.capture_logs() as registros:
            escritas = diario.registrar_queda("probe_offline", 1000.0)
        assert escritas == 1
        assert registros[0]["event"] == "bateria_na_queda"
        assert registros[0]["pct_kernel"] is None
        assert registros[0]["controle"] == SEM_ENDERECO

    def test_a_queda_dupla_nao_desmente_a_primeira_linha(
        self, tmp_path: Path
    ) -> None:
        """Um controle que some de vez passa pelas DUAS bordas: primeiro o
        ``poll_read_failed``, segundos depois o ``probe_offline``. A segunda já
        não tem cache — e sem a dedup escreveria "ninguém tinha medido" logo
        abaixo da linha que acabou de dizer 5%.

        Mordida: apague o gate de :data:`JANELA_DEDUP_QUEDA_S` e o teste acusa
        a segunda linha.
        """
        uniq = _uniq_realista()
        no = _no_do_kernel(tmp_path, uniq, "5", "Discharging")
        diario = DiarioDaBateria(raiz=tmp_path)
        diario.observar([_descreve(uniq, 5)], 1000.0)
        (no / "capacity").unlink()
        (no / "status").unlink()
        no.rmdir()
        with structlog.testing.capture_logs() as registros:
            diario.registrar_queda("poll_read_failed", 1010.0)
            diario.registrar_queda("probe_offline", 1012.0)
        quedas = [r for r in registros if r["event"] == "bateria_na_queda"]
        assert len(quedas) == 1, "a segunda borda escreveu uma linha vazia"
        assert quedas[0]["pct_kernel"] == 5
        # Passada a janela, uma queda nova volta a falar mesmo sem leitura.
        with structlog.testing.capture_logs() as registros:
            diario.registrar_queda("probe_offline", 1010.0 + JANELA_DEDUP_QUEDA_S + 1)
        assert len(registros) == 1
        assert registros[0]["pct_kernel"] is None

    def test_controle_que_some_com_outro_de_pe_deixa_rastro(
        self, tmp_path: Path
    ) -> None:
        """O ``probe_offline`` nasce de um ``any()`` — só o ÚLTIMO a cair o
        dispara. É por isso que "18 quedas" é PISO, não total; aqui a queda de
        um controle no meio de três deixa linha."""
        um = _uniq_realista()
        outro = "".join(_OUIS_REAIS_OCTETOS[1]) + "b21e04"
        _no_do_kernel(tmp_path, um, "35", "Discharging")
        _no_do_kernel(tmp_path, outro, "85", "Discharging")
        diario = DiarioDaBateria(raiz=tmp_path)
        diario.observar([_descreve(um, 35), _descreve(outro, 85)], 1000.0)
        with structlog.testing.capture_logs() as registros:
            diario.observar([_descreve(outro, 85)], 1000.0 + INTERVALO_SONDA_S)
        quedas = [r for r in registros if r["event"] == "bateria_na_queda"]
        assert len(quedas) == 1
        assert quedas[0]["motivo"] == "sumiu_do_backend"
        assert quedas[0]["controle"] == mascarar_endereco(um)

    def test_contadores_do_store(self, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.daemon.state_store import StateStore

        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "5", "Discharging")
        store = StateStore()
        diario = DiarioDaBateria(raiz=tmp_path, store=store)
        diario.observar([_descreve(uniq, 5)], 1000.0)
        diario.registrar_queda("probe_offline", 1000.0)
        contadores = store.snapshot().counters
        assert contadores.get("battery.journal.sample") == 1
        assert contadores.get("battery.journal.drop") == 1


# --------------------------------------------------------------------------
# 5. O endereço NUNCA sai cru — a mordida do MAC
# --------------------------------------------------------------------------


class TestEnderecoNaoVaza:
    """Mordida MEDIDA em 07/08/2026: troquei ``mascarar_endereco(uniq)`` por
    ``uniq`` nas duas linhas do ``battery_journal`` e os dois testes desta
    classe reprovaram, apontando o endereço inteiro; devolvi a máscara e
    passaram.

    O portão usado aqui é o MESMO do repositório
    (``tests/unit/test_docs_mac_anonimato.MAC_COMPLETO_RE``): se a convenção da
    casa mudar, muda nos dois lugares de uma vez.

    A fixture tem OUI REAL desta bancada, montado em tempo de execução — sem
    isso o portão não reconheceria o endereço e o teste passaria vazio.
    """

    def test_amostra_nao_leva_o_endereco_cru(self, tmp_path: Path) -> None:
        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "5", "Discharging")
        diario = DiarioDaBateria(raiz=tmp_path)
        with structlog.testing.capture_logs() as registros:
            diario.observar([_descreve(uniq, 5)], 1000.0)
        texto = _texto_de_registros(registros)
        assert _macs_sem_mascara(texto) == [], f"endereço cru no journal: {texto}"
        assert mascarar_endereco(uniq) in texto
        # E o sufixo real não aparece em lugar nenhum da linha.
        assert _SUFIXO_DE_FIXTURE[:4] not in texto

    def test_queda_nao_leva_o_endereco_cru(self, tmp_path: Path) -> None:
        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "5", "Discharging")
        diario = DiarioDaBateria(raiz=tmp_path)
        diario.observar([_descreve(uniq, 5)], 1000.0)
        with structlog.testing.capture_logs() as registros:
            diario.registrar_queda("probe_offline", 1030.0)
        texto = _texto_de_registros(registros)
        assert _macs_sem_mascara(texto) == [], f"endereço cru no journal: {texto}"
        assert mascarar_endereco(uniq) in texto


# --------------------------------------------------------------------------
# 6. A fiação — sem ela o módulo é um enfeite
# --------------------------------------------------------------------------


class TestFiacao:
    """Mordida: apague a chamada de ``_amostrar_bateria`` no poll loop (ou a de
    ``registrar_queda_da_bateria`` em ``connection.py``) e os dois testes desta
    classe reprovam."""

    def test_o_daemon_sonda_a_bateria(self, tmp_path: Path) -> None:
        from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
        from hefesto_dualsense4unix.testing.fake_controller import FakeController

        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "5", "Discharging")
        fc = FakeController()
        fc.describe_controllers = lambda: [_descreve(uniq, 5)]  # type: ignore[method-assign]
        daemon = Daemon(controller=fc, config=DaemonConfig())
        daemon._diario_bateria = DiarioDaBateria(raiz=tmp_path, store=daemon.store)
        with structlog.testing.capture_logs() as registros:
            daemon._amostrar_bateria(1000.0)
        amostras = [r for r in registros if r["event"] == "bateria_amostra"]
        assert len(amostras) == 1
        assert amostras[0]["pct_kernel"] == 5

    @pytest.mark.asyncio
    async def test_o_poll_loop_chama_a_sonda(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem esta chamada o módulo inteiro é enfeite: ninguém sonda nada."""
        from hefesto_dualsense4unix.core.controller import ControllerState
        from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
        from hefesto_dualsense4unix.testing.fake_controller import FakeController

        chamadas: list[float] = []
        monkeypatch.setattr(
            Daemon,
            "_amostrar_bateria",
            lambda self, agora: chamadas.append(agora),
            raising=True,
        )
        estados = [
            ControllerState(
                battery_pct=80, l2_raw=0, r2_raw=0, connected=True, transport="bt"
            )
            for _ in range(200)
        ]
        daemon = Daemon(
            controller=FakeController(transport="bt", states=estados),
            config=DaemonConfig(
                poll_hz=200,
                auto_reconnect=False,
                ipc_enabled=False,
                udp_enabled=False,
                autoswitch_enabled=False,
                mouse_emulation_enabled=False,
                keyboard_emulation_enabled=False,
            ),
        )
        run_task = asyncio.create_task(daemon.run())
        await asyncio.sleep(0.15)
        daemon.stop()
        await run_task
        assert chamadas, "o poll loop não sondou a bateria nenhuma vez"

    @pytest.mark.asyncio
    async def test_erro_de_leitura_tambem_registra_a_carga(
        self, tmp_path: Path
    ) -> None:
        """O irmão do ``probe_offline``: o poll loop perdendo a leitura.

        São dois caminhos para a MESMA borda (``CONTROLLER_DISCONNECTED``), e
        quem cair pelo segundo tem de deixar a carga registrada igual — senão
        metade das quedas continua sem resposta.
        """
        from hefesto_dualsense4unix.core.controller import ControllerState
        from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
        from hefesto_dualsense4unix.testing.fake_controller import FakeController

        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "5", "Discharging")

        class _LeituraQueMorre(FakeController):
            def __init__(self) -> None:
                super().__init__(
                    transport="bt",
                    states=[
                        ControllerState(
                            battery_pct=5,
                            l2_raw=0,
                            r2_raw=0,
                            connected=True,
                            transport="bt",
                        )
                    ],
                )
                self.leituras = 0

            def read_state(self) -> ControllerState:
                self.leituras += 1
                if self.leituras > 2:
                    raise OSError("[Errno 19] No such device")
                return super().read_state()

        daemon = Daemon(
            controller=_LeituraQueMorre(),
            config=DaemonConfig(
                poll_hz=200,
                auto_reconnect=False,
                ipc_enabled=False,
                udp_enabled=False,
                autoswitch_enabled=False,
                mouse_emulation_enabled=False,
                keyboard_emulation_enabled=False,
            ),
        )
        daemon._diario_bateria = DiarioDaBateria(raiz=tmp_path, store=daemon.store)
        daemon._diario_bateria.observar([_descreve(uniq, 5)], 0.0)

        with structlog.testing.capture_logs() as registros:
            run_task = asyncio.create_task(daemon.run())
            await asyncio.sleep(0.15)
            daemon.stop()
            await run_task
        quedas = [r for r in registros if r["event"] == "bateria_na_queda"]
        assert quedas, "erro de leitura não deixou linha de bateria"
        assert quedas[0]["motivo"] == "poll_read_failed"
        assert quedas[0]["pct_kernel"] == 5

    def test_backend_sem_describe_nao_derruba_o_poll_loop(
        self, tmp_path: Path
    ) -> None:
        from hefesto_dualsense4unix.daemon.lifecycle import Daemon

        daemon = Daemon(controller=SimpleNamespace())  # type: ignore[arg-type]
        daemon._amostrar_bateria(1000.0)  # não levanta

    def test_borda_de_desconexao_registra_a_carga(self, tmp_path: Path) -> None:
        """A borda ``probe_offline`` do ``reconnect_loop`` deixa a última carga.

        Monta o daemon como o ``test_hidraw_broker_hooks`` faz: um
        ``SimpleNamespace`` com o mínimo que o loop toca, e um ``is_connected``
        que devolve True no baseline e False na primeira iteração — que é a
        borda online→offline.
        """
        from hefesto_dualsense4unix.daemon import connection

        uniq = _uniq_realista()
        _no_do_kernel(tmp_path, uniq, "5", "Discharging")
        diario = DiarioDaBateria(raiz=tmp_path)
        diario.observar([_descreve(uniq, 5)], 1000.0)

        conexoes = iter([True, False, False, False])
        parada = iter([False, True, True, True])
        stop_event = asyncio.Event()
        stop_event.set()  # os waits voltam na hora; _is_stopping governa o fim
        publicados: list[tuple[str, Any]] = []

        daemon = SimpleNamespace(
            controller=SimpleNamespace(
                connect=lambda: None,
                is_connected=lambda: next(conexoes),
                get_transport=lambda: "bt",
            ),
            bus=SimpleNamespace(
                publish=lambda topico, carga: publicados.append((topico, carga))
            ),
            config=None,
            store=None,
            _stop_event=stop_event,
            _is_stopping=lambda: next(parada),
            _arm_input_grace=lambda: None,
            _diario_bateria=diario,
        )

        async def _run_blocking(fn: Any, *args: Any) -> Any:
            return fn(*args)

        daemon._run_blocking = _run_blocking
        watch = SimpleNamespace(poll=lambda: False)

        with structlog.testing.capture_logs() as registros:
            asyncio.run(connection.reconnect_loop(daemon, input_watch=watch))

        quedas = [r for r in registros if r["event"] == "bateria_na_queda"]
        assert quedas, "a desconexão não deixou linha de bateria no journal"
        assert quedas[0]["pct_kernel"] == 5
        assert quedas[0]["motivo"] == "probe_offline"
        assert _macs_sem_mascara(_texto_de_registros(registros)) == []
        assert any(t == "controller.disconnected" for t, _ in publicados)


def test_faixas_estao_ordenadas_e_cobrem_a_escala() -> None:
    assert list(FAIXAS) == sorted(set(FAIXAS))
    assert FAIXAS[0] == 0 and FAIXAS[-1] == 100
