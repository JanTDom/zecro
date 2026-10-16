import type { StyleBlend } from './types/dna';
import type { EditorialCharacter } from './types/project';

export interface EditorialStyle {
  id: Exclude<EditorialCharacter, 'serious' | 'popular'>;
  name: string;
  description: string;
  example: string;
  archetype: 'quality_press' | 'mass_market' | 'tabloid' | 'editorial_magazine' | 'tv_guide';
  blend: StyleBlend;
  headlineFont: string;
  bodyFont: string;
  energy: number;
  group: 'ogólne' | 'tematyczne';
}

// These are editable starting points for TitleDNA, never page templates.
export const EDITORIAL_STYLES: EditorialStyle[] = [
  { id: 'analysis', name: 'Wiadomości i analizy', description: 'Spokojna hierarchia, więcej miejsca na tekst i wyjaśnienia.', example: 'Gdy ważne są fakty i kontekst.', archetype: 'quality_press', blend: { opinion_to_tabloid: .10, classical_to_avantgarde: .20, dense_to_photo: .25 }, headlineFont: 'PT Serif, Georgia, serif', bodyFont: 'PT Serif, Georgia, serif', energy: .55, group: 'ogólne' },
  { id: 'midmarket', name: 'Gazeta środka', description: 'Równowaga faktów i formy: wyraziste tytuły, infografiki, dobra fotografia i rzetelny tekst bez krzykliwości.', example: 'Dla nowoczesnych dzienników i tygodników (styl compact / mid-market).', archetype: 'mass_market', blend: { opinion_to_tabloid: .45, classical_to_avantgarde: .35, dense_to_photo: .50 }, headlineFont: 'PT Serif, Georgia, serif', bodyFont: 'Inter, Arial, sans-serif', energy: .75, group: 'ogólne' },
  { id: 'everyday', name: 'Popularna codzienna', description: 'Krótsze teksty, wyraźne tytuły i szybka orientacja na stronie.', example: 'Dla szerokiego grona czytelników.', archetype: 'mass_market', blend: { opinion_to_tabloid: .58, classical_to_avantgarde: .40, dense_to_photo: .55 }, headlineFont: 'Roboto Condensed, Arial Narrow, sans-serif', bodyFont: 'Inter, Arial, sans-serif', energy: .85, group: 'ogólne' },
  { id: 'tabloid', name: 'Bulwarowa', description: 'Mocne tytuły, duże zdjęcia i bardzo dynamiczny rytm.', example: 'Gdy strona ma przyciągać wzrok.', archetype: 'tabloid', blend: { opinion_to_tabloid: .90, classical_to_avantgarde: .75, dense_to_photo: .82 }, headlineFont: 'Roboto Condensed, Arial Narrow, sans-serif', bodyFont: 'Inter, Arial, sans-serif', energy: 1.20, group: 'ogólne' },
  { id: 'magazine', name: 'Magazyn i reportaż', description: 'Więcej oddechu, mocne fotografie i elegancka typografia.', example: 'Dla dłuższych historii i wywiadów.', archetype: 'editorial_magazine', blend: { opinion_to_tabloid: .45, classical_to_avantgarde: .60, dense_to_photo: .72 }, headlineFont: 'PT Serif, Georgia, serif', bodyFont: 'PT Serif, Georgia, serif', energy: 1.0, group: 'ogólne' },
  { id: 'guide', name: 'Program TV i poradnik', description: 'Ramówki, stałe rubryki i informacje, które łatwo znaleźć.', example: 'Dla przewodnika telewizyjnego, kalendarza lub porad.', archetype: 'tv_guide', blend: { opinion_to_tabloid: .40, classical_to_avantgarde: .15, dense_to_photo: .35 }, headlineFont: 'Inter, Arial, sans-serif', bodyFont: 'Inter, Arial, sans-serif', energy: .70, group: 'ogólne' },
  { id: 'business', name: 'Biznes i gospodarka', description: 'Dane, kontekst i czytelne podziały informacji.', example: 'Dla rynku, pracy i finansów.', archetype: 'quality_press', blend: { opinion_to_tabloid: .16, classical_to_avantgarde: .28, dense_to_photo: .18 }, headlineFont: 'PT Serif, Georgia, serif', bodyFont: 'Inter, Arial, sans-serif', energy: .62, group: 'tematyczne' },
  { id: 'sports', name: 'Sportowa', description: 'Wyniki, bohaterowie i dynamiczne zdjęcia.', example: 'Dla wydarzeń i analiz sportowych.', archetype: 'mass_market', blend: { opinion_to_tabloid: .68, classical_to_avantgarde: .55, dense_to_photo: .78 }, headlineFont: 'Roboto Condensed, Arial Narrow, sans-serif', bodyFont: 'Inter, Arial, sans-serif', energy: 1.02, group: 'tematyczne' },
  { id: 'science', name: 'Nauka i technologia', description: 'Wyjaśnienia, dane i przejrzyste ilustracje.', example: 'Dla odkryć i nowych technologii.', archetype: 'editorial_magazine', blend: { opinion_to_tabloid: .22, classical_to_avantgarde: .43, dense_to_photo: .44 }, headlineFont: 'PT Serif, Georgia, serif', bodyFont: 'Inter, Arial, sans-serif', energy: .78, group: 'tematyczne' },
  { id: 'culture', name: 'Kultura i styl życia', description: 'Reportaże, recenzje i dużo miejsca na obrazy.', example: 'Dla sztuki, książek i życia codziennego.', archetype: 'editorial_magazine', blend: { opinion_to_tabloid: .42, classical_to_avantgarde: .67, dense_to_photo: .68 }, headlineFont: 'PT Serif, Georgia, serif', bodyFont: 'PT Serif, Georgia, serif', energy: .95, group: 'tematyczne' },
];

export function editorialStyle(id?: EditorialCharacter): EditorialStyle {
  const normalized = id === 'serious' ? 'analysis' : id === 'popular' ? 'tabloid' : id === 'local' ? 'midmarket' : id;
  return EDITORIAL_STYLES.find(style => style.id === normalized) || EDITORIAL_STYLES[0];
}

export function exactStyleForBlend(blend?: StyleBlend): EditorialStyle | undefined {
  if (!blend) return undefined;
  return EDITORIAL_STYLES.find(style =>
    Math.abs(style.blend.opinion_to_tabloid - blend.opinion_to_tabloid) < .011 &&
    Math.abs(style.blend.classical_to_avantgarde - blend.classical_to_avantgarde) < .011 &&
    Math.abs(style.blend.dense_to_photo - blend.dense_to_photo) < .011);
}
