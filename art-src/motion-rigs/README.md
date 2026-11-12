# Motion rigs

Biblioteca de referências de movimento fornecida pelo Artur. Os GIFs são dados de pose: as cores identificam
partes do corpo; texto, moldura, fundo e estilo visual não devem passar para a arte final.

## Contrato semântico

- cabeça: ciano
- torso: laranja
- braço esquerdo: verde
- braço direito: roxo
- perna esquerda: amarelo
- perna direita: vermelho
- arma, golpe ou efeito: rosa

O rig decide pose, oclusão, timing e amplitude. A régua de identidade do personagem decide desenho,
paleta, roupa e acabamento. Nunca redesenhar a roupa a partir do rig.

## Fontes preservadas

### Direcionais/top-down

1. `source/01-attack-n.gif`
2. `source/02-death-e.gif`
3. `source/03-roll-w.gif`
4. `source/04-run-nw.gif`
5. `source/05-walk-nw.gif`
6. `source/06-idle-nw.gif`

Esses exemplos não cobrem as oito direções. Direções ausentes são produzidas pelo proxy 3D e
comparadas com as vistas aprovadas do personagem.

### Combate e armas

7. `source/07-katana-run.gif`
8. `source/08-katana-walk.gif`
9. `source/09-dash.gif`
10. `source/10-katana-attacks.gif`
11. `source/11-air-attacks.gif`
12. `source/12-katana-run-attacks.gif`
13. `source/13-shoot-2h.gif`
14. `source/14-running-aiming.gif`
15. `source/15-running-shooting.gif`
18. `source/18-punch-jab.gif`
19. `source/19-stab.gif`
20. `source/20-sword-attack.gif`
41. `source/41-sword-run.gif`
42. `source/42-sword-idle.gif`

### Locomoção e estados

16. `source/16-ladder-front.gif`
17. `source/17-ladder-side.gif`
21. `source/21-run.gif`
22. `source/22-walk.gif`
23. `source/23-idle.gif`
24. `source/24-hurt.gif`
25. `source/25-death.gif`
26. `source/26-crouch-walk.gif`
27. `source/27-crouch-idle.gif`
28. `source/28-push.gif`
29. `source/29-push-pull-idle.gif`
30. `source/30-pull.gif`
31. `source/31-roll.gif`
32. `source/32-slide.gif`
33. `source/33-air-spin.gif`
34. `source/34-jump-up.gif`
35. `source/35-land.gif`
36. `source/36-ledge-grab-climb.gif`
37. `source/37-wall-slide-a.gif`
38. `source/38-wall-slide-b.gif`
39. `source/39-wall-land-a.gif`
40. `source/40-wall-land-b.gif`

## Proxy top-down gerado

Fonte: `art/specs/characters/pirata_motion_proxy/pirata_motion_proxy.yaml`.

- `generated/pirata-proxy-rotation-ruler.png`: pose neutra em `s,se,e,ne,n,nw,w,sw`.
- `generated/pirata-proxy-rotation-8dir.gif`: inspeção da rotação.
- `generated/pirata-proxy-walk-contact.png`: oito direções por quatro poses.
- `generated/pirata-proxy-walk-8dir.gif`: inspeção animada.

## Ordem de produção

1. Aprovar as oito vistas neutras da arte.
2. Fixar identidade da cabeça, lapelas, botões, cinto e paleta por direção, sem congelar pixels do torso.
3. Transferir as quatro poses do proxy para cada direção.
4. Permitir contrarrotação e quique de 1 px no torso; braços, pernas, abas e arma recebem a amplitude principal.
5. Normalizar pivot, ground line e canvas.
6. Medir estabilidade dos detalhes internos. O desenho deve persistir, mas o alvo não é zero pixels alterados.

