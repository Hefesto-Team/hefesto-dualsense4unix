"""Duas bordas do que o projeto entrega a quem não é a mantenedora.

1. O `scripts/purge.sh` é o script mais destrutivo da casa — ele chama o
   `uninstall.sh --yes`. Até 31/07 ele não tinha `--help` e aceitava argumento
   desconhecido com um aviso, seguindo em frente: é o mesmo acidente que o
   `uninstall.sh` já pagou (`BUG-UNINSTALL-HELP-DESINSTALA-01`). O
   `scripts/install_udev.sh` entra na mesma passada por política: dois padrões
   de parser na mesma pasta é o que faz o próximo script nascer com o frouxo.
2. O `packaging/nix/README.md` abre prometendo `nix run`, e o
   `packaging/nix/package.nix` tem `lib.fakeSha256` — todo comando da página
   falha por construção enquanto o hash for placeholder.

Os testes que executam o `purge.sh` rodam com um `sudo` falso no PATH e com
`HOME` num diretório temporário: mesmo que a cura seja arrancada e o parser
volte a seguir em frente, nenhum passo com root e nenhum passo no HOME real
pode acontecer.
"""
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
    """PATH com `sudo` inerte e HOME descartável.

    A rede de proteção existe para o dia em que o teste ficar VERMELHO: é
    justamente aí que o script voltaria a executar de verdade.
    """
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
        """`--help` é o reflexo de quem vê um script novo pela primeira vez.

        Mordida: sem o case `--help`, a flag cai no `*)`, o script segue para o
        `main()` e a primeira coisa que a pessoa vê é a pergunta se quer
        descontaminar tudo.
        """
        r = _rodar(PURGE, "--help", tmp_path=tmp_path)
        assert r.returncode == 0, f"--help não saiu 0 (saiu {r.returncode}): {r.stderr}"
        for flag in ("--yes", "--dry-run", "--with-config", "--keep-steam-input"):
            assert flag in r.stdout, f"o --help não documenta {flag}"
        assert "descontaminar TODAS" not in r.stdout, (
            "o --help chegou a fazer a pergunta do wipe — ele não pode passar do parser"
        )
        assert "[purge] início" not in r.stdout, "o --help entrou no main()"

    def test_argumento_desconhecido_aborta_sem_tocar_em_nada(self, tmp_path: Path) -> None:
        """O dedo torto com `--yes` legítimo era o buraco de verdade.

        `--dry-rum` em vez de `--dry-run` virava um aviso rolando para fora da
        tela, e o `main()` seguia — com `--yes`, sem sequer perguntar.

        Mordida: com o `*)` de volta ao aviso sem `exit`, o `--dry-run` liga o
        modo simulado, o script percorre o `main()` inteiro e sai 0. O
        `--dry-run` fica no comando de propósito: com a cura ou sem ela, este
        teste nunca muta o sistema.
        """
        r = _rodar(PURGE, "--dry-rum", "--dry-run", tmp_path=tmp_path)
        assert r.returncode == 2, (
            f"argumento desconhecido não abortou com 2 (saiu {r.returncode})"
        )
        assert "desconhecido" in r.stderr
        assert "[purge] início" not in r.stdout, (
            "o purge entrou no main() depois de ver um argumento que não entende"
        )

    def test_o_corpo_do_desconhecido_tem_exit_2(self) -> None:
        """Complemento barato, no molde do teste do install: o ramo existe no
        código, e não só no comportamento observado."""
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
        """Aqui o pior caso é inócuo — o script só reaplica regras. Entra por
        política: manter dois padrões de parser na mesma pasta é o que faz o
        próximo script nascer com o frouxo.

        Mordida: com o `*)` de volta ao aviso, o script segue e imprime `[0/3]`.
        """
        r = _rodar(INSTALL_UDEV, "--disable-usb-audi", tmp_path=tmp_path)
        assert r.returncode == 2, (
            f"install_udev.sh não abortou com 2 (saiu {r.returncode}): {r.stdout}"
        )
        assert "[0/3]" not in r.stdout, "o script começou a instalar mesmo assim"


def _placeholder_de_hash_ativo(texto_nix: str) -> bool:
    """`lib.fakeSha256` numa linha que ATRIBUI o hash, não em comentário.

    O `package.nix` cita o nome num comentário sobre outro assunto: procurar a
    string no arquivo inteiro faria o teste continuar verde depois de alguém
    gravar o hash real — e ele deixaria de cobrar a remoção do aviso.
    """
    return any(
        "fakeSha256" in linha.strip()
        for linha in texto_nix.splitlines()
        if not linha.strip().startswith("#")
    )


class TestReadmeDoNixNaoPrometeOQueOHashImpede:
    def test_o_aviso_do_hash_vem_antes_do_primeiro_comando(self) -> None:
        """A ressalva existia — 111 linhas ABAIXO da promessa.

        Com `lib.fakeSha256`, todo `fetchPypi` falha em hash-mismatch por
        desenho, então `nix run`/`nix build` são impossíveis por construção. E
        no caminho `nix run github:...` não existe "substituir uma vez": não há
        árvore local para editar.

        Mordida nos dois sentidos: mover o aviso para baixo do "Uso rapido" →
        vermelho; e, quando alguém gravar o hash real e esquecer de tirar o
        aviso, o outro ramo cobra a remoção. Sem essa segunda metade o teste
        viraria carimbo.
        """
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
