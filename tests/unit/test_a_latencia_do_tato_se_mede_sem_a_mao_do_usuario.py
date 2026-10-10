"""A latência do tato se mede sem a mão do usuário (08/10/2026).

O ensaio ``scripts/ensaios/latencia_do_tato.py`` lê o giro do controle pousado e mede o
intervalo entre a escrita do relatório e o primeiro desvio acima do ruído. Aqui o giro é
sintético: ruído gaussiano e, em cima dele, um degrau de vibração num instante conhecido.
Cada régua tem a sua mordida: a que mede do relatório errado, a que aceita o ruído como
toque, a que aceita o giro em movimento, a que devolve zero no lugar de «nenhum toque lido»
e a que deixa o desvio de um toque valer para o anterior.

Nada aqui toca o aparelho, o daemon do usuário ou o ``~/.config``: o ``rodar_no_aparelho`` é da
bancada, e o ``ha_daemon`` real é trocado por um dublê nos testes da linha de comando.
"""

from __future__ import annotations

import importlib.util
import random
import socket
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
INSTRUMENTO = RAIZ / "scripts" / "ensaios" / "latencia_do_tato.py"
PROTOCOLO = RAIZ / "docs" / "protocol" / "latencia-do-tato.md"

PASSO_S = 0.002
T0 = 1000.0


def _carregar() -> ModuleType:
    spec = importlib.util.spec_from_file_location("latencia_do_tato", INSTRUMENTO)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


ens = _carregar()


def _t(i: int) -> float:
    return T0 + i * PASSO_S


def giro(n: int, degraus: list[tuple[int, int]] | None = None, *, sigma: float = 0.1,
         amplitude: float = 30.0, seed: int = 7, balanco: float = 0.0) -> list[Any]:
    """``n`` quadros a cada 2 ms; ruído de ``sigma`` °/s; vibração nos intervalos ``degraus``."""
    sorteio = random.Random(seed)
    quadros = []
    for i in range(n):
        x = sorteio.gauss(0.0, sigma)
        y = sorteio.gauss(0.0, sigma)
        z = sorteio.gauss(0.0, sigma)
        for ini, fim in degraus or []:
            if ini <= i < fim:
                x += amplitude if (i - ini) % 2 == 0 else -amplitude
        if balanco:
            x += balanco * (1 if (i // 10) % 2 == 0 else -1)
        quadros.append(ens.Quadro(_t(i), x, y, z))
    return quadros


ESCRITA = _t(100)


# --- a medida --------------------------------------------------------------------------------


def test_o_degrau_a_14_ms_da_escrita_devolve_14_ms() -> None:
    quadros = giro(200, [(107, 140)])
    assert ens.latencia_de_um_toque(quadros, ESCRITA) == pytest.approx(14.0, abs=0.01)


def test_sem_degrau_devolve_nenhum_toque_lido_e_nunca_zero() -> None:
    quadros = giro(200)
    resultado = ens.latencia_de_um_toque(quadros, ESCRITA)
    assert resultado is None, "ruído sozinho não é toque: o resultado é «nenhum toque lido»"
    assert ens.medir_toques(quadros, [ESCRITA]) == [None]
    assert ens.linha_da_tabela("cabo", "P1", ens.resumir([None, None])).count(
        "nenhum toque lido") == 3


def test_um_quadro_isolado_acima_do_limiar_nao_e_toque() -> None:
    quadros = giro(200, [(107, 108)])
    assert ens.latencia_de_um_toque(quadros, ESCRITA) is None


def test_cada_toque_e_medido_da_sua_escrita_e_nao_da_anterior() -> None:
    """Duas escritas a 300 ms (o motor já parou); o degrau de cada uma a 14 ms dela."""
    quadros = giro(500, [(107, 130), (257, 280)])
    segunda = _t(250)
    medidas = ens.medir_toques(quadros, [ESCRITA, segunda])
    assert medidas == [pytest.approx(14.0, abs=0.01), pytest.approx(14.0, abs=0.01)]


def test_o_desvio_de_um_toque_nao_vale_para_o_toque_anterior() -> None:
    """A segunda escrita vem 100 ms depois; o degrau é DO USUÁRIO, e a primeira não leu nada."""
    quadros = giro(400, [(157, 180)])
    segunda = _t(150)
    medidas = ens.medir_toques(quadros, [ESCRITA, segunda])
    assert medidas[0] is None, "o degrau é depois da segunda escrita: não é do primeiro toque"
    assert medidas[1] == pytest.approx(14.0, abs=0.01)


def test_a_ordem_das_escritas_nao_muda_a_medida() -> None:
    quadros = giro(500, [(107, 130), (257, 280)])
    assert ens.medir_toques(quadros, [_t(250), ESCRITA]) == ens.medir_toques(
        quadros, [ESCRITA, _t(250)])


def test_o_motor_ainda_vibrando_na_linha_de_base_nao_e_giro_parado() -> None:
    """Duas escritas a 100 ms: a cauda da primeira suja a base da segunda, e ele recusa."""
    quadros = giro(400, [(107, 160), (157, 180)])
    with pytest.raises(ens.GiroEmMovimento):
        ens.medir_toques(quadros, [ESCRITA, _t(150)])


def test_o_ruido_forte_mas_parado_nao_vira_toque() -> None:
    """Ruído de 1 °/s (dez vezes o normal) sem vibração: o limiar sobe com ele."""
    quadros = giro(200, sigma=1.0, seed=3)
    assert ens.latencia_de_um_toque(quadros, ESCRITA) is None


def test_o_limiar_nunca_e_zero() -> None:
    parado = [ens.Quadro(_t(i), 0.0, 0.0, 0.0) for i in range(100)]
    base = ens.linha_de_base(parado)
    assert base.limiar == ens.PISO_DO_LIMIAR_GRAUS_S > 0


# --- o giro que não está parado, e o que não há ----------------------------------------------


def test_o_giro_em_movimento_na_linha_de_base_e_recusado() -> None:
    quadros = giro(200, [(107, 140)], balanco=20.0)
    with pytest.raises(ens.GiroEmMovimento):
        ens.latencia_de_um_toque(quadros, ESCRITA)


def test_poucos_quadros_antes_da_escrita_nao_dao_medida() -> None:
    quadros = giro(200)
    with pytest.raises(ens.SemMedicao):
        ens.latencia_de_um_toque(quadros, _t(3))
    with pytest.raises(ens.SemMedicao):
        ens.latencia_de_um_toque([], ESCRITA)


def test_o_resumo_tem_mediana_p95_e_maximo_dos_toques_lidos() -> None:
    resumo = ens.resumir([10.0, 12.0, 14.0, None, 100.0])
    assert (resumo.toques, resumo.lidos) == (5, 4)
    assert resumo.mediana_ms == pytest.approx(13.0)
    assert resumo.maximo_ms == 100.0
    assert resumo.p95_ms == 100.0
    vazio = ens.resumir([None])
    assert (vazio.lidos, vazio.mediana_ms, vazio.p95_ms, vazio.maximo_ms) == (0, None, None, None)


# --- as recusas ------------------------------------------------------------------------------


def test_o_lar_real_nao_e_lar_de_mentira(tmp_path: Path) -> None:
    real = tmp_path / "casa"
    real.mkdir()
    falso = tmp_path / "lar-de-mentira"
    falso.mkdir()
    assert not ens.lar_e_de_mentira(str(real), str(real))
    assert not ens.lar_e_de_mentira(None, str(real))
    assert not ens.lar_e_de_mentira(str(falso), None)
    assert ens.lar_e_de_mentira(str(falso), str(real))


def test_os_sockets_do_daemon_incluem_o_do_run_user_mesmo_com_o_ambiente_desviado() -> None:
    env = {"XDG_RUNTIME_DIR": "/tmp/falso/run", "HEFESTO_DUALSENSE4UNIX_FAKE": "1"}
    caminhos = [str(c) for c in ens.sockets_do_daemon(env, 4242)]
    assert "/tmp/falso/run/hefesto-dualsense4unix/hefesto-dualsense4unix-fake.sock" in caminhos
    assert "/run/user/4242/hefesto-dualsense4unix/hefesto-dualsense4unix-fake.sock" in caminhos
    sem_fake = [str(c) for c in ens.sockets_do_daemon({}, 4242)]
    assert sem_fake == ["/run/user/4242/hefesto-dualsense4unix/hefesto-dualsense4unix.sock"]


def test_ha_daemon_distingue_socket_vivo_socket_morto_e_ausente(tmp_path: Path) -> None:
    ausente = tmp_path / "nao-existe.sock"
    assert ens.ha_daemon([ausente]) is False

    vivo = tmp_path / "vivo.sock"
    servidor = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    servidor.bind(str(vivo))
    servidor.listen(1)
    try:
        assert ens.ha_daemon([ausente, vivo]) is True
    finally:
        servidor.close()
    # o arquivo ficou, mas ninguém ouve mais: daemon morto, não vivo
    assert vivo.exists()
    assert ens.ha_daemon([vivo]) is False


def test_recusas_dizem_o_lar_real_e_o_daemon(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = tmp_path / "casa"
    real.mkdir()
    monkeypatch.setattr(ens, "ha_daemon", lambda *_a, **_k: True)
    motivos = ens.recusas({"HOME": str(real)}, 1000, str(real))
    assert len(motivos) == 2
    assert "lar real" in motivos[0] and "daemon" in motivos[1]
    monkeypatch.setattr(ens, "ha_daemon", lambda *_a, **_k: False)
    falso = tmp_path / "lar-de-mentira"
    falso.mkdir()
    assert ens.recusas({"HOME": str(falso)}, 1000, str(real)) == []


def test_sem_medir_nao_toca_em_nada_e_diz_o_que_recusaria(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ens, "ha_daemon", lambda *_a, **_k: True)

    def nao_pode(*_a: object, **_k: object) -> None:
        raise AssertionError("sem --medir o aparelho não é tocado")

    monkeypatch.setattr(ens, "rodar_no_aparelho", nao_pode)
    assert ens.main([]) == 0
    saida = capsys.readouterr().out
    assert "SEM --medir" in saida and "recusaria agora" in saida


def test_com_medir_e_recusa_o_aparelho_nao_e_tocado(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ens, "ha_daemon", lambda *_a, **_k: True)

    def nao_pode(*_a: object, **_k: object) -> None:
        raise AssertionError("recusado: o aparelho não pode ser aberto")

    monkeypatch.setattr(ens, "rodar_no_aparelho", nao_pode)
    rc = ens.main(["--medir", "--hidraw", "/dev/hidraw0", "--movimento", "/dev/input/event0"])
    assert rc == ens.RC_RECUSADO
    assert "RECUSADO" in capsys.readouterr().out


def test_giro_em_movimento_vira_rc_3_e_nao_tabela(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ens, "ha_daemon", lambda *_a, **_k: False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(ens, "recusas", lambda *_a, **_k: [])
    movimento = giro(200, [(107, 140)], balanco=20.0)

    monkeypatch.setattr(
        ens, "rodar_no_aparelho", lambda *_a, **_k: (movimento, [ESCRITA]))
    rc = ens.main(["--medir", "--hidraw", "/dev/hidraw0", "--movimento", "/dev/input/event0"])
    assert rc == ens.RC_GIRO_EM_MOVIMENTO
    assert "| transporte |" not in capsys.readouterr().out


def test_com_giro_parado_a_linha_de_comando_imprime_a_tabela(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(ens, "recusas", lambda *_a, **_k: [])
    monkeypatch.setattr(
        ens, "rodar_no_aparelho",
        lambda *_a, **_k: (giro(200, [(107, 140)]), [ESCRITA]))
    rc = ens.main(["--medir", "--transporte", "radio", "--controle", "P2",
                   "--hidraw", "/dev/hidraw0", "--movimento", "/dev/input/event0"])
    assert rc == 0
    saida = capsys.readouterr().out
    assert ens.CABECALHO_DA_TABELA in saida
    assert "| radio | P2 | 1 de 1 | 14.0 ms |" in saida


# --- o relatório que o ensaio escreve --------------------------------------------------------


def test_o_relatorio_de_vibracao_liga_e_desliga_os_dois_motores_nos_dois_transportes() -> None:
    from hefesto_dualsense4unix.core import ds_output_report as rep

    cabo = ens.relatorio_de_vibracao("cabo", 0xFF, 0)
    assert cabo[0] == rep.USB_REPORT_ID
    assert cabo[1] & rep.VALID_FLAG0_COMPATIBLE_VIBRATION
    assert (cabo[3], cabo[4]) == (0xFF, 0xFF)
    parado = ens.relatorio_de_vibracao("cabo", 0, 1)
    assert (parado[3], parado[4]) == (0, 0)

    radio = ens.relatorio_de_vibracao("radio", 0xFF, 3)
    assert radio[0] == rep.BT_REPORT_ID and radio[1] >> 4 == 3 and radio[2] == rep.BT_TAG
    assert (radio[5], radio[6]) == (0xFF, 0xFF)
    assert int.from_bytes(radio[-4:], "little") == rep.bt_crc32(radio[:-4])


def test_o_toque_de_teste_leva_as_flags_do_rumble_que_o_produto_escreve() -> None:
    """O relatório medido é o do produto: ``COMPATIBLE_VIBRATION`` + ``HAPTICS_SELECT``.

    Sem o ``HAPTICS_SELECT`` o firmware não troca para a vibração emulada; o produto
    (sem háptica por áudio tocando) e o ``hid_playstation`` mandam os dois bits, e o
    ``flag2`` leva a vibração v2. A régua lê o bloco comum dos dois transportes.
    """
    from hefesto_dualsense4unix.core import ds_output_report as rep

    rumble = rep.VALID_FLAG0_COMPATIBLE_VIBRATION | rep.VALID_FLAG0_HAPTICS_SELECT
    for transporte, inicio in (("cabo", 1), ("radio", 3)):
        common = ens.relatorio_de_vibracao(transporte, 0xFF, 0)[inicio:]
        assert common[0] & rumble == rumble, f"{transporte}: o flag0 do rumble do produto"
        assert common[rep.COMMON_VALID_FLAG2] & rep.VALID_FLAG2_COMPATIBLE_VIBRATION2


# --- o protocolo e a tabela ------------------------------------------------------------------


def test_o_protocolo_existe_e_traz_o_cabecalho_da_tabela_do_ensaio() -> None:
    texto = PROTOCOLO.read_text(encoding="utf-8")
    assert ens.CABECALHO_DA_TABELA in texto, (
        "a tabela do protocolo é a que o ensaio imprime: o cabeçalho é o mesmo")
    assert "nenhum toque lido" in texto
    assert "scripts/ensaios/latencia_do_tato.py" in texto
    janela = f"{ens.JANELA_DO_RUIDO_S:g}".replace(".", ",")
    assert f"{janela} s ANTES da escrita" in texto
    assert f"acima de {ens.LIMITE_DE_GIRO_PARADO_GRAUS_S:g} °/s" in texto
    assert f"{ens.MINIMO_DE_QUADROS_NA_BASE} quadros de giro" in texto
