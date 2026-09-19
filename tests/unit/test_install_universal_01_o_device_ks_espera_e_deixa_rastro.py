"""INSTALL-UNIVERSAL (18/09/2026) — o device KS espera o prefixo e deixa rastro.

Ordem dela: *"ele precisa funcionar como produto"* — a vibração que chega aos
jogos da Sony na máquina dela tem de chegar na de qualquer pessoa, e quando
não chegar, tem de DIZER.

O curador do device KS (`hefesto-audio-ks`) roda dentro do lançamento, antes do
`exec`, com a saída em /dev/null. Três buracos, medidos pelo auditor e pelo
cético do INSTALL-UNIVERSAL:

1. **`ocupado`** — o wineserver do prefixo ainda vivo (o do install script da
   Steam, ou o da sessão que acabou de fechar). O curador recusava e o jogo
   abria sem vibração. Agora o wrapper espera, até cinco tentativas a mais.
2. **a falha era calada** — nem o doctor nem o daemon olhavam o curador. O
   wrapper deixa `launch_env/audio_ks_ultimo`, e o `check_ultimo_device_ks` lê.
   Todo caminho deixa o SEU motivo: o install incompleto (`sem-curador`), a
   máquina sem `python3` (`sem-python`, que antes saía sem rastro ou como
   `desligado`) e o device que SAIU (`removido`, que antes se dizia `ok`).
3. **a cópia em bin/ envelhece** — um `git pull` sem reinstalar deixa as três
   cópias velhas. O `check_copias_do_wrapper` compara com o checkout.

Tudo com prefixo, sysfs e HOME sintéticos: a suíte nunca lê a Steam dela.
"""

from __future__ import annotations

import fcntl
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks
from tests.unit.test_haptica_nativa_01_o_device_ks_que_o_jogo_procura import (
    _ENV_LIGADO,
    _MODULO,
    _WRAPPER,
    PADRAO,
    _DaemonQueResponde,
    _path_minimo,
    _prefixo,
    _registro,
    _sysfs_com_dualsense,
)

RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
APPID = "3357650"

#: Um curador de mentira que responde `ocupado` (3) nas primeiras N chamadas e
#: depois `feito` (0). Conta as chamadas num arquivo: é a única forma de medir
#: QUANTAS vezes o wrapper tentou, que é o que a espera promete.
_CURADOR_TEIMOSO = """\
import os
import sys
from pathlib import Path

contador = Path(os.environ["HEFESTO_TESTE_CONTADOR"])
n = int(contador.read_text() or "0") + 1 if contador.exists() else 1
contador.write_text(str(n))
sys.exit(3 if n <= int(os.environ["HEFESTO_TESTE_OCUPADO_ATE"]) else 0)
"""


def _lancar(
    tmp_path: Path,
    *,
    env_do_daemon: str,
    registro: str | None,
    curador: str | None = None,
    extra: dict[str, str] | None = None,
    sem_curador: bool = False,
    sem_python: bool = False,
) -> tuple[subprocess.CompletedProcess[str], Path, Path]:
    """Roda o wrapper DE VERDADE; devolve (o processo, o compatdata, o rastro).

    `registro=None` é o prefixo que ainda não existe: a primeira sessão de todo
    jogo novo, em que o proton cria o `system.reg` DEPOIS do wrapper.
    `sem_curador` é o install incompleto (o `hefesto-audio-ks` não foi
    materializado); `sem_python` é o PATH do lançamento sem `python3`.
    """
    home = tmp_path / "home"
    binario = home / ".local" / "share" / "hefesto-dualsense4unix" / "bin"
    binario.mkdir(parents=True)
    alvo = binario / "hefesto-audio-ks"
    if not sem_curador:
        if curador is None:
            alvo.write_bytes(_MODULO.read_bytes())
        else:
            alvo.write_text(curador, encoding="utf-8")
        alvo.chmod(0o755)
    estado = tmp_path / "estado"
    pasta = estado / "hefesto-dualsense4unix" / "launch_env"
    pasta.mkdir(parents=True)
    (pasta / "default.env").write_text(env_do_daemon, encoding="utf-8")
    if registro is None:
        compat = tmp_path / "compatdata" / APPID
        compat.mkdir(parents=True)
    else:
        compat = _prefixo(tmp_path, registro)
    caminho = Path(_path_minimo(tmp_path / "bin"))
    # A espera precisa do `sleep`; o PATH mínimo do produto não o tem, e sem
    # ele o wrapper desiste na primeira tentativa (o lado seguro de errar).
    sono = shutil.which("sleep")
    assert sono is not None
    (caminho / "sleep").symlink_to(sono)
    if sem_python:
        (caminho / "python3").unlink()
    runtime = Path(tempfile.mkdtemp(prefix="hefks-"))  # AF_UNIX: caminho curto
    (runtime / "hefesto-dualsense4unix").mkdir()
    daemon = _DaemonQueResponde(runtime / "hefesto-dualsense4unix" / "hefesto-dualsense4unix.sock")
    env = {
        "PATH": str(caminho),
        "HOME": str(home),
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_STATE_HOME": str(estado),
        "SteamAppId": APPID,
        "STEAM_COMPAT_DATA_PATH": str(compat),
        "HEFESTO_SYSFS": str(_sysfs_com_dualsense(tmp_path / "sys")),
        "HEFESTO_KS_ESPERA_SECS": "0",
        **(extra or {}),
    }
    try:
        feito = subprocess.run(
            ["sh", str(_WRAPPER), "sh", "-c", 'printf "o jogo abriu\\n"'],
            env=env,
            capture_output=True,
            text=True,
            timeout=60.0,
            check=False,
        )
    finally:
        daemon.parar()
        shutil.rmtree(runtime, ignore_errors=True)
    return feito, compat, pasta / "audio_ks_ultimo"


def _rastro(arquivo: Path) -> dict[str, str]:
    assert arquivo.is_file(), "o wrapper não deixou rastro do curador"
    return dict(
        linha.split("=", 1) for linha in arquivo.read_text(encoding="utf-8").splitlines()
    )


# ---------------------------------------------------------------- o wrapper


def test_o_ocupado_passageiro_e_esperado_e_o_device_sai(tmp_path: Path) -> None:
    """A MORDIDA da espera: tire o laço do `curar_audio_ks` e o rastro diz
    `ocupado` com UMA tentativa, e o jogo abre sem o device.

    O wineserver do install script da Steam fica vivo por um instante; o
    `proton waitforexitandrun` espera por ELE antes de abrir o jogo, então
    esperar aqui custa zero.
    """
    contador = tmp_path / "contador"
    feito, _, arquivo = _lancar(
        tmp_path,
        env_do_daemon=_ENV_LIGADO,
        registro=_registro(),
        curador=_CURADOR_TEIMOSO,
        extra={"HEFESTO_TESTE_CONTADOR": str(contador), "HEFESTO_TESTE_OCUPADO_ATE": "2"},
    )
    assert feito.returncode == 0, feito.stderr
    assert "o jogo abriu" in feito.stdout
    rastro = _rastro(arquivo)
    assert rastro["motivo"] == "ok", rastro
    assert rastro["tentativas"] == "3", rastro
    assert rastro["appid"] == APPID
    assert contador.read_text() == "3"


def test_a_espera_tem_teto_e_o_jogo_abre_mesmo_assim(tmp_path: Path) -> None:
    """Com o prefixo travado o tempo todo: seis tentativas, e o jogo abre.

    O curador DE VERDADE, com a mesma trava que o proton usa (`pfx.lock`)
    segurada por este processo. Sem teto, o lançamento nunca chegaria ao
    `exec` — e o jogo abrir é a promessa que vale acima de todas.
    """
    compat_previsto = tmp_path / "compatdata" / APPID
    (compat_previsto / "pfx").mkdir(parents=True)
    (compat_previsto / "pfx" / "system.reg").write_text(_registro(), encoding="utf-8")
    trava = os.open(compat_previsto / "pfx.lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(trava, fcntl.LOCK_EX)
        home = tmp_path / "home"
        binario = home / ".local" / "share" / "hefesto-dualsense4unix" / "bin"
        binario.mkdir(parents=True)
        (binario / "hefesto-audio-ks").write_bytes(_MODULO.read_bytes())
        (binario / "hefesto-audio-ks").chmod(0o755)
        estado = tmp_path / "estado"
        pasta = estado / "hefesto-dualsense4unix" / "launch_env"
        pasta.mkdir(parents=True)
        (pasta / "default.env").write_text(_ENV_LIGADO, encoding="utf-8")
        caminho = Path(_path_minimo(tmp_path / "bin"))
        (caminho / "sleep").symlink_to(shutil.which("sleep") or "/bin/sleep")
        runtime = Path(tempfile.mkdtemp(prefix="hefks-"))
        (runtime / "hefesto-dualsense4unix").mkdir()
        daemon = _DaemonQueResponde(
            runtime / "hefesto-dualsense4unix" / "hefesto-dualsense4unix.sock"
        )
        try:
            feito = subprocess.run(
                ["sh", str(_WRAPPER), "sh", "-c", 'printf "o jogo abriu\\n"'],
                env={
                    "PATH": str(caminho),
                    "HOME": str(home),
                    "XDG_RUNTIME_DIR": str(runtime),
                    "XDG_STATE_HOME": str(estado),
                    "SteamAppId": APPID,
                    "STEAM_COMPAT_DATA_PATH": str(compat_previsto),
                    "HEFESTO_SYSFS": str(_sysfs_com_dualsense(tmp_path / "sys")),
                    "HEFESTO_KS_ESPERA_SECS": "0",
                },
                capture_output=True,
                text=True,
                timeout=60.0,
                check=False,
            )
        finally:
            daemon.parar()
            shutil.rmtree(runtime, ignore_errors=True)
    finally:
        os.close(trava)
    assert feito.returncode == 0, feito.stderr
    assert "o jogo abriu" in feito.stdout
    rastro = _rastro(pasta / "audio_ks_ultimo")
    assert rastro["motivo"] == "ocupado", rastro
    assert rastro["rc"] == "3"
    assert rastro["tentativas"] == "6", "até cinco tentativas A MAIS, nem uma além"
    assert "HEFESTOKS" not in (compat_previsto / "pfx" / "system.reg").read_text(encoding="utf-8")


def test_a_primeira_sessao_do_jogo_novo_fica_registrada(tmp_path: Path) -> None:
    """Sem `system.reg` (o prefixo nasce dentro do %command%): rastro, não silêncio."""
    feito, compat, arquivo = _lancar(tmp_path, env_do_daemon=_ENV_LIGADO, registro=None)
    assert feito.returncode == 0, feito.stderr
    assert "o jogo abriu" in feito.stdout
    assert _rastro(arquivo)["motivo"] == "sem-registro"
    assert not (compat / "pfx").exists(), "o wrapper não cria prefixo"


def test_sem_a_opcao_o_rastro_diz_desligado(tmp_path: Path) -> None:
    feito, _, arquivo = _lancar(
        tmp_path, env_do_daemon="PROTON_ENABLE_MHWILDS_USB_AUDIO=0\n", registro=_registro()
    )
    assert feito.returncode == 0, feito.stderr
    assert _rastro(arquivo)["motivo"] == "desligado"


def test_o_curador_de_verdade_grava_e_o_rastro_diz_ok(tmp_path: Path) -> None:
    feito, compat, arquivo = _lancar(tmp_path, env_do_daemon=_ENV_LIGADO, registro=_registro())
    assert feito.returncode == 0, feito.stderr
    rastro = _rastro(arquivo)
    assert (rastro["motivo"], rastro["rc"], rastro["tentativas"]) == ("ok", "0", "1")
    assert "HEFESTOKS" in (compat / "pfx" / "system.reg").read_text(encoding="utf-8")


def test_sem_o_curador_o_jogo_abre_e_o_rastro_diz(tmp_path: Path) -> None:
    """A máquina com o install incompleto — a razão de esta leva existir.

    A MORDIDA: tire o `registrar_audio_ks 0 sem-curador 0` e o rastro não
    nasce; o doctor passa a dizer "nenhum lançamento" sobre um que houve.
    """
    feito, compat, arquivo = _lancar(
        tmp_path, env_do_daemon=_ENV_LIGADO, registro=_registro(), sem_curador=True
    )
    assert feito.returncode == 0, feito.stderr
    assert "o jogo abriu" in feito.stdout
    assert _rastro(arquivo)["motivo"] == "sem-curador"
    assert "HEFESTOKS" not in (compat / "pfx" / "system.reg").read_text(encoding="utf-8")


def _nosso() -> str:
    """O bloco que um lançamento anterior gravou — o que o `--remover` tira."""
    return "\n".join(ks.blocos_do_controle(PADRAO, [bytes(8)], 1))


def test_sem_a_opcao_o_device_de_antes_sai_e_o_rastro_diz_removido(tmp_path: Path) -> None:
    """A MORDIDA: com o `--remover`, o 0 do curador virava `ok` — e o doctor
    dava "[ OK ] device KS conferido" sobre o device que acabara de SAIR.
    """
    feito, compat, arquivo = _lancar(
        tmp_path,
        env_do_daemon="PROTON_ENABLE_MHWILDS_USB_AUDIO=0\n",
        registro=_registro(_nosso()),
    )
    assert feito.returncode == 0, feito.stderr
    rastro = _rastro(arquivo)
    assert (rastro["motivo"], rastro["rc"]) == ("removido", "0"), rastro
    assert "HEFESTOKS" not in (compat / "pfx" / "system.reg").read_text(encoding="utf-8")


@pytest.mark.parametrize("com_bloco_nosso", [False, True], ids=["limpo", "com-bloco-de-antes"])
def test_sem_python3_o_jogo_abre_e_o_rastro_diz(tmp_path: Path, com_bloco_nosso: bool) -> None:
    """Sem `python3` no PATH do lançamento: rastro que aponta a MÁQUINA.

    As duas mordidas, uma por caso: com um bloco nosso a limpar, o wrapper
    saía sem rastro nenhum (o doctor lia o lançamento anterior como se fosse
    este); sem bloco, dizia `desligado`, que aponta para o controle.
    """
    registro = _registro(_nosso()) if com_bloco_nosso else _registro()
    feito, _, arquivo = _lancar(
        tmp_path, env_do_daemon=_ENV_LIGADO, registro=registro, sem_python=True
    )
    assert feito.returncode == 0, feito.stderr
    assert "o jogo abriu" in feito.stdout
    assert _rastro(arquivo)["motivo"] == "sem-python"


def test_jogo_nativo_nao_deixa_rastro(tmp_path: Path) -> None:
    """Sem `STEAM_COMPAT_DATA_PATH` não há prefixo, e não há o que dizer."""
    feito, _, arquivo = _lancar(
        tmp_path,
        env_do_daemon=_ENV_LIGADO,
        registro=_registro(),
        extra={"STEAM_COMPAT_DATA_PATH": ""},
    )
    assert feito.returncode == 0, feito.stderr
    assert not arquivo.exists()


# ------------------------------------------------------------------ o doctor


def _doctor(funcao: str, tmp_path: Path, **env: str) -> str:
    r = subprocess.run(
        ["bash", "-c", f'source "{DOCTOR}"; {funcao}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(tmp_path / "home"),
            "XDG_STATE_HOME": str(tmp_path / "estado"),
            "XDG_RUNTIME_DIR": str(tmp_path / "run"),
            **env,
        },
    )
    return r.stdout + r.stderr


def _rastro_no_disco(tmp_path: Path, motivo: str, rc: str = "0", tentativas: str = "1") -> None:
    pasta = tmp_path / "estado" / "hefesto-dualsense4unix" / "launch_env"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "audio_ks_ultimo").write_text(
        f"appid={APPID}\nepoch=1789700000\nrc={rc}\nmotivo={motivo}\ntentativas={tentativas}\n",
        encoding="utf-8",
    )


def test_doctor_sem_registro_e_informacao_e_nao_aviso(tmp_path: Path) -> None:
    """Todo jogo novo passa por aí: um aviso a cada jogo instalado seria ruído."""
    _rastro_no_disco(tmp_path, "sem-registro")
    saida = _doctor("check_ultimo_device_ks", tmp_path)
    assert "[WARN]" not in saida
    assert "vale a partir do próximo lançamento" in saida


def test_doctor_ocupado_depois_da_espera_e_aviso(tmp_path: Path) -> None:
    _rastro_no_disco(tmp_path, "ocupado", rc="3", tentativas="6")
    saida = _doctor("check_ultimo_device_ks", tmp_path)
    assert "[WARN] device KS do DualSense NÃO gravado" in saida
    assert "6 tentativa(s)" in saida


def test_doctor_erro_do_curador_e_aviso_com_o_codigo(tmp_path: Path) -> None:
    _rastro_no_disco(tmp_path, "erro", rc="124")
    saida = _doctor("check_ultimo_device_ks", tmp_path)
    assert "[WARN] o curador do device KS falhou" in saida
    assert "código 124" in saida


def test_doctor_ok_passa(tmp_path: Path) -> None:
    _rastro_no_disco(tmp_path, "ok")
    saida = _doctor("check_ultimo_device_ks", tmp_path)
    assert "[ OK ] device KS do DualSense conferido" in saida


def test_doctor_sem_curador_e_aviso_com_o_gesto(tmp_path: Path) -> None:
    """A MORDIDA: rebaixe o `sem-curador` a `info` e esta régua reprova."""
    _rastro_no_disco(tmp_path, "sem-curador")
    saida = _doctor("check_ultimo_device_ks", tmp_path)
    assert "[WARN] o último lançamento" in saida
    assert "não achou o curador do device KS" in saida
    assert "rode ./install.sh" in saida


def test_doctor_sem_python_e_aviso(tmp_path: Path) -> None:
    _rastro_no_disco(tmp_path, "sem-python")
    saida = _doctor("check_ultimo_device_ks", tmp_path)
    assert "[WARN] o último lançamento pelo Proton" in saida
    assert "não achou python3" in saida
    # O aviso diz o gesto: é a máquina, e não o controle.
    assert "instale o python3" in saida and "abra o jogo de novo" in saida


def test_doctor_desligado_e_informacao(tmp_path: Path) -> None:
    _rastro_no_disco(tmp_path, "desligado")
    saida = _doctor("check_ultimo_device_ks", tmp_path)
    assert "[WARN]" not in saida and "[ OK ]" not in saida
    assert "sem a opção da vibração" in saida


def test_doctor_removido_e_informacao_e_nao_verde(tmp_path: Path) -> None:
    """O device que SAIU não é "conferido": a frase do `desligado`, e o porquê."""
    _rastro_no_disco(tmp_path, "removido")
    saida = _doctor("check_ultimo_device_ks", tmp_path)
    assert "[WARN]" not in saida and "[ OK ]" not in saida
    assert "sem a opção da vibração" in saida
    assert "saiu do prefixo" in saida


def test_doctor_sem_rastro_nao_inventa(tmp_path: Path) -> None:
    saida = _doctor("check_ultimo_device_ks", tmp_path)
    assert "[WARN]" not in saida and "[ OK ]" not in saida
    assert "nenhum lançamento pelo Proton" in saida


_COPIAS = {
    "hefesto-launch": RAIZ / "assets" / "hefesto-launch.sh",
    "hefesto-camadas": _MODULO.with_name("camadas_vulkan.py"),
    "hefesto-audio-ks": _MODULO,
}


def _instalar_copias(tmp_path: Path, *, sem: str = "", velha: str = "") -> None:
    """O que o install.sh faz nos passos 4b-2 a 4b-4: `install -Dm755`, byte a byte."""
    binario = tmp_path / "home" / ".local" / "share" / "hefesto-dualsense4unix" / "bin"
    binario.mkdir(parents=True)
    for nome, fonte in _COPIAS.items():
        if nome == sem:
            continue
        dado = fonte.read_bytes()
        if nome == velha:
            dado += "\n# a cópia de antes do git pull\n".encode()
        (binario / nome).write_bytes(dado)
        (binario / nome).chmod(0o755)


def test_doctor_copias_iguais_ao_checkout_passam(tmp_path: Path) -> None:
    _instalar_copias(tmp_path)
    saida = _doctor("check_copias_do_wrapper", tmp_path)
    assert "[WARN]" not in saida
    assert "[ OK ] wrapper e curadores do lançamento instalados e iguais a este checkout" in saida


def test_doctor_acusa_a_copia_velha_de_qualquer_dos_tres(tmp_path: Path) -> None:
    """A MORDIDA do `cmp`: tire a comparação e a cópia velha passa em verde.

    É a CLASSE: os três pares envelhecem do mesmo jeito, e o `hefesto-camadas`
    é o que nenhum check olhava antes.
    """
    for nome in _COPIAS:
        caso = tmp_path / nome
        caso.mkdir()
        _instalar_copias(caso, velha=nome)
        saida = _doctor("check_copias_do_wrapper", caso)
        pasta = caso / "home" / ".local" / "share" / "hefesto-dualsense4unix" / "bin"
        assert f"[WARN] cópia em {pasta} diferente deste checkout: {nome}" in saida, saida
        assert "rode ./install.sh" in saida


def test_doctor_acusa_o_curador_ausente(tmp_path: Path) -> None:
    _instalar_copias(tmp_path, sem="hefesto-audio-ks")
    saida = _doctor("check_copias_do_wrapper", tmp_path)
    assert "[WARN] curador hefesto-audio-ks ausente" in saida
    assert "vibração dos jogos da Sony" in saida


def test_o_doctor_roda_as_duas_checagens() -> None:
    """A função existir não basta: ela tem de estar no `main()` do doctor."""
    texto = DOCTOR.read_text(encoding="utf-8")
    corpo = texto[texto.index("\nmain() {") :]
    corpo = corpo[: corpo.index("\n}\n")]
    assert "\n    check_copias_do_wrapper\n" in corpo
    assert "\n    check_ultimo_device_ks\n" in corpo
