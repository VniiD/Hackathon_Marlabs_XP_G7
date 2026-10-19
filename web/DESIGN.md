# Design do frontend

Decisões de interface do projeto. A referência é a XP Inc. (base neutra e acento turquesa);
cores, fonte e componentes abaixo são propostas nossas, não o design system oficial da XP.

## Jornadas

- **Entrada**: "Quem está acessando?", com perfis prontos (uma assessora e os clientes) e
  "Criar conta". Um clique entra, sem e-mail nem senha, para a demo não perder tempo.
- **Cliente**: no primeiro acesso cai na análise de perfil, uma pergunta por vez. Cada
  pergunta mostra os tópicos a abordar; o cliente grava um áudio (transcrito pela AssemblyAI)
  ou escreve, e os tópicos vão sendo marcados conforme aparecem na resposta. Tudo é salvo
  sozinho no backend; "Limpar resposta" apaga o texto para gravar de novo. As 3 obrigatórias
  têm uma escolha rápida que define o perfil e libera a plataforma; as outras 4 podem ficar
  para depois. Dentro: patrimônio unificado, reunião, pedido de alteração e copiloto.
- **Assessor**: painel com o patrimônio sob assessoria por classe e por ativo, tipos de
  cliente, clientes por criticidade, agenda, pedidos e notícias com os clientes expostos.
  Clicar em um cliente abre a tela de detalhe, que inclui as respostas da análise de perfil.
  As anotações pessoais do assessor (para puxar assunto) ficam numa gaveta recolhida na borda
  direita, atrás da aba "Contexto pessoal", fora do corpo da página que o cliente pode ver na
  tela. Cada anotação é um post-it com texto e data, que pode ser editado ou apagado.

## Tokens (em `src/styles.css`)

| Papel | Valor |
|---|---|
| Fundo, superfície, superfície elevada | `#080B0D`, `#11171A`, `#1A2326` |
| Texto principal, secundário, apagado | `#F5F7F7`, `#9DA8AA`, `#7A878A` |
| Acento (ação e seleção) | `#00A99D`, com texto escuro `#03201D` por cima |
| Classes de ativo | `#3987E5` renda fixa, `#D95926` ações, `#9085E9` fundos, `#C98500` cripto, `#D55181` outros |
| Estados | `#F0787A` crítico/queda, `#E3B341` atenção, `#5FCB9A` positivo/alta |

- Fonte: IBM Plex Sans (400, 500, 600), empacotada no build para funcionar sem internet.
- O turquesa marca só ação e seleção. Classes de ativo têm paleta própria, com ordem fixa.
- Criticidade e sentimento usam forma e texto além da cor (triângulo, losango, círculo).
- Valores em reais usam algarismos tabulares e ficam alinhados à direita nas tabelas.

## Elemento próprio

A **faixa de composição**: uma barra 100% com legenda de valores exatos. Aparece no painel do
assessor (onde filtra a tabela de ativos), na carteira do cliente e no detalhe do cliente.

## Movimento

Animações de entrada só nos perfis da tela inicial, nas mensagens do copiloto e no resultado
do perfil; o ponto vermelho pulsa enquanto grava. Tudo é desligado com `prefers-reduced-motion`.

## Pendências

- O nome do produto é `XP.inc` (`APP_NAME` em `src/lib.ts`).
- Não há tema claro.
- Os tópicos são marcados por palavras-chave (`src/questions.ts`), o que erra em respostas
  fora do esperado. O ideal é o backend extrair os dados da resposta com o Gemini.
