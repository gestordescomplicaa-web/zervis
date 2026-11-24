package com.zervis.voz;

import android.app.Activity;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Bundle;
import android.view.View;
import android.widget.ImageView;
import android.widget.TextView;

import java.io.File;

/** A imagem que o Zé mandou, inteira na tela (aberta pela notificação, {@link Imagem}): o título no
 * alto, "Fechar" (ou um toque na foto) e, na foto que está na galeria, "Compartilhar". */
public final class ImagemActivity extends Activity {
    private static final int LADO = 2048;

    @Override
    protected void onCreate(Bundle salvo) {
        super.onCreate(salvo);
        setContentView(R.layout.tela_imagem);
        String caminho = getIntent().getStringExtra(Imagem.ARQUIVO);
        File arquivo = caminho != null ? new File(caminho) : null;
        // Só uma imagem da pasta do próprio app (o Intent é dele, mas sem confiar no caminho).
        File pasta = new File(getCacheDir(), Imagem.CANAL);
        Bitmap foto = arquivo != null && pasta.equals(arquivo.getParentFile()) && arquivo.isFile()
                ? Imagem.carregar(arquivo, LADO) : null;
        String titulo = getIntent().getStringExtra(Imagem.TITULO);
        if (titulo == null) titulo = getString(R.string.imagem_do_ze);
        ((TextView) findViewById(R.id.titulo)).setText(titulo);
        findViewById(R.id.fechar).setOnClickListener(v -> finish());
        ImageView imagem = findViewById(R.id.foto);
        if (foto == null) {
            imagem.setVisibility(View.GONE);
            findViewById(R.id.indisponivel).setVisibility(View.VISIBLE);
            return;
        }
        imagem.setImageBitmap(foto);
        imagem.setContentDescription(titulo);
        imagem.setOnClickListener(v -> finish());
        String galeria = getIntent().getStringExtra(Imagem.GALERIA);
        if (galeria != null && galeria.startsWith("content://media/")) {
            View enviar = findViewById(R.id.compartilhar);
            String nome = titulo;
            enviar.setVisibility(View.VISIBLE);
            enviar.setOnClickListener(v -> startActivity(Imagem.compartilhar(Uri.parse(galeria), nome)));
        }
    }
}
