package com.zervis.voz;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;

import org.json.JSONObject;

/**
 * Uma ligação do WhatsApp que pede você (ADR 0066): alguém liga, conversa com o agente e pede para
 * falar com você. O Zé manda {"tipo":"ligacao","estado":...} e aqui vira uma notificação:
 *
 * - "chamando": quem é e o assunto, com "Atender" e "Agora não" (o Zé também pergunta falando);
 * - "em_curso": a ligação passou para o celular, com "Encerrar" (a voz vai pelo canal do Zé, no
 *   modo de ligação do aparelho, que tira o eco);
 * - "fim": some.
 */
final class Ligacao {
    static final String CANAL = "ligacao";
    static final String ATENDER = "ligacao_atender";
    static final String RECUSAR = "ligacao_recusar";
    static final String ENCERRAR = "ligacao_encerrar";
    static final String ID = "id";

    private static final int NOTIFICACAO = 20;

    private Ligacao() {
    }

    static void criarCanal(Context c) {
        NotificationChannel canal = new NotificationChannel(CANAL, "Ligações", NotificationManager.IMPORTANCE_HIGH);
        canal.setDescription("Quem está na linha e quer falar com você.");
        c.getSystemService(NotificationManager.class).createNotificationChannel(canal);
    }

    static void mostrar(Context c, JSONObject m) {
        NotificationManager avisos = c.getSystemService(NotificationManager.class);
        String estado = m.optString("estado");
        String id = m.optString(ID);
        if ("fim".equals(estado) || id.isEmpty()) {
            apagar(c);
            return;
        }
        String nome = m.optString("nome", "Um contato");
        Notification.Builder b = new Notification.Builder(c, CANAL)
                .setSmallIcon(R.drawable.ic_ze)
                .setCategory(Notification.CATEGORY_CALL)
                .setVisibility(Notification.VISIBILITY_PRIVATE)
                .setPublicVersion(new Notification.Builder(c, CANAL)
                        .setSmallIcon(R.drawable.ic_ze)
                        .setContentTitle("Ligação no WhatsApp")
                        .build());
        if ("em_curso".equals(estado)) {
            b.setContentTitle("Em ligação")
                    .setContentText(nome)
                    .setOngoing(true)
                    .setUsesChronometer(true)
                    .setOnlyAlertOnce(true)
                    .addAction(new Notification.Action.Builder(null, "Encerrar", paraOZe(c, ENCERRAR, id)).build());
        } else {
            String assunto = m.optString("assunto");
            b.setContentTitle(nome + " quer falar com você")
                    .setContentText(assunto)
                    .setStyle(new Notification.BigTextStyle().bigText(assunto))
                    .setTimeoutAfter(60_000) // a pessoa não espera mais que isso na linha
                    .addAction(new Notification.Action.Builder(null, "Atender", paraOZe(c, ATENDER, id)).build())
                    .addAction(new Notification.Action.Builder(null, "Agora não", paraOZe(c, RECUSAR, id)).build());
        }
        avisos.notify(NOTIFICACAO, b.build());
    }

    static void apagar(Context c) {
        c.getSystemService(NotificationManager.class).cancel(NOTIFICACAO);
    }

    private static PendingIntent paraOZe(Context c, String acao, String id) {
        Intent intent = new Intent(c, VozService.class)
                .setAction(acao)
                .setData(Uri.parse("zervis-voz://ligacao/" + Uri.encode(id)))
                .putExtra(ID, id);
        return PendingIntent.getService(c, 0, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
    }
}
