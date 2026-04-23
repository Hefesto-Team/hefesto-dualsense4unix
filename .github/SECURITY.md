# Política de segurança

## Versões suportadas

Apenas a versão estável mais recente recebe correções de segurança. Não há backport para versões anteriores.

| Versão | Suporte |
|--------|---------|
| 2.1.x  | Sim     |
| 2.0.x  | Não     |
| < 2.0  | Não     |

Consulte `CHANGELOG.md` para o estado atual.

---

## Reportando uma vulnerabilidade

**Não abra issue pública** para vulnerabilidades de segurança. Use disclosure responsável por e-mail:

- **Contato:** `andre.dsbf@gmail.com`
- **Assunto sugerido:** `[Hefesto SEC] <resumo curto>`

Inclua no relatório:

1. Descrição da vulnerabilidade e impacto estimado.
2. Passos para reproduzir em árvore limpa (`git checkout main && git pull`).
3. Versão afetada (`hefesto --version`).
4. Distribuição e kernel (`uname -a`).
5. Prova de conceito mínima, se aplicável.
6. Sugestão de mitigação, se houver.

---

## Escopo

### Dentro do escopo

- Escape ou escalação via IPC Unix socket (`$XDG_RUNTIME_DIR/hefesto/hefesto.sock`).
- Injeção via UDP DSX (`127.0.0.1:6969`).
- Abuso do endpoint Prometheus (`127.0.0.1:9090`) quando habilitado.
- Race conditions em `single_instance` que permitam execução de código arbitrário.
- Leitura ou escrita não autorizada de arquivos em `~/.config/hefesto/`.
- Falhas de validação em schemas pydantic que permitam travessia de diretório.
- Regras udev distribuídas (`assets/*.rules`) com permissões excessivas.
- Emulação Xbox 360 via `uinput` com efeito fora do usuário corrente.

### Fora do escopo

- Kernel Linux, pydualsense, GTK, ou outras dependências upstream (reporte direto aos mantenedores).
- Ataques que requerem acesso físico ao hardware além do controle DualSense.
- Negação de serviço via força bruta no socket local (vetor requer execução local já comprometida).
- Questões de privacidade do protocolo Bluetooth da Sony (fechado).

---

## Processo de resposta

1. Acuso recebimento em até 7 dias corridos.
2. Triagem e confirmação em até 14 dias.
3. Correção em branch privada; coordenação de disclosure com o relator.
4. Release de patch com crédito (opcional, conforme preferência do relator).
5. Aviso público via CHANGELOG e GitHub Security Advisory.

Não há programa de recompensa financeira — este é um projeto pessoal sem financiamento.

---

## Chave PGP

Não há chave PGP ativa no momento. Se o relatório exigir canal criptografado, negocie via e-mail inicial claro em quais dados não devem trafegar em texto puro.

---

## Histórico

Nenhum advisory público até esta data. Este documento será atualizado quando houver.

---

*"A forja não revela o ferreiro. Só a espada."*
