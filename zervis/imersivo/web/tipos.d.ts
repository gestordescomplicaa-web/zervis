// O que os scripts da Imersão dividem entre si; este arquivo é usado apenas pelo verificador
// (`npm run check`, tsconfig.imersao.json). Cada `jarvis-*.js` é um script clássico que publica a
// própria API em `window` e lê a dos outros: o verificador confere o código de dentro de cada
// arquivo, e estas pontes ficam abertas (`any`) até cada uma ganhar o seu tipo.
interface Window {
  // Os scripts do Zé (zervis/imersivo/web/jarvis-*.js).
  jarvisAbertura: any;
  jarvisAndamento: any;
  jarvisApresentacao: any;
  jarvisAvatar: any;
  jarvisBrainGestures: any;
  jarvisCenas: any;
  jarvisCerebro: any;
  jarvisConfig: any;
  jarvisControle: any;
  jarvisFundo: any;
  JarvisGraph: any;
  jarvisHolograma: any;
  jarvisMaos: any;
  jarvisMapas: any;
  jarvisPanels: any;
  jarvisRitmo: any;
  jarvisTeclado: any;
  jarvisTema: any;
  jarvisWorkspace: any;
  // O palco (stage.html, o Barehands adaptado; THIRD_PARTY.md).
  barehandsPerformance: any;
  jarvisItemDe: any;
  jarvisPanelActions: any;
  jarvisRing: any;
  jarvisStage: any;
}

// O three.js vem pelo importmap do stage.html (servido localmente), sem os tipos dele.
declare module "three";
declare module "three/addons/*";
