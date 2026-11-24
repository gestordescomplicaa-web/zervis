package com.zervis.voz;

/**
 * O que a tela Início mostra no centro, de tudo o que o serviço sabe agora: a conexão, o botão
 * apertado, a fala do Zé tocando aqui e o estado que o Zé manda ({"tipo":"estado"}, o mesmo do
 * ícone do painel). Sem Android: testado na CI ({@code FaseTest}).
 */
final class Fase {
    static final String DESCONECTADO = "desconectado";
    static final String CONECTANDO = "conectando";
    static final String SEM_REDE = "sem_rede"; // caiu: tenta de novo sozinho
    static final String EM_USO = "em_uso"; // outro aparelho assumiu a voz
    static final String SEM_MICROFONE = "sem_microfone";
    static final String PRONTO = "pronto";
    static final String OUVINDO = "ouvindo";
    static final String PENSANDO = "pensando";
    static final String FALANDO = "falando";
    static final String CONFIRMANDO = "confirmando"; // o Zé espera o "sim"
    static final String INATIVO = "inativo";

    private Fase() {}

    /**
     * @param queda    por que a conexão caiu ({@link #SEM_REDE}, {@link #EM_USO}) ou
     *                 {@link #SEM_MICROFONE}; vazio, nada
     * @param doZe     o último estado que o Zé mandou nesta conexão (vazio: um Zé que não manda)
     * @param falaAte  até quando a fala do Zé toca aqui (relógio desde o boot, ms)
     * @param esperaAte sem o estado do Zé: até quando o pedido enviado conta como "pensando"
     */
    static String de(boolean ligado, boolean conectando, boolean conectado, String queda,
                     boolean apertado, String doZe, long falaAte, long esperaAte, long agora) {
        if (!ligado) return DESCONECTADO;
        if (conectando) return CONECTANDO;
        if (!conectado) return EM_USO.equals(queda) ? EM_USO : SEM_REDE;
        if (SEM_MICROFONE.equals(queda)) return SEM_MICROFONE;
        if (agora < falaAte) return FALANDO;
        if (apertado) return OUVINDO;
        switch (doZe) {
            case "ouvindo": return OUVINDO;
            case "pensando": return PENSANDO;
            case "falando": return FALANDO;
            case "confirmando": return CONFIRMANDO;
            case "inativo": return INATIVO;
            case "": return agora < esperaAte ? PENSANDO : PRONTO;
            default: return PRONTO; // "ativo"
        }
    }

    /** Conectado ao Zé (o anel aceso, o botão fala). */
    static boolean conectado(String fase) {
        switch (fase) {
            case DESCONECTADO: case CONECTANDO: case SEM_REDE: case EM_USO: return false;
            default: return true;
        }
    }
}
