package com.zervis.voz;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.util.AttributeSet;
import android.view.View;

/** O nível do microfone ao vivo, com a marca do mínimo da escuta de perto: a barra fica ciano
 * quando a voz passa do mínimo (o Zé ouve) e cinza abaixo dele. */
public final class Medidor extends View {
    private final Paint trilha = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint contorno = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint barra = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint marca = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF caixa = new RectF();
    private final float dp;
    private int nivel;
    private int minimo = Proximidade.PADRAO;

    public Medidor(Context contexto, AttributeSet atributos) {
        super(contexto, atributos);
        dp = getResources().getDisplayMetrics().density;
        trilha.setColor(contexto.getColor(R.color.fundo_2));
        contorno.setStyle(Paint.Style.STROKE);
        contorno.setStrokeWidth(dp);
        contorno.setColor(contexto.getColor(R.color.borda));
        marca.setColor(contexto.getColor(R.color.texto));
    }

    void mostrar(int agora, int minimoAgora) {
        if (agora == nivel && minimoAgora == minimo) return;
        nivel = agora;
        minimo = minimoAgora;
        String rotulo = getResources().getString(R.string.leitura, nivel, minimo);
        setContentDescription(getResources().getString(R.string.nivel) + ": " + rotulo);
        invalidate();
    }

    @Override
    protected void onDraw(Canvas tela) {
        float altura = 12 * dp;
        float topo = (getHeight() - altura) / 2f;
        float raio = altura / 2f;
        caixa.set(0, topo, getWidth(), topo + altura);
        tela.drawRoundRect(caixa, raio, raio, trilha);
        float ate = getWidth() * Math.min(1f, nivel / (float) Proximidade.TETO);
        if (ate > 0) {
            barra.setColor(getContext().getColor(nivel >= minimo ? R.color.acento : R.color.apagado));
            caixa.set(0, topo, Math.max(ate, altura), topo + altura);
            tela.drawRoundRect(caixa, raio, raio, barra);
        }
        caixa.set(0, topo, getWidth(), topo + altura);
        tela.drawRoundRect(caixa, raio, raio, contorno);
        float x = getWidth() * minimo / (float) Proximidade.TETO;
        caixa.set(x - dp, 0, x + dp, getHeight());
        tela.drawRoundRect(caixa, dp, dp, marca);
    }
}
