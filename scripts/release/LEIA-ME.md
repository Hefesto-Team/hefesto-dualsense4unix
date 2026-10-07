# Como uma release sai

Tudo daqui roda com o `python3` do sistema (só a biblioteca padrão) e segue o mesmo contrato: rodar de novo não
muda nada, `--conferir` diz o que mudaria e sai 1 se mudaria, e a primeira linha da saída é o resumo.

## O caminho, da versão à tag

```bash
python3 scripts/release/versao.py seguinte           # a próxima versão, pelo tipo dos commits desde a última tag
python3 scripts/release/changelog.py montar 0.9.5    # a seção do CHANGELOG, do que estava escrito e do que foi fechado
python3 scripts/release/versao.py gravar 0.9.5       # a mesma versão em todos os alvos (e a release do AppStream)
git add <os arquivos que o gravar listou> && git commit -m "chore(release): 0.9.5"
git tag v0.9.5 && git push origin v0.9.5             # a tag dispara o .github/workflows/release.yml
```

A série (`0.9.5`, ou `4` para seguir do `v4.0.0`) é a linha `release.serie` de `.github/repositorio.yml`: `feat` e `fix`
sobem o mesmo número, o primeiro depois dela (0.9.5 -> 0.9.5.1 -> 0.9.5.2). Nenhum número
é escolhido à mão, e `docs`, `test` e `chore` sozinhos não lançam nada.

O que entra na seção do CHANGELOG, sem repetir linha:

1. o que estiver escrito à mão em `## [Unreleased]` (a seção passa a ficar vazia);
2. o bloco `publico` de cada sprint fechada desde a última tag (o formato está em `publico.py`);
3. o título dos PRs que entraram desde a última tag.

## O que o `release.yml` faz com a tag

1. `build`: a tag tem de dizer a versão do pacote (`versao.py conferir-tag`), e os portões rodam como no CI.
2. `appimage`, `deb`, `flatpak`: cada artefato, e o smoke de instalação do `.deb`.
3. `integridade`: o `SHA256SUMS` de todo arquivo e o atestado de procedência de cada um.
4. `github-release` (ambiente `release`, com a aprovação de quem mantém): a release nasce como **rascunho**, recebe os
   arquivos e só então é publicada (`publicar.py`). A release imutável trava a versão ao publicar: apagar e recriar a
   versão deixou de existir, e a correção de uma versão publicada é a versão seguinte.
5. `pypi` (ambiente `pypi`, só com a variável `PYPI_PUBLISH` igual a `true`).
6. `pacotes`: os arquivos do `PKGBUILD`, do `.spec`, do `control` e do Nix na versão da tag, com o hash do tarball dela,
   num artefato; com a variável `PACOTES_REPOS` (`DONO/NOME[:distro]`, separados por vírgula) e o segredo
   `PACOTES_TOKEN`, também abre o PR de atualização em cada repositório de pacote.

## Conferir o que se baixou

```bash
sha256sum -c SHA256SUMS --ignore-missing
gh attestation verify NOME-DO-ARQUIVO --repo Hefesto-Team/hefesto-dualsense4unix
```

## O que é de quem mantém, uma vez cada

- **A série da versão**: a linha `release.serie`. A que está lá vale até quem mantém trocar.
- **O publicador de confiança do PyPI** (a publicação usa OIDC, sem segredo): em
  <https://pypi.org/manage/account/publishing/> registrar o dono `Hefesto-Team`, o repositório
  `hefesto-dualsense4unix`, o fluxo `release.yml` e o ambiente `pypi`; depois criar a variável de repositório
  `PYPI_PUBLISH` com o valor `true`. Enquanto a variável não existir, `scripts/github/aplicar.py --conferir` avisa no
  detalhe («aviso: release: o publicador de confiança do PyPI não está registrado…»).
- **O AUR e o Flathub** são contas de quem mantém: o artefato `pacotes-<versão>` traz os arquivos prontos, e a primeira
  publicação lá é à mão. Depois dela, um repositório de pacote hospedado no GitHub entra em `PACOTES_REPOS`.
