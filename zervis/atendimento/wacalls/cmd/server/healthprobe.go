package main

import (
	"fmt"
	"net"
	"net/http"
	"os"
	"strings"
	"time"
)

// probeHealth consulta o servidor HTTP local e devolve o código de saída do
// healthcheck: 0 quando o processo ainda atende, 1 quando não.
//
// A imagem é distroless (sem shell, wget ou curl), então a sonda precisa ser o
// próprio binário. Só o que já estava vivo antes responde: um processo travado
// deixa de aceitar a conexão e o Swarm consegue substituí-lo — o mesmo modo de
// falha que motivou o healthcheck do agente ("no worker is available").
func probeHealth(addr string) int {
	url := "http://" + healthProbeTarget(addr) + "/"
	client := &http.Client{Timeout: 3 * time.Second}
	resp, err := client.Get(url)
	if err != nil {
		fmt.Fprintf(os.Stderr, "healthcheck: %v\n", err)
		return 1
	}
	defer resp.Body.Close()
	// Qualquer resposta HTTP prova que o servidor está roteando. Exigir 200 no
	// "/" ataria a sonda à presença do cliente estático, que é opcional.
	if resp.StatusCode >= 500 {
		fmt.Fprintf(os.Stderr, "healthcheck: HTTP %d\n", resp.StatusCode)
		return 1
	}
	return 0
}

// healthProbeTarget transforma o endereço de escuta em um destino conectável.
// `-addr` costuma vir como ":8080" ou "0.0.0.0:8080"; nenhum dos dois serve como
// host de uma requisição, e 0.0.0.0 como destino falha em alguns ambientes.
func healthProbeTarget(addr string) string {
	host, port, err := net.SplitHostPort(strings.TrimSpace(addr))
	if err != nil {
		return "127.0.0.1:8080"
	}
	if host == "" || host == "0.0.0.0" || host == "::" || host == "[::]" {
		host = "127.0.0.1"
	}
	if port == "" {
		port = "8080"
	}
	return net.JoinHostPort(host, port)
}
