"""Casco visual: o modelo 3D esculpido a partir das vistas aprovadas (frente, lado, costas), na câmera do jogo.

Um bloco de voxels é projetado em cada vista com a MESMA câmera do render (ortográfica, `angulo` do jogo.json,
`px_por_metro`, a figura girada pela direção da vista). Fica só o voxel que cai dentro da figura em todas as vistas.
A arte é registrada em cada vista pela caixa da projeção do próprio casco (centro em x, linha do pé embaixo), em
algumas voltas, até parar de mudar. O resultado é separado em partes (cabeça, tronco, braços, pernas) para o rig.

Nada aqui inventa forma: a forma vem toda da arte. Onde as vistas se contradizem, o casco fica com o volume comum e
a sobra aparece medida em `iou` por vista.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage


def mascara(rgba: np.ndarray) -> np.ndarray:
    return np.asarray(rgba)[..., 3] > 127


def _caixa(m: np.ndarray):
    ys, xs = np.nonzero(m)
    return xs.min(), xs.max() + 1, ys.min(), ys.max() + 1


class Casco:
    def __init__(self, vistas: dict, jogo: dict, sub: int = 2):
        """vistas: {nome: (rgba, angulo_graus)}; sub: voxels por pixel da arte."""
        self.ang = math.radians(float(jogo["angulo"]))
        self.s = 1.0 / float(jogo["px_por_metro"])          # metros por pixel da arte
        self.v = self.s / sub                                # aresta do voxel
        # o pós-render põe 1 px de contorno por fora: o casco é a figura da arte SEM o contorno dela
        fora = jogo.get("contorno", "fora") == "fora"
        self.vistas = {n: (self._sem_contorno(mascara(rgba)) if fora else mascara(rgba), math.radians(float(a)))
                       for n, (rgba, a) in vistas.items()}
        self.rgba = {n: np.asarray(rgba)[..., :3].astype(float) for n, (rgba, _) in vistas.items()}
        self.borda = {n: mascara(rgba) & ~self.vistas[n][0] for n, (rgba, _) in vistas.items()}
        larg = max(m.shape[1] for m, _ in self.vistas.values())
        alt = max(m.shape[0] for m, _ in self.vistas.values())
        meia = 0.75 * larg * self.s
        zmax = 1.15 * alt * self.s / max(0.2, math.cos(self.ang))
        n_xy = int(math.ceil(2 * meia / self.v))
        n_z = int(math.ceil(zmax / self.v))
        self.origem = np.array([-meia, -meia, 0.0])
        i = (np.arange(n_xy) + 0.5) * self.v - meia
        k = (np.arange(n_z) + 0.5) * self.v
        self.X, self.Y, self.Z = np.meshgrid(i, i, k, indexing="ij")
        w0 = -0.5 * larg * self.s * math.sin(self.ang)       # pé da frente um pouco à frente do eixo
        self.reg = {n: [0.0, w0] for n in self.vistas}       # onde caem o centro e a base da arte (u, w), metros
        self.ocup = None

    # ------------------------------------------------------------------ projeção (igual à câmera do jogo)
    def tela(self, th, X=None, Y=None, Z=None):
        X = self.X if X is None else X
        Y = self.Y if Y is None else Y
        Z = self.Z if Z is None else Z
        xr = X * math.cos(th) - Y * math.sin(th)
        yr = X * math.sin(th) + Y * math.cos(th)
        return xr, yr * math.sin(self.ang) + Z * math.cos(self.ang)   # u para a direita, w para cima

    def _pixel(self, nome, u, w):
        m, _ = self.vistas[nome]
        x0, x1, y0, y1 = _caixa(m)
        du, dw = self.reg[nome]
        col = np.floor((u - du) / self.s + (x0 + x1) / 2.0).astype(int)
        lin = np.floor(y1 - (w - dw) / self.s).astype(int)
        return col, lin

    def esculpir(self, voltas: int = 6) -> np.ndarray:
        for _ in range(voltas):
            ocup = np.ones(self.X.shape, bool)
            for nome, (m, th) in self.vistas.items():
                u, w = self.tela(th)
                col, lin = self._pixel(nome, u, w)
                dentro = (col >= 0) & (col < m.shape[1]) & (lin >= 0) & (lin < m.shape[0])
                ok = np.zeros_like(ocup)
                ok[dentro] = m[lin[dentro], col[dentro]]
                ocup &= ok
            ocup = self._maior_peca(ocup)
            if not ocup.any():
                break
            mudou = 0.0
            for nome, (m, th) in self.vistas.items():
                u, w = self.tela(th, self.X[ocup], self.Y[ocup], self.Z[ocup])
                # centro em u e base em w da projeção têm que cair no centro e na base da arte
                novo = [(u.min() + u.max()) / 2.0, w.min() - self.v / 2]
                mudou = max(mudou, abs(novo[0] - self.reg[nome][0]), abs(novo[1] - self.reg[nome][1]))
                self.reg[nome] = novo
            self.ocup = ocup
            if mudou < self.v * 0.5:
                break
        return self.ocup

    @staticmethod
    def _sem_contorno(m):
        e = ndimage.binary_erosion(m, structure=np.ones((3, 3), bool))
        return e if e.sum() > 0.4 * m.sum() else m

    @staticmethod
    def _maior_peca(ocup):
        rot, n = ndimage.label(ocup)
        if n <= 1:
            return ocup
        tam = ndimage.sum(ocup, rot, range(1, n + 1))
        return rot == (1 + int(np.argmax(tam)))

    # ------------------------------------------------------------------ medida: casco projetado x arte
    def silhueta(self, nome) -> np.ndarray:
        m, th = self.vistas[nome]
        out = np.zeros_like(m)
        u, w = self.tela(th, self.X[self.ocup], self.Y[self.ocup], self.Z[self.ocup])
        # amostra os 4 cantos de cada voxel para não deixar furo de amostragem
        for a in (-0.45, 0.45):
            for b in (-0.45, 0.45):
                col, lin = self._pixel(nome, u + a * self.v, w + b * self.v)
                ok = (col >= 0) & (col < m.shape[1]) & (lin >= 0) & (lin < m.shape[0])
                out[lin[ok], col[ok]] = True
        return out

    def iou(self) -> dict:
        res = {}
        for nome, (m, _) in self.vistas.items():
            s = self.silhueta(nome)
            res[nome] = round(float((s & m).sum() / max(1, (s | m).sum())), 4)
        return res

    # ------------------------------------------------------------------ partes para o rig
    def partes(self, quadril=0.30, pescoco=0.55, braco_x=0.62, bota=0.38, cotovelo=0.5) -> dict:
        """Rótulo por voxel, em frações da altura do casco: pernas abaixo do quadril (lado pelo sinal de x),
        cabeça acima do pescoço, braços na faixa do meio além de braco_x da meia-largura dessa faixa."""
        o = self.ocup
        zs = self.Z[o]
        h0, h1 = zs.min(), zs.max() + self.v
        H = h1 - h0
        zq, zp = h0 + quadril * H, h0 + pescoco * H
        Z, X = self.Z, self.X
        meio = o & (Z >= zq) & (Z < zp)
        lim = braco_x * np.abs(X[meio]).max() if meio.any() else 1e9
        rot = {}
        perna = o & (Z < zq)
        zb = h0 + bota * (zq - h0)
        zj = (zb + zq) / 2
        for lado, nome in ((-1, "Esquerda"), (1, "Direita")):
            pl = perna & (np.sign(X) == lado)
            rot[("Perna " + nome, "Bota")] = pl & (Z < zb)
            rot[("Perna " + nome, "Canela")] = pl & (Z >= zb) & (Z < zj)
            rot[("Perna " + nome, "Coxa")] = pl & (Z >= zj)
            br = meio & (np.abs(X) > lim) & (np.sign(X) == lado)
            if br.any():
                zbr = Z[br]
                zc = zbr.min() + cotovelo * (zbr.max() - zbr.min())
                rot[("Braço " + nome, "Antebraço")] = br & (Z < zc)
                rot[("Braço " + nome, "Braço superior")] = br & (Z >= zc)
        rot[("Cabeça", "Cabeça")] = o & (Z >= zp)
        rot[("Tronco", "Tronco")] = meio & (np.abs(X) <= lim)
        return {k: m for k, m in rot.items() if m.any()}

    def pivos(self, rot: dict) -> dict:
        """Juntas pelas caixas das partes (metros)."""
        def caixa(*chaves):
            m = np.zeros(self.X.shape, bool)
            for c in chaves:
                if c in rot:
                    m |= rot[c]
            if not m.any():
                return None
            return (np.array([self.X[m].min(), self.Y[m].min(), self.Z[m].min()]),
                    np.array([self.X[m].max(), self.Y[m].max(), self.Z[m].max()]))

        P = {}
        r = lambda a: [round(float(x), 4) for x in a]
        t = caixa(("Tronco", "Tronco"))
        c = caixa(("Cabeça", "Cabeça"))
        yc = float((t[0][1] + t[1][1]) / 2) if t else 0.0
        if t:
            P["tronco"] = r([0, yc, t[0][2]])
        if c:
            P["cabeca"] = r([0, yc, c[0][2]])
        for lado, l, nome in ((-1, "e", "Esquerda"), (1, "d", "Direita")):
            b = caixa(("Braço " + nome, "Braço superior"), ("Braço " + nome, "Antebraço"))
            a = caixa(("Braço " + nome, "Antebraço"))
            if b:
                xin = b[1][0] if lado < 0 else b[0][0]
                P["ombro_" + l] = r([xin, yc, b[1][2] - self.v])
                if a:
                    P["cotovelo_" + l] = r([(a[0][0] + a[1][0]) / 2, yc, a[1][2]])
            p = caixa(("Perna " + nome, "Coxa"), ("Perna " + nome, "Canela"), ("Perna " + nome, "Bota"))
            cn = caixa(("Perna " + nome, "Canela"))
            bt = caixa(("Perna " + nome, "Bota"))
            if p:
                xm = float((p[0][0] + p[1][0]) / 2)
                P["coxa_" + l] = r([xm, yc, p[1][2]])
                if cn:
                    P["canela_" + l] = r([xm, yc, cn[1][2]])
                if bt:
                    P["pe_" + l] = r([xm, yc, bt[1][2]])
        return P

    # ------------------------------------------------------------------ cor: família de cada face, pela arte
    def _visivel(self, nome, idx):
        """Para os voxels idx (n,3): se cada um é o mais perto da câmera no seu pixel da vista (z-buffer)."""
        m, th = self.vistas[nome]
        c = (idx + 0.5) * self.v + self.origem
        u, w = self.tela(th, c[:, 0], c[:, 1], c[:, 2])
        yr = c[:, 0] * math.sin(th) + c[:, 1] * math.cos(th)
        perto = -yr * math.cos(self.ang) + c[:, 2] * math.sin(self.ang)
        col, lin = self._pixel(nome, u, w)
        H, W = m.shape
        ok = (col >= 0) & (col < W) & (lin >= 0) & (lin < H)
        # z-buffer na resolução do voxel (não do pixel da arte): numa superfície inclinada, vários voxels dividem
        # um pixel e todos os da frente são visíveis
        gu = np.floor((u - u.min()) / self.v).astype(np.int64)
        gw = np.floor((w - w.min()) / self.v).astype(np.int64)
        chave = gw * (gu.max() + 1) + gu
        zb = np.full(int(chave.max()) + 1, -1e9)
        np.maximum.at(zb, chave, perto)
        vis = ok & (perto >= zb[chave] - 1.5 * self.v)
        return vis, col, lin

    def _familia_px(self, nome, col, lin, tons, nomes):
        img, borda = self.rgba[nome], self.borda[nome]
        H, W = borda.shape
        out = np.full(len(col), -1)
        for dy, dx in [(0, 0), (0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
            y, x = np.clip(lin + dy, 0, H - 1), np.clip(col + dx, 0, W - 1)
            falta = (out < 0) & ~borda[y, x] & self.vistas[nome][0][y, x]
            if falta.any():
                cor = img[y[falta], x[falta]]
                d = ((cor[:, None, :] - tons[None, :, :]) ** 2).sum(-1)
                out[falta] = nomes[d.argmin(1)]
        return out

    def familias_faces(self, faces, familias: dict) -> np.ndarray:
        """faces: (n, 4) = voxel i,j,k + eixo*2+(sinal>0). Família (índice em familias) de cada face, lida na vista
        que mais encara a face e onde o voxel não está escondido; -1 se nenhuma vista vê."""
        nomes_f = list(familias)
        tons, nomes = [], []
        for k, f in enumerate(nomes_f):
            for hx in f_rampa(familias[f]):
                tons.append([int(hx[i:i + 2], 16) for i in (1, 3, 5)])
                nomes.append(k)
        tons, nomes = np.array(tons, float), np.array(nomes)
        idx = faces[:, :3]
        normal = np.zeros((len(faces), 3))
        normal[np.arange(len(faces)), faces[:, 3] // 2] = np.where(faces[:, 3] % 2 == 1, 1.0, -1.0)
        notas = []
        for nome, (m, th) in self.vistas.items():
            # direção para a câmera no referencial do modelo (a figura gira th; a câmera olha de -y, de cima)
            t = np.array([-math.sin(th) * math.cos(self.ang), -math.cos(th) * math.cos(self.ang), math.sin(self.ang)])
            notas.append(normal @ t)
        notas = np.array(notas)                                   # (vistas, n)
        votos = np.zeros((len(faces), len(nomes_f)))
        self.por_vista = {}
        for k, nome in enumerate(self.vistas):
            sel = notas[k] > 0.05
            if not sel.any():
                continue
            vis, col, lin = self._visivel(nome, idx[sel])
            fam = np.full(sel.sum(), -1)
            if vis.any():
                fam[vis] = self._familia_px(nome, col[vis], lin[vis], tons, nomes)
            pv = np.full(len(faces), -1)
            pv[np.nonzero(sel)[0]] = fam
            self.por_vista[nome] = pv
            linhas = np.nonzero(sel)[0][fam >= 0]
            np.add.at(votos, (linhas, fam[fam >= 0]), notas[k][linhas] ** 2)
        out = np.where(votos.max(1) > 0, votos.argmax(1), -1)
        return out

    # ------------------------------------------------------------------ malha: faces expostas de cada parte
    def malhas(self, rot: dict, familias: dict | None = None) -> list:
        out = []
        cantos = {  # (eixo, sinal) -> 4 cantos (deslocamentos inteiros) da face
            (0, 1): [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
            (0, -1): [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)],
            (1, 1): [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)],
            (1, -1): [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
            (2, 1): [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
            (2, -1): [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)],
        }
        nomes_f = list(familias) if familias else []
        for (col, obj), m in rot.items():
            quads, info = [], []
            p = np.pad(m, 1)
            for (eixo, sinal), cs in cantos.items():
                viz = np.roll(p, -sinal, axis=eixo)[1:-1, 1:-1, 1:-1]
                idx = np.argwhere(m & ~viz)
                if len(idx):
                    quads.append(idx[:, None, :] + np.array(cs)[None, :, :])
                    info.append(np.c_[idx, np.full(len(idx), eixo * 2 + (sinal > 0))])
            q = np.concatenate(quads)                         # (n, 4, 3) inteiros
            verts, inv = np.unique(q.reshape(-1, 3), axis=0, return_inverse=True)
            peca = {"colecao": col, "objeto": obj,
                    "verts": (verts * self.v + self.origem).round(5).tolist(),
                    "faces": inv.reshape(-1, 4).tolist()}
            if familias:
                fam = self.familias_faces(np.concatenate(info), familias)
                # face que nenhuma vista vê: a família mais comum da peça
                vistos = fam[fam >= 0]
                comum = int(np.bincount(vistos).argmax()) if len(vistos) else 0
                peca["familias"] = [nomes_f[f if f >= 0 else comum] for f in fam]
                # cor por direção (decisão do Artur, 2026-11-17): a família lida em cada vista; onde a vista não
                # vê a face, vale o voto de todas
                peca["familias_vista"] = {
                    v: [nomes_f[p] if p >= 0 else g for p, g in zip(pv, peca["familias"])]
                    for v, pv in self.por_vista.items()}
            out.append(peca)
        return out


def f_rampa(f) -> list:
    return [h if h.startswith("#") else "#" + h for h in f["rampa"]]