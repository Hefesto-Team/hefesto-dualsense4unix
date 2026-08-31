# Divergências declaradas entre `mockup/` e `layout/`

Toda linha aqui é uma diferença **conhecida e justificada** entre o desenho que
ela aprovou e o que o produto renderiza hoje. O `scripts/check_o_desenho_aprovado.py`
lê este arquivo; o que não estiver aqui, ele reprova.

**Formato** — uma seção por arquivo, com data e motivo:

```
## 01-jogar.html
- **DD/MM/AAAA** — o que mudou, e por quê. Quem pediu, se foi ela.
```

Quando ela aprovar o desenho novo, este arquivo é **zerado** pelo `--aprovar`:
as divergências deixam de existir porque a fotografia passou a ser a de agora.

---

<!-- Nenhuma divergência declarada. A fotografia é de 31/08/2026. -->
