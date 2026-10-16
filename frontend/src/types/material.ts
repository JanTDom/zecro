import { StyleBlend } from './dna';

export type EditorialRole = 
  | 'kicker' 
  | 'headline' 
  | 'deck' 
  | 'lead' 
  | 'body' 
  | 'byline' 
  | 'pullquote' 
  | 'caption' 
  | 'subhead'
  | 'infographic'
  | 'dateline';

export interface StoryMaterial {
  id: string;
  role: 'lead-story' | 'secondary' | 'sidebar' | 'brief' | 'anchor';
  importance: number; // 1 to 5 stars
  kicker: string;
  headline: string;
  deck: string;
  lead: string;
  body: string;
  byline: string;
  dateline: string;
  pullQuote?: string;
  wordCount: number;
}

export interface PhotoMaterial {
  id: string;
  storyId?: string;
  url: string;
  previewUrl: string;
  caption: string;
  credit: string;
  importance: number; // 1 to 5
  autoCutout: boolean; // auto background removal
  hasCutoutMask?: boolean;
  alphaMaskUrl?: string;
  widthPx?: number;
  heightPx?: number;
  dpi?: number;
  sourceFile?: File;
  cutoutContourPoints?: [number, number][];
  aspectRatio?: number; // width / height, when known from metadata
  focalPoint?: [number, number]; // important subject position, normalized
  focalStatus?: 'ready' | 'uncertain' | 'unavailable';
  focalSubjectKind?: 'person' | 'object' | 'scene' | 'uncertain';
  placementHint: 'lead-hero' | 'top-banner' | 'sidebar' | 'floating-island' | 'bleed';
  allowTextWrap: boolean;
}

export interface IntakeData {
  projectId: string;
  pageTopic?: import('../pageTopics').PageTopic;
  editorialMood?: 'auto' | 'urgent' | 'human' | 'solemn' | 'celebratory' | 'analytical' | 'practical' | 'scandal' | 'entertainment';
  pageZone?: 'front_page' | 'spread' | 'back_page';
  styleBlend?: StyleBlend;
  seed?: number;
  editionDate: string;
  pageNumber: number;
  section: string;
  leadStory: StoryMaterial;
  secondaryStories: StoryMaterial[];
  photos: PhotoMaterial[];
  /** TV guide schedule rows (station, HH:MM, title …). */
  tvSchedule?: { station: string; time: string; title: string; genre?: string; description?: string; highlight?: boolean }[];
  generationConfig: {
    candidateCount: number;
    tensionTarget: number; // 1 to 15
    explorationTemp: number; // 0.1 to 1.0
    allowCutouts: boolean;
    prioritizeNovelty: boolean;
    visualReview?: boolean;
    copyReview?: boolean;
    acceptWeakPhotos?: boolean;
    placeholderCopy?: boolean;
  };
}
