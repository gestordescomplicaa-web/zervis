// Página voz, carregada sob demanda.
PAGINAS.voz = async function() {
    const [e, o, r, s] = await Promise.all([api("estado"), api("escuta"), api("remoto"), api("sintese")]);
    const etiqueta = (ok, sim, nao) => `<span class="etiqueta ${ok ? "bom" : "alerta"}">${ok ? sim : nao}</span>`;
    const linha = (titulo, estado, texto) => cartao("", `<div class="cabeca"><h2>${titulo}</h2>${estado}</div>${sub(texto)}`);
    return `${cabeca("Voz")}
      ${cartaoSintese(s)}
      ${cartao("", `<div class="cabeca"><h2>Modo de fala</h2><span class="etiqueta bom">${esc(nomeModo(e.modo_fala))}</span></div>
        ${sub("Quando o Zé fala sem você pedir. Atalho: Alt+M.")}
        <div class="modos-fala" role="radiogroup" aria-label="Modo de fala">${MODOS_FALA.map((m) => `<button type="button" role="radio" class="modo" data-acao="modo-fala" data-modo="${m.valor}" aria-checked="${m.valor === e.modo_fala}"><strong>${m.nome}</strong><small>${m.detalhe}</small></button>`).join("")}</div>`)}
      ${cartao("", `<div class="cabeca"><h2>WhatsApp</h2>${etiqueta(e.whatsapp.ligado, "Ligado", e.whatsapp.disponivel ? "Desligado" : "Indisponível")}</div>
        ${sub("Avisa quando um lead quer comprar.")}
        <div class="linha">${botao(e.whatsapp.ligado ? "Desligar" : "Ligar", "whatsapp", `data-ligar="${e.whatsapp.ligado ? "" : 1}" ${e.whatsapp.disponivel ? "" : "disabled"}`)}</div>`)}
      ${cartao("", `<div class="cabeca"><h2>Escuta</h2><span class="etiqueta bom">${esc(nomeEscuta(e.escuta.modo))}</span></div>
        ${sub("Quando o chamado “Ei Zé” funciona.")}
        <div class="modos-fala" role="radiogroup" aria-label="Escuta">${MODOS_ESCUTA.map((m) => { const sem = m.valor === "janela" && !e.escuta.janela; return `<button type="button" role="radio" class="modo" data-acao="escuta-modo" data-modo="${m.valor}" aria-checked="${m.valor === e.escuta.modo}" ${sem ? "disabled" : ""}><strong>${m.nome}</strong><small>${sem ? "Requer Hyprland." : m.detalhe}</small></button>`; }).join("")}</div>`)}
      ${cartao("", `<div class="cabeca"><h2>Ativação</h2><span class="etiqueta bom">${e.chamado === "botao" ? "Só o botão" : "“Ei Zé”"}</span></div>
        ${sub("Como chamar o Zé no microfone deste computador. O botão vale nos dois.")}
        <div class="modos-fala" role="radiogroup" aria-label="Ativação">${[["voz", "“Ei Zé”", "O chamado falado ou o botão."], ["botao", "Só o botão", "Ouve só com o botão apertado. A voz conectada continua ao vivo."]].map(([v, n, d]) => `<button type="button" role="radio" class="modo" data-acao="chamado-modo" data-modo="${v}" aria-checked="${v === e.chamado}"><strong>${n}</strong><small>${d}</small></button>`).join("")}</div>`)}
      ${cartao("", `<div class="cabeca"><h2>Espera</h2><span class="etiqueta bom">${ESPERAS.find((m) => m[0] === e.espera)?.[1] || "Normal"}</span></div>
        ${sub("Quanto o Zé espera, depois de uma pausa, para responder.")}
        <div class="modos-fala" role="radiogroup" aria-label="Espera">${ESPERAS.map(([v, n, d]) => `<button type="button" role="radio" class="modo" data-acao="espera-modo" data-modo="${v}" aria-checked="${v === e.espera}"><strong>${n}</strong><small>${d}</small></button>`).join("")}</div>`)}
      ${cartao("", `<div class="cabeca"><h2>Acesso pelo celular</h2></div>
        ${sub("O Zé no navegador do celular, em casa ou fora. Exige senha e código do autenticador.")}
        <div class="linha"><label>Senha de acesso${r.senha ? " (definida)" : ""}<input id="senha-acesso" type="password" autocomplete="new-password" placeholder="${r.senha ? "Nova senha" : "Mínimo de 8 caracteres"}"></label>${botao("Salvar senha", "senha-salvar")}</div>
        <div class="parte"><div class="cabeca"><h3 class="subtitulo">Código do autenticador</h3>${etiqueta(r.codigo, "Ligado", "Desligado")}</div>
          ${codigoPreparado ? `<div class="acesso-qr">${codigoPreparado.qr}<div class="campos"><p>Leia com o aplicativo autenticador (Google Authenticator, Aegis…) ou digite a chave:</p><p class="mono">${esc(codigoPreparado.chave)}</p>
            <div class="linha"><label>Código de 6 dígitos<input id="codigo-confirmar" inputmode="numeric" autocomplete="one-time-code" maxlength="7"></label>${botao("Confirmar", "codigo-confirmar", "", "principal")}</div></div></div>`
            : `<div class="linha">${r.codigo ? botao("Desligar", "codigo-desligar", "", "discreta") : botao("Ligar", "codigo-preparar", r.senha ? "" : "disabled")}</div>`}</div>
        <div class="parte"><div class="cabeca"><h3 class="subtitulo">Acesso de qualquer lugar</h3>${etiqueta(!!r.tunel.endereco, "Ativo", "Inativo")}</div>
          ${r.tunel.endereco ? `<div class="acesso-qr">${r.tunel.qr}<div class="campos"><p>Aponte a câmera do celular para o código, ou abra:</p><p class="mono">${esc(r.tunel.endereco)}</p><p class="nota">${r.tunel.fixo ? "Endereço fixo, no seu domínio." : "O endereço muda quando o computador reinicia."}</p></div></div>`
            : `<p class="nota">${r.senha && r.codigo ? "Abre um endereço seguro pelo Cloudflare, para o Wi-Fi e o 4G." : "Requer a senha e o código do autenticador ligados."}</p>`}
          <div class="linha">${r.tunel.ativo ? botao("Copiar endereço", "remoto-copiar", `data-endereco="${esc(r.tunel.endereco)}"`) + botao("Desativar", "tunel-desativar", "", "discreta") : botao("Ativar", "tunel-ativar", r.senha && r.codigo ? "" : "disabled", "principal")}</div>
          ${r.senha && r.codigo ? enderecoFixo(r.tunel) : ""}</div>
        ${r.lista.length ? `<div class="parte"><h3 class="subtitulo">Aparelhos conectados</h3>${r.lista.map((a) => `<div class="linha aparelho"><span>${esc(a.aparelho)}</span><small>${new Date(a.desde * 1000).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" })}${a.origem ? ` · ${esc(a.origem)}` : ""}</small>${botao("Desconectar", "aparelho-desconectar", `data-id="${esc(a.id)}"`, "discreta")}</div>`).join("")}</div>` : ""}
        ${r.instalado ? `<div class="parte"><h3 class="subtitulo">Rede privada (Tailscale)</h3>${sub(r.ativo ? `Ativa em <span class="mono">${esc(r.endereco)}</span>` : "Alternativa ao túnel, para quem já usa o Tailscale.")}
          ${r.ativo && r.firewall ? `<p class="aviso">Libere a voz no firewall: <span class="mono">${esc(r.firewall)}</span></p>` : ""}
          ${r.conectado ? `<div class="linha">${r.ativo ? botao("Desativar", "remoto-desativar", "", "discreta") : botao("Ativar", "remoto-ativar")}</div>` : ""}</div>` : ""}`)}
      ${appVoz(r)}
      ${linha("Palavra de ativação", etiqueta(o.ativacao, "Ativa", "Não treinada"), o.ativacao ? "“Ei Zé”." : "“Ei Zé”. Necessária para os comandos de voz.")}
      ${linha("Reconhecimento de fala", etiqueta(o.deepgram.tem, "Configurado", "Não configurado"), o.deepgram.tem ? "Deepgram." : 'Deepgram. Configure em <a href="#modelos">Modelos</a>.')}`;
  };

/** Quem fala as respostas: o Cadu (local) ou o ElevenLabs (nuvem), com a chave e a voz.
 * @param {{motor: string, chave: {tem: boolean, fim: string}, voz: string, nome: string, vozes: {id: string, nome: string, detalhe: string}[], caracteres_hoje: number, erro: string, cadastro: string}} s */
function cartaoSintese(s) {
  const nuvem = s.motor === "elevenlabs";
  const opcoes = [["piper", "Cadu", "Local e grátis. Funciona sem internet."],
    ["elevenlabs", "ElevenLabs", s.chave.tem ? "Voz mais natural, na nuvem. Paga por caractere." : "Cole a chave abaixo para usar."]];
  const vozes = s.vozes.map((v) => `<option value="${esc(v.id)}" ${v.id === s.voz ? "selected" : ""}>${esc(v.nome)}${v.detalhe ? " · " + esc(v.detalhe) : ""}</option>`).join("");
  return cartao("", `<div class="cabeca"><h2>Voz do Zé</h2><span class="etiqueta bom">${nuvem ? esc(s.nome || "ElevenLabs") : "Cadu"}</span><a class="externo" href="${esc(s.cadastro)}" target="_blank" rel="noopener">Obter chave do ElevenLabs ↗</a></div>
    ${sub("Quem fala as respostas. Se o ElevenLabs falhar, o Cadu fala no lugar.")}
    <div class="modos-fala" role="radiogroup" aria-label="Voz do Zé">${opcoes.map(([v, n, d]) => `<button type="button" role="radio" class="modo" data-acao="sintese-motor" data-motor="${v}" aria-checked="${v === s.motor}" ${v === "elevenlabs" && !s.chave.tem ? "disabled" : ""}><strong>${n}</strong><small>${d}</small></button>`).join("")}</div>
    <div class="linha"><input id="chave-sintese" type="password" class="mono" placeholder="${s.chave.tem ? "•••• " + esc(s.chave.fim) : "Chave de API do ElevenLabs"}" autocomplete="off" spellcheck="false" aria-label="Chave de API do ElevenLabs">
      ${botao("Salvar", "sintese-chave", "", s.chave.tem ? "" : "principal")}${s.chave.tem ? botao("Remover", "sintese-apagar", "", "discreta") : ""}</div>
    ${s.chave.tem && vozes ? `<div class="linha"><label>Voz<select id="voz-sintese">${vozes}</select></label>${botao("Usar e ouvir", "sintese-voz")}</div>` : ""}
    ${s.erro ? `<p class="aviso">${esc(s.erro)}</p>` : ""}
    ${s.chave.tem ? `<p class="nota">Hoje: ${s.caracteres_hoje.toLocaleString("pt-BR")} caracteres pelo ElevenLabs.</p>` : ""}`);
}

/** O túnel fixo num domínio da pessoa: colar o comando do Cloudflare e dizer o endereço.
 * @param {{fixo: string, porta: number}} t */
function enderecoFixo(t) {
  if (t.fixo) return `<p class="nota">Endereço fixo: <span class="mono">${esc(t.fixo)}</span> ${botao("Voltar ao automático", "tunel-rapido", "", "discreta")}</p>`;
  return `<details class="detalhes" id="fixo-detalhes"><summary>Usar um endereço fixo (um domínio seu no Cloudflare)</summary>
    <ol class="passos-fixo">
      <li>No Cloudflare: <strong>Zero Trust → Networks → Tunnels → Create a tunnel</strong>, tipo <strong>Cloudflared</strong>, com um nome (por exemplo, ze).</li>
      <li>Copie o comando de instalação que ele mostra e cole abaixo. Não precisa rodar o comando.</li>
      <li>Em <strong>Public Hostname</strong>, escolha o subdomínio (ze) e o domínio; em Service, <strong>HTTP</strong> e <span class="mono">127.0.0.1:${t.porta}</span>.</li>
    </ol>
    <label>Comando do Cloudflare<textarea id="fixo-colado" rows="3" placeholder="cloudflared service install eyJhIjoi…" spellcheck="false"></textarea></label>
    <div class="linha"><label>Endereço<input id="fixo-endereco" placeholder="ze.seudominio.com.br" autocomplete="off" spellcheck="false"></label>${botao("Salvar e ligar", "tunel-fixar", "", "principal")}</div>
    <p class="resultado" id="resultado-fixo"></p></details>`;
}

/** O código de pareamento do app de voz que está na tela (some ao recarregar a página).
 * @type {{codigo: string, endereco: string, qr: string} | null} */
let codigoApp = null;
const APK_VOZ = "https://github.com/gestordescomplicaa-web/zervis/releases/download/app-voz/ze-voz.apk";

/** O app de voz do Android: pareado com a câmera do celular, abre só a voz. */
function appVoz(r) {
  const aparelhos = r.app_voz || [];
  const lista = aparelhos.map((a) => `<div class="linha aparelho"><span>${esc(a.nome)}</span><small>${a.uso ? "usado " + new Date(a.uso * 1000).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "pareado"}</small>${botao("Remover", "app-voz-remover", `data-id="${esc(a.id)}"`, "discreta")}</div>`).join("");
  const pareando = codigoApp ? `<div class="acesso-qr">${codigoApp.qr}<div class="campos"><p>Com o app instalado, aponte a <strong>câmera</strong> do celular para o código: o Android abre o app e ele pareia sozinho.</p>
      <p class="nota">Ou, no app, digite o endereço e o código: <span class="mono">${esc(codigoApp.endereco)}</span> · <span class="mono">${esc(codigoApp.codigo)}</span>. Vale 10 minutos, uma vez.</p></div></div>` : "";
  return cartao("", `<div class="cabeca"><h2>App de voz (Android)</h2>${aparelhos.length ? '<span class="etiqueta bom">Pareado</span>' : ""}</div>
    ${sub("Fale com o Zé com o celular bloqueado, no bolso, pelo fone. Sem tela: uma notificação com Falar e Desconectar.")}
    <p class="nota">Instale no celular: <a href="${APK_VOZ}" target="_blank" rel="noopener">baixar o ze-voz.apk</a>.</p>
    ${pareando}
    <div class="linha">${botao(codigoApp ? "Gerar outro código" : "Parear celular", "app-voz-parear", r.tunel.endereco ? "" : "disabled", aparelhos.length ? "" : "principal")}</div>
    ${r.tunel.endereco ? "" : '<p class="nota">Requer o acesso de qualquer lugar ativo (acima).</p>'}
    ${lista ? `<div class="parte"><h3 class="subtitulo">Celulares pareados</h3>${lista}</div>` : ""}`);
}

Object.assign(ACOES, {
  "sintese-chave": async (b) => { const r = await ocupado(b, () => api("sintese/chave", { chave: valorCampo("chave-sintese").value })); toast(r.aviso); await abrir(); },
  "sintese-apagar": (b) => confirmar(b, "Remover a chave do ElevenLabs?", async () => { const r = await api("sintese/apagar", {}); toast(r.aviso); await abrir(); }),
  "sintese-motor": async (b) => { const r = await ocupado(b, () => api("sintese/escolher", { motor: b.dataset.motor })); toast(r.aviso); await abrir(); },
  "sintese-voz": async (b) => { const r = await ocupado(b, () => api("sintese/escolher", { motor: "elevenlabs", voz: valorCampo("voz-sintese").value })); toast(r.aviso); await abrir(); },
  "app-voz-parear": async (b) => { codigoApp = await ocupado(b, () => api("voz-app/codigo", {})); await abrir(); },
  "app-voz-remover": (b) => confirmar(b, "Remover este celular?", async () => { const r = await api("voz-app/remover", { id: b.dataset.id }); toast(r.aviso); await abrir(); }),
});

