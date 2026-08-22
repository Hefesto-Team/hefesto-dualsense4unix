# As cores do plástico do DualSense

**O que é.** O DualSense guarda a cor do próprio plástico num código de dois
dígitos, lido do serial de fábrica. A tabela código → **nome** já existe em
`scripts/ensaios/cor_do_plastico.py` (dicionário `CORES`, com três fontes
independentes). Este documento acrescenta o que faltava: o **tom**, para a
interface pintar a borda do card do controle. Levantado em 21-22/08/2026.

**Plástico não é lightbar.** A tabela abaixo é do **plástico físico** —
propriedade do aparelho, lida do hardware, imutável, e serve só para identificar
qual controle é qual. A **cor da lightbar** é outra coisa, continua configurável
pela pessoa, e vive em `core/led_control.py` (`_PLAYER_SLOT_COLORS`). Nada aqui
a altera, e nenhum RGB de uma serve de fonte para a outra.

**A decisão dela (21/08/2026):** o padrão é leitura automática (pelo cabo hoje,
pelo rádio quando a ponte existir), e **a pessoa pode escolher a cor** — a
escolha dela vence a tabela. Isso importa porque, medido, quase toda linha
abaixo é aproximada.

## A régua de confiança

| Grau | Significa |
|---|---|
| `oficial` | valor publicado pela Sony. **Zero linhas** — a Sony não publica hex, RGB nem Pantone de plástico. |
| `medido` | alguém pôs o aparelho na mesa e leu a cor. **Uma linha.** |
| `consenso` | fontes independentes concordam no valor. **Zero linhas.** |
| `amostrado` | pixel colhido de foto oficial da Sony. **Zero linhas** — ver "o que falta". |
| `aproximado` | derivado do **nome** ou da **descrição**, não do aparelho. Chute informado, e está escrito. |

## A tabela

| Código | Nome | Hex | Fonte | Confiança |
|---|---|---|---|---|
| `00` | White | `#EDEEF0` | aproximação do branco levemente frio das fotos de produto | `aproximado` |
| `01` | Midnight Black | `#00040D` | [color-name.com/midnight-black](https://www.color-name.com/midnight-black.color) — nome genérico | `aproximado` |
| `02` | Cosmic Red | `#DA244B` | [color-name.com/cosmic-red](https://www.color-name.com/cosmic-red.color) — nome genérico | `aproximado` |
| `03` | Nova Pink | `#EE7EA6` | aproximação da descrição ("lado rosa-choque do espectro") — [ComicBook](https://comicbook.com/gaming/news/ps5-controller-colors-nova-pink-starlight-blue-galactic-purple/) | `aproximado` |
| `04` | Galactic Purple | `#5F4B9B` | aproximação da descrição ("roxo cósmico profundo") — [PS5 Home](https://ps5home.com/all-dualsense-ps5-controller-colours-guide/) | `aproximado` |
| `05` | Starlight Blue | `#B5CED4` | **medição dela**, 21/08/2026 | `medido` |
| `06` | Grey Camouflage | `#7F8479` | aproximação do cinza de base; **é padrão camuflado, não cor única** | `aproximado` |
| `07` | Volcanic Red | `#8C2B2E` | aproximação da Deep Earth ("vermelho vulcânico, acabamento metálico") — [PlayStation.Blog](https://blog.playstation.com/2023/09/14/introducing-the-deep-earth-collection-a-new-metallic-colorway-for-ps5-accessories-available-starting-later-this-year/) | `aproximado` |
| `08` | Sterling Silver | `#A8ADB3` | aproximação da Deep Earth (metálico); o nome genérico `#E2E5E6` é claro demais para este plástico | `aproximado` |
| `09` | Cobalt Blue | `#2B4C7E` | aproximação da Deep Earth (metálico); o nome genérico `#0047AB` é saturado demais para este plástico | `aproximado` |
| `10` | Chroma Teal | `#1E8E82` | aproximação da descrição oficial ("tons iridescentes de verde") — [PlayStation.Blog](https://blog.playstation.com/2024/09/24/first-look-at-the-chroma-collection-an-all-new-iridescent-line-of-ps5-accessories-available-to-pre-order-this-october/) | `aproximado` |
| `11` | Chroma Indigo | `#3B3E8C` | aproximação da descrição oficial ("azuis profundos e roxos vivos") | `aproximado` |
| `12` | Chroma Pearl | `#E9DEDC` | aproximação da descrição oficial ("rosas e cremes, brilho perolado") | `aproximado` |
| `30` | 30th Anniversary | `#C6C2B6` | aproximação do cinza do PlayStation original | `aproximado` |
| `Z1` | God of War Ragnarok | `#D9DEE3` | aproximação; base branco-acinzentada com runas azuis | `aproximado` |
| `Z2` | Spider-Man 2 | `#A8232B` | aproximação; vermelho e preto | `aproximado` |
| `Z3` | Astro Bot | `#E7EAEE` | aproximação; base branca com acentos azuis | `aproximado` |
| `Z4` | Fortnite | `#DDD8EC` | aproximação; base clara com roxo e azul | `aproximado` |
| `Z6` | The Last of Us | `#C3C6C2` | aproximação; cinza-claro | `aproximado` |
| `ZA` | God of War 20th Anniversary | `#CFCAC2` | aproximação da descrição oficial ("pele coberta de cinzas de Kratos", faixa vermelha) — [PlayStation.Blog](https://blog.playstation.com/2025/09/24/celebrate-kratos-legacy-with-the-dualsense-wireless-controller-god-of-war-20th-anniversary-limited-edition/) | `aproximado` |
| `ZB` | Icon Blue Limited Edition | `#1F4E9C` | aproximação; azul PlayStation | `aproximado` |

**20 das 21 linhas são `aproximado`.** Só a `05` foi medida.

## A conferência do `#B5CED4`

Ela mediu o controle dela e informou `#B5CED4`. Duas bases de nomes de cor
publicam, para o nome "Starlight Blue", valores praticamente idênticos:
`#B5CED3` ([color-name.com](https://www.color-name.com/starlight-blue.color)) e
`#B5CED4` (CrispEdge). A divergência é **1 unidade no canal azul** — abaixo do
limiar de percepção, e abaixo do ruído de qualquer amostragem de foto.

**Ressalva honesta:** essa concordância **não é confirmação independente**. As
duas bases publicam o nome genérico "Starlight Blue", sem qualquer menção ao
DualSense; se o valor dela veio de uma tabela dessa família, as duas fontes têm
a mesma ancestralidade e concordar não prova nada sobre o plástico. O valor dela
fica como está de qualquer forma — a observação dela sobre o aparelho é fonte
primária nesta casa.

## Ressalvas por linha

- **`10`, `11`, `12` (coleção Chroma) são iridescentes por projeto.** A Sony
  descreve mudança de cor conforme o ângulo. Um hex único é, ali, uma média
  arbitrária.
- **`06` é padrão camuflado**, com várias cores num mesmo plástico.
- **`07`, `08`, `09` (Deep Earth) são metálicos**: o brilho varia mais com a
  iluminação do que a cor de base.
- **`Z1` a `ZB` e `30` são artes multicoloridas.** O hex da tabela é a cor
  dominante do corpo, não a arte.
- Em todas essas, a escolha manual da pessoa vale mais que a tabela.

## O que falta, para quem continuar

O caminho para tirar 20 linhas de `aproximado` é o que ela pediu: **amostrar
pixel de foto oficial da Sony**. Não foi feito aqui porque o interpretador deste
ambiente não tem rede (`curl` falha na conexão), então baixar e amostrar imagem
foi impossível — o que se pôde consultar veio de busca e leitura de página. Duas
fontes de foto oficial que servem: as páginas de produto da PlayStation Direct e
as artes dos posts da PlayStation.Blog citados acima.

Ao amostrar, colher da **face frontal** (a parte que a pessoa reconhece), e não
das empunhaduras — que em quase toda cor são de tom diferente do corpo.
