// As datas do chat e do sino (ADR 0139): o dia pelo nome ("Hoje", "Ontem", "Segunda-feira, 23 de
// novembro") e a data completa da hora. Fora da abertura: o chat e o sino carregam depois dela.

const SEMANA = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"];
const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const dois = (/** @type {number} */ n) => String(n).padStart(2, "0");

/** O dia de uma data, AAAA-MM-DD, no relógio do aparelho. @param {Date} [d] */
export const diaDe = (d = new Date()) => `${d.getFullYear()}-${dois(d.getMonth() + 1)}-${dois(d.getDate())}`;

/** "Hoje", "Ontem", "Segunda-feira, 23 de novembro" e, de outro ano, com o ano.
 * @param {string} dia AAAA-MM-DD @param {string} [hoje] AAAA-MM-DD; o do Zé, quando se sabe */
export function rotuloDia(dia, hoje = diaDe()) {
  if (dia === hoje) return "Hoje";
  const d = new Date(`${dia}T12:00:00`), h = new Date(`${hoje}T12:00:00`);
  if (Math.round((h.getTime() - d.getTime()) / 864e5) === 1) return "Ontem";
  const nome = `${SEMANA[d.getDay()]}, ${d.getDate()} de ${MESES[d.getMonth()]}`;
  return d.getFullYear() === h.getFullYear() ? nome : `${nome} de ${d.getFullYear()}`;
}

/** "25/11/2026 às 14:32", de um horário do Zé ("2026-11-25T14:32:10-03:00"). @param {string} iso */
export const dataCompleta = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)} às ${iso.slice(11, 16)}`;

/** O mesmo, de um epoch em segundos (os itens do sino). @param {number} s */
export function dataDoEpoch(s) {
  const d = new Date(s * 1000);
  return `${dois(d.getDate())}/${dois(d.getMonth() + 1)}/${d.getFullYear()} às ${dois(d.getHours())}:${dois(d.getMinutes())}`;
}
