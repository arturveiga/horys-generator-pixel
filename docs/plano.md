# Plano: animação por modelo 3D (recomeço em 2026-11-11)

O rig 2D de partes (~55%) e o SpriteKiln puro (~46%) não deram animação consistente no boss macaco-golem.
O plano recomeça do zero com outra fonte de movimento:

```
modelo 3D low-poly → câmera ortográfica fixa 3/4 (30–35°) → pixel art 2D → motor de sequência do Horys → spritesheet Godot 4
```

O modelo 3D garante volume, escala e posição iguais em todos os quadros. O Horys só trata o que sai do render
(paleta, alpha, limpeza, medição); não redesenha forma por script.

## Custo zero (obrigatório)

- Só ferramentas grátis ou open-source, rodando local.
- Nada de API paga, crédito com cartão ou assinatura (PixelLab, Retro Diffusion e afins ficam de fora).
- Checar a licença antes de adotar qualquer dependência; registrar em [decisoes.md](decisoes.md).
- Download de terceiros só com autorização explícita do Artur.

## Alvo do primeiro teste

- Boss macaco-golem, ~198 px de altura numa tela de 256×256, pivô no centro dos pés.
- ≤ 16 cores (subpaleta única do boss), contorno de 1 px.
- `idle` com 4 quadros; `walk` com 8 quadros a ~8 fps.
- Vista de frente primeiro; outras direções só depois que a frente passar.

## Experimento A: Blender

Blender (GPL, app externo) com câmera ortográfica fixa, luz fixa e render em resolução baixa.

- **A1:** add-on Pixel Art Rendering (Lucas Roedel).
- **A2:** PixelatorPlus.
- **A3:** só recursos nativos (Eevee, câmera ortográfica, resolução baixa, filtro *closest*, material toon).

Para cada variante: mesmo modelo, mesma câmera, mesma animação; checar licença do add-on antes de instalar.

## Experimento B: Blockbench + BlockBenchMCP

Modelo low-poly em cubos no Blockbench, animado e exportado em quadros pela mesma câmera fixa.
O BlockBenchMCP é GPL: **fica externo**, usado como ferramenta, nunca copiado nem vendorizado no núcleo do Horys.

## Regras de integração

- Escala comum a todos os quadros e animações; **nada de normalização por quadro**.
- Não apagar quique nem agachamento: o deslocamento vertical do corpo é parte do movimento.
- Paleta única do boss para todos os quadros.
- Não colar decalque estático em peça que gira (o crânio ou a placa girando com decalque fixo quebra o volume).
- Preservar o brilho dos olhos (âmbar) em todos os quadros; a limpeza protege essas cores.
- Limpeza leve: zerar órfãos e alpha parcial; não redesenhar silhueta.

## Validação objetiva

Toda sequência passa por medição automática antes do revisor:

- mesmo canvas em todos os quadros;
- alpha binário (0 ou 255);
- todas as cores dentro da paleta;
- câmera fixa (fundo, chão e pivô no mesmo lugar);
- sem deriva horizontal no `idle` (o centro de massa não anda);
- sem cintilação (pixel que acende e apaga entre quadros vizinhos sem motivo);
- sem quadros idênticos dentro do ciclo;
- o loop fecha (último quadro emenda no primeiro).

O módulo `src/horys_pixel/sequencia/validar.py` e o preset `render3d` estão sendo implementados em paralelo.
Depois da medição, o revisor (`horys-pixel-liso-revisor`) segue sendo a régua de aceitação (≥ 80%, sem grave).

## Fases

### 1. Auditoria
- [ ] Listar o que o Horys já faz e serve ao novo fluxo (`horys_sequencia`, converter, limpar, portão, exportar).
- [ ] Listar ferramentas instaladas (Blender, Blockbench) e versões; checar licenças.
- [ ] Definir câmera, luz e escala comuns (documentar os números aqui).

### 2. Experimento A (Blender)
- [ ] Modelo low-poly do golem (crânio de frente, pernas em A) com rig simples de ossos.
- [ ] `idle` 4 quadros e `walk` 8 quadros na câmera fixa.
- [ ] Render em A1, A2 e A3; validação objetiva e revisor em cada um.

### 3. Experimento B (Blockbench)
- [ ] Mesmo golem em cubos, mesmas animações, mesma câmera.
- [ ] Exportar quadros, validação objetiva e revisor.

### 4. Comparação
- [ ] Tabela A1 × A2 × A3 × B: nota do revisor, falhas da validação, tempo de produção, editabilidade.
- [ ] Escolher um caminho e registrar em [decisoes.md](decisoes.md).

### 5. Integração mínima
- [ ] Preset `render3d` no motor de sequência lendo os quadros do caminho escolhido.
- [ ] Spritesheet + JSON para Godot 4 (tela 256×256, pivô nos pés, fps por animação).
- [ ] Testar no jogo um `idle` e um `walk`.

## Regras finais

- Não gastar dinheiro em nada sem o sim do Artur.
- Não commitar sem autorização.
- Não esconder resultado ruim: nota e falhas vão para o relatório como saíram.
- Preservar os editáveis (`.blend`, `.bbmodel`, `.aseprite`) junto de cada entrega.

Lições anteriores: [aprendizados-boss.md](aprendizados-boss.md).
