package com.zervis.voz;

/**
 * A escuta de perto (ADR 0086): pelo microfone do celular, só passa a voz de quem fala junto dele,
 * como numa ligação fora do viva-voz. A voz a um palmo do microfone chega dezenas de vezes mais
 * forte que a conversa da sala, a TV ou a rua; o que fica abaixo do nível mínimo vai como silêncio.
 *
 * O nível vai de 0 a 60 (decibéis acima de um piso: 60 é o máximo do microfone), medido em blocos
 * de 20 ms. Abre com 40 ms seguidos acima do mínimo (um estalo não abre) e segura 600 ms depois da
 * última voz, para as pausas e as sílabas fracas de uma frase não serem cortadas. Aberta, a voz um
 * pouco abaixo do mínimo ainda segura.
 *
 * Sem nada do Android: os testes rodam na CI (ProximidadeTest).
 */
final class Proximidade {
    static final int PISO = 0;
    static final int TETO = 60;
    static final int PADRAO = 30;
    /** O nível mínimo que a tela deixa escolher: abaixo ou acima disto, a escuta não distingue. */
    static final int MENOR = 10;
    static final int MAIOR = 50;

    private static final int BLOCO = 640; // bytes: 20 ms a 16 kHz, 16 bits
    private static final int SEGUIDOS = 2;
    private static final int SEGURA = 30; // blocos: 600 ms
    private static final int FOLGA = 6; // aberta, a voz até isto abaixo do mínimo ainda segura

    private final int minimo;
    private int seguidos;
    private int restam; // blocos que ainda fica aberta
    private int nivel;

    Proximidade(int minimo) {
        this.minimo = Math.max(MENOR, Math.min(MAIOR, minimo));
    }

    /** Um quadro do microfone (PCM de 16 bits, o byte baixo primeiro): passa ou vai como silêncio. */
    boolean passa(byte[] pcm, int tamanho) {
        boolean passou = restam > 0;
        int pico = PISO;
        for (int i = 0; i + 1 < tamanho; i += BLOCO) {
            int n = medir(pcm, i, Math.min(tamanho, i + BLOCO));
            pico = Math.max(pico, n);
            if (n >= minimo) {
                seguidos++;
                if (seguidos >= SEGUIDOS || restam > 0) restam = SEGURA;
            } else {
                seguidos = 0;
                if (restam > 0) restam = n >= minimo - FOLGA ? SEGURA : restam - 1;
            }
            if (restam > 0) passou = true;
        }
        nivel = pico;
        return passou;
    }

    /** O nível do último quadro (o bloco mais forte), para a tela. */
    int nivel() {
        return nivel;
    }

    /** O nível de um bloco, sem a componente contínua do microfone. */
    private static int medir(byte[] pcm, int de, int ate) {
        int amostras = (ate - de) / 2;
        if (amostras == 0) return PISO;
        long soma = 0;
        for (int i = de; i + 1 < ate; i += 2) soma += (short) ((pcm[i] & 0xff) | (pcm[i + 1] << 8));
        double media = (double) soma / amostras;
        double energia = 0;
        for (int i = de; i + 1 < ate; i += 2) {
            double a = (short) ((pcm[i] & 0xff) | (pcm[i + 1] << 8)) - media;
            energia += a * a;
        }
        double rms = Math.sqrt(energia / amostras);
        if (rms < 1) return PISO;
        long decibeis = Math.round(20 * Math.log10(rms / 32768.0)) + TETO;
        return (int) Math.max(PISO, Math.min(TETO, decibeis));
    }
}
