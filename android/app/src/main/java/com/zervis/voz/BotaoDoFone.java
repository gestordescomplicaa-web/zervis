package com.zervis.voz;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.view.KeyEvent;

/** O botão do fone (play/pause, o botão único): falar e enviar, pelo serviço. */
public final class BotaoDoFone extends BroadcastReceiver {
    @Override
    @SuppressWarnings("deprecation") // a versão com a classe é do Android 13; o app vai do 11
    public void onReceive(Context contexto, Intent intent) {
        KeyEvent tecla = intent.getParcelableExtra(Intent.EXTRA_KEY_EVENT);
        if (tecla != null && tecla.getAction() == KeyEvent.ACTION_DOWN && VozService.ehBotao(tecla.getKeyCode())) {
            contexto.startService(new Intent(contexto, VozService.class).setAction(VozService.FALAR));
        }
    }
}
