// Página voz, carregada sob demanda.
PAGINAS.voz = async function() {
    const [e, o, r] = await Promise.all([api("estado"), api("escuta"), api("remoto")]);
    const etiqueta = (ok, sim, nao) => `<span class="etiqueta ${ok ? "bom" : "alerta"}">${ok ? sim : nao}</span>`;
    const linha = (titulo, estado, texto) => cartao("", `<div class="cabeca"><h2>${titulo}</h2>${estado}</div>${sub(texto)}`);
    return `${cabeca("Voz")}
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
      ${linha("Palavra de ativação", etiqueta(o.ativacao, "Ativa", "Não treinada"), o.ativacao ? "“Ei Zé”." : "“Ei Zé”. Necessária para os comandos de voz.")}
      ${linha("Reconhecimento de fala", etiqueta(o.deepgram.tem, "Configurado", "Não configurado"), o.deepgram.tem ? "Deepgram." : 'Deepgram. Configure em <a href="#modelos">Modelos</a>.')}
      ${linha("Síntese de voz", etiqueta(true, "Ativa", ""), "Piper, voz Cadu (pt-BR). Processamento local.")}`;
  };

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

