export interface Topic {
  label: string;
  // Palavras que indicam que o tópico apareceu na resposta (texto sem acento).
  match: RegExp;
}

export interface Question {
  id: string;
  // Rótulo curto usado nas listas e no painel do assessor.
  short: string;
  text: string;
  required: boolean;
  // Roteiro da resposta: o que o cliente deve abordar ao falar ou escrever.
  topics: Topic[];
  // Escolha rápida que entra no cálculo do perfil (0, 1 ou 2 pontos, na ordem).
  quick?: { label: string; options: string[] };
}

// As obrigatórias vêm primeiro: definem o perfil e liberam a plataforma.
export const QUESTIONS: Question[] = [
  {
    id: "objetivos",
    short: "Objetivos",
    required: true,
    text: "O que você quer conquistar com seus investimentos?",
    quick: {
      label: "Quando pretende usar a maior parte desse dinheiro?",
      options: ["Em menos de 2 anos", "Entre 2 e 5 anos", "Depois de 5 anos"],
    },
    topics: [
      {
        label: "Seu objetivo principal",
        match: /aposent|casa|imovel|apartamento|viag|faculdade|estud|renda|independencia|carro|negocio|patrimonio|filh/,
      },
      { label: "Quanto precisa juntar", match: /r\$|reais|\bmil\b|milh/ },
      { label: "Em quanto tempo", match: /\bano|\bmes|prazo|20\d\d/ },
      {
        label: "O que não pode dar errado",
        match: /nao posso|nao quero|medo|preocup|risco|garant|seguranca|perder/,
      },
    ],
  },
  {
    id: "experiencia",
    short: "Experiência",
    required: true,
    text: "Com o que você já investiu até hoje?",
    quick: {
      label: "Qual destes descreve melhor sua experiência?",
      options: ["Poupança e renda fixa", "Fundos e ações", "Derivativos, cripto ou exterior"],
    },
    topics: [
      {
        label: "Produtos que já teve",
        match: /poupanca|cdb|tesouro|lci|lca|fundo|acao|acoes|fii|cripto|bitcoin|previdencia|etf|debenture/,
      },
      { label: "Há quanto tempo investe", match: /\bano|\bmes|desde|tempo|comecei|recente/ },
      {
        label: "Como decide onde investir",
        match: /assessor|gerente|sozinh|pesquis|indica|banco|corretora|decid|estud|video/,
      },
      { label: "Perdas que já teve", match: /perd|prejuizo|caiu|queda/ },
    ],
  },
  {
    id: "risco",
    short: "Risco",
    required: true,
    text: "Como você reage quando seus investimentos oscilam?",
    quick: {
      label: "Se sua carteira caísse 10% em um mês, o que você faria?",
      options: [
        "Resgataria para não perder mais",
        "Esperaria a recuperação",
        "Aproveitaria para investir mais",
      ],
    },
    topics: [
      { label: "Quanto aceita perder em um ano", match: /%|por cento|perder|perda|aceit|toler/ },
      {
        label: "Quanto precisa ter à mão para resgatar rápido",
        match: /resgat|liquidez|dispon|sacar|emergencia|rapido|a mao/,
      },
      {
        label: "Como se sentiu em quedas passadas",
        match: /senti|nervos|tranquil|ansios|dorm|medo|calm|preocup/,
      },
    ],
  },
  {
    id: "renda",
    short: "Renda",
    required: false,
    text: "Como é a sua renda hoje?",
    topics: [
      {
        label: "De onde vem",
        match: /salario|clt|empresa|autonom|aposentad|aluguel|pro.?labore|negocio|freela|servidor|pensao|dividendo/,
      },
      { label: "Quanto entra por mês", match: /r\$|reais|\bmil\b|\d/ },
      {
        label: "Se é estável ou varia",
        match: /estavel|variavel|\bfix[ao]|comiss|bonus|oscila|incert|garantid|varia/,
      },
      { label: "Quanto consegue guardar", match: /guard|sobr|poup|invist|aport|economiz/ },
    ],
  },
  {
    id: "gastos",
    short: "Gastos e dívidas",
    required: false,
    text: "Quais são seus principais gastos e compromissos?",
    topics: [
      {
        label: "Despesas fixas do mês",
        match: /despesa|gasto|conta|aluguel|condominio|escola|plano de saude|custo/,
      },
      {
        label: "Dívidas e financiamentos",
        match: /divida|financiament|emprestimo|parcela|cartao|consorcio/,
      },
      { label: "Quem depende de você", match: /filh|espos|marid|dependente|\bpai|\bmae|familia|sozinh/ },
      {
        label: "Grandes gastos previstos",
        match: /compra|reforma|viagem|casamento|faculdade|troca|previs|planej|ano que vem/,
      },
    ],
  },
  {
    id: "patrimonio",
    short: "Patrimônio",
    required: false,
    text: "O que você já tem guardado ou investido, aqui e em outros lugares?",
    topics: [
      { label: "Reserva de emergência", match: /reserva|emergencia/ },
      {
        label: "Investimentos em outros bancos e corretoras",
        match: /banco|corretora|poupanca|cdb|tesouro|fundo|acoes|previdencia/,
      },
      {
        label: "Imóveis e outros bens",
        match: /imovel|casa|apartamento|terreno|carro|veiculo|sitio|empresa/,
      },
      { label: "Previdência e seguros", match: /previdencia|pgbl|vgbl|seguro/ },
    ],
  },
  {
    id: "vida",
    short: "Vida e família",
    required: false,
    text: "O que mais sua assessoria deveria saber sobre você?",
    topics: [
      { label: "Planos de família", match: /filh|familia|casament|neto|aposent|mudanca/ },
      { label: "Datas importantes", match: /aniversario|data|20\d\d|mes de/ },
      {
        label: "O que gosta de fazer",
        match: /gost|hobby|viaj|esporte|corr|time|torc|leitura|cozinh|pesca/,
      },
    ],
  },
];

export const REQUIRED = QUESTIONS.filter((q) => q.required);

const normalize = (text: string) =>
  text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");

// Checagem simples por palavras-chave; o backend pode trocar por extração com LLM.
export function coveredTopics(question: Question, text: string): boolean[] {
  const plain = normalize(text);
  return question.topics.map((t) => t.match.test(plain));
}
