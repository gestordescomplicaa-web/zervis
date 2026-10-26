package com.zervis.voz;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * A única tela: parear e ligar. Aberta pelo QR do painel (zervis-voz://parear), pareia sozinha;
 * aberta pelo ícone, liga a voz e sai. Sem pareamento, pede o endereço e o código.
 */
public final class MainActivity extends Activity {
    private Ajustes ajustes;
    private TextView mensagem;

    @Override
    protected void onCreate(Bundle salvo) {
        super.onCreate(salvo);
        ajustes = new Ajustes(this);
        tratar(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        tratar(intent);
    }

    private void tratar(Intent intent) {
        Uri link = intent.getData();
        if (link != null && "zervis-voz".equals(link.getScheme())) {
            String e = link.getQueryParameter("e");
            String c = link.getQueryParameter("c");
            if (e != null && c != null) {
                formulario(e, c);
                parear(e, c);
                return;
            }
        }
        if (ajustes.pareado()) {
            ligar();
        } else {
            formulario("", "");
        }
    }

    private void formulario(String endereco, String codigo) {
        LinearLayout tela = new LinearLayout(this);
        tela.setOrientation(LinearLayout.VERTICAL);
        int m = (int) (20 * getResources().getDisplayMetrics().density);
        tela.setPadding(m, m, m, m);
        TextView titulo = new TextView(this);
        titulo.setText("Parear com o Zé\nNo painel: Voz → App de voz → Parear celular.");
        tela.addView(titulo);
        EditText campoEndereco = new EditText(this);
        campoEndereco.setHint("ze.seudominio.com.br");
        campoEndereco.setText(endereco);
        campoEndereco.setInputType(InputType.TYPE_TEXT_VARIATION_URI);
        tela.addView(campoEndereco);
        EditText campoCodigo = new EditText(this);
        campoCodigo.setHint("Código");
        campoCodigo.setText(codigo);
        campoCodigo.setInputType(InputType.TYPE_TEXT_FLAG_CAP_CHARACTERS);
        tela.addView(campoCodigo);
        Button botao = new Button(this);
        botao.setText("Parear");
        botao.setOnClickListener(v -> parear(campoEndereco.getText().toString(), campoCodigo.getText().toString()));
        tela.addView(botao);
        mensagem = new TextView(this);
        mensagem.setGravity(Gravity.CENTER_HORIZONTAL);
        tela.addView(mensagem);
        setContentView(tela);
    }

    private void parear(String digitado, String codigo) {
        String endereco = Pareamento.endereco(digitado);
        if (mensagem != null) mensagem.setText("Pareando…");
        new Thread(() -> {
            try {
                String chave = Pareamento.parear(endereco, codigo);
                ajustes.parear(endereco, chave);
                runOnUiThread(() -> {
                    Toast.makeText(this, "Pareado com o Zé.", Toast.LENGTH_SHORT).show();
                    ligar();
                });
            } catch (IOException erro) {
                String texto = erro.getMessage() != null ? erro.getMessage() : "Sem conexão com o Zé.";
                runOnUiThread(() -> { if (mensagem != null) mensagem.setText(texto); });
            }
        }, "parear").start();
    }

    private void ligar() {
        List<String> faltam = new ArrayList<>();
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED)
            faltam.add(Manifest.permission.RECORD_AUDIO);
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            faltam.add(Manifest.permission.POST_NOTIFICATIONS);
        if (Build.VERSION.SDK_INT >= 31
                && checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) != PackageManager.PERMISSION_GRANTED)
            faltam.add(Manifest.permission.BLUETOOTH_CONNECT);
        if (!faltam.isEmpty()) {
            requestPermissions(faltam.toArray(new String[0]), 1);
            return;
        }
        // Com a tela aberta: o Android só deixa um serviço de microfone começar em primeiro plano.
        startForegroundService(new Intent(this, VozService.class).setAction(VozService.LIGAR));
        finish();
    }

    @Override
    public void onRequestPermissionsResult(int pedido, String[] permissoes, int[] resultados) {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startForegroundService(new Intent(this, VozService.class).setAction(VozService.LIGAR));
            finish();
        } else {
            Toast.makeText(this, "Sem o microfone, o Zé não ouve.", Toast.LENGTH_LONG).show();
            finish();
        }
    }
}
