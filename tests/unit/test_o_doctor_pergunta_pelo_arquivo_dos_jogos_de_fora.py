"""O doctor pergunta pelo arquivo dos jogos de fora da Steam.

Sprint O-DOCTOR-PERGUNTA-PELO-ARQUIVO-DOS-JOGOS-DE-FORA-DA-STEAM-01, decisão
D-2211-O-DOCTOR-PERGUNTA-PELO-ARQUIVO-DOS-JOGOS-DE-FORA-DA-STEAM.

Medido em 22/11/2026: o portão `contratos-de-fora` reprovava porque a linha do censo do
`shortcuts.vdf` apontava o contrato `steam-localconfig`, cuja sonda não abria o arquivo: o doctor
daria «OK» com o arquivo dos jogos de fora ilegível. O 68641ca95 pôs a pergunta na sonda; esta
régua prova o que a sprint pede, com a Steam de mentira em pasta temporária, o arquivo montado
byte a byte, appid da faixa fictícia (9900000 em diante) e título inventado:

1. sem `shortcuts.vdf` a sonda responde como antes;
2. com o arquivo válido (um jogo de fora do Windows e um nativo) a sonda diz `OK`;
3. com o arquivo cortado no meio de uma entrada, com bytes que não são VDF binário e com uma entrada
   sem nome ou sem executável, a sonda diz que quebrou, com o nome do arquivo e sem o caminho da
   conta;
4. com duas contas, uma boa e uma quebrada, a sonda quebra pela quebrada;
5. o contrato cobre o arquivo, a promessa e o `conferir` o dizem, e o portão
   `scripts/check_os_contratos_de_fora.py` fica verde.

MORDIDAS (25/11/2026): a sonda sem a pergunta do `shortcuts.vdf` reprova os casos do arquivo
quebrado; o `cobre` sem o alvo reprova o portão; o `os_que_nao_abrem` sem a conta das entradas sem
campos reprova o caso da entrada vazia.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import contratos_de_fora as cf
from tests.unit.test_o_doctor_nomeia_o_contrato import _amb
from tests.unit.test_o_jogo_de_fora_da_steam_recebe_o_atalho import _arquivo, _entrada

RAIZ = Path(__file__).resolve().parents[2]
ALVO = "cfg:shortcuts.vdf"
LOCALCONFIG = '"UserLocalConfigStore"\n{\n}\n'
WINDOWS = 9900001
NATIVO = 9900002


def _steam(tmp_path: Path) -> Path:
    return tmp_path / "home/.steam/steam/userdata"


def _conta(tmp_path: Path, conta: str, jogos: bytes | None) -> Path:
    pasta = _steam(tmp_path) / conta / "config"
    pasta.mkdir(parents=True)
    (pasta / "localconfig.vdf").write_text(LOCALCONFIG, encoding="utf-8")
    if jogos is not None:
        (pasta / "shortcuts.vdf").write_bytes(jogos)
    return pasta


def _validos() -> bytes:
    return _arquivo(
        _entrada(0, appid=WINDOWS, nome="Jogo Inventado do Windows", exe='"/jogos/x/inventado.exe"',
                 opcoes=""),
        _entrada(1, appid=NATIVO, nome="Jogo Inventado Nativo", exe='"/usr/bin/inventado"',
                 opcoes="%command%"),
    )


def _contrato() -> cf.Contrato:
    (contrato,) = [c for c in cf.CONTRATOS if c.id == "steam-localconfig"]
    return contrato


def _linha(tmp_path: Path) -> tuple[str, str]:
    ((tag, msg),) = cf.linhas_do_doctor(_amb(tmp_path, {}), [_contrato()])
    return tag, msg


def test_sem_o_arquivo_dos_jogos_de_fora_a_sonda_responde_como_antes(tmp_path: Path) -> None:
    _conta(tmp_path, "1000", None)
    assert _linha(tmp_path)[0] == "[ OK ]"


def test_o_arquivo_valido_com_um_jogo_do_windows_e_um_nativo_e_ok(tmp_path: Path) -> None:
    _conta(tmp_path, "1000", _validos())
    assert _linha(tmp_path)[0] == "[ OK ]"


def test_o_arquivo_cortado_no_meio_de_uma_entrada_quebra_com_o_nome_do_arquivo(
    tmp_path: Path,
) -> None:
    """D-2211-O-DOCTOR-PERGUNTA-PELO-ARQUIVO-DOS-JOGOS-DE-FORA-DA-STEAM."""
    bruto = _validos()
    _conta(tmp_path, "7261234", bruto[: len(bruto) * 6 // 10])
    tag, msg = _linha(tmp_path)
    assert tag == "[WARN]"
    assert "shortcuts.vdf" in msg and "steam-localconfig" in msg
    assert "7261234" not in msg and str(tmp_path) not in msg, "a frase traz o caminho da conta"


def test_os_bytes_que_nao_sao_vdf_quebram(tmp_path: Path) -> None:
    _conta(tmp_path, "1000", b"texto que a Steam nunca escreveria")
    tag, msg = _linha(tmp_path)
    assert tag == "[WARN]" and "shortcuts.vdf" in msg


def test_a_entrada_sem_nome_e_sem_executavel_quebra(tmp_path: Path) -> None:
    vazia = _arquivo(_entrada(0, appid=WINDOWS, nome="", exe="", opcoes=""))
    _conta(tmp_path, "1000", vazia)
    tag, msg = _linha(tmp_path)
    assert tag == "[WARN]"
    assert "shortcuts.vdf" in msg and "sem nome ou sem executável" in msg


def test_com_duas_contas_a_quebrada_derruba_a_linha(tmp_path: Path) -> None:
    _conta(tmp_path, "1000", _validos())
    _conta(tmp_path, "2000", b"\x00shortcuts\x00\x00")
    tag, msg = _linha(tmp_path)
    assert tag == "[WARN]" and "1 shortcuts.vdf" in msg


def test_o_contrato_cobre_o_arquivo_e_o_diz_na_promessa_e_no_conferir() -> None:
    contrato = _contrato()
    assert ALVO in contrato.cobre
    assert "shortcuts.vdf" in contrato.promessa
    assert "shortcuts.vdf" in contrato.conferir


def test_o_portao_dos_contratos_de_fora_fica_verde() -> None:
    ambiente = {**os.environ, "PYTHONPATH": str(RAIZ / "src")}
    saida = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "check_os_contratos_de_fora.py")],
        cwd=RAIZ, env=ambiente, capture_output=True, text=True, timeout=180, check=False,
    )
    assert saida.returncode == 0, saida.stdout[-1500:] + saida.stderr[-500:]


@pytest.mark.parametrize("conta", ["1000", "7261234"])
def test_a_frase_nunca_traz_o_caminho_da_conta(tmp_path: Path, conta: str) -> None:
    _conta(tmp_path, conta, b"\x00shortcuts\x00\x00")
    _tag, msg = _linha(tmp_path)
    assert conta not in msg and str(tmp_path) not in msg
