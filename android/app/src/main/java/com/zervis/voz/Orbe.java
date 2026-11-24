package com.zervis.voz;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.ColorMatrix;
import android.graphics.ColorMatrixColorFilter;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.SweepGradient;
import android.os.SystemClock;
import android.util.AttributeSet;
import android.view.View;

/**
 * O Zé no centro da tela Início, com o estado em volta, como o ícone do painel: respira pronto,
 * ondas saindo enquanto ouve (maiores com a voz), arco girando pensando, pulso com brilho
 * falando, âmbar esperando o "sim", apagado e cinza sem conexão. Anima só com a tela visível e
 * fica parado se o Android estiver com as animações desligadas.
 */
public final class Orbe extends View {
    private static final int ACENTO = 0xFF46D9DE;
    private static final int ALERTA = 0xFFEFBE7C;
    private static final int SUAVE = 0xFF93AAB0;

    private final Paint halo = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint disco = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint borda = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint onda = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint arco = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint imagem = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final ColorMatrixColorFilter cinza;
    private final RectF destino = new RectF();
    private final Bitmap macaco;
    private final float dp;
    private final long inicio = SystemClock.uptimeMillis();
    private String fase = Fase.DESCONECTADO;
    private float nivel; // 0 a 1: o microfone agora
    private float cx;
    private float cy;
    private float raioDisco;
    private float raioArco;
    private float raioHalo;
    private SweepGradient arcoCiano;
    private SweepGradient arcoCinza;

    public Orbe(Context contexto, AttributeSet atributos) {
        super(contexto, atributos);
        dp = getResources().getDisplayMetrics().density;
        macaco = BitmapFactory.decodeResource(getResources(), R.drawable.ze_macaco);
        ColorMatrix semCor = new ColorMatrix();
        semCor.setSaturation(0);
        cinza = new ColorMatrixColorFilter(semCor);
        borda.setStyle(Paint.Style.STROKE);
        borda.setStrokeWidth(1.5f * dp);
        onda.setStyle(Paint.Style.STROKE);
        onda.setStrokeWidth(2 * dp);
        arco.setStyle(Paint.Style.STROKE);
        arco.setStrokeWidth(3 * dp);
        arco.setStrokeCap(Paint.Cap.ROUND);
    }

    /** Muda o estado ({@link Fase}); o desenho acompanha na hora. */
    void fase(String nova) {
        if (nova.equals(fase)) return;
        fase = nova;
        invalidate();
    }

    /** O nível do microfone agora, de 0 a 1: as ondas crescem com a voz. */
    void nivel(float agora) {
        nivel = Math.max(0f, Math.min(1f, agora));
    }

    @Override
    protected void onSizeChanged(int largura, int altura, int antes, int antesAltura) {
        cx = largura / 2f;
        cy = altura / 2f;
        float lado = Math.min(largura, altura);
        raioHalo = lado / 2f;
        raioDisco = lado * 0.383f;
        raioArco = lado * 0.425f;
        // Como o "radial-gradient(circle, …)" da referência: o raio vai até o canto do quadro.
        halo.setShader(new RadialGradient(cx, cy, raioHalo * 1.414f,
                new int[] {0x3346D9DE, 0x0F46D9DE, 0x0046D9DE}, new float[] {0f, 0.45f, 0.7f},
                Shader.TileMode.CLAMP));
        disco.setShader(new RadialGradient(cx, cy - raioDisco * 0.3f, raioDisco * 1.3f,
                new int[] {0xFF12303A, 0xFF0A161D, 0xFF070C11}, new float[] {0f, 0.6f, 1f},
                Shader.TileMode.CLAMP));
        arcoCiano = new SweepGradient(cx, cy, new int[] {0x0046D9DE, 0x0046D9DE, ACENTO},
                new float[] {0f, 0.62f, 1f});
        arcoCinza = new SweepGradient(cx, cy, new int[] {0x0093AAB0, 0x0093AAB0, SUAVE},
                new float[] {0f, 0.62f, 1f});
        float meio = lado * 0.275f; // o macaco: 55% do lado
        destino.set(cx - meio, cy - meio, cx + meio, cy + meio);
    }

    private static float onda(long t, long periodo) {
        return (1f - (float) Math.cos(2 * Math.PI * (t % periodo) / periodo)) / 2f; // 0 a 1 a 0
    }

    @Override
    protected void onDraw(Canvas tela) {
        long t = SystemClock.uptimeMillis() - inicio;
        boolean apagado = !Fase.conectado(fase) || Fase.INATIVO.equals(fase)
                || Fase.SEM_MICROFONE.equals(fase);
        float escala = 1f;
        float brilho = apagado ? 0f : 1f;
        if (Fase.PRONTO.equals(fase)) {
            escala = 1f + 0.025f * onda(t, 4000);
        } else if (Fase.FALANDO.equals(fase)) {
            float p = onda(t, 900);
            escala = 1f + 0.045f * p;
            brilho = 0.7f + 0.3f * p;
        }
        if (brilho > 0) {
            halo.setAlpha((int) (255 * brilho));
            tela.drawCircle(cx, cy, raioHalo, halo);
        }

        boolean ouvindo = Fase.OUVINDO.equals(fase);
        if (ouvindo || Fase.CONFIRMANDO.equals(fase)) {
            onda.setColor(ouvindo ? ACENTO : ALERTA);
            for (int k = 0; k < 2; k++) {
                float f = ((t + k * 800L) % 1600L) / 1600f;
                onda.setAlpha((int) (140 * (1f - f)));
                tela.drawCircle(cx, cy, raioDisco * (1f + (0.3f + 0.15f * nivel) * f), onda);
            }
        }

        boolean conectando = Fase.CONECTANDO.equals(fase);
        if (conectando || Fase.PENSANDO.equals(fase)) {
            long volta = conectando ? 1800 : 1100;
            arco.setShader(conectando ? arcoCinza : arcoCiano);
            arco.setAlpha(conectando ? 180 : 255);
            tela.save();
            tela.rotate(360f * (t % volta) / volta, cx, cy);
            tela.drawCircle(cx, cy, raioArco, arco);
            tela.restore();
        }

        tela.save();
        tela.scale(escala, escala, cx, cy);
        tela.drawCircle(cx, cy, raioDisco, disco);
        if (apagado) {
            borda.setColor(0x4D93AAB0);
            borda.clearShadowLayer();
        } else {
            boolean forte = ouvindo || Fase.FALANDO.equals(fase);
            borda.setColor(Fase.CONFIRMANDO.equals(fase) ? ALERTA : forte ? ACENTO : 0x7346D9DE);
            borda.setShadowLayer(14 * dp, 0, 0, 0x5546D9DE);
        }
        tela.drawCircle(cx, cy, raioDisco, borda);
        imagem.setColorFilter(apagado ? cinza : null);
        imagem.setAlpha(apagado ? 102 : conectando ? 153 : 255);
        tela.drawBitmap(macaco, null, destino, imagem);
        tela.restore();

        if (!apagado && ValueAnimator.areAnimatorsEnabled() && isShown()) postInvalidateOnAnimation();
    }
}
