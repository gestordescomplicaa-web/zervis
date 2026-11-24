package com.zervis.voz;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.ColorStateList;
import android.media.AudioManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.view.View;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.IOException;
import java.net.ConnectException;
import java.net.SocketTimeoutException;
import java.net.UnknownHostException;
import java.util.ArrayList;
import java.util.List;

/**
 * As telas Parear e Início. Aberta pelo QR do painel (zervis-voz://parear), pareia sozinha; sem
 * pareamento, pede o endereço e o código. Pareada, liga a voz e mostra o Início: o Zé no centro com
 * o estado em volta ({@link Orbe}), o modo de ouvir e o botão de falar. Os ajustes ficam em
 * {@link AjustesActivity}. Fechar a tela não desliga a voz; "Desconectar", nos ajustes, desliga.
 */
public final class MainActivity extends Activity {
    private static final int PAREAR = 1;
    private static final int INICIO = 2;
    private static final long TIQUE_MS = 160;
    private static final long ROTA_MS = 1000;

    private Ajustes ajustes;
    private int tela;
    private final Handler relogio = new Handler(Looper.getMainLooper());
    private long rotaEm;

    // Parear
    private EditText campoEndereco;
    private EditText campoCodigo;
    private TextView mensagem;
    private View parearBotao;
    private TextView parearTexto;

    // Início
    private Orbe orbe;
    private TextView estado;
    private TextView dica;
    private View ponto;
    private TextView conexao;
    private Button modoChamado;
    private Button modoAoVivo;
    private View falar;
    private ImageView falarIcone;
    private TextView falarTexto;
    private ImageView saidaIcone;
    private TextView saida;
    private TextView microfone;

    // O estado da voz e o nível do microfone, 6 vezes por segundo, com a tela aberta.
    private final Runnable aoVivo = new Runnable() {
        @Override
        public void run() {
            if (tela == INICIO) {
                if (!ajustes.pareado()) {
                    // O Zé recusou a chave (o celular foi removido no painel): parear de novo.
                    mostrarParear("", "", getString(R.string.parear_de_novo));
                } else {
                    atualizarInicio();
                }
            }
            relogio.postDelayed(this, TIQUE_MS);
        }
    };

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

    @Override
    protected void onResume() {
        super.onResume();
        relogio.removeCallbacks(aoVivo);
        relogio.post(aoVivo);
        if (orbe != null) orbe.invalidate(); // a animação volta com a tela
    }

    @Override
    protected void onPause() {
        relogio.removeCallbacks(aoVivo);
        super.onPause();
    }

    private void tratar(Intent intent) {
        String acao = intent.getAction();
        // A atualização (o aviso e o resultado do instalador) mora nos ajustes; o app antigo
        // apontava para cá.
        if (Atualizacao.RESULTADO.equals(acao) || AjustesActivity.ATUALIZAR.equals(acao)) {
            startActivity(new Intent(intent).setClass(this, AjustesActivity.class));
            if (tela == 0) {
                if (ajustes.pareado()) mostrarInicio(); else mostrarParear("", "", null);
            }
            return;
        }
        Uri link = intent.getData();
        if (link != null && "zervis-voz".equals(link.getScheme())) {
            String e = link.getQueryParameter("e");
            String c = link.getQueryParameter("c");
            if (e != null && c != null) {
                mostrarParear(e, c, null);
                parear(e, c);
                return;
            }
        }
        if (!ajustes.pareado()) {
            mostrarParear("", "", null);
            return;
        }
        ligar();
    }

    // --- parear ----------------------------------------------------------------------------

    private void mostrarParear(String endereco, String codigo, String aviso) {
        tela = PAREAR;
        orbe = null;
        setContentView(R.layout.tela_parear);
        campoEndereco = findViewById(R.id.campoEndereco);
        campoCodigo = findViewById(R.id.campoCodigo);
        mensagem = findViewById(R.id.mensagem);
        parearBotao = findViewById(R.id.parear);
        parearTexto = findViewById(R.id.parearTexto);
        campoEndereco.setText(endereco);
        campoCodigo.setText(codigo);
        campoCodigo.setOnEditorActionListener((v, acao, evento) -> {
            if (acao != EditorInfo.IME_ACTION_DONE) return false;
            pedirPareamento();
            return true;
        });
        parearBotao.setOnClickListener(v -> pedirPareamento());
        if (aviso != null) avisar(aviso, true);
    }

    private void pedirPareamento() {
        // Sem o teclado: a mensagem (erro ou "Pareando…") aparece embaixo dos campos.
        InputMethodManager teclado = getSystemService(InputMethodManager.class);
        teclado.hideSoftInputFromWindow(campoCodigo.getWindowToken(), 0);
        parear(campoEndereco.getText().toString(), campoCodigo.getText().toString());
    }

    private void avisar(String texto, boolean erro) {
        mensagem.setText(texto);
        mensagem.setTextColor(getColor(erro ? R.color.erro : R.color.suave));
        mensagem.setVisibility(View.VISIBLE);
    }

    private void parear(String digitado, String codigo) {
        if (digitado.trim().isEmpty() || codigo.trim().isEmpty()) {
            avisar(getString(R.string.preencha), true);
            return;
        }
        String endereco = Pareamento.endereco(digitado);
        parearBotao.setEnabled(false);
        parearTexto.setText(R.string.pareando);
        mensagem.setVisibility(View.GONE);
        campoCodigo.setBackgroundResource(R.drawable.campo);
        new Thread(() -> {
            try {
                String chave = Pareamento.parear(endereco, codigo.trim());
                ajustes.parear(endereco, chave);
                runOnUiThread(() -> {
                    Toast.makeText(this, R.string.pareado, Toast.LENGTH_SHORT).show();
                    ligar();
                });
            } catch (IOException erro) {
                boolean rede = erro instanceof UnknownHostException || erro instanceof ConnectException
                        || erro instanceof SocketTimeoutException || erro.getMessage() == null;
                String texto = rede ? getString(R.string.sem_conexao_com_o_ze) : erro.getMessage();
                runOnUiThread(() -> {
                    if (tela != PAREAR) return;
                    parearBotao.setEnabled(true);
                    parearTexto.setText(R.string.parear);
                    campoCodigo.setBackgroundResource(R.drawable.campo_erro);
                    avisar(texto, true);
                });
            }
        }, "parear").start();
    }

    // --- ligar -------------------------------------------------------------------------------

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
        if (tela != INICIO) mostrarInicio();
        if (!faltam.isEmpty()) {
            requestPermissions(faltam.toArray(new String[0]), 1);
            return;
        }
        // Com a tela aberta: o Android só deixa um serviço de microfone começar em primeiro plano.
        startForegroundService(new Intent(this, VozService.class).setAction(VozService.LIGAR));
    }

    @Override
    public void onRequestPermissionsResult(int pedido, String[] permissoes, int[] resultados) {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            startForegroundService(new Intent(this, VozService.class).setAction(VozService.LIGAR));
        } else {
            Toast.makeText(this, R.string.sem_microfone, Toast.LENGTH_LONG).show();
        }
    }

    private void avisarServico() {
        startService(new Intent(this, VozService.class).setAction(VozService.AJUSTAR));
    }

    // --- início ------------------------------------------------------------------------------

    private void mostrarInicio() {
        tela = INICIO;
        setContentView(R.layout.tela_inicio);
        orbe = findViewById(R.id.orbe);
        estado = findViewById(R.id.estado);
        dica = findViewById(R.id.dica);
        ponto = findViewById(R.id.ponto);
        conexao = findViewById(R.id.conexao);
        modoChamado = findViewById(R.id.modoChamado);
        modoAoVivo = findViewById(R.id.modoAoVivo);
        falar = findViewById(R.id.falar);
        falarIcone = findViewById(R.id.falarIcone);
        falarTexto = findViewById(R.id.falarTexto);
        saidaIcone = findViewById(R.id.saidaIcone);
        saida = findViewById(R.id.saida);
        microfone = findViewById(R.id.microfone);
        TextView endereco = findViewById(R.id.endereco);
        endereco.setText(Uri.parse(ajustes.endereco()).getHost());
        findViewById(R.id.ajustes).setOnClickListener(v -> startActivity(new Intent(this, AjustesActivity.class)));
        modoChamado.setOnClickListener(v -> escolherModo(Ajustes.CHAMADO));
        modoAoVivo.setOnClickListener(v -> escolherModo(Ajustes.AO_VIVO));
        falar.setOnClickListener(v -> tocarNoBotao());
        rotaEm = 0;
        atualizarInicio();
    }

    private void escolherModo(String modo) {
        if (modo.equals(ajustes.modo())) return;
        ajustes.modo(modo);
        avisarServico(); // o modo novo vale numa conexão nova: o serviço reconecta
        atualizarInicio();
    }

    private void tocarNoBotao() {
        if (!VozService.ligadoAgora) {
            ligar();
            return;
        }
        // Falar e Enviar; desconectado (caiu ou outro aparelho assumiu), o mesmo reconecta.
        startService(new Intent(this, VozService.class).setAction(VozService.FALAR));
    }

    private static void texto(TextView v, String t) {
        if (!t.contentEquals(v.getText())) v.setText(t); // sem repetir o anúncio da leitura de tela
    }

    private void atualizarInicio() {
        String fase = VozService.fase();
        orbe.fase(fase);
        orbe.nivel(VozService.nivelAgora / (float) Proximidade.TETO);
        boolean aoVivoAgora = Ajustes.AO_VIVO.equals(ajustes.modo());
        modoChamado.setSelected(!aoVivoAgora);
        modoAoVivo.setSelected(aoVivoAgora);

        int titulo;
        int chip = R.string.chip_conectado;
        int cor = R.color.bom;
        int botao = R.string.falar;
        int icone = R.drawable.ic_mic;
        String explicacao;
        boolean pode = true;
        switch (fase) {
            case Fase.DESCONECTADO:
                titulo = R.string.fase_desconectado;
                explicacao = getString(R.string.dica_desconectado);
                chip = R.string.chip_desconectado;
                cor = R.color.suave;
                botao = R.string.conectar;
                icone = R.drawable.ic_desligar;
                break;
            case Fase.CONECTANDO:
                titulo = R.string.fase_conectando;
                explicacao = getString(R.string.dica_conectando);
                chip = R.string.chip_conectando;
                cor = R.color.alerta;
                pode = false;
                break;
            case Fase.SEM_REDE:
                titulo = R.string.fase_sem_rede;
                long falta = Math.max(1, (VozService.tentarEm - SystemClock.elapsedRealtime() + 999) / 1000);
                explicacao = getString(R.string.dica_sem_rede, (int) falta);
                chip = R.string.chip_sem_rede;
                cor = R.color.alerta;
                botao = R.string.tentar_agora;
                icone = R.drawable.ic_atualizar;
                break;
            case Fase.EM_USO:
                titulo = R.string.fase_em_uso;
                explicacao = getString(R.string.dica_em_uso);
                chip = R.string.chip_em_uso;
                cor = R.color.suave;
                botao = R.string.retomar;
                break;
            case Fase.SEM_MICROFONE:
                titulo = R.string.fase_sem_microfone;
                explicacao = getString(R.string.dica_sem_microfone);
                pode = false;
                break;
            case Fase.OUVINDO:
                titulo = R.string.fase_ouvindo;
                boolean apertado = VozService.apertadoAgora;
                explicacao = getString(apertado ? R.string.dica_apertado : R.string.dica_ouvindo);
                if (apertado) {
                    botao = R.string.enviar;
                    icone = R.drawable.ic_enviar;
                }
                break;
            case Fase.PENSANDO:
                titulo = R.string.fase_pensando;
                explicacao = getString(R.string.dica_pensando);
                break;
            case Fase.FALANDO:
                titulo = R.string.fase_falando;
                explicacao = getString(R.string.dica_falando);
                break;
            case Fase.CONFIRMANDO:
                titulo = R.string.fase_confirmando;
                explicacao = getString(R.string.dica_confirmando);
                break;
            case Fase.INATIVO:
                titulo = R.string.fase_inativo;
                explicacao = getString(R.string.dica_inativo);
                break;
            default:
                titulo = R.string.fase_pronto;
                explicacao = getString(aoVivoAgora ? R.string.dica_ao_vivo : R.string.dica_chamado);
        }
        texto(estado, getString(titulo));
        texto(dica, explicacao);
        texto(conexao, getString(chip));
        ponto.setBackgroundTintList(ColorStateList.valueOf(getColor(cor)));
        texto(falarTexto, getString(botao));
        falarIcone.setImageResource(icone);
        falar.setEnabled(pode);
        falar.setAlpha(pode ? 1f : 0.55f);
        if (SystemClock.elapsedRealtime() >= rotaEm) {
            rotaEm = SystemClock.elapsedRealtime() + ROTA_MS;
            mostrarRota();
        }
    }

    /** Por onde a fala sai e quem é o microfone agora, numa linha. */
    private void mostrarRota() {
        AudioManager audio = getSystemService(AudioManager.class);
        String aparelho = Rota.aparelho(audio);
        if (aparelho != null) {
            boolean doFone = Rota.temMicrofone(audio) && !ajustes.microfoneDoCelular(aparelho);
            saidaIcone.setImageResource(R.drawable.ic_fone);
            texto(saida, aparelho);
            texto(microfone, getString(doFone ? R.string.microfone_do_fone : R.string.microfone_do_celular));
        } else if (Rota.temFio(audio)) {
            saidaIcone.setImageResource(R.drawable.ic_fone);
            texto(saida, getString(R.string.saida_fio));
            texto(microfone, getString(R.string.microfone_do_fone));
        } else {
            saidaIcone.setImageResource(R.drawable.ic_alto_falante);
            texto(saida, getString(ajustes.orelha() ? R.string.saida_orelha : R.string.saida_alto_falante));
            texto(microfone, getString(R.string.microfone_do_celular));
        }
    }
}
