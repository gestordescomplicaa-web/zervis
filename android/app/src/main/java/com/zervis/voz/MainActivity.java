package com.zervis.voz;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInstaller;
import android.content.pm.PackageManager;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
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
 * A única tela. Aberta pelo QR do painel (zervis-voz://parear), pareia sozinha; sem pareamento,
 * pede o endereço e o código. Pareado, liga a voz e mostra os ajustes: o modo de ouvir, o
 * microfone de cada aparelho Bluetooth e a atualização do app. Fechar a tela não desliga a voz.
 */
public final class MainActivity extends Activity {
    static final String ATUALIZAR = "com.zervis.voz.ATUALIZAR"; // a notificação de versão nova

    private Ajustes ajustes;
    private TextView mensagem;
    private long nova; // a versão publicada mais nova que a instalada (0: nenhuma conhecida)

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
        if (Atualizacao.RESULTADO.equals(intent.getAction())) {
            instalado(intent);
            return;
        }
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
        if (!ajustes.pareado()) {
            formulario("", "");
            return;
        }
        ligar();
        if (ATUALIZAR.equals(intent.getAction())) procurar();
    }

    // --- parear ----------------------------------------------------------------------------

    private LinearLayout coluna() {
        LinearLayout tela = new LinearLayout(this);
        tela.setOrientation(LinearLayout.VERTICAL);
        int m = (int) (20 * getResources().getDisplayMetrics().density);
        tela.setPadding(m, m, m, m);
        return tela;
    }

    private TextView texto(LinearLayout tela, String conteudo) {
        TextView t = new TextView(this);
        t.setText(conteudo);
        tela.addView(t);
        return t;
    }

    private Button botao(LinearLayout tela, String rotulo, Runnable ao) {
        Button b = new Button(this);
        b.setText(rotulo);
        b.setAllCaps(false);
        b.setOnClickListener(v -> ao.run());
        tela.addView(b);
        return b;
    }

    private void formulario(String endereco, String codigo) {
        LinearLayout tela = coluna();
        texto(tela, "Parear com o Zé\nNo painel: Voz → App de voz → Parear celular.");
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
        botao(tela, "Parear", () -> parear(campoEndereco.getText().toString(), campoCodigo.getText().toString()));
        mensagem = texto(tela, "");
        mensagem.setGravity(Gravity.CENTER_HORIZONTAL);
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

    // --- ligar e ajustar ---------------------------------------------------------------------

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
        painel();
    }

    @Override
    public void onRequestPermissionsResult(int pedido, String[] permissoes, int[] resultados) {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startForegroundService(new Intent(this, VozService.class).setAction(VozService.LIGAR));
            painel();
        } else {
            Toast.makeText(this, "Sem o microfone, o Zé não ouve.", Toast.LENGTH_LONG).show();
            finish();
        }
    }

    private void avisarServico() {
        startService(new Intent(this, VozService.class).setAction(VozService.AJUSTAR));
    }

    private void painel() {
        LinearLayout tela = coluna();
        texto(tela, "Zé Voz " + Atualizacao.nome(this) + "\n" + Uri.parse(ajustes.endereco()).getHost());

        boolean aoVivo = Ajustes.AO_VIVO.equals(ajustes.modo());
        botao(tela, aoVivo ? "Ouvir: ao vivo" : "Ouvir: “Ei Zé”", () -> {
            ajustes.trocarModo();
            avisarServico();
            painel();
        });

        AudioManager audio = getSystemService(AudioManager.class);
        String aparelho = Rota.aparelho(audio);
        if (aparelho != null) {
            if (Rota.temMicrofone(audio)) {
                boolean celular = ajustes.microfoneDoCelular(aparelho);
                botao(tela, celular ? "Microfone: do celular" : "Microfone: de " + aparelho, () -> {
                    ajustes.microfoneDoCelular(aparelho, !celular);
                    avisarServico();
                    painel();
                });
                texto(tela, "Vale para " + aparelho + ". A fala sai sempre por ele.");
            } else {
                texto(tela, aparelho + ": a fala sai por ele; o microfone é o do celular.");
            }
        }

        botao(tela, nova > Atualizacao.instalada(this) ? "Atualizar para a 0.1." + nova : "Procurar atualização",
                () -> { if (nova > Atualizacao.instalada(this)) atualizar(); else procurar(); });
        mensagem = texto(tela, "");
        mensagem.setGravity(Gravity.CENTER_HORIZONTAL);

        botao(tela, "Desconectar", () -> {
            startService(new Intent(this, VozService.class).setAction(VozService.DESLIGAR));
            finish();
        });
        botao(tela, "Fechar", this::finish);
        setContentView(tela);
    }

    // --- atualização -------------------------------------------------------------------------

    private void procurar() {
        if (mensagem != null) mensagem.setText("Procurando…");
        new Thread(() -> {
            try {
                long publicada = Atualizacao.publicada();
                ajustes.procurou(System.currentTimeMillis());
                runOnUiThread(() -> {
                    nova = publicada;
                    painel();
                    mensagem.setText(publicada > Atualizacao.instalada(this) ? "Versão nova disponível." : "Versão mais recente.");
                });
            } catch (IOException erro) {
                runOnUiThread(() -> { if (mensagem != null) mensagem.setText(erro.getMessage()); });
            }
        }, "procurar").start();
    }

    private void atualizar() {
        // A primeira vez, o Android pede para deixar o Zé Voz instalar apps; depois, só a confirmação.
        if (!getPackageManager().canRequestPackageInstalls()) {
            Toast.makeText(this, "Permita instalar apps do Zé Voz e toque em Atualizar de novo.", Toast.LENGTH_LONG).show();
            startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + getPackageName())));
            return;
        }
        if (mensagem != null) mensagem.setText("Baixando…");
        new Thread(() -> {
            try {
                Atualizacao.instalar(this);
            } catch (IOException erro) {
                runOnUiThread(() -> { if (mensagem != null) mensagem.setText(erro.getMessage()); });
            }
        }, "atualizar").start();
    }

    @SuppressWarnings("deprecation") // a versão com a classe é do Android 13; o app vai do 11
    private void instalado(Intent intent) {
        int status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE);
        if (status == PackageInstaller.STATUS_PENDING_USER_ACTION) {
            Intent confirmar = intent.getParcelableExtra(Intent.EXTRA_INTENT);
            if (confirmar != null) startActivity(confirmar);
            return;
        }
        if (status == PackageInstaller.STATUS_SUCCESS) {
            Toast.makeText(this, "Zé Voz atualizado.", Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        String motivo = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE);
        if (ajustes.pareado()) painel(); else formulario("", "");
        if (mensagem != null) mensagem.setText("Não atualizou" + (motivo != null ? ": " + motivo : "."));
    }
}
