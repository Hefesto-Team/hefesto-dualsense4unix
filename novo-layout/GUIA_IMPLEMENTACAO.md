# Guia de Implementação — Hefesto DualSense4Unix (nova identidade)

Guia detalhado para uma IA (ou dev) aplicar a nova identidade visual e os ajustes
de interface no app real. Todos os valores são exatos. A referência visual está em:

- `Paleta Hefesto.dc.html` — sistema de cores completo
- `Telas Hefesto.dc.html` — mockups das 4 abas alteradas (Status, Gatilhos, Perfis, Navegação DSX)
- `assets/hefesto-logo.svg` — logo circular final (512×512, escala livre)

---

## 1. Paleta de cores (tema Drácula)

### 1.1 Cores base — use SEMPRE estas 11, nunca invente cor nova
| Nome         | Hex       | Papel na interface |
|--------------|-----------|--------------------|
| Background   | `#282a36` | Fundo dos painéis/cards |
| Current Line | `#44475a` | Seleção, hover, contorno de campos |
| Foreground   | `#f8f8f2` | Texto principal |
| Comment      | `#6272a4` | Texto secundário, dicas, notas |
| Cyan         | `#8be9fd` | Info, valores numéricos, links |
| Green        | `#50fa7b` | Sucesso, "Aplicar", toggle ligado, status OK |
| Orange       | `#ffb86c` | Atenção, "Importar" |
| Pink         | `#ff79c6` | MARCA, destaque, aba ativa |
| Purple       | `#bd93f9` | Acento primário, estado selecionado |
| Red          | `#ff5555` | Erro, "Remover", falha [FAIL] |
| Yellow       | `#f1fa8c` | Alerta suave (pouco usado) |

### 1.2 Superfícies (níveis de profundidade neutros)
| Token         | Hex       | Uso |
|---------------|-----------|-----|
| App BG        | `#21222c` | Fundo da janela (mais escuro que os painéis) |
| Panel         | `#282a36` | Cards e seções |
| Elevated      | `#2b2d3a` | Trilha de sliders, cabeçalho de tabela, menus |
| Border sutil  | `#343746` | Divisórias entre seções |
| Border forte  | `#44475a` | Contorno de inputs e áreas interativas |
| Texto suave   | `#c8ccda` | Texto de rótulo (entre foreground e comment) |
| Texto mudo    | `#8b8fa8` | Texto de item não selecionado |

### 1.3 Papéis semânticos (cada cor = UM trabalho)
- **Acento primário / seleção** → Purple `#bd93f9`. Estado selecionado = borda `#bd93f9`
  + fundo translúcido `rgba(189,147,249,0.16)` (NÃO usar roxo chapado/sólido).
- **Marca / aba ativa** → Pink `#ff79c6`. Aba ativa: texto `#f8f8f2` + borda inferior 2px `#ff79c6`.
- **Confirmar** → Green `#50fa7b` ("Aplicar", "Ativar", toggle ligado, status saudável).
- **Atenção** → Orange `#ffb86c` ("Importar").
- **Info** → Cyan `#8be9fd` (valores, [INFO]).
- **Perigo** → Red `#ff5555` ("Remover", [FAIL]).

---

## 2. Logo e cabeçalho

- Trocar a logo atual por `assets/hefesto-logo.svg`.
- **Título:** `Hefesto — DualSense4Unix` com cores por trecho:
  - "Hefesto" → `#ff79c6` (rosa)
  - "—" → `#6272a4`
  - "DualSense" → `#f8f8f2`
  - "4" → `#50fa7b` (verde)
  - "Unix" → `#f8f8f2`
- **Subtítulo:** trocar `daemon de gatilhos adaptativos para DualSense`
  por **`Gerenciador DualSense para Linux`** (cor `#6272a4`).

---

## 3. Botões do rodapé global (padrão)
- **Aplicar** → fundo sólido `#50fa7b`, texto `#21222c`.
- **Salvar Perfil** → contorno `#bd93f9`, texto `#bd93f9`, fundo transparente.
- **Importar** → contorno `#ffb86c`, texto `#ffb86c`.
- **Restaurar Default** → contorno `#6272a4`, texto `#8b8fa8`.

Botões de card selecionável: não selecionado = borda `#44475a`, fundo `#21222c`,
texto `#8b8fa8`. Selecionado = borda `#bd93f9`, fundo `rgba(189,147,249,0.16)`,
texto `#f8f8f2`, peso 600.

---

## 4. Aba STATUS (adicionar sensores)

Manter os elementos existentes e ADICIONAR três módulos por controle:

1. **Giroscópio** — 3 eixos (X, Y, Z) como barras horizontais bidirecionais
   (origem no centro). Cores: X=`#ff5555`, Y=`#50fa7b`, Z=`#8be9fd`. Valor em `graus/s`.
2. **Microfone** — medidor de nível (barras verticais) + selo de estado:
   `ATIVO` (fundo `#50fa7b`, texto `#21222c`) ou `MUDO` (fundo `#2b2d3a`, texto `#6272a4`).
3. **Touchpad** — retângulo com contorno `#44475a` mostrando ponto(s) de toque
   (círculo `#8be9fd` com brilho); rótulo "N toque" / "sem toque".

Layout compacto: dois controles lado a lado, cada card com Estado→Bateria/L2/R2→
Analógicos L3/R3→painel de botões→Giroscópio→Microfone+Touchpad. Sem barra de rolagem.

---

## 5. Aba GATILHOS (altura reduzida)

- Reduzir a altura de cada botão de modo para **~1/3 do original** (grid 3 colunas,
  botões ~28–32px de altura, fonte 11px). Selecionado usa o padrão roxo (4.).
- Abaixo do grid: descrição do modo + 4 sliders (Início, Fim, Intensidade início (1-8),
  Intensidade fim (1-8)). **Rótulo do slider em uma linha só** (`white-space:nowrap`,
  largura fixa ~150px) — não deixar "Intensidade início (1-8)" quebrar.
- Botões por gatilho no rodapé do card: "Aplicar em L2/R2" (contorno `#50fa7b`) e
  "Desligar" (contorno `#6272a4`).
- Meta: botões + config + ações cabem sem ativar a barra de rolagem.

---

## 6. Aba PERFIS (remover Detalhes técnicos)

- Manter: tabela "Perfis salvos" (Nome/Prioridade/Quando usar) e "Editor do perfil"
  (Nome, Prioridade, window_class, title_regex, process_name, Modo avançado,
  cards de Modo).
- **REMOVER completamente o bloco "Detalhes técnicos" (o JSON).**
- Cabeçalho de tabela: fundo `#2b2d3a`, texto de coluna `#bd93f9`. Linha selecionada:
  fundo `rgba(189,147,249,0.16)`.
- Ações no rodapé: Novo/Duplicar/Recarregar (contorno `#6272a4`), Remover (contorno
  `#ff5555`), Ativar (contorno `#50fa7b`), Salvar (contorno `#bd93f9`).

---

## 7. Abas MOUSE + TECLADO → unificar em "NAVEGAÇÃO DSX"

- Remover as abas "Mouse" e "Teclado" e criar UMA aba **"Navegação DSX"**.
- Duas colunas lado a lado, sem barra de rolagem:
  - **Coluna Mouse:** toggle "Emular mouse+teclado", texto de aviso, status
    "uinput disponível" (`#50fa7b`), sliders "Velocidade do cursor" e
    "Velocidade da rolagem", bloco "Mapeamento" (todos os mapeamentos atuais),
    nota do rodapé.
  - **Coluna Teclado:** "Atalhos de teclado do perfil ativo", notas de uso,
    tabela Botão do controle → Tecla do teclado (todos os atalhos atuais),
    botões Adicionar (`#50fa7b`) / Remover (`#ff5555`) / Restaurar defaults (`#6272a4`).

---

## 8. Fontes
- Interface/títulos: **Space Grotesk** (500–700).
- Valores, hex, logs, código, tabelas técnicas: **JetBrains Mono**.

---

## 9. Regras gerais
- Nada de roxo chapado/sólido em grandes áreas — usar o padrão borda+fundo translúcido.
- Rosa é exclusivo da marca e da aba ativa (não competir com o roxo).
- Todas as 4 abas alteradas devem caber na janela SEM barra de rolagem.
- Não remover nenhum elemento funcional (exceto "Detalhes técnicos" em Perfis).
