// Dependências servidas localmente; este arquivo é usado apenas pelo verificador.
interface Window {
  webkitAudioContext: typeof AudioContext;
  desenharManutencao?: (estado: {ligada: boolean, aguardando: boolean}) => void;
  desenharTravaSessoes?: () => void;
  unificandoSessoes?: boolean;
}
declare class Terminal {
  constructor(opcoes?: Record<string, unknown>);
  cols: number;
  rows: number;
  options: {disableStdin?: boolean};
  loadAddon(addon: unknown): void;
  open(elemento: HTMLElement): void;
  onData(callback: (dados: string) => void): {dispose(): void};
  onResize(callback: (tamanho: {cols: number, rows: number}) => void): {dispose(): void};
  write(dados: string): void;
  focus(): void;
  dispose(): void;
}
declare namespace FitAddon {
  class FitAddon { fit(): void; }
}

interface EtapaAtualizacao {
  id: string;
  titulo: string;
  estado: "pendente" | "atual" | "feita" | "falhou";
  segundos: number;
  estimado: number;
}
interface Atualizacao {
  estado: "aguardando" | "aplicando" | "falhou" | "pronto" | "voltou";
  etapas: EtapaAtualizacao[];
  decorrido: number;
  texto: string;
  fim: number;
}
