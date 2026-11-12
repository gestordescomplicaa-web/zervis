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
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.view.Gravity;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;
import android.widget.Toast;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

/**
 * A tela do app. Aberta pelo QR do painel (zervis-voz://parear), pareia sozinha; sem pareamento,
 * pede o endereço e o código. Pareado, liga a voz e mostra o estado e os ajustes: o modo de ouvir,
 * a escuta de perto (com o nível do microfone ao vivo, para acertar o mínimo), a saída sem fone,
 * o microfone de cada aparelho Bluetooth e a atualização do app. Fechar a tela não desliga a voz.
 */
public final class MainActivity extends Activity {
    static final String ATUALIZAR = "com.zervis.voz.ATUALIZAR"; // a notificação de versão nova

    private Ajustes ajustes;
    private TextView mensagem;
    private long nova; // a versão publicada mais nova que a instalada (0: nenhuma conhecida)
    private final Handler relogio = new Handler(Looper.getMainLooper());
    private TextView estado;
    private ProgressBar medidor;
    private TextView leitura;
    // O estado da voz e o nível do microfone, 6 vezes por segundo, com a tela aberta.
    private final Runnable atualizarAoVivo = new Runnable() {
        @Override
        public void run() {
            if (estado != null) estado.setText(VozService.estadoAgora.isEmpty() ? "Desconectado" : VozService.estadoAgora);
            if (medidor != null) medidor.setProgress(VozService.pertoAgora ? VozService.nivelAgora : 0);
            if (leitura != null) {
                leitura.setText(VozService.pertoAgora
                        ? "Nível agora: " + VozService.nivelAgora + " · mínimo: " + ajustes.nivelPerto()
                        : "Com fone, o microfone já fica perto da boca: passa tudo.");
            }
            relogio.postDelayed(this, 160);
        }
    };

    @Override
    protected void onResume() {
        super.onResume();
        relogio.removeCallbacks(atualizarAoVivo);
        relogio.post(atualizarAoVivo);
    }

    @Override
    protected void onPause() {
        relogio.removeCallbacks(atualizarAoVivo);
        super.onPause();
    }

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

    private void titulo(LinearLayout tela, String conteudo) {
        TextView t = texto(tela, conteudo);
        t.setTextSize(16);
        t.setPadding(0, (int) (14 * getResources().getDisplayMetrics().density), 0, 0);
    }

    private void painel() {
        LinearLayout tela = coluna();
        texto(tela, "Zé Voz " + Atualizacao.nome(this) + "\n" + Uri.parse(ajustes.endereco()).getHost());
        estado = texto(tela, VozService.estadoAgora);

        boolean aoVivo = Ajustes.AO_VIVO.equals(ajustes.modo());
        botao(tela, aoVivo ? "Ouvir: ao vivo" : "Ouvir: “Ei Zé”", () -> {
            ajustes.trocarModo();
            avisarServico();
            painel();
        });

        // A escuta de perto (ADR 0086): pelo microfone do celular, só quem fala junto dele.
        titulo(tela, "Escuta de perto");
        texto(tela, "Ouve só quem fala junto do microfone, como numa ligação. Ignora conversas e ruídos ao redor.");
        boolean perto = ajustes.perto();
        botao(tela, perto ? "Ligada" : "Desligada", () -> {
            ajustes.perto(!perto);
            avisarServico();
            painel();
        });
        if (perto) {
            medidor = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
            medidor.setMax(Proximidade.TETO);
            tela.addView(medidor);
            leitura = texto(tela, "");
            texto(tela, "Mínimo para ouvir (mais alto: mais perto da boca)");
            SeekBar minimo = new SeekBar(this);
            minimo.setMax(Proximidade.MAIOR - Proximidade.MENOR);
            minimo.setProgress(ajustes.nivelPerto() - Proximidade.MENOR);
            minimo.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
                @Override
                public void onProgressChanged(SeekBar barra, int valor, boolean daPessoa) {
                    if (daPessoa) ajustes.nivelPerto(valor + Proximidade.MENOR);
                }

                @Override
                public void onStartTrackingTouch(SeekBar barra) {
                }

                @Override
                public void onStopTrackingTouch(SeekBar barra) {
                    avisarServico(); // o mínimo novo vale na hora
                }
            });
            tela.addView(minimo);
        } else {
            medidor = null;
            leitura = null;
        }

        AudioManager audio = getSystemService(AudioManager.class);
        String aparelho = Rota.aparelho(audio);
        if (aparelho == null && !Rota.temFio(audio)) {
            titulo(tela, "Saída da voz");
            boolean orelha = ajustes.orelha();
            botao(tela, orelha ? "Fone da orelha" : "Alto-falante", () -> {
                ajustes.orelha(!orelha);
                avisarServico();
                painel();
            });
        }
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

        titulo(tela, "Atualização");
        botao(tela, nova > Atualizacao.instalada(this) ? "Atualizar para a 0.1." + nova : "Procurar atualização",
                () -> { if (nova > Atualizacao.instalada(this)) atualizar(); else procurar(); });
        mensagem = texto(tela, "");
        mensagem.setGravity(Gravity.CENTER_HORIZONTAL);

        botao(tela, "Desconectar", () -> {
            startService(new Intent(this, VozService.class).setAction(VozService.DESLIGAR));
            finish();
        });
        botao(tela, "Fechar", this::finish);
        ScrollView rolagem = new ScrollView(this); // a tela cresceu: no celular pequeno, rola
        rolagem.addView(tela);
        setContentView(rolagem);
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
