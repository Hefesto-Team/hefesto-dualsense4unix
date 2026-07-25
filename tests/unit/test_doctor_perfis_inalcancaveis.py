"""Check "perfis inalcançáveis" do doctor.sh (débito R-12 item 2).

A GUI já dizia "Só manual (nunca ativa sozinho)" na coluna "Quando usar"; na
linha de comando não havia nada — um perfil sem critério de janela não falha,
não loga e não aparece em lugar nenhum. Ele só nunca entra, e a leitura de
quem está do lado de cá é "o autoswitch está quebrado".

A lógica vive em shell puro no doctor.sh (funções testáveis via ``source``,
padrão de `test_doctor_vpad_motion.py` / `test_doctor_8bitdo_cascade.py`):

- ``_perfis_inalcancaveis <dir>``: classifica cada JSON do diretório em
  ``inalcancavel`` (criteria com os três campos vazios — o acidente),
  ``manual`` (sentinel declarado) ou ``ilegivel``. Perfis sãos não saem.
- ``check_perfis_inalcancaveis``: formata o relatório, lendo o diretório do
  XDG (funciona com o daemon parado, que é quando ela vai olhar).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DOCTOR = ROOT / "scripts" / "doctor.sh"

_ENV_BASE = {"PATH": "/usr/bin:/bin:/usr/local/bin", "DOCTOR_SH": str(DOCTOR)}


def _rodar(linha: str, **env: str) -> str:
    """Executa uma função shell REAL do doctor (source, sem rodar o main)."""
    res = subprocess.run(
        ["bash", "-c", f'set --; source "$DOCTOR_SH"; {linha}'],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env={**_ENV_BASE, "HOME": env.get("HOME", "/nao-existe"), **env},
    )
    assert res.returncode == 0, res.stderr
    return res.stdout.strip()


def _escrever(dir_: Path, nome: str, match: Any) -> None:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / f"{nome}.json").write_text(
        json.dumps({"name": nome, "version": 1, "match": match, "priority": 10}),
        encoding="utf-8",
    )


class TestClassificacao:
    def test_criteria_vazio_e_denunciado(self, tmp_path: Path) -> None:
        """O acidente: o preset `coop_local` de fábrica ficou assim por meses."""
        _escrever(tmp_path, "coop_local", {"type": "criteria"})

        saida = _rodar(f'_perfis_inalcancaveis "{tmp_path}"')

        assert saida.split("\t")[0] == "inalcancavel"
        assert "coop_local" in saida

    def test_sentinel_manual_sai_como_declaracao(self, tmp_path: Path) -> None:
        """Não é defeito: alguém escreveu que o perfil é só para a mão."""
        _escrever(tmp_path, "so_na_mao", {"type": "manual"})

        assert _rodar(f'_perfis_inalcancaveis "{tmp_path}"').startswith("manual\t")

    def test_perfis_saos_nao_aparecem(self, tmp_path: Path) -> None:
        _escrever(tmp_path, "fallback", {"type": "any"})
        _escrever(tmp_path, "navegacao", {"type": "criteria", "window_class": ["firefox"]})
        _escrever(tmp_path, "fps", {"type": "criteria", "window_title_regex": "Doom"})
        _escrever(tmp_path, "jogo", {"type": "criteria", "process_name": ["eldenring"]})

        assert _rodar(f'_perfis_inalcancaveis "{tmp_path}"') == ""

    def test_json_quebrado_nao_some_em_silencio(self, tmp_path: Path) -> None:
        (tmp_path / "torto.json").write_text("{isto não é json", encoding="utf-8")

        saida = _rodar(f'_perfis_inalcancaveis "{tmp_path}"')

        assert saida.startswith("ilegivel\ttorto.json")

    def test_diretorio_ausente_devolve_vazio_sem_erro(self, tmp_path: Path) -> None:
        assert _rodar(f'_perfis_inalcancaveis "{tmp_path}/nao-existe"') == ""

    def test_uma_linha_por_perfil_problematico(self, tmp_path: Path) -> None:
        _escrever(tmp_path, "orfao_a", {"type": "criteria"})
        _escrever(tmp_path, "orfao_b", {"type": "criteria", "window_class": []})
        _escrever(tmp_path, "bom", {"type": "any"})

        linhas = _rodar(f'_perfis_inalcancaveis "{tmp_path}"').splitlines()

        assert [linha.split("\t")[0] for linha in linhas] == [
            "inalcancavel",
            "inalcancavel",
        ]


class TestRelatorio:
    def _xdg(self, tmp_path: Path) -> Path:
        return tmp_path / "hefesto-dualsense4unix" / "profiles"

    def test_avisa_e_ensina_a_cura(self, tmp_path: Path) -> None:
        _escrever(self._xdg(tmp_path), "coop_local", {"type": "criteria"})

        saida = _rodar(
            "check_perfis_inalcancaveis", XDG_CONFIG_HOME=str(tmp_path)
        )

        assert "[WARN]" in saida
        assert "coop_local" in saida
        # A cura tem de estar na própria linha: quem roda o doctor não vai
        # procurar o significado de "inalcançável" na documentação.
        assert "manual" in saida and "Perfis" in saida

    def test_manual_declarado_nao_vira_aviso(self, tmp_path: Path) -> None:
        """É exatamente o ponto do sentinel: parar de acusar quem foi honesto."""
        _escrever(self._xdg(tmp_path), "so_na_mao", {"type": "manual"})

        saida = _rodar(
            "check_perfis_inalcancaveis", XDG_CONFIG_HOME=str(tmp_path)
        )

        assert "[WARN]" not in saida
        assert "[ OK ]" in saida
        assert "so_na_mao" in saida

    def test_tudo_sao_passa(self, tmp_path: Path) -> None:
        _escrever(self._xdg(tmp_path), "fallback", {"type": "any"})

        saida = _rodar(
            "check_perfis_inalcancaveis", XDG_CONFIG_HOME=str(tmp_path)
        )

        assert saida.startswith("[ OK ]")

    def test_sem_diretorio_e_informacao_nao_aviso(self, tmp_path: Path) -> None:
        """Antes do primeiro boot do daemon não existe perfil nenhum."""
        saida = _rodar(
            "check_perfis_inalcancaveis", XDG_CONFIG_HOME=str(tmp_path)
        )

        assert "[WARN]" not in saida and "[FAIL]" not in saida


class TestFiacaoNoMain:
    def test_check_roda_no_diagnostico(self) -> None:
        """Regra da casa: um item que existe no doctor é chamado pelo main."""
        fonte = DOCTOR.read_text(encoding="utf-8")
        assert "    check_perfis_inalcancaveis\n" in fonte
