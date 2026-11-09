# Feed Científico Cabeça de Dona

Página que junta, todo dia, artigos científicos (PubMed) e notícias de ciência (ScienceDaily) sobre os seus temas, com o resumo de cada estudo direto no cartão.

## O que tem na pasta

| Arquivo | Para que serve |
|---|---|
| `config.json` | Os temas acompanhados e as palavras de busca. É o único arquivo que você precisa mexer para mudar os temas. |
| `buscar_artigos.py` | Busca os artigos novos e salva em `artigos.json`. |
| `artigos.json` | Os artigos já encontrados. É atualizado sozinho. |
| `index.html` + `logo.png` | A página com a identidade do Cabeça de Dona. |
| `.github/workflows/atualizar.yml` | A rotina que atualiza o feed todo dia às 7h depois que ele estiver publicado no GitHub. |
| `abrir.sh` | Abre o feed no seu computador. |

## Abrir no seu computador

No Terminal:

```bash
bash ~/Desktop/feed-cabeca-de-dona/abrir.sh
```

Para só abrir, sem buscar artigos novos:

```bash
bash ~/Desktop/feed-cabeca-de-dona/abrir.sh --so-abrir
```

## Como funciona o resumo

- **Em resumo**: a conclusão do estudo, como os autores escreveram. Quando o resumo não tem uma parte de conclusão, aparecem as duas últimas frases.
- **Resumo completo**: abre o resumo inteiro do artigo, separado por partes (objetivo, métodos, resultados, conclusão).
- **Traduzir**: abre o título e o resumo já traduzidos para o português no Google Tradutor.

## Trocar ou incluir temas

Peça no Claude Code: "inclui o tema X no feed do Cabeça de Dona". Cada tema tem um nome, uma cor e uma busca do PubMed.
