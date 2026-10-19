// A página de volta do login de um conector: a aba que o painel abriu fecha sozinha.
// Se o navegador não deixar, fica o link para o painel.
if (document.currentScript?.dataset.ok === "1") setTimeout(() => window.close(), 1500);
