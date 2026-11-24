package com.zervis.voz;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageInstaller;
import android.content.res.ColorStateList;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.provider.Settings;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.SeekBar;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import java.io.IOException;

/**
 * Os ajustes do app: a escuta de perto (com o nível do microfone ao vivo, para acertar o mínimo),
 * o áudio (a saída sem fone, ou o microfone do aparelho Bluetooth conectado), a versão e a
 * atualização, e desconectar. O aviso de versão nova e o resultado do instalador abrem aqui.
 */
public final class AjustesActivity extends Activity {
    static final String ATUALIZAR = "com.zervis.voz.ATUALIZAR"; // a notificação de versão nova
    private static final long TIQUE_MS = 160;
    private static final long ROTA_MS = 1000;

    private Ajustes ajustes;
    private final Handler relogio = new Handler(Looper.getMainLooper());
    private long nova; // a versão publicada mais nova que a instalada (0: nenhuma conhecida)
    private long rotaEm;
    private boolean fone; // o microfone é o de um fone (Bluetooth ou com fio): a escuta de perto não vale

    private Switch perto;
    private View pertoBloco;
    private TextView pertoComFone;
    private Medidor medidor;
    private TextView leitura;
    private TextView audioRotulo;
    private View audioOpcoes;
    private Button audioA;
    private Button audioB;
    private TextView audioNota;
    private View atualizarBotao;
    private ImageView atualizarIcone;
    private TextView atualizarTexto;
    private TextView atualizarMensagem;

    private final Runnable aoVivo = new Runnable() {
        @Override
        public void run() {
            if (SystemClock.elapsedRealtime() >= rotaEm) {
                rotaEm = SystemClock.elapsedRealtime() + ROTA_MS;
                mostrarAudio();
            }
            int nivel = VozService.pertoAgora ? VozService.nivelAgora : 0;
            medidor.mostrar(nivel, ajustes.nivelPerto());
            String texto = getString(R.string.leitura, nivel, ajustes.nivelPerto());
            if (!texto.contentEquals(leitura.getText())) leitura.setText(texto);
            relogio.postDelayed(this, TIQUE_MS);
        }
    };

    @Override
    protected void onCreate(Bundle salvo) {
        super.onCreate(salvo);
        ajustes = new Ajustes(this);
        setContentView(R.layout.tela_ajustes);
        perto = findViewById(R.id.perto);
        pertoBloco = findViewById(R.id.pertoBloco);
        pertoComFone = findViewById(R.id.pertoComFone);
        medidor = findViewById(R.id.medidor);
        leitura = findViewById(R.id.leitura);
        audioRotulo = findViewById(R.id.audioRotulo);
        audioOpcoes = findViewById(R.id.audioOpcoes);
        audioA = findViewById(R.id.audioA);
        audioB = findViewById(R.id.audioB);
        audioNota = findViewById(R.id.audioNota);
        atualizarBotao = findViewById(R.id.atualizar);
        atualizarIcone = findViewById(R.id.atualizarIcone);
        atualizarTexto = findViewById(R.id.atualizarTexto);
        atualizarMensagem = findViewById(R.id.atualizarMensagem);

        findViewById(R.id.voltar).setOnClickListener(v -> finish());
        perto.setChecked(ajustes.perto());
        perto.setOnCheckedChangeListener((v, ligada) -> {
            ajustes.perto(ligada);
            avisarServico();
            mostrarPerto();
        });
        SeekBar minimo = findViewById(R.id.minimo);
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

        ((TextView) findViewById(R.id.versao)).setText(getString(R.string.versao, Atualizacao.nome(this)));
        atualizarBotao.setOnClickListener(v -> {
            if (nova > Atualizacao.instalada(this)) atualizar(); else procurar();
        });
        ((TextView) findViewById(R.id.enderecoAjustes)).setText(Uri.parse(ajustes.endereco()).getHost());
        findViewById(R.id.desconectar).setOnClickListener(v -> {
            startService(new Intent(this, VozService.class).setAction(VozService.DESLIGAR));
            finish();
        });
        mostrarAtualizacao();
        mostrarAudio();
        tratar(getIntent());
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        tratar(intent);
    }

    @Override
    protected void onResume() {
        super.onResume();
        rotaEm = 0;
        relogio.removeCallbacks(aoVivo);
        relogio.post(aoVivo);
    }

    @Override
    protected void onPause() {
        relogio.removeCallbacks(aoVivo);
        super.onPause();
    }

    private void tratar(Intent intent) {
        if (Atualizacao.RESULTADO.equals(intent.getAction())) instalado(intent);
        else if (ATUALIZAR.equals(intent.getAction())) procurar();
    }

    private void avisarServico() {
        startService(new Intent(this, VozService.class).setAction(VozService.AJUSTAR));
    }

    // --- escuta de perto e áudio ---------------------------------------------------------------

    private void mostrarPerto() {
        boolean ligada = ajustes.perto();
        pertoBloco.setVisibility(ligada && !fone ? View.VISIBLE : View.GONE);
        pertoComFone.setVisibility(ligada && fone ? View.VISIBLE : View.GONE);
    }

    /** O cartão Áudio pelo que está conectado agora: sem fone, a saída; num aparelho Bluetooth com
     * microfone, de quem é o microfone; numa caixa sem microfone e no fone com fio, só a nota. */
    private void mostrarAudio() {
        AudioManager audio = getSystemService(AudioManager.class);
        String aparelho = Rota.aparelho(audio);
        boolean fio = Rota.temFio(audio);
        if (aparelho != null && Rota.temMicrofone(audio)) {
            boolean celular = ajustes.microfoneDoCelular(aparelho);
            fone = !celular;
            opcoes(getString(R.string.microfone), getString(R.string.do_celular),
                    getString(R.string.de_aparelho, aparelho), celular,
                    () -> ajustes.microfoneDoCelular(aparelho, true),
                    () -> ajustes.microfoneDoCelular(aparelho, false));
            nota(getString(R.string.nota_aparelho, aparelho));
        } else if (aparelho != null) {
            fone = false;
            semOpcoes(getString(R.string.nota_caixa, aparelho));
        } else if (fio) {
            fone = true;
            semOpcoes(getString(R.string.nota_fio));
        } else {
            fone = false;
            opcoes(getString(R.string.saida_da_voz), getString(R.string.saida_alto_falante),
                    getString(R.string.saida_orelha), !ajustes.orelha(),
                    () -> ajustes.orelha(false), () -> ajustes.orelha(true));
            nota(null);
        }
        mostrarPerto();
    }

    private void opcoes(String rotulo, String a, String b, boolean primeira, Runnable escolherA, Runnable escolherB) {
        audioRotulo.setVisibility(View.VISIBLE);
        audioRotulo.setText(rotulo);
        audioOpcoes.setVisibility(View.VISIBLE);
        audioOpcoes.setContentDescription(rotulo);
        audioA.setText(a);
        audioB.setText(b);
        audioA.setSelected(primeira);
        audioB.setSelected(!primeira);
        audioA.setOnClickListener(v -> { escolherA.run(); avisarServico(); mostrarAudio(); });
        audioB.setOnClickListener(v -> { escolherB.run(); avisarServico(); mostrarAudio(); });
    }

    private void semOpcoes(String texto) {
        audioRotulo.setVisibility(View.GONE);
        audioOpcoes.setVisibility(View.GONE);
        nota(texto);
    }

    private void nota(String texto) {
        audioNota.setVisibility(texto == null ? View.GONE : View.VISIBLE);
        if (texto != null) audioNota.setText(texto);
    }

    // --- atualização -------------------------------------------------------------------------

    /** Com versão nova, o botão vira o principal (ciano): "Atualizar para a 0.1.N". */
    private void mostrarAtualizacao() {
        boolean tem = nova > Atualizacao.instalada(this);
        atualizarTexto.setText(tem ? getString(R.string.atualizar_para, "0.1." + nova) : getString(R.string.procurar_atualizacao));
        atualizarBotao.setBackgroundResource(tem ? R.drawable.botao_principal : R.drawable.botao_secundario);
        int cor = getColor(tem ? R.color.sobre_acento : R.color.texto);
        atualizarTexto.setTextColor(cor);
        atualizarIcone.setImageTintList(ColorStateList.valueOf(cor));
    }

    private void mensagem(String texto) {
        atualizarMensagem.setVisibility(texto == null ? View.GONE : View.VISIBLE);
        if (texto != null) atualizarMensagem.setText(texto);
    }

    private void procurar() {
        atualizarTexto.setText(R.string.procurando);
        mensagem(null);
        new Thread(() -> {
            try {
                long publicada = Atualizacao.publicada();
                ajustes.procurou(System.currentTimeMillis());
                runOnUiThread(() -> {
                    nova = publicada;
                    mostrarAtualizacao();
                    mensagem(getString(publicada > Atualizacao.instalada(this) ? R.string.versao_nova : R.string.versao_mais_recente));
                });
            } catch (IOException erro) {
                runOnUiThread(() -> {
                    mostrarAtualizacao();
                    mensagem(erro.getMessage());
                });
            }
        }, "procurar").start();
    }

    private void atualizar() {
        // A primeira vez, o Android pede para deixar o Zé Voz instalar apps; depois, só a confirmação.
        if (!getPackageManager().canRequestPackageInstalls()) {
            Toast.makeText(this, R.string.permitir_instalar, Toast.LENGTH_LONG).show();
            startActivity(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + getPackageName())));
            return;
        }
        atualizarTexto.setText(R.string.baixando);
        new Thread(() -> {
            try {
                Atualizacao.instalar(this);
            } catch (IOException erro) {
                runOnUiThread(() -> {
                    mostrarAtualizacao();
                    mensagem(erro.getMessage());
                });
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
            Toast.makeText(this, R.string.atualizado, Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        String motivo = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE);
        mostrarAtualizacao();
        mensagem(motivo != null ? getString(R.string.nao_atualizou_motivo, motivo) : getString(R.string.nao_atualizou));
    }
}
