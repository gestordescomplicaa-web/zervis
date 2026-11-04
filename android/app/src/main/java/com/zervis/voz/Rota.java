package com.zervis.voz;

import android.media.AudioDeviceInfo;
import android.media.AudioManager;

/** Os aparelhos de áudio conectados: o Bluetooth (o nome, para lembrar a escolha, e se tem
 * microfone) e o fone com fio. */
final class Rota {
    private Rota() {}

    private static boolean bluetooth(int tipo) {
        return tipo == AudioDeviceInfo.TYPE_BLUETOOTH_A2DP
                || tipo == AudioDeviceInfo.TYPE_BLUETOOTH_SCO
                || tipo == AudioDeviceInfo.TYPE_BLE_HEADSET
                || tipo == AudioDeviceInfo.TYPE_BLE_SPEAKER;
    }

    /** O nome do aparelho Bluetooth de áudio conectado, ou null sem nenhum. */
    static String aparelho(AudioManager audio) {
        for (AudioDeviceInfo d : audio.getDevices(AudioManager.GET_DEVICES_OUTPUTS)) {
            if (bluetooth(d.getType())) {
                CharSequence nome = d.getProductName();
                return nome != null && nome.length() > 0 ? nome.toString() : "Bluetooth";
            }
        }
        return null;
    }

    /** Um fone com fio (ou USB) plugado. */
    static boolean temFio(AudioManager audio) {
        for (AudioDeviceInfo d : audio.getDevices(AudioManager.GET_DEVICES_OUTPUTS)) {
            int tipo = d.getType();
            if (tipo == AudioDeviceInfo.TYPE_WIRED_HEADSET || tipo == AudioDeviceInfo.TYPE_WIRED_HEADPHONES
                    || tipo == AudioDeviceInfo.TYPE_USB_HEADSET) {
                return true;
            }
        }
        return false;
    }

    /** O aparelho Bluetooth tem microfone (o perfil de ligação: fone, ou caixa com viva-voz)? */
    static boolean temMicrofone(AudioManager audio) {
        for (AudioDeviceInfo d : audio.getDevices(AudioManager.GET_DEVICES_INPUTS)) {
            if (d.getType() == AudioDeviceInfo.TYPE_BLUETOOTH_SCO || d.getType() == AudioDeviceInfo.TYPE_BLE_HEADSET) {
                return true;
            }
        }
        return false;
    }
}
