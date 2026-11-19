# horys-pixel

Pixel art 2D top-down **constante** a partir de uma referência: a arte parada que você aprova vira o gabarito, e o
Blender anima o modelo 3D ajustado a ela nas 8 direções, com a mesma escala, câmera, luz e paleta em todo asset do
jogo.

- **Como usar:** [comousar.md](comousar.md)
- **Como a imagem do gerador tem que vir:** [prompt.md](prompt.md)
- **Contrato do jogo** (escala, câmera, luz, portões): [jogo.json](jogo.json)
- **Exemplo completo de asset:** [assets/bonequinho](assets/bonequinho)

```
src/horys_pixel/
  leitura.py     imagem do gerador -> arte parada 1x (grade da própria imagem, detalhe preservado, guarda de altura)
  paleta.py      famílias com rampa de 2–3 tons + tinta
  gabarito.py    render parado do 3D x arte aprovada (silhueta, materiais, altura)
  blender/       dentro.py roda no Blender: câmera do jogo, toon pela paleta, rig por pivôs, ações procedurais
  pos.py         paleta travada, pixel solto, anticintilação, contorno, folhas, .aseprite
  portoes.py     medidas que bloqueiam a entrega
  fluxo.py       as etapas em ordem, cada uma exige a aprovação da anterior
  visor/         página local só para ver (horys visor)
  cli.py         horys novo | prompt | ler | paleta | aprovar | inspecionar | gabarito | animar | exportar | visor | estado
```

Licença MIT.
