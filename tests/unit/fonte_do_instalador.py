"""A fonte ÚNICA que os portões leem quando perguntam "o instalador faz X?".

POR QUE ESTE ARQUIVO EXISTE (31/08/2026)
========================================
As onze curas de HOST mudaram de casa. Moravam no `install.sh` — o
`_render_broker_units` nas linhas 873-893 e as dez `*_host` nas 989-1677 — e
passaram para `scripts/lib/camada_de_maquina.sh`, que os DOIS instaladores
sourceiam: o `install.sh` numa linha só, e o `install-dev.sh
--camada-de-maquina`. O motivo, com data, está no cabeçalho da lib: ela
desinstalou o Hefesto estável e ficou só com o de desenvolvimento, e o app de
dev dependia do estável para essa camada — parou de funcionar em silêncio.

**Nenhuma função mudou de comportamento.** São as mesmas, byte por byte. O que
mudou foi o ARQUIVO em que o texto delas está.

E ISSO SOZINHO REPROVOU 42 TESTES, com 4 erros, em 11 arquivos. Nenhum deles
achou defeito nenhum: todos liam `install.sh` com `read_text()` e procuravam um
trecho que agora mora ao lado. Um portão que reprova por olhar no arquivo errado
é pior que portão nenhum — o nenhum não dá susto, e susto repetido é o que faz
alguém desligar a régua.

O QUE ESTE ARQUIVO RESOLVE, e é o motivo de ser UM SÓ
----------------------------------------------------
1. **Uma cura de host pode mudar de arquivo de novo.** Quando mudar, o conserto
   é aqui, numa linha — não em onze arquivos, cada um com a sua decisão.
2. **Ninguém precisa decidir caso a caso em qual arquivo procurar.** A pergunta
   que os portões fazem nunca foi "está no `install.sh`?"; sempre foi "o
   instalador faz isto?". Essa pergunta tem UMA resposta, e ela é o texto dos
   dois arquivos juntos.

A ORDEM É `install.sh` PRIMEIRO, e ela não é arbitrária
-------------------------------------------------------
Muitos portões usam `.index()` para medir POSIÇÃO — "o render vem antes de
instalar o binário", "o passo 3h anuncia o BROKER-01". `str.index` devolve a
PRIMEIRA ocorrência: pondo o `install.sh` na frente, todo trecho que já morava
lá continua sendo achado no mesmo lugar relativo, e nenhum veredito de posição
muda por causa da junção. A ordem inversa moveria a âncora de cada um desses
testes para dentro da lib, calada.

O QUE ESTE ARQUIVO **NÃO** É
----------------------------
Não é atalho para afrouxar régua. Ele muda ONDE o teste procura; nunca o que o
teste EXIGE. Um teste que reprova depois de trocar a leitura por esta fonte está
apontando defeito de verdade — e defeito de verdade se relata, não se acomoda.

E ele não serve para tudo: quem precisa do CAMINHO — `.exists()`, `bash -n`,
`subprocess.run([BASH, str(INSTALL), "--help"])` — quer o `Path`, não o texto.
Por isso os dois caminhos estão exportados aqui, e cada portão pega o que
precisa.
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

#: O instalador do app estável. Continua sendo o dono da CERCA (`if [[
#: "${FORMAT}" != "native" ]]`), dos passos numerados e das flags de linha de
#: comando — nada disso mudou de casa.
INSTALL = RAIZ / "install.sh"

#: As onze curas de HOST, desde 31/08/2026. Sourceada pelo `install.sh` e pelo
#: `install-dev.sh --camada-de-maquina`.
CAMADA_DE_MAQUINA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"

#: O instalador do app de dev, que sourceia a mesma lib. Exportado para quem
#: precisar cobrar a paridade entre os dois.
INSTALL_DEV = RAIZ / "install-dev.sh"

#: Os arquivos que, juntos, são "o instalador" para efeito de leitura.
ARQUIVOS = (INSTALL, CAMADA_DE_MAQUINA)

#: A emenda entre os dois textos. É COMENTÁRIO de bash de propósito: os portões
#: que filtram comentários (`_sem_comentarios`) não a enxergam, e os que não
#: filtram só veem texto inerte. Nenhuma busca da casa casa com ela.
SEPARADOR = (
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# ACIMA: install.sh · ABAIXO: scripts/lib/camada_de_maquina.sh\n"
    "# Emendados por tests/unit/fonte_do_instalador.py — leia o docstring de lá.\n"
    "# ---------------------------------------------------------------------------\n"
)


def texto_do_instalador() -> str:
    """O texto do `install.sh` MAIS o da camada de máquina, nesta ordem.

    É o que responde "o instalador faz X?". Não engole arquivo faltando: se um
    dos dois sumir, o `read_text` levanta `FileNotFoundError` e o portão morre
    barulhento. O contrário — devolver `""` — faria todo portão que lê daqui
    passar por vacuidade, que é o pior estado possível para uma régua.
    """
    return SEPARADOR.join(caminho.read_text(encoding="utf-8") for caminho in ARQUIVOS)


def texto_do_install_sh() -> str:
    """Só o `install.sh`.

    Para o portão que mede algo que é do ARQUIVO, não do instalador: a cerca
    dos formatos, a ordem dos passos, o `--help`. Quem usa isto está dizendo
    "a lib não tem nada com essa pergunta" — e é bom que esteja dizendo.
    """
    return INSTALL.read_text(encoding="utf-8")


def texto_da_camada_de_maquina() -> str:
    """Só a lib das curas de HOST."""
    return CAMADA_DE_MAQUINA.read_text(encoding="utf-8")


def existe_o_instalador() -> bool:
    """Os dois arquivos estão no disco?

    Alguns portões guardam a leitura com `.exists()` para não explodir num
    checkout parcial. Como agora são dois arquivos, a guarda também é dupla.
    """
    return all(caminho.exists() for caminho in ARQUIVOS)
