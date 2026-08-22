# ADR-021: verbosidade tem custo medido, e fato errado sai de todos os lugares

**Status:** aceito · **Data:** 2026-08-21
**Decisão de:** ela, textual, em 21/08/2026

## Contexto

O `CLAUDE.md` já carrega, desde 11/08/2026, a regra de que **fato errado se
substitui** em vez de ganhar lápide ao lado do certo. Ela nasceu de uma pergunta
dela: *"substituir pela info certa não seria melhor? Seria menos texto pros
agentes lerem e pros devs também."*

Duas coisas mudaram desde então e pedem que a regra saia do `CLAUDE.md`:

1. **O `CLAUDE.md` não é versionado.** Está em `.gitignore:90`, e o
   `anonymity-check.yml` **reprova** se ele entrar na árvore. Ou seja: a regra
   mais citada da casa vive só na máquina de quem a escreveu. Quem clona o
   repositório não a recebe.
2. **A correção pela metade continuou acontecendo.** Substituir onde se notou,
   e não onde aparece, deixa as duas versões vivas — que é exatamente o defeito
   que a regra existe para matar.

## Decisão

Ela, em 21/08/2026, literal:

> *"vamos deixar o projeto menos verboso. provou que uma info tá errada,
> substituímos ela pela certa em todos os lugares. a ideia é que o dev não morra
> no caminho ou que a IA não chegue a um milhão de tokens só de ler um único
> script ou documento."*

Disso saem três regras:

**1. Fato errado sai de TODOS os lugares onde aparece.** Não só de onde foi
notado. Antes de fechar a correção, varra a árvore pelo valor antigo.

**2. Verbosidade é custo, não zelo.** Em atenção de quem lê e em contexto de
quem processa. Vale para código, documento de sprint, comentário e **mensagem de
commit**.

**3. Na dúvida entre repetir e referenciar, referencie.** Na dúvida entre
guardar e cortar, guarde — errar para o lado de guardar continua reversível.

## O que NÃO muda

O teste que separa decisão medida de número errado continua valendo: *se apagar
isto faria alguém repetir um trabalho ou pagar um custo já pago?* Se sim, é
decisão medida e leva data. Se não, sai.

Esta ADR não autoriza apagar história. Autoriza **não repeti-la** em cinco
lugares.

## Consequências

- A regra passa a viver em `.github/CONTRIBUTING.md`, que é versionado. O
  `CLAUDE.md` continua sendo o atalho de quem trabalha aqui, mas deixa de ser a
  única fonte.
- Documento longo não é mais sinal de cuidado. Um índice de sprint que ninguém
  termina de ler não orienta ninguém.
- Correção de fato errado passa a ter uma prova barata: `grep` pelo valor antigo
  na árvore inteira, e o resultado tem de ser vazio ou só histórico datado.
