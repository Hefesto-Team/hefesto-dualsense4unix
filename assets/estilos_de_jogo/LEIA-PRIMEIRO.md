# Estilo de Jogo — receitas, não perfis

**Decisão dela, 06/09/2026:** *"os perfis que voltaram não fazem sentido. ação,
aventura, corrida. Isso não é perfil, isso é estilo de jogo."*

Os oito arquivos desta pasta vieram de `assets/profiles_default/` e **não são
semeados**. Ninguém os copia para `~/.config/.../profiles/`; nenhuma tela os
lista. Eles são o dado bruto — gatilho, vibração e luz de cada estilo — que o
**motor de Estilo de Jogo** vai ler quando for construído (decisão 8 de
03/09/2026, sprint posterior).

**O único leitor de runtime hoje** é `profiles/loader.py`, e ele lê **para
comparar**: `migrar_generos_para_estilos_de_jogo` só tira da lista dela um
gênero já semeado que ainda seja idêntico a este arquivo. Um que ela editou é
perfil dela e fica.

**Se você mudar um destes arquivos**, essa comparação passa a dizer "ela
editou" para todo mundo que tem a versão anterior no disco, e os oito ficam na
lista para sempre. Eles estão congelados até o motor existir.

O formato ainda é o de perfil (`profiles/schema.py`) porque é o que a migração
compara. Quem escrever o motor decide se ele continua sendo.
