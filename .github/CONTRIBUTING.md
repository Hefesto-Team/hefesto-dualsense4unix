# Contribuindo

Issues e pull requests são bem-vindos. Para uma mudança grande, abra uma issue antes, para combinarmos o caminho.

Tudo no projeto é escrito em português do Brasil, com acentuação: código, comentários, documentação e mensagens de commit.

## Ambiente

```bash
bash scripts/dev_bootstrap.sh              # cria a .venv com as dependências
bash scripts/dev_bootstrap.sh --with-tray  # inclui PyGObject e GTK, para a janela e a bandeja
pip install pre-commit && pre-commit install
```

## Antes de abrir o pull request

```bash
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/hefesto_dualsense4unix
bash scripts/portoes.sh
bash scripts/rodar-a-suite.sh
```

Se a mudança toca o serviço, rode `./run.sh --smoke`, que sobe o serviço por alguns segundos com um controle simulado no cabo (`./run.sh --smoke --bt` simula o Bluetooth). Se toca a janela, anexe um print de antes e de depois.

## O que já se mediu

Antes de mexer num tema, leia o que já se mediu sobre ele em `docs/research/`.
O registro de 27 e 28/09/2026 está em
[docs/research/2026-09-27-e-28/](../docs/research/2026-09-27-e-28/README.md):
o modo e o pad virtual, o som, a háptica pelo rádio, as Conexões, o engasgo, o
CI e a auditoria do produto. Cada documento diz o que se mediu, a causa, o que
se decidiu e o que ficou aberto.

## Regras do projeto

- Um teste tem de reprovar quando a correção que ele protege é arrancada. Antes de entregar, tire a correção, veja o teste falhar e devolva.
- Um fato errado se substitui pelo certo em todos os lugares onde aparece, e não só onde foi notado. Procure o valor antigo na árvore inteira antes de fechar.
- As verificações de `scripts/portoes.sh` só enxergam arquivo que o git conhece: rode-as depois do `git add`.
- O lint usa o comando exato do CI: `ruff check src/ tests/`.
- O `install.sh` nunca roda com `sudo` na frente, porque o `HOME` passaria a ser o do root. Sem terminal interativo, use `./install.sh --yes`.
- Endereço de aparelho, em teste ou documento, só nas faixas fictícias (`aa:bb:cc`, `02:fe:`, `e8:47:3a`), nunca o de um controle de verdade.

## Commits

Uma linha no formato `tipo(escopo): o que muda`. Tipos: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`. Se precisar, um corpo curto com o porquê.

## Dados pessoais

Além do endereço do aparelho, não ponha número de série nem caminho da sua máquina em teste ou documento.

## A língua do produto

O português do Brasil é a língua do Hefesto: é a língua em que o produto está escrito e em que ele é entregue.

O encanamento de tradução existe (`po/`, `scripts/i18n_extract.sh`, `scripts/i18n_compile.sh` e `src/hefesto_dualsense4unix/utils/i18n.py`), mas a maior parte do texto das abas ainda não passa por ele:

<!-- CONTAGEM-GERADA — não edite à mão: scripts/check_o_projeto_e_traduzivel.py --publicar -->
Dos **34** arquivos `.py` de `src/hefesto_dualsense4unix/app/actions/`
— os que escrevem o texto vivo das abas —, **19** escrevem prosa com
acentuação portuguesa fora da função de tradução, e **9** importam essa
função. Quem traduzisse os catálogos inteiros veria o esqueleto fixo mudar
de idioma e o recado da janela continuar em português.

Critério, lido do AST e não de um grep: importa `_` de `hefesto_dualsense4unix.utils.i18n`
ou `gettext`; tem literal com caractere acentuado fora de docstring.
<!-- /CONTAGEM-GERADA -->

Por isso o projeto ainda não pede traduções. Quem mexer em i18n mexe para ligar o encanamento às telas; quando a contagem acima chegar a zero, a tradução passa a alcançar a janela inteira.

Ficam em inglês dentro do português: `lightbar` e `rumble`, os nomes que a Sony dá às peças, e `daemon`, o termo do Unix.

## Dúvidas

Abra uma issue com o modelo «Pergunta».
