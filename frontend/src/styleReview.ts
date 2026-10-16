import type { Candidate } from './types/generation';

export type StyleReviewState = 'candidate_for_editor' | 'needs_revision' | 'unreviewed';

export function styleReviewState(candidate: Candidate): StyleReviewState {
  const review = candidate.visualReview;
  if (!review || review.status === 'unavailable' || review.status === 'failed') return 'unreviewed';
  if (review.category_review?.status) return review.category_review.status;
  // Older saved runs predate the explicit review contract. Reinterpret them
  // conservatively so a former 50% pass cannot look publication-ready.
  if ((review.style_fidelity ?? 0) >= .9 && (review.score ?? 0) >= .8 &&
      !(review.category_mismatch?.length)) return 'candidate_for_editor';
  return 'needs_revision';
}
