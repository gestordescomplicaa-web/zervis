package com.zervis.voz;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

/** A escuta de perto (ADR 0086): o que passa e o que vai como silêncio, com sons de bancada. */
public class ProximidadeTest {
    private static final int TAXA = 16000;
    private static final int QUADRO_MS = 80;

    /** Um tom no nível pedido (0 a 60), em PCM de 16 bits. */
    private static byte[] som(int nivel, int ms) {
        int amostras = TAXA * ms / 1000;
        double pico = 32768.0 * Math.pow(10, (nivel - Proximidade.TETO) / 20.0) * Math.sqrt(2);
        byte[] pcm = new byte[amostras * 2];
        for (int i = 0; i < amostras; i++) {
            short a = (short) Math.max(-32768, Math.min(32767, Math.round(pico * Math.sin(2 * Math.PI * 300 * i / TAXA))));
            pcm[2 * i] = (byte) a;
            pcm[2 * i + 1] = (byte) (a >> 8);
        }
        return pcm;
    }

    private static byte[] silencio(int ms) {
        return new byte[TAXA * ms / 1000 * 2];
    }

    private static boolean quadro(Proximidade p, byte[] pcm) {
        return p.passa(pcm, pcm.length);
    }

    @Test
    public void aVozDePertoPassaDesdeOPrimeiroQuadro() {
        Proximidade p = new Proximidade(30);
        assertTrue(quadro(p, som(42, QUADRO_MS)));
        assertEquals(42, p.nivel());
    }

    @Test
    public void aConversaDaSalaNuncaPassa() {
        Proximidade p = new Proximidade(30);
        for (int i = 0; i < 50; i++) assertFalse(quadro(p, som(18, QUADRO_MS)));
        assertEquals(18, p.nivel());
    }

    @Test
    public void umEstaloNaoAbre() {
        Proximidade p = new Proximidade(30);
        byte[] pcm = silencio(QUADRO_MS);
        byte[] estalo = som(55, 10);
        System.arraycopy(estalo, 0, pcm, 640, estalo.length); // 10 ms forte no meio do silêncio
        assertFalse(quadro(p, pcm));
        assertFalse(quadro(p, silencio(QUADRO_MS)));
    }

    @Test
    public void seguraAsPausasDaFraseEFechaDepois() {
        Proximidade p = new Proximidade(30);
        assertTrue(quadro(p, som(40, QUADRO_MS)));
        int abertos = 0;
        while (quadro(p, silencio(QUADRO_MS))) abertos++;
        assertEquals(8, abertos); // 600 ms depois da última voz: 7 quadros e meio
        assertFalse(quadro(p, som(18, QUADRO_MS))); // fechada, a sala continua de fora
    }

    @Test
    public void aSilabaFracaSeguraMasNaoAbre() {
        Proximidade p = new Proximidade(30);
        for (int i = 0; i < 20; i++) assertFalse(quadro(p, som(26, QUADRO_MS)));
        assertTrue(quadro(p, som(40, QUADRO_MS)));
        for (int i = 0; i < 20; i++) assertTrue(quadro(p, som(26, QUADRO_MS)));
    }

    @Test
    public void oNivelVaiDoSilencioAoMaximoDoMicrofone() {
        Proximidade p = new Proximidade(30);
        quadro(p, silencio(QUADRO_MS));
        assertEquals(Proximidade.PISO, p.nivel());
        quadro(p, som(57, QUADRO_MS)); // um tom no máximo, sem cortar
        assertEquals(57, p.nivel());
    }

    @Test
    public void oQuadroIncompletoTambemConta() {
        Proximidade p = new Proximidade(30);
        byte[] pcm = som(40, 50); // menos que um quadro: o fim de uma leitura
        assertTrue(p.passa(pcm, pcm.length));
        assertFalse(new Proximidade(30).passa(pcm, 0));
    }
}
