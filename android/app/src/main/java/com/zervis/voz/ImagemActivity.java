package com.zervis.voz;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.TextView;

import java.io.File;

/** A imagem que o Zé mandou, inteira na tela (aberta pela notificação, {@link Imagem}). Um toque fecha. */
public final class ImagemActivity extends Activity {
    private static final int LADO = 2048;

    @Override
    protected void onCreate(Bundle salvo) {
        super.onCreate(salvo);
        String caminho = getIntent().getStringExtra(Imagem.ARQUIVO);
        File arquivo = caminho != null ? new File(caminho) : null;
        // Só uma imagem da pasta do próprio app (o Intent é dele, mas sem confiar no caminho).
        File pasta = new File(getCacheDir(), Imagem.CANAL);
        Bitmap foto = arquivo != null && pasta.equals(arquivo.getParentFile()) && arquivo.isFile()
                ? Imagem.carregar(arquivo, LADO) : null;
        FrameLayout tela = new FrameLayout(this);
        tela.setBackgroundColor(Color.BLACK);
        tela.setOnClickListener(v -> finish());
        if (foto != null) {
            ImageView imagem = new ImageView(this);
            imagem.setImageBitmap(foto);
            imagem.setScaleType(ImageView.ScaleType.FIT_CENTER);
            imagem.setAdjustViewBounds(true);
            String titulo = getIntent().getStringExtra(Imagem.TITULO);
            imagem.setContentDescription(titulo != null ? titulo : "Imagem do Zé");
            tela.addView(imagem, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        } else {
            TextView aviso = new TextView(this);
            aviso.setText("Imagem indisponível.");
            aviso.setTextColor(Color.WHITE);
            aviso.setGravity(Gravity.CENTER);
            tela.addView(aviso, new FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        }
        setContentView(tela);
    }
}
