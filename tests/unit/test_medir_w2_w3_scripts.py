"""Onda W — scripts de medição W2 (LPS raso) e W3 (coexistência WiFi x BT).

Desenho: docs/process/estudos/2026-07-20-desenho-onda-w-patch-dkms.md (§4/§5).

Contrato (falha-sem/passa-com, SEM root, SEM tocar WiFi/BT reais):
- `bash -n` limpo e executáveis;
- DRY-RUN POR DEFAULT: sem `--run` NENHUM nmcli modify/up, ping, curl ou
  rfkill roda — provado FUNCIONALMENTE com stubs que registram cada
  invocação (o W2 só faz descoberta read-only no dry-run);
- W3 `--run` sem root morre ANTES de qualquer rfkill (gate de root);
- traps de restauração presentes: W2 devolve o powersave ORIGINAL ganhe
  quem ganhar; W3 nunca deixa o WiFi bloqueado (rfkill unblock no EXIT);
- W2 NÃO persiste nada: nenhuma escrita em modprobe.d/NM conf (o
  disable_lps_deep é NO-OP em USB — não existe conf dele em lugar nenhum);
- o asset gateado assets/NetworkManager/hefesto-wifi-powersave.conf tem
  EXATAMENTE a cura mínima (match wifi + powersave=2) e nada mais.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

BASH = shutil.which("bash") or "/bin/bash"
REPO_ROOT = Path(__file__).resolve().parents[2]
W2_PATH = REPO_ROOT / "scripts" / "medir_w2_lps.sh"
W3_PATH = REPO_ROOT / "scripts" / "medir_w3_coex.sh"
NM_CONF_PATH = REPO_ROOT / "assets" / "NetworkManager" / "hefesto-wifi-powersave.conf"

W2 = W2_PATH.read_text(encoding="utf-8") if W2_PATH.exists() else ""
W3 = W3_PATH.read_text(encoding="utf-8") if W3_PATH.exists() else ""
NM_CONF = NM_CONF_PATH.read_text(encoding="utf-8") if NM_CONF_PATH.exists() else ""


def _sem_comentarios(texto: str) -> str:
    linhas = [re.sub(r"(^|\s)#.*$", r"\1", linha) for linha in texto.splitlines()]
    return "\n".join(linhas)


def _stub_logando(stubs: Path, nome: str, resposta: str = "") -> None:
    """Stub que registra CADA invocação em ${W_STUB_LOG} e responde fixo."""
    corpo = (
        "#!/bin/bash\n"
        f'printf \'%s\\n\' "{nome} $*" >> "${{W_STUB_LOG}}"\n'
        f"{resposta}\n"
    )
    caminho = stubs / nome
    caminho.write_text(corpo, encoding="utf-8")
    caminho.chmod(0o755)


def _roda_script(
    script: Path, args: list[str], stubs: Path, log: Path
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = f"{stubs}:/usr/bin:/bin"
    env["W_STUB_LOG"] = str(log)
    return subprocess.run(
        [BASH, str(script), *args], capture_output=True, text=True, check=False, env=env
    )


def _stubs_w2(tmp_path: Path) -> tuple[Path, Path]:
    stubs = tmp_path / "bin"
    stubs.mkdir(exist_ok=True)
    log = tmp_path / "chamadas.log"
    log.write_text("", encoding="utf-8")
    # Descoberta read-only do W2: device wifi, conexão ativa, powersave
    # atual e gateway — respostas plausíveis e determinísticas.
    _stub_logando(
        stubs,
        "nmcli",
        'case "$*" in\n'
        '  *"device status"*) echo "wlxfake0:wifi" ;;\n'
        '  *"connection show --active"*) echo "CasaNet:wlxfake0" ;;\n'
        '  *"802-11-wireless.powersave"*) echo "3" ;;\n'
        "esac",
    )
    _stub_logando(stubs, "ip", 'echo "default via 192.168.1.1 proto dhcp metric 600"')
    # Ferramentas do --run: se QUALQUER uma rodar no dry-run, o log entrega.
    for nome in ("ping", "curl", "journalctl", "rfkill"):
        _stub_logando(stubs, nome)
    return stubs, log


class TestLayoutESintaxe:
    def test_scripts_e_asset_presentes(self) -> None:
        for path in (W2_PATH, W3_PATH, NM_CONF_PATH):
            assert path.exists(), f"arquivo da Onda W ausente: {path.relative_to(REPO_ROOT)}"

    def test_bash_n_limpo(self) -> None:
        for caminho in (W2_PATH, W3_PATH):
            resultado = subprocess.run(
                ["bash", "-n", str(caminho)], capture_output=True, text=True, check=False
            )
            assert resultado.returncode == 0, f"{caminho.name}: {resultado.stderr}"

    def test_scripts_executaveis(self) -> None:
        # O uso documentado é `./medir_*.sh` — sem o bit de execução o
        # gate humano tropeça no primeiro passo.
        for caminho in (W2_PATH, W3_PATH):
            assert os.access(caminho, os.X_OK), f"{caminho.name} sem chmod +x"


class TestW2DryRunPorDefault:
    """Funcional: stubs registram cada chamada — dry-run só pode LER."""

    def test_dry_run_nao_modifica_nada(self, tmp_path: Path) -> None:
        stubs, log = _stubs_w2(tmp_path)
        resultado = _roda_script(W2_PATH, [], stubs, log)
        assert resultado.returncode == 0, resultado.stderr
        assert "DRY-RUN" in resultado.stdout
        chamadas = log.read_text(encoding="utf-8")
        assert "modify" not in chamadas, "dry-run NUNCA muda o powersave"
        assert "connection up" not in chamadas, "dry-run NUNCA derruba/religa o WiFi"
        for proibido in ("ping", "curl", "journalctl", "rfkill"):
            assert not re.search(rf"^{proibido} ", chamadas, re.MULTILINE), (
                f"dry-run não pode medir de verdade ({proibido} rodou)"
            )

    def test_dry_run_descobre_e_mostra_o_plano(self, tmp_path: Path) -> None:
        stubs, log = _stubs_w2(tmp_path)
        resultado = _roda_script(W2_PATH, [], stubs, log)
        assert "wlxfake0" in resultado.stdout, "a descoberta read-only aparece no plano"
        assert "powersave" in resultado.stdout
        assert "--run" in resultado.stdout, "o plano aponta o gate humano (--run)"

    def test_argumento_desconhecido_e_erro(self, tmp_path: Path) -> None:
        stubs, log = _stubs_w2(tmp_path)
        resultado = _roda_script(W2_PATH, ["--frobnicar"], stubs, log)
        assert resultado.returncode == 2, (
            "arg desconhecido precisa falhar alto (typo em --run não pode virar dry-run)"
        )


class TestW3DryRunEGateDeRoot:
    def _stubs_w3(self, tmp_path: Path) -> tuple[Path, Path]:
        stubs = tmp_path / "bin"
        stubs.mkdir(exist_ok=True)
        log = tmp_path / "chamadas.log"
        log.write_text("", encoding="utf-8")
        for nome in ("rfkill", "btmon", "hciconfig", "curl", "python3"):
            _stub_logando(stubs, nome)
        return stubs, log

    def test_dry_run_nao_toca_em_nada(self, tmp_path: Path) -> None:
        stubs, log = self._stubs_w3(tmp_path)
        resultado = _roda_script(W3_PATH, [], stubs, log)
        assert resultado.returncode == 0, resultado.stderr
        assert "DRY-RUN" in resultado.stdout
        assert log.read_text(encoding="utf-8") == "", (
            "o dry-run do W3 é 100% inerte — nenhuma ferramenta pode rodar"
        )

    def test_run_sem_root_morre_antes_de_qualquer_rfkill(self, tmp_path: Path) -> None:
        assert os.geteuid() != 0, "a suíte nunca roda como root (regra da casa)"
        stubs, log = self._stubs_w3(tmp_path)
        resultado = _roda_script(W3_PATH, ["--run"], stubs, log)
        assert resultado.returncode != 0, "--run sem root tem de falhar"
        assert "root" in resultado.stderr, "mensagem honesta do gate de root"
        assert log.read_text(encoding="utf-8") == "", (
            "o gate de root vem ANTES de qualquer rfkill/btmon"
        )


class TestFailSafesDeRestauracao:
    def test_w2_trap_exit_restaura_o_powersave_original(self) -> None:
        assert "trap restaurar EXIT" in W2
        ini = W2.index("restaurar() {")
        corpo = W2[ini : W2.index("\n}", ini)]
        assert "802-11-wireless.powersave" in corpo
        assert '"${PS_ORIG}"' in corpo, (
            "a restauração devolve o valor ORIGINAL medido no início — ganhe "
            "quem ganhar, a conexão volta como estava"
        )

    def test_w3_trap_exit_desbloqueia_o_wifi(self) -> None:
        assert "trap restaurar EXIT" in W3
        assert "rfkill unblock wifi" in W3, (
            "fail-safe absoluto: NUNCA deixar o WiFi bloqueado ao sair"
        )


class TestNadaDestrutivoNemPersistente:
    def test_w2_nao_escreve_modprobe_d_nem_conf_do_nm(self) -> None:
        codigo = _sem_comentarios(W2)
        assert "modprobe.d" not in codigo, (
            "disable_lps_deep é NO-OP em USB — não existe conf de modprobe.d "
            "no W2 (o vilão ativo é o LPS raso via NM)"
        )
        assert "/etc/" not in codigo, (
            "o W2 MEDE E RELATA — persistir powersave=2 é decisão gateada "
            "pela evidência (asset próprio, opt-in do install)"
        )

    def test_w2_nao_toca_rfkill_nem_modulo(self) -> None:
        codigo = _sem_comentarios(W2)
        assert not re.search(r"\brfkill\b", codigo)
        assert not re.search(r"\b(modprobe|rmmod|insmod)\b", codigo)

    def test_w3_nao_toca_nm_nem_modulo(self) -> None:
        codigo = _sem_comentarios(W3)
        assert not re.search(r"\bnmcli\b", codigo), (
            "o W3 isola rádio vs EMI via rfkill — nunca reconfigura conexão"
        )
        assert "/etc/" not in codigo
        assert not re.search(r"\b(modprobe|rmmod|insmod)\b", codigo)

    def test_w3_recomendacao_de_topologia_e_impressa_nao_executada(self) -> None:
        # A recomendação (mover o dongle p/ o xHCI 02:00.0 com portas
        # SuperSpeed livres) é MEDÍVEL e manual — nenhum script move nada.
        assert "02:00.0" in W3
        assert "re-rodar" in W3

    def test_gate_humano_documentado_nos_dois(self) -> None:
        for texto, nome in ((W2, "W2"), (W3, "W3")):
            assert "--run" in texto, f"{nome} sem o gate --run"
            assert "gate humano" in texto.lower(), (
                f"{nome}: a exigência de gate humano fica escrita no script"
            )


class TestAssetPowersaveGateado:
    def test_conteudo_minimo_da_cura(self) -> None:
        assert "[connection.hefesto-wifi-powersave]" in NM_CONF
        assert "match-device=type:wifi" in NM_CONF
        assert "wifi.powersave=2" in NM_CONF

    def test_nada_alem_da_cura(self) -> None:
        efetivas = [
            linha.strip()
            for linha in NM_CONF.splitlines()
            if linha.strip() and not linha.strip().startswith("#")
        ]
        assert efetivas == [
            "[connection.hefesto-wifi-powersave]",
            "match-device=type:wifi",
            "wifi.powersave=2",
        ], "o conf.d carrega SÓ a cura medida — tuning extra não pega carona"

    def test_asset_documenta_o_gate_por_evidencia(self) -> None:
        assert "medir_w2_lps.sh" in NM_CONF, (
            "o cabeçalho aponta a medição que justifica (ou não) instalar"
        )
