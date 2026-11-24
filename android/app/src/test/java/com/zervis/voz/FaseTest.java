package com.zervis.voz;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class FaseTest {
    private static final long AGORA = 100_000;

    private static String conectado(boolean apertado, String doZe, long falaAte, long esperaAte) {
        return Fase.de(true, false, true, "", apertado, doZe, falaAte, esperaAte, AGORA);
    }

    @Test
    public void conexaoVemAntesDeTudo() {
        assertEquals(Fase.DESCONECTADO, Fase.de(false, false, false, "", true, "falando", 0, 0, AGORA));
        assertEquals(Fase.CONECTANDO, Fase.de(true, true, false, "", false, "", 0, 0, AGORA));
        assertEquals(Fase.EM_USO, Fase.de(true, false, false, Fase.EM_USO, false, "", 0, 0, AGORA));
        assertEquals(Fase.SEM_REDE, Fase.de(true, false, false, "", false, "", 0, 0, AGORA));
        assertEquals(Fase.SEM_MICROFONE, Fase.de(true, false, true, Fase.SEM_MICROFONE, false, "", 0, 0, AGORA));
    }

    @Test
    public void oEstadoDoZeManda() {
        assertEquals(Fase.PRONTO, conectado(false, "ativo", 0, 0));
        assertEquals(Fase.OUVINDO, conectado(false, "ouvindo", 0, 0));
        assertEquals(Fase.PENSANDO, conectado(false, "pensando", 0, 0));
        assertEquals(Fase.FALANDO, conectado(false, "falando", 0, 0));
        assertEquals(Fase.CONFIRMANDO, conectado(false, "confirmando", 0, 0));
        assertEquals(Fase.INATIVO, conectado(false, "inativo", 0, 0));
    }

    @Test
    public void oQueAconteceAquiVemAntesDoEstadoDoZe() {
        // A fala tocando no celular (o Bluetooth atrasa) e o botão apertado.
        assertEquals(Fase.FALANDO, conectado(false, "ativo", AGORA + 500, 0));
        assertEquals(Fase.OUVINDO, conectado(true, "ativo", 0, 0));
    }

    @Test
    public void semOEstadoDoZeOPedidoEnviadoEsperaPensando() {
        assertEquals(Fase.PENSANDO, conectado(false, "", 0, AGORA + 1));
        assertEquals(Fase.PRONTO, conectado(false, "", 0, AGORA - 1));
        // Com o estado do Zé, a espera local não vale: ele diz quando está pensando.
        assertEquals(Fase.PRONTO, conectado(false, "ativo", 0, AGORA + 1));
    }

    @Test
    public void conectadoParaATela() {
        assertTrue(Fase.conectado(Fase.PRONTO));
        assertTrue(Fase.conectado(Fase.SEM_MICROFONE));
        assertFalse(Fase.conectado(Fase.SEM_REDE));
        assertFalse(Fase.conectado(Fase.EM_USO));
    }
}
