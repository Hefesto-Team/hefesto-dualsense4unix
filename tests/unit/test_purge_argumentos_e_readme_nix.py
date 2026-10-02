"""Duas bordas do que o projeto entrega a quem não é a mantenedora."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PURGE = RAIZ / "scripts" / "purge.sh"
INSTALL_UDEV = RAIZ / "scripts" / "install_udev.sh"
PACKAGE_NIX = RAIZ / "packaging" / "nix" / "package.nix"
README_NIX = RAIZ / "packaging" / "nix" / "README.md"


def _ambiente_de_sacrificio(tmp_path: Path) -> dict[str, str]:
    """PATH com `sudo` inerte e HOME descartável."""
    binario = tmp_path / "bin"
    binario.mkdir()
    falso = binario / "sudo"
    falso.write_text('#!/bin/sh\necho "[sudo-falso] $*"\n', encoding="utf-8")
    falso.chmod(0o755)

    ambiente = dict(os.environ)
    ambiente["PATH"] = f"{binario}:{ambiente.get('PATH', '')}"
    ambiente["HOME"] = str(tmp_path / "casa")
    (tmp_path / "casa").mkdir()
    return ambiente


def _rodar(script: Path, *args: str, tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(script), *args],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        env=_ambiente_de_sacrificio(tmp_path),
        cwd=str(RAIZ),
        timeout=60,
        check=False,
    )


class TestPurgeNaoAceitaOQueNaoEntende:
    def test_help_imprime_as_flags_e_sai_zero(self, tmp_path: Path) -> None:
        """`--help` é o reflexo de quem vê um script novo pela primeira vez."""
        r = _rodar(PURGE, "--help", tmp_path=tmp_path)
        assert r.returncode == 0, f"--help não saiu 0 (saiu {r.returncode}): {r.stderr}"
        for flag in ("--yes", "--dry-run", "--with-config", "--keep-steam-input"):
            assert flag in r.stdout, f"o --help não documenta {flag}"
        assert "descontaminar TODAS" not in r.stdout, (
            "o --help chegou a fazer a pergunta do wipe — ele não pode passar do parser"
        )
        assert "[purge] início" not in r.stdout, "o --help entrou no main()"

    def test_argumento_desconhecido_aborta_sem_tocar_em_nada(self, tmp_path: Path) -> None:
        """O dedo torto com `--yes` legítimo era o buraco de verdade."""
        r = _rodar(PURGE, "--dry-rum", "--dry-run", tmp_path=tmp_path)
        assert r.returncode == 2, (
            f"argumento desconhecido não abortou com 2 (saiu {r.returncode})"
        )
        assert "desconhecido" in r.stderr
        assert "[purge] início" not in r.stdout, (
            "o purge entrou no main() depois de ver um argumento que não entende"
        )

    def test_o_corpo_do_desconhecido_tem_exit_2(self) -> None:
        """Complemento barato, no molde do teste do install: o ramo existe no"""
        texto = PURGE.read_text(encoding="utf-8")
        inicio = texto.index('for arg in "$@"; do')
        parser = texto[inicio : texto.index("\ndone\n", inicio)]
        assert "exit 2" in parser, "o `*)` do parser do purge voltou a não abortar"
        assert "--help" in parser, "o parser do purge voltou a não conhecer --help"


class TestInstallUdevSegueOMesmoPadrao:
    def test_help_sai_zero_sem_instalar(self, tmp_path: Path) -> None:
        r = _rodar(INSTALL_UDEV, "--help", tmp_path=tmp_path)
        assert r.returncode == 0
        assert "--disable-usb-audio" in r.stdout
        assert "[0/3]" not in r.stdout, "o --help chegou a executar o primeiro passo"

    def test_flag_com_erro_de_digitacao_aborta(self, tmp_path: Path) -> None:
        """Aqui o pior caso é inócuo — o script só reaplica regras. Entra por"""
        r = _rodar(INSTALL_UDEV, "--disable-usb-audi", tmp_path=tmp_path)
        assert r.returncode == 2, (
            f"install_udev.sh não abortou com 2 (saiu {r.returncode}): {r.stdout}"
        )
        assert "[0/3]" not in r.stdout, "o script começou a instalar mesmo assim"


def _placeholder_de_hash_ativo(texto_nix: str) -> bool:
    """`lib.fakeSha256` numa linha que ATRIBUI o hash, não em comentário."""
    return any(
        "fakeSha256" in linha.strip()
        for linha in texto_nix.splitlines()
        if not linha.strip().startswith("#")
    )


class TestReadmeDoNixNaoPrometeOQueOHashImpede:
    def test_o_aviso_do_hash_vem_antes_do_primeiro_comando(self) -> None:
        """A ressalva existia — 111 linhas ABAIXO da promessa."""
        pacote = PACKAGE_NIX.read_text(encoding="utf-8")
        readme = README_NIX.read_text(encoding="utf-8")

        if not _placeholder_de_hash_ativo(pacote):
            assert "fakeSha256" not in readme, (
                "o hash real entrou no package.nix e o README continua avisando "
                "que ele é placeholder"
            )
            return

        assert "fakeSha256" in readme, (
            "o package.nix ainda tem o placeholder e o README não avisa"
        )
        primeiro_comando = readme.index("```")
        assert readme.index("fakeSha256") < primeiro_comando, (
            "o aviso do hash placeholder está DEPOIS do primeiro bloco de "
            "comando — quem lê o 'Uso rapido' não chega nele"
        )
        assert "nix-prefetch-url" in readme[:primeiro_comando], (
            "o aviso não diz como preencher o hash"
        )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__]))
