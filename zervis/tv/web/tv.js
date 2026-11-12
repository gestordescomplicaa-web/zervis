// SPDX-License-Identifier: AGPL-3.0-or-later
// O Modo TV (ADR 0084): a página que a TV abre. Pergunta ao Zé o que mostrar duas vezes por
// segundo; a peça vem do Acervo (GLB) e gira, sólida, em resolução intermediária (a TV de 2021
// roda a 31 quadros em 1080p e a 58 em meia resolução). Sem nada, o relógio.
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

const chave = new URLSearchParams(location.search).get("chave") || "";
const RESOLUCAO = 0.75;
const $ = (id) => document.getElementById(id);

const renderer = new THREE.WebGLRenderer({ canvas: $("palco"), antialias: true, alpha: true });
renderer.setPixelRatio(RESOLUCAO);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
const cena = new THREE.Scene();
cena.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
cena.add(new THREE.HemisphereLight(0xffffff, 0x0b2522, 0.5));
const luz = new THREE.DirectionalLight(0xffffff, 1.6);  // de cima e de lado: as faces ganham sombra
luz.position.set(3, 5, 2);
cena.add(luz);
const contra = new THREE.DirectionalLight(0x8ff0e4, 0.9);  // o contorno na cor do Zé
contra.position.set(-3, 1, -3);
cena.add(contra);
const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 10000);
const pivo = new THREE.Group();
cena.add(pivo);

function medir() {
  renderer.setSize(innerWidth, innerHeight, false);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
}
addEventListener("resize", medir);
medir();

const carregador = new GLTFLoader();
let atual = -1;
async function mostrarModelo(c) {
  const gltf = await carregador.loadAsync(`/tv/modelo?chave=${encodeURIComponent(chave)}&arquivo=${encodeURIComponent(c.arquivo)}`);
  if (c.seq !== atual) return;
  pivo.clear();
  const obj = gltf.scene, caixa = new THREE.Box3().setFromObject(obj);
  const tamanho = caixa.getSize(new THREE.Vector3()), centro = caixa.getCenter(new THREE.Vector3());
  obj.position.sub(centro);
  pivo.add(obj);
  pivo.rotation.set(0, 0, 0);
  // De cima, a uns 25°, com folga: a peça ocupa o meio da tela e o título fica livre embaixo.
  const raio = tamanho.length() / 2, distancia = raio / Math.sin(THREE.MathUtils.degToRad(camera.fov / 2)) * 1.55;
  camera.position.set(0, distancia * Math.sin(0.44), distancia * Math.cos(0.44));
  camera.lookAt(0, -raio * 0.12, 0);
  $("titulo").textContent = c.titulo || "";
  $("detalhe").textContent = c.detalhe || "";
  document.body.classList.add("modelo");
}
function mostrarRelogio() {
  document.body.classList.remove("modelo");
  setTimeout(() => { if (!document.body.classList.contains("modelo")) pivo.clear(); }, 900);
}

async function perguntar() {
  try {
    const r = await fetch(`/tv/estado?chave=${encodeURIComponent(chave)}`, { cache: "no-store" });
    if (r.ok) {
      const e = await r.json();
      document.body.classList.toggle("falando", !!e.falando);
      if (e.cena.seq !== atual) {
        atual = e.cena.seq;
        if (e.cena.tipo === "modelo") mostrarModelo(e.cena).catch(() => mostrarRelogio());
        else mostrarRelogio();
      }
    }
  } catch { /* o Zé reiniciando: tenta de novo */ }
  setTimeout(perguntar, 500);
}
perguntar();

function relogio() {
  const agora = new Date();
  $("hora").textContent = agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  $("data").textContent = agora.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
}
relogio();
setInterval(relogio, 1000);

(function quadro() {
  requestAnimationFrame(quadro);
  if (!document.body.classList.contains("modelo") && !pivo.children.length) return;
  pivo.rotation.y += 0.006;
  renderer.render(cena, camera);
})();
