package com.zervis.voz;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.AudioAttributes;
import android.media.AudioDeviceCallback;
import android.media.AudioDeviceInfo;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioRecord;
import android.media.AudioTrack;
import android.media.MediaRecorder;
import android.media.audiofx.AcousticEchoCanceler;
import android.media.session.MediaSession;
import android.media.session.PlaybackState;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.os.PowerManager;
import android.view.KeyEvent;

import org.json.JSONException;
import org.json.JSONObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import okhttp3.WebSocket;
import okhttp3.WebSocketListener;
import okio.ByteString;

/**
 * A voz com o Zé, com a tela bloqueada: o microfone vai em PCM de 16 bits a 16 kHz, em quadros de
 * 80 ms, pelo WebSocket do painel (/voz-app/ws, o mesmo protocolo da voz do navegador, ADR 0024);
 * a fala do Zé volta pelo mesmo canal ({"tipo":"voz","taxa":N}, os pedaços, "fim" ou "parar").
 *
 * Com um fone Bluetooth com microfone, o microfone e a fala vão por ele (o modo de comunicação,
 * como numa ligação). Sem ele (uma caixa de som Bluetooth, o fone com fio, o alto-falante), ou
 * com o aparelho marcado "microfone do celular" na tela, a fala sai como mídia, por onde o celular
 * toca música, e o microfone é o do celular, com o cancelamento de eco quando o Android tem.
 * Uma vez por dia, ao conectar, procura versão nova do app e avisa numa notificação. No modo chamado, o Zé ouve o "Ei Zé" como no microfone do PC; o botão do fone (ou
 * "Falar" na notificação) abre o pedido e, de novo, envia. Cai a rede: tenta de novo, com espera
 * crescente, até a pessoa desconectar.
 */
public final class VozService extends Service {
    static final String LIGAR = "ligar";
    static final String FALAR = "falar";
    static final String MODO = "modo";
    static final String DESLIGAR = "desligar";
    static final String AJUSTAR = "ajustar"; // a tela mudou o modo ou o microfone

    private static final long DIA_MS = 24L * 60 * 60 * 1000;

    private static final int TAXA = 16000;
    private static final int QUADRO = 2560; // 80 ms a 16 kHz, 16 bits
    private static final long[] ESPERAS_MS = {2000, 5000, 15000, 30000, 60000};
    private static final String CANAL = "voz";
    private static final int AVISO = 1;
    private static final int VERSAO_NOVA = 2;

    private final Handler principal = new Handler(Looper.getMainLooper());
    private final ExecutorService tocar = Executors.newSingleThreadExecutor();
    private Ajustes ajustes;
    private OkHttpClient cliente;
    private volatile WebSocket ws;
    private AudioManager audio;
    private AudioRecord gravador;
    private AcousticEchoCanceler semEco;
    private String modoDaConexao = "";
    private Thread captura;
    private AudioTrack falante;
    private int taxaFala;
    private MediaSession sessao;
    private PowerManager.WakeLock acordado;
    private volatile boolean ligado;
    private volatile boolean falando; // o pedido aberto pelo botão (apertar) ainda não foi enviado
    private int quedas;
    private volatile boolean chamada; // a fala vai como numa ligação (fone Bluetooth com microfone)
    private final AudioDeviceCallback aparelhos = new AudioDeviceCallback() {
        @Override
        public void onAudioDevicesAdded(AudioDeviceInfo[] novos) { escolherSaida(); }

        @Override
        public void onAudioDevicesRemoved(AudioDeviceInfo[] saidos) { escolherSaida(); }
    };
    private String estado = "Conectando…";

    static boolean ehBotao(int tecla) {
        return tecla == KeyEvent.KEYCODE_HEADSETHOOK
                || tecla == KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE
                || tecla == KeyEvent.KEYCODE_MEDIA_PLAY
                || tecla == KeyEvent.KEYCODE_MEDIA_PAUSE;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        ajustes = new Ajustes(this);
        audio = getSystemService(AudioManager.class);
        cliente = new OkHttpClient.Builder()
                .pingInterval(20, TimeUnit.SECONDS)
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .build();
        NotificationManager avisos = getSystemService(NotificationManager.class);
        NotificationChannel canal = new NotificationChannel(CANAL, "Voz com o Zé", NotificationManager.IMPORTANCE_LOW);
        canal.setShowBadge(false);
        avisos.createNotificationChannel(canal);
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int id) {
        String acao = intent != null && intent.getAction() != null ? intent.getAction() : LIGAR;
        switch (acao) {
            case DESLIGAR:
                desligar();
                return START_NOT_STICKY;
            case FALAR:
                if (ligado) falar();
                return START_STICKY;
            case MODO:
                ajustes.trocarModo();
                ajustar();
                return START_STICKY;
            case AJUSTAR:
                if (ligado) ajustar();
                return START_STICKY;
            default:
                if (!ligado) ligar();
                return START_STICKY;
        }
    }

    private void ligar() {
        if (!ajustes.pareado()) {
            stopSelf();
            return;
        }
        ligado = true;
        startForeground(AVISO, aviso(), ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE);
        acordado = getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "ze-voz:voz");
        acordado.acquire();
        escolherSaida();
        audio.registerAudioDeviceCallback(aparelhos, principal);
        sessao = new MediaSession(this, "ze-voz");
        sessao.setCallback(new MediaSession.Callback() {
            @Override
            @SuppressWarnings("deprecation")
            public boolean onMediaButtonEvent(Intent botao) {
                KeyEvent tecla = botao.getParcelableExtra(Intent.EXTRA_KEY_EVENT);
                if (tecla != null && tecla.getAction() == KeyEvent.ACTION_DOWN && ehBotao(tecla.getKeyCode())) {
                    falar();
                    return true;
                }
                return super.onMediaButtonEvent(botao);
            }
        });
        // "Tocando": o Android manda o botão do fone para a sessão de mídia ativa mais recente.
        sessao.setPlaybackState(new PlaybackState.Builder()
                .setActions(PlaybackState.ACTION_PLAY_PAUSE | PlaybackState.ACTION_PLAY | PlaybackState.ACTION_PAUSE)
                .setState(PlaybackState.STATE_PLAYING, 0, 1f)
                .build());
        sessao.setActive(true);
        conectar();
    }

    /** A tela mudou algo: o modo novo vale numa conexão nova; o microfone, na hora. */
    private void ajustar() {
        escolherSaida();
        mostrar(estado);
        if (ws != null && !ajustes.modo().equals(modoDaConexao)) ws.close(1000, "modo");
    }

    /** Fone Bluetooth com microfone: como numa ligação. Senão, ou com o aparelho marcado
     * "microfone do celular": a fala como mídia, que vai ao aparelho Bluetooth, ao fone com fio ou
     * ao alto-falante (no modo de ligação, iria ao fone da orelha do celular). Chamado ao ligar, a
     * cada aparelho que entra ou sai e quando a tela muda o microfone. */
    private void escolherSaida() {
        if (!ligado) return;
        String aparelho = Rota.aparelho(audio);
        boolean fone = aparelho != null && Rota.temMicrofone(audio) && !ajustes.microfoneDoCelular(aparelho);
        if (fone) {
            audio.setMode(AudioManager.MODE_IN_COMMUNICATION);
            usarFoneBluetooth(true);
        } else {
            usarFoneBluetooth(false);
            audio.setMode(AudioManager.MODE_NORMAL);
        }
        if (fone == chamada) return;
        chamada = fone;
        tocar.execute(() -> {
            if (falante == null) return;
            int taxa = taxaFala;
            falante.release();
            falante = null;
            prepararFala(taxa); // o tipo do áudio decide a saída: refaz o falante no meio da fala
        });
    }

    private void usarFoneBluetooth(boolean usar) {
        if (Build.VERSION.SDK_INT >= 31) {
            if (!usar) {
                audio.clearCommunicationDevice();
                return;
            }
            for (AudioDeviceInfo d : audio.getAvailableCommunicationDevices()) {
                if (d.getType() == AudioDeviceInfo.TYPE_BLUETOOTH_SCO || d.getType() == AudioDeviceInfo.TYPE_BLE_HEADSET) {
                    audio.setCommunicationDevice(d);
                    return;
                }
            }
        } else {
            legadoBluetooth(usar);
        }
    }

    @SuppressWarnings("deprecation")
    private void legadoBluetooth(boolean usar) {
        if (usar) {
            audio.startBluetoothSco();
            audio.setBluetoothScoOn(true);
        } else {
            audio.setBluetoothScoOn(false);
            audio.stopBluetoothSco();
        }
    }

    private void conectar() {
        if (!ligado) return;
        mostrar("Conectando…");
        String endereco = ajustes.endereco().replaceFirst("^http", "ws");
        Request pedido = new Request.Builder()
                .url(endereco + "/voz-app/ws")
                .header("Authorization", "Bearer " + ajustes.chave())
                .build();
        ws = cliente.newWebSocket(pedido, new WebSocketListener() {
            @Override
            public void onOpen(WebSocket s, Response resposta) {
                try {
                    modoDaConexao = ajustes.modo();
                    s.send(new JSONObject().put("taxa", TAXA).put("modo", modoDaConexao).toString());
                } catch (JSONException erro) {
                    s.close(1011, "json");
                    return;
                }
                quedas = 0;
                falando = false;
                principal.post(() -> mostrar(Ajustes.AO_VIVO.equals(modoDaConexao) ? "Ao vivo" : "Diga “Ei Zé” ou toque em Falar"));
                gravar(s);
                procurarVersao();
            }

            @Override
            public void onMessage(WebSocket s, String texto) {
                try {
                    JSONObject m = new JSONObject(texto);
                    String tipo = m.optString("tipo");
                    if ("voz".equals(tipo)) {
                        int taxa = m.optInt("taxa", 22050);
                        tocar.execute(() -> prepararFala(taxa));
                    } else if ("parar".equals(tipo)) {
                        tocar.execute(() -> { if (falante != null) { falante.pause(); falante.flush(); falante.play(); } });
                    }
                } catch (JSONException ignorado) {
                    // outra mensagem de controle: nada a fazer
                }
            }

            @Override
            public void onMessage(WebSocket s, ByteString pedaco) {
                byte[] pcm = pedaco.toByteArray();
                tocar.execute(() -> { if (falante != null) falante.write(pcm, 0, pcm.length); });
            }

            @Override
            public void onClosing(WebSocket s, int codigo, String motivo) {
                s.close(1000, null);
            }

            @Override
            public void onClosed(WebSocket s, int codigo, String motivo) {
                caiu(s, false);
            }

            @Override
            public void onFailure(WebSocket s, Throwable erro, Response resposta) {
                boolean recusado = resposta != null && resposta.code() == 403;
                caiu(s, recusado);
            }
        });
    }

    private void gravar(WebSocket s) {
        pararCaptura();
        int minimo = AudioRecord.getMinBufferSize(TAXA, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
        try {
            gravador = new AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, TAXA,
                    AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, Math.max(minimo, QUADRO * 4));
        } catch (SecurityException semPermissao) {
            principal.post(() -> mostrar("Sem permissão do microfone"));
            return;
        }
        AudioRecord este = gravador;
        // A fala do Zé na caixa de som volta pelo microfone do celular: o cancelamento de eco tira.
        if (AcousticEchoCanceler.isAvailable()) {
            semEco = AcousticEchoCanceler.create(este.getAudioSessionId());
            if (semEco != null) semEco.setEnabled(true);
        }
        captura = new Thread(() -> {
            byte[] quadro = new byte[QUADRO];
            este.startRecording();
            while (ligado && s == ws && !Thread.currentThread().isInterrupted()) {
                int lidos = este.read(quadro, 0, QUADRO);
                if (lidos > 0) s.send(ByteString.of(quadro, 0, lidos));
            }
        }, "ze-voz-microfone");
        captura.start();
    }

    private void pararCaptura() {
        if (captura != null) captura.interrupt();
        captura = null;
        if (semEco != null) {
            semEco.release();
            semEco = null;
        }
        if (gravador != null) {
            try { gravador.stop(); } catch (IllegalStateException ignorado) { /* já parado */ }
            gravador.release();
            gravador = null;
        }
    }

    private void prepararFala(int taxa) {
        if (falante != null && taxa == taxaFala) return;
        if (falante != null) falante.release();
        taxaFala = taxa;
        int minimo = AudioTrack.getMinBufferSize(taxa, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT);
        falante = new AudioTrack.Builder()
                .setAudioAttributes(new AudioAttributes.Builder()
                        .setUsage(chamada ? AudioAttributes.USAGE_VOICE_COMMUNICATION : AudioAttributes.USAGE_MEDIA)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build())
                .setAudioFormat(new AudioFormat.Builder()
                        .setSampleRate(taxa)
                        .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                        .build())
                .setBufferSizeInBytes(Math.max(minimo, taxa)) // meio segundo: o Zé manda até 0,5 s adiantado
                .setTransferMode(AudioTrack.MODE_STREAM)
                .build();
        falante.play();
    }

    private void caiu(WebSocket s, boolean recusado) {
        if (s != ws) return; // uma conexão antiga
        ws = null;
        pararCaptura();
        if (!ligado) return;
        if (recusado) {
            ajustes.esquecer();
            principal.post(() -> { mostrar("Pareie de novo no painel do Zé"); desligar(); });
            return;
        }
        long espera = ESPERAS_MS[Math.min(quedas, ESPERAS_MS.length - 1)];
        quedas++;
        principal.post(() -> mostrar("Sem conexão: de novo em " + espera / 1000 + " s"));
        principal.postDelayed(this::conectar, espera);
    }

    /** Uma vez por dia: se há versão nova do app, uma notificação abre a tela para atualizar. */
    private void procurarVersao() {
        long agora = System.currentTimeMillis();
        if (agora - ajustes.procurouEm() < DIA_MS) return;
        ajustes.procurou(agora);
        new Thread(() -> {
            try {
                long publicada = Atualizacao.publicada();
                if (publicada <= Atualizacao.instalada(this)) return;
                Intent abrir = new Intent(this, MainActivity.class).setAction(MainActivity.ATUALIZAR);
                Notification nova = new Notification.Builder(this, CANAL)
                        .setSmallIcon(R.drawable.ic_ze)
                        .setContentTitle("Atualização do Zé Voz")
                        .setContentText("Versão 0.1." + publicada + " disponível. Toque para atualizar.")
                        .setAutoCancel(true)
                        .setContentIntent(PendingIntent.getActivity(this, 4, abrir, PendingIntent.FLAG_IMMUTABLE))
                        .build();
                getSystemService(NotificationManager.class).notify(VERSAO_NOVA, nova);
            } catch (java.io.IOException semRede) {
                // tenta de novo amanhã
            }
        }, "ze-voz-versao").start();
    }

    /** O botão: a primeira vez abre o pedido (como apertar o botão do painel); a segunda envia. */
    private void falar() {
        WebSocket s = ws;
        if (s == null) return;
        falando = !falando;
        s.send(falando ? "{\"tipo\":\"apertar\"}" : "{\"tipo\":\"soltar\"}");
        mostrar(falando ? "Ouvindo… toque em Enviar" : "Enviado");
    }

    private void desligar() {
        ligado = false;
        principal.removeCallbacksAndMessages(null);
        WebSocket s = ws;
        ws = null;
        if (s != null) s.close(1000, "desligado");
        pararCaptura();
        tocar.execute(() -> { if (falante != null) { falante.release(); falante = null; } });
        if (sessao != null) { sessao.release(); sessao = null; }
        audio.unregisterAudioDeviceCallback(aparelhos);
        usarFoneBluetooth(false);
        audio.setMode(AudioManager.MODE_NORMAL);
        if (acordado != null && acordado.isHeld()) acordado.release();
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    private void mostrar(String texto) {
        estado = texto;
        if (ligado) getSystemService(NotificationManager.class).notify(AVISO, aviso());
    }

    private Notification aviso() {
        boolean aoVivo = Ajustes.AO_VIVO.equals(ajustes.modo());
        return new Notification.Builder(this, CANAL)
                .setSmallIcon(R.drawable.ic_ze)
                .setContentTitle("Zé conectado")
                .setContentText(estado)
                .setOngoing(true)
                .setCategory(Notification.CATEGORY_CALL)
                .setContentIntent(PendingIntent.getActivity(this, 5, new Intent(this, MainActivity.class), PendingIntent.FLAG_IMMUTABLE))
                .addAction(new Notification.Action.Builder(null, falando ? "Enviar" : "Falar", acao(FALAR, 1)).build())
                .addAction(new Notification.Action.Builder(null, aoVivo ? "Usar “Ei Zé”" : "Ao vivo", acao(MODO, 2)).build())
                .addAction(new Notification.Action.Builder(null, "Desconectar", acao(DESLIGAR, 3)).build())
                .build();
    }

    private PendingIntent acao(String qual, int codigo) {
        Intent intent = new Intent(this, VozService.class).setAction(qual);
        return PendingIntent.getService(this, codigo, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }

    @Override
    public void onDestroy() {
        if (ligado) desligar();
        tocar.shutdown();
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
