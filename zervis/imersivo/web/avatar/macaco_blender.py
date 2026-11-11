# The Zé's monkey (avatar/jarvis-macaco.glb) from the original download, in one run:
#   blender -b -P avatar/macaco_blender.py -- <monkey__australopithecus_stone_bust.glb> avatar/jarvis-macaco.glb
# Source: "Monkey / Australopithecus stone bust" by gamnok (Sketchfab, CC BY 4.0; the 1k-texture
# GLB). Steps: join and reduce to 60 thousand faces, no texture; split the lips on the carved
# crease and open the jaw as the shape key jawOpen (an oval opening); a dark mouth inside; a
# chimpanzee dentition (2.1.2.3, U-shaped arcade, blunt canines) kept clear of the lips; the
# emotions alegria, tristeza, raiva and duvida as shape keys. Approved in the lab on 11/11/2026.
# Normalized: 1 unit tall, centred; Blender Z up, face towards -Y.
import bpy, bmesh, math, sys
from mathutils import Matrix, Vector
entrada, saida = sys.argv[sys.argv.index("--") + 1:]   # the Sketchfab GLB, the glTF to write
CANTO = .104                                   # where the lips meet (|x|), seen on the renders
vinco = lambda x: .100 - .35 * x * x           # the crease height: flat in front, a little lower at the corners
DOBRADICA, ANGULO = Vector((0, .0, .15)), math.radians(10)

def suave(a, b, x):
    t = max(0., min(1., (x - a) / (b - a))); return t * t * (3 - 2 * t)

def abrir(ob, peso):
    if not ob.data.shape_keys: ob.shape_key_add(name="Basis")
    k = ob.shape_key_add(name="jawOpen")
    for v in ob.data.vertices:
        w = peso(v)
        if w > 0: k.data[v.index].co = DOBRADICA + Matrix.Rotation(ANGULO * w, 4, "X") @ (v.co - DOBRADICA)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=entrada)
malhas = [x for x in bpy.context.scene.objects if x.type == "MESH"]
for x in bpy.context.scene.objects: x.select_set(x in malhas)
bpy.context.view_layer.objects.active = malhas[0]
bpy.ops.object.join()
o = bpy.context.view_layer.objects.active
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0005)
bpy.ops.object.mode_set(mode="OBJECT")
reduzir_ = o.modifiers.new("reduzir", "DECIMATE"); reduzir_.ratio = min(1.0, 60000 / len(o.data.polygons))
bpy.ops.object.modifier_apply(modifier="reduzir")
o.data.materials.clear()
while o.data.uv_layers: o.data.uv_layers.remove(o.data.uv_layers[0])
for x in list(bpy.data.objects):
    if x is not o: bpy.data.objects.remove(x)
bpy.ops.object.shade_smooth()
# through a glTF and back, as the approved model was made (it leaves the reduced mesh triangulated)
import os, tempfile
meio = os.path.join(tempfile.mkdtemp(), "busto.glb")
bpy.ops.export_scene.gltf(filepath=meio, export_format="GLB", export_materials="NONE", export_texcoords=False, export_tangents=False, export_yup=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=meio)
o = next(x for x in bpy.context.scene.objects if x.type == "MESH")
bpy.context.view_layer.objects.active = o; o.select_set(True)
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM"); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
bm = bmesh.new(); bm.from_mesh(o.data)
cs = [v.co.copy() for v in bm.verts]
lo = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs))); hi = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
bmesh.ops.transform(bm, matrix=Matrix.Scale(1 / (hi.z - lo.z), 4) @ Matrix.Translation(-(lo + hi) / 2), verts=bm.verts)

# the lip surface, measured: for each |x|, how far forward the face is at the crease
tabela = []
for i in range(0, 23):
    x = i * .005
    ys = [-v.co.y for v in bm.verts if abs(abs(v.co.x) - x) < .004 and abs(v.co.z - vinco(x)) < .012 and -v.co.y > .1]
    tabela.append((x, max(ys) if ys else None))
for i in range(len(tabela)):          # fill gaps and smooth
    if tabela[i][1] is None: tabela[i] = (tabela[i][0], tabela[i - 1][1])
lisa = [(x, sum(t[1] for t in tabela[max(0, i - 1):i + 2]) / len(tabela[max(0, i - 1):i + 2])) for i, (x, _) in enumerate(tabela)]
def frente(x):
    x = abs(x)
    for (x0, y0), (x1, y1) in zip(lisa, lisa[1:]):
        if x <= x1: return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return lisa[-1][1]
print("lábio (x, frente):", [(round(x, 3), round(y, 3)) for x, y in lisa[::3]])

# 1. the cut along the crease: flatten the crease, cut with a plane, put it back
regiao = [f for f in bm.faces if abs(f.calc_center_median().x) < CANTO + .012 and -f.calc_center_median().y > .14
          and abs(f.calc_center_median().z - vinco(f.calc_center_median().x)) < .02]
verts = {v for f in regiao for v in f.verts}
for v in verts: v.co.z -= vinco(v.co.x) - .1
corte = bmesh.ops.bisect_plane(bm, geom=list(set(regiao) | {e for f in regiao for e in f.edges} | verts), plane_co=(0, 0, .1), plane_no=(0, 0, 1))
novos = {v for v in corte["geom_cut"] if isinstance(v, bmesh.types.BMVert)}
for v in verts | novos: v.co.z += vinco(v.co.x) - .1
labio = [e for e in corte["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and all(abs(v.co.x) < CANTO - .012 and -v.co.y > .14 for v in e.verts)]
bmesh.ops.split_edges(bm, edges=labio)
lado = {}
for v in bm.verts:
    if abs(v.co.z - vinco(v.co.x)) < 2e-4 and abs(v.co.x) < CANTO + .005 and -v.co.y > .14:
        zs = [f.calc_center_median().z - vinco(f.calc_center_median().x) for f in v.link_faces]
        lado[v.index] = "baixo" if zs and max(zs) < 0 else "cima" if zs and min(zs) > 0 else "canto"
o.data.materials.clear(); o.data.materials.append(bpy.data.materials.new("Pele"))
bm.to_mesh(o.data); bm.free()
print("corte:", len(labio), "arestas; lábios:", {k: list(lado.values()).count(k) for k in ("cima", "baixo", "canto")})

def peso_pele(v):
    c = v.co
    if lado.get(v.index) == "cima" or c.z > vinco(c.x) + 1e-4: return 0.
    w = suave(.10, .17, -c.y) * (1 - suave(CANTO - .01, CANTO + .05, abs(c.x))) * suave(-.05, .015, c.z)
    oval = 1 - suave(.03, CANTO + .004, abs(c.x)) ** 1.3        # the lips part in an oval, corners stay
    perto = suave(.0, .065, vinco(c.x) - c.z)                  # 0 at the lip, 1 further below (no fold)
    w *= oval + (1 - oval) * perto
    return w * (.5 if lado.get(v.index) == "canto" else 1.)
abrir(o, peso_pele); o.name = o.data.name = "busto"

# the inner line of the mouth: the lip curve pushed inward; past the corners it runs straight back
def linha(s):
    """s in [-1, 1] across the mouth (0 = middle); beyond |s|=1 straight back along the cheeks."""
    lado_ = 1 if s >= 0 else -1; a = min(abs(s), 1.)
    x = a * (CANTO - .014)
    p = Vector((lado_ * x, -frente(x) + .015 + .02 * a ** 4, 0))
    if abs(s) > 1: p.y += (abs(s) - 1) * .05; p.x -= lado_ * (abs(s) - 1) * .05   # behind the corners: back and inward
    return p

# 2. the mouth inside: a U-shaped trough along that line, open towards the lips
interna = bpy.data.materials.new("BocaInterna"); interna.diffuse_color = (.06, .03, .03, 1)
mb = bmesh.new(); aneis = []
N, M = 48, 12
for i in range(N + 1):
    s = -1.35 + 2.7 * i / N
    a_ = min(abs(s), 1.)
    p = linha(s) + Vector((-(1 if s >= 0 else -1) * .012 * a_ ** 3, .03 * a_ ** 3, 0)); z0 = vinco(p.x)   # deeper at the sides
    q = linha(s + .01) - linha(s - .01); t = Vector((q.x, q.y, 0)).normalized()
    dentro = Vector((-t.y, t.x, 0))
    if dentro.dot(Vector((-p.x, .05, 0))) < 0: dentro = -dentro   # towards the middle of the mouth
    fim = 1 - suave(1.15, 1.35, abs(s))              # taper shut at the back
    prof, alt = .02 + .018 * fim, .004 + .02 * fim * (1 - .45 * a_ ** 4)
    anel = []
    for j in range(M + 1):
        th = -math.pi / 2 + math.pi * j / M
        anel.append(mb.verts.new(p - dentro * .004 + dentro * prof * math.cos(th) + Vector((0, 0, z0 + alt * math.sin(th)))))
    aneis.append(anel)
for a, b in zip(aneis, aneis[1:]):
    for j in range(M): mb.faces.new((a[j], b[j], b[j + 1], a[j + 1]))
malha = bpy.data.meshes.new("boca"); mb.to_mesh(malha); mb.free()
boca = bpy.data.objects.new("boca", malha); bpy.context.scene.collection.objects.link(boca)
boca.data.materials.append(interna)
abrir(boca, lambda v: suave(vinco(v.co.x) + .004, vinco(v.co.x) - .012, v.co.z) * (1 - suave(.03, CANTO + .02, abs(v.co.x)) ** 1.3 * .85))
bpy.context.view_layer.objects.active = boca; boca.select_set(True); bpy.ops.object.shade_smooth(); boca.select_set(False)

# 3. the chimpanzee dentition: 2.1.2.3 per quadrant (32 teeth), a U-shaped arcade: spatulate
# incisors round the front, then premolars and molars in near-parallel rows going back; an upper
# diastema between the lateral incisor and the canine, a small lower one behind the canine.
# Mesiodistal sizes from chimpanzee odontometry (mm), scaled to the bust; canines kept blunt.
MM = .00185
# (kind, mesiodistal width, crown height, buccolingual depth), mm
CIMA = [("i", 11.7, 11.5, 9.), ("i", 8.6, 10.0, 8.), ("vao", 3.0, 0, 0), ("c", 11.0, 12.5, 11.),
        ("p", 8.1, 8.0, 12.), ("p", 7.4, 7.5, 12.), ("m", 10.5, 6.5, 13.), ("m", 10.2, 6.2, 13.), ("m", 9.2, 5.8, 12.)]
BAIXO = [("i", 6.6, 9.5, 8.), ("i", 7.3, 9.5, 8.), ("c", 10.0, 11.0, 10.), ("vao", 1.5, 0, 0),
         ("p", 10.0, 7.5, 9.), ("p", 8.0, 7.0, 10.), ("m", 11.1, 6.0, 11.), ("m", 11.5, 5.8, 11.), ("m", 11.0, 5.5, 10.)]
dentes_mat = bpy.data.materials.new("Dentes"); dentes_mat.diffuse_color = (.93, .91, .86, 1)
gengiva_mat = bpy.data.materials.new("Gengiva"); gengiva_mat.diffuse_color = (.55, .22, .25, 1)

def arcada(baixo):
    """The tooth-row centre line, middle to the back: a curve round the front to the canine,
    then a straight, slightly diverging row back towards the corner of the mouth."""
    recuo = .006 if baixo else 0.                       # the lower row sits just behind the upper
    yF = -frente(0) + .030 + recuo
    xc, yc = .052 - recuo * .5, yF + .030
    pts = [Vector((xc * k / 30, yF + (yc - yF) * (k / 30) ** 2, 0)) for k in range(31)]
    fim = Vector((.074 - recuo * .5, -.198, 0))
    pts += [pts[-1].lerp(fim, k / 30) for k in range(1, 31)]
    return pts
def ao_longo(pts, dist):
    feito = 0.
    for a, b in zip(pts, pts[1:]):
        l = (b - a).length
        if feito + l >= dist:
            return a.lerp(b, (dist - feito) / l), (b - a).normalized()
        feito += l
    return pts[-1], (pts[-1] - pts[-2]).normalized()

pecas = []
for baixo, fileira in ((0, CIMA), (1, BAIXO)):
    pts = arcada(baixo)
    for lado_ in (-1, 1):
        dist = .0004
        for tipo, md, alto_mm, bl in fileira:
            larg = md * MM
            if tipo == "vao": dist += larg; continue
            alto, fundo = alto_mm * MM, bl * MM
            c, tan = ao_longo(pts, dist + larg / 2); dist += larg + .0003
            c = Vector((lado_ * c.x, c.y, 0)); tan = Vector((lado_ * tan.x, tan.y, 0))
            z0 = vinco(c.x)
            bpy.ops.mesh.primitive_cube_add(size=1); d = bpy.context.active_object
            d.scale = (larg * .96, fundo, alto); bpy.ops.object.transform_apply(scale=True)
            bev = d.modifiers.new("b", "BEVEL"); bev.width = min(larg, alto, fundo) * (.42 if tipo in "pm" else .3); bev.segments = 4
            bpy.ops.object.modifier_apply(modifier="b")
            for v in d.data.vertices:
                borda = (-v.co.z if not baixo else v.co.z) / (alto / 2)
                if borda <= 0: continue
                if tipo == "c":   v.co.x *= 1 - .45 * borda ** 2; v.co.y *= 1 - .45 * borda ** 2   # blunt cone
                elif tipo == "i": v.co.y *= 1 - .45 * borda                                          # spatulate edge
                elif tipo == "p": v.co.x *= 1 - .15 * borda ** 2                                     # two soft cusps
            # crowns hang from the gum just above the lip line (upper) or below it (lower)
            z = z0 + .0095 - alto / 2 if not baixo else z0 - .0145 + alto / 2   # lower row behind the lower lip
            if tipo == "c" and not baixo:      # the upper canines sit where the lip is thin: tuck them in and up
                z += .0035; c = c + Vector((-.006 * lado_ * abs(tan.y), .005, 0))
            d.rotation_euler = (0, 0, math.atan2(tan.y, tan.x))
            d.location = (c.x, c.y, z)
            bpy.ops.object.transform_apply(location=True, rotation=True)
            d.data.materials.append(dentes_mat); d["baixo"] = baixo; pecas.append(d)
    # the gum along the same line, above the upper crowns and below the lower ones
    gb = bmesh.new(); fileiras = []
    comp = sum(f[1] for f in fileira) * MM + .004               # as long as the row of teeth
    corte_g, feito = len(pts), 0.
    for k, (a, b) in enumerate(zip(pts, pts[1:])):
        feito += (b - a).length
        if feito > comp: corte_g = k + 1; break
    meio = pts[:corte_g]
    linha_g = [Vector((-q.x, q.y, 0)) for q in meio[::-1][:-1]] + meio
    for i, q in enumerate(linha_g):
        nxt = linha_g[min(i + 1, len(linha_g) - 1)]; prv = linha_g[max(i - 1, 0)]
        tg = (nxt - prv).normalized(); dentro = Vector((-tg.y, tg.x, 0))
        if dentro.dot(Vector((-q.x, .05, 0))) < 0: dentro = -dentro
        ponta = 1 - suave(.75, 1., min(i, len(linha_g) - 1 - i) and 1 - min(i, len(linha_g) - 1 - i) / (len(linha_g) / 2) or 1.)
        z0 = vinco(q.x) + (.0065 if not baixo else -.0085); h = (.007 if not baixo else -.007) * ponta
        fileiras.append([gb.verts.new(q + dentro * dd + Vector((0, 0, z0 + dz))) for dd, dz in ((-.006, 0), (-.006, h), (.010, h), (.010, 0))])
    for a, b in zip(fileiras, fileiras[1:]):
        for k in range(4): gb.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
    m = bpy.data.meshes.new("gengiva"); gb.to_mesh(m); gb.free()
    g = bpy.data.objects.new("gengiva", m); bpy.context.scene.collection.objects.link(g)
    g.data.materials.append(gengiva_mat); g["baixo"] = baixo; pecas.append(g)
print("dentes:", len([d for d in pecas if d.name != "gengiva" and not d.name.startswith("gengiva")]))
# no tooth or gum may touch the lips: every vertex has to stay inside the skin with a margin,
# with the mouth closed and open (the upper teeth against the closed lower lip, the lower teeth
# against the open one). A piece that touches goes back into the mouth until it is clear.
from mathutils.bvhtree import BVHTree
FOLGA = .0015
def pele_com(abertura):
    o.data.shape_keys.key_blocks["jawOpen"].value = abertura
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    return BVHTree.FromObject(o, dg)
pele_fechada, pele_aberta = pele_com(0.), pele_com(.85)
o.data.shape_keys.key_blocks["jawOpen"].value = 0.
def encosta(ob, bvh, giro):
    m = ob.matrix_world
    for v in ob.data.vertices:
        pto = giro(m @ v.co)
        perto, normal, _, dist = bvh.find_nearest(pto, .02)
        if perto is None: continue
        if (pto - perto).dot(normal) > -FOLGA:      # outside the skin, or touching it
            return True
    return False
fechar = lambda p_: p_
abrir_baixo = lambda p_: DOBRADICA + Matrix.Rotation(ANGULO * .85, 4, "X") @ (p_ - DOBRADICA)
recuos = 0
for d in pecas:
    for _ in range(30):
        toca = encosta(d, pele_fechada, fechar) or (d["baixo"] and encosta(d, pele_aberta, abrir_baixo))
        if not toca: break
        d.location.y += .0007                                    # back into the mouth
        d.location.x -= .0003 * (1 if d.location.x > 0 else -1)  # and towards the middle
        bpy.context.view_layer.update(); recuos += 1
print("recuos:", recuos, "| ainda encostam:", sum(encosta(d, pele_fechada, fechar) or (d["baixo"] and encosta(d, pele_aberta, abrir_baixo)) for d in pecas))
grupos = {b: [d for d in pecas if d["baixo"] == b] for b in (0, 1)}
for baixo, nome in ((0, "dentes_cima"), (1, "dentes_baixo")):
    grupo = grupos[baixo]
    bpy.ops.object.select_all(action="DESELECT")
    for d in grupo: d.select_set(True)
    bpy.context.view_layer.objects.active = grupo[0]; bpy.ops.object.join()
    ob = bpy.context.active_object; ob.name = ob.data.name = nome
    bpy.ops.object.shade_smooth()
    abrir(ob, (lambda v: 1.) if baixo else (lambda v: 0.))
bpy.ops.object.select_all(action="DESELECT"); bpy.context.view_layer.objects.active = o; o.select_set(True); bpy.ops.object.shade_smooth()

# 4. the emotions as shape keys, then the glTF
o = bpy.data.objects["busto"]

def bolha(c, centro, raio):
    d = Vector(((c.x - centro[0]) / raio[0], (c.y - centro[1]) / raio[1], (c.z - centro[2]) / raio[2]))
    return math.exp(-d.length_squared * 2.2)

def na_frente(c):          # only the face's skin in front, never the back of the head
    return max(0., min(1., (-c.y - .12) / .06))

def chave(nome, mover):
    k = o.shape_key_add(name=nome, from_mix=False)
    for v in o.data.vertices:
        c = v.co
        d = mover(c) * na_frente(c)
        if d.length_squared > 1e-12:
            k.data[v.index].co = c + d
    return k

def alegria(c):
    d = Vector()
    for s in (-1, 1):
        canto = bolha(c, (s * .095, -.24, .10), (.035, .06, .03))
        d += Vector((s * .007, .011, .02)) * canto                   # corners up and back: a smile
        bochecha = bolha(c, (s * .085, -.25, .17), (.045, .06, .04))
        d += Vector((0, -.003, .011)) * bochecha                      # cheeks rise
        palpebra = bolha(c, (s * .052, -.24, .272), (.025, .04, .012))
        d += Vector((0, 0, .006)) * palpebra                          # a gentle squint
    return d

def tristeza(c):
    d = Vector()
    for s in (-1, 1):
        canto = bolha(c, (s * .095, -.24, .10), (.035, .06, .03))
        d += Vector((0, .003, -.02)) * canto                         # corners down
        dentro = bolha(c, (s * .03, -.27, .355), (.03, .06, .025))
        d += Vector((0, 0, .024)) * dentro                            # inner brows up
        fora = bolha(c, (s * .11, -.22, .35), (.03, .06, .025))
        d += Vector((0, 0, -.009)) * fora
    beico = bolha(c, (0, -.33, .08), (.05, .04, .02))
    d += Vector((0, -.01, -.003)) * beico                            # lower lip pushed out
    return d

def raiva(c):
    d = Vector()
    for s in (-1, 1):
        sobr = bolha(c, (s * .06, -.26, .355), (.06, .06, .03))
        d += Vector((-s * .009, -.007, -.026)) * sobr                 # brows down and together
    nariz = bolha(c, (0, -.31, .23), (.04, .05, .03))
    d += Vector((0, .003, .008)) * nariz                              # the nose wrinkles up
    labio = bolha(c, (0, -.34, .12), (.045, .04, .02))
    d += Vector((0, 0, .004)) * labio                                 # the upper lip lifts a little
    return d

def duvida(c):
    d = Vector()
    d += Vector((0, 0, .032)) * bolha(c, (.06, -.26, .36), (.06, .06, .03))       # one brow up
    d += Vector((0, 0, -.008)) * bolha(c, (-.06, -.26, .355), (.05, .06, .025))  # the other a little down
    d += Vector((.01, .006, .011)) * bolha(c, (.095, -.24, .10), (.03, .06, .025))   # one corner pulled aside
    d += Vector((0, 0, -.003)) * bolha(c, (-.095, -.24, .10), (.03, .06, .025))
    return d

for nome, f in (("alegria", alegria), ("tristeza", tristeza), ("raiva", raiva), ("duvida", duvida)):
    chave(nome, f)
print("chaves:", [k.name for k in o.data.shape_keys.key_blocks])
bpy.ops.export_scene.gltf(filepath=saida, export_format="GLB", export_morph=True, export_morph_normal=False,
                          export_texcoords=False, export_tangents=False, export_yup=True, export_apply=False)
