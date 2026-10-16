export const PAGE_TOPICS = [
  { id: 'general', name: 'Różne wiadomości', description: 'Uniwersalna strona z kilkoma tematami.', section: 'Wiadomości' },
  { id: 'events', name: 'Wydarzenia', description: 'Relacja z ważnego wydarzenia lub dnia.', section: 'Wydarzenia' },
  { id: 'politics', name: 'Polityka', description: 'Fakty, decyzje i ich konsekwencje.', section: 'Polityka' },
  { id: 'science', name: 'Nauka', description: 'Odkrycia i wyjaśnienia bez sensacji.', section: 'Nauka' },
  { id: 'celebrities', name: 'Gwiazdy i celebryci', description: 'Ludzie, kultura popularna i zdjęcia.', section: 'Ludzie' },
  { id: 'economy', name: 'Gospodarka', description: 'Rynek, praca i liczby w kontekście.', section: 'Gospodarka' },
  { id: 'sports', name: 'Sport', description: 'Wyniki, rywalizacja i bohaterowie.', section: 'Sport' },
  { id: 'culture', name: 'Kultura', description: 'Sztuka, książki i recenzje.', section: 'Kultura' },
  { id: 'practical', name: 'Porady i program', description: 'Zestawienia i informacje do szybkiego znalezienia.', section: 'Poradnik' },
] as const;

export type PageTopic = typeof PAGE_TOPICS[number]['id'];
