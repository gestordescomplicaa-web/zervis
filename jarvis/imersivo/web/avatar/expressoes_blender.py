# SPDX-License-Identifier: AGPL-3.0-or-later
"""Gera o jarvis-chimpanze.glb a partir do .blend do chimpanzé, sem deformar a cabeça.

    blender -b <cabeca>.blend -P avatar/expressoes_blender.py -- <pasta de saída>

1. Expressões novas como variações (shape keys relativas à Basis): Sorriso, Sobrancelha_Duvida,
   Rosnar, Sobrancelha_Triste, Boca_Triste e Sorriso_Dentes. A Basis e as chaves que já existem não mudam. Os pontos de referência saem da própria
   malha: linha dos lábios e cantos pela chave Boca_Aberta; sobrancelhas pelas chaves Erguida e
   Brava (servem para qualquer revisão da cabeça que mantenha essas chaves).
2. Salva <saída>/chimpanze_cabeca_expressoes.blend (o original fica intocado).
3. Exporta <saída>/jarvis-chimpanze.glb: só a cabeça e os ossos, todas as chaves, sem o pelo de
   geometry nodes (o navegador refaz), com o atributo `pelo` como `_pelo` para o pelo nascer onde
   nasce no Blender.
"""

import sys

import bpy
import numpy as np

saida = sys.argv[sys.argv.index("--") + 1]
o = bpy.data.objects["CHIMP_Cabeca"]
rig = bpy.data.objects["CHIMP_Rig"]
me = o.data
kb = me.shape_keys.key_blocks
co = np.array([v.co[:] for v in me.vertices])
x, y, z = co.T
frente = -y  # Blender: a frente do rosto é -Y


def delta(nome):
    return np.array([p.co[:] for p in kb[nome].data]) - co


def g(v, s):
    return np.exp(-(v * v) / (2 * s * s))


def suave(a, b, t):
    t = np.clip((t - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


pele = np.zeros(len(co), bool)
for p in me.polygons:
    if p.material_index == 0:
        pele[list(p.vertices)] = True
boca = np.linalg.norm(delta("Boca_Aberta"), axis=1)
w = boca / boca.max()
labios_z = float(z[pele & (w > 0.9)].max())  # topo do lábio de baixo
transicao = pele & (w > 0.02) & (w < 0.35) & (frente > 0.07)
meia_boca = float(np.abs(x[transicao]).max()) * 0.87  # cantos da boca
ponta = float(frente[pele & (np.abs(z - labios_z) < 0.006) & (np.abs(x) < 0.01)].max())
print(f"marcos: lábios z={labios_z:.4f} cantos |x|={meia_boca:.4f} frente={ponta:.4f}")
na_frente = suave(ponta - 0.06, ponta - 0.025, frente) * pele
lado = np.where(x >= 0, 1.0, -1.0)


def chave(nome, d):
    if nome in kb:
        o.shape_key_remove(kb[nome])
    o.shape_key_add(name=nome, from_mix=False).data.foreach_set("co", (co + d).ravel())
    n = np.linalg.norm(d, axis=1)
    print(f"{nome}: até {n.max() * 1000:.1f} mm em {(n > 1e-5).sum()} vértices")


# Sorriso: cantos sobem, abrem e recuam; bochechas sobem um pouco.
canto = g(np.abs(x) - meia_boca, 0.013) * g(z - labios_z, 0.011) * na_frente
bochecha = g(np.abs(x) - 0.03, 0.014) * g(z - labios_z - 0.028, 0.012) * na_frente
d = np.zeros_like(co)
d[:, 0] = lado * 0.004 * canto
d[:, 2] = 0.011 * canto + 0.004 * bochecha
d[:, 1] = 0.004 * canto - 0.002 * bochecha
chave("Sorriso", d)

# Dúvida: a sobrancelha esquerda do personagem (+X) sobe, a direita franze.
t = suave(-0.012, 0.012, x)[:, None]
chave(
    "Sobrancelha_Duvida",
    delta("Sobrancelha_Erguida") * 2 * t + delta("Sobrancelha_Brava") * 1.1 * (1 - t),
)

# Rosnar: lábio de cima sobe dos lados do centro, nariz franze.
labio = g(np.abs(x) - 0.014, 0.011) * g(z - labios_z - 0.007, 0.006) * na_frente
nariz = g(x, 0.014) * g(z - labios_z - 0.035, 0.01) * na_frente
d = np.zeros_like(co)
d[:, 2] = 0.007 * labio + 0.003 * nariz
d[:, 1] = -0.002 * labio
chave("Rosnar", d)

# Tristeza, sobrancelhas: a ponta de dentro sobe e a de fora cai (o "telhado" da tristeza).
ax = np.abs(x)[:, None]
dentro = 1 - suave(0.012, 0.042, ax)
fora = suave(0.022, 0.05, ax)
erguida = delta("Sobrancelha_Erguida")
d = erguida * (1.9 * dentro - 1.1 * fora)
d[:, 0] -= (
    lado * 0.0012 * (np.linalg.norm(erguida, axis=1) / 0.005) * dentro[:, 0]
)  # juntam um pouco
chave("Sobrancelha_Triste", d)

# Tristeza, boca: cantos descem e recuam, o lábio de baixo avança um pouco (o "beicinho").
canto = g(np.abs(x) - meia_boca, 0.012) * g(z - labios_z, 0.01) * na_frente
beico = g(x, 0.016) * g(z - labios_z + 0.006, 0.006) * na_frente * (w > 0.5)
d = np.zeros_like(co)
d[:, 0] = -lado * 0.0015 * canto
d[:, 2] = -0.008 * canto + 0.0015 * beico
d[:, 1] = 0.002 * canto - 0.003 * beico
chave("Boca_Triste", d)

# Sorriso com os dentes: os lábios se afastam (o de cima sobe, o de baixo desce) sem abrir a
# mandíbula, e os cantos sobem e recuam. Os dentes e os olhos não se mexem; o resto da boca
# (lábios por dentro, gengiva, cavidade) acompanha pela mesma máscara suave.
fixos = np.zeros(len(co), bool)
for p in me.polygons:
    if me.materials[p.material_index] and me.materials[p.material_index].name.startswith(
        ("CHIMP_Dentes", "CHIMP_Olhos")
    ):
        fixos[list(p.vertices)] = True
largura = 1 - suave(meia_boca * 0.75, meia_boca * 1.15, np.abs(x))
perto = suave(ponta - 0.05, ponta - 0.015, frente) * ~fixos
cima = largura * g(z - labios_z - 0.004, 0.006) * perto * (w < 0.5)
baixo = largura * g(z - labios_z + 0.004, 0.006) * perto * (w >= 0.5)
canto = g(np.abs(x) - meia_boca, 0.013) * g(z - labios_z, 0.011) * na_frente
d = np.zeros_like(co)
d[:, 2] = 0.0065 * cima - 0.0055 * baixo + 0.008 * canto
d[:, 1] = 0.0015 * cima - 0.001 * baixo + 0.0045 * canto  # +Y recua
d[:, 0] = lado * 0.005 * canto
chave("Sorriso_Dentes", d)

bpy.ops.wm.save_as_mainfile(filepath=f"{saida}/chimpanze_cabeca_expressoes.blend", copy=True)

for k in kb[1:]:
    k.value = 0
for m in o.modifiers:
    if m.type == "NODES":
        m.show_viewport = m.show_render = False  # o pelo é refeito no navegador
pelo = np.zeros(len(me.vertices))
me.attributes["pelo"].data.foreach_get("value", pelo)
(me.attributes.get("_pelo") or me.attributes.new("_pelo", "FLOAT", "POINT")).data.foreach_set(
    "value", pelo
)
rig.hide_viewport = False
rig.hide_set(False)
o.hide_set(False)
bpy.ops.object.select_all(action="DESELECT")
o.select_set(True)
rig.select_set(True)
bpy.context.view_layer.objects.active = o
bpy.ops.export_scene.gltf(
    filepath=f"{saida}/jarvis-chimpanze.glb", export_format="GLB", use_selection=True,
    export_yup=True, export_apply=False, export_texcoords=True, export_normals=True,
    export_morph=True, export_morph_normal=False, export_materials="EXPORT",
    export_animations=False, export_attributes=True, export_extras=True,
)  # fmt: skip
print("pronto:", saida)
