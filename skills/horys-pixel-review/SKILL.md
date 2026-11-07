---
name: horys-pixel-review
description: Revisa pixel art como um diretor de arte exigente — sprites, animações, tiles, ícones e personagens, aberto no Aseprite ou em PNG. Mede (paleta, alfa, pixels órfãos, contorno dobrado, degraus irregulares, simetria, linha dos pés e altura entre quadros e vistas, quadros parados), marca cada problema na camada 'revisao' do Aseprite e faz a revisão visual com as boas práticas do estilo. Também mede "IA slop" em telas e conceitos gerados. Use sempre que pedirem para revisar, avaliar, criticar ou aprovar uma arte em pixel, quando disserem que está "torto", "feio", "estranho", "crocante" ou "com cara de IA", antes de entregar qualquer sprite novo e ao comparar versões — mesmo sem dizer "revisão".
---

# horys-pixel-review (revisar)

Ferramentas MCP `horys_*`. As regras vêm do estilo do projeto (`horys_estilos(nome)` → KB): leia
`estilo/estilo.md`, a técnica do tipo de asset (`tecnicas/...`) e `tecnicas/checklist.md` antes de julgar. Não
copie as notas para cá.

## Passos
1. **Contexto.** Jogo e estilo, tipo de asset, vista, tamanho no jogo, quadros e tags (`horys_status`), e com o que
   precisa combinar (assets aprovados vizinhos; `horys_gosto_consultar` mostra o que o usuário já recusou).
2. **Medir.**
   - Sprite aberto no Aseprite: `horys_medir_arquivo(estilo)` (sem `caminhos`, mede o composto de todos os quadros).
   - PNGs: `horys_medir_arquivo(caminhos: [...], paleta|estilo, fundo: hex do chão, quadros: N, vista)`. Vários PNGs
     de uma vez comparam altura e linha dos pés entre vistas.
   - Tela, conceito ou imagem gerada: `mockup: true` (cores únicas, vizinhos quase iguais, grade de pixel).
   - Asset do fluxo horys: o `horys_portao` já mede tudo (veja `_checagem.txt` e `medidas/`).
3. **Olhar.** `horys_ver(critica: true)` (cor, cinza, silhueta, 1×) e `horys_ver(rect)` para detalhes;
   `horys_regua` lado a lado. Os números apontam onde olhar; não decidem sozinhos (um "órfão" pode ser o brilho do
   olho). Confira:
   - silhueta numa cor só e leitura em 1× sobre o chão real;
   - rosto: olhos do mesmo tamanho e altura, brilho do mesmo lado, boca centrada;
   - cabelo em mechas e massas, não fios soltos; luz numa faixa;
   - clusters intencionais, sem ruído; tons por material conforme o estilo; contorno conforme o estilo;
   - luz do mesmo lado em todas as partes; partes de trás mais escuras;
   - animação: pés estáveis, volume e altura constantes, nada pulando, nenhum quadro parado num movimento contínuo;
   - entre vistas: mesma altura, linha dos pés, cores e design;
   - critérios de rejeição do jogo.
4. **Marcar.** `horys_marcar(quadro, pontos, retangulos)` em cada problema, para o usuário ver no Aseprite.
5. **Relatar** no formato abaixo (sem terminal: `horys_pedido_atualizar(etapa: 'concluido', texto: relatório)`).
   Para cada problema: onde (quadro e coordenada), qual regra e qual correção concreta (que pixel vira o quê).
6. **Corrigir** só se o usuário pedir (`horys_perguntar` "quer que eu corrija?"). Depois, meça de novo e compare.

## O que costuma deixar a arte "torta"
- Degraus irregulares em curvas e diagonais (1-2-1, 2-1-2): a borda treme.
- Contorno grosso em degrau (pixel duplo fora da quina).
- Rosto assimétrico; cabeça fora do eixo; tronco inclinado sem intenção.
- Altura, pés ou centro variando entre quadros ou vistas.
- Ruído: pixels soltos, manchinhas de 1–2 px dentro de área chapada.
- Contorno "perdido" dentro de uma massa; cores quase iguais lado a lado; degradê; pillow shading.

## Sinais de "IA slop"
Milhares de cores, vizinhos quase iguais, nenhuma grade de pixel fixa, detalhe que não descreve forma, densidades
misturadas. Pixel art de jogo de verdade fica entre 16 e 64 cores com grade única. Conceito gerado serve de
referência; o asset final é limpo à mão numa grade única com paleta fechada (skill horys-pixel).

## Formato do relatório
```
Asset: <nome> (<arquivo>), <vista/quadros>
Medição: <cores, alfa, fora da paleta, órfãos, contorno dobrado, degraus, assimetria, pés/altura>
Bloqueia: <itens que violam critérios de rejeição, com onde e como corrigir>
Corrigir: <problemas reais de leitura ou consistência>
Polir: <ajustes finos opcionais>
```
