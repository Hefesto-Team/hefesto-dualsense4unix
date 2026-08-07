# LICENSES/ — os textos das licenças de terceiros que viajam com o Hefesto

Este diretório existe por uma exigência escrita, não por capricho: a **GPL-2.0,
seção 1**, obriga quem distribui o código-fonte a *"dar a qualquer outro
destinatário do Programa uma cópia desta Licença junto com o Programa"*.

O Hefesto distribui código-fonte de terceiros sob GPL-2.0 — os três módulos de
kernel de `assets/dkms/` — em cinco dos seus alvos de empacotamento. Os avisos
`SPDX-License-Identifier` estão preservados nos arquivos desde sempre, e isso é
metade da exigência. **A cópia do texto era a metade que faltava**, e é o que
mora aqui.

O que cada texto cobre, e de onde veio, está abaixo. A auditoria arquivo a
arquivo (origem, patches próprios, `MODULE_LICENSE`, linha do SPDX) está no
`NOTICE`, na raiz do repositório — este README não a repete.

## Os arquivos

### `GPL-2.0.txt`

**Cobre:** `assets/dkms/hid-nintendo/` (SPDX `GPL-2.0+` e `GPL-2.0-or-later`),
`assets/dkms/hid-playstation/` (SPDX `GPL-2.0-or-later`) e a metade GPL do
`assets/dkms/rtw88-usb/` (SPDX `GPL-2.0 OR BSD-3-Clause`).

**Procedência — MEDIDO em 07/08/2026:** cópia byte a byte de
`/usr/share/common-licenses/GPL-2`, o texto que o pacote `base-files` do
Debian/Pop!\_OS distribui (`dpkg -S` confirma o dono). Nenhuma modificação.

| o quê | valor |
|---|---|
| SHA-256 | `8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643` |
| linhas | 339 |

Conferir a qualquer momento, sem confiar em ninguém:

```bash
sha256sum LICENSES/GPL-2.0.txt
diff LICENSES/GPL-2.0.txt /usr/share/common-licenses/GPL-2   # em Debian/Ubuntu/Pop!_OS
```

### `BSD-3-Clause.txt`

**Cobre:** a **outra metade** do `assets/dkms/rtw88-usb/`. Aquele módulo não é
GPL pura: `usb.c:1` e os onze cabeçalhos vendorados trazem
`SPDX-License-Identifier: GPL-2.0 OR BSD-3-Clause`, e `usb.c:1504` traz
`MODULE_LICENSE("Dual BSD/GPL")`. É licença **dupla** — quem redistribui escolhe
um dos dois termos —, e enviar só o texto da GPL deixaria metade da escolha sem
o texto que a sustenta.

**Procedência — MEDIDO em 07/08/2026:** extraído literalmente da estrofe
`License:   BSD-3-Clause` de `/usr/share/doc/libbpf1/copyright` (formato DEP-5),
com a única transformação sendo mecânica e reversível: remover o espaço de
indentação de cada linha e trocar as linhas `.` por linhas em branco, que é
exatamente o que o DEP-5 define. **Nenhuma palavra foi escrita à mão** — a
regra da casa aqui é "não se inventa texto de licença".

| o quê | valor |
|---|---|
| SHA-256 do texto extraído | `89ab950bb21ce83f5ec42ea3d44e1fdc2d61db642c8d6f23e10995c33528adcf` |
| SHA-256 do arquivo de origem | `4d0df00a62374f3992ad0f2ec566838cafb406d11bef776d2667d3aabaa4b430` |

Uma ressalva que precisa estar escrita, porque um leitor apressado tropeça nela:
o texto começa em *"Redistribution and use..."* e **não** traz a linha
`Copyright (c) <ano> <titular>`. Isso não é omissão — o titular do direito é
declarado no cabeçalho de cada arquivo coberto
(`Copyright(c) 2018-2019 Realtek Corporation`, em `assets/dkms/rtw88-usb/usb.c:2`
e nos demais), e é lá que ele tem de estar. O que este arquivo carrega são as
**condições**, que são as mesmas para todo titular.

## O que este diretório NÃO é

Não é a licença do Hefesto. O código próprio do projeto é **MIT**, e o texto
está no `LICENSE` da raiz — sozinho, sem nada antes dele, por decisão dela de
07/08/2026 (ver `NOTICE`, seção "ESCOPO DESTE ARQUIVO").

Não é a lista das dependências Python. Elas não são vendorizadas: quem as
instala é o pip ou o gerenciador de pacotes da distribuição, e cada uma chega
com o seu próprio `dist-info` e o seu próprio texto de licença. Estão
**declaradas** no `NOTICE`, com a licença lida dos metadados instalados, mas os
textos delas não moram aqui porque não somos nós que as redistribuímos — com uma
exceção nomeada no `NOTICE`: o bundle Flatpak embute as dependências dentro de
`/app`, e nesse caso é o pip que leva o texto de cada uma junto.

## Onde estes textos viajam

Os cinco alvos de empacotamento que carregam `assets/dkms/` carregam este
diretório junto. Quem cobra a simetria é
`tests/unit/test_cr05_licencas_de_terceiros_viajam.py` — arquivo novo neste
diretório sem linha correspondente nos alvos reprova a suíte.

| alvo | como este diretório entra |
|---|---|
| sdist `.tar.gz` | automático: o `hatchling` inclui o que está versionado |
| tarball da tag | automático: `git archive` inclui o que está versionado |
| `.deb` | `scripts/build_deb.sh` |
| `.flatpak` | `flatpak/br.andrefarias.Hefesto.yml` |
| Arch | `packaging/arch/PKGBUILD` |
| Fedora | `packaging/fedora/hefesto-dualsense4unix.spec` |
| **a instalação nativa** (`./install.sh`) | `scripts/dkms_lib.sh` — copia para `/usr/src/<pkg>-<ver>/LICENSES/` |
| **o helper dos pacotes** (`scripts/install-host-udev.sh`) | idem: os dois chamam a mesma `dkms_install_patched_module` |

### Nota datada — 07/08/2026: as duas últimas linhas entraram depois

Esta tabela nasceu com **seis** linhas, e elas estavam certas para a pergunta
que a CR-05 fazia: *quais artefatos PUBLICADOS carregam os fontes GPL*. As duas
últimas respondem outra pergunta, que ficou sem dono no mesmo dia: **quais
caminhos põem os fontes GPL no disco de uma máquina.** São os dois
instaladores, e nenhum dos dois levava o texto junto — `grep -rn LICENSES
install.sh scripts/*.sh` devolvia zero. GRAU: **MEDIDO**.

Quem cobra estas duas é `tests/unit/test_licenca_viaja_com_o_fonte_dkms.py`, e
ele morde por EXECUÇÃO da biblioteca, não por busca de trecho. O motivo de ser
outro arquivo, e não mais um caso no
`test_cr05_licencas_de_terceiros_viajam.py`: aquele lê texto de empacotador;
este roda `bash` com raízes em `tmp` e confere o arquivo que aparece no destino.

Não carregam, e está certo: o wheel e o AppImage não levam `assets/dkms/`, então
não têm o que licenciar aqui.
